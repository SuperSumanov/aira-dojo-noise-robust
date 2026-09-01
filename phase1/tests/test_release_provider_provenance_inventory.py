import hashlib
import json
from pathlib import Path

import pytest

from phase1.build_release_provider_provenance_inventory import (
    ProviderInventoryError,
    build_inventory,
    canonical_batch_lock,
)
from phase1.verify_release_provider_provenance_inventory import recompute, verify


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def fixture_contract(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    batches = [
        {"file": "cards_a.jsonl", "sha256": "a" * 64, "bytes": 10, "rows": 2},
        {"file": "cards_b.jsonl", "sha256": "b" * 64, "bytes": 20, "rows": 3},
        {"file": "cards_c.jsonl", "sha256": "c" * 64, "bytes": 30, "rows": 5},
    ]
    release = {
        "schema_version": "aira-dojo-corpus-release-v1",
        "version": "v1",
        "release_commit": "d" * 40,
        "rebuild_protocol": "test",
        "batch_count": 3,
        "batch_lock_sha256": canonical_batch_lock(batches),
        "output": {"file": "cards_current_v1.jsonl", "rows": 10, "bytes": 60, "sha256": "e" * 64},
    }
    registry = {"schema_version": "aira-dojo-corpus-batch-registry-v1", "batches": batches}
    annotations = {
        "_note": "metadata only",
        "ds-flash-v1": ["cards_a.jsonl"],
        "ds-flash-v1-boundary-note": "boundary",
        "ds-flash-v2": [],
        "ds-flash-ambiguous": ["cards_b.jsonl"],
        "qwen3-coder-flash": [],
        "glm-5": [],
    }
    release_path = tmp_path / "v1.json"
    registry_path = tmp_path / "registry.json"
    manifest_path = tmp_path / "manifest.txt"
    annotations_path = tmp_path / "annotations.json"
    write_json(release_path, release)
    write_json(registry_path, registry)
    manifest_path.write_text("cards_a.jsonl\ncards_b.jsonl\ncards_c.jsonl\n", encoding="utf-8")
    write_json(annotations_path, annotations)
    return release_path, registry_path, manifest_path, annotations_path


def test_metadata_only_inventory_matches_independent_reconstruction(tmp_path: Path) -> None:
    paths = fixture_contract(tmp_path)
    inventory = build_inventory(*paths)
    independent = recompute(*paths)
    verify(inventory, independent)
    assert inventory["coverage"] == {
        "mapped_batches": 2,
        "mapped_rows": 5,
        "exact_version_or_model_batches": 1,
        "exact_version_or_model_rows": 2,
        "version_boundary_ambiguous_batches": 1,
        "version_boundary_ambiguous_rows": 3,
        "unmapped_batches": 1,
        "unmapped_rows": 5,
    }
    assert inventory["unmapped_batch_files"] == ["cards_c.jsonl"]
    assert inventory["scope"]["card_payloads_read"] is False
    assert inventory["scope"]["release_cleared"] is False


def test_duplicate_annotation_fails_closed(tmp_path: Path) -> None:
    release, registry, manifest, annotations = fixture_contract(tmp_path)
    value = json.loads(annotations.read_text(encoding="utf-8"))
    value["ds-flash-v2"] = ["cards_a.jsonl"]
    write_json(annotations, value)
    with pytest.raises(ProviderInventoryError, match="more than once"):
        build_inventory(release, registry, manifest, annotations)


def test_annotation_outside_release_fails_closed(tmp_path: Path) -> None:
    release, registry, manifest, annotations = fixture_contract(tmp_path)
    value = json.loads(annotations.read_text(encoding="utf-8"))
    value["qwen3-coder-flash"] = ["cards_future.jsonl"]
    write_json(annotations, value)
    with pytest.raises(ProviderInventoryError, match="outside release"):
        build_inventory(release, registry, manifest, annotations)


def test_manifest_reordering_fails_closed(tmp_path: Path) -> None:
    release, registry, manifest, annotations = fixture_contract(tmp_path)
    manifest.write_text("cards_b.jsonl\ncards_a.jsonl\ncards_c.jsonl\n", encoding="utf-8")
    with pytest.raises(ProviderInventoryError, match="ordered manifest"):
        build_inventory(release, registry, manifest, annotations)


def test_release_lock_drift_fails_closed(tmp_path: Path) -> None:
    release, registry, manifest, annotations = fixture_contract(tmp_path)
    value = json.loads(release.read_text(encoding="utf-8"))
    value["batch_lock_sha256"] = hashlib.sha256(b"drift").hexdigest()
    write_json(release, value)
    with pytest.raises(ProviderInventoryError, match="batch lock"):
        build_inventory(release, registry, manifest, annotations)
