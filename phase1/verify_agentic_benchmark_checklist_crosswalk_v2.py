#!/usr/bin/env python3
"""Independently verify the clean-provenance ABC crosswalk v2."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from phase1 import agentic_benchmark_checklist_crosswalk_v2_schema as schema


EXPECTED_DOMAINS = {
    "O.i.1": "outcome_validity",
    **{f"T.{index}": "task_validity" for index in range(1, 11)},
    **{f"R.{index}": "benchmark_reporting" for index in range(1, 14)},
}


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def normalized_lf_bytes(path: Path) -> bytes:
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise VerificationError(f"cannot read UTF-8 artifact: {path}") from error
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def normalized_sha256(path: Path) -> str:
    return hashlib.sha256(normalized_lf_bytes(path)).hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def resolve_evidence(repo_root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    require(not pure.is_absolute() and ".." not in pure.parts, "unsafe evidence path")
    require(pure.parts and pure.parts[0] == "phase1", "evidence outside phase1")
    unresolved = repo_root.joinpath(*pure.parts)
    require(not unresolved.is_symlink(), f"symlinked evidence forbidden: {relative}")
    resolved = unresolved.resolve()
    phase1_root = (repo_root / "phase1").resolve()
    require(phase1_root in resolved.parents, f"escaped evidence path: {relative}")
    require(resolved.is_file(), f"missing evidence file: {relative}")
    return resolved


def load_source(repo_root: Path) -> dict[str, Any]:
    path = resolve_evidence(repo_root, schema.SOURCE_PATH)
    require(
        normalized_sha256(path) == schema.SOURCE_SHA256_NORMALIZED_LF,
        "source v1 template hash mismatch",
    )
    source = json.loads(normalized_lf_bytes(path).decode("utf-8"))
    require(source.get("protocol") == schema.SOURCE_PROTOCOL, "bad source protocol")
    require(source.get("status") == schema.SOURCE_STATUS, "bad source status")
    require(
        tuple(item.get("id") for item in source.get("items", []))
        == schema.EXPECTED_ITEM_IDS,
        "source ABC item set or order changed",
    )
    return source


def expected_crosswalk(repo_root: Path) -> dict[str, Any]:
    source = load_source(repo_root)
    payload = copy.deepcopy(source)
    payload["protocol"] = schema.PROTOCOL
    payload["status"] = schema.STATUS
    payload["assessment_date"] = "2026-08-26"
    payload["source_v1_template"] = {
        "path": schema.SOURCE_PATH,
        "sha256_normalized_lf": schema.SOURCE_SHA256_NORMALIZED_LF,
        "used_for_human_item_text_and_conservative_statuses_only": True,
        "source_evidence_artifacts_opened": False,
        "source_access_attestation_inherited": False,
    }
    payload["provenance_repair"] = {
        "removed_evidence_ids": list(schema.REMOVED_EVIDENCE_IDS),
        "added_clean_evidence_ids": list(schema.ADDED_EVIDENCE),
        "withdrawn_artifacts_used_as_v2_evidence": False,
        "v6_or_value_reading_matrix_inherited": False,
        "human_statuses_upgraded_during_migration": False,
        "historical_files_deleted_or_overwritten": False,
    }
    payload["access_attestation"] = copy.deepcopy(schema.ACCESS_ATTESTATION)

    catalog = copy.deepcopy(source["evidence_catalog"])
    for evidence_id in schema.REMOVED_EVIDENCE_IDS:
        require(evidence_id in catalog, f"removed source evidence missing: {evidence_id}")
        del catalog[evidence_id]
    require(not set(catalog).intersection(schema.ADDED_EVIDENCE), "added evidence collision")
    catalog.update(copy.deepcopy(schema.ADDED_EVIDENCE))
    payload["evidence_catalog"] = catalog

    source_statuses = {item["id"]: item["status"] for item in source["items"]}
    for item in payload["items"]:
        ids: list[str] = []
        for evidence_id in item["local_evidence_ids"]:
            replacement = schema.EVIDENCE_ID_REPLACEMENTS.get(evidence_id, evidence_id)
            if replacement not in ids:
                ids.append(replacement)
        for evidence_id in schema.ITEM_EXTRA_EVIDENCE.get(item["id"], ()):
            if evidence_id not in ids:
                ids.append(evidence_id)
        item["local_evidence_ids"] = ids
        if item["id"] in schema.ITEM_RATIONALE_REPLACEMENTS:
            item["rationale"] = schema.ITEM_RATIONALE_REPLACEMENTS[item["id"]]
        require(item["status"] == source_statuses[item["id"]], "human status changed")
    return payload


def verify_crosswalk(repo_root: Path, crosswalk_path: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    try:
        payload = json.loads(normalized_lf_bytes(crosswalk_path.resolve()).decode("utf-8"))
    except json.JSONDecodeError as error:
        raise VerificationError("candidate crosswalk is invalid JSON") from error
    require(payload == expected_crosswalk(repo_root), "v2 differs from independent migration")

    require(payload["protocol"] == schema.PROTOCOL, "unexpected protocol")
    require(payload["status"] == schema.STATUS, "unexpected status")
    require(payload["access_attestation"] == schema.ACCESS_ATTESTATION, "bad access state")
    require(
        tuple(payload.get("allowed_statuses", ())) == schema.ALLOWED_STATUSES,
        "bad allowed statuses",
    )
    require(
        payload["assessed_artifact"]["confirmatory_cohort_complete"] is False,
        "first-960 cannot be complete",
    )
    require(
        payload["assessed_artifact"]["prospective_outcomes_open_allowed"] is False,
        "outcome opening cannot be allowed",
    )

    catalog = payload["evidence_catalog"]
    require(not set(schema.REMOVED_EVIDENCE_IDS).intersection(catalog), "removed ID remains")
    require(set(schema.ADDED_EVIDENCE).issubset(catalog), "clean evidence missing")
    seen_paths: set[str] = set()
    verified_hashes: dict[str, str] = {}
    for evidence_id, evidence in sorted(catalog.items()):
        relative = evidence["path"]
        require(relative not in seen_paths, f"duplicate evidence path: {relative}")
        seen_paths.add(relative)
        require(
            not any(
                fragment in relative
                for fragment in schema.FORBIDDEN_EVIDENCE_PATH_FRAGMENTS
            ),
            f"withdrawn evidence path used: {evidence_id}",
        )
        require(isinstance(evidence.get("role"), str) and evidence["role"].strip(), "bad role")
        resolved = resolve_evidence(repo_root, relative)
        actual = normalized_sha256(resolved)
        require(actual == evidence["sha256_normalized_lf"], f"hash mismatch: {evidence_id}")
        verified_hashes[evidence_id] = actual

    items = payload["items"]
    require(tuple(item["id"] for item in items) == schema.EXPECTED_ITEM_IDS, "item order")
    referenced: set[str] = set()
    statuses: Counter[str] = Counter()
    for item in items:
        item_id = item["id"]
        status = item["status"]
        statuses[status] += 1
        require(item["domain"] == EXPECTED_DOMAINS[item_id], f"bad domain: {item_id}")
        require(status in schema.ALLOWED_STATUSES, f"bad status: {item_id}")
        require(all(item.get(key) for key in ("criterion", "rationale", "remaining_gap")), f"bad text: {item_id}")
        ids = item["local_evidence_ids"]
        require(isinstance(ids, list) and ids, f"missing local evidence: {item_id}")
        require(len(ids) == len(set(ids)), f"duplicate evidence id: {item_id}")
        require(not set(ids).intersection(schema.REMOVED_EVIDENCE_IDS), f"removed id: {item_id}")
        for evidence_id in ids:
            require(evidence_id in catalog, f"unknown evidence: {item_id}:{evidence_id}")
            referenced.add(evidence_id)
        urls = item["external_evidence_urls"]
        require(isinstance(urls, list), f"bad external URLs: {item_id}")
        require(all(isinstance(url, str) and url.startswith("https://") for url in urls), f"bad URL: {item_id}")
        if status == "INHERITED_UPSTREAM":
            require(urls, f"inherited item lacks URL: {item_id}")
        if status == "NOT_APPLICABLE":
            require("analogue" in item["rationale"].lower(), f"N/A lacks analogue: {item_id}")

    require(referenced == set(catalog), "catalog/reference mismatch")
    require(dict(statuses) == payload["status_counts"], "status counts mismatch")
    for item_id, expected_status in schema.LOCKED_CONSERVATIVE_STATUSES.items():
        actual_status = next(item["status"] for item in items if item["id"] == item_id)
        require(actual_status == expected_status, f"conservative status changed: {item_id}")

    contract = payload["interpretation_contract"]
    require(contract["machine_semantic_certification"] is False, "semantic certification")
    require(contract["aggregate_compliance_score_reported"] is False, "aggregate score")
    require(contract["binary_pass_fail_conversion_allowed"] is False, "binary conversion")
    return {
        "protocol": "independent_agentic_benchmark_checklist_crosswalk_verifier_v2",
        "status": "INDEPENDENTLY_VERIFIED_CLEAN_PROVENANCE_ABC_CROSSWALK",
        "crosswalk_sha256_normalized_lf": normalized_sha256(crosswalk_path),
        "source_v1_template_sha256_normalized_lf": schema.SOURCE_SHA256_NORMALIZED_LF,
        "evidence_catalog_sha256": canonical_sha256(catalog),
        "verified_evidence_mapping_sha256": canonical_sha256(verified_hashes),
        "items_verified": len(items),
        "evidence_files_verified": len(catalog),
        "removed_evidence_ids": list(schema.REMOVED_EVIDENCE_IDS),
        "added_clean_evidence_ids": list(schema.ADDED_EVIDENCE),
        "status_counts": dict(statuses),
        "human_statuses_upgraded_during_migration": False,
        "semantic_assessment_certified": False,
        "aggregate_compliance_score_reported": False,
        "source_v1_template_opened": True,
        "source_v1_evidence_artifacts_opened": False,
        "withdrawn_artifacts_used_as_v2_evidence": False,
        "prediction_pair_files_opened": False,
        "prediction_values_read_or_aggregated": False,
        "prospective_outcomes_read": False,
        "accuracy_effect_or_search_utility_computed": False,
        "gpu_or_api_calls": 0,
        "imports_crosswalk_authoring_code": False,
    }


def atomic_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise VerificationError(f"output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--crosswalk", required=True)
    parser.add_argument("--out", required=True)
    arguments = parser.parse_args()
    receipt = verify_crosswalk(Path(arguments.repo_root), Path(arguments.crosswalk))
    atomic_json(Path(arguments.out).resolve(), receipt)
    print(receipt["status"])


if __name__ == "__main__":
    main()
