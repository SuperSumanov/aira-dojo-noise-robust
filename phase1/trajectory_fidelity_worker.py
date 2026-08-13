#!/usr/bin/env python3
"""Collect a continuation fidelity trajectory from one execution per candidate.

Unlike fidelity_worker.py, this process is not restarted at each cap.  A pristine host-side
watcher snapshots stdout/stderr metadata and submission.csv at predeclared checkpoints, then
grades copied snapshots only after the candidate process has stopped.  The watcher never writes
inside the candidate workspace except for the initial solution.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SIF = Path("/research/d7/spc/yzyang4/aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif")
DEFAULT_DATA = Path("/research/d7/spc/yzyang4/mle-bench-data")
GRADER = Path("/research/d7/spc/yzyang4/venvs/exp/bin/mlebench")
DEFAULT_CACHE = Path("/research/d7/spc/yzyang4/scratch/hf_cache")
SCORE_RE = re.compile(r'"?score"?[=:]\s*([-+0-9.eE]+)')
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


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def parse_val(text: str) -> tuple[float | None, str | None]:
    matches = list(KEYED.finditer(text))
    if matches:
        return float(matches[-1].group(1)), "keyed"
    matches = list(BARE.finditer(text))
    if matches:
        return float(matches[-1].group(1)), "bare"
    return None, None


def read_text_snapshot(path: Path) -> tuple[str, int, str, bool]:
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return "", 0, hashlib.sha256(b"").hexdigest(), False
    with os.fdopen(fd, "rb") as f:
        before = os.fstat(f.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise RuntimeError(f"log is not a regular file: {path}")
        data = f.read(before.st_size)
        after = os.fstat(f.fileno())
    if len(data) != before.st_size:
        raise RuntimeError(f"log truncated during snapshot: {path}")
    changed = (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or before.st_ino != after.st_ino
    )
    return data.decode("utf-8", errors="replace"), len(data), hashlib.sha256(data).hexdigest(), changed


def copy_submission(source: Path, destination: Path) -> dict:
    record = {
        "sub_exists": source.is_file(),
        "sub_copied": False,
        "sub_size": None,
        "sub_sha256": None,
        "sub_copy_error": None,
        "snapshot_path": None,
        "sub_source_size_before": None,
        "sub_source_size_after": None,
        "sub_source_mtime_ns_before": None,
        "sub_source_mtime_ns_after": None,
        "sub_source_changed_during_copy": None,
        "sub_copy_wall_s": None,
    }
    try:
        fd = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return record
    except Exception as exc:
        record["sub_exists"] = source.exists() or source.is_symlink()
        record["sub_copy_error"] = f"{type(exc).__name__}: {exc}"
        return record
    record["sub_exists"] = True
    started = time.monotonic()
    try:
        src = os.fdopen(fd, "rb")
        before = os.fstat(src.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise RuntimeError("submission is not a regular file")
        destination.parent.mkdir(parents=True, exist_ok=True)
        tmp = destination.parent / f".{destination.name}.{os.getpid()}.tmp"
        with tmp.open("xb") as dst:
            remaining = before.st_size
            while remaining:
                chunk = src.read(min(1 << 20, remaining))
                if not chunk:
                    raise RuntimeError("submission truncated during checkpoint copy")
                dst.write(chunk)
                remaining -= len(chunk)
            dst.flush()
            os.fsync(dst.fileno())
        after = os.fstat(src.fileno())
        src.close()
        path_changed = False
        try:
            path_now = os.stat(source, follow_symlinks=False)
            path_changed = path_now.st_dev != after.st_dev or path_now.st_ino != after.st_ino
        except FileNotFoundError:
            path_changed = True
        changed = (
            before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or before.st_ino != after.st_ino
            or path_changed
        )
        os.replace(tmp, destination)
        fsync_dir(destination.parent)
        record.update(
            {
                "sub_copied": True,
                "sub_size": destination.stat().st_size,
                "sub_sha256": file_sha256(destination),
                "snapshot_path": str(destination),
                "sub_source_size_before": before.st_size,
                "sub_source_size_after": after.st_size,
                "sub_source_mtime_ns_before": before.st_mtime_ns,
                "sub_source_mtime_ns_after": after.st_mtime_ns,
                "sub_source_changed_during_copy": changed,
                "sub_copy_wall_s": round(time.monotonic() - started, 6),
            }
        )
    except Exception as exc:
        try:
            os.close(fd)
        except OSError:
            pass
        if 'tmp' in locals():
            tmp.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        record["sub_copy_error"] = f"{type(exc).__name__}: {exc}"
        record["sub_copy_wall_s"] = round(time.monotonic() - started, 6)
    return record


def kill_process_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait(timeout=30)
    for _ in range(20):
        try:
            os.killpg(proc.pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    raise RuntimeError(f"process group survived SIGKILL pgid={proc.pid}")


def monitor_process(
    proc: subprocess.Popen,
    workdir: Path,
    stdout_path: Path,
    stderr_path: Path,
    checkpoints: list[float],
    snapshot_dir: Path,
    poll_s: float,
    started_monotonic: float | None = None,
) -> tuple[list[dict], float, int]:
    started = time.monotonic() if started_monotonic is None else started_monotonic
    snapshots = []
    for cap in checkpoints:
        while proc.poll() is None:
            elapsed = time.monotonic() - started
            remaining = cap - elapsed
            if remaining <= 0:
                break
            time.sleep(min(poll_s, remaining))

        elapsed = time.monotonic() - started
        alive = proc.poll() is None
        sub = copy_submission(
            workdir / "submission.csv",
            snapshot_dir / f"submission_t{str(cap).replace('.', 'p')}.csv",
        )
        stdout_text, stdout_bytes, stdout_sha, stdout_changed = read_text_snapshot(stdout_path)
        stderr_text, stderr_bytes, stderr_sha, stderr_changed = read_text_snapshot(stderr_path)
        val, val_how = parse_val(stdout_text + "\n" + stderr_text)
        capture_completed_elapsed = time.monotonic() - started
        snapshots.append(
            {
                "cap_s": cap,
                "snapshot_elapsed_s": round(elapsed, 6),
                "process_alive": alive,
                "process_rc_at_snapshot": None if alive else proc.returncode,
                "capture_completed_elapsed_s": round(capture_completed_elapsed, 6),
                "stdout_val": val,
                "val_how": val_how,
                "stdout_bytes": stdout_bytes,
                "stderr_bytes": stderr_bytes,
                "stdout_sha256": stdout_sha,
                "stderr_sha256": stderr_sha,
                "stdout_changed_during_read": stdout_changed,
                "stderr_changed_during_read": stderr_changed,
                **sub,
            }
        )

    kill_process_group(proc)
    wall_s = time.monotonic() - started
    return snapshots, wall_s, int(proc.returncode)


def grade_snapshot(path: Path, competition: str, data_dir: Path) -> dict:
    if not path.is_file():
        return {
            "sub_score": None,
            "grade_rc": None,
            "grade_wall_s": None,
            "grade_output_sha256": None,
            "grade_skipped_reason": "no_stable_snapshot",
        }
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [str(GRADER), "grade-sample", str(path), competition, "--data-dir", str(data_dir)],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        output = (completed.stdout or "") + "\n" + (completed.stderr or "")
        match = SCORE_RE.search(output)
        score = float(match.group(1)) if match else None
        if score is not None and not math.isfinite(score):
            score = None
        return {
            "sub_score": score,
            "grade_rc": completed.returncode,
            "grade_wall_s": round(time.monotonic() - started, 6),
            "grade_output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
            "grade_skipped_reason": None,
        }
    except subprocess.TimeoutExpired as exc:
        output = ((exc.stdout or "") if isinstance(exc.stdout, str) else "") + (
            (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        )
        return {
            "sub_score": None,
            "grade_rc": "TIMEOUT",
            "grade_wall_s": round(time.monotonic() - started, 6),
            "grade_output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
            "grade_skipped_reason": None,
        }


def validate_card_records(
    records: list[dict], checkpoints: list[float], card_dir: Path | None = None
) -> str:
    if not isinstance(records, list) or len(records) != len(checkpoints):
        raise RuntimeError("card transaction has wrong record count")
    required = {
        "schema_version", "card_id", "competition", "cap_s", "sub_copied", "sub_score",
        "grade_rc", "final_rc", "manifest_sha256", "container_sha256", "solution_sha256",
        "snapshot_relpath",
    }
    ids = {str(row.get("card_id", "")) for row in records if isinstance(row, dict)}
    caps = {float(row.get("cap_s")) for row in records if isinstance(row, dict)}
    if len(ids) != 1 or "" in ids or caps != set(checkpoints):
        raise RuntimeError("card transaction identities/checkpoints mismatch")
    for row in records:
        missing = required - set(row)
        if missing:
            raise RuntimeError(f"card transaction missing fields: {sorted(missing)}")
        if card_dir is not None and row["sub_copied"]:
            rel = row["snapshot_relpath"]
            if not isinstance(rel, str) or Path(rel).is_absolute() or ".." in Path(rel).parts:
                raise RuntimeError("unsafe/missing snapshot relative path")
            snapshot = card_dir / rel
            if not snapshot.is_file():
                raise RuntimeError(f"snapshot file missing: {snapshot}")
            if snapshot.stat().st_size != row["sub_size"] or file_sha256(snapshot) != row["sub_sha256"]:
                raise RuntimeError(f"snapshot size/hash mismatch: {snapshot}")
    return next(iter(ids))


def card_dir_path(out_dir: Path, card_id: str) -> Path:
    safe = hashlib.sha256(card_id.encode("utf-8")).hexdigest()
    return out_dir / "cards" / safe


def write_card_transaction(
    out_dir: Path,
    records: list[dict],
    checkpoints: list[float],
    staging_dir: Path,
) -> None:
    card_id = validate_card_records(records, checkpoints, staging_dir)
    destination = card_dir_path(out_dir, card_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise RuntimeError(f"refusing existing card transaction: {destination}")
    if staging_dir.parent != out_dir or not staging_dir.name.startswith(".card-"):
        raise RuntimeError("invalid transaction staging directory")
    records_path = staging_dir / "records.json"
    with records_path.open("x", encoding="utf-8", newline="") as f:
        json.dump(records, f, ensure_ascii=False, sort_keys=True, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(staging_dir, destination)
    fsync_dir(destination.parent)


def materialize_jsonl(out_dir: Path, checkpoints: list[float]) -> Path:
    cards_dir = out_dir / "cards"
    destination = out_dir / "trajectory_records.jsonl"
    fd, tmp_name = tempfile.mkstemp(prefix=".trajectory_records.", dir=out_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as out:
            for path in sorted(cards_dir.glob("*/records.json")):
                records = json.loads(path.read_text(encoding="utf-8"))
                validate_card_records(records, checkpoints, path.parent)
                for row in sorted(records, key=lambda item: float(item["cap_s"])):
                    out.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp_name, destination)
        fsync_dir(destination.parent)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return destination


def load_manifest(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or not isinstance(row.get("card_id"), str):
                raise RuntimeError(f"bad manifest row {lineno}")
            if not isinstance(row.get("competition"), str) or not isinstance(row.get("code"), str):
                raise RuntimeError(f"missing competition/code row {lineno}")
            rows.append(row)
    if len({row["card_id"] for row in rows}) != len(rows):
        raise RuntimeError("duplicate card_id in manifest")
    return rows


def load_done(out_dir: Path, checkpoints: list[float]) -> set[str]:
    stale = sorted(out_dir.glob(".card-*")) if out_dir.exists() else []
    if stale:
        raise RuntimeError(f"incomplete card staging directories require quarantine: {stale}")
    cards_dir = out_dir / "cards"
    if not cards_dir.exists():
        return set()
    done = set()
    for path in sorted(cards_dir.glob("*/records.json")):
        records = json.loads(path.read_text(encoding="utf-8"))
        cid = validate_card_records(records, checkpoints, path.parent)
        if cid in done or card_dir_path(out_dir, cid) / "records.json" != path:
            raise RuntimeError(f"duplicate/misnamed card transaction: {path}")
        done.add(cid)
    return done


def build_command(
    workdir: Path,
    public_data: Path,
    hf_cache: Path,
    online: bool,
    nvfix: Path | None,
) -> list[str]:
    binds = f"{workdir}:/workspace,{public_data}:/workspace/data:ro,{hf_cache}:/hf"
    envs = [
        "PYTHONUNBUFFERED=1",
        "WANDB_DISABLED=1",
        "TQDM_DISABLE=1",
        "TF_CPP_MIN_LOG_LEVEL=3",
        "HOME=/tmp",
        "HF_HOME=/hf",
        "TORCH_HOME=/hf/torch",
        "HF_HUB_OFFLINE=0" if online else "HF_HUB_OFFLINE=1",
    ]
    if online:
        envs += [
            "http_proxy=http://137.189.90.241:8000/",
            "https_proxy=http://137.189.90.241:8000/",
            "HF_HUB_DISABLE_XET=1",
        ]
    extra = []
    if nvfix is not None:
        extra = [
            "--bind", "/etc/OpenCL/vendors/nvidia.icd:/etc/OpenCL/vendors/nvidia.icd",
            "--bind", f"{nvfix}:/mnt",
        ]
        envs.append("LD_LIBRARY_PATH=/mnt:/.singularity.d/libs")
    return [
        "singularity", "exec", "--containall", "--cleanenv", "--nv", "--pwd", "/workspace",
        "--bind", binds, *extra, str(SIF), "env", *envs, "python", "solution.py",
    ]


def run_candidate(
    node: dict,
    checkpoints: list[float],
    workbase: Path,
    data_dir: Path,
    hf_cache: Path,
    online: bool,
    poll_s: float,
    keep_workdir: bool,
    manifest_sha: str,
    image_sha: str,
    snapshot_dir: Path,
) -> list[dict]:
    safe_id = hashlib.sha256(node["card_id"].encode("utf-8")).hexdigest()[:20]
    workdir = workbase / safe_id
    if workdir.exists():
        raise RuntimeError(f"refusing existing candidate workdir: {workdir}")
    workdir.mkdir(parents=True)
    (workdir / "solution.py").write_text(node["code"], encoding="utf-8")
    stdout_path = workdir / "stdout.log"
    stderr_path = workdir / "stderr.log"
    if snapshot_dir.exists():
        raise RuntimeError(f"refusing existing host snapshot directory: {snapshot_dir}")
    snapshot_dir.mkdir(parents=True)

    public_data = data_dir / node["competition"] / "prepared" / "public"
    if not public_data.is_dir():
        raise RuntimeError(f"public data directory missing: {public_data}")
    nvfix = workbase / "nvfix"
    source_nvvm = Path("/usr/lib/x86_64-linux-gnu/libnvidia-nvvm.so.4")
    source_icd = Path("/etc/OpenCL/vendors/nvidia.icd")
    if not source_nvvm.is_file() or not source_icd.is_file():
        raise RuntimeError("required NVIDIA/OpenCL host fix is unavailable")
    nvfix.mkdir(parents=True, exist_ok=True)
    shutil.copy(source_nvvm, nvfix / "libnvidia-nvvm.so.4")

    cmd = build_command(
        workdir,
        public_data,
        hf_cache,
        online,
        nvfix,
    )

    def launch() -> tuple[subprocess.Popen, object, object, float]:
        stdout_handle = stdout_path.open("wb")
        stderr_handle = stderr_path.open("wb")
        started = time.monotonic()
        proc = subprocess.Popen(
            cmd,
            stdout=stdout_handle,
            stderr=stderr_handle,
            start_new_session=True,
        )
        return proc, stdout_handle, stderr_handle, started

    proc, stdout_handle, stderr_handle, started = launch()
    time.sleep(min(3.0, checkpoints[0]))
    if proc.poll() == 255 and stdout_path.stat().st_size == 0 and stderr_path.stat().st_size == 0:
        stdout_handle.close()
        stderr_handle.close()
        time.sleep(20)
        stdout_path.unlink(missing_ok=True)
        stderr_path.unlink(missing_ok=True)
        proc, stdout_handle, stderr_handle, started = launch()
    snapshots, wall_s, final_rc = monitor_process(
        proc, workdir, stdout_path, stderr_path, checkpoints, snapshot_dir, poll_s, started
    )
    stdout_handle.close()
    stderr_handle.close()

    records = []
    for snapshot in snapshots:
        stable = (
            bool(snapshot["sub_copied"])
            and not bool(snapshot["sub_source_changed_during_copy"])
            and snapshot["sub_copy_error"] is None
        )
        snapshot_path = Path(snapshot["snapshot_path"]) if stable else Path("/__missing__")
        grade = grade_snapshot(snapshot_path, node["competition"], data_dir)
        public_snapshot = dict(snapshot)
        if snapshot["snapshot_path"]:
            public_snapshot["snapshot_relpath"] = f"snapshots/{Path(snapshot['snapshot_path']).name}"
        else:
            public_snapshot["snapshot_relpath"] = None
        public_snapshot.pop("snapshot_path", None)
        records.append(
            {
                "schema_version": 1,
                "card_id": node["card_id"],
                "competition": node["competition"],
                "parent": node.get("parent"),
                "stratum": node.get("stratum"),
                "manifest_sha256": manifest_sha,
                "solution_sha256": hashlib.sha256(node["code"].encode("utf-8")).hexdigest(),
                "container_image": str(SIF),
                "container_sha256": image_sha,
                "grader": str(GRADER),
                "grader_sha256": file_sha256(GRADER.resolve()),
                "wall_s": round(wall_s, 6),
                "final_rc": final_rc,
                "checkpoints_s": checkpoints,
                "continuous_execution": True,
                **public_snapshot,
                **grade,
            }
        )
    if not keep_workdir:
        shutil.rmtree(workdir)
    return records


def self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        script = root / "toy.py"
        script.write_text(
            "import pathlib,time\n"
            "print('validation auc=0.61', flush=True)\n"
            "time.sleep(0.18)\n"
            "pathlib.Path('submission.csv').write_text('id,pred\\n1,0.5\\n')\n"
            "print('validation auc=0.72', flush=True)\n"
            "time.sleep(2)\n",
            encoding="utf-8",
        )
        stdout_path, stderr_path = root / "out", root / "err"
        with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
            proc = subprocess.Popen(
                [sys.executable, str(script)],
                cwd=root,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )
            snapshots, wall_s, rc = monitor_process(
                proc, root, stdout_path, stderr_path, [0.1, 0.35, 0.55], root / "snaps", 0.01
            )
        assert snapshots[0]["sub_exists"] is False
        assert snapshots[1]["sub_copied"] is True and snapshots[1]["stdout_val"] == 0.72
        assert snapshots[2]["sub_sha256"] == snapshots[1]["sub_sha256"]
        assert rc < 0 and 0.5 <= wall_s < 1.5
        transaction_root = root / "transaction_out"
        transaction_root.mkdir()
        staging = Path(tempfile.mkdtemp(prefix=".card-", dir=transaction_root))
        dummy = []
        for cap in [0.1, 0.35, 0.55]:
            dummy.append({
                "schema_version": 1,
                "card_id": "toy-card",
                "competition": "toy-task",
                "cap_s": cap,
                "sub_copied": False,
                "sub_score": None,
                "grade_rc": None,
                "final_rc": rc,
                "manifest_sha256": "m",
                "container_sha256": "i",
                "solution_sha256": "s",
                "snapshot_relpath": None,
            })
        write_card_transaction(transaction_root, dummy, [0.1, 0.35, 0.55], staging)
        assert load_done(transaction_root, [0.1, 0.35, 0.55]) == {"toy-card"}
        materialized = materialize_jsonl(transaction_root, [0.1, 0.35, 0.55])
        assert sum(1 for line in materialized.read_text(encoding="utf-8").splitlines() if line) == 3
        print("TRAJECTORY_SELF_TEST_PASS", len(snapshots), round(wall_s, 3), rc)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--checkpoints", default="30,60,120")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--online", action="store_true")
    ap.add_argument("--dry-count", action="store_true")
    ap.add_argument("--poll-s", type=float, default=0.25)
    ap.add_argument("--workbase", type=Path, default=Path("/tmp/trajectory_fidelity"))
    ap.add_argument("--data-dir", type=Path, default=Path(os.environ.get("MLE_BENCH_DATA_DIR", DEFAULT_DATA)))
    ap.add_argument("--hf-cache", type=Path, default=Path(os.environ.get("REGRADE_HF_CACHE", DEFAULT_CACHE)))
    ap.add_argument("--container-sha256")
    ap.add_argument("--keep-workdir", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.manifest or not args.out or not args.container_sha256:
        ap.error("--manifest --out --container-sha256 are required")
    checkpoints = sorted({float(x) for x in args.checkpoints.split(",")})
    if not checkpoints or checkpoints[0] <= 0 or args.poll_s <= 0:
        raise RuntimeError("checkpoints and poll interval must be positive")
    if file_sha256(SIF) != args.container_sha256:
        raise RuntimeError("container image SHA mismatch")
    if not GRADER.is_file() or not args.data_dir.is_dir() or not args.hf_cache.is_dir():
        raise RuntimeError("grader/data/cache prerequisites missing")

    nodes = load_manifest(args.manifest)
    done = load_done(args.out, checkpoints)
    todo = [node for node in nodes if node["card_id"] not in done]
    if args.limit:
        todo = todo[: args.limit]
    print(
        f"[trajectory] nodes={len(nodes)} checkpoints={checkpoints} complete={len(done)} todo={len(todo)}",
        flush=True,
    )
    if args.dry_count:
        print(len(todo))
        return

    args.out.mkdir(parents=True, exist_ok=True)
    args.workbase.mkdir(parents=True, exist_ok=True)
    args.hf_cache.mkdir(parents=True, exist_ok=True)
    manifest_sha = file_sha256(args.manifest)
    for node in todo:
        staging = Path(tempfile.mkdtemp(prefix=".card-", dir=args.out))
        try:
            records = run_candidate(
                node,
                checkpoints,
                args.workbase,
                args.data_dir,
                args.hf_cache,
                args.online,
                args.poll_s,
                args.keep_workdir,
                manifest_sha,
                args.container_sha256,
                staging / "snapshots",
            )
            write_card_transaction(args.out, records, checkpoints, staging)
        except Exception:
            # Preserve the hidden staging directory and workdir for forensic diagnosis.
            raise
        materialize_jsonl(args.out, checkpoints)
        usable = sum(record["sub_score"] is not None for record in records)
        print(
            f"[trajectory] card={node['card_id']} records={len(records)} usable={usable} final_rc={records[0]['final_rc']}",
            flush=True,
        )
    materialize_jsonl(args.out, checkpoints)
    print("TRAJECTORY_FIDELITY_WORKER_DONE", flush=True)


if __name__ == "__main__":
    main()
