#!/usr/bin/env python3
"""Approval-gated 120-second replay worker for score-channel confirmation.

The worker accepts only a frozen replay shard and a separately frozen approval
receipt.  It emits no candidate code or raw stdout/stderr; only parsed signals,
byte counts, and cryptographic hashes are append-only checkpointed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


PROTOCOL = "score-channel-replay-result-v1"
ROW_SCHEMA = "score-channel-replay-result-row-v1"
MANIFEST_SCHEMA = "score-channel-replay-candidate-v1"
APPROVAL_PROTOCOL = "score-channel-replay-approval-v1"
CAP_SECONDS = 120
SIF = Path(
    "/research/d7/spc/yzyang4/aira-dojo/build/superimage/"
    "superimage.root.2026-07-macos-v1.sif"
)
DEFAULT_DATA = Path("/research/d7/spc/yzyang4/mle-bench-data")
DEFAULT_GRADER = Path("/research/d7/spc/yzyang4/venvs/exp/bin/mlebench")
DEFAULT_HF_CACHE = Path("/research/d7/spc/yzyang4/scratch/hf_cache")
DEFAULT_WORK = Path("/tmp/score_channel_replay_work")
PROXY = "http://137.189.90.241:8000/"
NVVM_SOURCE = Path("/usr/lib/x86_64-linux-gnu/libnvidia-nvvm.so.4")
OPENCL_VENDOR = Path("/etc/OpenCL/vendors/nvidia.icd")

MANIFEST_KEYS = {
    "schema_version", "card_id", "competition", "task", "run_id", "parent",
    "code", "code_sha256", "source_intake", "selection_rank_in_run",
    "shard_id", "cap_seconds",
}
RESULT_KEYS = {
    "schema_version", "card_id", "competition", "task", "run_id", "parent",
    "source_intake", "selection_rank_in_run", "shard_id", "cap_seconds",
    "code_sha256", "rc", "wall_seconds", "stdout_val", "val_how",
    "stdout_bytes", "stderr_bytes", "stdout_sha256", "stderr_sha256",
    "sub_exists", "submission_bytes", "submission_sha256",
    "submission_line_count", "submission_header_sha256", "grader_rc",
    "sub_score", "grader_output_sha256", "execution_attempts",
    "manifest_sha256", "approval_sha256", "worker_source_commit",
}
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer\s+[A-Za-z0-9._-]{20,}|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY)"
)
KEYED = re.compile(
    r"(?i)\b(?:val(?:idation)?|cv|oof|dev|holdout)[^\n=:]{0,40}?"
    r"(?:score|acc(?:uracy)?|auc|rmse|rmsle|mae|logloss|log[- ]?loss|loss|f1|kappa|"
    r"map@?\d*|pearson|spearman|rho|corr)"
    r"[^\n0-9]{0,24}?(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
)
BARE = re.compile(
    r"(?i)\b(?:score|accuracy|auc|logloss|kappa|f1)\s*[=:]\s*"
    r"(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
)
SCORE_RE = re.compile(r'"?score"?\s*[=:]\s*([-+0-9.eE]+)')


class ReplayError(RuntimeError):
    """Fail-closed replay contract error."""


def canonical(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            state.update(block)
    return state.hexdigest()


def artifact_stats(path: Path) -> tuple[int, str, int, str]:
    state = hashlib.sha256()
    total = 0
    newlines = 0
    last = b""
    header = bytearray()
    header_done = False
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            state.update(block)
            total += len(block)
            newlines += block.count(b"\n")
            last = block[-1:]
            if not header_done:
                before, separator, _ = block.partition(b"\n")
                header.extend(before)
                header_done = bool(separator)
                if len(header) > 1024 * 1024:
                    raise ReplayError("submission header exceeds 1 MiB")
    line_count = 0 if total == 0 else newlines + int(last != b"\n")
    return total, state.hexdigest(), line_count, sha256_bytes(bytes(header).rstrip(b"\r"))


def valid_sha(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value.lower())
    ):
        raise ReplayError(f"invalid {label}")
    return value.lower()


def valid_commit(value: Any) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value.lower())
    ):
        raise ReplayError("invalid source commit")
    return value.lower()


def repository_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    value = result.stdout.strip().lower()
    if result.returncode or len(value) != 40:
        raise ReplayError("cannot resolve worker repository commit")
    return value


def finite_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        canonical(value)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise ReplayError(f"cannot read canonical {label}") from error
    if not isinstance(value, dict):
        raise ReplayError(f"{label} is not an object")
    return value


def read_rows(path: Path, label: str, *, allow_empty: bool = False) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ReplayError(f"cannot read {label}") from error
    if not lines and not allow_empty:
        raise ReplayError(f"{label} is empty")
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(lines, 1):
        if not line:
            raise ReplayError(f"blank line in {label}")
        try:
            row = json.loads(line)
            canonical(row)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise ReplayError(f"invalid {label} line {number}") from error
        if not isinstance(row, dict):
            raise ReplayError(f"non-object {label} line {number}")
        rows.append(row)
    return rows


def parse_val(text: str) -> tuple[float | None, str | None]:
    match = None
    for candidate in KEYED.finditer(text):
        match = candidate
    if match is not None:
        value = float(match.group(1))
        return (value, "keyed") if math.isfinite(value) else (None, None)
    for candidate in BARE.finditer(text):
        match = candidate
    if match is not None:
        value = float(match.group(1))
        return (value, "bare") if math.isfinite(value) else (None, None)
    return None, None


def load_manifest(path: Path, expected_sha: str) -> tuple[list[dict[str, Any]], int, str]:
    expected_sha = valid_sha(expected_sha, "manifest SHA")
    if sha256_file(path) != expected_sha:
        raise ReplayError("manifest SHA mismatch")
    rows = read_rows(path, "replay manifest")
    cards: set[str] = set()
    shard_ids: set[int] = set()
    for row in rows:
        if set(row) != MANIFEST_KEYS or row.get("schema_version") != MANIFEST_SCHEMA:
            raise ReplayError("replay manifest row schema mismatch")
        card = row.get("card_id")
        task = row.get("task")
        code = row.get("code")
        shard_id = row.get("shard_id")
        if (
            not isinstance(card, str) or not card or card in cards
            or not isinstance(task, str) or not task or row.get("competition") != task
            or not isinstance(row.get("run_id"), str) or not row["run_id"]
            or not isinstance(row.get("parent"), str) or not row["parent"]
            or not isinstance(row.get("source_intake"), str) or not row["source_intake"]
            or isinstance(row.get("selection_rank_in_run"), bool)
            or not isinstance(row.get("selection_rank_in_run"), int)
            or row["selection_rank_in_run"] not in {1, 2}
            or not isinstance(code, str) or not code
            or isinstance(shard_id, bool) or not isinstance(shard_id, int) or shard_id not in range(4)
            or row.get("cap_seconds") != CAP_SECONDS
        ):
            raise ReplayError("invalid replay identity, shard, code, or cap")
        if sha256_bytes(code.encode("utf-8")) != valid_sha(row.get("code_sha256"), "code SHA"):
            raise ReplayError("candidate code SHA mismatch")
        if CREDENTIAL.search(code.encode("utf-8")):
            raise ReplayError("credential-shaped candidate code")
        cards.add(card)
        shard_ids.add(shard_id)
    if len(shard_ids) != 1:
        raise ReplayError("a worker manifest must contain exactly one shard")
    return rows, next(iter(shard_ids)), expected_sha


def load_approval(
    path: Path, expected_sha: str, manifest_sha: str, shard_id: int, source_commit: str,
) -> tuple[dict[str, Any], str]:
    expected_sha = valid_sha(expected_sha, "approval SHA")
    if sha256_file(path) != expected_sha:
        raise ReplayError("approval SHA mismatch")
    approval = read_object(path, "approval receipt")
    if (
        approval.get("protocol") != APPROVAL_PROTOCOL
        or approval.get("approved") is not True
        or approval.get("cap_seconds") != CAP_SECONDS
        or approval.get("gpus_per_shard") != 1
        or approval.get("shards") != 4
        or approval.get("base_llm_update") is not False
        or approval.get("llm_api_calls") != 0
        or approval.get("worker_source_commit") != source_commit
        or approval.get("online_hf") is not True
        or approval.get("fresh_workspace_per_candidate") is not True
    ):
        raise ReplayError("approval matrix contract mismatch")
    shard_hashes = approval.get("shard_sha256")
    if not isinstance(shard_hashes, dict) or shard_hashes.get(str(shard_id)) != manifest_sha:
        raise ReplayError("approval does not bind this shard")
    valid_sha(approval.get("replay_manifest_sha256"), "full replay manifest SHA")
    valid_sha(approval.get("replay_summary_sha256"), "replay summary SHA")
    if (
        isinstance(approval.get("planned_candidate_replays"), bool)
        or not isinstance(approval.get("planned_candidate_replays"), int)
        or approval["planned_candidate_replays"] <= 0
        or not finite_number(approval.get("cap_upper_bound_gpu_hours"))
        or float(approval["cap_upper_bound_gpu_hours"]) <= 0
        or not isinstance(approval.get("user_approval_recorded_at_utc"), str)
        or not approval["user_approval_recorded_at_utc"]
    ):
        raise ReplayError("approval accounting is incomplete")
    return approval, expected_sha


def verify_environment(
    approval: dict[str, Any], data_dir: Path, grader: Path,
) -> None:
    if not SIF.is_file() or not grader.is_file() or not data_dir.is_dir():
        raise ReplayError("approved container, grader, or data root is missing")
    image_stat = SIF.stat()
    if (
        approval.get("container_image_path") != str(SIF)
        or approval.get("container_image_size") != image_stat.st_size
        or approval.get("container_image_mtime_ns") != image_stat.st_mtime_ns
        or approval.get("data_dir") != str(data_dir)
        or approval.get("grader_path") != str(grader)
        or approval.get("grader_sha256") != sha256_file(grader)
    ):
        raise ReplayError("runtime environment differs from the approved binding")


def validate_result(row: dict[str, Any], manifest: dict[str, Any], manifest_sha: str, approval_sha: str, source_commit: str) -> None:
    if set(row) != RESULT_KEYS or row.get("schema_version") != ROW_SCHEMA:
        raise ReplayError("result row schema mismatch")
    for key in (
        "card_id", "competition", "task", "run_id", "parent", "source_intake",
        "selection_rank_in_run", "shard_id", "cap_seconds", "code_sha256",
    ):
        if row.get(key) != manifest.get(key):
            raise ReplayError(f"result/manifest mismatch for {key}")
    if row.get("manifest_sha256") != manifest_sha or row.get("approval_sha256") != approval_sha:
        raise ReplayError("result binding SHA mismatch")
    if row.get("worker_source_commit") != source_commit:
        raise ReplayError("result worker commit mismatch")
    if row.get("val_how") not in {None, "keyed", "bare"}:
        raise ReplayError("invalid parser type")
    if finite_number(row.get("stdout_val")) != (row.get("val_how") in {"keyed", "bare"}):
        raise ReplayError("stdout value/parser mismatch")
    if finite_number(row.get("sub_score")) and row.get("sub_exists") is not True:
        raise ReplayError("finite external score without a submission")
    if not isinstance(row.get("sub_exists"), bool):
        raise ReplayError("invalid submission-exists flag")
    if isinstance(row.get("rc"), bool) or not isinstance(row.get("rc"), int):
        raise ReplayError("invalid candidate return code")
    if row.get("grader_rc") is not None and (
        isinstance(row.get("grader_rc"), bool) or not isinstance(row.get("grader_rc"), int)
    ):
        raise ReplayError("invalid grader return code")
    for key in (
        "stdout_bytes", "stderr_bytes", "submission_bytes", "submission_line_count",
        "execution_attempts",
    ):
        if isinstance(row.get(key), bool) or not isinstance(row.get(key), int) or row[key] < 0:
            raise ReplayError(f"invalid nonnegative integer {key}")
    for key in ("stdout_sha256", "stderr_sha256"):
        valid_sha(row.get(key), key)
    for key in ("submission_sha256", "submission_header_sha256", "grader_output_sha256"):
        if row.get(key) is not None:
            valid_sha(row[key], key)
    if row["sub_exists"] is False and any(
        row.get(key) is not None
        for key in (
            "submission_sha256", "submission_header_sha256", "grader_rc", "sub_score",
            "grader_output_sha256",
        )
    ):
        raise ReplayError("submission-absent result contains grader fields")
    if row["sub_exists"] is False and row["submission_bytes"] != 0:
        raise ReplayError("submission-absent result has nonzero bytes")
    if row["sub_exists"] is False and row["submission_line_count"] != 0:
        raise ReplayError("submission-absent result has nonzero lines")
    if row["sub_exists"] is True and any(
        row.get(key) is None
        for key in (
            "submission_sha256", "submission_header_sha256", "grader_rc",
            "grader_output_sha256",
        )
    ):
        raise ReplayError("submission-present result lacks artifact or grader receipt")
    if not finite_number(row.get("wall_seconds")) or float(row["wall_seconds"]) < 0:
        raise ReplayError("invalid wall time")


def load_done(path: Path, manifests: dict[str, dict[str, Any]], manifest_sha: str, approval_sha: str, source_commit: str) -> set[str]:
    if not path.exists():
        return set()
    done: set[str] = set()
    for row in read_rows(path, "existing replay results", allow_empty=True):
        card = row.get("card_id")
        if card not in manifests or card in done:
            raise ReplayError("existing result is extra or duplicated")
        validate_result(row, manifests[card], manifest_sha, approval_sha, source_commit)
        done.add(card)
    return done


def safe_workspace(base: Path, card_id: str) -> Path:
    base = base.resolve()
    if base in {Path("/").resolve(), Path.home().resolve()}:
        raise ReplayError("unsafe work root")
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    name = "candidate_" + sha256_bytes(card_id.encode("utf-8"))[:24]
    path = (base / name).resolve()
    if path.parent != base or path == base:
        raise ReplayError("unsafe candidate workspace")
    return path


def prepare_nvfix(base: Path) -> Path:
    base = base.resolve()
    if not NVVM_SOURCE.is_file() or not OPENCL_VENDOR.is_file():
        raise ReplayError("job-10533 NVIDIA/OpenCL compatibility files are missing")
    root = (base / "nvfix").resolve()
    if root.parent != base:
        raise ReplayError("unsafe NVIDIA compatibility path")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = root / NVVM_SOURCE.name
    if not target.is_file() or sha256_file(target) != sha256_file(NVVM_SOURCE):
        shutil.copy2(NVVM_SOURCE, target)
    return root


def append_result(path: Path, row: dict[str, Any]) -> None:
    payload = (canonical(row) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        remaining = memoryview(payload)
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise ReplayError("short append to replay checkpoint")
            remaining = remaining[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def run_one(
    manifest: dict[str, Any], *, manifest_sha: str, approval_sha: str,
    source_commit: str, data_dir: Path, grader: Path, hf_cache: Path, work_root: Path,
    nvfix: Path,
) -> dict[str, Any]:
    card = manifest["card_id"]
    task = manifest["task"]
    workspace = safe_workspace(work_root, card)
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(mode=0o700)
    try:
        (workspace / "solution.py").write_text(manifest["code"], encoding="utf-8")
        public = data_dir / task / "prepared" / "public"
        if not public.is_dir() or not SIF.is_file() or not grader.is_file():
            raise ReplayError("container, grader, or public task data is missing")
        hf_cache.mkdir(parents=True, exist_ok=True)
        binds = f"{workspace}:/workspace,{public}:/workspace/data:ro,{hf_cache}:/hf"
        command = [
            "timeout", "--signal=KILL", str(CAP_SECONDS), "singularity", "exec",
            "--containall", "--cleanenv", "--nv", "--pwd", "/workspace",
            "--bind", binds,
            "--bind", f"{OPENCL_VENDOR}:{OPENCL_VENDOR}",
            "--bind", f"{nvfix}:/mnt",
            str(SIF), "env",
            "PYTHONUNBUFFERED=1", "WANDB_DISABLED=1", "TQDM_DISABLE=1",
            "TF_CPP_MIN_LOG_LEVEL=3", "HOME=/tmp", "HF_HOME=/hf", "TORCH_HOME=/hf/torch",
            "HF_HUB_OFFLINE=0", f"http_proxy={PROXY}", f"https_proxy={PROXY}",
            "HF_HUB_DISABLE_XET=1", "LD_LIBRARY_PATH=/mnt:/.singularity.d/libs",
            "python", "solution.py",
        ]
        attempts = 1
        overall_started = time.monotonic()
        attempt_started = overall_started
        process = subprocess.run(command, capture_output=True)
        if process.returncode == 255 and time.monotonic() - attempt_started < 3:
            time.sleep(20)
            attempts = 2
            process = subprocess.run(command, capture_output=True)
        wall = time.monotonic() - overall_started
        stdout = process.stdout or b""
        stderr = process.stderr or b""
        combined = stdout.decode("utf-8", errors="replace") + "\n" + stderr.decode("utf-8", errors="replace")
        stdout_val, val_how = parse_val(combined)

        submission = workspace / "submission.csv"
        sub_exists = submission.is_file()
        if sub_exists:
            submission_bytes, submission_sha, submission_lines, submission_header_sha = artifact_stats(submission)
        else:
            submission_bytes, submission_sha, submission_lines, submission_header_sha = 0, None, 0, None
        grader_rc: int | None = None
        sub_score: float | None = None
        grader_output_sha: str | None = None
        if sub_exists:
            try:
                graded = subprocess.run(
                    [str(grader), "grade-sample", str(submission), task, "--data-dir", str(data_dir)],
                    capture_output=True, timeout=600,
                )
                grader_rc = graded.returncode
                grader_blob = (graded.stdout or b"") + b"\n" + (graded.stderr or b"")
                grader_output_sha = sha256_bytes(grader_blob)
                decoded = grader_blob.decode("utf-8", errors="replace")
                match = SCORE_RE.search(decoded)
                if match is not None:
                    candidate = float(match.group(1))
                    if math.isfinite(candidate):
                        sub_score = candidate
            except subprocess.TimeoutExpired as error:
                grader_rc = 124
                blob = (error.stdout or b"") + b"\n" + (error.stderr or b"")
                grader_output_sha = sha256_bytes(blob)

        return {
            "schema_version": ROW_SCHEMA,
            "card_id": card,
            "competition": manifest["competition"],
            "task": task,
            "run_id": manifest["run_id"],
            "parent": manifest["parent"],
            "source_intake": manifest["source_intake"],
            "selection_rank_in_run": manifest["selection_rank_in_run"],
            "shard_id": manifest["shard_id"],
            "cap_seconds": CAP_SECONDS,
            "code_sha256": manifest["code_sha256"],
            "rc": process.returncode,
            "wall_seconds": round(wall, 6),
            "stdout_val": stdout_val,
            "val_how": val_how,
            "stdout_bytes": len(stdout),
            "stderr_bytes": len(stderr),
            "stdout_sha256": sha256_bytes(stdout),
            "stderr_sha256": sha256_bytes(stderr),
            "sub_exists": sub_exists,
            "submission_bytes": submission_bytes,
            "submission_sha256": submission_sha,
            "submission_line_count": submission_lines,
            "submission_header_sha256": submission_header_sha,
            "grader_rc": grader_rc,
            "sub_score": sub_score,
            "grader_output_sha256": grader_output_sha,
            "execution_attempts": attempts,
            "manifest_sha256": manifest_sha,
            "approval_sha256": approval_sha,
            "worker_source_commit": source_commit,
        }
    finally:
        if workspace.exists():
            shutil.rmtree(workspace)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expect-manifest-sha256", required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--expect-approval-sha256", required=True)
    parser.add_argument("--expect-source-commit", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--grader", type=Path, default=DEFAULT_GRADER)
    parser.add_argument("--hf-cache", type=Path, default=DEFAULT_HF_CACHE)
    parser.add_argument("--work-root", type=Path, default=DEFAULT_WORK)
    parser.add_argument("--dry-count", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = arguments()
    source_commit = valid_commit(args.expect_source_commit)
    if repository_head(Path(__file__).resolve().parents[1]) != source_commit:
        raise ReplayError("worker repository commit differs from expected source commit")
    rows, shard_id, manifest_sha = load_manifest(args.manifest, args.expect_manifest_sha256)
    approval, approval_sha = load_approval(
        args.approval, args.expect_approval_sha256, manifest_sha, shard_id, source_commit
    )
    verify_environment(approval, args.data_dir, args.grader)
    manifests = {row["card_id"]: row for row in rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    done = load_done(args.out, manifests, manifest_sha, approval_sha, source_commit)
    todo = [row for row in rows if row["card_id"] not in done]
    if args.dry_count:
        print(canonical({"protocol": PROTOCOL, "shard_id": shard_id, "done": len(done), "todo": len(todo)}))
        return
    nvfix = prepare_nvfix(args.work_root)
    for index, manifest in enumerate(todo, 1):
        result = run_one(
            manifest,
            manifest_sha=manifest_sha,
            approval_sha=approval_sha,
            source_commit=source_commit,
            data_dir=args.data_dir,
            grader=args.grader,
            hf_cache=args.hf_cache,
            work_root=args.work_root,
            nvfix=nvfix,
        )
        validate_result(result, manifest, manifest_sha, approval_sha, source_commit)
        append_result(args.out, result)
        print(
            f"SCORE_CHANNEL_REPLAY_PROGRESS shard={shard_id} index={index}/{len(todo)} "
            f"card_sha={sha256_bytes(manifest['card_id'].encode('utf-8'))[:16]} "
            f"sub={int(finite_number(result['sub_score']))} keyed={int(result['val_how'] == 'keyed')}",
            flush=True,
        )
    print(
        f"SCORE_CHANNEL_REPLAY_WORKER_COMPLETE shard={shard_id} rows={len(rows)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
