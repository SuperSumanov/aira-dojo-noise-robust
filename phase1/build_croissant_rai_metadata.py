#!/usr/bin/env python3
"""Build fail-closed Croissant 1.1 + RAI 1.0 metadata from the v11 schema inventory.

The script has two deliberately separate modes:

* readiness mode always emits a value-free release-readiness receipt;
* release mode emits Croissant JSON-LD only after all publication-time fields are
  present and non-placeholder.

It reads schema metadata only. It never opens card, decision, prospective, label,
prediction, or outcome payloads.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlparse


CROISSANT_SPEC = "http://mlcommons.org/croissant/1.1"
RAI_SPEC = "http://mlcommons.org/croissant/RAI/1.0"
EXPECTED_INVENTORY_PROTOCOL = "release-schema-inventory-v1"
REQUIRED_CONFIG_KEYS = (
    "license",
    "url",
    "creator",
    "datePublished",
    "contentBaseUrl",
)
PLACEHOLDER_RE = re.compile(
    r"(?:^|[^a-z])(todo|tbd|placeholder|example\.com|changeme|fill[ _-]?me)(?:$|[^a-z])",
    re.IGNORECASE,
)
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(payload, encoding="utf-8", newline="\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_http_url(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip() or PLACEHOLDER_RE.search(value):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _validate_inventory(inventory: Any) -> dict[str, Any]:
    if not isinstance(inventory, dict):
        raise ValueError("schema inventory must be a JSON object")
    if inventory.get("protocol") != EXPECTED_INVENTORY_PROTOCOL:
        raise ValueError("unexpected schema inventory protocol")
    scope = inventory.get("scope")
    if not isinstance(scope, dict):
        raise ValueError("schema inventory scope is missing")
    for forbidden in (
        "candidate_identities_emitted",
        "labels_or_predictions_emitted",
        "prospective_resources_read",
        "source_values_emitted",
    ):
        if scope.get(forbidden) is not False:
            raise ValueError(f"schema inventory violates value-free scope: {forbidden}")
    resources = inventory.get("resources")
    if not isinstance(resources, dict) or not resources:
        raise ValueError("schema inventory contains no resources")
    for name, resource in resources.items():
        if not isinstance(resource, dict):
            raise ValueError(f"invalid resource metadata: {name}")
        path = resource.get("path")
        rows = resource.get("rows")
        size = resource.get("bytes")
        digest = resource.get("sha256_raw")
        fields = resource.get("fields")
        if not isinstance(path, str) or not path.endswith(".jsonl"):
            raise ValueError(f"invalid resource path: {name}")
        if not isinstance(rows, int) or rows < 0:
            raise ValueError(f"invalid row count: {name}")
        if not isinstance(size, int) or size < 0:
            raise ValueError(f"invalid byte count: {name}")
        if not isinstance(digest, str) or not HEX64_RE.fullmatch(digest):
            raise ValueError(f"invalid resource digest: {name}")
        if not isinstance(fields, dict) or "$" not in fields:
            raise ValueError(f"invalid field inventory: {name}")
    return resources


def build_readiness(inventory_path: Path, inventory: dict[str, Any]) -> dict[str, Any]:
    resources = _validate_inventory(inventory)
    total_rows = sum(resource["rows"] for resource in resources.values())
    total_bytes = sum(resource["bytes"] for resource in resources.values())
    resource_receipts = []
    for name in sorted(resources):
        resource = resources[name]
        resource_receipts.append(
            {
                "resource_id": name,
                "path": resource["path"],
                "rows": resource["rows"],
                "bytes": resource["bytes"],
                "sha256_raw": resource["sha256_raw"],
                "field_paths": len(resource["fields"]),
            }
        )
    return {
        "protocol": "croissant-rai-release-readiness-v1",
        "status": "ENGINEERING_READY_PUBLICATION_FIELDS_BLOCKED",
        "specifications": {
            "croissant": CROISSANT_SPEC,
            "responsible_ai": RAI_SPEC,
        },
        "resolved_required_dataset_fields": [
            "@context",
            "@type",
            "dct:conformsTo",
            "name",
            "description",
            "distribution structure, byte counts, and SHA-256 digests",
        ],
        "blocked_publication_config_fields": list(REQUIRED_CONFIG_KEYS),
        "blocked_field_count": len(REQUIRED_CONFIG_KEYS),
        "resource_count": len(resources),
        "total_rows_across_resources": total_rows,
        "total_bytes_across_resources": total_bytes,
        "resources": resource_receipts,
        "inputs": {
            "schema_inventory": inventory_path.as_posix(),
            "schema_inventory_sha256": _sha256(inventory_path),
        },
        "release_clearance": False,
        "interpretation": (
            "The metadata engineering path is deterministic, but no Croissant release "
            "artifact may be emitted until all publication-time fields are supplied and "
            "the independent legal/content gates close."
        ),
        "scope": {
            "schema_metadata_only": True,
            "card_or_decision_payload_read": False,
            "labels_outcomes_predictions_read": False,
            "prospective_resources_read": False,
            "counts_as_distinct_claim_evidence": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
    }


def _validate_creator(value: Any) -> list[dict[str, str]]:
    creators = value if isinstance(value, list) else [value]
    if not creators:
        raise ValueError("creator must contain at least one person or organization")
    normalized: list[dict[str, str]] = []
    for creator in creators:
        if not isinstance(creator, dict):
            raise ValueError("each creator must be an object")
        creator_type = creator.get("@type")
        name = creator.get("name")
        if creator_type not in {"sc:Person", "sc:Organization"}:
            raise ValueError("creator @type must be sc:Person or sc:Organization")
        if not isinstance(name, str) or not name.strip() or PLACEHOLDER_RE.search(name):
            raise ValueError("creator name is missing or placeholder")
        normalized.append({"@type": creator_type, "name": name.strip()})
    return normalized


def _validate_release_config(config: Any) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise ValueError("release config must be a JSON object")
    missing = [key for key in REQUIRED_CONFIG_KEYS if key not in config]
    if missing:
        raise ValueError("missing publication config fields: " + ", ".join(missing))

    licenses = config["license"] if isinstance(config["license"], list) else [config["license"]]
    if not licenses or not all(_is_http_url(item) for item in licenses):
        raise ValueError("license must contain one or more non-placeholder HTTP(S) URLs")
    if not _is_http_url(config["url"]):
        raise ValueError("url must be a non-placeholder HTTP(S) URL")
    if not _is_http_url(config["contentBaseUrl"]):
        raise ValueError("contentBaseUrl must be a non-placeholder HTTP(S) URL")
    creators = _validate_creator(config["creator"])
    try:
        published = dt.date.fromisoformat(config["datePublished"])
    except (TypeError, ValueError) as exc:
        raise ValueError("datePublished must be an ISO-8601 calendar date") from exc
    if published.year < 2026:
        raise ValueError("datePublished predates the v11 release process")

    normalized = {
        "license": licenses,
        "url": config["url"].rstrip("/"),
        "creator": creators,
        "datePublished": published.isoformat(),
        "contentBaseUrl": config["contentBaseUrl"].rstrip("/") + "/",
    }
    if "publisher" in config:
        normalized["publisher"] = _validate_creator(config["publisher"])
    if "citeAs" in config:
        cite_as = config["citeAs"]
        if not isinstance(cite_as, str) or not cite_as.strip() or PLACEHOLDER_RE.search(cite_as):
            raise ValueError("citeAs is empty or placeholder")
        normalized["citeAs"] = cite_as.strip()
    return normalized


def _primitive_types(field: dict[str, Any]) -> list[str]:
    counts = field.get("type_counts")
    if not isinstance(counts, dict):
        return []
    mapping = {
        "boolean": "sc:Boolean",
        "integer": "sc:Integer",
        "number": "sc:Float",
        "string": "sc:Text",
    }
    return [mapping[item] for item in mapping if counts.get(item, 0)]


def _field_id(resource_id: str, json_path: str) -> str:
    suffix = json_path.removeprefix("$.")
    suffix = suffix.replace("[]", "-items")
    suffix = re.sub(r"[^A-Za-z0-9._-]+", "-", suffix).strip("-")
    return f"{resource_id}/{suffix}"


def _record_fields(resource_id: str, field_inventory: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for json_path in sorted(field_inventory):
        if json_path == "$" or json_path.endswith("[]"):
            continue
        field = field_inventory[json_path]
        if not isinstance(field, dict):
            continue
        counts = field.get("type_counts", {})
        is_array = bool(isinstance(counts, dict) and counts.get("array", 0))
        if is_array:
            element = field_inventory.get(json_path + "[]", {})
            data_types = _primitive_types(element) or ["sc:Text"]
        else:
            data_types = _primitive_types(field)
        if not data_types:
            continue
        output: dict[str, Any] = {
            "@type": "cr:Field",
            "@id": _field_id(resource_id, json_path),
            "name": json_path.removeprefix("$.") or "$",
            "dataType": data_types[0] if len(data_types) == 1 else data_types,
            "source": {
                "@type": "cr:DataSource",
                "fileObject": {"@id": resource_id},
                "extract": {"jsonPath": json_path},
            },
        }
        if is_array:
            output["isArray"] = True
            output["arrayShape"] = "(-1,)"
        result.append(output)
    if not result:
        raise ValueError(f"resource {resource_id} has no primitive fields")
    return result


def _context() -> dict[str, Any]:
    return {
        "@language": "en",
        "@vocab": "http://schema.org/",
        "sc": "http://schema.org/",
        "cr": "http://mlcommons.org/croissant/",
        "rai": "http://mlcommons.org/croissant/RAI/",
        "dct": "http://purl.org/dc/terms/",
        "conformsTo": "dct:conformsTo",
        "arrayShape": "cr:arrayShape",
        "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
        "extract": "cr:extract",
        "field": "cr:field",
        "fileObject": "cr:fileObject",
        "isArray": "cr:isArray",
        "jsonPath": "cr:jsonPath",
        "recordSet": "cr:recordSet",
        "source": "cr:source",
    }


def build_metadata(inventory: dict[str, Any], config: Any) -> dict[str, Any]:
    resources = _validate_inventory(inventory)
    release = _validate_release_config(config)
    distributions: list[dict[str, Any]] = []
    record_sets: list[dict[str, Any]] = []
    for resource_id in sorted(resources):
        resource = resources[resource_id]
        content_url = urljoin(
            release["contentBaseUrl"], quote(resource["path"].replace("\\", "/"), safe="/"),
        )
        distributions.append(
            {
                "@type": "cr:FileObject",
                "@id": resource_id,
                "name": resource_id,
                "description": f"Immutable JSONL resource with {resource['rows']} records.",
                "contentUrl": content_url,
                "contentSize": f"{resource['bytes']} B",
                "encodingFormat": "application/x-ndjson",
                "sha256": resource["sha256_raw"],
            }
        )
        record_sets.append(
            {
                "@type": "cr:RecordSet",
                "@id": f"{resource_id}-records",
                "name": f"{resource_id} records",
                "description": f"One record per line in the {resource_id} resource.",
                "field": _record_fields(resource_id, resource["fields"]),
            }
        )

    metadata: dict[str, Any] = {
        "@context": _context(),
        "@type": "sc:Dataset",
        "dct:conformsTo": [CROISSANT_SPEC, RAI_SPEC],
        "name": "AIRA-Dojo MLE-Agent Decision Corpus",
        "description": (
            "A versioned corpus of MLE-agent candidate programs, external execution "
            "observations, search-tree lineage, and run-clean sibling decision resources "
            "for predictor benchmarking and audit research."
        ),
        "license": release["license"],
        "url": release["url"],
        "creator": release["creator"],
        "datePublished": release["datePublished"],
        "version": "11.0.0",
        "isLiveDataset": False,
        "keywords": [
            "machine learning engineering",
            "agent trajectories",
            "search trees",
            "critics",
            "predictor benchmark",
            "dataset audit",
        ],
        "distribution": distributions,
        "recordSet": record_sets,
        "rai:dataCollection": (
            "Candidate programs and lineage were collected from AIRA-Dojo search runs "
            "over public MLE-style tasks; external evaluators produced execution outcomes."
        ),
        "rai:dataCollectionType": [
            "Software Collection",
            "Experiments",
            "Secondary Data analysis",
        ],
        "rai:dataCollectionRawData": (
            "Immutable run archives and batch manifests; external competition datasets "
            "are not redistributed and must be prepared separately by users."
        ),
        "rai:dataManipulationProtocol": (
            "Append-only batch concatenation, physical-run reconstruction, run-clean "
            "splitting, sibling-pair construction, and hash-bound release inventories."
        ),
        "rai:dataPreprocessingProtocol": [
            "Validate immutable batch rows, bytes, order, and SHA-256 digests.",
            "Reconstruct or validate physical run identifiers before split assignment.",
            "Quarantine non-finite labels and preserve missing-value semantics.",
        ],
        "rai:dataAnnotationProtocol": (
            "Labels are external task-evaluator grades and deterministic normalized "
            "derivatives; pair orientation follows the higher-is-better task metadata."
        ),
        "rai:dataAnnotationAnalysis": [
            "Test-retest label repeatability and noise ceilings are reported separately.",
            "Run-level leakage, duplicate pairs, coverage, and withdrawals are audited."
        ],
        "rai:personalSensitiveInformation": (
            "Generated code and terminal tails are treated as high-risk free text. Final "
            "credential, path, PII, and competition-content clearance is mandatory."
        ),
        "rai:dataBiases": [
            "Public MLE/Kaggle-style tasks do not represent all machine-learning engineering.",
            "Generator, task, operator, hardware, runtime, and scoring affect record yield.",
            "Unequal branching can make pair-micro results task- or run-dominated.",
        ],
        "rai:dataLimitations": [
            "Historical source retention is incomplete for some physical runs.",
            "Retained children and sibling counts are not guaranteed complete opportunity sets.",
            "Post-execution observations are not execution-free predictor inputs.",
            "The release remains subject to competition, provider, privacy, and license gates.",
        ],
        "rai:dataUseCases": [
            "Benchmark execution-free candidate critics under run-clean splits.",
            "Study search-tree data quality, leakage, coverage, and label repeatability.",
            "Reproduce audited sibling-decision protocols without redistributing task data."
        ],
        "rai:dataReleaseMaintenance": (
            "New batches and releases are append-only and hash-bound. Defects trigger "
            "versioned errata or withdrawal records rather than silent replacement."
        ),
    }
    if "publisher" in release:
        metadata["publisher"] = release["publisher"]
    if "citeAs" in release:
        metadata["citeAs"] = release["citeAs"]
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema-inventory", type=Path, required=True)
    parser.add_argument("--readiness-output", type=Path, required=True)
    parser.add_argument("--release-config", type=Path)
    parser.add_argument("--metadata-output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inventory = _read_json(args.schema_inventory)
    readiness = build_readiness(args.schema_inventory, inventory)
    _write_json(args.readiness_output, readiness)

    if bool(args.release_config) != bool(args.metadata_output):
        raise ValueError("--release-config and --metadata-output must be supplied together")
    if args.release_config:
        config = _read_json(args.release_config)
        metadata = build_metadata(inventory, config)
        _write_json(args.metadata_output, metadata)

    print(f"STATUS={readiness['status']}")
    print(f"RESOURCES={readiness['resource_count']}")
    print(f"ROWS={readiness['total_rows_across_resources']}")
    print(f"BLOCKED_FIELDS={readiness['blocked_field_count']}")
    print(f"READINESS_SHA256={_sha256(args.readiness_output)}")
    if args.metadata_output:
        print(f"METADATA_SHA256={_sha256(args.metadata_output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
