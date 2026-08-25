#!/usr/bin/env python3
"""Verify the ABC crosswalk schema and bind its local evidence by SHA-256.

This verifier deliberately does not certify the human semantic assessment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any


EXPECTED_ITEM_IDS = (
    "O.i.1",
    "T.1",
    "T.2",
    "T.3",
    "T.4",
    "T.5",
    "T.6",
    "T.7",
    "T.8",
    "T.9",
    "T.10",
    "R.1",
    "R.2",
    "R.3",
    "R.4",
    "R.5",
    "R.6",
    "R.7",
    "R.8",
    "R.9",
    "R.10",
    "R.11",
    "R.12",
    "R.13",
)

EXPECTED_DOMAINS = {
    "O.i.1": "outcome_validity",
    **{f"T.{index}": "task_validity" for index in range(1, 11)},
    **{f"R.{index}": "benchmark_reporting" for index in range(1, 14)},
}

ALLOWED_STATUSES = (
    "PASS_LOCAL",
    "PARTIAL",
    "INHERITED_UPSTREAM",
    "NOT_APPLICABLE",
)

LOCKED_CONSERVATIVE_STATUSES = {
    "O.i.1": "INHERITED_UPSTREAM",
    "T.1": "PARTIAL",
    "T.6": "PARTIAL",
    "T.10": "PARTIAL",
    "R.1": "PARTIAL",
    "R.3": "PARTIAL",
    "R.10": "PARTIAL",
    "R.12": "PARTIAL",
    "R.13": "NOT_APPLICABLE",
}

HEX64 = re.compile(r"^[0-9a-f]{64}$")


class VerificationError(ValueError):
    """Raised when a crosswalk invariant is violated."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _normalized_lf_bytes(path: Path) -> bytes:
    text = path.read_bytes().decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _sha256_normalized_lf(path: Path) -> str:
    return hashlib.sha256(_normalized_lf_bytes(path)).hexdigest()


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot load JSON {path}: {exc}") from exc
    _require(isinstance(value, dict), "crosswalk root must be an object")
    return value


def _validate_path(repo_root: Path, relative: str) -> Path:
    _require(isinstance(relative, str) and relative, "evidence path must be non-empty")
    pure = PurePosixPath(relative)
    _require(not pure.is_absolute(), f"absolute evidence path forbidden: {relative}")
    _require(".." not in pure.parts, f"parent traversal forbidden: {relative}")
    _require(pure.parts and pure.parts[0] == "phase1", f"evidence outside phase1: {relative}")
    resolved = (repo_root / Path(*pure.parts)).resolve()
    phase1_root = (repo_root / "phase1").resolve()
    _require(
        resolved == phase1_root or phase1_root in resolved.parents,
        f"resolved evidence outside phase1: {relative}",
    )
    _require(resolved.is_file(), f"missing evidence file: {relative}")
    return resolved


