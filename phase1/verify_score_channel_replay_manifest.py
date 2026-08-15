"""Independently verify the frozen score-channel replay manifest without labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


SELECTION_PROTOCOL = "score-channel-parent-selection-v1"
REPLAY_PROTOCOL = "score-channel-replay-manifest-v1"
CAP_SECONDS = 120
SHARDS = 4
SELECTION_KEYS = {
    "schema_version", "task", "run_id", "parent_id", "source_intake",
    "selection_rank_in_run", "selection_key_sha256", "candidate_card_ids",
    "candidate_count", "candidate_identity_sha256",
}
BLIND_KEYS = {
    "card_id", "task", "run_id", "code", "code_sha256", "lineage",
    "generation_started_at_utc", "source_sha256",
}
LINEAGE_KEYS = {"parent", "depth", "step", "n_siblings", "op"}
REPLAY_KEYS = {
    "schema_version", "card_id", "competition", "task", "run_id", "parent",
    "code", "code_sha256", "source_intake", "selection_rank_in_run",
    "shard_id", "cap_seconds",
}


class ReplayVerificationError(RuntimeError):
    """Fail-closed replay-manifest verification error."""


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            state.update(block)
    return state.hexdigest()


def text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def valid_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value.lower()
    ):
        raise ReplayVerificationError(f"invalid {label}")
    return value.lower()


def object_file(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReplayVerificationError(f"cannot read {label}") from error
    if not isinstance(value, dict):
        raise ReplayVerificationError(f"{label} is not an object")
    return value


def row_file(path: Path, label: str, *, allow_empty: bool = False) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ReplayVerificationError(f"cannot read {label}") from error
    if (not lines and not allow_empty) or any(not line for line in lines):
        raise ReplayVerificationError(f"{label} is empty or contains blank lines")
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
            canonical(row)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise ReplayVerificationError(f"invalid {label} line {number}") from error
        if not isinstance(row, dict):
            raise ReplayVerificationError(f"non-object {label} line {number}")
        rows.append(row)
    return rows


def shard(run_id: str) -> int:
    return int(text_digest(f"score-channel-shard-v1|{run_id}"), 16) % SHARDS


def reconstruct(
    selection_dir: Path,
    intake_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selection_summary_path = selection_dir / "summary.json"
    selected_path = selection_dir / "selected_parents.jsonl"
    summary = object_file(selection_summary_path, "parent-selection summary")
    if summary.get("protocol") != SELECTION_PROTOCOL or summary.get("status") != "PARENT_GATE_PASS_REPLAY_APPROVAL_PENDING":
        raise ReplayVerificationError("parent selection is not frozen")
    if summary.get("gates") != {
        "run_gate_pass": True,
        "task_balance_pass": True,
        "parent_gate_pass": True,
        "replay_manifest_pending": True,
        "replay_submission_authorized": False,
    }:
        raise ReplayVerificationError("parent-selection gate mismatch")
    if digest(selected_path) != valid_sha((summary.get("outputs") or {}).get("selected_parents_sha256"), "selected-parent SHA"):
        raise ReplayVerificationError("selected-parent SHA mismatch")
    selected = row_file(selected_path, "selected parents")
    wanted: dict[str, dict[str, Any]] = {}
    per_intake: dict[str, set[str]] = {}
    for row in selected:
        if set(row) != SELECTION_KEYS or row.get("schema_version") != "score-channel-parent-selection-row-v1":
            raise ReplayVerificationError("selected-parent schema mismatch")
        cards = row.get("candidate_card_ids")
        if not isinstance(cards, list) or cards != sorted(set(cards)) or len(cards) < 2 or row.get("candidate_count") != len(cards):
            raise ReplayVerificationError("selected candidate identity set mismatch")
        if text_digest(canonical(cards)) != valid_sha(row.get("candidate_identity_sha256"), "candidate identity SHA"):
            raise ReplayVerificationError("candidate identity SHA mismatch")
        intake = row.get("source_intake")
        if not isinstance(intake, str) or Path(intake).name != intake:
            raise ReplayVerificationError("invalid source intake")
        per_intake.setdefault(intake, set()).update(cards)
        for card in cards:
            if card in wanted:
                raise ReplayVerificationError("candidate selected more than once")
            wanted[card] = row
    intake_shas = (summary.get("inputs") or {}).get("intake_summary_sha256")
    if not isinstance(intake_shas, dict):
        raise ReplayVerificationError("selection intake binding is absent")
    views: dict[str, dict[str, Any]] = {}
    for intake, cards in sorted(per_intake.items()):
        root = intake_root / intake
        intake_summary_path = root / "summary.json"
        if intake not in intake_shas or digest(intake_summary_path) != valid_sha(intake_shas[intake], "intake summary SHA"):
            raise ReplayVerificationError("intake summary changed after selection")
        intake_summary = object_file(intake_summary_path, "intake summary")
        blind_path = root / "eligible_blind_manifest.jsonl"
        if digest(blind_path) != valid_sha((intake_summary.get("outputs") or {}).get("eligible_blind_manifest_sha256"), "blind-manifest SHA"):
            raise ReplayVerificationError("blind-manifest SHA mismatch")
        for view in row_file(blind_path, "eligible blind manifest"):
            card = view.get("card_id")
            if card not in cards:
                continue
            if set(view) != BLIND_KEYS or not isinstance(view.get("lineage"), dict) or set(view["lineage"]) != LINEAGE_KEYS:
                raise ReplayVerificationError("blind-view schema mismatch")
            parent = wanted[card]
            if (
                view.get("task") != parent.get("task")
                or view.get("run_id") != parent.get("run_id")
                or view["lineage"].get("parent") != parent.get("parent_id")
                or card in views
            ):
                raise ReplayVerificationError("blind-view identity mismatch")
            code = view.get("code")
            if not isinstance(code, str) or not code or text_digest(code) != valid_sha(view.get("code_sha256"), "code SHA"):
                raise ReplayVerificationError("blind-view code SHA mismatch")
            views[card] = view
    if set(views) != set(wanted):
        raise ReplayVerificationError("selected candidate code support mismatch")
    expected: list[dict[str, Any]] = []
    for card, parent in wanted.items():
        view = views[card]
        expected.append({
            "schema_version": "score-channel-replay-candidate-v1",
            "card_id": card,
            "competition": parent["task"],
            "task": parent["task"],
            "run_id": parent["run_id"],
            "parent": parent["parent_id"],
            "code": view["code"],
            "code_sha256": view["code_sha256"],
            "source_intake": parent["source_intake"],
            "selection_rank_in_run": parent["selection_rank_in_run"],
            "shard_id": shard(parent["run_id"]),
            "cap_seconds": CAP_SECONDS,
        })
    expected.sort(key=lambda row: (
        row["shard_id"], row["run_id"], row["selection_rank_in_run"], row["parent"], row["card_id"]
    ))
    return expected, summary


def verify(
    selection_dir: Path,
    intake_root: Path,
    replay_dir: Path,
    receipt_path: Path,
) -> dict[str, Any]:
    if receipt_path.exists():
        raise FileExistsError(f"refusing to overwrite replay verifier receipt: {receipt_path}")
    expected, _ = reconstruct(selection_dir, intake_root)
    summary_path = replay_dir / "summary.json"
    manifest_path = replay_dir / "replay_manifest.jsonl"
    summary = object_file(summary_path, "replay summary")
    if summary.get("protocol") != REPLAY_PROTOCOL or summary.get("status") != "REPLAY_MANIFEST_FROZEN_APPROVAL_PENDING":
        raise ReplayVerificationError("replay manifest is not frozen")
    if summary.get("inputs") != {
        "parent_selection_summary_sha256": digest(selection_dir / "summary.json"),
        "selected_parents_sha256": digest(selection_dir / "selected_parents.jsonl"),
    }:
        raise ReplayVerificationError("replay input binding mismatch")
    if summary.get("gates") != {
        "parent_gate_pass": True,
        "manifest_frozen": True,
        "user_matrix_and_budget_approval_recorded": False,
        "replay_submission_authorized": False,
    }:
        raise ReplayVerificationError("replay authorization gate mismatch")
    if digest(manifest_path) != valid_sha((summary.get("outputs") or {}).get("replay_manifest_sha256"), "replay manifest SHA"):
        raise ReplayVerificationError("replay manifest SHA mismatch")
    actual = row_file(manifest_path, "replay manifest")
    for row in actual:
        if set(row) != REPLAY_KEYS:
            raise ReplayVerificationError("replay row schema mismatch")
        if any(key in row for key in ("graded", "y_norm", "gap", "winner", "stdout_val", "sub_score")):
            raise ReplayVerificationError("replay row contains outcome-bearing key")
    if actual != expected:
        raise ReplayVerificationError("replay manifest differs from independent reconstruction")
    shard_hashes = (summary.get("outputs") or {}).get("shard_sha256")
    shard_counts = (summary.get("counts") or {}).get("shard_candidate_replays")
    if not isinstance(shard_hashes, dict) or not isinstance(shard_counts, dict):
        raise ReplayVerificationError("shard receipts are absent")
    for shard_id in range(SHARDS):
        path = replay_dir / f"shard_{shard_id}.jsonl"
        rows = row_file(path, f"shard {shard_id}", allow_empty=True)
        expected_rows = [row for row in expected if row["shard_id"] == shard_id]
        if rows != expected_rows or digest(path) != valid_sha(shard_hashes.get(str(shard_id)), "shard SHA"):
            raise ReplayVerificationError("shard rows or SHA mismatch")
        if shard_counts.get(str(shard_id)) != len(rows):
            raise ReplayVerificationError("shard count mismatch")
    counts = summary.get("counts") or {}
    physical_runs = len({row["run_id"] for row in expected})
    selected_parents = len({(row["run_id"], row["parent"]) for row in expected})
    if counts.get("physical_runs") != physical_runs or counts.get("selected_parents") != selected_parents or counts.get("planned_candidate_replays") != len(expected):
        raise ReplayVerificationError("replay counts mismatch")
    budget = summary.get("budget") or {}
    expected_hours = len(expected) * CAP_SECONDS / 3600.0
    if (
        not isinstance(budget.get("cap_upper_bound_gpu_hours"), (int, float))
        or not math.isclose(float(budget["cap_upper_bound_gpu_hours"]), expected_hours, rel_tol=0, abs_tol=1e-12)
        or budget.get("llm_api_calls") != 0
        or budget.get("gpu_jobs_submitted") != 0
    ):
        raise ReplayVerificationError("replay budget receipt mismatch")
    receipt = {
        "protocol": "score-channel-replay-manifest-independent-verifier-v1",
        "status": "PASS_REPLAY_MANIFEST_APPROVAL_PENDING",
        "implementation_independent_of_producer": True,
        "producer_module_imported": False,
        "label_vault_opened": False,
        "label_values_read": False,
        "code_identity_reconstructed": True,
        "physical_run_single_shard_reconstructed": True,
        "manifest_and_shards_exact": True,
        "planned_candidate_replays": len(expected),
        "cap_upper_bound_gpu_hours": expected_hours,
        "replay_summary_sha256": digest(summary_path),
        "replay_manifest_sha256": digest(manifest_path),
        "gpu_jobs_submitted": 0,
        "replay_submission_authorized": False,
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt_path.with_name(receipt_path.name + f".tmp-{os.getpid()}")
    if temporary.exists():
        raise FileExistsError(f"temporary replay verifier receipt exists: {temporary}")
    temporary.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    os.replace(temporary, receipt_path)
    return receipt


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-dir", required=True, type=Path)
    parser.add_argument("--intake-root", required=True, type=Path)
    parser.add_argument("--replay-dir", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    try:
        receipt = verify(args.selection_dir, args.intake_root, args.replay_dir, args.receipt)
    except (ReplayVerificationError, FileExistsError, OSError) as error:
        print(f"SCORE_CHANNEL_REPLAY_VERIFY_ERROR: {error}", file=os.sys.stderr)
        return 2
    print(canonical(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
