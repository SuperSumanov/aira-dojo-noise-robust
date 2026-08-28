#!/usr/bin/env python3
"""Build an aggregate-only historical relation-integrity contrast receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


PROTOCOL_SHA256 = "9b647d1e25786631875114893604650c273a36051c815d976ab189602e0feb37"


class ContrastError(RuntimeError):
    """Raised when a frozen aggregate dependency or invariant drifts."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContrastError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContrastError(f"invalid JSON: {path}") from error
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def safe_path(repo_root: Path, relative: str, *, directory: bool = False) -> Path:
    part = Path(relative)
    require(not part.is_absolute() and ".." not in part.parts, f"unsafe path: {relative}")
    raw = repo_root / part
    require(not raw.is_symlink(), f"symlink forbidden: {relative}")
    resolved = raw.resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as error:
        raise ContrastError(f"path escapes repository: {relative}") from error
    require(resolved.is_dir() if directory else resolved.is_file(), f"missing input: {relative}")
    return resolved


def parse_manifest(root: Path, name: str) -> tuple[Path, dict[str, str]]:
    manifest = root / name
    require(manifest.is_file() and not manifest.is_symlink(), "package manifest missing")
    members: dict[str, str] = {}
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8-sig").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        require(match is not None, f"malformed manifest line {line_number}: {manifest}")
        digest, raw_name = match.groups()
        member_name = raw_name.removeprefix("./")
        part = Path(member_name)
        require(
            member_name and not part.is_absolute() and ".." not in part.parts,
            f"unsafe manifest member: {member_name}",
        )
        require(member_name not in members and member_name != name, "duplicate manifest member")
        member = root / part
        require(member.is_file() and not member.is_symlink(), f"missing manifest member: {member_name}")
        require(sha256_file(member) == digest, f"manifest member hash drift: {member_name}")
        members[member_name] = digest
    observed = {
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if item.is_file() and item.name != name
    }
    require(set(members) == observed, f"manifest membership drift: {root}")
    return manifest, members


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    require(denominator > 0 and 0 <= numerator <= denominator, "invalid ratio")
    return {
        "numerator": numerator,
        "denominator": denominator,
        "decimal_17g": format(numerator / denominator, ".17g"),
    }


