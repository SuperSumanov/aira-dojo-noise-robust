#!/usr/bin/env python3
"""Independently reconstruct and verify Evidence Index v10."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any


PROTOCOL_SHA256 = "a210f17f0ded3c64b795a6d898032e04be44ae403b3585eafe527bff3e12534d"


class VerificationError(RuntimeError):
    """Raised when the candidate or one of its frozen sources drifts."""


def check(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    data = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes().decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"invalid JSON: {path}") from error
    check(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def inside(repo_root: Path, relative: str) -> Path:
    value = Path(relative)
    check(relative and not value.is_absolute() and ".." not in value.parts, f"unsafe path: {relative}")
    raw = repo_root / value
    check(not raw.is_symlink(), f"symlink input forbidden: {relative}")
    resolved = raw.resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as error:
        raise VerificationError(f"path escapes repository: {relative}") from error
    check(resolved.is_file(), f"input absent: {relative}")
    return resolved


def lookup(payload: Any, dotted: str) -> Any:
    current = payload
    for item in dotted.split("."):
        if isinstance(current, dict) and item in current:
            current = current[item]
        elif isinstance(current, list) and item.isdecimal() and int(item) < len(current):
            current = current[int(item)]
        else:
            raise VerificationError(f"assertion path absent: {dotted}")
    return current


def inspect_artifact(repo_root: Path, specification: dict[str, Any]) -> int:
    check(set(specification) == {"path", "sha256", "json_assertions"}, "artifact schema")
    path = inside(repo_root, specification["path"])
    check(path.suffix == ".json", "artifact suffix")
    check(file_sha256(path) == specification["sha256"], f"artifact digest: {specification['path']}")
    payload = json_object(path)
    assertions = specification["json_assertions"]
    check(isinstance(assertions, dict) and assertions, "artifact assertions")
    for dotted, expected in assertions.items():
        check(lookup(payload, dotted) == expected, f"artifact assertion: {dotted}")
    return len(assertions)


def inspect_source(repo_root: Path, protocol: dict[str, Any]) -> dict[str, Any]:
    rule = protocol["source_v9"]
    path = inside(repo_root, rule["path"])
    check(file_sha256(path) == rule["sha256"], "source v9 digest")
    source = json_object(path)
    check(source.get("protocol") == rule["protocol"], "source v9 protocol")
    check(source.get("status") == rule["status"], "source v9 status")
    entries = source.get("entries")
    check(isinstance(entries, list) and len(entries) == rule["entry_count"], "source entry count")
    names = [entry.get("name") for entry in entries]
    check(all(isinstance(name, str) and name for name in names), "source entry name")
    check(len(names) == len(set(names)), "source duplicate entry")
    return source


def inspect_claim_contract(protocol: dict[str, Any], source_names: set[str]) -> None:
    additions = protocol["distinct_entries"]
    reconstructions = protocol["reconstructions"]
    reporting = protocol["reporting_contract"]
    check(len(additions) == reporting["distinct_entries_added"], "distinct count")
    check(len(reconstructions) == reporting["reconstruction_records_added"], "reconstruction count")
    entry_keys = {
        "name",
        "evidence_class",
        "counts_as_distinct_claim_evidence",
        "claim_signature",
        "claim_components",
        "estimand",
        "supported_claim",
        "does_not_prove",
        "artifacts",
    }
    names: set[str] = set()
    signatures: set[str] = set()
    components: dict[str, dict[str, Any]] = {}
    artifact_paths: set[str] = set()
    for entry in additions:
        check(set(entry) == entry_keys, "distinct entry schema")
        name = entry["name"]
        check(isinstance(name, str) and name and name not in source_names and name not in names, "distinct entry name")
        check(entry["counts_as_distinct_claim_evidence"] is True, "distinct count flag")
        signature = entry["claim_signature"]
        check(isinstance(signature, dict) and signature, "claim signature")
        digest = canonical_digest(signature)
        check(digest not in signatures, "duplicate distinct claim signature")
        signatures.add(digest)
        check(isinstance(entry["claim_components"], dict), "claim components")
        components[name] = entry["claim_components"]
        check(isinstance(entry["artifacts"], list) and entry["artifacts"], "distinct artifacts")
        for artifact in entry["artifacts"]:
            path = artifact.get("path")
            check(path not in artifact_paths, "artifact reuse")
            artifact_paths.add(path)
        names.add(name)

    reconstruction_keys = {
        "name",
        "evidence_class",
        "counts_as_distinct_claim_evidence",
        "reproduction_of",
        "shared_component_name",
        "shared_component_signature",
        "incremental_descriptive_component",
        "supported_claim",
        "does_not_prove",
        "artifacts",
    }
    reconstruction_names: set[str] = set()
    for record in reconstructions:
        check(set(record) == reconstruction_keys, "reconstruction schema")
        name = record["name"]
        check(
            isinstance(name, str)
            and name
            and name not in source_names
            and name not in names
            and name not in reconstruction_names,
            "reconstruction name",
        )
        check(record["counts_as_distinct_claim_evidence"] is False, "reconstruction counted")
        target = record["reproduction_of"]
        check(target in components, "reconstruction target")
        component_name = record["shared_component_name"]
        check(component_name in components[target], "target shared component")
        check(record["shared_component_signature"] == components[target][component_name], "shared component mismatch")
        check(
            record["incremental_descriptive_component"].get("counts_as_independent_confirmation") is False,
            "incremental confirmation flag",
        )
        check(isinstance(record["artifacts"], list) and record["artifacts"], "reconstruction artifacts")
        for artifact in record["artifacts"]:
            path = artifact.get("path")
            check(path not in artifact_paths, "artifact reuse")
            artifact_paths.add(path)
        reconstruction_names.add(name)

    check(reporting["source_v9_entries_must_be_preserved_without_modification"] is True, "source preservation gate")
    check(reporting["reconstruction_records_must_not_appear_in_distinct_entries"] is True, "reconstruction separation gate")
    check(reporting["duplicate_claim_components_require_reproduction_pointer"] is True, "duplicate pointer gate")
    check(reporting["legacy_v9_entries_retroactively_fingerprinted"] is False, "legacy fingerprint scope")
    check(reporting["source_v9_provisional_status_must_be_preserved"] is True, "status preservation gate")


def inspect_reconstruction_equivalence(
    repo_root: Path, protocol: dict[str, Any]
) -> dict[str, Any]:
    target_specification = next(
        entry
        for entry in protocol["distinct_entries"]
        if entry["name"] == "archive_granularity_retention"
    )
    reconstruction = protocol["reconstructions"][0]
    check(reconstruction["reproduction_of"] == target_specification["name"], "numeric target")
    target = json_object(inside(repo_root, target_specification["artifacts"][0]["path"]))
    rebuilt = json_object(inside(repo_root, reconstruction["artifacts"][0]["path"]))
    crosswalk = json_object(inside(repo_root, reconstruction["artifacts"][2]["path"]))
    retained = target["retained_by_archive_granular_validation"]
    floor = rebuilt["prior_supported_competition_floor"]
    summaries = floor["prior_metric_summaries"]
    check(retained["affected_competitions"] == floor["competition_count"], "shared competition count")
    for metric in ("accepted_archives", "physical_runs", "eligible_runs", "eligible_endpoints"):
        check(retained[metric] == summaries[metric]["sum"], f"shared total: {metric}")
        distribution = retained["anonymous_affected_task_distribution"][metric]
        summary = summaries[metric]
        check(distribution["minimum"] == summary["minimum"], f"shared minimum: {metric}")
        check(distribution["maximum"] == summary["maximum"], f"shared maximum: {metric}")
        check(
            Fraction(str(distribution["median"]))
            == Fraction(summary["median"]["numerator"], summary["median"]["denominator"]),
            f"shared median: {metric}",
        )
    check(
        str(retained["dominant_affected_task_eligible_run_share"])
        == summaries["eligible_runs"]["maximum_share"]["decimal_17g"],
        "shared eligible-run dominance",
    )
    check(
        str(retained["dominant_affected_task_eligible_endpoint_share"])
        == summaries["eligible_endpoints"]["maximum_share"]["decimal_17g"],
        "shared endpoint dominance",
    )
    check(
        crosswalk["classification"]
        == "PRIOR_EVIDENCE_OMISSION_CORRECTED_INDEPENDENT_RECONSTRUCTION",
        "crosswalk classification",
    )
    check(
        crosswalk["incremental_descriptive_fields"]["independent_scientific_confirmation"]
        is False,
        "crosswalk confirmation boundary",
    )
    return {
        "target_entry": target_specification["name"],
        "reconstruction_record": reconstruction["name"],
        "shared_numeric_fields_exact": 19,
        "counts_as_distinct_claim_evidence": False,
        "incremental_descriptive_component_is_independent_confirmation": False,
    }


def expected_candidate(repo_root: Path, protocol_path: Path, protocol: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    assertion_counts: dict[str, int] = {}
    artifact_counts: dict[str, int] = {}
    additions: list[dict[str, Any]] = []
    for specification in protocol["distinct_entries"]:
        entry = copy.deepcopy(specification)
        count = sum(inspect_artifact(repo_root, artifact) for artifact in entry["artifacts"])
        entry["claim_signature_sha256"] = canonical_digest(entry["claim_signature"])
        entry["artifact_count"] = len(entry["artifacts"])
        entry["json_assertion_count"] = count
        assertion_counts[entry["name"]] = count
        artifact_counts[entry["name"]] = len(entry["artifacts"])
        additions.append(entry)

    reconstructions: list[dict[str, Any]] = []
    for specification in protocol["reconstructions"]:
        record = copy.deepcopy(specification)
        count = sum(inspect_artifact(repo_root, artifact) for artifact in record["artifacts"])
        record["shared_component_signature_sha256"] = canonical_digest(record["shared_component_signature"])
        record["artifact_count"] = len(record["artifacts"])
        record["json_assertion_count"] = count
        assertion_counts[record["name"]] = count
        artifact_counts[record["name"]] = len(record["artifacts"])
        reconstructions.append(record)

    equivalence = inspect_reconstruction_equivalence(repo_root, protocol)

    candidate = copy.deepcopy(source)
    candidate.update(
        {
            "protocol": "decision_corpus_evidence_index_v10",
            "status": source["status"],
            "source_v9_index": {
                "path": protocol["source_v9"]["path"],
                "sha256": protocol["source_v9"]["sha256"],
                "entry_count": len(source["entries"]),
                "entries_preserved_without_modification": len(source["entries"]),
            },
            "v10_protocol": {
                "path": protocol_path.relative_to(repo_root).as_posix(),
                "sha256": PROTOCOL_SHA256,
                "post_result_reporting_extension": True,
            },
            "v10_reporting_contract": copy.deepcopy(protocol["reporting_contract"]),
            "claim_accounting": {
                "source_distinct_entry_count": len(source["entries"]),
                "distinct_entries_added": len(additions),
                "reconstruction_records_added": len(reconstructions),
                "total_distinct_entry_count": len(source["entries"]) + len(additions),
                "duplicate_claims_counted_as_distinct": 0,
                "source_v9_status_preserved": True,
                "shared_numeric_fields_crosschecked": equivalence[
                    "shared_numeric_fields_exact"
                ],
            },
            "claim_deduplication": {
                "structured_signature_scope": "v10 additions and reconstruction records; legacy v9 entries are preserved but not retroactively fingerprinted",
                "distinct_claim_signature_sha256_by_name": {
                    entry["name"]: canonical_digest(entry["claim_signature"])
                    for entry in protocol["distinct_entries"]
                },
                "reconstruction_target_by_name": {
                    record["name"]: record["reproduction_of"] for record in reconstructions
                },
                "artifact_count_by_record": artifact_counts,
                "json_assertion_count_by_record": assertion_counts,
                "reconstruction_numeric_crosscheck": equivalence,
            },
            "v10_security": copy.deepcopy(protocol["security"]),
            "entries": copy.deepcopy(source["entries"]) + additions,
            "reconstructions": reconstructions,
        }
    )
    return candidate


def verify_candidate(repo_root: Path, protocol_path: Path, candidate_path: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    protocol_path = protocol_path.resolve()
    candidate_path = candidate_path.resolve()
    check(protocol_path.is_relative_to(repo_root), "protocol outside repository")
    check(candidate_path.is_file(), "candidate absent")
    check(file_sha256(protocol_path) == PROTOCOL_SHA256, "protocol digest")
    protocol = json_object(protocol_path)
    check(protocol.get("protocol") == "decision-corpus-evidence-index-v10-claim-dedup-protocol-v1", "protocol name")
    check(protocol.get("status") == "PUBLIC_RESULT_REPORTING_INDEX_EXTENSION_FIXED", "protocol status")
    check(
        protocol.get("security")
        == {
            "prospective_label_grade_outcome_or_prediction_values_read": False,
            "raw_senior_archives_opened": False,
            "task_run_card_code_edge_or_row_identities_emitted": False,
            "row_level_release_created": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
        "security contract",
    )
    source = inspect_source(repo_root, protocol)
    inspect_claim_contract(protocol, {entry["name"] for entry in source["entries"]})
    expected = expected_candidate(repo_root, protocol_path, protocol, source)
    candidate = json_object(candidate_path)
    check(candidate == expected, "candidate differs from independent v10 reconstruction")
    check(candidate["entries"][: len(source["entries"])] == source["entries"], "source entries changed")
    reconstruction_names = {record["name"] for record in candidate["reconstructions"]}
    check(not reconstruction_names.intersection(entry["name"] for entry in candidate["entries"]), "reconstruction in distinct entries")
    check(candidate["status"] == source["status"], "provisional status promoted")
    return {
        "protocol": "independent-decision-corpus-evidence-index-v10-verification",
        "status": "INDEPENDENT_CLAIM_DEDUPLICATED_EVIDENCE_INDEX_V10_VERIFIED",
        "index_sha256": file_sha256(candidate_path),
        "source_v9_sha256": protocol["source_v9"]["sha256"],
        "source_entries_preserved_without_modification": len(source["entries"]),
        "distinct_entries_added": len(protocol["distinct_entries"]),
        "reconstruction_records_added": len(protocol["reconstructions"]),
        "total_distinct_entry_count": len(candidate["entries"]),
        "duplicate_claims_counted_as_distinct": 0,
        "shared_numeric_fields_crosschecked": 19,
        "source_v9_status_preserved": True,
        "all_aggregate_fields_equal": True,
        "imports_builder": False,
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
    arguments = parser.parse_args()
    receipt = verify_candidate(
        arguments.repo_root, arguments.protocol, arguments.candidate
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "distinct_entries": receipt["total_distinct_entry_count"],
                "reconstructions": receipt["reconstruction_records_added"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
