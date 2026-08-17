#!/usr/bin/env python3
"""Independent verifier for a result-blind score-channel orientation receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


SELECTION_KEYS = {
    "schema_version", "task", "run_id", "parent_id", "source_intake",
    "selection_rank_in_run", "selection_key_sha256", "candidate_card_ids",
    "candidate_count", "candidate_identity_sha256",
}


class VerifyError(RuntimeError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            state.update(block)
    return state.hexdigest()


def sha(value: Any, label: str) -> str:
    if (
        not isinstance(value, str) or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value.lower())
    ):
        raise VerifyError(f"invalid {label}")
    return value.lower()


def obj(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        canonical(value)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise VerifyError(f"invalid {label}") from error
    if not isinstance(value, dict):
        raise VerifyError(f"non-object {label}")
    return value


def rows(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise VerifyError("cannot read selected parents") from error
    if not lines or any(not line for line in lines):
        raise VerifyError("selected parents empty or blank")
    output = []
    for line in lines:
        try:
            value = json.loads(line)
            canonical(value)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise VerifyError("invalid selected-parent row") from error
        if not isinstance(value, dict):
            raise VerifyError("non-object selected-parent row")
        output.append(value)
    return output


def rebuild(args: argparse.Namespace) -> dict[str, Any]:
    expected_receipt = sha(args.expect_orientation_sha256, "orientation receipt SHA")
    if digest(args.orientation) != expected_receipt:
        raise VerifyError("orientation receipt SHA mismatch")
    summary_path = args.selection_dir / "summary.json"
    parent_path = args.selection_dir / "selected_parents.jsonl"
    summary = obj(summary_path, "selection summary")
    if (
        summary.get("protocol") != "score-channel-parent-selection-v1"
        or summary.get("status") != "PARENT_GATE_PASS_REPLAY_APPROVAL_PENDING"
        or (summary.get("gates") or {}).get("parent_gate_pass") is not True
        or digest(parent_path) != sha(
            (summary.get("outputs") or {}).get("selected_parents_sha256"),
            "selected-parent SHA",
        )
    ):
        raise VerifyError("selection contract mismatch")
    selected = rows(parent_path)
    seen: set[tuple[str, str]] = set()
    tasks: set[str] = set()
    for row in selected:
        key = (row.get("run_id"), row.get("parent_id"))
        task = row.get("task")
        if (
            set(row) != SELECTION_KEYS
            or row.get("schema_version") != "score-channel-parent-selection-row-v1"
            or not isinstance(task, str) or not task
            or key in seen
        ):
            raise VerifyError("invalid selected-parent identity")
        seen.add(key)
        tasks.add(task)
    if (summary.get("counts") or {}).get("selected_parents") != len(selected):
        raise VerifyError("selected-parent count mismatch")

    legacy = obj(args.legacy, "legacy source")
    if any(type(value) is not bool for value in legacy.values()):
        raise VerifyError("invalid legacy source")
    supplement = obj(args.supplement, "supplement")
    if (
        supplement.get("protocol") != "score-channel-metric-orientation-source-v1"
        or supplement.get("outcomes_read") is not False
        or supplement.get("created_before_replay_outcomes") is not True
        or not isinstance(supplement.get("tasks"), dict)
    ):
        raise VerifyError("supplement contract mismatch")
    merged = dict(legacy)
    source = {task: "legacy" for task in legacy}
    for task, row in supplement["tasks"].items():
        if (
            not isinstance(row, dict) or type(row.get("lower_is_better")) is not bool
            or row.get("orientation") != (-1 if row["lower_is_better"] else 1)
        ):
            raise VerifyError("invalid supplemental task")
        lower = row["lower_is_better"]
        if task in merged and merged[task] is not lower:
            raise VerifyError("source conflict")
        source[task] = "legacy+supplement" if task in legacy else "supplement"
        merged[task] = lower
    if not tasks <= set(merged):
        raise VerifyError("selected orientation missing")
    ordered = sorted(tasks)
    expected = {
        "protocol": "score-channel-task-orientation-v1",
        "created_before_replay_outcomes": True,
        "outcomes_read": False,
        "tasks": ordered,
        "lower_is_better": {task: merged[task] for task in ordered},
        "orientation": {task: -1 if merged[task] else 1 for task in ordered},
        "source_by_task": {task: source[task] for task in ordered},
        "inputs": {
            "selection_summary_sha256": digest(summary_path),
            "selected_parents_sha256": digest(parent_path),
            "legacy_orientation_sha256": digest(args.legacy),
            "orientation_supplement_sha256": digest(args.supplement),
        },
    }
    actual = obj(args.orientation, "orientation receipt")
    for key, value in expected.items():
        if actual.get(key) != value:
            raise VerifyError(f"orientation receipt differs for {key}")
    implementation = actual.get("implementation")
    if (
        not isinstance(implementation, dict)
        or not isinstance(implementation.get("source_commit"), str)
        or len(implementation["source_commit"]) != 40
        or not isinstance(implementation.get("python"), str)
    ):
        raise VerifyError("invalid producer implementation receipt")
    sha(implementation.get("script_sha256"), "producer script SHA")
    return {
        "protocol": "score-channel-orientation-independent-verifier-v1",
        "status": "VERIFIED_SCORE_CHANNEL_TASK_ORIENTATION",
        "producer_imported": False,
        "outcomes_read": False,
        "orientation_sha256": expected_receipt,
        "tasks": ordered,
        "orientation": expected["orientation"],
        "inputs": expected["inputs"],
    }


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-dir", type=Path, required=True)
    parser.add_argument("--legacy", type=Path, required=True)
    parser.add_argument("--supplement", type=Path, required=True)
    parser.add_argument("--orientation", type=Path, required=True)
    parser.add_argument("--expect-orientation-sha256", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if args.receipt.exists():
        print("SCORE_CHANNEL_ORIENTATION_VERIFY_ERROR: refusing to overwrite receipt", file=os.sys.stderr)
        return 2
    try:
        value = rebuild(args)
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8", newline="\n",
        )
    except (VerifyError, OSError) as error:
        print(f"SCORE_CHANNEL_ORIENTATION_VERIFY_ERROR: {error}", file=os.sys.stderr)
        return 2
    print(canonical({"status": value["status"], "tasks": value["tasks"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
