from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath

import pytest

from phase1 import e2a_hf_cache as cache
from phase1 import verify_safetensors_equivalence as equivalence
from phase1 import verify_e2a_hf_cache as independent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_writable(root: Path) -> None:
    if not root.exists():
        return
    for path in [root, *root.rglob("*")]:
        if not path.is_symlink():
            os.chmod(path, 0o755 if path.is_dir() else 0o644)


def test_version_guard() -> None:
    equivalence.require_safe_torch_version("2.6.0+cu124")
    equivalence.require_safe_torch_version("2.11.0")
    with pytest.raises(equivalence.EquivalenceError):
        equivalence.require_safe_torch_version("2.5.1+cu124")


@pytest.mark.skipif(os.name == "nt", reason="Windows test user cannot create symlinks")
def test_materialize_replaces_unsafe_snapshot_with_verified_safe_weights(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    repo = source / "hub" / "models--microsoft--deberta-v3-base"
    blobs = repo / "blobs"
    main = repo / "snapshots" / "main-sha"
    safe_revision = repo / "snapshots" / "safe-sha"
    no_exist = repo / ".no_exist" / "main-sha"
    for directory in (blobs, main, safe_revision, no_exist):
        directory.mkdir(parents=True, exist_ok=True)
    bin_blob = blobs / "bin-blob"
    safe_blob = blobs / "safe-blob"
    bin_blob.write_bytes(b"same tensor payload in pickle form")
    safe_blob.write_bytes(b"same tensor payload in safe form")
    (main / "pytorch_model.bin").symlink_to("../../blobs/bin-blob")
    (safe_revision / "model.safetensors").symlink_to("../../blobs/safe-blob")
    (no_exist / "model.safetensors").write_bytes(b"")
    receipt = tmp_path / "equivalence.json"
    receipt.write_text(json.dumps({
        "status": equivalence.STATUS,
        "values_bitwise_identical": True,
        "key_sets_identical": True,
        "shapes_identical": True,
        "dtypes_identical": True,
        "pytorch_sha256": sha(bin_blob),
        "safetensors_sha256": sha(safe_blob),
    }), encoding="utf-8")
    output = tmp_path / "output"
    try:
        result = cache.materialize(
            source,
            output,
            PurePosixPath(
                "hub/models--microsoft--deberta-v3-base/snapshots/main-sha/"
                "pytorch_model.bin"
            ),
            PurePosixPath(
                "hub/models--microsoft--deberta-v3-base/snapshots/safe-sha/"
                "model.safetensors"
            ),
            receipt,
        )
        target_main = (
            output / "hub" / "models--microsoft--deberta-v3-base" / "snapshots" / "main-sha"
        )
        assert not (target_main / "pytorch_model.bin").exists()
        assert (target_main / "model.safetensors").is_symlink()
        assert (target_main / "model.safetensors").read_bytes() == safe_blob.read_bytes()
        assert not (
            output / "hub" / "models--microsoft--deberta-v3-base" / ".no_exist"
            / "main-sha" / "model.safetensors"
        ).exists()
        assert result["status"] == cache.STATUS
        assert result["full_payload_verified"] is True
        assert cache.verify_cache(
            output,
            expected_manifest_sha256=result["manifest_sha256"],
            expected_payload_sha256=result["payload_sha256"],
        )["read_only_verified"] is True
        independently = independent.verify(
            output,
            result["manifest_sha256"],
            result["payload_sha256"],
            full=True,
        )
        assert independently["status"] == independent.STATUS
        assert independently["materializer_imported"] is False
    finally:
        make_writable(output)


def test_manifest_detects_payload_mutation(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    root.mkdir()
    payload = root / "payload.bin"
    payload.write_bytes(b"first")
    manifest = cache.make_manifest(root, "a" * 64)
    cache.atomic_json(root / cache.MANIFEST_NAME, manifest)
    cache.freeze_permissions(root)
    try:
        cache.verify_cache(root)
        os.chmod(payload, 0o644)
        payload.write_bytes(b"second")
        with pytest.raises(cache.CacheError):
            cache.verify_cache(root)
    finally:
        make_writable(root)


def test_materialize_rejects_absolute_or_traversing_cache_paths(tmp_path: Path) -> None:
    with pytest.raises(cache.CacheError, match="canonical relative POSIX"):
        cache.require_relative_cache_path(PurePosixPath("/outside/model.bin"), "test")
    with pytest.raises(cache.CacheError, match="canonical relative POSIX"):
        cache.require_relative_cache_path(PurePosixPath("../outside/model.bin"), "test")
