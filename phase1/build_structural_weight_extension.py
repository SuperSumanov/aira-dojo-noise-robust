#!/usr/bin/env python3
"""Outcome-blind 404-run extension of the frozen structural-weight trajectory."""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

from phase1 import build_structural_weight_trajectory as core


PROTOCOL = "prospective_structural_weight_extension_ad0b_v1"
STATUS = "OUTCOME_BLIND_STRUCTURAL_WEIGHT_EXTENSION_READY"
EXPECTED_SNAPSHOT = "ad0b624d636cb5e89f94d8887a7abe99f7b9ef6ce77bbde7da704b0275dedb0e"
BASELINE_RUNS = 240
PRIOR_ENDPOINT = 339
CURRENT_RUNS = 404
MILESTONES = (120, 160, 200, 240, 260, 280, 300, 320, 339, 360, 380, 400, 404)
EXTENSION_CHECKPOINTS = (360, 380, 400, 404)
PROTOCOL_BASENAME = "First960_结构权重时序外延404_结果前冻结.md"
PRIOR_PUBLIC = {
    "snapshot_sha256": "7cdaefcf2be7786442e1af1f4d0b4012edee708932f1fad31e174c0dcaf803a1",
    "runs": 339,
    "run_hhi": 0.04887705467234014,
    "pair_hhi": 0.1357471491993994,
    "pair_maximum_share": 0.31233396584440226,
    "maximum_positive_single_drop_attribution": 0.9641733656841007,
}
KNOWN_CURRENT_INVENTORY = {
    "runs": 404,
    "endpoints": 11310,
    "structural_pairs": 2884,
    "tasks": 31,
}
KNOWN_CURRENT_DOMINANT_PAIR_TASK_SHARE = 0.2947295423023578


