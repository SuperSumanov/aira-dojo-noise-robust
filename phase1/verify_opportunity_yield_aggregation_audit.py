#!/usr/bin/env python3
"""Independently verify the outcome-blind opportunity-yield audit contract."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


PROTOCOL = "decision-opportunity-yield-aggregation-audit-v1"
STATUS = "FROZEN_OUTCOME_BLIND_BEFORE_FIRST960_CLOSURE"
EVIDENCE = {
    "decision_predictor_estimand_panel": (
        "phase1/decision_predictor_estimand_panel_v1.json",
        "4f394d0e0437992eb9d3e5f3aa56f83df86ffcbda68a752ebada4e306bf7adea",
    ),
    "structural_dependency_atlas": (
        "phase1/results/structural_dependency_atlas_7cda_20260825/atlas.json",
        "1c3e5c34afe82a236e4f242373ee7b71fd44d90207eb2d74b9177fb6776db1a5",
    ),
    "structural_weight_trajectory": (
        "phase1/results/structural_weight_trajectory_7cda_20260826/trajectory.json",
        "bbdb802711bd2f300725be156c5fd228a79fa0792f8d7317674a6a0bbb419f30",
    ),
}


class OpportunityYieldAuditVerificationError(RuntimeError):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise OpportunityYieldAuditVerificationError(message)


def read_object(path: Path) -> tuple[bytes, dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise OpportunityYieldAuditVerificationError(f"unsafe or absent input: {path.name}")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OpportunityYieldAuditVerificationError(f"invalid JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise OpportunityYieldAuditVerificationError(f"non-object input: {path.name}")
    return raw, value


def verify(
    contract_path: Path,
    expected_contract_sha256: str,
    repo_root: Path,
    source_commit: str,
) -> dict[str, Any]:
    require(
        len(source_commit) == 40
        and all(character in "0123456789abcdef" for character in source_commit),
        "source commit is not a lowercase full Git SHA",
    )
    contract_raw, contract = read_object(contract_path)
    require(digest(contract_raw) == expected_contract_sha256, "contract SHA mismatch")
    require(contract.get("protocol") == PROTOCOL, "contract protocol mismatch")
    require(contract.get("status") == STATUS, "contract status mismatch")
    require(
        set(contract)
        == {
            "protocol",
            "status",
            "paper_scope",
            "evidence_bindings",
            "authority",
            "entry_gate",
            "task_weight_identity",
            "arm_audit",
            "contrast_audit",
            "inference_and_reporting",
            "related_work_boundary",
            "access_and_compute",
        },
        "contract top-level schema mismatch",
    )

    repo_root = repo_root.resolve()
    bindings = contract.get("evidence_bindings")
    require(isinstance(bindings, dict) and set(bindings) == set(EVIDENCE), "evidence set mismatch")
    evidence_values: dict[str, dict[str, Any]] = {}
    for name, (relative, expected_sha) in EVIDENCE.items():
        require(
            bindings.get(name) == {"path": relative, "sha256": expected_sha},
            f"evidence binding mismatch: {name}",
        )
        evidence_path = (repo_root / relative).resolve()
        try:
            evidence_path.relative_to(repo_root)
        except ValueError as exc:
            raise OpportunityYieldAuditVerificationError("evidence escapes repository") from exc
        evidence_raw, evidence_value = read_object(evidence_path)
        require(digest(evidence_raw) == expected_sha, f"evidence SHA mismatch: {name}")
        evidence_values[name] = evidence_value

    require(
        contract.get("authority")
        == {
            "supplementary_audit_only": True,
            "supersedes_generic_headline": False,
            "supersedes_existing_experiment_primary": False,
            "supersedes_truth_support_effect_or_inference_contract": False,
            "may_rescue_failed_primary": False,
            "ranking_flip_is_descriptive_not_a_new_primary": True,
        },
        "authority firewall mismatch",
    )
    entry = contract.get("entry_gate")
    require(
        isinstance(entry, dict)
        and entry.get("population") == "chronological first-960 eligible physical runs"
        and entry.get("independent_accrual_closure_required") is True
        and entry.get("structural_gate_required") is True
        and entry.get("all_prediction_escrow_hashes_must_verify_before_truth_access") is True
        and entry.get("exact_common_pair_support_required_for_every_compared_arm") is True
        and entry.get("arm_and_contrast_registry_frozen_before_truth_access") is True
        and entry.get(
            "every_cohort_task_requires_at_least_one_structural_and_informative_common_pair"
        )
        is True
        and entry.get("silent_pair_task_run_or_parent_drop_allowed") is False
        and entry.get("outcome_or_prediction_dependent_selection_allowed") is False,
        "entry gate mismatch",
    )
    identity = contract.get("task_weight_identity")
    require(
        isinstance(identity, dict)
        and identity.get("opportunity_yield") == "Y_t=S_t/R_t"
        and identity.get("informative_rate") == "E_t=I_t/S_t"
        and identity.get("run_share") == "p_t=R_t/sum_t R_t"
        and identity.get("structural_pair_share") == "q_t=S_t/sum_t S_t"
        and identity.get("informative_pair_share") == "r_t=I_t/sum_t I_t"
        and identity.get("structural_identity")
        == "q_t=p_t*Y_t/sum_s(p_s*Y_s)"
        and identity.get("informative_identity")
        == "r_t=q_t*E_t/sum_s(q_s*E_s)"
        and identity.get("total_variations")
        == {
            "run_to_structural": "TV_run_structural=0.5*sum_t(abs(q_t-p_t))",
            "structural_to_informative": (
                "TV_structural_informative=0.5*sum_t(abs(r_t-q_t))"
            ),
            "run_to_informative": "TV_run_informative=0.5*sum_t(abs(r_t-p_t))",
        }
        and identity.get("identity_absolute_tolerance") == 1e-12
        and identity.get("all_task_weights_yields_and_informative_rates_reported")
        is True,
        "task-weight identity mismatch",
    )
    arm = contract.get("arm_audit")
    require(
        isinstance(arm, dict)
        and arm.get("pair_weighted_metric") == "A_pair_m=sum_t(r_t*a_m_t)"
        and arm.get("structural_weighted_task_metric")
        == "A_struct_m=sum_t(q_t*a_m_t)"
        and arm.get("run_weighted_task_metric") == "A_run_m=sum_t(p_t*a_m_t)"
        and arm.get("uniform_task_metric") == "A_task_m=mean_t(a_m_t)"
        and arm.get("observed_reweighting")
        == {
            "structural_yield": "delta_yield_m=A_struct_m-A_run_m",
            "informative_filter": "delta_info_m=A_pair_m-A_struct_m",
            "total": "delta_total_m=A_pair_m-A_run_m=delta_yield_m+delta_info_m",
        }
        and arm.get("task_range") == "W_m=max_t(a_m_t)-min_t(a_m_t)"
        and arm.get("sharp_bounds")
        == {
            "structural_yield": "abs(delta_yield_m)<=W_m*TV_run_structural",
            "informative_filter": (
                "abs(delta_info_m)<=W_m*TV_structural_informative"
            ),
            "total": "abs(delta_total_m)<=W_m*TV_run_informative",
        }
        and arm.get("bound_absolute_tolerance") == 1e-12
        and arm.get("report_every_registered_arm_together") is True,
        "arm audit mismatch",
    )
    contrast = contract.get("contrast_audit")
    require(
        isinstance(contrast, dict)
        and contrast.get("pair_weighted_contrast") == "C_pair_ab=sum_t(r_t*c_ab_t)"
        and contrast.get("structural_weighted_task_contrast")
        == "C_struct_ab=sum_t(q_t*c_ab_t)"
        and contrast.get("run_weighted_task_contrast") == "C_run_ab=sum_t(p_t*c_ab_t)"
        and contrast.get("uniform_task_contrast") == "C_task_ab=mean_t(c_ab_t)"
        and contrast.get("observed_reweighting")
        == (
            "C_pair_ab-C_run_ab is decomposed exactly into "
            "(C_struct_ab-C_run_ab)+(C_pair_ab-C_struct_ab)"
        )
        and contrast.get("task_range") == "W_ab=max_t(c_ab_t)-min_t(c_ab_t)"
        and contrast.get("sharp_bounds")
        == (
            "apply W_ab times the matching run-to-structural, "
            "structural-to-informative, and run-to-informative TV to the two "
            "components and total"
        )
        and contrast.get("all_preregistered_contrasts_reported_together") is True
        and contrast.get("unregistered_post_truth_contrasts_allowed") is False,
        "contrast audit mismatch",
    )
    reporting = contract.get("inference_and_reporting")
    require(
        isinstance(reporting, dict)
        and reporting.get("decomposition_is_deterministic_descriptive") is True
        and reporting.get("new_p_value_or_confidence_interval_for_identity_or_bound") is False
        and reporting.get("generic_estimand_panel_retains_its_task_bootstrap_loto_and_run_cluster_sensitivity") is True
        and reporting.get("experiment_specific_primary_and_bootstrap_remain_authoritative") is True
        and reporting.get("no_aggregation_truth_channel_task_subgroup_or_flip_rescue") is True,
        "inference or reporting firewall mismatch",
    )
    related = contract.get("related_work_boundary")
    require(
        isinstance(related, dict)
        and related.get("general_cluster_vs_individual_weighting_is_prior_statistical_work") is True
        and "10.1111/1541-0420.00005" in related.get("informative_cluster_size_reference", "")
        and "10.1093/ije/dyac131" in related.get("estimand_reference", "")
        and set(related.get("novelty_not_claimed", []))
        == {
            "the algebra of size-biased cluster weighting",
            "the general distinction between cluster-average and unit-average estimands",
            "macro versus micro averaging in isolation",
        },
        "related-work boundary mismatch",
    )
    access = contract.get("access_and_compute")
    require(
        access
        == {
            "prospective_label_grade_outcome_or_winner_orientation_read": False,
            "prediction_values_read_or_aggregated": False,
            "accuracy_effect_or_search_utility_computed": False,
            "raw_archive_payload_read": False,
            "gpu_jobs": 0,
            "api_calls": 0,
            "new_model_fits": 0,
            "base_llm_updates": 0,
        },
        "access attestation mismatch",
    )

    panel = evidence_values["decision_predictor_estimand_panel"]
    atlas = evidence_values["structural_dependency_atlas"]
    trajectory = evidence_values["structural_weight_trajectory"]
    trajectory_tv = trajectory.get("mechanism_decomposition", {}).get(
        "run_to_pair_total_variation", {}
    )
    evidence_checks = {
        "panel_frozen_before_closure": panel.get("status") == STATUS,
        "panel_forbids_rescue": panel.get("authority", {}).get(
            "panel_metric_may_rescue_failed_experiment_primary"
        )
        is False,
        "panel_has_pair_micro_sensitivity": "pair_micro_accuracy"
        in [
            row.get("id")
            for row in panel.get("required_nonrescuing_panel", [])
            if isinstance(row, dict)
        ],
        "atlas_marks_pair_count_nonindependent": atlas.get("estimand_contract", {}).get(
            "raw_pair_count_is_an_independence_claim"
        )
        is False,
        "atlas_uses_observed_yield_without_reordering": atlas.get(
            "estimand_contract", {}
        ).get("accrual_guard_uses_observed_pair_yield_without_reordering_first960")
        is True,
        "trajectory_has_positive_run_pair_tv": trajectory_tv.get("current", 0) > 0,
        "trajectory_attributes_majority_tv_delta_to_yield": trajectory_tv.get(
            "opportunity_yield_fraction_of_positive_delta", 0
        )
        >= 0.5,
        "trajectory_forbids_accuracy_claim": trajectory.get("interpretation_contract", {}).get(
            "predictor_accuracy_claim"
        )
        is False
        and trajectory.get("interpretation_contract", {}).get("method_superiority_claim")
        is False,
    }
    require(all(evidence_checks.values()), "evidence semantics no longer support audit boundary")
    return {
        "protocol": "independent-decision-opportunity-yield-aggregation-audit-v1",
        "status": "INDEPENDENT_OPPORTUNITY_YIELD_AUDIT_CONTRACT_PASS",
        "contract_sha256": expected_contract_sha256,
        "source_commit": source_commit,
        "verifier_source_sha256": digest(Path(__file__).read_bytes()),
        "evidence_sha256": {
            name: sha for name, (_path, sha) in sorted(EVIDENCE.items())
        },
        "checks": {
            "contract_schema_exact": True,
            "evidence_paths_and_hashes_exact": True,
            "authority_firewall_exact": True,
            "closure_and_common_support_gate_exact": True,
            "weight_identity_exact": True,
            "arm_range_tv_bound_exact": True,
            "contrast_range_tv_bound_exact": True,
            "reporting_firewall_exact": True,
            "prior_work_boundary_explicit": True,
            "access_attestation_exact": True,
            **evidence_checks,
        },
        "scope_limit": "contract, hash, and authority verification only; no prospective effect evaluation",
        "access_and_compute": access,
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise OpportunityYieldAuditVerificationError("refusing to overwrite verifier output")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise OpportunityYieldAuditVerificationError("output parent is absent or unsafe")
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--expect-contract-sha256", required=True)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = verify(
            args.contract,
            args.expect_contract_sha256,
            args.repo_root,
            args.source_commit,
        )
        write_new(args.output.resolve(), receipt)
        print(json.dumps({"status": receipt["status"], "checks": len(receipt["checks"])}, sort_keys=True))
        return 0
    except (OpportunityYieldAuditVerificationError, OSError, ValueError) as exc:
        print(f"OPPORTUNITY_YIELD_AUDIT_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
