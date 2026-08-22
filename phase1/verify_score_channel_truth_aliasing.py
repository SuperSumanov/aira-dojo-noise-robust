#!/usr/bin/env python3
"""Independent verifier for the post-hoc score-channel truth-aliasing audit."""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
from pathlib import Path
import subprocess
from typing import Any

from phase1 import verify_score_channel_prospective_analysis as base


TOLERANCE = 1e-12


class VerificationError(RuntimeError):
    pass


def repo_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    value = result.stdout.strip()
    if result.returncode or len(value) != 40:
        raise VerificationError("cannot resolve repository head")
    return value


def read_protocol(path: Path, expected_sha: str) -> dict[str, Any]:
    if base.digest(path) != base.valid_sha(expected_sha, "protocol SHA"):
        raise VerificationError("protocol SHA mismatch")
    value = base.object_file(path, "truth aliasing protocol")
    if (
        value.get("protocol") != "score-channel-truth-aliasing-protocol-v1"
        or value.get("status") != "FROZEN_POST_HOC_RAW_GRADE_NOT_READ"
        or (value.get("timing_and_evidence") or {}).get("formal_primary_status_may_change") is not False
    ):
        raise VerificationError("protocol contract mismatch")
    return value


def labels_from_vaults(
    intake_root: Path,
    selected: list[dict[str, Any]],
    selection_summary: dict[str, Any],
) -> dict[str, tuple[float, float]]:
    by_intake: dict[str, set[str]] = collections.defaultdict(set)
    expected_identity: dict[str, tuple[str, str]] = {}
    for parent in selected:
        for card in parent["candidate_card_ids"]:
            by_intake[parent["source_intake"]].add(card)
            expected_identity[card] = (parent["task"], parent["run_id"])
    summary_shas = (selection_summary.get("inputs") or {}).get("intake_summary_sha256")
    if not isinstance(summary_shas, dict):
        raise VerificationError("selection omits intake bindings")

    labels: dict[str, tuple[float, float]] = {}
    for intake, wanted in sorted(by_intake.items()):
        root = intake_root / intake
        summary_file = root / "summary.json"
        if base.digest(summary_file) != base.valid_sha(summary_shas.get(intake), "intake SHA"):
            raise VerificationError("intake summary SHA mismatch")
        intake_summary = base.object_file(summary_file, "intake summary")
        vault = root / "label_vault.jsonl"
        if base.digest(vault) != base.valid_sha(
            (intake_summary.get("outputs") or {}).get("label_vault_sha256"), "vault SHA"
        ):
            raise VerificationError("label vault SHA mismatch")
        for row in base.row_file(vault, "label vault", allow_empty=True):
            card = row.get("card_id")
            if card not in wanted:
                continue
            if (
                set(row) != base.VAULT_KEYS
                or card in labels
                or (row.get("task"), row.get("run_id")) != expected_identity[card]
                or row.get("eligible_by_start_time") is not True
                or not base.finite(row.get("graded"))
                or not base.finite(row.get("y_norm"))
            ):
                raise VerificationError("invalid selected label")
            labels[card] = (float(row["graded"]), float(row["y_norm"]))
    if set(labels) != set(expected_identity):
        raise VerificationError("selected labels incomplete")
    return labels


def is_varied(values: list[float]) -> bool:
    if len(values) < 2 or any(not math.isfinite(value) for value in values):
        raise VerificationError("invalid value set")
    return max(values) - min(values) > TOLERANCE


def boundary(values: list[float]) -> str:
    if is_varied(values):
        raise VerificationError("non-tied boundary request")
    if max(abs(value) for value in values) <= TOLERANCE:
        return "all_zero"
    if max(abs(value - 1.0) for value in values) <= TOLERANCE:
        return "all_one"
    return "interior"


def top1_credit(signal: dict[str, float], truth: dict[str, float]) -> float:
    if set(signal) != set(truth) or len(signal) < 2:
        raise VerificationError("invalid credit support")
    signal_max = max(signal.values())
    selected = {card for card, value in signal.items() if abs(value - signal_max) <= TOLERANCE}
    truth_max = max(truth.values())
    winners = {card for card, value in truth.items() if abs(value - truth_max) <= TOLERANCE}
    return len(selected & winners) / len(selected)


