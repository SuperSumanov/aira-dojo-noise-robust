"""Independently verify the outcome-blind prospective structural support gate.

This module deliberately does not import the production accumulator.  It reads only
registered blind manifests, structural-pair manifests, and identity-only run records.
It never opens the label vault, frozen outcomes, grades, or scorer predictions.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any, Iterable


class VerificationError(RuntimeError):
    """Raised when an independently checked structural invariant fails."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise VerificationError(f"expected JSON object: {path.name}")
    return value


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise VerificationError(
                    f"invalid JSONL in {path.name} at line {line_number}"
                ) from error
            if not isinstance(value, dict):
                raise VerificationError(
                    f"non-object JSONL in {path.name} at line {line_number}"
                )
            yield value


def require_sha(path: Path, expected: Any) -> None:
    if not isinstance(expected, str) or sha256(path) != expected:
        raise VerificationError(f"SHA mismatch: {path.name}")


def canonical_pair(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    required = {"task", "run_id", "parent", "left", "right"}
    if set(row) != required or not all(isinstance(row[key], str) for key in required):
        raise VerificationError("structural pair schema mismatch")
    pair = (row["task"], row["run_id"], row["parent"], row["left"], row["right"])
    if not pair[3] < pair[4]:
        raise VerificationError("structural pair orientation is not canonical")
    return pair


def verify(
    state_root: Path,
    snapshot_root: Path,
    minimum_pairs: int,
    minimum_decision_runs: int,
    minimum_tasks: int,
    maximum_dominant_task_share: float,
) -> dict[str, Any]:
    state_root = state_root.resolve()
    snapshot_root = snapshot_root.resolve()
    if snapshot_root.parent != state_root / "snapshots":
        raise VerificationError("snapshot is outside the prospective state root")
    if len(snapshot_root.name) != 64 or any(c not in "0123456789abcdef" for c in snapshot_root.name):
        raise VerificationError("snapshot directory name is not a lowercase SHA-256")

    registry_path = snapshot_root / "intake_registry.jsonl"
    accumulator_dir = snapshot_root / "accumulator"
    accumulator_summary_path = accumulator_dir / "summary.json"
    provisional_runs_path = accumulator_dir / "provisional_runs.jsonl"
    registry = list(read_jsonl(registry_path))
    if not registry:
        raise VerificationError("empty intake registry")

    cards: dict[str, tuple[str, str, str, str]] = {}
    registered_pairs: set[tuple[str, str, str, str, str]] = set()
    pair_rows_seen = 0
    intake_summary_shas: dict[str, str] = {}
    opened_basenames = {
        "intake_registry.jsonl",
        "summary.json",
        "eligible_blind_manifest.jsonl",
        "eligible_structural_pairs.jsonl",
        "provisional_runs.jsonl",
    }

    seen_drops: set[str] = set()
    for entry in registry:
        if set(entry) != {"drop_id", "intake_dir", "summary_sha256"}:
            raise VerificationError("intake registry schema mismatch")
        drop_id = entry["drop_id"]
        if not isinstance(drop_id, str) or drop_id in seen_drops:
            raise VerificationError("duplicate or invalid drop ID")
        seen_drops.add(drop_id)
        intake_dir = Path(entry["intake_dir"]).resolve()
        if intake_dir.parent != state_root / "intakes" or intake_dir.name != drop_id:
            raise VerificationError("intake path binding mismatch")
        summary_path = intake_dir / "summary.json"
        require_sha(summary_path, entry["summary_sha256"])
        summary = read_json(summary_path)
        outputs = summary.get("outputs")
        security = summary.get("security")
        blindness = summary.get("blindness")
        if not isinstance(outputs, dict) or not isinstance(security, dict) or not isinstance(
            blindness, dict
        ):
            raise VerificationError("intake receipt metadata missing")
        if (
            security.get("env_members_read") is not False
            or security.get("live_event_journal_members_read") is not False
            or security.get("journal_scanned_before_json") is not True
            or blindness.get("labels_used_for_run_selection") is not False
            or blindness.get("labels_used_for_endpoint_selection") is not False
        ):
            raise VerificationError("intake blindness or credential gate mismatch")
        intake_summary_shas[drop_id] = entry["summary_sha256"]

        blind_path = intake_dir / "eligible_blind_manifest.jsonl"
        pair_path = intake_dir / "eligible_structural_pairs.jsonl"
        require_sha(blind_path, outputs.get("eligible_blind_manifest_sha256"))
        require_sha(pair_path, outputs.get("eligible_structural_pairs_sha256"))
        for row in read_jsonl(blind_path):
            try:
                card_id = row["card_id"]
                run_id = row["run_id"]
                task = row["task"]
                code_sha = row["code_sha256"]
                parent = row["lineage"]["parent"]
            except (KeyError, TypeError) as error:
                raise VerificationError("blind endpoint schema mismatch") from error
            if not all(isinstance(value, str) for value in (card_id, run_id, task, code_sha, parent)):
                raise VerificationError("blind endpoint identity type mismatch")
            if card_id in cards:
                raise VerificationError("eligible endpoint appears in multiple drops")
            cards[card_id] = (task, run_id, parent, code_sha)
        for row in read_jsonl(pair_path):
            pair_rows_seen += 1
            pair = canonical_pair(row)
            if pair in registered_pairs:
                raise VerificationError("duplicate registered structural pair")
            registered_pairs.add(pair)

    groups: dict[tuple[str, str, str], set[str]] = collections.defaultdict(set)
    for card_id, (task, run_id, parent, _code_sha) in cards.items():
        groups[(task, run_id, parent)].add(card_id)
    rebuilt_pairs = {
        (task, run_id, parent, left, right)
        for (task, run_id, parent), card_ids in groups.items()
        for left, right in itertools.combinations(sorted(card_ids), 2)
    }
    if rebuilt_pairs != registered_pairs or pair_rows_seen != len(registered_pairs):
        raise VerificationError("registered and independently rebuilt structural pairs differ")

    runs = list(read_jsonl(provisional_runs_path))
    run_rows: dict[str, dict[str, Any]] = {}
    for row in runs:
        run_id = row.get("run_id")
        if not isinstance(run_id, str) or run_id in run_rows:
            raise VerificationError("duplicate or invalid provisional run")
        if not isinstance(row.get("task"), str) or row.get("flow_status") != "scoreable":
            raise VerificationError("provisional run schema or flow mismatch")
        run_rows[run_id] = row
    endpoint_run_ids = {identity[1] for identity in cards.values()}
    if endpoint_run_ids != set(run_rows):
        raise VerificationError("blind endpoint and provisional run support differ")
    endpoint_counts = collections.Counter(identity[1] for identity in cards.values())
    if any(row.get("endpoints") != endpoint_counts[run_id] for run_id, row in run_rows.items()):
        raise VerificationError("run endpoint accounting mismatch")
    if any(identity[0] != run_rows[identity[1]]["task"] for identity in cards.values()):
        raise VerificationError("task binding differs between endpoints and runs")

    pair_task_counts = collections.Counter(pair[0] for pair in rebuilt_pairs)
    decision_run_ids = {pair[1] for pair in rebuilt_pairs}
    tasks = {str(row["task"]) for row in runs}
    code_counts = collections.Counter(identity[3] for identity in cards.values())
    dominant_pair_count = max(pair_task_counts.values(), default=0)
    pair_count = len(rebuilt_pairs)
    dominant_share = dominant_pair_count / pair_count if pair_count else None
    remaining_pairs = max(0, minimum_pairs - pair_count)
    checks = {
        "structural_pairs": pair_count >= minimum_pairs,
        "finite_decision_runs": len(decision_run_ids) >= minimum_decision_runs,
        "tasks": len(tasks) >= minimum_tasks,
        "dominant_pair_task_share": dominant_share is not None
        and dominant_share <= maximum_dominant_task_share,
    }

    accumulator_summary = read_json(accumulator_summary_path)
    inventory = accumulator_summary.get("inventory")
    support = accumulator_summary.get("task_support")
    if not isinstance(inventory, dict) or not isinstance(support, dict):
        raise VerificationError("accumulator summary schema mismatch")
    reported_support = support.get("all_eligible")
    if not isinstance(reported_support, dict):
        raise VerificationError("accumulator task support missing")
    cross_checks = {
        "transactions": inventory.get("drops") == len(registry),
        "eligible_runs": inventory.get("eligible_runs") == len(runs),
        "eligible_tasks": inventory.get("eligible_tasks") == len(tasks),
        "eligible_endpoints": inventory.get("eligible_endpoints") == len(cards),
        "eligible_structural_pairs": inventory.get("eligible_structural_pairs") == pair_count,
        "unique_exact_code_sha256": inventory.get("unique_exact_code_sha256")
        == len(code_counts),
        "exact_code_duplicate_endpoints": inventory.get("exact_code_duplicate_endpoints")
        == sum(count - 1 for count in code_counts.values()),
        "task_pair_counts": reported_support.get("structural_pair_counts")
        == dict(sorted(pair_task_counts.items())),
    }
    if not all(cross_checks.values()):
        raise VerificationError("independent inventory differs from accumulator summary")

    gate_pass = all(checks.values())
    return {
        "status": "STRUCTURAL_GATE_MET" if gate_pass else "STRUCTURAL_GATE_NOT_YET_MET",
        "protocol": "prospective_structural_gate_independent_verifier_v1",
        "source_sha256": sha256(Path(__file__)),
        "snapshot_sha256": snapshot_root.name,
        "inputs": {
            "intake_registry_sha256": sha256(registry_path),
            "accumulator_summary_sha256": sha256(accumulator_summary_path),
            "provisional_runs_sha256": sha256(provisional_runs_path),
            "intake_summary_sha256": dict(sorted(intake_summary_shas.items())),
        },
        "independent_inventory": {
            "transactions": len(registry),
            "eligible_runs": len(runs),
            "eligible_tasks": len(tasks),
            "eligible_endpoints": len(cards),
            "eligible_structural_pairs": pair_count,
            "finite_decision_runs": len(decision_run_ids),
            "pair_tasks": len(pair_task_counts),
            "dominant_pair_task_count": dominant_pair_count,
            "dominant_pair_task_share": dominant_share,
            "unique_exact_code_sha256": len(code_counts),
            "exact_code_duplicate_endpoints": sum(count - 1 for count in code_counts.values()),
        },
        "gate": {
            "minimum_structural_pairs": minimum_pairs,
            "minimum_finite_decision_runs": minimum_decision_runs,
            "minimum_tasks": minimum_tasks,
            "maximum_dominant_pair_task_share": maximum_dominant_task_share,
            "remaining_structural_pairs": remaining_pairs,
            "checks": checks,
            "all_pass": gate_pass,
            "vault_open_allowed": gate_pass,
        },
        "cross_checks_against_accumulator": cross_checks,
        "security": {
            "allowed_basenames_read": sorted(opened_basenames),
            "label_vault_opened": False,
            "outcome_files_opened": [],
            "scorer_prediction_files_opened": [],
            "code_or_task_values_emitted": False,
        },
    }


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--snapshot-root", required=True, type=Path)
    parser.add_argument("--minimum-pairs", required=True, type=int)
    parser.add_argument("--minimum-decision-runs", required=True, type=int)
    parser.add_argument("--minimum-tasks", required=True, type=int)
    parser.add_argument("--maximum-dominant-task-share", required=True, type=float)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite output: {args.output}")
    if (
        args.minimum_pairs <= 0
        or args.minimum_decision_runs <= 0
        or args.minimum_tasks <= 0
        or not 0 < args.maximum_dominant_task_share <= 1
    ):
        raise VerificationError("gate thresholds are invalid")
    receipt = verify(
        args.state_root,
        args.snapshot_root,
        args.minimum_pairs,
        args.minimum_decision_runs,
        args.minimum_tasks,
        args.maximum_dominant_task_share,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "PROSPECTIVE_STRUCTURAL_GATE_INDEPENDENT_VERIFICATION_COMPLETE",
        f"status={receipt['status']}",
        f"pairs={receipt['independent_inventory']['eligible_structural_pairs']}",
        f"decision_runs={receipt['independent_inventory']['finite_decision_runs']}",
        f"tasks={receipt['independent_inventory']['eligible_tasks']}",
        f"remaining_pairs={receipt['gate']['remaining_structural_pairs']}",
        "outcomes_read=false",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