def _claim_sections(
    runs: list[dict[str, Any]],
    records: dict[str, dict[str, Any]],
    scopes: dict[int, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]:
    baseline = scopes[BASELINE_RUNS]
    prior = scopes[PRIOR_ENDPOINT]
    current = scopes[CURRENT_RUNS]
    base_run_hhi = baseline["concentration"]["runs"]["hhi"]
    base_pair_hhi = baseline["concentration"]["structural_pairs"]["hhi"]
    current_pair_hhi = current["concentration"]["structural_pairs"]["hhi"]
    pair_delta = current_pair_hhi - base_pair_hhi

    checkpoints = []
    for count in EXTENSION_CHECKPOINTS:
        point = scopes[count]
        checkpoints.append(
            {
                "prefix_runs": count,
                "inversion_vs_reconstructed_first240": (
                    point["concentration"]["runs"]["hhi"] <= base_run_hhi
                    and point["concentration"]["structural_pairs"]["hhi"] > base_pair_hhi
                ),
            }
        )

    additions = runs[BASELINE_RUNS:]
    drop_rows = []
    for drop_id in sorted({row["drop_id"] for row in additions}):
        kept = runs[:BASELINE_RUNS] + [row for row in additions if row["drop_id"] != drop_id]
        value = core.scope_summary(kept, records)
        loo_pair_hhi = value["concentration"]["structural_pairs"]["hhi"]
        drop_rows.append(
            {
                "drop_id": drop_id,
                "removed_added_runs": sum(row["drop_id"] == drop_id for row in additions),
                "remaining_runs": len(kept),
                "run_hhi_delta_vs_first240": (
                    value["concentration"]["runs"]["hhi"] - base_run_hhi
                ),
                "pair_hhi_delta_vs_first240": loo_pair_hhi - base_pair_hhi,
                "attribution_fraction_of_positive_pair_hhi_delta": (
                    (current_pair_hhi - loo_pair_hhi) / pair_delta if pair_delta > 0 else None
                ),
            }
        )
    maximum_drop = max(
        [
            max(0.0, row["attribution_fraction_of_positive_pair_hhi_delta"])
            for row in drop_rows
            if row["attribution_fraction_of_positive_pair_hhi_delta"] is not None
        ]
        or [0.0]
    )

    dominant = current["concentration"]["structural_pairs"]["dominant_tasks"]
    if len(dominant) != 1:
        raise core.TrajectoryError("current pair-dominant task is tied")
    dominant_task = dominant[0]
    task_rows = []
    for task in sorted(current["counts"]["runs"]):
        base_value = core.scope_summary(
            [row for row in runs[:BASELINE_RUNS] if row["task"] != task], records
        )
        current_value = core.scope_summary(
            [row for row in runs if row["task"] != task], records
        )
        run_delta = (
            current_value["concentration"]["runs"]["hhi"]
            - base_value["concentration"]["runs"]["hhi"]
        )
        loo_pair_delta = (
            current_value["concentration"]["structural_pairs"]["hhi"]
            - base_value["concentration"]["structural_pairs"]["hhi"]
        )
        task_rows.append(
            {
                "removed_task": task,
                "is_current_pair_dominant_task": task == dominant_task,
                "run_hhi_delta": run_delta,
                "pair_hhi_delta": loo_pair_delta,
                "inversion_retained": run_delta <= 0 and loo_pair_delta > 0,
            }
        )

    retained = sum(row["inversion_retained"] for row in task_rows)
    dominant_retained = next(
        row["inversion_retained"]
        for row in task_rows
        if row["is_current_pair_dominant_task"]
    )
    mechanism = core.decomposition(baseline, current)
    pair_decomp = mechanism["pair_hhi"]
    tv_decomp = mechanism["run_to_pair_total_variation"]
    prior_inversion = (
        prior["concentration"]["runs"]["hhi"] <= base_run_hhi
        and prior["concentration"]["structural_pairs"]["hhi"] > base_pair_hhi
    )
    current_inversion = (
        current["concentration"]["runs"]["hhi"] <= base_run_hhi
        and current_pair_hhi > base_pair_hhi
    )
    gates = {
        "E1_extension_temporal_persistence": {
            "pass": all(row["inversion_vs_reconstructed_first240"] for row in checkpoints),
            "required": "all_360_380_400_404_checkpoints_retain_inversion",
            "observed": sum(row["inversion_vs_reconstructed_first240"] for row in checkpoints),
            "total": len(checkpoints),
            "checkpoints": checkpoints,
        },
        "E2_no_single_drop_artifact": {
            "pass": pair_delta > 0 and maximum_drop < 0.5,
            "required": "maximum_positive_single_drop_attribution_below_0.5",
            "observed": maximum_drop,
            "prior_public_observed": PRIOR_PUBLIC[
                "maximum_positive_single_drop_attribution"
            ],
        },
        "E3_single_task_robustness": {
            "pass": retained / len(task_rows) >= 0.8 and dominant_retained,
            "required": (
                "at_least_80_percent_task_deletions_and_dominant_task_deletion_retain_inversion"
            ),
            "retained": retained,
            "total": len(task_rows),
            "fraction": retained / len(task_rows),
            "dominant_task": dominant_task,
            "dominant_task_deletion_retained": dominant_retained,
        },
        "E4_yield_is_primary_mechanism": {
            "pass": (
                pair_decomp["total_delta"] > 0
                and tv_decomp["total_delta"] > 0
                and pair_decomp["opportunity_yield_fraction_of_positive_delta"] >= 0.5
                and tv_decomp["opportunity_yield_fraction_of_positive_delta"] >= 0.5
            ),
            "required": "yield_fraction_at_least_0.5_for_pair_hhi_and_run_to_pair_tv",
            "pair_hhi_yield_fraction": pair_decomp[
                "opportunity_yield_fraction_of_positive_delta"
            ],
            "run_to_pair_tv_yield_fraction": tv_decomp[
                "opportunity_yield_fraction_of_positive_delta"
            ],
        },
        "E5_reconstructed_version_direction_consistency": {
            "pass": prior_inversion and current_inversion,
            "required": "reconstructed_first339_and_first404_both_invert_vs_reconstructed_first240",
            "reconstructed_first339_inversion": prior_inversion,
            "reconstructed_first404_inversion": current_inversion,
        },
    }
    version_sensitivity = {
        "warning": (
            "provisional chronological ranks can change after late arrival; old and reconstructed "
            "first339 are not asserted byte-identical"
        ),
        "old_public_first339": PRIOR_PUBLIC,
        "reconstructed_first339": core.compact_scope(prior),
        "old_minus_reconstructed_first339": {
            "run_hhi": PRIOR_PUBLIC["run_hhi"] - prior["concentration"]["runs"]["hhi"],
            "pair_hhi": PRIOR_PUBLIC["pair_hhi"]
            - prior["concentration"]["structural_pairs"]["hhi"],
            "pair_maximum_share": PRIOR_PUBLIC["pair_maximum_share"]
            - prior["concentration"]["structural_pairs"]["maximum_share"],
        },
    }
    return drop_rows, task_rows, mechanism, gates, version_sensitivity


def build_result(
    snapshot_root: Path,
    expected_snapshot: str,
    source_commit: str,
    protocol_spec: Path,
    expected_protocol_spec_sha256: str,
) -> dict[str, Any]:
    if not core.valid_git_commit(source_commit):
        raise core.TrajectoryError("source commit is not a full lowercase Git SHA")
    if expected_snapshot != EXPECTED_SNAPSHOT:
        raise core.TrajectoryError("snapshot is not the preregistered ad0b snapshot")
    if protocol_spec.name != PROTOCOL_BASENAME:
        raise core.TrajectoryError("unexpected protocol specification basename")
    core.regular_file(protocol_spec)
    if core.sha256_file(protocol_spec) != expected_protocol_spec_sha256:
        raise core.TrajectoryError("protocol specification hash mismatch")
    runs, records, receipts = core.load_structural_inputs(snapshot_root, expected_snapshot)
    if len(runs) != CURRENT_RUNS:
        raise core.TrajectoryError(f"extension expects exactly {CURRENT_RUNS} runs")
    current_preflight = core.scope_summary(runs, records)
    observed_inventory = {
        key: current_preflight["inventory"][key]
        for key in ("runs", "endpoints", "structural_pairs", "tasks")
    }
    if observed_inventory != KNOWN_CURRENT_INVENTORY:
        raise core.TrajectoryError("snapshot inventory disagrees with preregistered known counts")
    observed_share = current_preflight["concentration"]["structural_pairs"]["maximum_share"]
    if observed_share != KNOWN_CURRENT_DOMINANT_PAIR_TASK_SHARE:
        raise core.TrajectoryError("snapshot dominant pair-task share disagrees with preregistration")
    scopes = {
        index: core.scope_summary(runs[:index], records)
        for index in range(1, CURRENT_RUNS)
    }
    scopes[CURRENT_RUNS] = current_preflight
    drop_rows, task_rows, mechanism, gates, sensitivity = _claim_sections(
        runs, records, scopes
    )
    trajectory = [
        {"prefix_runs": index, **core.compact_scope(scopes[index])}
        for index in range(1, CURRENT_RUNS + 1)
    ]
    result = {
        "protocol": PROTOCOL,
        "status": STATUS,
        "snapshot_sha256": expected_snapshot,
        "known_before_protocol_freeze": {
            "current_inventory_known": KNOWN_CURRENT_INVENTORY,
            "current_dominant_pair_task_share_known": KNOWN_CURRENT_DOMINANT_PAIR_TASK_SHARE,
            "prior_public_result_known": PRIOR_PUBLIC,
            "current_hhi_trajectory_decomposition_and_deletions_known": False,
            "analysis_is_descriptive_not_a_predictor_effect_test": True,
        },
        "inputs": {
            **receipts["input_hashes"],
            "protocol_spec_sha256": expected_protocol_spec_sha256,
        },
        "reproducibility": {
            "source_commit": source_commit,
            "source_sha256": core.sha256_file(Path(__file__)),
            "python_version": platform.python_version(),
            "randomness_used": False,
            "baseline_runs": BASELINE_RUNS,
            "prior_endpoint_runs": PRIOR_ENDPOINT,
            "current_runs": CURRENT_RUNS,
            "milestones": list(MILESTONES),
            "extension_checkpoints": list(EXTENSION_CHECKPOINTS),
        },
        "full_prefix_trajectory": trajectory,
        "milestones": [
            {"prefix_runs": index, **core.compact_scope(scopes[index])}
            for index in MILESTONES
        ],
        "baseline_first240": core.compact_scope(scopes[BASELINE_RUNS]),
        "reconstructed_first339": core.compact_scope(scopes[PRIOR_ENDPOINT]),
        "current_first404": core.compact_scope(scopes[CURRENT_RUNS]),
        "current_task_yield_table": core.task_table(
            scopes[BASELINE_RUNS], scopes[CURRENT_RUNS]
        ),
        "mechanism_decomposition": mechanism,
        "leave_one_added_drop_out": drop_rows,
        "leave_one_task_out": task_rows,
        "claim_gates": gates,
        "version_sensitivity": sensitivity,
        "interpretation_contract": {
            "all_gates_passed": all(gate["pass"] for gate in gates.values()),
            "known_pair_share_declared_as_new_discovery": False,
            "provisional_rank_stability_claim": False,
            "inverse_hhi_is_statistical_effective_sample_size": False,
            "raw_pair_count_is_independent_sample_size": False,
            "predictor_accuracy_claim": False,
            "method_superiority_claim": False,
            "search_utility_claim": False,
            "closure_rerun_required": True,
        },
        "security": {
            "opened_basenames": [
                "SHA256SUMS",
                "summary.json",
                "provisional_first960_runs.jsonl",
                "intake_registry.jsonl",
                "source_provenance.json",
                "eligible_structural_pairs.jsonl",
            ],
            "eligible_blind_manifest_opened": False,
            "label_vault_opened": False,
            "outcome_grade_winner_orientation_opened": False,
            "score_or_prediction_values_opened": False,
            "raw_archive_or_journal_bytes_opened": False,
            "gpu_calls": 0,
            "api_calls": 0,
            "model_fits": 0,
            "base_llm_updates": 0,
        },
    }
    return result


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or not path.parent.is_dir() or path.parent.is_symlink():
        raise core.TrajectoryError("unsafe or existing output path")
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-root", required=True, type=Path)
    parser.add_argument("--expect-snapshot-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--protocol-spec", required=True, type=Path)
    parser.add_argument("--expect-protocol-spec-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = build_result(
            args.snapshot_root.resolve(),
            args.expect_snapshot_sha256,
            args.source_commit,
            args.protocol_spec.resolve(),
            args.expect_protocol_spec_sha256,
        )
        write_new(args.output.resolve(), result)
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "runs": result["current_first404"]["inventory"]["runs"],
                    "pairs": result["current_first404"]["inventory"]["structural_pairs"],
                    "claim_gates": {
                        key: value["pass"] for key, value in result["claim_gates"].items()
                    },
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    except (core.TrajectoryError, OSError, ValueError, ZeroDivisionError) as exc:
        print(f"STRUCTURAL_WEIGHT_EXTENSION_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
