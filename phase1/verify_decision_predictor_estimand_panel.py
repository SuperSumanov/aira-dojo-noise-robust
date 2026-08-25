#!/usr/bin/env python3
"""Independently verify the outcome-blind decision-predictor estimand panel."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


PROTOCOL = "decision-predictor-estimand-panel-v1"
STATUS = "FROZEN_OUTCOME_BLIND_BEFORE_FIRST960_CLOSURE"
EVIDENCE = {
    "structural_dependency_atlas": (
        "phase1/results/structural_dependency_atlas_7cda_20260825/atlas.json",
        "1c3e5c34afe82a236e4f242373ee7b71fd44d90207eb2d74b9177fb6776db1a5",
    ),
    "critic_scaling_primary_contract": (
        "phase1/critic_scaling_confirmation_contract_v1.json",
        "579771ac1b90b1022bdded1182ce5c5a17780a741dc95d82a53f5f91d577a568",
    ),
    "component_breadth_primary_contract": (
        "phase1/critic_component_breadth_future_evaluation_v1.json",
        "1596c6f2abdfdd8b8880937f41099d81db74151e491175c123e581d9b028fdad",
    ),
}


class EstimandPanelVerificationError(RuntimeError):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_object(path: Path) -> tuple[bytes, dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise EstimandPanelVerificationError(f"unsafe or absent input: {path.name}")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EstimandPanelVerificationError(f"invalid JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise EstimandPanelVerificationError(f"non-object input: {path.name}")
    return raw, value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EstimandPanelVerificationError(message)


def verify(
    contract_path: Path,
    expected_contract_sha256: str,
    repo_root: Path,
    source_commit: str,
) -> dict[str, Any]:
    if len(source_commit) != 40 or any(character not in "0123456789abcdef" for character in source_commit):
        raise EstimandPanelVerificationError("source commit is not a lowercase full Git SHA")
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
            "generic_headline",
            "required_nonrescuing_panel",
            "paired_contrast_contract",
            "inference",
            "required_support_table",
            "reporting_firewall",
            "access_and_compute",
        },
        "contract top-level schema mismatch",
    )

    repo_root = repo_root.resolve()
    bindings = contract.get("evidence_bindings")
    require(isinstance(bindings, dict) and set(bindings) == set(EVIDENCE), "evidence set mismatch")
    evidence_values: dict[str, dict[str, Any]] = {}
    for name, (relative, expected_sha) in EVIDENCE.items():
        require(bindings.get(name) == {"path": relative, "sha256": expected_sha}, f"binding mismatch: {name}")
        path = (repo_root / relative).resolve()
        try:
            path.relative_to(repo_root)
        except ValueError as exc:
            raise EstimandPanelVerificationError("evidence escapes repository") from exc
        raw, value = read_object(path)
        require(digest(raw) == expected_sha, f"evidence SHA mismatch: {name}")
        evidence_values[name] = value

    authority = contract.get("authority")
    require(
        authority
        == {
            "generic_reporting_panel_only": True,
            "supersedes_existing_experiment_primary": False,
            "supersedes_existing_truth_contract": False,
            "supersedes_existing_support_or_effect_gate": False,
            "existing_experiment_contract_controls_its_claim": True,
            "panel_metric_may_rescue_failed_experiment_primary": False,
        },
        "authority firewall mismatch",
    )
    headline = contract.get("generic_headline")
    require(isinstance(headline, dict), "generic headline missing")
    require(
        headline.get("id") == "task_macro_parent_macro_pair_accuracy"
        and headline.get("aggregation_order")
        == [
            "compute tie-aware credit for each informative canonical sibling pair",
            "average pair credits within each physical decision parent",
            "average contributing parent metrics within each task",
            "average task metrics with equal task weight",
        ]
        and headline.get("physical_run_role")
        == "identity and dependence cluster; not an implicit pair-frequency weight",
        "generic headline hierarchy mismatch",
    )
    panel = contract.get("required_nonrescuing_panel")
    require(isinstance(panel, list) and len(panel) == 3, "secondary panel size mismatch")
    require(
        [row.get("id") for row in panel]
        == [
            "task_macro_pair_macro_accuracy",
            "task_macro_run_macro_parent_macro_pair_accuracy",
            "pair_micro_accuracy",
        ]
        and all(row.get("may_rescue_generic_headline_or_existing_primary") is False for row in panel),
        "secondary panel identity or rescue lock mismatch",
    )
    contrast = contract.get("paired_contrast_contract")
    require(
        isinstance(contrast, dict)
        and contrast.get("same_truth_and_pair_ids_for_all_arms") is True
        and contrast.get("compute_arm_difference_at_pair_before_aggregation") is True
        and contrast.get("same_parent_run_and_task_hierarchy_for_all_arms") is True
        and contrast.get("zero_prediction_margin_credit") == 0.5
        and contrast.get("pair_iid_confidence_interval_allowed") is False,
        "paired contrast contract mismatch",
    )
    inference = contract.get("inference")
    require(
        isinstance(inference, dict)
        and inference.get("generic_headline_cluster") == "task"
        and inference.get("bootstrap_draws") == 20000
        and inference.get("bootstrap_seed") == 20260901
        and inference.get("leave_one_task_out_required") is True
        and inference.get("physical_run_clustered_sensitivity_required") is True
        and inference.get("pair_iid_interval_allowed") is False
        and inference.get("existing_experiment_specific_bootstrap_remains_authoritative_for_its_gate") is True,
        "inference lock mismatch",
    )
    firewall = contract.get("reporting_firewall")
    require(
        isinstance(firewall, dict)
        and firewall.get("every_existing_primary_reported_first_for_its_claim") is True
        and firewall.get("all_panel_rows_reported_together") is True
        and firewall.get("no_metric_selected_after_effect_values") is True
        and firewall.get("no_task_subgroup_rescue") is True
        and firewall.get("no_truth_channel_rescue") is True
        and firewall.get("no_aggregation_rescue") is True,
        "reporting firewall mismatch",
    )
    access = contract.get("access_and_compute")
    require(
        access
        == {
            "prospective_label_grade_outcome_or_winner_orientation_read": False,
            "prediction_values_read_or_aggregated": False,
            "accuracy_effect_or_search_utility_computed": False,
            "gpu_jobs": 0,
            "api_calls": 0,
            "new_model_fits": 0,
            "base_llm_updates": 0,
        },
        "access attestation mismatch",
    )

    atlas = evidence_values["structural_dependency_atlas"]
    scaling = evidence_values["critic_scaling_primary_contract"]
    breadth = evidence_values["component_breadth_primary_contract"]
    evidence_checks = {
        "atlas_forbids_pair_count_independence_claim": atlas.get("estimand_contract", {}).get(
            "raw_pair_count_is_an_independence_claim"
        )
        is False,
        "atlas_marks_inverse_hhi_descriptive": atlas.get("estimand_contract", {}).get(
            "inverse_hhi_is_descriptive_diversity_not_effective_sample_size"
        )
        is True,
        "scaling_primary_remains_task_macro": scaling.get("inference", {}).get(
            "primary_aggregation"
        )
        == "task_macro",
        "component_breadth_primary_remains_parent_macro": breadth.get("primary", {}).get(
            "paired_effect"
        )
        == "broad minus concentrated task-macro parent-macro pair accuracy",
    }
    require(all(evidence_checks.values()), "evidence semantics no longer match panel boundary")
    return {
        "protocol": "independent-decision-predictor-estimand-panel-v1",
        "status": "INDEPENDENT_ESTIMAND_PANEL_PASS",
        "contract_sha256": expected_contract_sha256,
        "source_commit": source_commit,
        "verifier_source_sha256": digest(Path(__file__).read_bytes()),
        "evidence_sha256": {name: sha for name, (_path, sha) in sorted(EVIDENCE.items())},
        "checks": {
            "contract_schema_exact": True,
            "evidence_paths_and_hashes_exact": True,
            "existing_primary_authority_preserved": True,
            "generic_headline_hierarchy_exact": True,
            "three_nonrescuing_views_exact": True,
            "paired_common_support_exact": True,
            "inference_lock_exact": True,
            "reporting_firewall_exact": True,
            "access_attestation_exact": True,
            **evidence_checks,
        },
        "scope_limit": "schema, hash, and explicit authority verification; not semantic certification or effect evaluation",
        "access_and_compute": access,
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise EstimandPanelVerificationError("refusing to overwrite verifier output")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise EstimandPanelVerificationError("output parent is absent or unsafe")
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
    except (EstimandPanelVerificationError, OSError, ValueError) as exc:
        print(f"ESTIMAND_PANEL_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
