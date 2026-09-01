#!/usr/bin/env python3
"""Independent verifier for Croissant/RAI readiness and optional final metadata."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


CROISSANT_SPEC = "http://mlcommons.org/croissant/1.1"
RAI_SPEC = "http://mlcommons.org/croissant/RAI/1.0"
EXPECTED_BLOCKERS = ["license", "url", "creator", "datePublished", "contentBaseUrl"]
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
PLACEHOLDER_RE = re.compile(
    r"(?:^|[^a-z])(todo|tbd|placeholder|example\.com|changeme|fill[ _-]?me)(?:$|[^a-z])",
    re.IGNORECASE,
)


def _read(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _http(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip() or PLACEHOLDER_RE.search(value):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _resource_receipts(resources: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for name in sorted(resources):
        resource = resources[name]
        digest = resource.get("sha256_raw")
        if not isinstance(digest, str) or not HEX64_RE.fullmatch(digest):
            raise ValueError(f"bad schema inventory digest: {name}")
        output.append(
            {
                "resource_id": name,
                "path": resource["path"],
                "rows": resource["rows"],
                "bytes": resource["bytes"],
                "sha256_raw": digest,
                "field_paths": len(resource["fields"]),
            }
        )
    return output


def _verify_readiness(
    schema_path: Path, schema: dict[str, Any], readiness: dict[str, Any]
) -> dict[str, Any]:
    if schema.get("protocol") != "release-schema-inventory-v1":
        raise ValueError("unexpected schema inventory protocol")
    scope = schema.get("scope", {})
    if scope != {
        "candidate_identities_emitted": False,
        "labels_or_predictions_emitted": False,
        "prospective_resources_read": False,
        "source_values_emitted": False,
    }:
        raise ValueError("schema inventory is not the expected value-free artifact")
    resources = schema.get("resources")
    if not isinstance(resources, dict) or not resources:
        raise ValueError("schema inventory resources missing")
    expected_resources = _resource_receipts(resources)
    expected_rows = sum(item["rows"] for item in expected_resources)
    expected_bytes = sum(item["bytes"] for item in expected_resources)
    checks = {
        "protocol": readiness.get("protocol") == "croissant-rai-release-readiness-v1",
        "blocked_status": readiness.get("status")
        == "ENGINEERING_READY_PUBLICATION_FIELDS_BLOCKED",
        "specifications": readiness.get("specifications")
        == {"croissant": CROISSANT_SPEC, "responsible_ai": RAI_SPEC},
        "blocked_fields": readiness.get("blocked_publication_config_fields")
        == EXPECTED_BLOCKERS,
        "blocked_field_count": readiness.get("blocked_field_count") == len(EXPECTED_BLOCKERS),
        "resource_count": readiness.get("resource_count") == len(resources),
        "row_count": readiness.get("total_rows_across_resources") == expected_rows,
        "byte_count": readiness.get("total_bytes_across_resources") == expected_bytes,
        "resource_receipts": readiness.get("resources") == expected_resources,
        "inventory_hash": readiness.get("inputs", {}).get("schema_inventory_sha256")
        == _sha256(schema_path),
        "release_not_cleared": readiness.get("release_clearance") is False,
        "value_free_scope": readiness.get("scope")
        == {
            "schema_metadata_only": True,
            "card_or_decision_payload_read": False,
            "labels_outcomes_predictions_read": False,
            "prospective_resources_read": False,
            "counts_as_distinct_claim_evidence": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
    }
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise ValueError("readiness verification failed: " + ", ".join(failed))
    return {
        "checks": checks,
        "resource_count": len(resources),
        "total_rows_across_resources": expected_rows,
        "total_bytes_across_resources": expected_bytes,
    }


def _verify_metadata(schema: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    resources = schema["resources"]
    required = {
        "@context",
        "@type",
        "dct:conformsTo",
        "name",
        "description",
        "license",
        "url",
        "creator",
        "datePublished",
        "distribution",
    }
    missing = sorted(required - metadata.keys())
    if missing:
        raise ValueError("Croissant metadata missing required fields: " + ", ".join(missing))
    if metadata["@type"] != "sc:Dataset":
        raise ValueError("metadata @type mismatch")
    if metadata["dct:conformsTo"] != [CROISSANT_SPEC, RAI_SPEC]:
        raise ValueError("metadata conformance list mismatch")
    if not _http(metadata["url"]):
        raise ValueError("metadata dataset URL invalid")
    licenses = metadata["license"] if isinstance(metadata["license"], list) else [metadata["license"]]
    if not licenses or not all(_http(item) for item in licenses):
        raise ValueError("metadata license URL invalid")
    try:
        dt.date.fromisoformat(metadata["datePublished"])
    except (TypeError, ValueError) as exc:
        raise ValueError("metadata datePublished invalid") from exc
    creators = metadata["creator"] if isinstance(metadata["creator"], list) else [metadata["creator"]]
    if not creators:
        raise ValueError("metadata creator missing")
    for creator in creators:
        if creator.get("@type") not in {"sc:Person", "sc:Organization"}:
            raise ValueError("metadata creator type invalid")
        if not isinstance(creator.get("name"), str) or not creator["name"].strip():
            raise ValueError("metadata creator name invalid")

    distributions = metadata["distribution"]
    if not isinstance(distributions, list) or len(distributions) != len(resources):
        raise ValueError("distribution count mismatch")
    by_id = {item.get("@id"): item for item in distributions}
    if set(by_id) != set(resources):
        raise ValueError("distribution resource IDs mismatch")
    for name, resource in resources.items():
        item = by_id[name]
        if item.get("@type") != "cr:FileObject":
            raise ValueError(f"distribution type mismatch: {name}")
        if not _http(item.get("contentUrl")):
            raise ValueError(f"distribution URL invalid: {name}")
        if item.get("contentSize") != f"{resource['bytes']} B":
            raise ValueError(f"distribution byte count mismatch: {name}")
        if item.get("sha256") != resource["sha256_raw"]:
            raise ValueError(f"distribution digest mismatch: {name}")
        if item.get("encodingFormat") != "application/x-ndjson":
            raise ValueError(f"distribution encoding mismatch: {name}")

    record_sets = metadata.get("recordSet")
    if not isinstance(record_sets, list) or len(record_sets) != len(resources):
        raise ValueError("recordSet count mismatch")
    expected_record_ids = {f"{name}-records" for name in resources}
    if {item.get("@id") for item in record_sets} != expected_record_ids:
        raise ValueError("recordSet IDs mismatch")
    for record_set in record_sets:
        fields = record_set.get("field")
        if not isinstance(fields, list) or not fields:
            raise ValueError("recordSet has no fields")
        seen: set[str] = set()
        for field in fields:
            field_id = field.get("@id")
            if not isinstance(field_id, str) or field_id in seen:
                raise ValueError("field IDs are missing or duplicated")
            seen.add(field_id)
            source_id = field.get("source", {}).get("fileObject", {}).get("@id")
            if source_id not in resources:
                raise ValueError("field source references an unknown resource")
            if not field.get("source", {}).get("extract", {}).get("jsonPath"):
                raise ValueError("field source is missing jsonPath")

    rai_fields = {
        "rai:dataCollection",
        "rai:dataCollectionType",
        "rai:dataCollectionRawData",
        "rai:dataManipulationProtocol",
        "rai:dataPreprocessingProtocol",
        "rai:dataAnnotationProtocol",
        "rai:dataAnnotationAnalysis",
        "rai:personalSensitiveInformation",
        "rai:dataBiases",
        "rai:dataLimitations",
        "rai:dataUseCases",
        "rai:dataReleaseMaintenance",
    }
    if not rai_fields.issubset(metadata):
        raise ValueError("metadata is missing selected RAI documentation fields")
    serialized = json.dumps(metadata, ensure_ascii=False)
    if PLACEHOLDER_RE.search(serialized):
        raise ValueError("metadata contains a placeholder token")
    return {
        "required_dataset_fields_present": True,
        "distribution_count": len(distributions),
        "record_set_count": len(record_sets),
        "selected_rai_fields_present": len(rai_fields),
        "placeholder_free": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema-inventory", type=Path, required=True)
    parser.add_argument("--readiness", type=Path, required=True)
    parser.add_argument("--verification-output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    schema = _read(args.schema_inventory)
    readiness = _read(args.readiness)
    receipt = _verify_readiness(args.schema_inventory, schema, readiness)
    metadata_receipt = None
    if args.metadata:
        metadata_receipt = _verify_metadata(schema, _read(args.metadata))
    result = {
        "protocol": "independent-croissant-rai-release-readiness-verification-v1",
        "status": (
            "INDEPENDENTLY_VERIFIED_CROISSANT_RAI_METADATA"
            if metadata_receipt
            else "INDEPENDENTLY_VERIFIED_CROISSANT_RAI_READINESS_BLOCKED"
        ),
        "readiness": receipt,
        "metadata": metadata_receipt,
        "input_sha256": {
            "schema_inventory": _sha256(args.schema_inventory),
            "readiness": _sha256(args.readiness),
            **({"metadata": _sha256(args.metadata)} if args.metadata else {}),
        },
        "scope": {
            "independent_implementation": True,
            "schema_metadata_only": True,
            "labels_outcomes_predictions_read": False,
            "prospective_resources_read": False,
            "release_clearance_granted": False,
            "counts_as_distinct_claim_evidence": False,
        },
    }
    _write(args.verification_output, result)
    print(f"STATUS={result['status']}")
    print(f"RESOURCES={receipt['resource_count']}")
    print(f"ROWS={receipt['total_rows_across_resources']}")
    print(f"VERIFY_SHA256={_sha256(args.verification_output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