def load_package(
    repo_root: Path, label: str, specification: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    root = safe_path(repo_root, specification["root"], directory=True)
    manifest, members = parse_manifest(root, specification["manifest"])
    require(sha256_file(manifest) == specification["manifest_sha256"], f"{label} manifest SHA drift")
    summary_name = specification["summary"]
    verification_name = specification["verification"]
    require(members.get(summary_name) == specification["summary_sha256"], f"{label} summary binding")
    require(
        members.get(verification_name) == specification["verification_sha256"],
        f"{label} verification binding",
    )
    summary_path = root / summary_name
    verification_path = root / verification_name
    require(sha256_file(summary_path) == specification["summary_sha256"], f"{label} summary SHA drift")
    require(
        sha256_file(verification_path) == specification["verification_sha256"],
        f"{label} verification SHA drift",
    )
    summary = read_json(summary_path)
    verification = read_json(verification_path)
    require(summary.get("classification") == specification["classification"], f"{label} classification")
    require(
        verification.get("classification") == specification["classification"],
        f"{label} verifier classification",
    )
    require(verification.get("all_aggregate_fields_equal") is True, f"{label} aggregate verification")
    require(
        verification.get("producer_result_sha256") == specification["summary_sha256"],
        f"{label} verifier producer binding",
    )
    independence = verification.get("imports_producer", verification.get("producer_imported"))
    require(independence is False, f"{label} verifier independence")
    metadata = {
        "root": specification["root"],
        "manifest": specification["manifest"],
        "manifest_sha256": specification["manifest_sha256"],
        "manifest_member_count": len(members),
        "summary": summary_name,
        "summary_sha256": specification["summary_sha256"],
        "verification": verification_name,
        "verification_sha256": specification["verification_sha256"],
        "classification": specification["classification"],
    }
    return summary, verification, metadata


def validate_canonical(summary: dict[str, Any], expected: dict[str, Any]) -> dict[str, int]:
    scientific = summary["scientific"]
    relations = scientific["global_relation_counts"]
    observed = {
        "parent_present_direct": relations["parent_present_verified_direct_sibling"],
        "orphan_parent_lineage_direct": relations["lineage_verified_orphan_parent_sibling"],
        "same_run_non_sibling": relations["same_run_declared_context_non_sibling"],
        "cross_run": relations["cross_run_declared_context"],
    }
    observed["all_rows"] = sum(observed.values())
    for key, value in observed.items():
        require(value == expected[key], f"canonical count drift: {key}")
    hard = scientific["hard_integrity_gates"]
    require(len(hard) == expected["hard_gates_total"], "canonical hard-gate total")
    require(sum(value is True for value in hard.values()) == expected["hard_gates_passed"], "canonical hard gates")
    support = [
        (set_name, gate_name, value)
        for set_name, gates in scientific["support_gates"].items()
        for gate_name, value in gates.items()
    ]
    require(len(support) == expected["support_gates_total"], "canonical support-gate total")
    require(
        sum(value is True for _, _, value in support) == expected["support_gates_passed"],
        "canonical support-gate passes",
    )
    failed = [f"{set_name}.{gate_name}" for set_name, gate_name, value in support if value is not True]
    require(failed == [expected["failed_support_gate"]], "canonical failed support gate")
    return observed


def validate_mixed(summary: dict[str, Any], expected: dict[str, Any]) -> dict[str, int]:
    classes = summary["semantic_class_counts"]
    observed = {
        "direct_sibling": classes["verified_direct_sibling"]["total"],
        "same_run_non_sibling": classes["same_run_declared_context_non_sibling"]["total"],
        "cross_run": classes["cross_run_declared_context"]["total"],
    }
    observed["all_rows"] = sum(observed.values())
    for key, value in observed.items():
        require(value == expected[key], f"mixed count drift: {key}")
    require(summary["inventory"]["decision_rows"] == expected["all_rows"], "mixed inventory count")
    gates = summary["hard_integrity_gates"]
    require(len(gates) == expected["hard_gates_total"], "mixed hard-gate total")
    require(sum(value is True for value in gates.values()) == expected["hard_gates_passed"], "mixed hard gates")
    failed = sorted(name for name, value in gates.items() if value is not True)
    require(failed == sorted(expected["failed_hard_gates"]), "mixed failed hard gates")
    require(
        summary["split_integrity"]["train_test_referenced_physical_run_overlap"]
        == expected["train_test_referenced_run_overlap"],
        "mixed referenced-run overlap",
    )
    return observed


def validate_repair(
    summary: dict[str, Any], expected: dict[str, Any], mixed_summary: dict[str, Any]
) -> dict[str, int]:
    observed = {
        "core_rows": summary["core_counts"]["total"],
        "quarantine_rows": summary["quarantine_counts"]["total"],
    }
    require(observed["core_rows"] + observed["quarantine_rows"] == mixed_summary["inventory"]["decision_rows"], "repair exhaustiveness")
    for key, value in observed.items():
        require(value == expected[key], f"repair count drift: {key}")
    require(summary["relation_class_counts"] == mixed_summary["semantic_class_counts"], "repair relation binding")
    hard = summary["hard_integrity_gates"]
    require(len(hard) == expected["hard_gates_total"], "repair hard-gate total")
    require(sum(value is True for value in hard.values()) == expected["hard_gates_passed"], "repair hard gates")
    support = summary["descriptive_support_compatibility_gates"]
    require(len(support) == expected["support_gates_total"], "repair support-gate total")
    require(sum(value is True for value in support.values()) == expected["support_gates_passed"], "repair support gates")
    require(
        summary["core_split_integrity"]["train_test_referenced_physical_run_overlap"]
        == expected["train_test_referenced_run_overlap"],
        "repair referenced-run overlap",
    )
    require(summary["parent_partition_mismatch_total"] == expected["parent_partition_mismatches"], "repair mismatch total")
    mismatch = summary["parent_partition_mismatch_counts"]
    require(
        mismatch["cross_run_declared_context"]["total"]
        == expected["parent_partition_mismatches_in_cross_run"],
        "repair mismatch localization",
    )
    require(mismatch["verified_direct_sibling"]["total"] == 0, "direct sibling mismatch")
    require(mismatch["same_run_declared_context_non_sibling"]["total"] == 0, "same-run mismatch")
    return observed


def build_contrast(
    repo_root: Path, protocol_path: Path, expected_protocol_sha256: str = PROTOCOL_SHA256
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    protocol_path = protocol_path.resolve()
    require(protocol_path.is_relative_to(repo_root), "protocol outside repository")
    require(sha256_file(protocol_path) == expected_protocol_sha256, "protocol SHA drift")
    protocol = read_json(protocol_path)
    require(protocol.get("status") == "POST_RESULT_DESCRIPTIVE_SYNTHESIS_SPECIFICATION_FIXED", "protocol status")
    require(protocol.get("frozen_after_all_source_results_were_known") is True, "known-result disclosure")
    scope = protocol["scope"]
    require(scope["aggregate_only"] is True, "aggregate-only boundary")
    require(scope["prospective_first960_or_target300_values_read"] is False, "prospective values boundary")
    require(scope["raw_senior_archives_opened"] is False, "raw archive boundary")
    require(scope["row_identities_or_pair_orientations_emitted"] is False, "row identity boundary")
    require(scope["labels_outcomes_predictions_accuracy_or_search_utility_read"] is False, "outcome boundary")
    require(scope["gpu_api_model_fit_base_update"] == [0, 0, 0, 0], "resource boundary")

    canonical, canonical_verification, canonical_meta = load_package(repo_root, "canonical", protocol["inputs"]["canonical_v11"])
    mixed, mixed_verification, mixed_meta = load_package(repo_root, "mixed", protocol["inputs"]["mixed_0819"])
    repaired, repair_verification, repair_meta = load_package(repo_root, "repair", protocol["inputs"]["repaired_0819"])
    facts = protocol["required_aggregate_facts"]
    canonical_counts = validate_canonical(canonical, facts["canonical"])
    mixed_counts = validate_mixed(mixed, facts["mixed"])
    repair_counts = validate_repair(repaired, facts["repair"], mixed)
    require(
        repaired["parent_certificate_sha256"]["formal_summary"] == protocol["inputs"]["mixed_0819"]["summary_sha256"],
        "repair-to-taxonomy summary binding",
    )
    require(
        repaired["parent_certificate_sha256"]["independent_verification"]
        == protocol["inputs"]["mixed_0819"]["verification_sha256"],
        "repair-to-taxonomy verifier binding",
    )
    require(repaired["input_sha256"] == mixed["input_sha256"], "repair input identity")
    require(repaired["source_commit"] == mixed["source_commit"], "repair source commit")
    require(canonical_verification.get("imports_producer") is False, "canonical verifier independence")
    require(mixed_verification.get("producer_imported") is False, "mixed verifier independence")
    require(repair_verification.get("producer_imported") is False, "repair verifier independence")

    canonical_direct = canonical_counts["parent_present_direct"] + canonical_counts["orphan_parent_lineage_direct"]
    mixed_non_direct = mixed_counts["same_run_non_sibling"] + mixed_counts["cross_run"]
    require(canonical_direct == canonical_counts["all_rows"], "canonical direct relation exhaustion")
    require(mixed_non_direct == repair_counts["quarantine_rows"], "mixed contamination/quarantine identity")
    require(mixed_counts["direct_sibling"] == repair_counts["core_rows"], "mixed direct/core identity")

    return {
        "protocol": "historical-decision-relation-integrity-contrast-v1-receipt",
        "status": "POST_RESULT_AGGREGATE_RELATION_INTEGRITY_CONTRAST_COMPLETE",
        "classification": "HISTORICAL_RELATION_INTEGRITY_DIAGNOSTIC_AND_REPAIR_CONTRAST",
        "protocol_sha256": expected_protocol_sha256,
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
                "rows": canonical_counts["all_rows"],
                "lineage_direct_rows": canonical_direct,
                "parent_present_direct_rows": canonical_counts["parent_present_direct"],
                "orphan_parent_lineage_direct_rows": canonical_counts["orphan_parent_lineage_direct"],
                "same_run_non_sibling_rows": canonical_counts["same_run_non_sibling"],
                "cross_run_rows": canonical_counts["cross_run"],
                "hard_integrity_gates": {
                    "passed": facts["canonical"]["hard_gates_passed"],
                    "total": facts["canonical"]["hard_gates_total"],
                },
                "support_gates": {
                    "passed": facts["canonical"]["support_gates_passed"],
                    "total": facts["canonical"]["support_gates_total"],
                    "failed": [facts["canonical"]["failed_support_gate"]],
                },
            },
            "mixed_0819_before_quarantine": {
                "rows": mixed_counts["all_rows"],
                "verified_direct_sibling_rows": mixed_counts["direct_sibling"],
                "same_run_non_sibling_rows": mixed_counts["same_run_non_sibling"],
                "cross_run_rows": mixed_counts["cross_run"],
                "hard_integrity_gates": {
                    "passed": facts["mixed"]["hard_gates_passed"],
                    "total": facts["mixed"]["hard_gates_total"],
                    "failed": facts["mixed"]["failed_hard_gates"],
                },
                "train_test_referenced_run_overlap": facts["mixed"]["train_test_referenced_run_overlap"],
            },
            "mixed_0819_after_direct_sibling_quarantine": {
                "core_rows": repair_counts["core_rows"],
                "quarantine_rows": repair_counts["quarantine_rows"],
                "hard_integrity_gates": {
                    "passed": facts["repair"]["hard_gates_passed"],
                    "total": facts["repair"]["hard_gates_total"],
                },
                "support_compatibility_gates": {
                    "passed": facts["repair"]["support_gates_passed"],
                    "total": facts["repair"]["support_gates_total"],
                },
                "train_test_referenced_run_overlap": facts["repair"]["train_test_referenced_run_overlap"],
                "parent_partition_mismatches": facts["repair"]["parent_partition_mismatches"],
                "parent_partition_mismatches_in_cross_run": facts["repair"]["parent_partition_mismatches_in_cross_run"],
            },
        },
        "aggregate_contrasts": {
            "canonical_lineage_direct_share": ratio(canonical_direct, canonical_counts["all_rows"]),
            "canonical_parent_present_core_retention": ratio(
                canonical_counts["parent_present_direct"], canonical_counts["all_rows"]
            ),
            "mixed_verified_direct_sibling_share": ratio(mixed_counts["direct_sibling"], mixed_counts["all_rows"]),
            "mixed_non_direct_relation_share": ratio(mixed_non_direct, mixed_counts["all_rows"]),
            "canonical_minus_mixed_direct_relation_share": ratio(mixed_non_direct, mixed_counts["all_rows"]),
            "mixed_quarantine_share": ratio(repair_counts["quarantine_rows"], mixed_counts["all_rows"]),
            "mixed_repaired_core_retention": ratio(repair_counts["core_rows"], mixed_counts["all_rows"]),
            "referenced_run_overlap_before_after": {
                "before": facts["mixed"]["train_test_referenced_run_overlap"],
                "after": facts["repair"]["train_test_referenced_run_overlap"],
            },
            "parent_partition_mismatch_cross_run_localization": ratio(
                facts["repair"]["parent_partition_mismatches_in_cross_run"],
                facts["repair"]["parent_partition_mismatches"],
            ),
        },
        "diagnostic_receipt": {
            "canonical_hard_integrity_accepted": True,
            "canonical_all_support_gates_accepted": False,
            "canonical_failed_support_gate_preserved": facts["canonical"]["failed_support_gate"],
            "mixed_family_hard_integrity_rejected": True,
            "deterministic_direct_sibling_quarantine_certificate_passed_all_hard_gates": True,
            "deterministic_direct_sibling_quarantine_passed_all_support_compatibility_gates": True,
            "audit_stack_is_not_constant_accept_or_constant_reject_on_these_two_historical_families": True,
        },
        "claim_boundary": protocol["claim_boundary"],
        "comparability_notes": protocol["comparability_notes"],
        "scope": scope,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = build_contrast(args.repo_root, args.protocol)
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
