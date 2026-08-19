"""Independently verify an E2-A HF cache without importing its materializer."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import stat
import sys
import tempfile
from typing import Any


MANIFEST_NAME = "e2a_hf_cache_manifest.json"
MANIFEST_SCHEMA = "e2a-hf-cache-manifest-v1"
MANIFEST_STATUS = "VERIFIED_IMMUTABLE_E2A_HF_CACHE"
STATUS = "INDEPENDENTLY_VERIFIED_IMMUTABLE_E2A_HF_CACHE"


class IndependentCacheError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def file_sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inside(root: pathlib.Path, path: pathlib.Path) -> bool:
    try:
        path.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        return False
    return True


def reconstruct_entries(root: pathlib.Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    paths = sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix())
    for path in paths:
        relative = path.relative_to(root).as_posix()
        if relative == MANIFEST_NAME:
            continue
        if path.is_symlink():
            target = os.readlink(path)
            if os.path.isabs(target) or not inside(root, path):
                raise IndependentCacheError(f"escaping or broken symlink: {relative}")
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
            raise IndependentCacheError(f"unsupported entry type: {relative}")
    return entries


def verify(
    root: pathlib.Path,
    expected_manifest_sha256: str,
    expected_payload_sha256: str,
    full: bool,
) -> dict[str, Any]:
    if not root.is_dir() or root.is_symlink():
        raise IndependentCacheError("cache root must be a non-symlink directory")
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise IndependentCacheError("cache manifest is missing or symlinked")
    manifest_sha = file_sha256(manifest_path)
    if manifest_sha != expected_manifest_sha256:
        raise IndependentCacheError("manifest SHA differs")
    manifest = json.loads(manifest_path.read_bytes())
    expected_keys = {
        "schema_version", "status", "equivalence_receipt_sha256", "entry_count",
        "payload_sha256", "entries",
    }
    if (
        not isinstance(manifest, dict) or set(manifest) != expected_keys
        or manifest["schema_version"] != MANIFEST_SCHEMA
        or manifest["status"] != MANIFEST_STATUS
        or manifest["payload_sha256"] != expected_payload_sha256
    ):
        raise IndependentCacheError("manifest schema/status/payload binding differs")
    if full:
        reconstructed = reconstruct_entries(root)
        reconstructed_payload_sha = hashlib.sha256(canonical_json(reconstructed)).hexdigest()
        if reconstructed != manifest["entries"]:
            raise IndependentCacheError("reconstructed payload entries differ")
        if len(reconstructed) != manifest["entry_count"]:
            raise IndependentCacheError("reconstructed entry count differs")
        if reconstructed_payload_sha != expected_payload_sha256:
            raise IndependentCacheError("reconstructed payload SHA differs")
        for path in [root, *root.rglob("*")]:
            if not path.is_symlink() and stat.S_IMODE(path.stat().st_mode) & 0o222:
                raise IndependentCacheError(
                    f"writable cache entry: {path.relative_to(root).as_posix()}"
                )
    return {
        "status": STATUS,
        "cache_root": root.resolve().as_posix(),
        "manifest_sha256": manifest_sha,
        "payload_sha256": manifest["payload_sha256"],
        "entry_count": manifest["entry_count"],
        "full_payload_verified": full,
        "read_only_verified": full,
        "materializer_imported": False,
    }


def verify_contract_cache_independent(
    root: pathlib.Path, contract: dict[str, Any], full: bool = False
) -> dict[str, Any] | None:
    from phase1.balanced_continuation_real_contract import E2A_WORKER_CONTRACT_SCHEMA

    if contract.get("schema_version") != E2A_WORKER_CONTRACT_SCHEMA:
        return None
    if root.resolve().as_posix() != contract["hf_cache_path"]:
        raise IndependentCacheError("HF cache path differs from contract")
    return verify(
        root,
        contract["hf_cache_manifest_sha256"],
        contract["hf_cache_payload_sha256"],
        full,
    )


def atomic_json(path: pathlib.Path, value: Any) -> None:
    if path.exists() or path.is_symlink():
        raise IndependentCacheError("independent verification receipt must be new")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = pathlib.Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical_json(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--expected-payload-sha256", required=True)
    parser.add_argument("--metadata-only", action="store_true")
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args()
    try:
        result = verify(
            pathlib.Path(args.cache).resolve(),
            args.expected_manifest_sha256,
            args.expected_payload_sha256,
            full=not args.metadata_only,
        )
        atomic_json(pathlib.Path(args.receipt).resolve(), result)
    except (IndependentCacheError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"INDEPENDENT_E2A_HF_CACHE_ERROR: {exc}", file=sys.stderr)
        return 2
    print(canonical_json(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
