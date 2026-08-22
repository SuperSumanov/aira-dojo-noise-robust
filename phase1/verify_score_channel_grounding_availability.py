#!/usr/bin/env python3
"""Independent verifier for the frozen grounding-availability analysis.

This module intentionally does not import the grounding-availability producer.
It reuses only the already independent frozen-input readers, then reconstructs
the joint channel states, parent-level regret decomposition, and clustered
uncertainty with a separate implementation.
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import os
from pathlib import Path
import random
from typing import Any, Iterable
import zlib

from phase1 import verify_score_channel_prospective_analysis as base


PROTOCOL = "score-channel-grounding-availability-v1"
PROTOCOL_SPEC = "score-channel-grounding-availability-protocol-v1"
STATUS = "GROUNDING_AVAILABILITY_SECONDARY_COMPLETE"
BOOTSTRAPS = 10_000
SEED = 20260813
TOLERANCE = 1e-12
STATES = ("both", "external_only", "stdout_only", "neither")
KNOWN_AGGREGATE = {
    "source": "phase1/results/score_channel_replay_execution_20260818/README.md",
    "primary_status": "SCORE_CHANNEL_MECHANISM_KILL",
    "planned_and_completed_replays": 320,
    "finite_external_cards": 15,
    "keyed_stdout_cards": 92,
    "both_channels_cards": 7,
    "common_cards": 6,
    "common_parents": 3,
    "external_top1": 1.0,
    "stdout_top1": 1.0,
    "delta": 0.0,
}

CANDIDATE_FIELDS = [
    "task",
    "run_id",
    "parent_id",
    "card_id",
    "external_available",
    "stdout_available",
    "joint_state",
]
PARENT_FIELDS = [
    "task",
    "run_id",
    "parent_id",
    "selection_rank_in_run",
    "candidate_count",
    "external_available_count",
    "stdout_available_count",
    "both_count",
    "external_only_count",
    "stdout_only_count",
    "neither_count",
    "external_comparative",
    "stdout_comparative",
    "both_comparative",
    "uniform_total_regret",
    "external_availability_regret",
    "external_ranking_regret",
    "external_total_regret",
    "stdout_availability_regret",
    "stdout_ranking_regret",
    "stdout_total_regret",
    "hybrid_availability_regret",
    "hybrid_ranking_regret",
    "hybrid_total_regret",
    "external_advantage_over_stdout",
    "hybrid_advantage_over_stdout",
]
PARENT_INTEGER_FIELDS = {
    "selection_rank_in_run",
    "candidate_count",
    "external_available_count",
    "stdout_available_count",
    "both_count",
    "external_only_count",
    "stdout_only_count",
    "neither_count",
    "external_comparative",
    "stdout_comparative",
    "both_comparative",
}


class GroundingVerifyError(RuntimeError):
    """Raised when an independent reconstruction or binding check fails."""


def finite(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def average(values: Iterable[float]) -> float:
    items = list(values)
    if not items:
        raise GroundingVerifyError("cannot average empty values")
    return sum(items) / len(items)


def clamp_regret(value: float, label: str) -> float:
    if value < -TOLERANCE:
        raise GroundingVerifyError(f"negative {label}: {value}")
    return max(0.0, value)


def selected_truth(signal: dict[str, float], truth: dict[str, float]) -> float:
    if not signal or not set(signal) <= set(truth):
        raise GroundingVerifyError("invalid signal support")
    signal_max = max(signal.values())
    maxima = [
        card
        for card, value in signal.items()
        if abs(value - signal_max) <= TOLERANCE
    ]
    return average(float(truth[card]) for card in maxima)


def independent_decomposition(
    cards: list[str],
    available: list[str],
    signal: dict[str, float],
    truth: dict[str, float],
) -> dict[str, float]:
    if not cards or set(cards) != set(truth) or set(available) != set(signal):
        raise GroundingVerifyError("decomposition support differs")
    full_best = max(float(truth[card]) for card in cards)
    if available:
        restricted_best = max(float(truth[card]) for card in available)
        policy_truth = selected_truth(signal, truth)
    else:
        restricted_best = average(float(truth[card]) for card in cards)
        policy_truth = restricted_best
    availability = clamp_regret(
        full_best - restricted_best, "availability regret"
    )
    ranking = clamp_regret(restricted_best - policy_truth, "ranking regret")
    total = clamp_regret(full_best - policy_truth, "total regret")
    if abs(total - availability - ranking) > TOLERANCE:
        raise GroundingVerifyError("decomposition identity differs")
    return {"availability": availability, "ranking": ranking, "total": total}


def independent_hybrid(
    cards: list[str],
    external_cards: list[str],
    stdout_cards: list[str],
    external_signal: dict[str, float],
    stdout_signal: dict[str, float],
    truth: dict[str, float],
) -> dict[str, float]:
    union = set(external_cards) | set(stdout_cards)
    full_best = max(float(truth[card]) for card in cards)
    if external_cards:
        policy_truth = selected_truth(external_signal, truth)
    elif stdout_cards:
        policy_truth = selected_truth(stdout_signal, truth)
    else:
        policy_truth = average(float(truth[card]) for card in cards)
    restricted_best = (
        max(float(truth[card]) for card in union) if union else policy_truth
    )
    availability = clamp_regret(
        full_best - restricted_best, "hybrid availability regret"
    )
    ranking = clamp_regret(
        restricted_best - policy_truth, "hybrid ranking regret"
    )
    total = clamp_regret(full_best - policy_truth, "hybrid total regret")
    if abs(total - availability - ranking) > TOLERANCE:
        raise GroundingVerifyError("hybrid decomposition identity differs")
    return {"availability": availability, "ranking": ranking, "total": total}


def reconstruct_rows(
    selected: list[dict[str, Any]],
    labels: dict[str, float],
    results: dict[str, dict[str, Any]],
    orientation: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    parents: list[dict[str, Any]] = []
    for parent in selected:
        task = str(parent["task"])
        cards = list(parent["candidate_card_ids"])
        truth = {card: float(labels[card]) for card in cards}
        direction = orientation[task]
        external_cards: list[str] = []
        stdout_cards: list[str] = []
        external_signal: dict[str, float] = {}
        stdout_signal: dict[str, float] = {}
        state_counts: collections.Counter[str] = collections.Counter()
        for card in cards:
            row = results[card]
            external = row.get("sub_exists") is True and finite(row.get("sub_score"))
            stdout = row.get("val_how") == "keyed" and finite(row.get("stdout_val"))
            if external:
                external_cards.append(card)
                external_signal[card] = direction * float(row["sub_score"])
            if stdout:
                stdout_cards.append(card)
                stdout_signal[card] = direction * float(row["stdout_val"])
            state = (
                "both"
                if external and stdout
                else "external_only"
                if external
                else "stdout_only"
                if stdout
                else "neither"
            )
            state_counts[state] += 1
            candidates.append(
                {
                    "task": task,
                    "run_id": parent["run_id"],
                    "parent_id": parent["parent_id"],
                    "card_id": card,
                    "external_available": int(external),
                    "stdout_available": int(stdout),
                    "joint_state": state,
                }
            )
        external_result = independent_decomposition(
            cards, external_cards, external_signal, truth
        )
        stdout_result = independent_decomposition(
            cards, stdout_cards, stdout_signal, truth
        )
        hybrid_result = independent_hybrid(
            cards,
            external_cards,
            stdout_cards,
            external_signal,
            stdout_signal,
            truth,
        )
        uniform_regret = clamp_regret(
            max(truth.values()) - average(truth.values()), "uniform total regret"
        )
        parents.append(
            {
                "task": task,
                "run_id": parent["run_id"],
                "parent_id": parent["parent_id"],
                "selection_rank_in_run": int(parent["selection_rank_in_run"]),
                "candidate_count": len(cards),
                "external_available_count": len(external_cards),
                "stdout_available_count": len(stdout_cards),
                "both_count": state_counts["both"],
                "external_only_count": state_counts["external_only"],
                "stdout_only_count": state_counts["stdout_only"],
                "neither_count": state_counts["neither"],
                "external_comparative": int(len(external_cards) >= 2),
                "stdout_comparative": int(len(stdout_cards) >= 2),
                "both_comparative": int(state_counts["both"] >= 2),
                "uniform_total_regret": uniform_regret,
                "external_availability_regret": external_result["availability"],
                "external_ranking_regret": external_result["ranking"],
                "external_total_regret": external_result["total"],
                "stdout_availability_regret": stdout_result["availability"],
                "stdout_ranking_regret": stdout_result["ranking"],
                "stdout_total_regret": stdout_result["total"],
                "hybrid_availability_regret": hybrid_result["availability"],
                "hybrid_ranking_regret": hybrid_result["ranking"],
                "hybrid_total_regret": hybrid_result["total"],
                "external_advantage_over_stdout": (
                    stdout_result["total"] - external_result["total"]
                ),
                "hybrid_advantage_over_stdout": (
                    stdout_result["total"] - hybrid_result["total"]
                ),
            }
        )
    return candidates, parents


def clustered_interval(
    rows: list[dict[str, Any]], cluster: str, field: str
) -> list[float]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row in rows:
        grouped[str(row[cluster])].append(float(row[field]))
    keys = sorted(grouped)
    if not keys:
        raise GroundingVerifyError("empty clustered interval")
    generator = random.Random(SEED + zlib.crc32(f"{cluster}:{field}".encode()))
    estimates = []
    for _ in range(BOOTSTRAPS):
        sampled = [generator.choice(keys) for _ in keys]
        estimates.append(
            average(value for key in sampled for value in grouped[key])
        )
    estimates.sort()
    return [
        estimates[int(0.025 * BOOTSTRAPS)],
        estimates[int(0.975 * BOOTSTRAPS)],
    ]


def reconstruct_summary(
    candidates: list[dict[str, Any]], parents: list[dict[str, Any]]
) -> dict[str, Any]:
    if not candidates or not parents:
        raise GroundingVerifyError("empty reconstructed support")
    state_counts = collections.Counter(row["joint_state"] for row in candidates)
    decomposition: dict[str, dict[str, float]] = {}
    for channel in ("external", "stdout", "hybrid"):
        decomposition[channel] = {
            component: average(
                float(row[f"{channel}_{component}_regret"]) for row in parents
            )
            for component in ("availability", "ranking", "total")
        }
        if abs(
            decomposition[channel]["total"]
            - decomposition[channel]["availability"]
            - decomposition[channel]["ranking"]
        ) > TOLERANCE:
            raise GroundingVerifyError("mean decomposition identity differs")
    contrasts: dict[str, dict[str, Any]] = {}
    for field in (
        "external_advantage_over_stdout",
        "hybrid_advantage_over_stdout",
    ):
        contrasts[field] = {
            "mean": average(float(row[field]) for row in parents),
            "run_clustered_ci95": clustered_interval(parents, "run_id", field),
            "task_clustered_ci95": clustered_interval(parents, "task", field),
        }
    tasks = sorted({str(row["task"]) for row in parents})
    per_task = {}
    for task in tasks:
        task_parents = [row for row in parents if row["task"] == task]
        per_task[task] = {
            "parents": len(task_parents),
            "candidates": sum(row["task"] == task for row in candidates),
            "external_advantage_over_stdout": average(
                float(row["external_advantage_over_stdout"])
                for row in task_parents
            ),
            "hybrid_advantage_over_stdout": average(
                float(row["hybrid_advantage_over_stdout"])
                for row in task_parents
            ),
        }
    return {
        "status": STATUS,
        "method_positive_claim_allowed": False,
        "counts": {
            "parents": len(parents),
            "candidates": len(candidates),
            "runs": len({row["run_id"] for row in parents}),
            "tasks": len(tasks),
            "joint_state_counts": {state: state_counts[state] for state in STATES},
            "joint_state_shares": {
                state: state_counts[state] / len(candidates) for state in STATES
            },
            "parents_with_any_external": sum(
                row["external_available_count"] > 0 for row in parents
            ),
            "parents_with_any_stdout": sum(
                row["stdout_available_count"] > 0 for row in parents
            ),
            "parents_external_comparative": sum(
                row["external_comparative"] for row in parents
            ),
            "parents_stdout_comparative": sum(
                row["stdout_comparative"] for row in parents
            ),
            "parents_both_comparative": sum(
                row["both_comparative"] for row in parents
            ),
        },
        "mean_regret_decomposition": decomposition,
        "paired_contrasts": contrasts,
        "uniform_mean_total_regret": average(
            float(row["uniform_total_regret"]) for row in parents
        ),
        "per_task": per_task,
    }


def read_csv(path: Path, fields: list[str], integer_fields: set[str]) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != fields:
            raise GroundingVerifyError(f"unexpected CSV schema: {path.name}")
        raw_rows = list(reader)
    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        converted: dict[str, Any] = {}
        for key in fields:
            value = raw[key]
            if key in integer_fields:
                converted[key] = int(value)
            elif key.endswith("_regret") or key.endswith("_over_stdout"):
                converted[key] = float(value)
            else:
                converted[key] = value
        rows.append(converted)
    return rows


def load_protocol(path: Path, expected_sha: str) -> dict[str, Any]:
    expected = base.valid_sha(expected_sha, "protocol SHA")
    if base.digest(path) != expected:
        raise GroundingVerifyError("protocol SHA mismatch")
    value = base.object_file(path, "grounding protocol")
    cohort = value.get("locked_cohort") or {}
    relation = value.get("relation_to_primary") or {}
    inference = value.get("inference") or {}
    scope = value.get("scope") or {}
    if (
        value.get("protocol") != PROTOCOL_SPEC
        or value.get("status") != "FROZEN_POST_HOC_SECONDARY_NOT_RUN"
        or value.get("outcomes_read_before_freeze") is not True
        or relation.get("primary_gate_changed") is not False
        or relation.get("primary_headline_replaced") is not False
        or relation.get("secondary_method_claim_allowed") is not False
        or relation.get("secondary_confirmatory_claim_allowed") is not False
        or value.get("known_aggregate_before_freeze") != KNOWN_AGGREGATE
        or value.get("raw_result_shards_opened_during_protocol_freeze") is not False
        or value.get("label_vault_opened_during_protocol_freeze") is not False
        or cohort.get("cap_seconds") != 120
        or cohort.get("selected_parents") != 158
        or cohort.get("selected_candidates") != 320
        or inference.get("bootstrap_draws") != BOOTSTRAPS
        or inference.get("seed") != SEED
        or inference.get("hypothesis_gate") is not None
        or scope.get("primary_results_were_already_hash_bound") is not True
        or scope.get("detailed_secondary_results_may_be_computed_only_after_protocol_commit")
        is not True
    ):
        raise GroundingVerifyError("protocol contract mismatch")
    return value


def verify(args: argparse.Namespace) -> dict[str, Any]:
    protocol = load_protocol(args.protocol, args.expect_protocol_sha256)
    cohort = protocol["locked_cohort"]
    summary = base.object_file(args.analysis_dir / "summary.json", "analysis summary")
    if summary.get("protocol") != PROTOCOL:
        raise GroundingVerifyError("wrong analysis protocol")

    selected, selection_summary = base.load_selected(args.selection_dir)
    selected_cards = {
        card for parent in selected for card in parent["candidate_card_ids"]
    }
    if (
        base.digest(args.selection_dir / "summary.json")
        != cohort["selection_summary_sha256"]
        or base.digest(args.selection_dir / "selected_parents.jsonl")
        != cohort["selected_parents_sha256"]
        or len(selected) != cohort["selected_parents"]
        or len(selected_cards) != cohort["selected_candidates"]
    ):
        raise GroundingVerifyError("locked selection differs")
    labels = base.load_labels(args.intake_root, selected, selection_summary)
    manifests, replay_summary = base.load_replay(args.replay_dir, selected_cards)
    if (
        base.digest(args.replay_dir / "summary.json")
        != cohort["replay_summary_sha256"]
        or base.digest(args.replay_dir / "replay_manifest.jsonl")
        != cohort["replay_manifest_sha256"]
    ):
        raise GroundingVerifyError("locked replay differs")

    approval_sha = base.valid_sha(args.expect_approval_sha256, "approval SHA")
    if base.digest(args.approval) != approval_sha:
        raise GroundingVerifyError("approval SHA mismatch")
    approval = base.object_file(args.approval, "approval")
    if (
        approval.get("protocol") != "score-channel-replay-approval-v1"
        or approval.get("approved") is not True
        or approval.get("cap_seconds") != 120
        or approval.get("shards") != 4
        or approval.get("gpus_per_shard") != 1
        or approval.get("base_llm_update") is not False
        or approval.get("llm_api_calls") != 0
        or approval.get("online_hf") is not True
        or approval.get("fresh_workspace_per_candidate") is not True
        or approval.get("replay_manifest_sha256")
        != base.digest(args.replay_dir / "replay_manifest.jsonl")
        or approval.get("replay_summary_sha256")
        != base.digest(args.replay_dir / "summary.json")
    ):
        raise GroundingVerifyError("approval contract mismatch")
    worker = base.valid_sha(
        approval.get("worker_source_commit"), "worker commit", length=40
    )
    if worker != cohort["frozen_worker_source_commit"]:
        raise GroundingVerifyError("worker commit differs from protocol")

    orientation_sha = base.valid_sha(
        args.expect_orientation_sha256, "orientation SHA"
    )
    if (
        base.digest(args.orientation) != orientation_sha
        or orientation_sha != cohort["orientation_sha256"]
    ):
        raise GroundingVerifyError("orientation SHA mismatch")
    orientation_receipt = base.object_file(args.orientation, "orientation")
    orientation = orientation_receipt.get("orientation")
    tasks = {row["task"] for row in selected}
    if (
        orientation_receipt.get("protocol")
        != "score-channel-task-orientation-v1"
        or orientation_receipt.get("outcomes_read") is not False
        or not isinstance(orientation, dict)
        or any(
            isinstance(orientation.get(task), bool)
            or orientation.get(task) not in {-1, 1}
            for task in tasks
        )
    ):
        raise GroundingVerifyError("orientation contract mismatch")
    fixed_orientation = {task: int(orientation[task]) for task in tasks}

    results, result_shas = base.load_results(
        args.result,
        args.expect_result_sha256,
        manifests,
        replay_summary,
        approval_sha,
        worker,
    )
    candidate_rows, parent_rows = reconstruct_rows(
        selected, labels, results, fixed_orientation
    )
    reconstructed = reconstruct_summary(candidate_rows, parent_rows)
    stored_candidates = read_csv(
        args.analysis_dir / "candidate_availability.csv",
        CANDIDATE_FIELDS,
        {"external_available", "stdout_available"},
    )
    stored_parents = read_csv(
        args.analysis_dir / "per_parent.csv", PARENT_FIELDS, PARENT_INTEGER_FIELDS
    )
    if stored_candidates != candidate_rows:
        raise GroundingVerifyError("candidate CSV differs from reconstruction")
    if stored_parents != parent_rows:
        raise GroundingVerifyError("parent CSV differs from reconstruction")
    for key in (
        "status",
        "method_positive_claim_allowed",
        "counts",
        "mean_regret_decomposition",
        "paired_contrasts",
        "uniform_mean_total_regret",
        "per_task",
    ):
        if summary.get(key) != reconstructed[key]:
            raise GroundingVerifyError(f"summary differs for {key}")
    expected_inputs = {
        "protocol_sha256": base.digest(args.protocol),
        "selection_summary_sha256": base.digest(
            args.selection_dir / "summary.json"
        ),
        "selected_parents_sha256": base.digest(
            args.selection_dir / "selected_parents.jsonl"
        ),
        "replay_summary_sha256": base.digest(args.replay_dir / "summary.json"),
        "replay_manifest_sha256": base.digest(
            args.replay_dir / "replay_manifest.jsonl"
        ),
        "approval_sha256": approval_sha,
        "orientation_sha256": orientation_sha,
        "result_sha256_by_shard": result_shas,
    }
    if summary.get("inputs") != expected_inputs:
        raise GroundingVerifyError("analysis input receipt differs")
    design = summary.get("design") or {}
    scope = summary.get("scope") or {}
    if (
        design.get("analysis_timing")
        != "post_hoc_after_primary_aggregate_known"
        or design.get("known_aggregate_before_freeze") != KNOWN_AGGREGATE
        or design.get("bootstrap_draws") != BOOTSTRAPS
        or design.get("seed") != SEED
        or design.get("primary_score_channel_gate_unchanged") is not True
        or design.get("raw_scores_or_labels_written") is not False
        or scope.get("secondary_descriptive_only") is not True
        or scope.get("method_claim_allowed") is not False
        or scope.get("task_subset_selection") is not False
        or scope.get("cap_swept") is not False
        or scope.get("base_llm_updated") is not False
        or scope.get("llm_api_calls") != 0
    ):
        raise GroundingVerifyError("analysis scope differs")
    return {
        "protocol": "score-channel-grounding-availability-independent-verifier-v1",
        "status": "VERIFIED_GROUNDING_AVAILABILITY_SECONDARY",
        "analysis_summary_sha256": base.digest(args.analysis_dir / "summary.json"),
        "candidate_availability_sha256": base.digest(
            args.analysis_dir / "candidate_availability.csv"
        ),
        "per_parent_sha256": base.digest(args.analysis_dir / "per_parent.csv"),
        "decision": reconstructed,
        "inputs": expected_inputs,
        "producer_imported": False,
    }


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--selection-dir", type=Path, required=True)
    parser.add_argument("--replay-dir", type=Path, required=True)
    parser.add_argument("--intake-root", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--expect-approval-sha256", required=True)
    parser.add_argument("--orientation", type=Path, required=True)
    parser.add_argument("--expect-orientation-sha256", required=True)
    parser.add_argument("--result", type=Path, action="append", required=True)
    parser.add_argument(
        "--expect-result-sha256", action="append", required=True
    )
    parser.add_argument("--analysis-dir", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if args.receipt.exists():
        print(
            "GROUNDING_AVAILABILITY_VERIFY_ERROR: refusing to overwrite receipt",
            file=os.sys.stderr,
        )
        return 2
    try:
        value = verify(args)
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except (base.VerifyError, GroundingVerifyError, OSError, ValueError) as error:
        print(f"GROUNDING_AVAILABILITY_VERIFY_ERROR: {error}", file=os.sys.stderr)
        return 2
    print(base.canonical({"status": value["status"], "decision": value["decision"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
