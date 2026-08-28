#!/usr/bin/env python3
"""Independently verify the historical relation-integrity contrast receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


PROTOCOL_SHA256 = "9b647d1e25786631875114893604650c273a36051c815d976ab189602e0feb37"


class VerificationError(RuntimeError):
    """Raised when a candidate or a bound aggregate package differs."""


def check(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            value.update(block)
    return value.hexdigest()


def object_from(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"invalid JSON: {path}") from error
    check(isinstance(value, dict), f"non-object JSON: {path}")
    return value


def bounded(repo: Path, relative: str, *, directory: bool = False) -> Path:
    part = Path(relative)
    check(not part.is_absolute() and ".." not in part.parts, f"unsafe path: {relative}")
    raw = repo / part
    check(not raw.is_symlink(), f"symlink input: {relative}")
    resolved = raw.resolve()
    try:
        resolved.relative_to(repo)
    except ValueError as error:
        raise VerificationError(f"escaped repository: {relative}") from error
    check(resolved.is_dir() if directory else resolved.is_file(), f"missing input: {relative}")
    return resolved


def manifest_members(root: Path, filename: str) -> tuple[Path, dict[str, str]]:
    manifest = root / filename
    check(manifest.is_file() and not manifest.is_symlink(), "manifest absent")
    found: dict[str, str] = {}
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8-sig").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        check(match is not None, f"manifest syntax line {line_number}")
        expected_hash, raw_name = match.groups()
        name = raw_name.removeprefix("./")
        part = Path(name)
        check(name and not part.is_absolute() and ".." not in part.parts, "unsafe manifest member")
        check(name not in found and name != filename, "duplicate manifest member")
        member = root / part
        check(member.is_file() and not member.is_symlink(), f"manifest member absent: {name}")
        check(digest(member) == expected_hash, f"manifest member digest: {name}")
        found[name] = expected_hash
    actual = {
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if item.is_file() and item.name != filename
    }
    check(set(found) == actual, "manifest membership mismatch")
    return manifest, found


def exact_ratio(numerator: int, denominator: int) -> dict[str, Any]:
    check(denominator > 0 and 0 <= numerator <= denominator, "ratio domain")
    return {
        "numerator": numerator,
        "denominator": denominator,
        "decimal_17g": format(numerator / denominator, ".17g"),
    }


def inspect_bundle(
    repo: Path, label: str, rule: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    root = bounded(repo, rule["root"], directory=True)
    manifest, members = manifest_members(root, rule["manifest"])
    check(digest(manifest) == rule["manifest_sha256"], f"{label} manifest digest")
    check(members.get(rule["summary"]) == rule["summary_sha256"], f"{label} summary membership")
    check(members.get(rule["verification"]) == rule["verification_sha256"], f"{label} verifier membership")
    summary_file = root / rule["summary"]
    verifier_file = root / rule["verification"]
    check(digest(summary_file) == rule["summary_sha256"], f"{label} summary digest")
    check(digest(verifier_file) == rule["verification_sha256"], f"{label} verifier digest")
    summary = object_from(summary_file)
    verifier = object_from(verifier_file)
    check(summary.get("classification") == rule["classification"], f"{label} summary classification")
    check(verifier.get("classification") == rule["classification"], f"{label} verifier classification")
    check(verifier.get("all_aggregate_fields_equal") is True, f"{label} aggregate equality")
    check(verifier.get("producer_result_sha256") == rule["summary_sha256"], f"{label} result binding")
    check(verifier.get("imports_producer", verifier.get("producer_imported")) is False, f"{label} independence")
    metadata = {
        "root": rule["root"],
        "manifest": rule["manifest"],
        "manifest_sha256": rule["manifest_sha256"],
        "manifest_member_count": len(members),
        "summary": rule["summary"],
        "summary_sha256": rule["summary_sha256"],
        "verification": rule["verification"],
        "verification_sha256": rule["verification_sha256"],
        "classification": rule["classification"],
    }
    return summary, verifier, metadata


def construct_expected(repo: Path, protocol_path: Path, protocol: dict[str, Any]) -> dict[str, Any]:
    sources = protocol["inputs"]
    canonical, canonical_check, canonical_meta = inspect_bundle(repo, "canonical", sources["canonical_v11"])
    mixed, mixed_check, mixed_meta = inspect_bundle(repo, "mixed", sources["mixed_0819"])
    repair, repair_check, repair_meta = inspect_bundle(repo, "repair", sources["repaired_0819"])
    expected = protocol["required_aggregate_facts"]

    canonical_relations = canonical["scientific"]["global_relation_counts"]
    canonical_values = {
        "parent_present_direct": canonical_relations["parent_present_verified_direct_sibling"],
        "orphan_parent_lineage_direct": canonical_relations["lineage_verified_orphan_parent_sibling"],
        "same_run_non_sibling": canonical_relations["same_run_declared_context_non_sibling"],
        "cross_run": canonical_relations["cross_run_declared_context"],
    }
    canonical_values["all_rows"] = sum(canonical_values.values())
    for name, value in canonical_values.items():
        check(value == expected["canonical"][name], f"canonical aggregate: {name}")
    canonical_hard = canonical["scientific"]["hard_integrity_gates"]
    check(len(canonical_hard) == expected["canonical"]["hard_gates_total"], "canonical hard total")
    check(sum(value is True for value in canonical_hard.values()) == expected["canonical"]["hard_gates_passed"], "canonical hard pass")
    canonical_support = [
        (set_name, gate_name, value)
        for set_name, gates in canonical["scientific"]["support_gates"].items()
        for gate_name, value in gates.items()
    ]
    check(len(canonical_support) == expected["canonical"]["support_gates_total"], "canonical support total")
    check(
        sum(value is True for _, _, value in canonical_support) == expected["canonical"]["support_gates_passed"],
        "canonical support pass",
    )
    check(
        [f"{set_name}.{gate_name}" for set_name, gate_name, value in canonical_support if value is not True]
        == [expected["canonical"]["failed_support_gate"]],
        "canonical support failure localization",
    )

    classes = mixed["semantic_class_counts"]
    mixed_values = {
        "direct_sibling": classes["verified_direct_sibling"]["total"],
        "same_run_non_sibling": classes["same_run_declared_context_non_sibling"]["total"],
        "cross_run": classes["cross_run_declared_context"]["total"],
    }
    mixed_values["all_rows"] = sum(mixed_values.values())
    for name, value in mixed_values.items():
        check(value == expected["mixed"][name], f"mixed aggregate: {name}")
    check(mixed["inventory"]["decision_rows"] == mixed_values["all_rows"], "mixed row count")
    mixed_hard = mixed["hard_integrity_gates"]
    check(len(mixed_hard) == expected["mixed"]["hard_gates_total"], "mixed hard total")
    check(sum(value is True for value in mixed_hard.values()) == expected["mixed"]["hard_gates_passed"], "mixed hard pass")
    check(
        sorted(name for name, value in mixed_hard.items() if value is not True)
        == sorted(expected["mixed"]["failed_hard_gates"]),
        "mixed hard failure localization",
    )
    check(
        mixed["split_integrity"]["train_test_referenced_physical_run_overlap"]
        == expected["mixed"]["train_test_referenced_run_overlap"],
        "mixed run overlap",
    )

    repair_values = {
        "core_rows": repair["core_counts"]["total"],
        "quarantine_rows": repair["quarantine_counts"]["total"],
    }
    for name, value in repair_values.items():
        check(value == expected["repair"][name], f"repair aggregate: {name}")
    check(sum(repair_values.values()) == mixed_values["all_rows"], "repair exhaustiveness")
    check(repair["relation_class_counts"] == mixed["semantic_class_counts"], "repair relation certificate")
    repair_hard = repair["hard_integrity_gates"]
    check(len(repair_hard) == expected["repair"]["hard_gates_total"], "repair hard total")
    check(sum(value is True for value in repair_hard.values()) == expected["repair"]["hard_gates_passed"], "repair hard pass")
    repair_support = repair["descriptive_support_compatibility_gates"]
    check(len(repair_support) == expected["repair"]["support_gates_total"], "repair support total")
    check(sum(value is True for value in repair_support.values()) == expected["repair"]["support_gates_passed"], "repair support pass")
    check(
        repair["core_split_integrity"]["train_test_referenced_physical_run_overlap"]
        == expected["repair"]["train_test_referenced_run_overlap"],
        "repair run overlap",
    )
    check(repair["parent_partition_mismatch_total"] == expected["repair"]["parent_partition_mismatches"], "repair mismatch total")
    mismatches = repair["parent_partition_mismatch_counts"]
    check(
        mismatches["cross_run_declared_context"]["total"]
        == expected["repair"]["parent_partition_mismatches_in_cross_run"],
        "repair mismatch localization",
    )
    check(mismatches["verified_direct_sibling"]["total"] == 0, "direct mismatch")
    check(mismatches["same_run_declared_context_non_sibling"]["total"] == 0, "same-run mismatch")
    check(repair["parent_certificate_sha256"]["formal_summary"] == sources["mixed_0819"]["summary_sha256"], "repair parent summary")
    check(
        repair["parent_certificate_sha256"]["independent_verification"]
        == sources["mixed_0819"]["verification_sha256"],
        "repair parent verifier",
    )
    check(repair["input_sha256"] == mixed["input_sha256"], "repair input identity")
    check(repair["source_commit"] == mixed["source_commit"], "repair source identity")
    check(canonical_check.get("imports_producer") is False, "canonical independent check")
    check(mixed_check.get("producer_imported") is False, "mixed independent check")
    check(repair_check.get("producer_imported") is False, "repair independent check")

    canonical_direct = canonical_values["parent_present_direct"] + canonical_values["orphan_parent_lineage_direct"]
    mixed_non_direct = mixed_values["same_run_non_sibling"] + mixed_values["cross_run"]
    check(canonical_direct == canonical_values["all_rows"], "canonical direct exhaustion")
    check(mixed_non_direct == repair_values["quarantine_rows"], "quarantine identity")
    check(mixed_values["direct_sibling"] == repair_values["core_rows"], "core identity")

    facts_c = expected["canonical"]
    facts_m = expected["mixed"]
    facts_r = expected["repair"]
    return {
        "protocol": "historical-decision-relation-integrity-contrast-v1-receipt",
        "status": "POST_RESULT_AGGREGATE_RELATION_INTEGRITY_CONTRAST_COMPLETE",
        "classification": "HISTORICAL_RELATION_INTEGRITY_DIAGNOSTIC_AND_REPAIR_CONTRAST",
        "protocol_sha256": PROTOCOL_SHA256,
        "known_result_status": {
            "all_source_results_known_before_specification": True,
            "descriptive_synthesis_not_preregistration": True,
            "prospective_confirmation_claimed": False,
        },
        "source_packages": {
            "canonical_v11": canonical_meta,
            "mixed_0819": mixed_meta,
            "repaired_0819": repair_meta,
        },
        "profiles": {
            "canonical_v11": {
                "rows": canonical_values["all_rows"],
                "lineage_direct_rows": canonical_direct,
                "parent_present_direct_rows": canonical_values["parent_present_direct"],
                "orphan_parent_lineage_direct_rows": canonical_values["orphan_parent_lineage_direct"],
                "same_run_non_sibling_rows": canonical_values["same_run_non_sibling"],
                "cross_run_rows": canonical_values["cross_run"],
                "hard_integrity_gates": {"passed": facts_c["hard_gates_passed"], "total": facts_c["hard_gates_total"]},
                "support_gates": {
                    "passed": facts_c["support_gates_passed"],
                    "total": facts_c["support_gates_total"],
                    "failed": [facts_c["failed_support_gate"]],
                },
            },
            "mixed_0819_before_quarantine": {
                "rows": mixed_values["all_rows"],
                "verified_direct_sibling_rows": mixed_values["direct_sibling"],
                "same_run_non_sibling_rows": mixed_values["same_run_non_sibling"],
                "cross_run_rows": mixed_values["cross_run"],
                "hard_integrity_gates": {
                    "passed": facts_m["hard_gates_passed"],
                    "total": facts_m["hard_gates_total"],
                    "failed": facts_m["failed_hard_gates"],
                },
                "train_test_referenced_run_overlap": facts_m["train_test_referenced_run_overlap"],
            },
            "mixed_0819_after_direct_sibling_quarantine": {
                "core_rows": repair_values["core_rows"],
                "quarantine_rows": repair_values["quarantine_rows"],
                "hard_integrity_gates": {"passed": facts_r["hard_gates_passed"], "total": facts_r["hard_gates_total"]},
                "support_compatibility_gates": {
                    "passed": facts_r["support_gates_passed"],
                    "total": facts_r["support_gates_total"],
                },
                "train_test_referenced_run_overlap": facts_r["train_test_referenced_run_overlap"],
                "parent_partition_mismatches": facts_r["parent_partition_mismatches"],
                "parent_partition_mismatches_in_cross_run": facts_r["parent_partition_mismatches_in_cross_run"],
            },
        },
        "aggregate_contrasts": {
            "canonical_lineage_direct_share": exact_ratio(canonical_direct, canonical_values["all_rows"]),
            "canonical_parent_present_core_retention": exact_ratio(
                canonical_values["parent_present_direct"], canonical_values["all_rows"]
            ),
            "mixed_verified_direct_sibling_share": exact_ratio(mixed_values["direct_sibling"], mixed_values["all_rows"]),
            "mixed_non_direct_relation_share": exact_ratio(mixed_non_direct, mixed_values["all_rows"]),
            "canonical_minus_mixed_direct_relation_share": exact_ratio(mixed_non_direct, mixed_values["all_rows"]),
            "mixed_quarantine_share": exact_ratio(repair_values["quarantine_rows"], mixed_values["all_rows"]),
            "mixed_repaired_core_retention": exact_ratio(repair_values["core_rows"], mixed_values["all_rows"]),
            "referenced_run_overlap_before_after": {
                "before": facts_m["train_test_referenced_run_overlap"],
                "after": facts_r["train_test_referenced_run_overlap"],
            },
            "parent_partition_mismatch_cross_run_localization": exact_ratio(
                facts_r["parent_partition_mismatches_in_cross_run"], facts_r["parent_partition_mismatches"]
            ),
        },
        "diagnostic_receipt": {
            "canonical_hard_integrity_accepted": True,
            "canonical_all_support_gates_accepted": False,
            "canonical_failed_support_gate_preserved": facts_c["failed_support_gate"],
            "mixed_family_hard_integrity_rejected": True,
            "deterministic_direct_sibling_quarantine_certificate_passed_all_hard_gates": True,
            "deterministic_direct_sibling_quarantine_passed_all_support_compatibility_gates": True,
            "audit_stack_is_not_constant_accept_or_constant_reject_on_these_two_historical_families": True,
        },
        "claim_boundary": protocol["claim_boundary"],
        "comparability_notes": protocol["comparability_notes"],
        "scope": protocol["scope"],
    }


def verify_candidate(
    repo_root: Path,
    protocol_path: Path,
    candidate_path: Path,
    expected_protocol_sha256: str = PROTOCOL_SHA256,
) -> dict[str, Any]:
    repo = repo_root.resolve()
    protocol_file = protocol_path.resolve()
    candidate_file = candidate_path.resolve()
    check(protocol_file.is_relative_to(repo), "protocol outside repository")
    check(candidate_file.is_file() and not candidate_file.is_symlink(), "candidate absent")
    check(digest(protocol_file) == expected_protocol_sha256, "protocol digest")
    protocol = object_from(protocol_file)
    check(protocol.get("status") == "POST_RESULT_DESCRIPTIVE_SYNTHESIS_SPECIFICATION_FIXED", "protocol status")
    check(protocol.get("frozen_after_all_source_results_were_known") is True, "known-result disclosure")
    scope = protocol["scope"]
    check(scope["aggregate_only"] is True, "aggregate scope")
    check(scope["prospective_first960_or_target300_values_read"] is False, "prospective scope")
    check(scope["raw_senior_archives_opened"] is False, "archive scope")
    check(scope["row_identities_or_pair_orientations_emitted"] is False, "identity scope")
    check(scope["labels_outcomes_predictions_accuracy_or_search_utility_read"] is False, "outcome scope")
    check(scope["gpu_api_model_fit_base_update"] == [0, 0, 0, 0], "resource scope")
    expected = construct_expected(repo, protocol_file, protocol)
    candidate = object_from(candidate_file)
    check(candidate == expected, "candidate differs from independently reconstructed receipt")
    return {
        "protocol": "historical-decision-relation-integrity-contrast-independent-verification-v1",
        "status": "INDEPENDENT_HISTORICAL_RELATION_INTEGRITY_CONTRAST_VERIFIED",
        "protocol_sha256": expected_protocol_sha256,
        "candidate_sha256": digest(candidate_file),
        "all_aggregate_fields_equal": True,
        "producer_imported": False,
        "source_package_manifest_sha256": {
            name: rule["manifest_sha256"] for name, rule in protocol["inputs"].items()
        },
        "known_result_descriptive_synthesis": True,
        "prospective_values_read": False,
        "raw_senior_archives_opened": False,
        "row_level_release_created": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = verify_candidate(args.repo_root, args.protocol, args.candidate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"status": receipt["status"], "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
