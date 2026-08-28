#!/usr/bin/env python3
"""Aggregate-only feasibility audit for a quarantined historical sibling core.

The fixed rule uses structural Card/run/split metadata only.  It emits counts,
dependency summaries, and irreversible fingerprints, never row identities,
pair orientation, labels, predictions, accuracy, or prospective cohort values.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
from fractions import Fraction
from pathlib import Path
from typing import Any

try:
    from phase1 import audit_senior_0819_decision_relation_taxonomy as relation
except ImportError:  # direct execution from phase1/
    import audit_senior_0819_decision_relation_taxonomy as relation


PROTOCOL = "senior-0819-verified-sibling-quarantine-v1"
STATUS = "FROZEN_AFTER_RELATION_TAXONOMY_FAILURE_BEFORE_CORE_CLOSURE_READOUT"
RECEIPT = "senior-0819-verified-sibling-quarantine-receipt-v1"
CORE = "verified_direct_sibling"
COMMIT_RE = re.compile(r"[0-9a-f]{40}")


class QuarantineAuditError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise QuarantineAuditError(message)


def load_json(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def load_protocol(path: Path, expected_sha: str) -> dict[str, Any]:
    require(relation.sha256(path) == expected_sha, "protocol SHA mismatch")
    value = load_json(path)
    require(value.get("protocol") == PROTOCOL, "protocol name mismatch")
    require(value.get("status") == STATUS, "protocol status mismatch")
    require(
        value["fixed_selection"]["core_name"] == "verified_direct_sibling_core",
        "core name drift",
    )
    require(value["fixed_selection"]["pair_orientation_used"] is False, "orientation drift")
    require(value["fixed_selection"]["row_level_release_created"] is False, "release drift")
    require(COMMIT_RE.fullmatch(value["source"]["senior_branch_commit"]) is not None, "commit")
    require(
        COMMIT_RE.fullmatch(value["source"]["published_certificate_commit"]) is not None,
        "certificate commit",
    )
    known = value["known_before_freeze"]
    for key in (
        "sibling_only_parent_partition_closure_seen",
        "sibling_only_train_test_referenced_run_overlap_seen",
        "parent_partition_mismatch_counts_by_relation_and_split_seen",
        "quarantine_exhaustiveness_and_fingerprints_seen",
    ):
        require(known[key] is False, f"repair readout seen before freeze: {key}")
    require(value["claim_boundary"]["support_counts_were_known_before_this_freeze"] is True, "support disclosure")
    return value


def load_parent_certificate(
    summary_path: Path,
    verification_path: Path,
    package_manifest_path: Path,
    protocol: dict[str, Any],
) -> dict[str, Any]:
    source = protocol["source"]
    require(
        relation.sha256(summary_path) == source["relation_taxonomy_formal_summary_sha256"],
        "parent summary SHA",
    )
    require(
        relation.sha256(verification_path)
        == source["relation_taxonomy_independent_verification_sha256"],
        "parent verification SHA",
    )
    require(
        relation.sha256(package_manifest_path) == source["published_package_manifest_sha256"],
        "parent package manifest SHA",
    )
    summary = load_json(summary_path)
    verification = load_json(verification_path)
    require(
        summary["classification"]
        == "HISTORICAL_RELATION_AWARE_DECISION_TAXONOMY_INTEGRITY_GATE_FAIL",
        "parent classification",
    )
    require(
        summary["protocol_sha256"] == source["relation_taxonomy_protocol_sha256"],
        "parent protocol",
    )
    require(verification["all_aggregate_fields_equal"] is True, "parent verification")
    require(
        verification["producer_result_sha256"]
        == source["relation_taxonomy_formal_summary_sha256"],
        "parent producer binding",
    )
    return summary


def parent_partition_matches(row: relation.DecisionRow, held_runs: set[str]) -> bool:
    expected_test = row.split == "test"
    return (row.parent_run in held_runs) == expected_test


def is_core(row: relation.DecisionRow, held_runs: set[str]) -> bool:
    return (
        row.relation == CORE
        and row.first_run == row.second_run == row.parent_run
        and parent_partition_matches(row, held_runs)
    )


def count_by_split(rows: list[relation.DecisionRow]) -> dict[str, int]:
    return {
        "total": len(rows),
        "train": sum(row.split == "train" for row in rows),
        "test": sum(row.split == "test" for row in rows),
    }


def classify(hard: dict[str, bool], support: dict[str, bool]) -> str:
    if not all(hard.values()):
        return "HISTORICAL_VERIFIED_SIBLING_CORE_QUARANTINE_INTEGRITY_GATE_FAIL"
    if all(support.values()):
        return "HISTORICAL_VERIFIED_SIBLING_CORE_QUARANTINE_FEASIBLE"
    return "HISTORICAL_VERIFIED_SIBLING_CORE_QUARANTINE_LIMITED_SUPPORT"


def audit(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol).resolve()
    protocol = load_protocol(protocol_path, args.protocol_sha256)
    paths = {
        "cards": Path(args.cards).resolve(),
        "run_split": Path(args.run_split).resolve(),
        "decision": Path(args.decision).resolve(),
    }
    observed = {name: relation.sha256(path) for name, path in paths.items()}
    for name, digest in observed.items():
        require(digest == protocol["immutable_inputs"][name]["sha256"], f"input SHA: {name}")

    parent = load_parent_certificate(
        Path(args.parent_summary).resolve(),
        Path(args.parent_verification).resolve(),
        Path(args.parent_package_manifest).resolve(),
        protocol,
    )
    all_runs, held_runs = relation.base.load_run_split(paths["run_split"], protocol)
    cards, card_inventory = relation.base.load_cards(paths["cards"], all_runs)
    rows, _diagnostics = relation.read_rows(
        paths["decision"], cards, held_runs, protocol["immutable_inputs"]["decision"]
    )

    core = [row for row in rows if is_core(row, held_runs)]
    quarantine = [row for row in rows if not is_core(row, held_runs)]
    class_counts = {
        name: count_by_split([row for row in rows if row.relation == name])
        for name in relation.CLASSES
    }
    mismatch_counts: dict[str, dict[str, int]] = {}
    for name in relation.CLASSES:
        selected = [
            row
            for row in rows
            if row.relation == name and not parent_partition_matches(row, held_runs)
        ]
        mismatch_counts[name] = count_by_split(selected)

    core_profiles: dict[str, dict[str, Any]] = {}
    core_exacts: dict[str, dict[str, Fraction]] = {}
    for split in ("train", "test"):
        selected = [row for row in core if row.split == split]
        core_profiles[split], core_exacts[split] = relation.profile(selected)
    quarantine_profile, _ = relation.profile(quarantine)
    core_integrity = relation.overlap_profile(core)

    known_classes = protocol["known_before_freeze"]["relation_class_counts_seen"]
    parent_core_profiles = {
        split: parent["split_class_profiles"][split][CORE] for split in ("train", "test")
    }
    fingerprints_match = all(
        core_profiles[split]["orientation_free_identity_fingerprint_sha256"]
        == parent_core_profiles[split]["orientation_free_identity_fingerprint_sha256"]
        for split in ("train", "test")
    )
    core_count = count_by_split(core)
    known_core = known_classes[CORE]
    mismatches_in_core = sum(not parent_partition_matches(row, held_runs) for row in core)
    total_mismatches = sum(value["total"] for value in mismatch_counts.values())
    mismatches_in_quarantine = sum(
        not parent_partition_matches(row, held_runs) for row in quarantine
    )

    hard = {
        "all_input_hashes_and_reported_counts_exact": True,
        "parent_certificate_dependencies_exact": True,
        "cards_exactly_cover_frozen_run_manifest": card_inventory["physical_runs"] == len(all_runs),
        "card_ids_unique_and_lineage_valid_within_run": True,
        "core_and_quarantine_are_exhaustive_and_disjoint": (
            len(core) + len(quarantine) == len(rows)
            and all(is_core(row, held_runs) for row in core)
            and all(not is_core(row, held_runs) for row in quarantine)
        ),
        "core_all_endpoints_are_direct_children_of_declared_parent": all(
            row.relation == CORE for row in core
        ),
        "core_all_members_share_task_and_physical_run": all(
            row.first_run == row.second_run == row.parent_run for row in core
        ),
        "core_parent_partition_matches_row_split": mismatches_in_core == 0,
        "all_parent_partition_mismatches_are_quarantined": (
            mismatches_in_quarantine == total_mismatches
        ),
        "core_train_test_unordered_pair_overlap_zero": (
            core_integrity["train_test_unordered_pair_overlap"] == 0
        ),
        "core_train_test_endpoint_overlap_zero": (
            core_integrity["train_test_endpoint_overlap"] == 0
        ),
        "core_train_test_referenced_physical_run_overlap_zero": (
            core_integrity["train_test_referenced_physical_run_overlap"] == 0
        ),
        "core_unordered_pair_duplicates_zero": (
            core_integrity["duplicate_unordered_pair_rows"] == 0
        ),
        "core_conflicting_orientations_zero": (
            core_integrity["conflicting_orientation_unordered_pairs"] == 0
        ),
        "core_split_counts_and_fingerprints_match_parent_certificate": (
            core_count == known_core and fingerprints_match
        ),
        "prior_relation_class_counts_exactly_reproduced": class_counts == known_classes,
    }

    frozen = protocol["descriptive_support_compatibility_gates"]
    test_profile = core_profiles["test"]
    test_exact = core_exacts["test"]
    support = {
        "minimum_test_pairs": test_profile["pairs"] >= frozen["minimum_test_pairs"],
        "minimum_test_tasks": test_profile["tasks"] >= frozen["minimum_test_tasks"],
        "minimum_test_physical_runs": (
            test_profile["physical_runs"] >= frozen["minimum_test_physical_runs"]
        ),
        "minimum_test_endpoints": test_profile["endpoints"] >= frozen["minimum_test_endpoints"],
        "minimum_test_components": (
            test_profile["components"] >= frozen["minimum_test_components"]
        ),
        "maximum_single_test_task_pair_share": (
            test_exact["maximum_single_task_pair_share"]
            <= relation.fraction(frozen["maximum_single_test_task_pair_share"])
        ),
        "maximum_single_test_run_pair_share": (
            test_exact["maximum_single_run_pair_share"]
            <= relation.fraction(frozen["maximum_single_test_run_pair_share"])
        ),
        "maximum_single_test_component_pair_share": (
            test_exact["maximum_single_component_pair_share"]
            <= relation.fraction(frozen["maximum_single_test_component_pair_share"])
        ),
    }

    return {
        "protocol": RECEIPT,
        "status": "HISTORICAL_VERIFIED_SIBLING_QUARANTINE_AUDIT_COMPLETE",
        "protocol_sha256": args.protocol_sha256,
        "source_commit": protocol["source"]["senior_branch_commit"],
        "input_sha256": observed,
        "parent_certificate_sha256": {
            "formal_summary": protocol["source"]["relation_taxonomy_formal_summary_sha256"],
            "independent_verification": protocol["source"][
                "relation_taxonomy_independent_verification_sha256"
            ],
        },
        "inventory": {
            "cards": card_inventory["cards"],
            "physical_runs": card_inventory["physical_runs"],
            "decision_rows": len(rows),
        },
        "core_counts": core_count,
        "quarantine_counts": count_by_split(quarantine),
        "relation_class_counts": class_counts,
        "parent_partition_mismatch_counts": mismatch_counts,
        "parent_partition_mismatch_total": total_mismatches,
        "core_split_profiles": core_profiles,
        "quarantine_profile": quarantine_profile,
        "core_split_integrity": core_integrity,
        "hard_integrity_gates": hard,
        "descriptive_support_compatibility_gates": support,
        "classification": classify(hard, support),
        "scope": {
            "historical_exploratory_dataset": True,
            "post_hoc_repair_feasibility": True,
            "support_counts_known_before_freeze": True,
            "pair_orientation_used": False,
            "model_predictions_or_accuracy_read": False,
            "search_utility_computed": False,
            "prospective_first960_or_target300_values_read": False,
            "raw_senior_archives_opened": False,
            "identities_or_row_values_emitted": False,
            "row_level_release_created": False,
            "gpu_jobs": 0,
            "api_calls": 0,
            "model_fits": 0,
            "base_llm_updates": 0,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--cards", required=True)
    parser.add_argument("--run-split", required=True)
    parser.add_argument("--decision", required=True)
    parser.add_argument("--parent-summary", required=True)
    parser.add_argument("--parent-verification", required=True)
    parser.add_argument("--parent-package-manifest", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = audit(args)
    Path(args.output).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(result["classification"])


if __name__ == "__main__":
    main()
