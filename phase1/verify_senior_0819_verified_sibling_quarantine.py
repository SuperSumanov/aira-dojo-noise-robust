#!/usr/bin/env python3
"""Independent verifier for the aggregate-only sibling quarantine audit.

This module does not import the quarantine producer.  It reuses the previously
independent Card/decision decoder and independently rebuilds selection, graph,
overlap, mismatch, support, and classification aggregates.
"""

from __future__ import annotations

import argparse
import json
import re
from fractions import Fraction
from pathlib import Path
from typing import Any

try:
    from phase1 import verify_senior_0819_decision_relation_taxonomy as independent
except ImportError:  # direct execution from phase1/
    import verify_senior_0819_decision_relation_taxonomy as independent


FROZEN_NAME = "senior-0819-verified-sibling-quarantine-v1"
FROZEN_STATUS = "FROZEN_AFTER_RELATION_TAXONOMY_FAILURE_BEFORE_CORE_CLOSURE_READOUT"
RESULT_NAME = "senior-0819-verified-sibling-quarantine-receipt-v1"
CORE = "verified_direct_sibling"
COMMIT_RE = re.compile(r"[0-9a-f]{40}")


class IndependentQuarantineError(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise IndependentQuarantineError(message)


def object_json(path: Path) -> dict[str, Any]:
    check(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(value, dict), f"JSON object required: {path}")
    return value


def frozen_protocol(path: Path, expected_sha: str) -> dict[str, Any]:
    check(independent.prior.digest(path) == expected_sha, "protocol hash")
    value = object_json(path)
    check(value.get("protocol") == FROZEN_NAME, "protocol name")
    check(value.get("status") == FROZEN_STATUS, "protocol status")
    check(value["fixed_selection"]["core_name"] == "verified_direct_sibling_core", "core")
    check(value["fixed_selection"]["pair_orientation_used"] is False, "orientation")
    check(value["fixed_selection"]["row_level_release_created"] is False, "release")
    check(COMMIT_RE.fullmatch(value["source"]["senior_branch_commit"]) is not None, "commit")
    for key in (
        "sibling_only_parent_partition_closure_seen",
        "sibling_only_train_test_referenced_run_overlap_seen",
        "parent_partition_mismatch_counts_by_relation_and_split_seen",
        "quarantine_exhaustiveness_and_fingerprints_seen",
    ):
        check(value["known_before_freeze"][key] is False, "readout disclosure")
    return value


def parent_certificate(
    summary_path: Path,
    verification_path: Path,
    package_manifest_path: Path,
    protocol: dict[str, Any],
) -> dict[str, Any]:
    source = protocol["source"]
    check(
        independent.prior.digest(summary_path)
        == source["relation_taxonomy_formal_summary_sha256"],
        "parent summary hash",
    )
    check(
        independent.prior.digest(verification_path)
        == source["relation_taxonomy_independent_verification_sha256"],
        "parent verifier hash",
    )
    check(
        independent.prior.digest(package_manifest_path)
        == source["published_package_manifest_sha256"],
        "parent package manifest hash",
    )
    summary = object_json(summary_path)
    verification = object_json(verification_path)
    check(
        summary["classification"]
        == "HISTORICAL_RELATION_AWARE_DECISION_TAXONOMY_INTEGRITY_GATE_FAIL",
        "parent classification",
    )
    check(summary["protocol_sha256"] == source["relation_taxonomy_protocol_sha256"], "parent protocol")
    check(verification["all_aggregate_fields_equal"] is True, "parent equality")
    check(
        verification["producer_result_sha256"]
        == source["relation_taxonomy_formal_summary_sha256"],
        "parent binding",
    )
    return summary


def parent_partition_ok(edge: independent.RelationEdge, held: set[str]) -> bool:
    return (edge.declared_run in held) == (edge.split == "test")


def selected_core(edge: independent.RelationEdge, held: set[str]) -> bool:
    return (
        edge.category == CORE
        and edge.high_run == edge.low_run == edge.declared_run
        and parent_partition_ok(edge, held)
    )


def split_count(edges: list[independent.RelationEdge]) -> dict[str, int]:
    return {
        "total": len(edges),
        "train": sum(edge.split == "train" for edge in edges),
        "test": sum(edge.split == "test" for edge in edges),
    }


def classification(hard: dict[str, bool], support: dict[str, bool]) -> str:
    if not all(hard.values()):
        return "HISTORICAL_VERIFIED_SIBLING_CORE_QUARANTINE_INTEGRITY_GATE_FAIL"
    if all(support.values()):
        return "HISTORICAL_VERIFIED_SIBLING_CORE_QUARANTINE_FEASIBLE"
    return "HISTORICAL_VERIFIED_SIBLING_CORE_QUARANTINE_LIMITED_SUPPORT"


def recompute(args: argparse.Namespace) -> dict[str, Any]:
    protocol = frozen_protocol(Path(args.protocol).resolve(), args.protocol_sha256)
    files = {
        "cards": Path(args.cards).resolve(),
        "run_split": Path(args.run_split).resolve(),
        "decision": Path(args.decision).resolve(),
    }
    hashes = {name: independent.prior.digest(path) for name, path in files.items()}
    for name, digest in hashes.items():
        check(digest == protocol["immutable_inputs"][name]["sha256"], f"input hash {name}")

    parent = parent_certificate(
        Path(args.parent_summary).resolve(),
        Path(args.parent_verification).resolve(),
        Path(args.parent_package_manifest).resolve(),
        protocol,
    )
    all_runs, held = independent.prior.manifest(files["run_split"], protocol)
    nodes, inventory = independent.prior.card_index(files["cards"], all_runs)
    edges, _diagnostics = independent.parse_decisions(
        files["decision"], nodes, held, protocol["immutable_inputs"]["decision"]
    )

    core = [edge for edge in edges if selected_core(edge, held)]
    quarantine = [edge for edge in edges if not selected_core(edge, held)]
    class_counts = {
        name: split_count([edge for edge in edges if edge.category == name])
        for name in independent.RELATIONS
    }
    mismatch_counts: dict[str, dict[str, int]] = {}
    for name in independent.RELATIONS:
        group = [
            edge
            for edge in edges
            if edge.category == name and not parent_partition_ok(edge, held)
        ]
        mismatch_counts[name] = split_count(group)

    profiles: dict[str, dict[str, Any]] = {}
    exacts: dict[str, dict[str, Fraction]] = {}
    for split in ("train", "test"):
        group = [edge for edge in core if edge.split == split]
        profiles[split], exacts[split] = independent.group_profile(group)
    quarantine_profile, _ = independent.group_profile(quarantine)
    separation = independent.separation(core)

    known_classes = protocol["known_before_freeze"]["relation_class_counts_seen"]
    parent_profiles = {
        split: parent["split_class_profiles"][split][CORE] for split in ("train", "test")
    }
    fingerprint_match = all(
        profiles[split]["orientation_free_identity_fingerprint_sha256"]
        == parent_profiles[split]["orientation_free_identity_fingerprint_sha256"]
        for split in ("train", "test")
    )
    core_counts = split_count(core)
    mismatch_total = sum(value["total"] for value in mismatch_counts.values())
    core_mismatches = sum(not parent_partition_ok(edge, held) for edge in core)
    quarantine_mismatches = sum(not parent_partition_ok(edge, held) for edge in quarantine)

    hard = {
        "all_input_hashes_and_reported_counts_exact": True,
        "parent_certificate_dependencies_exact": True,
        "cards_exactly_cover_frozen_run_manifest": inventory["physical_runs"] == len(all_runs),
        "card_ids_unique_and_lineage_valid_within_run": True,
        "core_and_quarantine_are_exhaustive_and_disjoint": (
            len(core) + len(quarantine) == len(edges)
            and all(selected_core(edge, held) for edge in core)
            and all(not selected_core(edge, held) for edge in quarantine)
        ),
        "core_all_endpoints_are_direct_children_of_declared_parent": all(
            edge.category == CORE for edge in core
        ),
        "core_all_members_share_task_and_physical_run": all(
            edge.high_run == edge.low_run == edge.declared_run for edge in core
        ),
        "core_parent_partition_matches_row_split": core_mismatches == 0,
        "all_parent_partition_mismatches_are_quarantined": (
            quarantine_mismatches == mismatch_total
        ),
        "core_train_test_unordered_pair_overlap_zero": (
            separation["train_test_unordered_pair_overlap"] == 0
        ),
        "core_train_test_endpoint_overlap_zero": separation["train_test_endpoint_overlap"] == 0,
        "core_train_test_referenced_physical_run_overlap_zero": (
            separation["train_test_referenced_physical_run_overlap"] == 0
        ),
        "core_unordered_pair_duplicates_zero": separation["duplicate_unordered_pair_rows"] == 0,
        "core_conflicting_orientations_zero": (
            separation["conflicting_orientation_unordered_pairs"] == 0
        ),
        "core_split_counts_and_fingerprints_match_parent_certificate": (
            core_counts == known_classes[CORE] and fingerprint_match
        ),
        "prior_relation_class_counts_exactly_reproduced": class_counts == known_classes,
    }

    limits = protocol["descriptive_support_compatibility_gates"]
    test = profiles["test"]
    test_exact = exacts["test"]
    support = {
        "minimum_test_pairs": test["pairs"] >= limits["minimum_test_pairs"],
        "minimum_test_tasks": test["tasks"] >= limits["minimum_test_tasks"],
        "minimum_test_physical_runs": test["physical_runs"] >= limits["minimum_test_physical_runs"],
        "minimum_test_endpoints": test["endpoints"] >= limits["minimum_test_endpoints"],
        "minimum_test_components": test["components"] >= limits["minimum_test_components"],
        "maximum_single_test_task_pair_share": (
            test_exact["maximum_single_task_pair_share"]
            <= independent.frozen_fraction(limits["maximum_single_test_task_pair_share"])
        ),
        "maximum_single_test_run_pair_share": (
            test_exact["maximum_single_run_pair_share"]
            <= independent.frozen_fraction(limits["maximum_single_test_run_pair_share"])
        ),
        "maximum_single_test_component_pair_share": (
            test_exact["maximum_single_component_pair_share"]
            <= independent.frozen_fraction(limits["maximum_single_test_component_pair_share"])
        ),
    }
    return {
        "protocol": RESULT_NAME,
        "status": "HISTORICAL_VERIFIED_SIBLING_QUARANTINE_AUDIT_COMPLETE",
        "protocol_sha256": args.protocol_sha256,
        "source_commit": protocol["source"]["senior_branch_commit"],
        "input_sha256": hashes,
        "parent_certificate_sha256": {
            "formal_summary": protocol["source"]["relation_taxonomy_formal_summary_sha256"],
            "independent_verification": protocol["source"][
                "relation_taxonomy_independent_verification_sha256"
            ],
        },
        "inventory": {
            "cards": inventory["cards"],
            "physical_runs": inventory["physical_runs"],
            "decision_rows": len(edges),
        },
        "core_counts": core_counts,
        "quarantine_counts": split_count(quarantine),
        "relation_class_counts": class_counts,
        "parent_partition_mismatch_counts": mismatch_counts,
        "parent_partition_mismatch_total": mismatch_total,
        "core_split_profiles": profiles,
        "quarantine_profile": quarantine_profile,
        "core_split_integrity": separation,
        "hard_integrity_gates": hard,
        "descriptive_support_compatibility_gates": support,
        "classification": classification(hard, support),
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


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--cards", required=True)
    parser.add_argument("--run-split", required=True)
    parser.add_argument("--decision", required=True)
    parser.add_argument("--parent-summary", required=True)
    parser.add_argument("--parent-verification", required=True)
    parser.add_argument("--parent-package-manifest", required=True)
    parser.add_argument("--producer-result", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = arguments()
    expected = object_json(Path(args.producer_result).resolve())
    observed = recompute(args)
    check(observed == expected, "producer and independent aggregate differ")
    receipt = {
        "protocol": "senior-0819-verified-sibling-quarantine-independent-verification-v1",
        "status": "INDEPENDENT_HISTORICAL_VERIFIED_SIBLING_QUARANTINE_VERIFIED",
        "protocol_sha256": args.protocol_sha256,
        "source_commit": expected["source_commit"],
        "producer_result_sha256": independent.prior.digest(
            Path(args.producer_result).resolve()
        ),
        "producer_imported": False,
        "all_aggregate_fields_equal": True,
        "classification": expected["classification"],
        "scope": expected["scope"],
    }
    Path(args.output).write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(receipt["classification"])


if __name__ == "__main__":
    main()
