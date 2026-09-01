"""Independent verifier for Target-522 watcher gap recovery."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_HEADER = [
    "snapshot_sha256", "runs", "endpoints", "tasks", "summary_sha256",
    "registry_sha256", "runs_sha256", "observed_at_utc",
]


class VerificationError(RuntimeError):
    pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def object_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise VerificationError(f"regular JSON required: {path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"invalid JSON: {path.name}") from error
    if not isinstance(value, dict):
        raise VerificationError("JSON object required")
    return value


def structural_fields(state: Path, spec: dict[str, Any]) -> tuple[int, int, int]:
    snapshot = spec["snapshot_sha256"]
    root = state / "snapshots" / snapshot
    if not root.is_dir() or root.is_symlink():
        raise VerificationError("snapshot root mismatch")
    summary_path = root / "accumulator" / "summary.json"
    registry_path = root / "intake_registry.jsonl"
    runs_path = root / "accumulator" / "provisional_runs.jsonl"
    for path, field in (
        (summary_path, "summary_sha256"),
        (registry_path, "registry_sha256"),
        (runs_path, "runs_sha256"),
    ):
        if not path.is_file() or path.is_symlink() or sha(path) != spec[field]:
            raise VerificationError(f"{field} drift")
    summary = object_json(summary_path)
    try:
        if summary["protocol"] != "prospective_accumulator_v1" or summary["closure"]["provided"] is not False:
            raise VerificationError("accumulator state mismatch")
        security = summary["security"]
        if security["label_vault_opened"] is not False:
            raise VerificationError("label vault opened")
        if security["outcome_files_opened"] != [] or security["scorer_prediction_files_opened"] != []:
            raise VerificationError("value file opened")
        if summary["inputs"]["registry_sha256"] != spec["registry_sha256"]:
            raise VerificationError("registry binding mismatch")
        if summary["outputs"]["provisional_runs_sha256"] != spec["runs_sha256"]:
            raise VerificationError("run binding mismatch")
        values = (
            summary["inventory"]["provisional_first960_runs"],
            summary["inventory"]["provisional_first960_endpoints"],
            summary["task_support"]["provisional_first960"]["tasks"],
        )
    except (KeyError, TypeError) as error:
        raise VerificationError("summary schema mismatch") from error
    if any(type(value) is not int or value <= 0 for value in values):
        raise VerificationError("invalid structural count")
    return values


def verify(protocol_path: Path, output: Path) -> dict[str, Any]:
    protocol = object_json(protocol_path)
    if protocol.get("protocol") != "target522-selection-gap-recovery-v1":
        raise VerificationError("protocol mismatch")
    if protocol.get("status") != "FROZEN_BEFORE_SUCCESSOR_RUN_COUNTS_READ":
        raise VerificationError("protocol status mismatch")
    selection = Path(protocol["selection_root"])
    state = Path(protocol["state_root"])
    if not selection.is_dir() or selection.is_symlink() or not state.is_dir() or state.is_symlink():
        raise VerificationError("root mismatch")
    if sha(selection / "protocol.json") != protocol["selection_protocol_sha256"]:
        raise VerificationError("selection protocol drift")
    if sha(selection / "source_script.sh") != protocol["selection_source_script_sha256"]:
        raise VerificationError("selection script drift")
    preflight_path = selection / "preflight_13.txt"
    if not preflight_path.is_file() or preflight_path.is_symlink():
        raise VerificationError("selection preflight missing")
    preflight = preflight_path.read_text(encoding="utf-8").splitlines()
    if f'03_source_commit={protocol["selection_source_commit"]}; PASS' not in preflight:
        raise VerificationError("selection source commit binding mismatch")
    if f'04_protocol_sha256={protocol["selection_protocol_sha256"]}; PASS' not in preflight:
        raise VerificationError("selection protocol binding mismatch")
    old_observed = selection / "observed.tsv"
    if sha(old_observed) != protocol["old_observed_sha256"]:
        raise VerificationError("old observed drift")
    old_rows = list(csv.reader(old_observed.read_text(encoding="utf-8").splitlines(), delimiter="\t"))
    if len(old_rows) != protocol["old_observed_lines"] or old_rows[0] != EXPECTED_HEADER:
        raise VerificationError("old observed shape mismatch")
    if old_rows[-1][0] != protocol["last_observed_snapshot_sha256"] or int(old_rows[-1][1]) != protocol["last_observed_runs"]:
        raise VerificationError("old observed tail mismatch")
    if (selection / "TIMEOUT_RC").read_text(encoding="utf-8").strip() != str(protocol["timeout_rc"]):
        raise VerificationError("timeout mismatch")
    for marker in ("candidate.tsv", "READY", "COMPLETE", "FAILED_RC", "CONTINUITY_GAP"):
        if (selection / marker).exists():
            raise VerificationError("forbidden selection marker")
    if (state / "LATEST").read_text(encoding="utf-8").strip() != protocol["current_latest_sha256"]:
        raise VerificationError("LATEST drift")

    manifest = output / "SHA256SUMS"
    expected_manifest: list[str] = []
    for name in ("observed_extension.tsv", "summary.json"):
        path = output / name
        if not path.is_file() or path.is_symlink():
            raise VerificationError("output file missing")
        expected_manifest.append(f"{sha(path)}  {name}")
    if manifest.read_text(encoding="utf-8").splitlines() != expected_manifest:
        raise VerificationError("output manifest mismatch")

    extension_bytes = (output / "observed_extension.tsv").read_bytes()
    try:
        extension_rows = list(csv.reader(extension_bytes.decode("utf-8").splitlines(), delimiter="\t"))
    except UnicodeDecodeError as error:
        raise VerificationError("extension is not UTF-8") from error
    specs = protocol.get("ordered_successors")
    if not isinstance(specs, list) or len(specs) != 7 or len(extension_rows) != 7:
        raise VerificationError("successor count mismatch")
    previous = protocol["last_observed_runs"]
    target = protocol["target_runs"]
    rebuilt: list[list[str]] = []
    for spec in specs:
        runs, endpoints, tasks = structural_fields(state, spec)
        if runs < previous or runs >= target:
            raise VerificationError("monotonicity or no-crossing gate failed")
        previous = runs
        rebuilt.append([
            spec["snapshot_sha256"], str(runs), str(endpoints), str(tasks),
            spec["summary_sha256"], spec["registry_sha256"], spec["runs_sha256"],
            protocol["frozen_at_utc"],
        ])
    if rebuilt != extension_rows or rebuilt[-1][0] != protocol["current_latest_sha256"]:
        raise VerificationError("extension reconstruction mismatch")
    recovered_sha = hashlib.sha256(old_observed.read_bytes() + extension_bytes).hexdigest()
    summary = object_json(output / "summary.json")
    expected = {
        "status": "TARGET522_GAP_RECOVERY_NO_CROSSING_PASS",
        "protocol_sha256": sha(protocol_path),
        "old_observed_sha256": protocol["old_observed_sha256"],
        "recovered_observed_sha256": recovered_sha,
        "recovered_successors": 7,
        "previous_runs": protocol["last_observed_runs"],
        "final_runs": previous,
        "target_runs": target,
        "remaining_runs": target - previous,
        "current_latest_sha256": protocol["current_latest_sha256"],
        "outcomes_read": False,
        "candidate_identity_or_profile_read": False,
        "registry_or_run_payload_parsed": False,
    }
    if summary != expected:
        raise VerificationError("summary mismatch")
    return {
        "status": "TARGET522_GAP_RECOVERY_INDEPENDENT_PASS",
        "recovered_successors": 7,
        "final_runs": previous,
        "remaining_runs": target - previous,
        "recovered_observed_sha256": recovered_sha,
        "producer_imported": False,
        "outcomes_read": False,
        "candidate_identity_or_profile_read": False,
        "registry_or_run_payload_parsed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("protocol", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    result = verify(args.protocol, args.output)
    if args.receipt.exists():
        raise VerificationError("receipt already exists")
    args.receipt.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
