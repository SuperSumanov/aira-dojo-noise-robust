#!/usr/bin/env python3
"""Build Evidence Index v10 with structured claim de-duplication."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any


PROTOCOL_SHA256 = "a210f17f0ded3c64b795a6d898032e04be44ae403b3585eafe527bff3e12534d"
INDEX_PROTOCOL = "decision_corpus_evidence_index_v10"


class BuildError(RuntimeError):
    """Raised when a frozen input or claim-accounting invariant drifts."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BuildError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        text = path.read_bytes().decode("utf-8-sig")
        value = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BuildError(f"invalid JSON: {path}") from error
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def safe_path(repo_root: Path, relative: str) -> Path:
    value = Path(relative)
    require(relative and not value.is_absolute() and ".." not in value.parts, f"unsafe path: {relative}")
    raw = repo_root / value
    require(not raw.is_symlink(), f"symlink input forbidden: {relative}")
    resolved = raw.resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as error:
        raise BuildError(f"path escapes repository: {relative}") from error
    require(resolved.is_file(), f"missing input: {relative}")
    return resolved


def asserted_value(payload: Any, dotted: str) -> Any:
    current = payload
    for component in dotted.split("."):
        if isinstance(current, dict) and component in current:
            current = current[component]
        elif isinstance(current, list) and component.isdecimal() and int(component) < len(current):
            current = current[int(component)]
        else:
            raise BuildError(f"missing assertion path: {dotted}")
    return current


def verify_artifact(repo_root: Path, specification: dict[str, Any]) -> int:
    require(
        set(specification) == {"path", "sha256", "json_assertions"},
        "artifact specification schema drift",
    )
    path = safe_path(repo_root, specification["path"])
    require(path.suffix == ".json", f"artifact is not JSON: {specification['path']}")
    require(sha256_file(path) == specification["sha256"], f"artifact SHA drift: {specification['path']}")
    payload = read_json(path)
    assertions = specification["json_assertions"]
    require(isinstance(assertions, dict) and assertions, "artifact assertions missing")
    for dotted, expected in assertions.items():
        require(asserted_value(payload, dotted) == expected, f"artifact assertion mismatch: {dotted}")
    return len(assertions)


def verify_source_v9(repo_root: Path, protocol: dict[str, Any]) -> dict[str, Any]:
    frozen = protocol["source_v9"]
    source_path = safe_path(repo_root, frozen["path"])
    require(sha256_file(source_path) == frozen["sha256"], "source v9 SHA drift")
    source = read_json(source_path)
    require(source.get("protocol") == frozen["protocol"], "source v9 protocol drift")
    require(source.get("status") == frozen["status"], "source v9 status drift")
    entries = source.get("entries")
    require(isinstance(entries, list) and len(entries) == frozen["entry_count"], "source v9 entry count")
    names = [entry.get("name") for entry in entries]
    require(all(isinstance(name, str) and name for name in names), "source v9 entry name missing")
    require(len(set(names)) == len(names), "source v9 duplicate entry name")
    return source


