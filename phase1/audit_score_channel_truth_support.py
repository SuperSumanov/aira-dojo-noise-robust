#!/usr/bin/env python3
"""Direct audit of discriminative truth support in the frozen score-channel cohort.

The audit intentionally does not import the grounding-availability producer. It
loads the hash-bound selection, labels, replay manifest, approval, and result
shards through the pre-existing independent readers, then emits counts only.
Raw labels and channel values are never written.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import subprocess
from typing import Any

from phase1 import verify_score_channel_prospective_analysis as base


PROTOCOL = "score-channel-truth-support-direct-audit-v1"
TOLERANCE = 1e-12


class TruthSupportError(RuntimeError):
    """Raised when an audit binding or support invariant fails."""


def truth_varies(cards: list[str], labels: dict[str, float]) -> bool:
    if len(cards) < 2 or any(card not in labels for card in cards):
        raise TruthSupportError("invalid truth support")
    values = [float(labels[card]) for card in cards]
    return max(values) - min(values) > TOLERANCE


def summarize_support(
    selected: list[dict[str, Any]],
    labels: dict[str, float],
    results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not selected:
        raise TruthSupportError("empty selection")
    task_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"parents": 0, "nontied": 0}
    )
    candidate_distribution: Counter[int] = Counter()
    states = {
        "all_tied": 0,
        "nontied": 0,
        "external_any": 0,
        "external_comparative": 0,
        "stdout_any": 0,
        "stdout_comparative": 0,
        "nontied_external_any": 0,
        "nontied_external_comparative": 0,
        "nontied_stdout_any": 0,
        "nontied_stdout_comparative": 0,
        "common_comparative": 0,
        "common_truth_tied": 0,
        "common_truth_nontied": 0,
        "common_cards": 0,
    }
    runs: set[str] = set()
    all_cards: set[str] = set()
    for parent in selected:
        cards = list(parent["candidate_card_ids"])
        if len(cards) < 2 or any(card in all_cards for card in cards):
            raise TruthSupportError("invalid or duplicate candidate identity")
        all_cards.update(cards)
        runs.add(str(parent["run_id"]))
        candidate_distribution[len(cards)] += 1
        varies = truth_varies(cards, labels)
        states["nontied" if varies else "all_tied"] += 1
        task = str(parent["task"])
        task_counts[task]["parents"] += 1
        task_counts[task]["nontied"] += int(varies)
        external = [
            card
            for card in cards
            if results[card].get("sub_exists") is True
            and base.finite(results[card].get("sub_score"))
        ]
        stdout = [
            card
            for card in cards
            if results[card].get("val_how") == "keyed"
            and base.finite(results[card].get("stdout_val"))
        ]
        states["external_any"] += int(bool(external))
        states["external_comparative"] += int(len(external) >= 2)
        states["stdout_any"] += int(bool(stdout))
        states["stdout_comparative"] += int(len(stdout) >= 2)
        if varies:
            states["nontied_external_any"] += int(bool(external))
            states["nontied_external_comparative"] += int(len(external) >= 2)
            states["nontied_stdout_any"] += int(bool(stdout))
            states["nontied_stdout_comparative"] += int(len(stdout) >= 2)
        common = sorted(set(external) & set(stdout))
        if len(common) >= 2:
            states["common_comparative"] += 1
            states["common_cards"] += len(common)
            common_varies = truth_varies(common, labels)
            states[
                "common_truth_nontied" if common_varies else "common_truth_tied"
            ] += 1

    parents = len(selected)
    tasks_with_nontied = [
        task for task, count in sorted(task_counts.items()) if count["nontied"]
    ]
    tasks_all_tied = [
        task for task, count in sorted(task_counts.items()) if not count["nontied"]
    ]
    return {
        "counts": {
            "selected_parents": parents,
            "selected_candidates": len(all_cards),
            "runs": len(runs),
            "tasks": len(task_counts),
            "candidate_count_distribution": {
                str(key): value for key, value in sorted(candidate_distribution.items())
            },
        },
        "truth_support": {
            "all_tied_parents": states["all_tied"],
            "nontied_parents": states["nontied"],
            "nontied_share": states["nontied"] / parents,
            "tasks_with_nontied": tasks_with_nontied,
            "tasks_all_tied": tasks_all_tied,
        },
        "channel_support": {
            "external": {
                "parents_with_any": states["external_any"],
                "comparative_parents": states["external_comparative"],
                "nontied_with_any": states["nontied_external_any"],
                "nontied_comparative": states[
                    "nontied_external_comparative"
                ],
            },
            "stdout": {
                "parents_with_any": states["stdout_any"],
                "comparative_parents": states["stdout_comparative"],
                "nontied_with_any": states["nontied_stdout_any"],
                "nontied_comparative": states["nontied_stdout_comparative"],
            },
        },
        "primary_common_support": {
            "comparative_parents": states["common_comparative"],
            "cards": states["common_cards"],
            "truth_tied_parents": states["common_truth_tied"],
            "truth_nontied_parents": states["common_truth_nontied"],
        },
        "identifiability_funnel": {
            "structural_parents": parents,
            "truth_informative_parents": states["nontied"],
            "external_comparative_and_truth_informative": states[
                "nontied_external_comparative"
            ],
            "stdout_comparative_and_truth_informative": states[
                "nontied_stdout_comparative"
            ],
            "paired_channels_comparative_and_truth_informative": states[
                "common_truth_nontied"
            ],
        },
        "interpretation": {
            "formal_primary_status_changed": False,
            "formal_primary_status": "SCORE_CHANNEL_MECHANISM_KILL",
            "discriminative_common_support_zero": states[
                "common_truth_nontied"
            ]
            == 0,
            "evidence_for_channel_equality_or_external_harm_allowed": False,
            "method_positive_claim_allowed": False,
        },
    }


def load_protocol(path: Path, expected_sha: str) -> dict[str, Any]:
    expected = base.valid_sha(expected_sha, "protocol SHA")
    if base.digest(path) != expected:
        raise TruthSupportError("protocol SHA mismatch")
    value = base.object_file(path, "grounding protocol")
    if (
        value.get("protocol")
        != "score-channel-grounding-availability-protocol-v1"
        or value.get("status") != "FROZEN_POST_HOC_SECONDARY_NOT_RUN"
        or value.get("outcomes_read_before_freeze") is not True
    ):
        raise TruthSupportError("protocol timing contract mismatch")
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
        raise TruthSupportError("cannot resolve source commit")
    return value


def audit(args: argparse.Namespace) -> dict[str, Any]:
    protocol = load_protocol(args.protocol, args.expect_protocol_sha256)
    cohort = protocol.get("locked_cohort") or {}
    selected, selection_summary = base.load_selected(args.selection_dir)
    cards = {card for parent in selected for card in parent["candidate_card_ids"]}
    labels = base.load_labels(args.intake_root, selected, selection_summary)
    manifests, replay_summary = base.load_replay(args.replay_dir, cards)
    if (
        base.digest(args.selection_dir / "summary.json")
        != cohort.get("selection_summary_sha256")
        or base.digest(args.selection_dir / "selected_parents.jsonl")
        != cohort.get("selected_parents_sha256")
        or base.digest(args.replay_dir / "summary.json")
        != cohort.get("replay_summary_sha256")
        or base.digest(args.replay_dir / "replay_manifest.jsonl")
        != cohort.get("replay_manifest_sha256")
        or len(selected) != cohort.get("selected_parents")
        or len(cards) != cohort.get("selected_candidates")
    ):
        raise TruthSupportError("locked cohort mismatch")

    approval_sha = base.valid_sha(args.expect_approval_sha256, "approval SHA")
    if base.digest(args.approval) != approval_sha:
        raise TruthSupportError("approval SHA mismatch")
    approval = base.object_file(args.approval, "approval")
    worker = base.valid_sha(
        approval.get("worker_source_commit"), "worker commit", length=40
    )
    if (
        approval.get("protocol") != "score-channel-replay-approval-v1"
        or approval.get("approved") is not True
        or worker != cohort.get("frozen_worker_source_commit")
        or approval.get("replay_manifest_sha256")
        != base.digest(args.replay_dir / "replay_manifest.jsonl")
        or approval.get("replay_summary_sha256")
        != base.digest(args.replay_dir / "summary.json")
    ):
        raise TruthSupportError("approval contract mismatch")
    results, result_shas = base.load_results(
        args.result,
        args.expect_result_sha256,
        manifests,
        replay_summary,
        approval_sha,
        worker,
    )
    decision = summarize_support(selected, labels, results)
    return {
        "protocol": PROTOCOL,
        "status": "DIRECT_LABEL_SUPPORT_AUDIT_COMPLETE",
        "producer_imported": False,
        **decision,
        "inputs": {
            "protocol_sha256": base.digest(args.protocol),
            "selection_summary_sha256": base.digest(
                args.selection_dir / "summary.json"
            ),
            "selected_parents_sha256": base.digest(
                args.selection_dir / "selected_parents.jsonl"
            ),
            "replay_summary_sha256": base.digest(
                args.replay_dir / "summary.json"
            ),
            "replay_manifest_sha256": base.digest(
                args.replay_dir / "replay_manifest.jsonl"
            ),
            "approval_sha256": approval_sha,
            "result_sha256_by_shard": result_shas,
        },
        "implementation": {
            "source_commit": repository_head(Path(__file__).resolve().parents[1]),
            "script_sha256": base.digest(Path(__file__)),
        },
        "access_attestation": {
            "raw_labels_or_channel_values_written": False,
            "task_subset_selected": False,
            "gpu_jobs": 0,
            "api_calls": 0,
            "model_fits": 0,
        },
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
    parser.add_argument("--result", type=Path, action="append", required=True)
    parser.add_argument(
        "--expect-result-sha256", action="append", required=True
    )
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if args.out.exists():
        print("TRUTH_SUPPORT_AUDIT_ERROR: refusing overwrite", file=os.sys.stderr)
        return 2
    try:
        value = audit(args)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
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
    except (base.VerifyError, TruthSupportError, OSError, ValueError) as error:
        print(f"TRUTH_SUPPORT_AUDIT_ERROR: {error}", file=os.sys.stderr)
        return 2
    print(
        base.canonical(
            {
                "status": value["status"],
                "identifiability_funnel": value["identifiability_funnel"],
                "interpretation": value["interpretation"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
