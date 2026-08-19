"""Materialize and verify the immutable, hash-bound E2-A Hugging Face cache."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import stat
import sys
import tempfile
from typing import Any

from phase1.verify_safetensors_equivalence import (
    STATUS as EQUIVALENCE_STATUS,
    canonical_json,
    file_sha256,
)


SCHEMA = "e2a-hf-cache-manifest-v1"
STATUS = "VERIFIED_IMMUTABLE_E2A_HF_CACHE"
MANIFEST_NAME = "e2a_hf_cache_manifest.json"


class CacheError(RuntimeError):
    pass


def checked_json(path: pathlib.Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise CacheError(f"expected JSON object: {path.name}")
    return value


def atomic_json(path: pathlib.Path, value: Any, mode: int = 0o600) -> None:
    if path.exists() or path.is_symlink():
        raise CacheError(f"output must be new: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = pathlib.Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical_json(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def within(root: pathlib.Path, path: pathlib.Path) -> bool:
    try:
        path.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        return False
    return True


def payload_entries(root: pathlib.Path) -> list[dict[str, Any]]:
    if not root.is_dir() or root.is_symlink():
        raise CacheError("cache root must be a non-symlink directory")
    entries: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if relative == MANIFEST_NAME:
            continue
        if path.is_symlink():
            target = os.readlink(path)
            if os.path.isabs(target) or not within(root, path):
                raise CacheError(f"cache symlink escapes or is broken: {relative}")
            entries.append({"path": relative, "type": "symlink", "target": target})
        elif path.is_file():
            entries.append({
                "path": relative,
                "type": "file",
                "size_bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            })
        elif path.is_dir():
            entries.append({"path": relative, "type": "directory"})
        else:
            raise CacheError(f"unsupported cache entry type: {relative}")
    return entries


def payload_sha256(entries: list[dict[str, Any]]) -> str:
    return hashlib.sha256(canonical_json(entries)).hexdigest()


def make_manifest(
    root: pathlib.Path, equivalence_receipt_sha256: str
) -> dict[str, Any]:
    entries = payload_entries(root)
    return {
        "schema_version": SCHEMA,
        "status": STATUS,
        "equivalence_receipt_sha256": equivalence_receipt_sha256,
        "entry_count": len(entries),
        "payload_sha256": payload_sha256(entries),
        "entries": entries,
    }


def require_read_only(root: pathlib.Path) -> None:
    for path in [root, *root.rglob("*")]:
        if path.is_symlink():
            continue
        if stat.S_IMODE(path.stat().st_mode) & 0o222:
            raise CacheError(f"cache entry remains writable: {path.relative_to(root)}")


def freeze_permissions(root: pathlib.Path) -> None:
    files: list[pathlib.Path] = []
    directories: list[pathlib.Path] = [root]
    for path in root.rglob("*"):
        if path.is_symlink():
            continue
        if path.is_dir():
            directories.append(path)
        elif path.is_file():
            files.append(path)
    for path in files:
        os.chmod(path, 0o444)
    for path in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        os.chmod(path, 0o555)


def thaw_for_cleanup(root: pathlib.Path) -> None:
    if not root.exists() or root.is_symlink():
        return
    for path in [root, *root.rglob("*")]:
        if not path.is_symlink():
            os.chmod(path, 0o755 if path.is_dir() else 0o600)


def require_relative_cache_path(path: pathlib.PurePosixPath, label: str) -> None:
    raw = path.as_posix()
    if (
        path.is_absolute() or not raw or "\\" in raw
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise CacheError(f"{label} must be a canonical relative POSIX cache path")


def verify_cache(
    root: pathlib.Path,
    expected_manifest_sha256: str | None = None,
    expected_payload_sha256: str | None = None,
    full: bool = True,
) -> dict[str, Any]:
    if not root.is_dir() or root.is_symlink():
        raise CacheError("cache root must be a non-symlink directory")
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise CacheError("cache manifest is missing or symlinked")
    manifest_sha = file_sha256(manifest_path)
    if expected_manifest_sha256 is not None and manifest_sha != expected_manifest_sha256:
        raise CacheError("cache manifest SHA-256 differs from contract")
    manifest = checked_json(manifest_path)
    required = {
        "schema_version", "status", "equivalence_receipt_sha256", "entry_count",
        "payload_sha256", "entries",
    }
    if set(manifest) != required or manifest["schema_version"] != SCHEMA or manifest[
        "status"
    ] != STATUS:
        raise CacheError("cache manifest schema/status differs")
    if expected_payload_sha256 is not None and manifest["payload_sha256"] != expected_payload_sha256:
        raise CacheError("cache payload SHA-256 differs from contract")
    if full:
        entries = payload_entries(root)
        if entries != manifest["entries"]:
            raise CacheError("cache payload entries differ from manifest")
        if len(entries) != manifest["entry_count"]:
            raise CacheError("cache manifest entry count differs")
        if payload_sha256(entries) != manifest["payload_sha256"]:
            raise CacheError("cache payload digest differs")
        require_read_only(root)
    return {
        "status": STATUS,
        "cache_root": root.resolve().as_posix(),
        "manifest_sha256": manifest_sha,
        "payload_sha256": manifest["payload_sha256"],
        "entry_count": manifest["entry_count"],
        "full_payload_verified": full,
        "read_only_verified": full,
    }


def verify_contract_cache(
    root: pathlib.Path, contract: dict[str, Any], full: bool = False
) -> dict[str, Any] | None:
    """Verify the E2 cache binding; legacy v1 contracts intentionally have no binding."""
    from phase1.balanced_continuation_real_contract import E2A_WORKER_CONTRACT_SCHEMA

    if contract.get("schema_version") != E2A_WORKER_CONTRACT_SCHEMA:
        return None
    if root.resolve().as_posix() != contract["hf_cache_path"]:
        raise CacheError("HF cache path differs from E2-A contract")
    return verify_cache(
        root,
        expected_manifest_sha256=contract["hf_cache_manifest_sha256"],
        expected_payload_sha256=contract["hf_cache_payload_sha256"],
        full=full,
    )


def materialize(
    source: pathlib.Path,
    output: pathlib.Path,
    pytorch_relative: pathlib.PurePosixPath,
    safetensors_relative: pathlib.PurePosixPath,
    equivalence_receipt_path: pathlib.Path,
) -> dict[str, Any]:
    if not source.is_dir() or source.is_symlink():
        raise CacheError("source cache must be a non-symlink directory")
    if output.exists() or output.is_symlink():
        raise CacheError("target cache must be new")
    require_relative_cache_path(pytorch_relative, "PyTorch path")
    require_relative_cache_path(safetensors_relative, "safetensors path")
    receipt = checked_json(equivalence_receipt_path)
    if (
        receipt.get("status") != EQUIVALENCE_STATUS
        or receipt.get("values_bitwise_identical") is not True
        or receipt.get("key_sets_identical") is not True
        or receipt.get("shapes_identical") is not True
        or receipt.get("dtypes_identical") is not True
    ):
        raise CacheError("tensor-equivalence receipt did not pass")
    pytorch_source = source / pathlib.Path(pytorch_relative)
    safetensors_source = source / pathlib.Path(safetensors_relative)
    if (
        not pytorch_source.is_file() or not safetensors_source.is_file()
        or not within(source, pytorch_source) or not within(source, safetensors_source)
    ):
        raise CacheError("checkpoint source paths are missing")
    if file_sha256(pytorch_source) != receipt.get("pytorch_sha256"):
        raise CacheError("PyTorch checkpoint differs from equivalence receipt")
    if file_sha256(safetensors_source) != receipt.get("safetensors_sha256"):
        raise CacheError("safetensors checkpoint differs from equivalence receipt")
    parts = pytorch_relative.parts
    if len(parts) < 5 or parts[-3] != "snapshots" or parts[-1] != "pytorch_model.bin":
        raise CacheError("PyTorch cache path is not a snapshot pytorch_model.bin")
    revision = parts[-2]
    repo_relative = pathlib.PurePosixPath(*parts[:-3])

    staging = output.parent / f".{output.name}.staging"
    if staging.exists() or staging.is_symlink():
        raise CacheError("target cache staging path already exists")
    try:
        shutil.copytree(source, staging, symlinks=True)
        target_pytorch = staging / pathlib.Path(pytorch_relative)
        target_safetensors_source = staging / pathlib.Path(safetensors_relative)
        target_model_safe = target_pytorch.parent / "model.safetensors"
        no_exist = staging / pathlib.Path(repo_relative) / ".no_exist" / revision / "model.safetensors"
        if target_pytorch.exists() or target_pytorch.is_symlink():
            target_pytorch.unlink()
        if no_exist.exists() or no_exist.is_symlink():
            no_exist.unlink()
        if target_model_safe.exists() or target_model_safe.is_symlink():
            target_model_safe.unlink()
        relative_target = os.path.relpath(target_safetensors_source.resolve(), target_model_safe.parent)
        target_model_safe.symlink_to(relative_target)
        if not within(staging, target_model_safe):
            raise CacheError("materialized safetensors link escaped cache")
        if file_sha256(target_model_safe) != receipt["safetensors_sha256"]:
            raise CacheError("materialized safetensors bytes differ")
        manifest = make_manifest(staging, file_sha256(equivalence_receipt_path))
        atomic_json(staging / MANIFEST_NAME, manifest, mode=0o444)
        freeze_permissions(staging)
        os.replace(staging, output)
    finally:
        if staging.exists():
            thaw_for_cleanup(staging)
            shutil.rmtree(staging, ignore_errors=True)
    return verify_cache(output, full=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("materialize")
    create.add_argument("--source", required=True)
    create.add_argument("--output", required=True)
    create.add_argument("--pytorch-relative", required=True)
    create.add_argument("--safetensors-relative", required=True)
    create.add_argument("--equivalence-receipt", required=True)
    create.add_argument("--receipt", required=True)
    check = sub.add_parser("verify")
    check.add_argument("--cache", required=True)
    check.add_argument("--expected-manifest-sha256")
    check.add_argument("--expected-payload-sha256")
    check.add_argument("--metadata-only", action="store_true")
    check.add_argument("--receipt", required=True)
    args = parser.parse_args()
    try:
        if args.command == "materialize":
            result = materialize(
                pathlib.Path(args.source).resolve(),
                pathlib.Path(args.output).resolve(),
                pathlib.PurePosixPath(args.pytorch_relative),
                pathlib.PurePosixPath(args.safetensors_relative),
                pathlib.Path(args.equivalence_receipt).resolve(),
            )
        else:
            result = verify_cache(
                pathlib.Path(args.cache).resolve(),
                args.expected_manifest_sha256,
                args.expected_payload_sha256,
                full=not args.metadata_only,
            )
        atomic_json(pathlib.Path(args.receipt).resolve(), result)
    except (CacheError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"E2A_HF_CACHE_ERROR: {exc}", file=sys.stderr)
        return 2
    print(canonical_json(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