def validate_claim_contract(protocol: dict[str, Any], source_names: set[str]) -> dict[str, Any]:
    reporting = protocol["reporting_contract"]
    additions = protocol["distinct_entries"]
    reconstructions = protocol["reconstructions"]
    require(isinstance(additions, list) and additions, "distinct entries missing")
    require(isinstance(reconstructions, list) and reconstructions, "reconstructions missing")
    require(len(additions) == reporting["distinct_entries_added"], "distinct entry count drift")
    require(len(reconstructions) == reporting["reconstruction_records_added"], "reconstruction count drift")

    required_entry_keys = {
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
    addition_names: list[str] = []
    signatures: dict[str, str] = {}
    components_by_name: dict[str, dict[str, Any]] = {}
    artifact_paths: set[str] = set()
    for entry in additions:
        require(set(entry) == required_entry_keys, "distinct entry schema drift")
        name = entry["name"]
        require(isinstance(name, str) and name, "distinct entry name missing")
        require(name not in source_names and name not in addition_names, f"duplicate entry name: {name}")
        require(entry["counts_as_distinct_claim_evidence"] is True, f"distinct entry not counted: {name}")
        signature = entry["claim_signature"]
        require(isinstance(signature, dict) and signature, f"claim signature missing: {name}")
        digest = canonical_sha256(signature)
        require(digest not in signatures, f"duplicate distinct claim signature: {name} and {signatures.get(digest)}")
        signatures[digest] = name
        components = entry["claim_components"]
        require(isinstance(components, dict), f"claim components invalid: {name}")
        components_by_name[name] = components
        artifacts = entry["artifacts"]
        require(isinstance(artifacts, list) and artifacts, f"artifacts missing: {name}")
        for artifact in artifacts:
            path = artifact.get("path")
            require(path not in artifact_paths, f"artifact reused across distinct entries: {path}")
            artifact_paths.add(path)
        addition_names.append(name)

    required_reconstruction_keys = {
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
    reconstruction_names: list[str] = []
    for record in reconstructions:
        require(set(record) == required_reconstruction_keys, "reconstruction schema drift")
        name = record["name"]
        require(
            isinstance(name, str)
            and name
            and name not in source_names
            and name not in addition_names
            and name not in reconstruction_names,
            f"duplicate reconstruction name: {name}",
        )
        require(record["counts_as_distinct_claim_evidence"] is False, "reconstruction counted as distinct")
        target = record["reproduction_of"]
        require(target in components_by_name, f"reconstruction target absent: {target}")
        component_name = record["shared_component_name"]
        require(component_name in components_by_name[target], "shared component absent from target")
        require(
            record["shared_component_signature"] == components_by_name[target][component_name],
            "shared component signature mismatch",
        )
        incremental = record["incremental_descriptive_component"]
        require(
            isinstance(incremental, dict)
            and incremental.get("counts_as_independent_confirmation") is False,
            "incremental component incorrectly claims confirmation",
        )
        artifacts = record["artifacts"]
        require(isinstance(artifacts, list) and artifacts, "reconstruction artifacts missing")
        for artifact in artifacts:
            path = artifact.get("path")
            require(path not in artifact_paths, f"artifact reused across evidence records: {path}")
            artifact_paths.add(path)
        reconstruction_names.append(name)

    require(reporting["reconstruction_records_must_not_appear_in_distinct_entries"] is True, "reporting reconstruction gate")
    require(reporting["duplicate_claim_components_require_reproduction_pointer"] is True, "reporting duplicate gate")
    require(reporting["legacy_v9_entries_retroactively_fingerprinted"] is False, "legacy fingerprint scope drift")
    require(reporting["source_v9_provisional_status_must_be_preserved"] is True, "status preservation gate")
    return {
        "addition_names": addition_names,
        "addition_signature_sha256": signatures,
        "reconstruction_names": reconstruction_names,
        "artifact_paths": artifact_paths,
    }


def verify_reconstruction_equivalence(
    repo_root: Path, protocol: dict[str, Any]
) -> dict[str, Any]:
    target_specification = next(
        entry
        for entry in protocol["distinct_entries"]
        if entry["name"] == "archive_granularity_retention"
    )
    reconstruction = protocol["reconstructions"][0]
    require(
        reconstruction["reproduction_of"] == target_specification["name"],
        "numeric reconstruction target drift",
    )
    target = read_json(safe_path(repo_root, target_specification["artifacts"][0]["path"]))
    rebuilt = read_json(safe_path(repo_root, reconstruction["artifacts"][0]["path"]))
    crosswalk = read_json(safe_path(repo_root, reconstruction["artifacts"][2]["path"]))

    retained = target["retained_by_archive_granular_validation"]
    floor = rebuilt["prior_supported_competition_floor"]
    summaries = floor["prior_metric_summaries"]
    require(retained["affected_competitions"] == floor["competition_count"], "shared competition count")
    direct_fields = {
        "accepted_archives": "accepted_archives",
        "physical_runs": "physical_runs",
        "eligible_runs": "eligible_runs",
        "eligible_endpoints": "eligible_endpoints",
    }
    for retained_name, summary_name in direct_fields.items():
        require(retained[retained_name] == summaries[summary_name]["sum"], f"shared total: {summary_name}")
        distribution = retained["anonymous_affected_task_distribution"][summary_name]
        summary = summaries[summary_name]
        require(distribution["minimum"] == summary["minimum"], f"shared minimum: {summary_name}")
        require(distribution["maximum"] == summary["maximum"], f"shared maximum: {summary_name}")
        require(
            Fraction(str(distribution["median"]))
            == Fraction(summary["median"]["numerator"], summary["median"]["denominator"]),
            f"shared median: {summary_name}",
        )
    require(
        str(retained["dominant_affected_task_eligible_run_share"])
        == summaries["eligible_runs"]["maximum_share"]["decimal_17g"],
        "shared eligible-run dominance",
    )
    require(
        str(retained["dominant_affected_task_eligible_endpoint_share"])
        == summaries["eligible_endpoints"]["maximum_share"]["decimal_17g"],
        "shared endpoint dominance",
    )
    require(
        crosswalk["classification"]
        == "PRIOR_EVIDENCE_OMISSION_CORRECTED_INDEPENDENT_RECONSTRUCTION",
        "crosswalk classification",
    )
    require(
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


def build_index(repo_root: Path, protocol_path: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    protocol_path = protocol_path.resolve()
    require(protocol_path.is_relative_to(repo_root), "protocol outside repository")
    require(sha256_file(protocol_path) == PROTOCOL_SHA256, "protocol SHA drift")
    protocol = read_json(protocol_path)
    require(protocol.get("protocol") == "decision-corpus-evidence-index-v10-claim-dedup-protocol-v1", "protocol name drift")
    require(protocol.get("status") == "PUBLIC_RESULT_REPORTING_INDEX_EXTENSION_FIXED", "protocol status drift")
    require(
        protocol.get("security")
        == {
            "prospective_label_grade_outcome_or_prediction_values_read": False,
            "raw_senior_archives_opened": False,
            "task_run_card_code_edge_or_row_identities_emitted": False,
            "row_level_release_created": False,
            "gpu_api_model_fit_base_update": [0, 0, 0, 0],
        },
        "security contract drift",
    )
    source = verify_source_v9(repo_root, protocol)
    source_names = {entry["name"] for entry in source["entries"]}
    contract = validate_claim_contract(protocol, source_names)

    assertion_counts: dict[str, int] = {}
    artifact_counts: dict[str, int] = {}
    distinct_entries: list[dict[str, Any]] = []
    for specification in protocol["distinct_entries"]:
        entry = copy.deepcopy(specification)
        count = sum(verify_artifact(repo_root, artifact) for artifact in entry["artifacts"])
        entry["claim_signature_sha256"] = canonical_sha256(entry["claim_signature"])
        entry["artifact_count"] = len(entry["artifacts"])
        entry["json_assertion_count"] = count
        assertion_counts[entry["name"]] = count
        artifact_counts[entry["name"]] = len(entry["artifacts"])
        distinct_entries.append(entry)

    reconstruction_records: list[dict[str, Any]] = []
    for specification in protocol["reconstructions"]:
        record = copy.deepcopy(specification)
        count = sum(verify_artifact(repo_root, artifact) for artifact in record["artifacts"])
        record["shared_component_signature_sha256"] = canonical_sha256(record["shared_component_signature"])
        record["artifact_count"] = len(record["artifacts"])
        record["json_assertion_count"] = count
        assertion_counts[record["name"]] = count
        artifact_counts[record["name"]] = len(record["artifacts"])
        reconstruction_records.append(record)

    equivalence = verify_reconstruction_equivalence(repo_root, protocol)

    for reserved in (
        "source_v9_index",
        "v10_protocol",
        "v10_reporting_contract",
        "claim_accounting",
        "claim_deduplication",
        "v10_security",
        "reconstructions",
    ):
        require(reserved not in source, f"source v9 already contains reserved field: {reserved}")
    result = copy.deepcopy(source)
    result.update(
        {
            "protocol": INDEX_PROTOCOL,
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
                "distinct_entries_added": len(distinct_entries),
                "reconstruction_records_added": len(reconstruction_records),
                "total_distinct_entry_count": len(source["entries"]) + len(distinct_entries),
                "duplicate_claims_counted_as_distinct": 0,
                "source_v9_status_preserved": True,
                "shared_numeric_fields_crosschecked": equivalence[
                    "shared_numeric_fields_exact"
                ],
            },
            "claim_deduplication": {
                "structured_signature_scope": "v10 additions and reconstruction records; legacy v9 entries are preserved but not retroactively fingerprinted",
                "distinct_claim_signature_sha256_by_name": {
                    name: canonical_sha256(protocol["distinct_entries"][index]["claim_signature"])
                    for index, name in enumerate(contract["addition_names"])
                },
                "reconstruction_target_by_name": {
                    record["name"]: record["reproduction_of"] for record in reconstruction_records
                },
                "artifact_count_by_record": artifact_counts,
                "json_assertion_count_by_record": assertion_counts,
                "reconstruction_numeric_crosscheck": equivalence,
            },
            "v10_security": copy.deepcopy(protocol["security"]),
            "entries": copy.deepcopy(source["entries"]) + distinct_entries,
            "reconstructions": reconstruction_records,
        }
    )
    require(len(result["entries"]) == result["claim_accounting"]["total_distinct_entry_count"], "total entry count")
    require(result["entries"][: len(source["entries"])] == source["entries"], "source entries changed")
    require(all(record["name"] not in {entry["name"] for entry in result["entries"]} for record in reconstruction_records), "reconstruction leaked into entries")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = build_index(arguments.repo_root, arguments.protocol)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "distinct_entries": len(result["entries"]),
                "reconstructions": len(result["reconstructions"]),
                "duplicate_claims_counted_as_distinct": result["claim_accounting"]["duplicate_claims_counted_as_distinct"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
