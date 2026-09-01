from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


PHASE1 = Path(__file__).resolve().parents[1]


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, PHASE1 / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = _load("build_croissant_rai_metadata", "build_croissant_rai_metadata.py")
verifier = _load("verify_croissant_rai_metadata", "verify_croissant_rai_metadata.py")


def _resource(path: str, rows: int, size: int, digest_char: str):
    return {
        "path": path,
        "rows": rows,
        "bytes": size,
        "sha256_raw": digest_char * 64,
        "sha256_normalized_lf": digest_char * 64,
        "fields": {
            "$": {"type_counts": {"object": rows}},
            "$.id": {"type_counts": {"string": rows}},
            "$.score": {"type_counts": {"number": rows - 1, "null": 1}},
            "$.tags": {"type_counts": {"array": rows}},
            "$.tags[]": {"type_counts": {"string": rows + 1}},
            "$.nested": {"type_counts": {"object": rows}},
            "$.nested.step": {"type_counts": {"integer": rows}},
        },
    }


def _inventory():
    return {
        "protocol": "release-schema-inventory-v1",
        "resources": {
            "cards": _resource("phase1/cards.jsonl", 3, 120, "a"),
            "pairs": _resource("phase1/pairs.jsonl", 2, 80, "b"),
        },
        "scope": {
            "candidate_identities_emitted": False,
            "labels_or_predictions_emitted": False,
            "prospective_resources_read": False,
            "source_values_emitted": False,
        },
    }


def _config():
    return {
        "license": ["https://spdx.org/licenses/CC-BY-4.0.html"],
        "url": "https://data.invalid.test/aira-dojo-decision-corpus",
        "creator": [{"@type": "sc:Organization", "name": "Research Team"}],
        "datePublished": "2026-09-02",
        "contentBaseUrl": "https://data.invalid.test/files/",
    }


def test_readiness_is_value_free_and_fail_closed(tmp_path: Path):
    inventory_path = tmp_path / "schema.json"
    inventory_path.write_text(json.dumps(_inventory()), encoding="utf-8")
    receipt = builder.build_readiness(inventory_path, _inventory())
    assert receipt["status"] == "ENGINEERING_READY_PUBLICATION_FIELDS_BLOCKED"
    assert receipt["resource_count"] == 2
    assert receipt["total_rows_across_resources"] == 5
    assert receipt["blocked_field_count"] == 5
    assert receipt["release_clearance"] is False
    assert receipt["scope"]["labels_outcomes_predictions_read"] is False


@pytest.mark.parametrize(
    "key,value",
    [
        ("license", "TODO"),
        ("url", "https://example.com/dataset"),
        ("creator", [{"@type": "sc:Person", "name": "TBD"}]),
        ("datePublished", "not-a-date"),
        ("contentBaseUrl", "file:///tmp/release"),
    ],
)
def test_release_config_rejects_placeholders_and_invalid_values(key, value):
    config = _config()
    config[key] = value
    with pytest.raises(ValueError):
        builder.build_metadata(_inventory(), config)


def test_missing_release_config_field_fails_closed():
    config = _config()
    del config["license"]
    with pytest.raises(ValueError, match="missing publication config fields"):
        builder.build_metadata(_inventory(), config)


def test_complete_config_builds_hash_bound_croissant_and_rai_metadata(tmp_path: Path):
    inventory = _inventory()
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(inventory), encoding="utf-8")
    readiness = builder.build_readiness(schema_path, inventory)
    metadata = builder.build_metadata(inventory, _config())

    assert metadata["@type"] == "sc:Dataset"
    assert metadata["dct:conformsTo"] == [builder.CROISSANT_SPEC, builder.RAI_SPEC]
    assert len(metadata["distribution"]) == 2
    assert len(metadata["recordSet"]) == 2
    assert metadata["distribution"][0]["sha256"] in {"a" * 64, "b" * 64}
    card_fields = next(x for x in metadata["recordSet"] if x["@id"] == "cards-records")["field"]
    tags = next(x for x in card_fields if x["name"] == "tags")
    assert tags["isArray"] is True
    assert tags["dataType"] == "sc:Text"

    verified_readiness = verifier._verify_readiness(schema_path, inventory, readiness)
    verified_metadata = verifier._verify_metadata(inventory, metadata)
    assert verified_readiness["resource_count"] == 2
    assert verified_metadata["distribution_count"] == 2
    assert verified_metadata["selected_rai_fields_present"] == 12


def test_scope_violation_is_rejected(tmp_path: Path):
    inventory = _inventory()
    inventory["scope"]["prospective_resources_read"] = True
    path = tmp_path / "schema.json"
    path.write_text(json.dumps(inventory), encoding="utf-8")
    with pytest.raises(ValueError, match="value-free scope"):
        builder.build_readiness(path, inventory)
