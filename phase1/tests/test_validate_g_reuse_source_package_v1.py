import hashlib
import json
from pathlib import Path

import pytest

from phase1.validate_g_reuse_source_package_v1 import PackageDeclarationError, validate


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def make_package(tmp_path: Path) -> tuple[Path, Path, dict]:
    root = tmp_path / "package"; root.mkdir()
    producer = {
        "protocol": "g-reuse-producer-receipt-v1", "producer_commit": "a" * 40,
        "stable_release_id": "release-v1", "exact_config_stratum_id": "stratum-v1",
        "command_argv_sha256": "b" * 64, "instance_manifest_sha256": "c" * 64,
        "run_count": 7, "executed_at_utc": "2026-09-05T00:00:00Z",
    }
    evaluator = {
        "protocol": "g-reuse-evaluator-receipt-v1", "evaluator_commit": "d" * 40,
        "evaluator_id": "pristine-v1", "score_schema_id": "score-v1",
        "execution_records_sha256": "e" * 64,
    }
    write_json(root / "producer.json", producer); write_json(root / "evaluator.json", evaluator)
    names = {
        "cards": "cards.bin", "global_pairs": "global.bin", "local_pairs": "local.bin",
        "split_manifest": "split.bin", "source_provenance": "source.bin",
        "producer_receipt": "producer.json", "evaluator_receipt": "evaluator.json",
    }
    for role, name in names.items():
        if not (root / name).exists():
            (root / name).write_bytes((role + "\n").encode())
    artifacts = []
    for role, name in names.items():
        raw = (root / name).read_bytes()
        artifacts.append({"role": role, "path": name, "bytes": len(raw),
                          "sha256": hashlib.sha256(raw).hexdigest(), "lfs_oid_sha256": None})
    manifest = {
        "protocol": "g-reuse-source-package-declaration-v1", "package_id": "test-package-v1",
        "producer": {"producer_commit": "a" * 40, "stable_release_id": "release-v1",
                     "exact_config_stratum_id": "stratum-v1"},
        "declarations": {"historical_development_only": True, "whole_experiment_split_declared": True,
                         "source_provenance_schema": "source-declaration-v2"},
        "artifacts": artifacts,
    }
    manifest_path = root / "manifest.json"; write_json(manifest_path, manifest)
    return root, manifest_path, manifest


def test_valid_declaration_is_not_effect_eligible(tmp_path: Path):
    root, manifest, _ = make_package(tmp_path)
    result = validate(root, manifest)
    assert result["artifacts"] == 7
    assert result["classification"] == "PACKAGE_DECLARATION_HASH_BOUND_NOT_EFFECT_ELIGIBLE"
    assert result["payload_files_parsed"] == result["protected_values_read"] == 0


def test_missing_role_rejected(tmp_path: Path):
    root, manifest_path, manifest = make_package(tmp_path)
    manifest["artifacts"].pop()
    write_json(manifest_path, manifest)
    with pytest.raises(PackageDeclarationError, match="artifact_count"):
        validate(root, manifest_path)


def test_hash_drift_rejected(tmp_path: Path):
    root, manifest_path, _ = make_package(tmp_path)
    (root / "cards.bin").write_bytes(b"changed")
    with pytest.raises(PackageDeclarationError, match="artifact_drift"):
        validate(root, manifest_path)


def test_path_traversal_rejected(tmp_path: Path):
    root, manifest_path, manifest = make_package(tmp_path)
    manifest["artifacts"][0]["path"] = "../outside"
    write_json(manifest_path, manifest)
    with pytest.raises(PackageDeclarationError, match="path_traversal"):
        validate(root, manifest_path)


def test_hardlink_alias_rejected(tmp_path: Path):
    root, manifest_path, manifest = make_package(tmp_path)
    alias = root / "alias.bin"
    alias.hardlink_to(root / "cards.bin")
    item = next(x for x in manifest["artifacts"] if x["role"] == "global_pairs")
    item["path"] = alias.name
    raw = alias.read_bytes()
    item["bytes"] = len(raw)
    item["sha256"] = hashlib.sha256(raw).hexdigest()
    write_json(manifest_path, manifest)
    with pytest.raises(PackageDeclarationError, match="artifact_not_regular"):
        validate(root, manifest_path)


def test_unlisted_hardlink_target_rejected(tmp_path: Path):
    root, manifest_path, manifest = make_package(tmp_path)
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    linked = root / "linked.bin"
    linked.hardlink_to(outside)
    item = next(x for x in manifest["artifacts"] if x["role"] == "global_pairs")
    item["path"] = linked.name
    raw = linked.read_bytes()
    item["bytes"] = len(raw)
    item["sha256"] = hashlib.sha256(raw).hexdigest()
    write_json(manifest_path, manifest)
    with pytest.raises(PackageDeclarationError, match="artifact_not_regular"):
        validate(root, manifest_path)


def test_symlink_artifact_rejected(tmp_path: Path):
    root, manifest_path, manifest = make_package(tmp_path)
    linked = root / "linked.bin"
    try:
        linked.symlink_to(root / "cards.bin")
    except OSError:
        pytest.skip("symlink creation unavailable")
    item = next(x for x in manifest["artifacts"] if x["role"] == "global_pairs")
    item["path"] = linked.name
    raw = linked.read_bytes()
    item["bytes"] = len(raw)
    item["sha256"] = hashlib.sha256(raw).hexdigest()
    write_json(manifest_path, manifest)
    with pytest.raises(PackageDeclarationError, match="artifact_symlink"):
        validate(root, manifest_path)


def test_producer_mismatch_rejected(tmp_path: Path):
    root, manifest_path, manifest = make_package(tmp_path)
    manifest["producer"]["producer_commit"] = "f" * 40
    write_json(manifest_path, manifest)
    with pytest.raises(PackageDeclarationError, match="producer_receipt_mismatch"):
        validate(root, manifest_path)


def test_non_utc_producer_time_rejected(tmp_path: Path):
    root, manifest_path, manifest = make_package(tmp_path)
    receipt_path = root / "producer.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["executed_at_utc"] = "2026-09-05T08:00:00+08:00"
    write_json(receipt_path, receipt)
    raw = receipt_path.read_bytes()
    item = next(x for x in manifest["artifacts"] if x["role"] == "producer_receipt")
    item["bytes"] = len(raw)
    item["sha256"] = hashlib.sha256(raw).hexdigest()
    write_json(manifest_path, manifest)
    with pytest.raises(PackageDeclarationError, match="executed_at_utc"):
        validate(root, manifest_path)


def test_duplicate_manifest_key_rejected(tmp_path: Path):
    root, manifest_path, _ = make_package(tmp_path)
    manifest_path.write_text('{"protocol":"a","protocol":"b"}', encoding="utf-8")
    with pytest.raises(PackageDeclarationError, match="duplicate_json_key"):
        validate(root, manifest_path)


def test_credential_shape_in_receipt_rejected_before_parse(tmp_path: Path):
    root, manifest_path, manifest = make_package(tmp_path)
    path = root / "producer.json"
    path.write_text('{"credential":"sk-' + 'x' * 24 + '"}', encoding="utf-8")
    raw = path.read_bytes()
    item = next(x for x in manifest["artifacts"] if x["role"] == "producer_receipt")
    item["bytes"] = len(raw); item["sha256"] = hashlib.sha256(raw).hexdigest()
    write_json(manifest_path, manifest)
    with pytest.raises(PackageDeclarationError, match="credential_shape"):
        validate(root, manifest_path)