def verify_crosswalk(repo_root: Path, crosswalk_path: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    crosswalk_path = crosswalk_path.resolve()
    crosswalk = _load_json(crosswalk_path)

    _require(
        crosswalk.get("protocol") == "agentic_benchmark_checklist_crosswalk_v1",
        "unexpected protocol",
    )
    _require(
        crosswalk.get("status")
        == "HUMAN_ASSESSMENT_WITH_HASH_BOUND_EVIDENCE_AWAITING_FIRST960",
        "unexpected crosswalk status",
    )
    source = crosswalk.get("source_checklist")
    _require(isinstance(source, dict), "source_checklist must be an object")
    _require(source.get("arxiv_id") == "2507.02825", "wrong ABC arXiv id")
    _require(source.get("revision") == "v5", "crosswalk must bind ABC paper v5")
    for key in ("paper_url", "checklist_url"):
        value = source.get(key)
        _require(isinstance(value, str) and value.startswith("https://"), f"invalid {key}")

    contract = crosswalk.get("interpretation_contract")
    _require(isinstance(contract, dict), "interpretation_contract must be an object")
    expected_contract = {
        "semantic_assessment_by_humans": True,
        "machine_verification_scope": (
            "schema_item_set_status_constraints_and_local_evidence_sha256_binding_only"
        ),
        "machine_semantic_certification": False,
        "aggregate_compliance_score_reported": False,
        "binary_pass_fail_conversion_allowed": False,
        "inherited_upstream_counts_as_local_pass": False,
        "partial_counts_as_pass": False,
        "not_applicable_counts_as_pass": False,
    }
    _require(contract == expected_contract, "interpretation contract changed")

    assessed = crosswalk.get("assessed_artifact")
    _require(isinstance(assessed, dict), "assessed_artifact must be an object")
    _require(assessed.get("confirmatory_cohort_complete") is False, "first-960 cannot be complete")
    _require(
        assessed.get("prospective_outcomes_open_allowed") is False,
        "prospective outcome opening cannot be allowed",
    )

    access = crosswalk.get("access_attestation")
    expected_access = {
        "prospective_labels_grades_outcomes_or_winner_orientation_read": False,
        "prediction_values_aggregated": False,
        "accuracy_effect_or_search_utility_computed": False,
        "gpu_or_api_calls": 0,
        "base_llm_updates": 0,
    }
    _require(access == expected_access, "access attestation changed")
    _require(tuple(crosswalk.get("allowed_statuses", ())) == ALLOWED_STATUSES, "bad statuses")

    catalog = crosswalk.get("evidence_catalog")
    _require(isinstance(catalog, dict) and catalog, "evidence_catalog must be non-empty")
    catalog_paths: set[str] = set()
    verified_hashes: dict[str, str] = {}
    for evidence_id, evidence in sorted(catalog.items()):
        _require(isinstance(evidence_id, str) and evidence_id, "bad evidence id")
        _require(isinstance(evidence, dict), f"bad evidence entry: {evidence_id}")
        relative = evidence.get("path")
        expected_hash = evidence.get("sha256_normalized_lf")
        role = evidence.get("role")
        _require(isinstance(relative, str), f"bad path for {evidence_id}")
        _require(relative not in catalog_paths, f"duplicate evidence path: {relative}")
        catalog_paths.add(relative)
        _require(isinstance(expected_hash, str) and HEX64.fullmatch(expected_hash), "bad hash")
        _require(isinstance(role, str) and role.strip(), f"missing evidence role: {evidence_id}")
        resolved = _validate_path(repo_root, relative)
        actual_hash = _sha256_normalized_lf(resolved)
        _require(actual_hash == expected_hash, f"hash mismatch for {evidence_id}: {relative}")
        verified_hashes[evidence_id] = actual_hash

    items = crosswalk.get("items")
    _require(isinstance(items, list), "items must be a list")
    item_ids = tuple(item.get("id") for item in items if isinstance(item, dict))
    _require(item_ids == EXPECTED_ITEM_IDS, "ABC item set or order changed")

    referenced_evidence: set[str] = set()
    statuses: Counter[str] = Counter()
    for item in items:
        _require(isinstance(item, dict), "every item must be an object")
        item_id = item["id"]
        status = item.get("status")
        statuses[status] += 1
        _require(item.get("domain") == EXPECTED_DOMAINS[item_id], f"bad domain: {item_id}")
        _require(status in ALLOWED_STATUSES, f"bad status: {item_id}")
        _require(
            isinstance(item.get("criterion"), str) and item["criterion"].strip(),
            f"missing criterion: {item_id}",
        )
        _require(
            isinstance(item.get("rationale"), str) and item["rationale"].strip(),
            f"missing rationale: {item_id}",
        )
        _require(
            isinstance(item.get("remaining_gap"), str) and item["remaining_gap"].strip(),
            f"missing remaining gap: {item_id}",
        )

        local_ids = item.get("local_evidence_ids")
        _require(isinstance(local_ids, list) and local_ids, f"missing local evidence: {item_id}")
        _require(len(local_ids) == len(set(local_ids)), f"duplicate local evidence: {item_id}")
        for evidence_id in local_ids:
            _require(evidence_id in catalog, f"unknown evidence {evidence_id}: {item_id}")
            referenced_evidence.add(evidence_id)

        urls = item.get("external_evidence_urls")
        _require(isinstance(urls, list), f"external evidence must be a list: {item_id}")
        for url in urls:
            _require(isinstance(url, str) and url.startswith("https://"), f"bad URL: {item_id}")

        if status == "INHERITED_UPSTREAM":
            _require(urls, f"inherited item lacks upstream reference: {item_id}")
            inherited_owners = {
                "upstream_mle_bench",
                "upstream_mle_bench_with_local_extension",
            }
            _require(
                item.get("ownership") in inherited_owners,
                f"inherited item has incompatible ownership: {item_id}",
            )
        if status == "NOT_APPLICABLE":
            _require("analogue" in item["rationale"].lower(), f"N/A lacks analogue: {item_id}")

    _require(
        referenced_evidence == set(catalog),
        f"unreferenced evidence ids: {sorted(set(catalog) - referenced_evidence)}",
    )
    _require(
        dict(statuses) == crosswalk.get("status_counts"),
        "status_counts do not match item statuses",
    )
    for item_id, expected_status in LOCKED_CONSERVATIVE_STATUSES.items():
        actual = next(item["status"] for item in items if item["id"] == item_id)
        _require(actual == expected_status, f"conservative status changed: {item_id}")

    priority_gaps = crosswalk.get("priority_gaps")
    _require(isinstance(priority_gaps, list) and len(priority_gaps) >= 4, "priority gaps missing")
    _require(all(isinstance(gap, str) and gap.strip() for gap in priority_gaps), "bad gap")

    receipt = {
        "protocol": "independent_agentic_benchmark_checklist_crosswalk_verifier_v1",
        "status": "INDEPENDENTLY_VERIFIED_SCHEMA_AND_LOCAL_EVIDENCE_BINDING",
        "crosswalk_sha256_normalized_lf": _sha256_normalized_lf(crosswalk_path),
        "evidence_catalog_sha256": _canonical_sha256(catalog),
        "verified_evidence_mapping_sha256": _canonical_sha256(verified_hashes),
        "items_verified": len(items),
        "evidence_files_verified": len(catalog),
        "status_counts": dict(statuses),
        "semantic_assessment_certified": False,
        "aggregate_compliance_score_reported": False,
        "prospective_outcomes_read": False,
        "prediction_values_aggregated": False,
        "accuracy_effect_or_search_utility_computed": False,
        "gpu_or_api_calls": 0,
        "imports_crosswalk_authoring_code": False,
    }
    return receipt


def _write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--crosswalk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = verify_crosswalk(args.repo_root, args.crosswalk)
        _write_json_exclusive(args.output, receipt)
    except (VerificationError, FileExistsError, OSError) as exc:
        print(f"VERIFICATION_FAILED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
