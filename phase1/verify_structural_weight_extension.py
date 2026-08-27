#!/usr/bin/env python3
"""Independent verifier for the 404-run structural-weight extension.

This module does not import the extension producer.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from phase1 import verify_structural_weight_trajectory as independent


EXPECTED_PROTOCOL = "prospective_structural_weight_extension_ad0b_v1"
EXPECTED_STATUS = "OUTCOME_BLIND_STRUCTURAL_WEIGHT_EXTENSION_READY"
EXPECTED_SNAPSHOT = "ad0b624d636cb5e89f94d8887a7abe99f7b9ef6ce77bbde7da704b0275dedb0e"
EXPECTED_PRODUCER_BASENAME = "build_structural_weight_extension.py"
EXPECTED_PROTOCOL_BASENAME = "First960_结构权重时序外延404_结果前冻结.md"
BASELINE = 240
PRIOR = 339
CURRENT = 404
MILESTONES = [120, 160, 200, 240, 260, 280, 300, 320, 339, 360, 380, 400, 404]
EXTENSION = [360, 380, 400, 404]
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


def reconstruct_claim_sections(
    runs: list[dict[str, Any]],
    records: dict[str, dict[str, Any]],
    scopes: dict[int, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]:
    base, prior, current = scopes[BASELINE], scopes[PRIOR], scopes[CURRENT]
    base_run_hhi = base["concentration"]["runs"]["hhi"]
    base_pair_hhi = base["concentration"]["structural_pairs"]["hhi"]
    current_pair_hhi = current["concentration"]["structural_pairs"]["hhi"]
    pair_delta = current_pair_hhi - base_pair_hhi
    checkpoints = []
    for count in EXTENSION:
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
    additions = runs[BASELINE:]
    drop_rows = []
    for drop in sorted({row["drop_id"] for row in additions}):
        kept = runs[:BASELINE] + [row for row in additions if row["drop_id"] != drop]
        value = independent.summarize(kept, records)
        hhi = value["concentration"]["structural_pairs"]["hhi"]
        drop_rows.append(
            {
                "drop_id": drop,
                "removed_added_runs": sum(row["drop_id"] == drop for row in additions),
                "remaining_runs": len(kept),
                "run_hhi_delta_vs_first240": value["concentration"]["runs"]["hhi"]
                - base_run_hhi,
                "pair_hhi_delta_vs_first240": hhi - base_pair_hhi,
                "attribution_fraction_of_positive_pair_hhi_delta": (
                    (current_pair_hhi - hhi) / pair_delta if pair_delta > 0 else None
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
        raise independent.VerificationError("pair-dominant task tie")
    dominant_task = dominant[0]
    task_rows = []
    for task in sorted(current["counts"]["runs"]):
        base_value = independent.summarize(
            [row for row in runs[:BASELINE] if row["task"] != task], records
        )
        current_value = independent.summarize(
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
    mechanism = independent.decompose(base, current)
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
            "pass": pair_decomp["total_delta"] > 0
            and tv_decomp["total_delta"] > 0
            and pair_decomp["opportunity_yield_fraction_of_positive_delta"] >= 0.5
            and tv_decomp["opportunity_yield_fraction_of_positive_delta"] >= 0.5,
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
    sensitivity = {
        "warning": (
            "provisional chronological ranks can change after late arrival; old and reconstructed "
            "first339 are not asserted byte-identical"
        ),
        "old_public_first339": PRIOR_PUBLIC,
        "reconstructed_first339": independent.compact(prior),
        "old_minus_reconstructed_first339": {
            "run_hhi": PRIOR_PUBLIC["run_hhi"] - prior["concentration"]["runs"]["hhi"],
            "pair_hhi": PRIOR_PUBLIC["pair_hhi"]
            - prior["concentration"]["structural_pairs"]["hhi"],
            "pair_maximum_share": PRIOR_PUBLIC["pair_maximum_share"]
            - prior["concentration"]["structural_pairs"]["maximum_share"],
        },
    }
    return drop_rows, task_rows, mechanism, gates, sensitivity


def verify(
    snapshot_root: Path,
    artifact_path: Path,
    expected_artifact_sha256: str,
    producer_source: Path,
    expected_producer_source_sha256: str,
    expected_source_commit: str,
    protocol_spec: Path,
    expected_protocol_spec_sha256: str,
) -> dict[str, Any]:
    artifact = json.loads(independent.file_bytes(artifact_path, expected_artifact_sha256))
    expected_top_level = {
        "protocol",
        "status",
        "snapshot_sha256",
        "known_before_protocol_freeze",
        "inputs",
        "reproducibility",
        "full_prefix_trajectory",
        "milestones",
        "baseline_first240",
        "reconstructed_first339",
        "current_first404",
        "current_task_yield_table",
        "mechanism_decomposition",
        "leave_one_added_drop_out",
        "leave_one_task_out",
        "claim_gates",
        "version_sensitivity",
        "interpretation_contract",
        "security",
    }
    if not isinstance(artifact, dict) or set(artifact) != expected_top_level:
        raise independent.VerificationError("artifact top-level schema mismatch")
    if artifact.get("protocol") != EXPECTED_PROTOCOL or artifact.get("status") != EXPECTED_STATUS:
        raise independent.VerificationError("artifact protocol or status mismatch")
    if artifact.get("snapshot_sha256") != EXPECTED_SNAPSHOT:
        raise independent.VerificationError("artifact is not bound to preregistered ad0b snapshot")
    if producer_source.name != EXPECTED_PRODUCER_BASENAME:
        raise independent.VerificationError("unexpected producer source basename")
    if protocol_spec.name != EXPECTED_PROTOCOL_BASENAME:
        raise independent.VerificationError("unexpected protocol specification basename")
    if not independent.is_hash(expected_source_commit, 40):
        raise independent.VerificationError("expected source commit is not a full Git SHA")
    independent.file_bytes(producer_source, expected_producer_source_sha256)
    independent.file_bytes(protocol_spec, expected_protocol_spec_sha256)
    if artifact.get("reproducibility", {}).get("source_sha256") != expected_producer_source_sha256:
        raise independent.VerificationError("producer binding mismatch")
    if artifact.get("inputs", {}).get("protocol_spec_sha256") != expected_protocol_spec_sha256:
        raise independent.VerificationError("protocol binding mismatch")
    reproducibility = artifact.get("reproducibility")
    expected_reproducibility = {
        "source_commit": expected_source_commit,
        "source_sha256": expected_producer_source_sha256,
        "randomness_used": False,
        "baseline_runs": BASELINE,
        "prior_endpoint_runs": PRIOR,
        "current_runs": CURRENT,
        "milestones": MILESTONES,
        "extension_checkpoints": EXTENSION,
    }
    if not isinstance(reproducibility, dict) or set(reproducibility) != {
        *expected_reproducibility,
        "python_version",
    }:
        raise independent.VerificationError("reproducibility schema mismatch")
    if not isinstance(reproducibility.get("python_version"), str) or not reproducibility[
        "python_version"
    ]:
        raise independent.VerificationError("python version receipt is invalid")
    for key, expected in expected_reproducibility.items():
        independent.assert_close(expected, reproducibility.get(key), f"reproducibility.{key}")
    expected_known = {
        "current_inventory_known": KNOWN_CURRENT_INVENTORY,
        "current_dominant_pair_task_share_known": KNOWN_CURRENT_DOMINANT_PAIR_TASK_SHARE,
        "prior_public_result_known": PRIOR_PUBLIC,
        "current_hhi_trajectory_decomposition_and_deletions_known": False,
        "analysis_is_descriptive_not_a_predictor_effect_test": True,
    }
    independent.assert_close(
        expected_known,
        artifact.get("known_before_protocol_freeze"),
        "known_before_protocol_freeze",
    )
    runs, records = independent.inspect_inputs(snapshot_root, artifact, expected_runs=CURRENT)
    scopes = {
        index: independent.summarize(runs[:index], records)
        for index in range(1, CURRENT + 1)
    }
    expected_trajectory = [
        {"prefix_runs": index, **independent.compact(scopes[index])}
        for index in range(1, CURRENT + 1)
    ]
    expected_milestones = [
        {"prefix_runs": index, **independent.compact(scopes[index])}
        for index in MILESTONES
    ]
    drop_rows, task_rows, mechanism, gates, sensitivity = reconstruct_claim_sections(
        runs, records, scopes
    )
    independent.assert_close(
        expected_trajectory, artifact.get("full_prefix_trajectory"), "full_prefix_trajectory"
    )
    independent.assert_close(expected_milestones, artifact.get("milestones"), "milestones")
    independent.assert_close(
        independent.compact(scopes[BASELINE]), artifact.get("baseline_first240"), "baseline_first240"
    )
    independent.assert_close(
        independent.compact(scopes[PRIOR]), artifact.get("reconstructed_first339"), "first339"
    )
    independent.assert_close(
        independent.compact(scopes[CURRENT]), artifact.get("current_first404"), "first404"
    )
    independent.assert_close(
        independent.task_yields(scopes[BASELINE], scopes[CURRENT]),
        artifact.get("current_task_yield_table"),
        "current_task_yield_table",
    )
    independent.assert_close(mechanism, artifact.get("mechanism_decomposition"), "mechanism")
    independent.assert_close(drop_rows, artifact.get("leave_one_added_drop_out"), "drop_rows")
    independent.assert_close(task_rows, artifact.get("leave_one_task_out"), "task_rows")
    independent.assert_close(gates, artifact.get("claim_gates"), "claim_gates")
    independent.assert_close(sensitivity, artifact.get("version_sensitivity"), "version_sensitivity")
    expected_security = {
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
    }
    independent.assert_close(expected_security, artifact.get("security"), "security")
    expected_interpretation = {
        "all_gates_passed": all(value["pass"] for value in gates.values()),
        "known_pair_share_declared_as_new_discovery": False,
        "provisional_rank_stability_claim": False,
        "inverse_hhi_is_statistical_effective_sample_size": False,
        "raw_pair_count_is_independent_sample_size": False,
        "predictor_accuracy_claim": False,
        "method_superiority_claim": False,
        "search_utility_claim": False,
        "closure_rerun_required": True,
    }
    independent.assert_close(
        expected_interpretation,
        artifact.get("interpretation_contract"),
        "interpretation_contract",
    )
    return {
        "protocol": "independent_prospective_structural_weight_extension_ad0b_v1",
        "status": "INDEPENDENT_STRUCTURAL_WEIGHT_EXTENSION_PASS",
        "trajectory_sha256": expected_artifact_sha256,
        "producer_source_sha256": expected_producer_source_sha256,
        "protocol_spec_sha256": expected_protocol_spec_sha256,
        "snapshot_sha256": artifact["snapshot_sha256"],
        "checks": {
            "snapshot_and_intake_hashes_reopened": True,
            "all_404_prefixes_recomputed": True,
            "all_milestones_recomputed": True,
            "task_yields_recomputed": True,
            "decompositions_recomputed": True,
            "drop_and_task_deletions_recomputed": True,
            "all_claim_gates_recomputed": True,
            "version_sensitivity_recomputed": True,
            "security_contract_exact": True,
        },
        "recomputed_key_findings": {
            "runs": len(runs),
            "pairs": scopes[CURRENT]["inventory"]["structural_pairs"],
            "claim_gates": {name: value["pass"] for name, value in gates.items()},
        },
        "security": {
            "label_outcome_prediction_or_raw_archive_opened": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or not path.parent.is_dir() or path.parent.is_symlink():
        raise independent.VerificationError("unsafe verification output path")
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-root", required=True, type=Path)
    parser.add_argument("--trajectory", required=True, type=Path)
    parser.add_argument("--expect-trajectory-sha256", required=True)
    parser.add_argument("--producer-source", required=True, type=Path)
    parser.add_argument("--expect-producer-source-sha256", required=True)
    parser.add_argument("--expect-source-commit", required=True)
    parser.add_argument("--protocol-spec", required=True, type=Path)
    parser.add_argument("--expect-protocol-spec-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = verify(
            args.snapshot_root.resolve(),
            args.trajectory.resolve(),
            args.expect_trajectory_sha256,
            args.producer_source.resolve(),
            args.expect_producer_source_sha256,
            args.expect_source_commit,
            args.protocol_spec.resolve(),
            args.expect_protocol_spec_sha256,
        )
        write_new(args.output.resolve(), result)
        print(json.dumps(result["recomputed_key_findings"], sort_keys=True, separators=(",", ":")))
        return 0
    except (independent.VerificationError, OSError, ValueError, ZeroDivisionError) as exc:
        print(f"STRUCTURAL_WEIGHT_EXTENSION_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
