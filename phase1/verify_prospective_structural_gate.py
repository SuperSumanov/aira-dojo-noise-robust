"""Independently verify the outcome-blind prospective structural support gate.

This module deliberately does not import the production accumulator.  It reads only
registered blind manifests, structural-pair manifests, and identity-only run records.
It never opens the label vault, frozen outcomes, grades, or scorer predictions.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import itertools
import json
import math
import platform
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


class VerificationError(RuntimeError):
    """Raised when an independently checked structural invariant fails."""


FROZEN_CONFIRMATORY_RUNS = 960
FROZEN_MINIMUM_PAIRS = 1_500
FROZEN_MINIMUM_DECISION_RUNS = 150
FROZEN_MINIMUM_TASKS = 15
FROZEN_MAXIMUM_DOMINANT_TASK_SHARE = 0.25


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
    minimum_cohort_runs: int,
    source_commit: str,
) -> dict[str, Any]:
    state_root = state_root.resolve()
    snapshot_root = snapshot_root.resolve()
    if snapshot_root.parent != state_root / "snapshots":
        raise VerificationError("snapshot is outside the prospective state root")
    if len(snapshot_root.name) != 64 or any(c not in "0123456789abcdef" for c in snapshot_root.name):
        raise VerificationError("snapshot directory name is not a lowercase SHA-256")
    if len(source_commit) != 40 or any(c not in "0123456789abcdef" for c in source_commit):
        raise VerificationError("source commit is not a lowercase full Git SHA")
    if minimum_cohort_runs <= 0:
        raise VerificationError("confirmatory cohort run target is invalid")

    registry_path = snapshot_root / "intake_registry.jsonl"
    accumulator_dir = snapshot_root / "accumulator"
    accumulator_summary_path = accumulator_dir / "summary.json"
    provisional_runs_path = accumulator_dir / "provisional_runs.jsonl"
    registry = list(read_jsonl(registry_path))
    if not registry:
        raise VerificationError("empty intake registry")

    cards: dict[str, tuple[str, str, str, str]] = {}
    drop_for_run: dict[str, str] = {}
    day_for_drop: dict[str, str] = {}
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
        day_for_drop[drop_id] = drop_id.split("-", 1)[0]
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
            run_owner = drop_for_run.setdefault(run_id, drop_id)
            if run_owner != drop_id:
                raise VerificationError("eligible run appears in multiple drops")
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
        if row.get("drop_id") != drop_for_run.get(run_id):
            raise VerificationError("provisional run drop binding mismatch")
        generation_started_at_utc = row.get("generation_started_at_utc")
        source_sha256 = row.get("source_sha256")
        if not isinstance(generation_started_at_utc, str) or not isinstance(source_sha256, str):
            raise VerificationError("provisional run ordering identity missing")
        try:
            timestamp = dt.datetime.fromisoformat(generation_started_at_utc.replace("Z", "+00:00"))
        except ValueError as error:
            raise VerificationError("invalid provisional run UTC timestamp") from error
        if timestamp.tzinfo is None or timestamp.utcoffset() != dt.timedelta(0):
            raise VerificationError("provisional run timestamp is not explicit UTC")
        if len(source_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in source_sha256
        ):
            raise VerificationError("provisional run source SHA is invalid")
        run_rows[run_id] = row
    endpoint_run_ids = {identity[1] for identity in cards.values()}
    if endpoint_run_ids != set(run_rows):
        raise VerificationError("blind endpoint and provisional run support differ")
    endpoint_counts = collections.Counter(identity[1] for identity in cards.values())
    if any(row.get("endpoints") != endpoint_counts[run_id] for run_id, row in run_rows.items()):
        raise VerificationError("run endpoint accounting mismatch")
    if any(identity[0] != run_rows[identity[1]]["task"] for identity in cards.values()):
        raise VerificationError("task binding differs between endpoints and runs")

    ordered_runs = sorted(
        runs,
        key=lambda row: (
            str(row["generation_started_at_utc"]),
            str(row["source_sha256"]),
            str(row["run_id"]),
        ),
    )
    cohort_rows = ordered_runs[:minimum_cohort_runs]
    cohort_run_ids = {str(row["run_id"]) for row in cohort_rows}
    cohort_cards = {
        card_id: identity for card_id, identity in cards.items() if identity[1] in cohort_run_ids
    }
    cohort_pairs = {pair for pair in rebuilt_pairs if pair[1] in cohort_run_ids}
    pair_task_counts = collections.Counter(pair[0] for pair in cohort_pairs)
    decision_run_ids = {pair[1] for pair in cohort_pairs}
    tasks = {str(row["task"]) for row in cohort_rows}
    code_counts = collections.Counter(identity[3] for identity in cohort_cards.values())
    code_runs: dict[str, set[str]] = collections.defaultdict(set)
    code_tasks: dict[str, set[str]] = collections.defaultdict(set)
    for task, run_id, _parent, code_sha in cohort_cards.values():
        code_runs[code_sha].add(run_id)
        code_tasks[code_sha].add(task)
    dominant_pair_count = max(pair_task_counts.values(), default=0)
    pair_count = len(cohort_pairs)
    dominant_share = dominant_pair_count / pair_count if pair_count else None
    pair_run_counts = collections.Counter(pair[1] for pair in cohort_pairs)
    decision_parent_groups = {(pair[0], pair[1], pair[2]) for pair in cohort_pairs}
    task_pair_coverage = len(pair_task_counts) / len(tasks) if tasks else None
    run_pair_coverage = len(decision_run_ids) / len(cohort_rows) if cohort_rows else None
    code_unique_fraction = len(code_counts) / len(cohort_cards) if cohort_cards else None
    duplicate_code_shas = {code_sha for code_sha, count in code_counts.items() if count > 1}
    cross_run_duplicate_groups = sum(
        len(code_runs[code_sha]) > 1 for code_sha in duplicate_code_shas
    )
    cross_task_duplicate_groups = sum(
        len(code_tasks[code_sha]) > 1 for code_sha in duplicate_code_shas
    )
    pair_probabilities = [
        pair_task_counts[task] / pair_count for task in sorted(pair_task_counts)
    ]
    pair_task_hhi = sum(probability**2 for probability in pair_probabilities)
    effective_pair_tasks = 1 / pair_task_hhi if pair_task_hhi else None
    normalized_pair_task_entropy = (
        -sum(probability * math.log(probability) for probability in pair_probabilities)
        / math.log(len(pair_probabilities))
        if len(pair_probabilities) > 1
        else None
    )

    cohort_drop_ids = {drop_for_run[run_id] for run_id in cohort_run_ids}
    day_transactions = collections.Counter(day_for_drop[drop_id] for drop_id in cohort_drop_ids)
    day_runs: dict[str, set[str]] = collections.defaultdict(set)
    day_decision_runs: dict[str, set[str]] = collections.defaultdict(set)
    day_tasks: dict[str, set[str]] = collections.defaultdict(set)
    day_pair_tasks: dict[str, set[str]] = collections.defaultdict(set)
    day_endpoints = collections.Counter()
    day_pairs = collections.Counter()
    for task, run_id, _parent, _code_sha in cohort_cards.values():
        day = day_for_drop[drop_for_run[run_id]]
        day_runs[day].add(run_id)
        day_tasks[day].add(task)
        day_endpoints[day] += 1
    for task, run_id, _parent, _left, _right in cohort_pairs:
        day = day_for_drop[drop_for_run[run_id]]
        day_decision_runs[day].add(run_id)
        day_pair_tasks[day].add(task)
        day_pairs[day] += 1
    per_day_support = {
        day: {
            "transactions": day_transactions[day],
            "eligible_runs": len(day_runs[day]),
            "finite_decision_runs": len(day_decision_runs[day]),
            "eligible_tasks": len(day_tasks[day]),
            "pair_tasks": len(day_pair_tasks[day]),
            "eligible_endpoints": day_endpoints[day],
            "eligible_structural_pairs": day_pairs[day],
        }
        for day in sorted(day_transactions)
    }
    remaining_pairs = max(0, minimum_pairs - pair_count)
    remaining_cohort_runs = max(0, minimum_cohort_runs - len(cohort_rows))

    accumulator_summary = read_json(accumulator_summary_path)
    inventory = accumulator_summary.get("inventory")
    support = accumulator_summary.get("task_support")
    if not isinstance(inventory, dict) or not isinstance(support, dict):
        raise VerificationError("accumulator summary schema mismatch")
    reported_support = support.get("all_eligible")
    reported_cohort_support = support.get("provisional_first960")
    if not isinstance(reported_support, dict) or not isinstance(reported_cohort_support, dict):
        raise VerificationError("accumulator task support missing")
    closure = accumulator_summary.get("closure")
    accumulator_status = accumulator_summary.get("status")
    if not isinstance(closure, dict) or not isinstance(accumulator_status, str):
        raise VerificationError("accumulator closure metadata missing")
    cross_checks = {
        "transactions": inventory.get("drops") == len(registry),
        "eligible_runs": inventory.get("eligible_runs") == len(ordered_runs),
        "eligible_tasks": inventory.get("eligible_tasks")
        == len({str(row["task"]) for row in ordered_runs}),
        "eligible_endpoints": inventory.get("eligible_endpoints") == len(cards),
        "eligible_structural_pairs": inventory.get("eligible_structural_pairs")
        == len(rebuilt_pairs),
        "provisional_first960_runs": inventory.get("provisional_first960_runs")
        == len(cohort_rows),
        "provisional_first960_endpoints": inventory.get("provisional_first960_endpoints")
        == len(cohort_cards),
        "provisional_first960_structural_pairs": inventory.get(
            "provisional_first960_structural_pairs"
        )
        == pair_count,
        "unique_exact_code_sha256": inventory.get("unique_exact_code_sha256")
        == len({identity[3] for identity in cards.values()}),
        "exact_code_duplicate_endpoints": inventory.get("exact_code_duplicate_endpoints")
        == sum(
            count - 1
            for count in collections.Counter(identity[3] for identity in cards.values()).values()
        ),
        "task_pair_counts": reported_support.get("structural_pair_counts")
        == dict(sorted(collections.Counter(pair[0] for pair in rebuilt_pairs).items())),
        "provisional_first960_task_pair_counts": reported_cohort_support.get(
            "structural_pair_counts"
        )
        == dict(sorted(pair_task_counts.items())),
    }
    if not all(cross_checks.values()):
        raise VerificationError("independent inventory differs from accumulator summary")

    cohort_complete = len(cohort_rows) >= minimum_cohort_runs
    closure_ready = (
        closure.get("provided") is True
        and closure.get("all_scheduled_runs_uploaded") is True
        and closure.get("outcomes_read") is False
        and accumulator_status == "PROSPECTIVE_FIRST960_IDENTITY_FROZEN"
    )
    checks = {
        "confirmatory_cohort_runs": cohort_complete,
        "accrual_closed_without_outcomes": closure_ready,
        "structural_pairs": pair_count >= minimum_pairs,
        "finite_decision_runs": len(decision_run_ids) >= minimum_decision_runs,
        "tasks": len(tasks) >= minimum_tasks,
        "dominant_pair_task_share": dominant_share is not None
        and dominant_share <= maximum_dominant_task_share,
    }
    gate_pass = all(checks.values())
    if len(cohort_rows) < minimum_cohort_runs:
        status = "CONFIRMATORY_COHORT_COLLECTING"
    elif not closure_ready:
        status = "CONFIRMATORY_COHORT_AWAITING_CLOSURE"
    elif gate_pass:
        status = "CONFIRMATORY_STRUCTURAL_GATE_MET"
    else:
        status = "CONFIRMATORY_COHORT_INSUFFICIENT_SUPPORT"
    return {
        "status": status,
        "protocol": "prospective_structural_gate_independent_verifier_v4",
        "source_sha256": sha256(Path(__file__)),
        "snapshot_sha256": snapshot_root.name,
        "reproducibility": {
            "source_commit": source_commit,
            "python_executable": str(Path(sys.executable).resolve()),
            "python_version": platform.python_version(),
            "randomness_used": False,
            "thresholds": {
                "minimum_structural_pairs": minimum_pairs,
                "minimum_finite_decision_runs": minimum_decision_runs,
                "minimum_tasks": minimum_tasks,
                "maximum_dominant_pair_task_share": maximum_dominant_task_share,
                "minimum_confirmatory_cohort_runs": minimum_cohort_runs,
                "accrual_closure_required": True,
            },
        },
        "inputs": {
            "intake_registry_sha256": sha256(registry_path),
            "accumulator_summary_sha256": sha256(accumulator_summary_path),
            "provisional_runs_sha256": sha256(provisional_runs_path),
            "intake_summary_sha256": dict(sorted(intake_summary_shas.items())),
        },
        "independent_inventory": {
            "transactions": len(registry),
            "all_eligible": {
                "runs": len(ordered_runs),
                "tasks": len({str(row["task"]) for row in ordered_runs}),
                "endpoints": len(cards),
                "structural_pairs": len(rebuilt_pairs),
            },
            "provisional_first960": {
                "target_runs": minimum_cohort_runs,
                "runs": len(cohort_rows),
                "tasks": len(tasks),
                "endpoints": len(cohort_cards),
                "structural_pairs": pair_count,
                "finite_decision_runs": len(decision_run_ids),
                "pair_tasks": len(pair_task_counts),
                "dominant_pair_task_count": dominant_pair_count,
                "dominant_pair_task_share": dominant_share,
                "unique_exact_code_sha256": len(code_counts),
                "exact_code_duplicate_endpoints": sum(
                    count - 1 for count in code_counts.values()
                ),
            },
        },
        "gate": {
            "minimum_confirmatory_cohort_runs": minimum_cohort_runs,
            "minimum_structural_pairs": minimum_pairs,
            "minimum_finite_decision_runs": minimum_decision_runs,
            "minimum_tasks": minimum_tasks,
            "maximum_dominant_pair_task_share": maximum_dominant_task_share,
            "remaining_confirmatory_runs": remaining_cohort_runs,
            "remaining_structural_pairs": remaining_pairs,
            "accumulator_status": accumulator_status,
            "accrual_closure_required": True,
            "checks": checks,
            "all_pass": gate_pass,
            "vault_open_allowed": gate_pass,
        },
        "asset_quality": {
            "scope": "provisional_first960_prefix",
            "decision_support": {
                "runs_with_finite_decision": len(decision_run_ids),
                "run_pair_coverage": run_pair_coverage,
                "tasks_with_finite_decision": len(pair_task_counts),
                "task_pair_coverage": task_pair_coverage,
                "decision_parent_groups": len(decision_parent_groups),
                "median_pairs_per_decision_run": statistics.median(pair_run_counts.values())
                if pair_run_counts
                else None,
                "minimum_pairs_per_supported_task": min(pair_task_counts.values(), default=0),
                "maximum_pairs_per_supported_task": max(pair_task_counts.values(), default=0),
            },
            "code_redundancy": {
                "exact_code_unique_fraction": code_unique_fraction,
                "duplicate_code_groups": len(duplicate_code_shas),
                "duplicate_endpoints_beyond_first": sum(
                    count - 1 for count in code_counts.values()
                ),
                "cross_run_duplicate_code_groups": cross_run_duplicate_groups,
                "cross_task_duplicate_code_groups": cross_task_duplicate_groups,
            },
            "task_balance": {
                "dominant_pair_task_count": dominant_pair_count,
                "dominant_pair_task_share": dominant_share,
                "pair_task_hhi": pair_task_hhi,
                "effective_pair_tasks": effective_pair_tasks,
                "normalized_pair_task_entropy": normalized_pair_task_entropy,
            },
            "temporal_support": {
                "collection_days": len(per_day_support),
                "per_day": per_day_support,
            },
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
    parser.add_argument("--minimum-cohort-runs", required=True, type=int)
    parser.add_argument("--source-commit", required=True)
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
        or args.minimum_cohort_runs <= 0
        or not 0 < args.maximum_dominant_task_share <= 1
    ):
        raise VerificationError("gate thresholds are invalid")
    frozen_thresholds = (
        FROZEN_MINIMUM_PAIRS,
        FROZEN_MINIMUM_DECISION_RUNS,
        FROZEN_MINIMUM_TASKS,
        FROZEN_MAXIMUM_DOMINANT_TASK_SHARE,
        FROZEN_CONFIRMATORY_RUNS,
    )
    supplied_thresholds = (
        args.minimum_pairs,
        args.minimum_decision_runs,
        args.minimum_tasks,
        args.maximum_dominant_task_share,
        args.minimum_cohort_runs,
    )
    if supplied_thresholds != frozen_thresholds:
        raise VerificationError("CLI thresholds differ from the frozen confirmatory protocol")
    repo_root = Path(__file__).resolve().parent.parent
    actual_commit = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()
    tracked_status = subprocess.check_output(
        ["git", "-C", str(repo_root), "status", "--porcelain", "--untracked-files=no"],
        text=True,
    ).strip()
    if actual_commit != args.source_commit or tracked_status:
        raise VerificationError("source commit binding or tracked worktree cleanliness failed")
    receipt = verify(
        args.state_root,
        args.snapshot_root,
        args.minimum_pairs,
        args.minimum_decision_runs,
        args.minimum_tasks,
        args.maximum_dominant_task_share,
        args.minimum_cohort_runs,
        args.source_commit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "PROSPECTIVE_STRUCTURAL_GATE_INDEPENDENT_VERIFICATION_COMPLETE",
        f"status={receipt['status']}",
        f"cohort_runs={receipt['independent_inventory']['provisional_first960']['runs']}",
        f"pairs={receipt['independent_inventory']['provisional_first960']['structural_pairs']}",
        f"decision_runs={receipt['independent_inventory']['provisional_first960']['finite_decision_runs']}",
        f"tasks={receipt['independent_inventory']['provisional_first960']['tasks']}",
        f"remaining_runs={receipt['gate']['remaining_confirmatory_runs']}",
        f"remaining_pairs={receipt['gate']['remaining_structural_pairs']}",
        "outcomes_read=false",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
