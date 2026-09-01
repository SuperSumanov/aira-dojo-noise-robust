"""Recover an expired Target-522 structural watcher without reading identities or values."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


HEADER = [
    "snapshot_sha256", "runs", "endpoints", "tasks", "summary_sha256",
    "registry_sha256", "runs_sha256", "observed_at_utc",
]


class RecoveryError(RuntimeError):
    pass


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def regular(path: Path) -> None:
    if not path.is_file() or path.is_symlink():
        raise RecoveryError(f"not a regular file: {path.name}")


def load_json(path: Path) -> dict[str, Any]:
    regular(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RecoveryError(f"invalid JSON: {path.name}") from error
    if not isinstance(value, dict):
        raise RecoveryError(f"JSON object required: {path.name}")
    return value


def parse_old_observed(path: Path, expected_lines: int) -> list[list[str]]:
    regular(path)
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines(), delimiter="\t"))
    if len(rows) != expected_lines or not rows or rows[0] != HEADER:
        raise RecoveryError("old observed ledger shape mismatch")
    seen: set[str] = set()
    previous = -1
    for row in rows[1:]:
        if len(row) != 8 or len(row[0]) != 64 or row[0] in seen:
            raise RecoveryError("invalid old observed row")
        if any(character not in "0123456789abcdef" for character in row[0]):
            raise RecoveryError("invalid old snapshot hash")
        try:
            count = int(row[1])
        except ValueError as error:
            raise RecoveryError("invalid old run count") from error
        if count < previous:
            raise RecoveryError("old observed counts regress")
        previous = count
        seen.add(row[0])
    return rows


def snapshot_row(state_root: Path, spec: dict[str, Any], observed_at: str) -> list[str]:
    snapshot = spec["snapshot_sha256"]
    if not isinstance(snapshot, str) or len(snapshot) != 64:
        raise RecoveryError("invalid successor hash")
    root = state_root / "snapshots" / snapshot
    if not root.is_dir() or root.is_symlink():
        raise RecoveryError("snapshot root mismatch")
    summary_path = root / "accumulator" / "summary.json"
    registry_path = root / "intake_registry.jsonl"
    runs_path = root / "accumulator" / "provisional_runs.jsonl"
    for path, key in (
        (summary_path, "summary_sha256"),
        (registry_path, "registry_sha256"),
        (runs_path, "runs_sha256"),
    ):
        regular(path)
        if digest(path) != spec[key]:
            raise RecoveryError(f"{key} mismatch")
    summary = load_json(summary_path)
    try:
        security = summary["security"]
        inventory = summary["inventory"]
        support = summary["task_support"]["provisional_first960"]
        if summary["protocol"] != "prospective_accumulator_v1":
            raise RecoveryError("accumulator protocol mismatch")
        if summary["closure"]["provided"] is not False:
            raise RecoveryError("closed accumulator is forbidden")
        if security["label_vault_opened"] is not False:
            raise RecoveryError("label vault was opened")
        if security["outcome_files_opened"] != [] or security["scorer_prediction_files_opened"] != []:
            raise RecoveryError("outcome or prediction file was opened")
        if summary["inputs"]["registry_sha256"] != spec["registry_sha256"]:
            raise RecoveryError("summary registry binding mismatch")
        if summary["outputs"]["provisional_runs_sha256"] != spec["runs_sha256"]:
            raise RecoveryError("summary runs binding mismatch")
        counts = (
            inventory["provisional_first960_runs"],
            inventory["provisional_first960_endpoints"],
            support["tasks"],
        )
    except (KeyError, TypeError) as error:
        raise RecoveryError("accumulator summary schema mismatch") from error
    if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in counts):
        raise RecoveryError("invalid structural count")
    return [snapshot, *(str(value) for value in counts), spec["summary_sha256"], spec["registry_sha256"], spec["runs_sha256"], observed_at]


def analyze(protocol_path: Path) -> tuple[bytes, dict[str, Any]]:
    protocol = load_json(protocol_path)
    if protocol.get("protocol") != "target522-selection-gap-recovery-v1" or protocol.get("version") != 1:
        raise RecoveryError("protocol identity mismatch")
    if protocol.get("status") != "FROZEN_BEFORE_SUCCESSOR_RUN_COUNTS_READ":
        raise RecoveryError("protocol was not result-blind frozen")
    state_root = Path(protocol["state_root"])
    selection_root = Path(protocol["selection_root"])
    if not state_root.is_dir() or state_root.is_symlink() or not selection_root.is_dir() or selection_root.is_symlink():
        raise RecoveryError("root mismatch")
    if digest(selection_root / "protocol.json") != protocol["selection_protocol_sha256"]:
        raise RecoveryError("selection protocol drift")
    if digest(selection_root / "source_script.sh") != protocol["selection_source_script_sha256"]:
        raise RecoveryError("selection source drift")
    regular(selection_root / "preflight_13.txt")
    preflight = (selection_root / "preflight_13.txt").read_text(encoding="utf-8").splitlines()
    if f'03_source_commit={protocol["selection_source_commit"]}; PASS' not in preflight:
        raise RecoveryError("selection source commit binding mismatch")
    if f'04_protocol_sha256={protocol["selection_protocol_sha256"]}; PASS' not in preflight:
        raise RecoveryError("selection protocol binding mismatch")
    observed_path = selection_root / "observed.tsv"
    if digest(observed_path) != protocol["old_observed_sha256"]:
        raise RecoveryError("old observed hash drift")
    old_rows = parse_old_observed(observed_path, protocol["old_observed_lines"])
    if old_rows[-1][0] != protocol["last_observed_snapshot_sha256"] or int(old_rows[-1][1]) != protocol["last_observed_runs"]:
        raise RecoveryError("old observed tail mismatch")
    regular(selection_root / "TIMEOUT_RC")
    if (selection_root / "TIMEOUT_RC").read_text(encoding="utf-8").strip() != str(protocol["timeout_rc"]):
        raise RecoveryError("timeout receipt mismatch")
    for marker in ("candidate.tsv", "READY", "COMPLETE", "FAILED_RC", "CONTINUITY_GAP"):
        if (selection_root / marker).exists():
            raise RecoveryError(f"forbidden selection marker: {marker}")
    regular(state_root / "LATEST")
    if (state_root / "LATEST").read_text(encoding="utf-8").strip() != protocol["current_latest_sha256"]:
        raise RecoveryError("current LATEST mismatch")
    successors = protocol.get("ordered_successors")
    if not isinstance(successors, list) or len(successors) != 7:
        raise RecoveryError("exactly seven successors required")
    rows = [snapshot_row(state_root, spec, protocol["frozen_at_utc"]) for spec in successors]
    hashes = [row[0] for row in rows]
    if len(set(hashes)) != len(hashes) or hashes[-1] != protocol["current_latest_sha256"]:
        raise RecoveryError("successor identity/order mismatch")
    previous = protocol["last_observed_runs"]
    target = protocol["target_runs"]
    for row in rows:
        count = int(row[1])
        if count < previous:
            raise RecoveryError("successor counts regress")
        if count >= target:
            raise RecoveryError("possible skipped Target-522 crossing")
        previous = count
    extension = "".join("\t".join(row) + "\n" for row in rows).encode("utf-8")
    recovered_observed_sha = hashlib.sha256(observed_path.read_bytes() + extension).hexdigest()
    summary = {
        "status": "TARGET522_GAP_RECOVERY_NO_CROSSING_PASS",
        "protocol_sha256": digest(protocol_path),
        "old_observed_sha256": protocol["old_observed_sha256"],
        "recovered_observed_sha256": recovered_observed_sha,
        "recovered_successors": len(rows),
        "previous_runs": protocol["last_observed_runs"],
        "final_runs": previous,
        "target_runs": target,
        "remaining_runs": target - previous,
        "current_latest_sha256": protocol["current_latest_sha256"],
        "outcomes_read": False,
        "candidate_identity_or_profile_read": False,
        "registry_or_run_payload_parsed": False,
    }
    return extension, summary


def write(output: Path, extension: bytes, summary: dict[str, Any]) -> None:
    if output.exists():
        raise RecoveryError("output already exists")
    output.mkdir(parents=True)
    (output / "observed_extension.tsv").write_bytes(extension)
    (output / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    lines = []
    for name in ("observed_extension.tsv", "summary.json"):
        lines.append(f"{digest(output / name)}  {name}\n")
    (output / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("protocol", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    write(args.output, *analyze(args.protocol))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