def independent_summary(
    selected: list[dict[str, Any]],
    labels: dict[str, tuple[float, float]],
    results: dict[str, dict[str, Any]],
    orientation: dict[str, int],
    parent_minimum: int,
    task_minimum: int,
) -> dict[str, Any]:
    total = collections.Counter()
    task_counts: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    cards_seen: set[str] = set()
    credits: list[tuple[float, float]] = []
    for parent in selected:
        cards = list(parent["candidate_card_ids"])
        if len(cards) < 2 or cards_seen.intersection(cards):
            raise VerificationError("candidate reuse or invalid parent")
        cards_seen.update(cards)
        task = parent["task"]
        direction = orientation.get(task)
        if direction not in {-1, 1}:
            raise VerificationError("invalid orientation")
        raw = [labels[card][0] for card in cards]
        normalized = [labels[card][1] for card in cards]
        raw_varied = is_varied(raw)
        normalized_varied = is_varied(normalized)
        total["parents"] += 1
        total["raw_nontied"] += int(raw_varied)
        total["raw_tied"] += int(not raw_varied)
        total["normalized_nontied"] += int(normalized_varied)
        total["normalized_tied"] += int(not normalized_varied)
        task_counts[task]["parents"] += 1
        task_counts[task]["raw_nontied"] += int(raw_varied)
        task_counts[task]["normalized_nontied"] += int(normalized_varied)
        if not normalized_varied:
            label = boundary(normalized)
            total[f"boundary_{label}"] += 1
            task_counts[task][f"normalized_tied_{label}"] += 1
        if raw_varied and not normalized_varied:
            total["alias"] += 1
            task_counts[task]["alias_parents"] += 1
        if normalized_varied and not raw_varied:
            total["impossible"] += 1
            task_counts[task]["impossible_direction_parents"] += 1

        common = [
            card
            for card in cards
            if results[card].get("sub_exists") is True
            and base.finite(results[card].get("sub_score"))
            and results[card].get("val_how") == "keyed"
            and base.finite(results[card].get("stdout_val"))
        ]
        if len(common) >= 2:
            total["common"] += 1
            task_counts[task]["common_comparative_parents"] += 1
            raw_common = [labels[card][0] for card in common]
            norm_common = [labels[card][1] for card in common]
            raw_common_varied = is_varied(raw_common)
            norm_common_varied = is_varied(norm_common)
            total["common_raw_nontied"] += int(raw_common_varied)
            total["common_norm_nontied"] += int(norm_common_varied)
            task_counts[task]["common_raw_nontied_parents"] += int(raw_common_varied)
            task_counts[task]["common_normalized_nontied_parents"] += int(norm_common_varied)
            if raw_common_varied:
                truth = {card: direction * labels[card][0] for card in common}
                external = {card: direction * float(results[card]["sub_score"]) for card in common}
                stdout = {card: direction * float(results[card]["stdout_val"]) for card in common}
                credits.append((top1_credit(external, truth), top1_credit(stdout, truth)))

    if total["impossible"]:
        raise VerificationError("impossible normalization direction observed")
    alias_tasks = sum(row["alias_parents"] > 0 for row in task_counts.values())
    gate = total["alias"] >= parent_minimum and alias_tasks >= task_minimum
    if credits:
        ext = sum(row[0] for row in credits) / len(credits)
        stdout = sum(row[1] for row in credits) / len(credits)
        credit = {
            "parents": len(credits),
            "external_top1_credit": ext,
            "stdout_top1_credit": stdout,
            "delta": ext - stdout,
        }
    else:
        credit = {
            "parents": 0,
            "external_top1_credit": None,
            "stdout_top1_credit": None,
            "delta": None,
        }
    off_grid = sum(abs(raw - round(raw, 5)) > TOLERANCE for raw, _ in labels.values())
    return {
        "counts": {
            "selected_parents": total["parents"],
            "selected_candidates": len(cards_seen),
            "tasks": len(task_counts),
        },
        "truth_support": {
            "raw_tied_parents": total["raw_tied"],
            "raw_nontied_parents": total["raw_nontied"],
            "normalized_tied_parents": total["normalized_tied"],
            "normalized_nontied_parents": total["normalized_nontied"],
            "alias_parents": total["alias"],
            "alias_tasks": alias_tasks,
            "impossible_direction_parents": total["impossible"],
            "normalized_tied_boundary_counts": {
                "all_zero": total["boundary_all_zero"],
                "all_one": total["boundary_all_one"],
                "interior": total["boundary_interior"],
            },
            "official_five_decimal_grid_violations": off_grid,
        },
        "common_channel_support": {
            "comparative_parents": total["common"],
            "raw_nontied_parents": total["common_raw_nontied"],
            "normalized_nontied_parents": total["common_norm_nontied"],
            "raw_truth_descriptive_credit": credit,
        },
        "per_task": {
            task: {key: int(value) for key, value in sorted(row.items())}
            for task, row in sorted(task_counts.items())
        },
        "material_aliasing_gate": {
            "alias_parents_minimum": parent_minimum,
            "alias_tasks_minimum": task_minimum,
            "alias_parent_gate_pass": total["alias"] >= parent_minimum,
            "alias_task_gate_pass": alias_tasks >= task_minimum,
            "status": "MATERIAL_Y_NORM_ALIASING" if gate else "LIMITED_Y_NORM_ALIASING",
        },
        "interpretation": {
            "formal_primary_status_changed": False,
            "old_machine_verdict_may_be_reversed": False,
            "post_hoc_old_cohort": True,
            "method_positive_claim_allowed": False,
            "unrounded_score_recovered": False,
        },
    }


