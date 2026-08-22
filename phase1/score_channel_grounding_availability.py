#!/usr/bin/env python3
"""Post-result-frozen score-channel availability and regret decomposition.

This is a secondary analysis.  It does not alter or replace the frozen primary
score-channel headline or GO/KILL rule.  The producer reuses the frozen primary
input contracts, then reports only availability indicators and parent-level
regret components; raw replay scores and raw labels are never written.  The
primary aggregate KILL result was known before this protocol was frozen, so the
output is descriptive and cannot support a confirmatory or method claim.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
import math
import os
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
from typing import Any, Iterable, Mapping, Sequence
import zlib

from phase1 import score_channel_prospective_analysis as frozen


PROTOCOL = "score-channel-grounding-availability-v1"
PROTOCOL_SPEC = "score-channel-grounding-availability-protocol-v1"
BOOTSTRAPS = 10_000
SEED = 20260813
CAP_SECONDS = 120
TOLERANCE = 1e-12
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


class AvailabilityError(RuntimeError):
    """Raised when a frozen secondary-analysis condition fails closed."""


def finite(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def mean(values: Iterable[float]) -> float:
    collected = list(values)
    if not collected:
        raise AvailabilityError("cannot average an empty collection")
    return sum(collected) / len(collected)


def nonnegative(value: float, label: str) -> float:
    if value < -TOLERANCE:
        raise AvailabilityError(f"negative {label}: {value}")
    return max(0.0, value)


def expected_truth_at_signal_max(
    signal: Mapping[str, float], truth: Mapping[str, float]
) -> float:
    if not signal or not set(signal) <= set(truth):
        raise AvailabilityError("signal/truth support mismatch")
    maximum = max(signal.values())
    chosen = [
        card
        for card, value in signal.items()
        if math.isclose(value, maximum, rel_tol=0.0, abs_tol=TOLERANCE)
    ]
    return mean(float(truth[card]) for card in chosen)


def channel_decomposition(
    cards: Sequence[str],
    available: Sequence[str],
    signal: Mapping[str, float],
    truth: Mapping[str, float],
) -> dict[str, float]:
    if not cards or set(cards) != set(truth) or set(available) != set(signal):
        raise AvailabilityError("channel decomposition support mismatch")
    full_oracle = max(float(truth[card]) for card in cards)
    if available:
        restricted_oracle = max(float(truth[card]) for card in available)
        policy_truth = expected_truth_at_signal_max(signal, truth)
    else:
        restricted_oracle = mean(float(truth[card]) for card in cards)
        policy_truth = restricted_oracle
    availability = nonnegative(
        full_oracle - restricted_oracle, "availability regret"
    )
    ranking = nonnegative(restricted_oracle - policy_truth, "ranking regret")
    total = nonnegative(full_oracle - policy_truth, "total regret")
    if not math.isclose(total, availability + ranking, rel_tol=0.0, abs_tol=TOLERANCE):
        raise AvailabilityError("regret decomposition identity failed")
    return {
        "availability_regret": availability,
        "ranking_regret": ranking,
        "total_regret": total,
    }


def hybrid_decomposition(
    cards: Sequence[str],
    external_cards: Sequence[str],
    stdout_cards: Sequence[str],
    external_signal: Mapping[str, float],
    stdout_signal: Mapping[str, float],
    truth: Mapping[str, float],
) -> dict[str, float]:
    available_union = sorted(set(external_cards) | set(stdout_cards))
    if external_cards:
        policy_truth = expected_truth_at_signal_max(external_signal, truth)
    elif stdout_cards:
        policy_truth = expected_truth_at_signal_max(stdout_signal, truth)
    else:
        policy_truth = mean(float(truth[card]) for card in cards)
    full_oracle = max(float(truth[card]) for card in cards)
    restricted_oracle = (
        max(float(truth[card]) for card in available_union)
        if available_union
        else policy_truth
    )
    availability = nonnegative(
        full_oracle - restricted_oracle, "hybrid availability regret"
    )
    ranking = nonnegative(
        restricted_oracle - policy_truth, "hybrid ranking regret"
    )
    total = nonnegative(full_oracle - policy_truth, "hybrid total regret")
    if not math.isclose(total, availability + ranking, rel_tol=0.0, abs_tol=TOLERANCE):
        raise AvailabilityError("hybrid regret decomposition identity failed")
    return {
        "availability_regret": availability,
        "ranking_regret": ranking,
        "total_regret": total,
    }


def candidate_and_parent_rows(
    selected: Sequence[dict[str, Any]],
    labels: Mapping[str, Any],
    results: Mapping[str, dict[str, Any]],
    orientation: Mapping[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_rows: list[dict[str, Any]] = []
    parent_rows: list[dict[str, Any]] = []
    for parent in selected:
        task = parent["task"]
        cards = list(parent["candidate_card_ids"])
        direction = orientation[task]
        truth = {
            card: float(
                labels[card]["y_norm"] if isinstance(labels[card], dict) else labels[card]
            )
            for card in cards
        }
        external_cards: list[str] = []
        stdout_cards: list[str] = []
        external_signal: dict[str, float] = {}
        stdout_signal: dict[str, float] = {}
        states: Counter[str] = Counter()
        for card in cards:
            result = results[card]
            external = result.get("sub_exists") is True and finite(result.get("sub_score"))
            stdout = result.get("val_how") == "keyed" and finite(result.get("stdout_val"))
            if external:
                external_cards.append(card)
                external_signal[card] = direction * float(result["sub_score"])
            if stdout:
                stdout_cards.append(card)
                stdout_signal[card] = direction * float(result["stdout_val"])
            if external and stdout:
                state = "both"
            elif external:
                state = "external_only"
            elif stdout:
                state = "stdout_only"
            else:
                state = "neither"
            states[state] += 1
            candidate_rows.append(
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

        external = channel_decomposition(
            cards, external_cards, external_signal, truth
        )
        stdout = channel_decomposition(cards, stdout_cards, stdout_signal, truth)
        hybrid = hybrid_decomposition(
            cards,
            external_cards,
            stdout_cards,
            external_signal,
            stdout_signal,
            truth,
        )
        uniform_total = nonnegative(
            max(truth.values()) - mean(truth.values()), "uniform total regret"
        )
        parent_rows.append(
            {
                "task": task,
                "run_id": parent["run_id"],
                "parent_id": parent["parent_id"],
                "selection_rank_in_run": int(parent["selection_rank_in_run"]),
                "candidate_count": len(cards),
                "external_available_count": len(external_cards),
                "stdout_available_count": len(stdout_cards),
                "both_count": states["both"],
                "external_only_count": states["external_only"],
                "stdout_only_count": states["stdout_only"],
                "neither_count": states["neither"],
                "external_comparative": int(len(external_cards) >= 2),
                "stdout_comparative": int(len(stdout_cards) >= 2),
                "both_comparative": int(states["both"] >= 2),
                "uniform_total_regret": uniform_total,
                "external_availability_regret": external["availability_regret"],
                "external_ranking_regret": external["ranking_regret"],
                "external_total_regret": external["total_regret"],
                "stdout_availability_regret": stdout["availability_regret"],
                "stdout_ranking_regret": stdout["ranking_regret"],
                "stdout_total_regret": stdout["total_regret"],
                "hybrid_availability_regret": hybrid["availability_regret"],
                "hybrid_ranking_regret": hybrid["ranking_regret"],
                "hybrid_total_regret": hybrid["total_regret"],
                "external_advantage_over_stdout": (
                    stdout["total_regret"] - external["total_regret"]
                ),
                "hybrid_advantage_over_stdout": (
                    stdout["total_regret"] - hybrid["total_regret"]
                ),
            }
        )
    return candidate_rows, parent_rows


def clustered_ci(
    rows: Sequence[dict[str, Any]],
    cluster_key: str,
    value_key: str,
    draws: int,
    seed: int,
) -> list[float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[str(row[cluster_key])].append(float(row[value_key]))
    keys = sorted(grouped)
    if not keys or draws <= 0:
        raise AvailabilityError("invalid clustered bootstrap support")
    offset = zlib.crc32(f"{cluster_key}:{value_key}".encode("utf-8"))
    rng = random.Random(seed + offset)
    estimates: list[float] = []
    for _ in range(draws):
        sampled = [rng.choice(keys) for _ in keys]
        estimates.append(mean(value for key in sampled for value in grouped[key]))
    estimates.sort()
    return [estimates[int(0.025 * draws)], estimates[int(0.975 * draws)]]


def summarize(
    candidate_rows: Sequence[dict[str, Any]],
    parent_rows: Sequence[dict[str, Any]],
    draws: int,
    seed: int,
) -> dict[str, Any]:
    if not candidate_rows or not parent_rows:
        raise AvailabilityError("availability analysis has empty support")
    states = Counter(row["joint_state"] for row in candidate_rows)
    candidate_total = len(candidate_rows)
    parent_total = len(parent_rows)
    decomposition = {}
    for channel in ("external", "stdout", "hybrid"):
        decomposition[channel] = {
            component: mean(
                float(row[f"{channel}_{component}_regret"]) for row in parent_rows
            )
            for component in ("availability", "ranking", "total")
        }
        if not math.isclose(
            decomposition[channel]["total"],
            decomposition[channel]["availability"]
            + decomposition[channel]["ranking"],
            rel_tol=0.0,
            abs_tol=TOLERANCE,
        ):
            raise AvailabilityError("mean regret decomposition identity failed")

    contrasts = {}
    for name, field in (
        ("external_advantage_over_stdout", "external_advantage_over_stdout"),
        ("hybrid_advantage_over_stdout", "hybrid_advantage_over_stdout"),
    ):
        contrasts[name] = {
            "mean": mean(float(row[field]) for row in parent_rows),
            "run_clustered_ci95": clustered_ci(
                parent_rows, "run_id", field, draws, seed
            ),
            "task_clustered_ci95": clustered_ci(
                parent_rows, "task", field, draws, seed
            ),
        }

    tasks = sorted({str(row["task"]) for row in parent_rows})
    per_task = {
        task: {
            "parents": sum(row["task"] == task for row in parent_rows),
            "candidates": sum(row["task"] == task for row in candidate_rows),
            "external_advantage_over_stdout": mean(
                float(row["external_advantage_over_stdout"])
                for row in parent_rows
                if row["task"] == task
            ),
            "hybrid_advantage_over_stdout": mean(
                float(row["hybrid_advantage_over_stdout"])
                for row in parent_rows
                if row["task"] == task
            ),
        }
        for task in tasks
    }
    return {
        "status": "GROUNDING_AVAILABILITY_SECONDARY_COMPLETE",
        "method_positive_claim_allowed": False,
        "counts": {
            "parents": parent_total,
            "candidates": candidate_total,
            "runs": len({row["run_id"] for row in parent_rows}),
            "tasks": len(tasks),
            "joint_state_counts": {
                key: states[key]
                for key in ("both", "external_only", "stdout_only", "neither")
            },
            "joint_state_shares": {
                key: states[key] / candidate_total
                for key in ("both", "external_only", "stdout_only", "neither")
            },
            "parents_with_any_external": sum(
                int(row["external_available_count"] > 0) for row in parent_rows
            ),
            "parents_with_any_stdout": sum(
                int(row["stdout_available_count"] > 0) for row in parent_rows
            ),
            "parents_external_comparative": sum(
                row["external_comparative"] for row in parent_rows
            ),
            "parents_stdout_comparative": sum(
                row["stdout_comparative"] for row in parent_rows
            ),
            "parents_both_comparative": sum(
                row["both_comparative"] for row in parent_rows
            ),
        },
        "mean_regret_decomposition": decomposition,
        "paired_contrasts": contrasts,
        "uniform_mean_total_regret": mean(
            float(row["uniform_total_regret"]) for row in parent_rows
        ),
        "per_task": per_task,
    }


def load_protocol(path: Path, expected_sha256: str) -> dict[str, Any]:
    if frozen.sha256_file(path) != frozen.valid_sha(
        expected_sha256, "availability protocol SHA"
    ):
        raise AvailabilityError("availability protocol SHA mismatch")
    value = frozen.read_object(path, "availability protocol")
    cohort = value.get("locked_cohort") or {}
    inference = value.get("inference") or {}
    relation = value.get("relation_to_primary") or {}
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
        or cohort.get("cap_seconds") != CAP_SECONDS
        or cohort.get("selected_parents") != 158
        or cohort.get("selected_candidates") != 320
        or inference.get("bootstrap_draws") != BOOTSTRAPS
        or inference.get("seed") != SEED
        or inference.get("hypothesis_gate") is not None
        or (value.get("scope") or {}).get("primary_results_were_already_hash_bound") is not True
        or (value.get("scope") or {}).get("detailed_secondary_results_may_be_computed_only_after_protocol_commit") is not True
    ):
        raise AvailabilityError("availability protocol contract mismatch")
    return value


def repository_head(root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    value = completed.stdout.strip()
    if completed.returncode or len(value) != 40:
        raise AvailabilityError("cannot resolve source commit")
    return value


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def produce(args: argparse.Namespace) -> dict[str, Any]:
    if args.out_dir.exists():
        raise FileExistsError(f"refusing to overwrite output: {args.out_dir}")
    protocol = load_protocol(args.protocol, args.expect_protocol_sha256)
    cohort = protocol["locked_cohort"]

    selected, selection_summary = frozen.load_selection(args.selection_dir)
    replay, replay_summary = frozen.load_replay(args.replay_dir, args.selection_dir)
    if (
        frozen.sha256_file(args.selection_dir / "summary.json")
        != cohort["selection_summary_sha256"]
        or frozen.sha256_file(args.selection_dir / "selected_parents.jsonl")
        != cohort["selected_parents_sha256"]
        or frozen.sha256_file(args.replay_dir / "summary.json")
        != cohort["replay_summary_sha256"]
        or frozen.sha256_file(args.replay_dir / "replay_manifest.jsonl")
        != cohort["replay_manifest_sha256"]
    ):
        raise AvailabilityError("locked cohort artifact mismatch")
    if len(selected) != cohort["selected_parents"] or len(replay) != cohort["selected_candidates"]:
        raise AvailabilityError("locked cohort count mismatch")

    manifests = {row["card_id"]: row for row in replay}
    selected_cards = {
        card for parent in selected for card in parent["candidate_card_ids"]
    }
    if selected_cards != set(manifests):
        raise AvailabilityError("selection/replay candidate mismatch")
    approval, approval_sha = frozen.load_approval(
        args.approval,
        args.expect_approval_sha256,
        args.replay_dir,
        replay_summary,
    )
    if approval["worker_source_commit"] != cohort["frozen_worker_source_commit"]:
        raise AvailabilityError("approval worker differs from frozen cohort")
    orientation, orientation_sha = frozen.load_orientation(
        args.orientation,
        cohort["orientation_sha256"],
        {row["task"] for row in selected},
    )
    labels = frozen.load_labels(args.intake_root, selected, selection_summary)
    results, result_shas = frozen.load_results(
        args.result,
        args.expect_result_sha256,
        manifests,
        replay_summary,
        approval_sha,
        cohort["frozen_worker_source_commit"],
    )
    candidate_rows, parent_rows = candidate_and_parent_rows(
        selected, labels, results, orientation
    )
    decision = summarize(candidate_rows, parent_rows, args.bootstraps, args.seed)
    summary = {
        "protocol": PROTOCOL,
        **decision,
        "design": {
            "analysis_timing": "post_hoc_after_primary_aggregate_known",
            "known_aggregate_before_freeze": protocol[
                "known_aggregate_before_freeze"
            ],
            "cap_seconds": CAP_SECONDS,
            "availability_states": [
                "both",
                "external_only",
                "stdout_only",
                "neither",
            ],
            "external_policy": "external_then_uniform",
            "stdout_policy": "stdout_then_uniform",
            "hybrid_policy": "external_then_stdout_then_uniform",
            "primary_cluster": "physical run",
            "secondary_cluster": "task",
            "bootstrap_draws": args.bootstraps,
            "seed": args.seed,
            "primary_score_channel_gate_unchanged": True,
            "raw_scores_or_labels_written": False,
        },
        "inputs": {
            "protocol_sha256": frozen.sha256_file(args.protocol),
            "selection_summary_sha256": frozen.sha256_file(
                args.selection_dir / "summary.json"
            ),
            "selected_parents_sha256": frozen.sha256_file(
                args.selection_dir / "selected_parents.jsonl"
            ),
            "replay_summary_sha256": frozen.sha256_file(
                args.replay_dir / "summary.json"
            ),
            "replay_manifest_sha256": frozen.sha256_file(
                args.replay_dir / "replay_manifest.jsonl"
            ),
            "approval_sha256": approval_sha,
            "orientation_sha256": orientation_sha,
            "result_sha256_by_shard": result_shas,
        },
        "scope": {
            "secondary_descriptive_only": True,
            "method_claim_allowed": False,
            "task_subset_selection": False,
            "cap_swept": False,
            "base_llm_updated": False,
            "llm_api_calls": 0,
        },
        "implementation": {
            "source_commit": repository_head(Path(__file__).resolve().parents[1]),
            "script_sha256": frozen.sha256_file(Path(__file__)),
        },
    }

    args.out_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{args.out_dir.name}.tmp.", dir=args.out_dir.parent)
    )
    try:
        write_csv(temporary / "candidate_availability.csv", CANDIDATE_FIELDS, candidate_rows)
        write_csv(temporary / "per_parent.csv", PARENT_FIELDS, parent_rows)
        (temporary / "summary.json").write_text(
            json.dumps(
                summary,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, args.out_dir)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return summary


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
    parser.add_argument("--result", type=Path, action="append", required=True)
    parser.add_argument("--expect-result-sha256", action="append", required=True)
    parser.add_argument("--bootstraps", type=int, default=BOOTSTRAPS)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if args.bootstraps != BOOTSTRAPS or args.seed != SEED:
        print(
            "GROUNDING_AVAILABILITY_ERROR: frozen bootstrap/seed mismatch",
            file=os.sys.stderr,
        )
        return 2
    try:
        summary = produce(args)
    except (AvailabilityError, frozen.AnalysisError, FileExistsError, OSError) as error:
        print(f"GROUNDING_AVAILABILITY_ERROR: {error}", file=os.sys.stderr)
        return 2
    print(
        frozen.canonical(
            {
                "status": summary["status"],
                "method_positive_claim_allowed": summary[
                    "method_positive_claim_allowed"
                ],
                "counts": summary["counts"],
                "paired_contrasts": summary["paired_contrasts"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
