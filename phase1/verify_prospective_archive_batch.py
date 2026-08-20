#!/usr/bin/env python3
"""Verify an immutable source-archive batch against the outcome-blind observer ledger."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any


PROTOCOL = "prospective_archive_batch_manifest_v1"
OBSERVER_PROTOCOL = "prospective_archive_observer_v1"
SHA_RX = re.compile(r"[0-9a-f]{64}")


class BatchVerificationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BatchVerificationError(f"cannot parse {label}") from exc
    if not isinstance(value, dict):
        raise BatchVerificationError(f"{label} is not an object")
    return value


def load_manifest(path: Path, expected_sha256: str) -> list[dict[str, Any]]:
    if not SHA_RX.fullmatch(expected_sha256) or sha256(path) != expected_sha256:
        raise BatchVerificationError("batch manifest SHA mismatch")
    value = read_object(path, "batch manifest")
    if (
        set(value) != {"protocol", "outcomes_read", "entries"}
        or value["protocol"] != PROTOCOL
        or value["outcomes_read"] is not False
        or not isinstance(value["entries"], list)
        or not value["entries"]
    ):
        raise BatchVerificationError("batch manifest contract mismatch")
    rows: list[dict[str, Any]] = []
    seen_relative: set[str] = set()
    seen_sha: set[str] = set()
    expected_keys = {
        "archive_mtime_ns",
        "archive_relative_path",
        "archive_sha256",
        "archive_size",
    }
    for index, row in enumerate(value["entries"], 1):
        if not isinstance(row, dict) or set(row) != expected_keys:
            raise BatchVerificationError(f"manifest schema mismatch at entry {index}")
        relative = row["archive_relative_path"]
        parts = PurePosixPath(relative).parts if isinstance(relative, str) else ()
        if (
            len(parts) != 2
            or any(part in {"", ".", ".."} for part in parts)
            or not relative.endswith(".tar.gz")
        ):
            raise BatchVerificationError(f"invalid archive path at entry {index}")
        archive_sha = row["archive_sha256"]
        if not isinstance(archive_sha, str) or not SHA_RX.fullmatch(archive_sha):
            raise BatchVerificationError(f"invalid archive SHA at entry {index}")
        if relative in seen_relative or archive_sha in seen_sha:
            raise BatchVerificationError(f"duplicate archive identity at entry {index}")
        for key in ("archive_size", "archive_mtime_ns"):
            if isinstance(row[key], bool) or not isinstance(row[key], int) or row[key] < 0:
                raise BatchVerificationError(f"invalid {key} at entry {index}")
        seen_relative.add(relative)
        seen_sha.add(archive_sha)
        rows.append(row)
    if [row["archive_relative_path"] for row in rows] != sorted(seen_relative):
        raise BatchVerificationError("batch manifest is not path-sorted")
    return rows


def verify(
    source_root: Path,
    state_root: Path,
    manifest: Path,
    expected_manifest_sha256: str,
    hash_source_archives: bool,
) -> dict[str, Any]:
    source_root = source_root.resolve()
    state_root = state_root.resolve()
    rows = load_manifest(manifest.resolve(), expected_manifest_sha256)
    observations = read_object(state_root / "observations.json", "observation ledger")
    if (
        set(observations) != {"protocol", "source_root", "baseline_sealed_at_epoch", "entries"}
        or observations["protocol"] != OBSERVER_PROTOCOL
        or observations["source_root"] != str(source_root)
        or not isinstance(observations["entries"], dict)
    ):
        raise BatchVerificationError("observation ledger contract mismatch")

    states = {"committed": 0, "rejected": 0, "pending": 0}
    per_archive: list[dict[str, Any]] = []
    for row in rows:
        relative = row["archive_relative_path"]
        archive = (source_root / PurePosixPath(relative)).resolve()
        if archive.parent.parent != source_root or not archive.is_file() or archive.is_symlink():
            raise BatchVerificationError(f"source archive path binding mismatch: {relative}")
        stat = archive.stat()
        if stat.st_size != row["archive_size"] or stat.st_mtime_ns != row["archive_mtime_ns"]:
            raise BatchVerificationError(f"source archive metadata mismatch: {relative}")
        if hash_source_archives and sha256(archive) != row["archive_sha256"]:
            raise BatchVerificationError(f"source archive hash mismatch: {relative}")

        entry = observations["entries"].get(relative)
        if not isinstance(entry, dict) or entry.get("present") is not True:
            raise BatchVerificationError(f"archive absent from observation ledger: {relative}")
        if entry.get("baseline") is True:
            raise BatchVerificationError(f"planned archive marked baseline: {relative}")
        if entry.get("size") != row["archive_size"] or entry.get("mtime_ns") != row["archive_mtime_ns"]:
            raise BatchVerificationError(f"observer metadata mismatch: {relative}")
        if Path(str(entry.get("path"))).resolve() != archive:
            raise BatchVerificationError(f"observer path mismatch: {relative}")

        committed = entry.get("committed_archive_sha256")
        rejected = entry.get("rejected_archive_sha256")
        if committed is not None and rejected is not None:
            raise BatchVerificationError(f"archive both committed and rejected: {relative}")
        if committed is not None:
            if committed != row["archive_sha256"] or entry.get("committed_snapshot_sha256") is None:
                raise BatchVerificationError(f"committed binding mismatch: {relative}")
            state = "committed"
        elif rejected is not None:
            if (
                rejected != row["archive_sha256"]
                or entry.get("rejection_reason_code") is None
                or entry.get("rejection_registry_sha256") is None
            ):
                raise BatchVerificationError(f"rejection binding mismatch: {relative}")
            state = "rejected"
        else:
            if any(
                entry.get(key) is not None
                for key in (
                    "committed_snapshot_sha256",
                    "rejection_reason_code",
                    "rejection_registry_sha256",
                )
            ):
                raise BatchVerificationError(f"partial archive disposition: {relative}")
            state = "pending"
        states[state] += 1
        per_archive.append({"archive_relative_path": relative, "state": state})

    return {
        "protocol": "prospective_archive_batch_verification_v1",
        "status": "BATCH_RESOLVED" if states["pending"] == 0 else "BATCH_PENDING",
        "manifest_sha256": expected_manifest_sha256,
        "archives": len(rows),
        "states": states,
        "per_archive": per_archive,
        "source_archives_hashed": hash_source_archives,
        "security": {
            "outcomes_read": False,
            "archive_payload_interpreted": False,
            "label_vault_opened": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--expect-manifest-sha256", required=True)
    parser.add_argument("--hash-source-archives", action="store_true")
    parser.add_argument("--require-resolved", action="store_true")
    args = parser.parse_args()
    try:
        receipt = verify(
            args.source_root,
            args.state_root,
            args.manifest,
            args.expect_manifest_sha256,
            args.hash_source_archives,
        )
        print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
        if args.require_resolved and receipt["status"] != "BATCH_RESOLVED":
            return 3
        return 0
    except (OSError, BatchVerificationError) as exc:
        print(f"PROSPECTIVE_ARCHIVE_BATCH_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