def load_bound_inputs(args: argparse.Namespace, protocol: dict[str, Any]):
    locked = protocol["locked_inputs"]
    selected, selection_summary = base.load_selected(args.selection_dir)
    all_cards = {card for parent in selected for card in parent["candidate_card_ids"]}
    actual_selection = {
        "selection_summary_sha256": base.digest(args.selection_dir / "summary.json"),
        "selected_parents_sha256": base.digest(args.selection_dir / "selected_parents.jsonl"),
        "selected_parents": len(selected),
        "selected_candidates": len(all_cards),
    }
    if any(actual_selection[key] != locked[key] for key in actual_selection):
        raise VerificationError("locked selection mismatch")
    labels = labels_from_vaults(args.intake_root, selected, selection_summary)
    manifests, replay_summary = base.load_replay(args.replay_dir, all_cards)
    if (
        base.digest(args.replay_dir / "summary.json") != locked["replay_summary_sha256"]
        or base.digest(args.replay_dir / "replay_manifest.jsonl") != locked["replay_manifest_sha256"]
    ):
        raise VerificationError("locked replay mismatch")

    approval_sha = base.valid_sha(args.expect_approval_sha256, "approval SHA")
    approval = base.object_file(args.approval, "approval")
    if (
        approval_sha != locked["approval_sha256"]
        or base.digest(args.approval) != approval_sha
        or approval.get("protocol") != "score-channel-replay-approval-v1"
        or approval.get("approved") is not True
        or approval.get("replay_manifest_sha256") != locked["replay_manifest_sha256"]
        or approval.get("replay_summary_sha256") != locked["replay_summary_sha256"]
    ):
        raise VerificationError("approval mismatch")
    worker = base.valid_sha(approval.get("worker_source_commit"), "worker commit", length=40)

    orientation_sha = base.valid_sha(args.expect_orientation_sha256, "orientation SHA")
    orientation_receipt = base.object_file(args.orientation, "orientation")
    raw_orientation = orientation_receipt.get("orientation")
    tasks = {row["task"] for row in selected}
    if (
        orientation_sha != locked["orientation_sha256"]
        or base.digest(args.orientation) != orientation_sha
        or orientation_receipt.get("protocol") != "score-channel-task-orientation-v1"
        or orientation_receipt.get("outcomes_read") is not False
        or not isinstance(raw_orientation, dict)
        or any(raw_orientation.get(task) not in {-1, 1} for task in tasks)
    ):
        raise VerificationError("orientation mismatch")
    orientation = {task: int(raw_orientation[task]) for task in tasks}
    results, result_shas = base.load_results(
        args.result,
        args.expect_result_sha256,
        manifests,
        replay_summary,
        approval_sha,
        worker,
    )
    if result_shas != locked["result_sha256_by_shard"]:
        raise VerificationError("result shard mismatch")
    return selected, labels, results, orientation, result_shas


