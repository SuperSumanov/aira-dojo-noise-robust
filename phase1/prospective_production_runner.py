#!/usr/bin/env python3
"""Outcome-blind, append-only production runner for prospective archive drops.

The runner observes metadata, waits for a frozen stability window, then executes one
archive transaction through intake, the active scorer, both registries, and the
provisional accumulator.  A transaction becomes visible only by atomically advancing
``LATEST`` to a fully verified immutable snapshot.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


PROTOCOL = "prospective_production_runner_v1"
OBSERVER_PROTOCOL = "prospective_archive_observer_v1"
ACTIVE_RECEIPT_SHA256 = "cfab01a80536a50ef21c47ac269c7ce54a11a3b1f0b6daa5700873cbb02ce178"
FIXED_SCORER_DIR = "fixed_decision_scorer_v11_20260814"
SHA_RX = re.compile(r"[0-9a-f]{64}")
DROP_RX = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
TRANSACTION_KEYS = {
    "archive_relative_path",
    "archive_sha256",
    "archive_size",
    "committed_at_utc",
    "drop_id",
    "intake_dir",
    "intake_summary_sha256",
    "score_dir",
    "score_summary_sha256",
}
FORBIDDEN_TRACE_MARKERS = (
    b"label_vault.jsonl",
    b"decision_frozen",
    b"/d_test/",
)


class ProductionError(RuntimeError):
    pass


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_string(epoch: float | None = None) -> str:
    value = dt.datetime.now(dt.timezone.utc) if epoch is None else dt.datetime.fromtimestamp(
        epoch, tz=dt.timezone.utc
    )
    return value.isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ProductionError(f"invalid UTC timestamp: {value!r}") from error
    if parsed.tzinfo is None or parsed.utcoffset() != dt.timedelta(0):
        raise ProductionError("timestamp must be explicit UTC")
    return parsed.astimezone(dt.timezone.utc)


def atomic_bytes(path: Path, blob: bytes) -> None:
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    with temporary.open("xb") as handle:
        handle.write(blob)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")


def canonical_jsonl(rows: Iterable[dict[str, Any]]) -> bytes:
    return b"".join(
        (
            json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n"
        ).encode("utf-8")
        for row in rows
    )


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProductionError(f"cannot read JSON: {path}") from error
    if not isinstance(value, dict):
        raise ProductionError(f"JSON root is not an object: {path}")
    return value


def git_output(repo_root: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo_root), *arguments], text=True, stderr=subprocess.STDOUT
    ).strip()


def verify_frozen_repo(repo_root: Path, expected_commit: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", expected_commit):
        raise ProductionError("expected commit must be a full lowercase SHA-1")
    actual = git_output(repo_root, "rev-parse", "HEAD")
    if actual != expected_commit:
        raise ProductionError(f"production worktree commit mismatch: {actual}")
    status = git_output(repo_root, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise ProductionError("production worktree is not exact-clean")
    return actual


def ensure_outside(path: Path, protected: Iterable[Path], label: str) -> None:
    resolved = path.resolve()
    for item in protected:
        base = item.resolve()
        if resolved == base or base in resolved.parents or resolved in base.parents:
            raise ProductionError(f"{label} must be outside protected input trees")


def inventory_archives(source_root: Path) -> dict[str, dict[str, Any]]:
    if not source_root.is_dir():
        raise ProductionError("senior source root is unavailable")
    records: dict[str, dict[str, Any]] = {}
    for directory in sorted(source_root.iterdir(), key=lambda path: path.name):
        if directory.is_symlink():
            raise ProductionError(f"source child directory is a symlink: {directory.name}")
        if not directory.is_dir():
            continue
        for archive in sorted(directory.glob("*.tar.gz"), key=lambda path: path.name):
            if archive.is_symlink() or not archive.is_file():
                raise ProductionError(f"archive is not a regular non-symlink file: {archive}")
            resolved = archive.resolve()
            if resolved.parent != directory.resolve():
                raise ProductionError(f"archive escapes its source directory: {archive}")
            relative = archive.relative_to(source_root).as_posix()
            if relative in records or relative.count("/") != 1:
                raise ProductionError(f"invalid or duplicate archive relative path: {relative}")
            stat = archive.stat()
            records[relative] = {
                "path": str(resolved),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
    return records


def empty_observations(source_root: Path) -> dict[str, Any]:
    return {
        "protocol": OBSERVER_PROTOCOL,
        "source_root": str(source_root.resolve()),
        "baseline_sealed_at_epoch": None,
        "entries": {},
    }


def load_observations(path: Path, source_root: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_observations(source_root)
    value = read_json(path)
    if (
        set(value) != {"protocol", "source_root", "baseline_sealed_at_epoch", "entries"}
        or value["protocol"] != OBSERVER_PROTOCOL
        or value["source_root"] != str(source_root.resolve())
        or not isinstance(value["entries"], dict)
    ):
        raise ProductionError("observation ledger contract mismatch")
    return value


def update_observations(
    previous: dict[str, Any],
    inventory: dict[str, dict[str, Any]],
    now_epoch: float,
    minimum_interval_seconds: int,
) -> dict[str, Any]:
    if minimum_interval_seconds <= 0:
        raise ProductionError("minimum observation interval must be positive")
    old_entries = previous["entries"]
    sealing_baseline = previous["baseline_sealed_at_epoch"] is None
    entries: dict[str, dict[str, Any]] = {}
    for relative, current in sorted(inventory.items()):
        old = old_entries.get(relative)
        same = bool(
            isinstance(old, dict)
            and old.get("present") is True
            and old.get("size") == current["size"]
            and old.get("mtime_ns") == current["mtime_ns"]
        )
        committed_sha = old.get("committed_archive_sha256") if isinstance(old, dict) else None
        committed_snapshot = old.get("committed_snapshot_sha256") if isinstance(old, dict) else None
        baseline = bool(old.get("baseline")) if isinstance(old, dict) else sealing_baseline
        if isinstance(old, dict) and baseline and not same:
            raise ProductionError(f"baseline source archive metadata changed: {relative}")
        if committed_sha is not None and not same:
            raise ProductionError(f"committed source archive metadata changed: {relative}")
        if same:
            first_stable = float(old["first_stable_at_epoch"])
            last_observed = float(old["last_observed_at_epoch"])
            observations = int(old["stable_observations"])
            if now_epoch - last_observed >= minimum_interval_seconds:
                last_observed = now_epoch
                observations += 1
        else:
            first_stable = now_epoch
            last_observed = now_epoch
            observations = 1
        entries[relative] = {
            "baseline": baseline,
            "committed_archive_sha256": committed_sha,
            "committed_snapshot_sha256": committed_snapshot,
            "first_stable_at_epoch": first_stable,
            "last_observed_at_epoch": last_observed,
            "mtime_ns": current["mtime_ns"],
            "path": current["path"],
            "present": True,
            "size": current["size"],
            "stable_observations": observations,
        }
    for relative, old in old_entries.items():
        if relative in entries:
            continue
        if isinstance(old, dict) and (
            old.get("committed_archive_sha256") or old.get("baseline") is True
        ):
            raise ProductionError(f"protected source archive disappeared: {relative}")
        missing = dict(old)
        missing["present"] = False
        entries[relative] = missing
    return {
        "protocol": OBSERVER_PROTOCOL,
        "source_root": previous["source_root"],
        "baseline_sealed_at_epoch": (
            now_epoch if sealing_baseline else previous["baseline_sealed_at_epoch"]
        ),
        "entries": entries,
    }


def ready_archives(
    observations: dict[str, Any],
    now_epoch: float,
    minimum_age_seconds: int,
    minimum_observations: int,
    minimum_stable_span_seconds: int,
) -> list[str]:
    if min(minimum_age_seconds, minimum_observations, minimum_stable_span_seconds) <= 0:
        raise ProductionError("archive readiness thresholds must be positive")
    ready: list[tuple[int, str]] = []
    for relative, entry in observations["entries"].items():
        if (
            not entry.get("present")
            or entry.get("baseline") is True
            or entry.get("committed_archive_sha256") is not None
            or now_epoch - int(entry["mtime_ns"]) / 1_000_000_000 < minimum_age_seconds
            or int(entry["stable_observations"]) < minimum_observations
            or float(entry["last_observed_at_epoch"])
            - float(entry["first_stable_at_epoch"])
            < minimum_stable_span_seconds
        ):
            continue
        ready.append((int(entry["mtime_ns"]), relative))
    return [relative for _, relative in sorted(ready)]


def safe_drop_id(relative: str, archive_sha: str) -> str:
    if not SHA_RX.fullmatch(archive_sha):
        raise ProductionError("invalid archive SHA for drop ID")
    raw = relative.removesuffix(".tar.gz")
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", raw.replace("/", "-")).strip("-._")
    slug = slug[:100].rstrip("-._")
    drop_id = f"{slug}-{archive_sha[:16]}" if slug else f"archive-{archive_sha[:16]}"
    if not DROP_RX.fullmatch(drop_id):
        raise ProductionError("cannot derive a safe drop ID")
    return drop_id


def validate_transaction(row: Any, line_number: int) -> dict[str, Any]:
    if not isinstance(row, dict) or set(row) != TRANSACTION_KEYS:
        raise ProductionError(f"transaction schema mismatch at line {line_number}")
    for key in (
        "archive_relative_path",
        "committed_at_utc",
        "drop_id",
        "intake_dir",
        "score_dir",
    ):
        if not isinstance(row[key], str) or not row[key] or any(c in row[key] for c in "\r\n\t"):
            raise ProductionError(f"invalid transaction {key} at line {line_number}")
    if not DROP_RX.fullmatch(row["drop_id"]):
        raise ProductionError(f"invalid transaction drop_id at line {line_number}")
    for key in ("archive_sha256", "intake_summary_sha256", "score_summary_sha256"):
        if not isinstance(row[key], str) or not SHA_RX.fullmatch(row[key]):
            raise ProductionError(f"invalid transaction {key} at line {line_number}")
    if isinstance(row["archive_size"], bool) or not isinstance(row["archive_size"], int) or row[
        "archive_size"
    ] < 0:
        raise ProductionError(f"invalid transaction archive_size at line {line_number}")
    if not Path(row["intake_dir"]).is_absolute() or not Path(row["score_dir"]).is_absolute():
        raise ProductionError(f"transaction output paths must be absolute at line {line_number}")
    parse_utc(row["committed_at_utc"])
    return row


def parse_transactions(blob: bytes) -> list[dict[str, Any]]:
    try:
        lines = blob.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise ProductionError("transaction registry is not UTF-8") from error
    rows: list[dict[str, Any]] = []
    seen_drop: set[str] = set()
    seen_archive: set[str] = set()
    seen_relative: set[str] = set()
    for line_number, line in enumerate(lines, 1):
        if not line:
            raise ProductionError(f"blank transaction registry line {line_number}")
        try:
            row = validate_transaction(json.loads(line), line_number)
        except json.JSONDecodeError as error:
            raise ProductionError(f"invalid transaction JSON at line {line_number}") from error
        if row["drop_id"] in seen_drop or row["archive_sha256"] in seen_archive or row[
            "archive_relative_path"
        ] in seen_relative:
            raise ProductionError(f"duplicate transaction identity at line {line_number}")
        seen_drop.add(row["drop_id"])
        seen_archive.add(row["archive_sha256"])
        seen_relative.add(row["archive_relative_path"])
        rows.append(row)
    return rows


def intake_registry_bytes(rows: list[dict[str, Any]]) -> bytes:
    return canonical_jsonl(
        {
            "drop_id": row["drop_id"],
            "intake_dir": row["intake_dir"],
            "summary_sha256": row["intake_summary_sha256"],
        }
        for row in rows
    )


def score_registry_bytes(rows: list[dict[str, Any]]) -> bytes:
    return canonical_jsonl(
        {
            "drop_id": row["drop_id"],
            "intake_dir": row["intake_dir"],
            "intake_summary_sha256": row["intake_summary_sha256"],
            "score_dir": row["score_dir"],
            "score_summary_sha256": row["score_summary_sha256"],
        }
        for row in rows
    )


def load_latest(state_root: Path) -> tuple[list[dict[str, Any]], str | None]:
    latest = state_root / "LATEST"
    if not latest.exists():
        return [], None
    snapshot_sha = latest.read_text(encoding="ascii").strip()
    if not SHA_RX.fullmatch(snapshot_sha):
        raise ProductionError("LATEST does not contain a snapshot SHA")
    snapshot = state_root / "snapshots" / snapshot_sha
    manifest = snapshot / "SHA256SUMS"
    if sha256(manifest) != snapshot_sha or verify_payload_manifest(snapshot) == 0:
        raise ProductionError("LATEST snapshot payload manifest mismatch")
    transaction_path = snapshot / "transactions.jsonl"
    blob = transaction_path.read_bytes()
    rows = parse_transactions(blob)
    if not rows:
        raise ProductionError("LATEST snapshot has an empty transaction registry")
    if (snapshot / "intake_registry.jsonl").read_bytes() != intake_registry_bytes(rows):
        raise ProductionError("latest intake registry is not a transaction projection")
    if (snapshot / "score_registry.jsonl").read_bytes() != score_registry_bytes(rows):
        raise ProductionError("latest score registry is not a transaction projection")
    return rows, snapshot_sha


def sanitized_environment() -> dict[str, str]:
    allowed = ("HOME", "LANG", "LC_ALL", "LD_LIBRARY_PATH", "PATH", "TMPDIR")
    environment = {key: os.environ[key] for key in allowed if key in os.environ}
    environment.update(
        {
            "OPENBLAS_NUM_THREADS": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
        }
    )
    return environment


def run_logged(
    argv: list[str],
    log_path: Path,
    *,
    cwd: Path,
    require_strace: bool,
    audit_no_outcomes: bool,
) -> None:
    trace_path = log_path.with_suffix(".strace")
    command = argv
    if require_strace:
        if shutil.which("strace") is None:
            raise ProductionError("production file audit requires strace")
        command = ["strace", "-f", "-e", "trace=file", "-o", str(trace_path), *argv]
    with log_path.open("xb") as handle:
        handle.write((json.dumps({"argv": argv}, ensure_ascii=False) + "\n").encode("utf-8"))
        handle.flush()
        completed = subprocess.run(
            command,
            stdout=handle,
            stderr=subprocess.STDOUT,
            env=sanitized_environment(),
            cwd=str(cwd),
            check=False,
        )
        handle.write(f"RETURN_CODE={completed.returncode}\n".encode("ascii"))
        handle.flush()
        os.fsync(handle.fileno())
    if completed.returncode != 0:
        raise ProductionError(f"subprocess failed with rc={completed.returncode}: {argv[2:4]}")
    if audit_no_outcomes:
        if not require_strace:
            raise ProductionError("outcome-blind subprocess requires a file-access trace")
        trace = trace_path.read_bytes().lower()
        hits = [marker.decode("ascii") for marker in FORBIDDEN_TRACE_MARKERS if marker in trace]
        if hits:
            raise ProductionError(f"forbidden file marker in subprocess trace: {hits}")


def verify_intake_binding(intake_dir: Path, archive: Path, archive_sha: str) -> str:
    summary_path = intake_dir / "summary.json"
    summary = read_json(summary_path)
    configuration = summary.get("configuration")
    if not isinstance(configuration, dict) or configuration.get("archive_selection") != "explicit_names":
        raise ProductionError("intake did not record explicit archive selection")
    if configuration.get("selected_archive_names") != [archive.name]:
        raise ProductionError("intake selected archive name mismatch")
    with (intake_dir / "archive_manifest.tsv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if len(rows) != 1 or rows[0].get("name") != archive.name or rows[0].get(
        "sha256"
    ) != archive_sha:
        raise ProductionError("intake archive manifest binding mismatch")
    return sha256(summary_path)


def write_payload_manifest(root: Path) -> tuple[int, str]:
    records: list[str] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_file() and path.name != "SHA256SUMS":
            records.append(f"{sha256(path)}  {path.relative_to(root).as_posix()}\n")
    blob = "".join(records).encode("utf-8")
    (root / "SHA256SUMS").write_bytes(blob)
    return len(records), sha256_bytes(blob)


def verify_payload_manifest(root: Path) -> int:
    count = 0
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise ProductionError("invalid snapshot payload manifest")
        target = root / match.group(2)
        if not target.is_file() or sha256(target) != match.group(1):
            raise ProductionError(f"snapshot payload hash mismatch: {match.group(2)}")
        count += 1
    if count == 0:
        raise ProductionError("empty snapshot payload manifest")
    return count


def process_archive(
    args: argparse.Namespace,
    observations: dict[str, Any],
    transactions: list[dict[str, Any]],
    relative: str,
    latest_snapshot_sha: str | None,
) -> tuple[str, str]:
    entry = observations["entries"][relative]
    archive = Path(entry["path"])
    before = archive.stat()
    if before.st_size != entry["size"] or before.st_mtime_ns != entry["mtime_ns"]:
        raise ProductionError("archive metadata changed after readiness decision")
    archive_sha = sha256(archive)
    after_hash = archive.stat()
    if (
        after_hash.st_size != before.st_size
        or after_hash.st_mtime_ns != before.st_mtime_ns
        or sha256(archive) != archive_sha
    ):
        raise ProductionError("archive changed while freezing content SHA")
    for row in transactions:
        if row["archive_sha256"] == archive_sha:
            if row["archive_relative_path"] != relative:
                raise ProductionError("same archive bytes appeared under a second source path")
            entry["committed_archive_sha256"] = archive_sha
            if latest_snapshot_sha is None:
                raise ProductionError("committed transaction has no latest snapshot")
            return "ALREADY_COMMITTED", latest_snapshot_sha

    drop_id = safe_drop_id(relative, archive_sha)
    state_root = args.state_root.resolve()
    repo_root = args.repo_root.resolve()
    fixed_dir = repo_root / "phase1" / "results" / FIXED_SCORER_DIR
    final_intake = state_root / "intakes" / drop_id
    final_score = state_root / "scores" / drop_id
    if final_intake.exists() or final_score.exists():
        raise ProductionError(f"unregistered final output requires recovery: {drop_id}")

    attempt = state_root / "attempts" / f"{drop_id}.{os.getpid()}"
    if attempt.exists():
        raise ProductionError("attempt directory already exists")
    snapshot_stage = attempt / "snapshot"
    logs = snapshot_stage / "logs"
    logs.mkdir(parents=True)
    intake_stage = attempt / "intake"
    score_stage = attempt / "score"
    python = sys.executable
    intake_command = [
        python,
        "-m",
        "phase1.prospective_drop_intake",
        "--drop-dir",
        str(archive.parent),
        "--archive-name",
        archive.name,
        "--freeze-receipt",
        str(fixed_dir / "freeze_receipt.json"),
        "--precutoff-endpoint-denylist",
        str(fixed_dir / "precutoff_endpoint_denylist.csv"),
        "--out-dir",
        str(intake_stage),
        "--repo-root",
        str(repo_root),
        "--expect-freeze-receipt-sha256",
        ACTIVE_RECEIPT_SHA256,
    ]
    run_logged(
        intake_command,
        logs / "01_intake.log",
        cwd=repo_root,
        require_strace=False,
        audit_no_outcomes=False,
    )
    intake_sha = verify_intake_binding(intake_stage, archive, archive_sha)
    if sha256(archive) != archive_sha:
        raise ProductionError("archive changed during intake")
    score_command = [
        python,
        "-m",
        "phase1.prospective_score_pipeline",
        "score-drop",
        "--drop-id",
        drop_id,
        "--repo-root",
        str(repo_root),
        "--intake-dir",
        str(intake_stage),
        "--expect-intake-summary-sha256",
        intake_sha,
        "--scorer-dir",
        str(fixed_dir),
        "--precutoff-endpoint-denylist",
        str(fixed_dir / "precutoff_endpoint_denylist.csv"),
        "--out-dir",
        str(score_stage),
    ]
    run_logged(
        score_command,
        logs / "02_score.log",
        cwd=repo_root,
        require_strace=args.require_strace,
        audit_no_outcomes=True,
    )
    score_sha = sha256(score_stage / "summary.json")
    (state_root / "intakes").mkdir(exist_ok=True)
    (state_root / "scores").mkdir(exist_ok=True)
    os.replace(intake_stage, final_intake)
    os.replace(score_stage, final_score)

    row = {
        "archive_relative_path": relative,
        "archive_sha256": archive_sha,
        "archive_size": before.st_size,
        "committed_at_utc": utc_string(),
        "drop_id": drop_id,
        "intake_dir": str(final_intake),
        "intake_summary_sha256": intake_sha,
        "score_dir": str(final_score),
        "score_summary_sha256": score_sha,
    }
    proposed = [*transactions, validate_transaction(row, len(transactions) + 1)]
    transaction_blob = canonical_jsonl(proposed)
    transaction_sha = sha256_bytes(transaction_blob)
    atomic_bytes(snapshot_stage / "transactions.jsonl", transaction_blob)
    atomic_bytes(snapshot_stage / "intake_registry.jsonl", intake_registry_bytes(proposed))
    atomic_bytes(snapshot_stage / "score_registry.jsonl", score_registry_bytes(proposed))

    validation_command = [
        python,
        "-m",
        "phase1.prospective_score_pipeline",
        "validate-registry",
        "--repo-root",
        str(repo_root),
        "--registry",
        str(snapshot_stage / "score_registry.jsonl"),
        "--out-dir",
        str(snapshot_stage / "score_registry_validation"),
    ]
    run_logged(
        validation_command,
        logs / "03_score_registry.log",
        cwd=repo_root,
        require_strace=args.require_strace,
        audit_no_outcomes=True,
    )
    accumulator_command = [
        python,
        "-m",
        "phase1.prospective_accumulator",
        "--registry",
        str(snapshot_stage / "intake_registry.jsonl"),
        "--freeze-receipt",
        str(fixed_dir / "freeze_receipt.json"),
        "--precutoff-endpoint-denylist",
        str(fixed_dir / "precutoff_endpoint_denylist.csv"),
        "--out-dir",
        str(snapshot_stage / "accumulator"),
        "--repo-root",
        str(repo_root),
    ]
    run_logged(
        accumulator_command,
        logs / "04_accumulator.log",
        cwd=repo_root,
        require_strace=args.require_strace,
        audit_no_outcomes=True,
    )
    accumulator_summary = read_json(snapshot_stage / "accumulator" / "summary.json")
    summary = {
        "status": "PROSPECTIVE_ARCHIVE_TRANSACTION_COMMITTED",
        "protocol": PROTOCOL,
        "git_commit": args.expected_commit,
        "source_sha256": sha256(Path(__file__)),
        "drop_id": drop_id,
        "archive_relative_path": relative,
        "archive_sha256": archive_sha,
        "transaction_registry_sha256": transaction_sha,
        "transactions": len(proposed),
        "accumulator_status": accumulator_summary.get("status"),
        "security": {
            "api_calls": 0,
            "gpu_jobs": 0,
            "label_vault_opened_by_runner": False,
            "outcome_files_opened_by_scorer_or_accumulator": [],
            "subprocess_environment_allowlist": True,
            "strace_required": bool(args.require_strace),
        },
        "software": {"python": sys.version, "platform": platform.platform()},
    }
    atomic_bytes(snapshot_stage / "runner_summary.json", canonical_json(summary))
    manifest_entries, snapshot_sha = write_payload_manifest(snapshot_stage)
    if verify_payload_manifest(snapshot_stage) != manifest_entries:
        raise ProductionError("snapshot postflight entry count mismatch")
    final_snapshot = state_root / "snapshots" / snapshot_sha
    if final_snapshot.exists():
        raise ProductionError("snapshot SHA already exists before promotion")
    (state_root / "snapshots").mkdir(exist_ok=True)
    os.replace(snapshot_stage, final_snapshot)
    atomic_bytes(state_root / "LATEST", f"{snapshot_sha}\n".encode("ascii"))
    entry["committed_archive_sha256"] = archive_sha
    entry["committed_snapshot_sha256"] = snapshot_sha
    try:
        attempt.rmdir()
    except OSError:
        pass
    return "PROSPECTIVE_ARCHIVE_TRANSACTION_COMMITTED", snapshot_sha


@contextlib.contextmanager
def exclusive_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    if os.name == "posix":
        import fcntl

        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as error:
            handle.close()
            raise ProductionError("another production runner holds the lock") from error
    else:
        import msvcrt

        try:
            if path.stat().st_size == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            handle.close()
            raise ProductionError("another production runner holds the lock") from error
    try:
        yield
    finally:
        if os.name == "posix":
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def run_once(args: argparse.Namespace) -> int:
    old_umask = os.umask(0o077)
    try:
        source_root = args.source_root.resolve()
        state_root = args.state_root.resolve()
        repo_root = args.repo_root.resolve()
        verify_frozen_repo(repo_root, args.expected_commit)
        ensure_outside(state_root, [source_root, repo_root], "production state")
        state_root.mkdir(parents=True, exist_ok=True)
        with exclusive_lock(state_root / "runner.lock"):
            fixed_dir = repo_root / "phase1" / "results" / FIXED_SCORER_DIR
            receipt_path = fixed_dir / "freeze_receipt.json"
            if sha256(receipt_path) != ACTIVE_RECEIPT_SHA256:
                raise ProductionError("active scorer receipt SHA mismatch")
            receipt = read_json(receipt_path)
            activated_at = parse_utc(str(receipt.get("activated_at_utc")))
            transactions, latest_sha = load_latest(state_root)
            observations_path = state_root / "observations.json"
            observations = load_observations(observations_path, source_root)
            observations = update_observations(
                observations,
                inventory_archives(source_root),
                args.now_epoch if args.now_epoch is not None else dt.datetime.now(
                    dt.timezone.utc
                ).timestamp(),
                args.minimum_observation_interval_seconds,
            )
            transaction_by_relative = {
                row["archive_relative_path"]: row for row in transactions
            }
            for relative, row in transaction_by_relative.items():
                entry = observations["entries"].get(relative)
                if entry is None or not entry.get("present"):
                    raise ProductionError("committed transaction source is absent from observation ledger")
                entry["committed_archive_sha256"] = row["archive_sha256"]
                entry["committed_snapshot_sha256"] = latest_sha
            atomic_bytes(observations_path, canonical_json(observations))
            now_epoch = args.now_epoch if args.now_epoch is not None else dt.datetime.now(
                dt.timezone.utc
            ).timestamp()
            ready = ready_archives(
                observations,
                now_epoch,
                args.minimum_age_seconds,
                args.minimum_observations,
                args.minimum_stable_span_seconds,
            )
            if args.observe_only or not ready:
                print(
                    "PROSPECTIVE_ARCHIVE_OBSERVATION_COMPLETE",
                    f"archives={sum(entry.get('present') is True for entry in observations['entries'].values())}",
                    f"baseline={sum(entry.get('present') is True and entry.get('baseline') is True for entry in observations['entries'].values())}",
                    f"ready={len(ready)}",
                    f"transactions={len(transactions)}",
                    "outcomes_read=false",
                    flush=True,
                )
                return 0
            status, snapshot_sha = process_archive(
                args, observations, transactions, ready[0], latest_sha
            )
            atomic_bytes(observations_path, canonical_json(observations))
            print(
                status,
                f"archive={ready[0]}",
                f"snapshot_sha256={snapshot_sha}",
                "outcomes_read=false",
                flush=True,
            )
            return 0
    finally:
        os.umask(old_umask)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--minimum-age-seconds", type=int, default=6 * 60 * 60)
    parser.add_argument("--minimum-observations", type=int, default=3)
    parser.add_argument("--minimum-observation-interval-seconds", type=int, default=5 * 60)
    parser.add_argument("--minimum-stable-span-seconds", type=int, default=10 * 60)
    parser.add_argument("--require-strace", action="store_true")
    parser.add_argument("--observe-only", action="store_true")
    parser.add_argument("--now-epoch", type=float, help=argparse.SUPPRESS)
    args = parser.parse_args()
    thresholds = (
        args.minimum_age_seconds,
        args.minimum_observations,
        args.minimum_observation_interval_seconds,
        args.minimum_stable_span_seconds,
    )
    if any(value <= 0 for value in thresholds):
        parser.error("all readiness thresholds must be positive")
    if args.minimum_stable_span_seconds < (
        args.minimum_observations - 1
    ) * args.minimum_observation_interval_seconds:
        parser.error("stable span is shorter than the required spaced observations")
    return args


def main() -> int:
    return run_once(arguments())


if __name__ == "__main__":
    raise SystemExit(main())
