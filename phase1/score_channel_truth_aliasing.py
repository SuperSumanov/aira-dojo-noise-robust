#!/usr/bin/env python3
"""Post-hoc audit of ordering support erased by clipped ``y_norm`` labels.

The frozen old score-channel cohort is already outcome-known.  This audit cannot
change its primary verdict.  It reports aggregate support only and never writes
raw label or channel values.
"""
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


PROTOCOL = "score-channel-truth-aliasing-audit-v1"
TOLERANCE = 1e-12


class AliasingError(RuntimeError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def repository_head(root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    value = completed.stdout.strip()
    if completed.returncode or len(value) != 40:
        raise AliasingError("cannot resolve source commit")
    return value


def load_protocol(path: Path, expected_sha: str) -> dict[str, Any]:
    if base.digest(path) != base.valid_sha(expected_sha, "protocol SHA"):
        raise AliasingError("protocol SHA mismatch")
    value = base.object_file(path, "truth aliasing protocol")
    timing = value.get("timing_and_evidence") or {}
    if (
        value.get("protocol") != "score-channel-truth-aliasing-protocol-v1"
        or value.get("status") != "FROZEN_POST_HOC_RAW_GRADE_NOT_READ"
        or timing.get("old_primary_outcomes_already_known") is not True
        or timing.get("raw_graded_alias_counts_read_before_freeze") is not False
        or timing.get("formal_primary_status_may_change") is not False
    ):
        raise AliasingError("protocol timing contract mismatch")
    if (value.get("scope") or {}) != {
        "gpu_jobs": 0,
        "api_calls": 0,
        "model_fits": 0,
        "base_llm_update": False,
    }:
        raise AliasingError("protocol resource scope mismatch")
    return value


def load_truth(
    intake_root: Path,
    selected: list[dict[str, Any]],
    selection_summary: dict[str, Any],
) -> dict[str, dict[str, float]]:
    wanted: dict[str, set[str]] = collections.defaultdict(set)
    identity: dict[str, tuple[str, str]] = {}
    for parent in selected:
        for card in parent["candidate_card_ids"]:
            wanted[parent["source_intake"]].add(card)
            identity[card] = (parent["task"], parent["run_id"])
    bindings = (selection_summary.get("inputs") or {}).get("intake_summary_sha256")
    if not isinstance(bindings, dict):
        raise AliasingError("missing intake bindings")

    labels: dict[str, dict[str, float]] = {}
    for intake, cards in sorted(wanted.items()):
        root = intake_root / intake
        summary_path = root / "summary.json"
        if base.digest(summary_path) != base.valid_sha(bindings.get(intake), "intake summary SHA"):
            raise AliasingError("intake summary SHA mismatch")
        intake_summary = base.object_file(summary_path, "intake summary")
        vault_path = root / "label_vault.jsonl"
        expected_vault = (intake_summary.get("outputs") or {}).get("label_vault_sha256")
        if base.digest(vault_path) != base.valid_sha(expected_vault, "label vault SHA"):
            raise AliasingError("label vault SHA mismatch")
        for row in base.row_file(vault_path, "label vault", allow_empty=True):
            card = row.get("card_id")
            if card not in cards:
                continue
            if (
                set(row) != base.VAULT_KEYS
                or card in labels
                or (row.get("task"), row.get("run_id")) != identity[card]
                or row.get("eligible_by_start_time") is not True
                or not base.finite(row.get("graded"))
                or not base.finite(row.get("y_norm"))
            ):
                raise AliasingError("invalid selected label")
            labels[card] = {"graded": float(row["graded"]), "y_norm": float(row["y_norm"])}
    if set(labels) != set(identity):
        raise AliasingError("selected labels incomplete")
    return labels


def varies(values: list[float]) -> bool:
    if len(values) < 2 or any(not math.isfinite(value) for value in values):
        raise AliasingError("invalid truth support")
    return max(values) - min(values) > TOLERANCE


def tie_boundary(values: list[float]) -> str:
    if varies(values):
        raise AliasingError("boundary requested for non-tied labels")
    if all(abs(value) <= TOLERANCE for value in values):
        return "all_zero"
    if all(abs(value - 1.0) <= TOLERANCE for value in values):
        return "all_one"
    return "interior"


def summarize(
    selected: list[dict[str, Any]],
    labels: dict[str, dict[str, float]],
    results: dict[str, dict[str, Any]],
    orientation: dict[str, int],
    alias_parent_minimum: int,
    alias_task_minimum: int,
) -> dict[str, Any]:
    states = collections.Counter()
    per_task: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    seen_cards: set[str] = set()
    common_raw_credits: list[tuple[float, float]] = []

    for parent in selected:
        cards = list(parent["candidate_card_ids"])
        if len(cards) < 2 or any(card in seen_cards for card in cards):
            raise AliasingError("duplicate or invalid selected candidate")
        seen_cards.update(cards)
        task = str(parent["task"])
        if orientation.get(task) not in {-1, 1}:
            raise AliasingError("missing task orientation")
        raw = [labels[card]["graded"] for card in cards]
        normalized = [labels[card]["y_norm"] for card in cards]
        raw_varies = varies(raw)
        normalized_varies = varies(normalized)

        states["parents"] += 1
        states["raw_nontied" if raw_varies else "raw_tied"] += 1
        states["normalized_nontied" if normalized_varies else "normalized_tied"] += 1
        per_task[task]["parents"] += 1
        per_task[task]["raw_nontied"] += int(raw_varies)
        per_task[task]["normalized_nontied"] += int(normalized_varies)
        if not normalized_varies:
            boundary = tie_boundary(normalized)
            states[f"normalized_tied_{boundary}"] += 1
            per_task[task][f"normalized_tied_{boundary}"] += 1
        if raw_varies and not normalized_varies:
            states["alias_parents"] += 1
            per_task[task]["alias_parents"] += 1
        if normalized_varies and not raw_varies:
            states["impossible_direction_parents"] += 1
            per_task[task]["impossible_direction_parents"] += 1

        common = [
            card
            for card in cards
            if results[card].get("sub_exists") is True
            and base.finite(results[card].get("sub_score"))
            and results[card].get("val_how") == "keyed"
            and base.finite(results[card].get("stdout_val"))
        ]
        if len(common) >= 2:
            states["common_comparative_parents"] += 1
            per_task[task]["common_comparative_parents"] += 1
            common_raw = [labels[card]["graded"] for card in common]
            common_normalized = [labels[card]["y_norm"] for card in common]
            common_raw_varies = varies(common_raw)
            common_normalized_varies = varies(common_normalized)
            states["common_raw_nontied_parents"] += int(common_raw_varies)
            states["common_normalized_nontied_parents"] += int(common_normalized_varies)
            per_task[task]["common_raw_nontied_parents"] += int(common_raw_varies)
            per_task[task]["common_normalized_nontied_parents"] += int(common_normalized_varies)
            if common_raw_varies:
                direction = orientation[task]
                truth = {card: direction * labels[card]["graded"] for card in common}
                external = {card: direction * float(results[card]["sub_score"]) for card in common}
                stdout = {card: direction * float(results[card]["stdout_val"]) for card in common}
                common_raw_credits.append(
                    (base.expected_credit(external, truth), base.expected_credit(stdout, truth))
                )

    off_grid = sum(
        abs(value["graded"] - round(value["graded"], 5)) > TOLERANCE
        for value in labels.values()
    )
    alias_tasks = sum(counts["alias_parents"] > 0 for counts in per_task.values())
    gate_pass = states["alias_parents"] >= alias_parent_minimum and alias_tasks >= alias_task_minimum
    if states["impossible_direction_parents"]:
        raise AliasingError("normalization created ordering absent from raw grade")

    if common_raw_credits:
        external_credit = sum(row[0] for row in common_raw_credits) / len(common_raw_credits)
        stdout_credit = sum(row[1] for row in common_raw_credits) / len(common_raw_credits)
        common_credit = {
            "parents": len(common_raw_credits),
            "external_top1_credit": external_credit,
            "stdout_top1_credit": stdout_credit,
            "delta": external_credit - stdout_credit,
        }
    else:
        common_credit = {
            "parents": 0,
            "external_top1_credit": None,
            "stdout_top1_credit": None,
            "delta": None,
        }

    return {
        "counts": {
            "selected_parents": states["parents"],
            "selected_candidates": len(seen_cards),
            "tasks": len(per_task),
        },
        "truth_support": {
            "raw_tied_parents": states["raw_tied"],
            "raw_nontied_parents": states["raw_nontied"],
            "normalized_tied_parents": states["normalized_tied"],
            "normalized_nontied_parents": states["normalized_nontied"],
            "alias_parents": states["alias_parents"],
            "alias_tasks": alias_tasks,
            "impossible_direction_parents": states["impossible_direction_parents"],
            "normalized_tied_boundary_counts": {
                "all_zero": states["normalized_tied_all_zero"],
                "all_one": states["normalized_tied_all_one"],
                "interior": states["normalized_tied_interior"],
            },
            "official_five_decimal_grid_violations": off_grid,
        },
        "common_channel_support": {
            "comparative_parents": states["common_comparative_parents"],
            "raw_nontied_parents": states["common_raw_nontied_parents"],
            "normalized_nontied_parents": states["common_normalized_nontied_parents"],
            "raw_truth_descriptive_credit": common_credit,
        },
        "per_task": {
            task: {key: int(value) for key, value in sorted(counts.items())}
            for task, counts in sorted(per_task.items())
        },
        "material_aliasing_gate": {
            "alias_parents_minimum": alias_parent_minimum,
            "alias_tasks_minimum": alias_task_minimum,
            "alias_parent_gate_pass": states["alias_parents"] >= alias_parent_minimum,
            "alias_task_gate_pass": alias_tasks >= alias_task_minimum,
            "status": "MATERIAL_Y_NORM_ALIASING" if gate_pass else "LIMITED_Y_NORM_ALIASING",
        },
        "interpretation": {
            "formal_primary_status_changed": False,
            "old_machine_verdict_may_be_reversed": False,
            "post_hoc_old_cohort": True,
            "method_positive_claim_allowed": False,
            "unrounded_score_recovered": False,
        },
    }


def load_inputs(args: argparse.Namespace, protocol: dict[str, Any]) -> tuple[
    list[dict[str, Any]], dict[str, dict[str, float]], dict[str, dict[str, Any]], dict[str, int], dict[str, str]
]:
    locked = protocol.get("locked_inputs") or {}
    selected, selection_summary = base.load_selected(args.selection_dir)
    selected_cards = {card for parent in selected for card in parent["candidate_card_ids"]}
    if (
        base.digest(args.selection_dir / "summary.json") != locked.get("selection_summary_sha256")
        or base.digest(args.selection_dir / "selected_parents.jsonl") != locked.get("selected_parents_sha256")
        or len(selected) != locked.get("selected_parents")
        or len(selected_cards) != locked.get("selected_candidates")
    ):
        raise AliasingError("locked selection mismatch")
    labels = load_truth(args.intake_root, selected, selection_summary)
    manifests, replay_summary = base.load_replay(args.replay_dir, selected_cards)
    if (
        base.digest(args.replay_dir / "summary.json") != locked.get("replay_summary_sha256")
        or base.digest(args.replay_dir / "replay_manifest.jsonl") != locked.get("replay_manifest_sha256")
    ):
        raise AliasingError("locked replay mismatch")

    approval_sha = base.valid_sha(args.expect_approval_sha256, "approval SHA")
    if approval_sha != locked.get("approval_sha256") or base.digest(args.approval) != approval_sha:
        raise AliasingError("approval SHA mismatch")
    approval = base.object_file(args.approval, "approval")
    worker = base.valid_sha(approval.get("worker_source_commit"), "worker commit", length=40)
    if (
        approval.get("protocol") != "score-channel-replay-approval-v1"
        or approval.get("approved") is not True
        or approval.get("replay_manifest_sha256") != locked.get("replay_manifest_sha256")
        or approval.get("replay_summary_sha256") != locked.get("replay_summary_sha256")
    ):
        raise AliasingError("approval contract mismatch")

    orientation_sha = base.valid_sha(args.expect_orientation_sha256, "orientation SHA")
    if orientation_sha != locked.get("orientation_sha256") or base.digest(args.orientation) != orientation_sha:
        raise AliasingError("orientation SHA mismatch")
    orientation_receipt = base.object_file(args.orientation, "orientation")
    orientation_raw = orientation_receipt.get("orientation")
    tasks = {parent["task"] for parent in selected}
    if (
        orientation_receipt.get("protocol") != "score-channel-task-orientation-v1"
        or orientation_receipt.get("outcomes_read") is not False
        or not isinstance(orientation_raw, dict)
        or any(orientation_raw.get(task) not in {-1, 1} for task in tasks)
    ):
        raise AliasingError("orientation contract mismatch")
    orientation = {task: int(orientation_raw[task]) for task in tasks}

    results, result_shas = base.load_results(
        args.result,
        args.expect_result_sha256,
        manifests,
        replay_summary,
        approval_sha,
        worker,
    )
    if result_shas != locked.get("result_sha256_by_shard"):
        raise AliasingError("locked result shards mismatch")
    return selected, labels, results, orientation, result_shas


def audit(args: argparse.Namespace) -> dict[str, Any]:
    protocol = load_protocol(args.protocol, args.expect_protocol_sha256)
    grader = protocol.get("grader_contract") or {}
    if (
        base.digest(args.grade_helpers) != grader.get("grade_helpers_sha256")
        or "rounded_score = round(score, 5)" not in args.grade_helpers.read_text(encoding="utf-8")
    ):
        raise AliasingError("official grader precision contract mismatch")
    grader_commit = repository_head(args.mlebench_repo)
    if grader_commit != grader.get("mlebench_git_commit"):
        raise AliasingError("MLE-bench commit mismatch")

    selected, labels, results, orientation, result_shas = load_inputs(args, protocol)
    gate = protocol.get("material_aliasing_gate") or {}
    decision = summarize(
        selected,
        labels,
        results,
        orientation,
        int(gate.get("alias_parents_minimum")),
        int(gate.get("alias_tasks_minimum")),
    )
    timing = protocol["timing_and_evidence"]
    if (
        decision["truth_support"]["normalized_tied_parents"] != timing["known_y_norm_tied_parents"]
        or decision["truth_support"]["normalized_nontied_parents"] != timing["known_y_norm_nontied_parents"]
        or decision["common_channel_support"]["comparative_parents"] != timing["known_common_comparative_parents"]
        or decision["common_channel_support"]["normalized_nontied_parents"]
        != timing["known_common_y_norm_nontied_parents"]
    ):
        raise AliasingError("known pre-freeze aggregate mismatch")
    return {
        "protocol": PROTOCOL,
        "status": "TRUTH_ALIASING_AUDIT_COMPLETE",
        **decision,
        "inputs": {
            "protocol_sha256": base.digest(args.protocol),
            "selection_summary_sha256": base.digest(args.selection_dir / "summary.json"),
            "selected_parents_sha256": base.digest(args.selection_dir / "selected_parents.jsonl"),
            "replay_summary_sha256": base.digest(args.replay_dir / "summary.json"),
            "replay_manifest_sha256": base.digest(args.replay_dir / "replay_manifest.jsonl"),
            "approval_sha256": base.digest(args.approval),
            "orientation_sha256": base.digest(args.orientation),
            "result_sha256_by_shard": result_shas,
            "grade_helpers_sha256": base.digest(args.grade_helpers),
            "mlebench_git_commit": grader_commit,
        },
        "implementation": {
            "source_commit": repository_head(args.repo_root),
            "script_sha256": base.digest(Path(__file__)),
        },
        "access_attestation": {
            "raw_labels_or_channel_values_written": False,
            "future_truth_vault_opened": False,
            "gpu_jobs": 0,
            "api_calls": 0,
            "model_fits": 0,
        },
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
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if args.output.exists():
        print("TRUTH_ALIASING_AUDIT_ERROR: refusing overwrite", file=os.sys.stderr)
        return 2
    try:
        value = audit(args)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except (AliasingError, base.VerifyError, OSError, TypeError, ValueError) as error:
        print(f"TRUTH_ALIASING_AUDIT_ERROR: {error}", file=os.sys.stderr)
        return 2
    print(canonical({
        "status": value["status"],
        "truth_support": value["truth_support"],
        "common_channel_support": value["common_channel_support"],
        "material_aliasing_gate": value["material_aliasing_gate"],
        "interpretation": value["interpretation"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