def verify(args: argparse.Namespace) -> dict[str, Any]:
    protocol = read_protocol(args.protocol, args.expect_protocol_sha256)
    grader = protocol["grader_contract"]
    if (
        repo_head(args.mlebench_repo) != grader["mlebench_git_commit"]
        or base.digest(args.grade_helpers) != grader["grade_helpers_sha256"]
        or "rounded_score = round(score, 5)" not in args.grade_helpers.read_text(encoding="utf-8")
    ):
        raise VerificationError("grader contract mismatch")
    selected, labels, results, orientation, result_shas = load_bound_inputs(args, protocol)
    gate = protocol["material_aliasing_gate"]
    rebuilt = independent_summary(
        selected,
        labels,
        results,
        orientation,
        int(gate["alias_parents_minimum"]),
        int(gate["alias_tasks_minimum"]),
    )
    analysis = base.object_file(args.analysis, "truth aliasing analysis")
    if analysis.get("protocol") != "score-channel-truth-aliasing-audit-v1":
        raise VerificationError("analysis protocol mismatch")
    for key, expected in rebuilt.items():
        if analysis.get(key) != expected:
            raise VerificationError(f"analysis differs for {key}")
    timing = protocol["timing_and_evidence"]
    if (
        rebuilt["truth_support"]["normalized_tied_parents"] != timing["known_y_norm_tied_parents"]
        or rebuilt["truth_support"]["normalized_nontied_parents"] != timing["known_y_norm_nontied_parents"]
        or rebuilt["common_channel_support"]["comparative_parents"] != timing["known_common_comparative_parents"]
        or rebuilt["common_channel_support"]["normalized_nontied_parents"]
        != timing["known_common_y_norm_nontied_parents"]
    ):
        raise VerificationError("known aggregate mismatch")
    expected_inputs = {
        "protocol_sha256": base.digest(args.protocol),
        "selection_summary_sha256": base.digest(args.selection_dir / "summary.json"),
        "selected_parents_sha256": base.digest(args.selection_dir / "selected_parents.jsonl"),
        "replay_summary_sha256": base.digest(args.replay_dir / "summary.json"),
        "replay_manifest_sha256": base.digest(args.replay_dir / "replay_manifest.jsonl"),
        "approval_sha256": base.digest(args.approval),
        "orientation_sha256": base.digest(args.orientation),
        "result_sha256_by_shard": result_shas,
        "grade_helpers_sha256": base.digest(args.grade_helpers),
        "mlebench_git_commit": repo_head(args.mlebench_repo),
    }
    if analysis.get("inputs") != expected_inputs:
        raise VerificationError("analysis input receipt mismatch")
    if (
        analysis.get("implementation", {}).get("source_commit") != repo_head(args.repo_root)
        or analysis.get("implementation", {}).get("script_sha256") != base.digest(args.producer)
        or analysis.get("access_attestation")
        != {
            "raw_labels_or_channel_values_written": False,
            "future_truth_vault_opened": False,
            "gpu_jobs": 0,
            "api_calls": 0,
            "model_fits": 0,
        }
    ):
        raise VerificationError("implementation or access attestation mismatch")
    return {
        "protocol": "score-channel-truth-aliasing-independent-verifier-v1",
        "status": "VERIFIED_TRUTH_ALIASING_AUDIT",
        "analysis_sha256": base.digest(args.analysis),
        "decision": rebuilt,
        "inputs": expected_inputs,
        "producer_imported": False,
        "raw_labels_or_channel_values_written": False,
    }


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--selection-dir", required=True, type=Path)
    parser.add_argument("--intake-root", required=True, type=Path)
    parser.add_argument("--replay-dir", required=True, type=Path)
    parser.add_argument("--approval", required=True, type=Path)
    parser.add_argument("--expect-approval-sha256", required=True)
    parser.add_argument("--orientation", required=True, type=Path)
    parser.add_argument("--expect-orientation-sha256", required=True)
    parser.add_argument("--result", action="append", required=True, type=Path)
    parser.add_argument("--expect-result-sha256", action="append", required=True)
    parser.add_argument("--mlebench-repo", required=True, type=Path)
    parser.add_argument("--grade-helpers", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--producer", required=True, type=Path)
    parser.add_argument("--analysis", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if args.receipt.exists():
        print("TRUTH_ALIASING_VERIFY_ERROR: refusing overwrite", file=os.sys.stderr)
        return 2
    try:
        value = verify(args)
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except (VerificationError, base.VerifyError, OSError, TypeError, ValueError) as error:
        print(f"TRUTH_ALIASING_VERIFY_ERROR: {error}", file=os.sys.stderr)
        return 2
    print(json.dumps({"status": value["status"], "analysis_sha256": value["analysis_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
