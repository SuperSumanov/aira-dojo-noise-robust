#!/usr/bin/env python3
"""Build an immutable, outcome-blind registry for explicit archive path aliases.

The builder reads only source-file metadata plus the already committed transaction
registry.  It deliberately does not hash or open alias archive payloads; the
production runner performs that byte-level equality check when applying the
registry.  This separation makes the exceptional disposition explicit without
turning arbitrary duplicate content into an automatic ignore rule.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from phase1.prospective_production_runner import (
    ALIAS_PROTOCOL,
    ALIAS_REASON_CODE,
    OBSERVER_PROTOCOL,
    ProductionError,
    canonical_json,
    load_latest,
    parse_utc,
    sha256,
)


DECLARATION_PROTOCOL = "prospective_archive_content_alias_declaration_v1"
DIAGNOSTIC_PROTOCOL = "prospective_archive_content_alias_diagnostic_v1"
COMMIT_RX = re.compile(r"[0-9a-f]{40}")
SHA_RX = re.compile(r"[0-9a-f]{64}")
DROP_RX = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
PAIR_KEYS = {"archive_relative_path", "canonical_archive_relative_path"}


class AliasRegistryBuildError(RuntimeError):
    pass


def hash_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def validate_relative(relative: Any) -> str:
    if not isinstance(relative, str):
        raise AliasRegistryBuildError("archive relative path is not a string")
    parts = PurePosixPath(relative).parts
    if (
        len(parts) != 2
        or any(part in {"", ".", ".."} for part in parts)
        or "\\" in relative
        or not relative.endswith(".tar.gz")
        or any(character in relative for character in "\r\n\t")
    ):
        raise AliasRegistryBuildError("invalid archive relative path")
    return relative


def load_declaration(
    path: Path,
    expected_sha256: str,
    expected_source_commit: str,
    expected_snapshot_sha256: str,
) -> tuple[list[dict[str, str]], str]:
    if not SHA_RX.fullmatch(expected_sha256):
        raise AliasRegistryBuildError("invalid expected declaration SHA-256")
    blob = path.read_bytes()
    actual_sha256 = hash_bytes(blob)
    if actual_sha256 != expected_sha256:
        raise AliasRegistryBuildError("alias declaration SHA mismatch")
    try:
        value = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AliasRegistryBuildError("cannot parse alias declaration") from error
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "protocol",
            "outcomes_read",
            "archive_payloads_opened",
            "source_commit",
            "snapshot_sha256",
            "entries",
        }
        or value.get("protocol") != DECLARATION_PROTOCOL
        or value.get("outcomes_read") is not False
        or value.get("archive_payloads_opened") is not False
        or value.get("source_commit") != expected_source_commit
        or value.get("snapshot_sha256") != expected_snapshot_sha256
        or not isinstance(value.get("entries"), list)
        or not value["entries"]
    ):
        raise AliasRegistryBuildError("alias declaration contract mismatch")

    pairs: list[dict[str, str]] = []
    aliases: set[str] = set()
    canonicals: set[str] = set()
    for index, pair in enumerate(value["entries"], 1):
        if not isinstance(pair, dict) or set(pair) != PAIR_KEYS:
            raise AliasRegistryBuildError(f"alias declaration schema mismatch at entry {index}")
        alias = validate_relative(pair["archive_relative_path"])
        canonical = validate_relative(pair["canonical_archive_relative_path"])
        if alias == canonical or PurePosixPath(alias).name != PurePosixPath(canonical).name:
            raise AliasRegistryBuildError(f"alias/canonical basename mismatch at entry {index}")
        if alias in aliases or canonical in canonicals:
            raise AliasRegistryBuildError(f"duplicate alias declaration identity at entry {index}")
        aliases.add(alias)
        canonicals.add(canonical)
        pairs.append(
            {
                "archive_relative_path": alias,
                "canonical_archive_relative_path": canonical,
            }
        )
    if [pair["archive_relative_path"] for pair in pairs] != sorted(aliases):
        raise AliasRegistryBuildError("alias declaration entries are not sorted")
    return pairs, actual_sha256


def _checked_entry_path(source_root: Path, relative: str, entry: dict[str, Any]) -> Path:
    expected_path = (source_root / PurePosixPath(relative)).resolve()
    try:
        raw_path = Path(entry["path"])
        if raw_path.is_symlink() or not raw_path.is_file():
            raise AliasRegistryBuildError(f"observed archive path is absent or unsafe: {relative}")
        actual_path = raw_path.resolve()
    except (KeyError, TypeError, OSError) as error:
        raise AliasRegistryBuildError(f"invalid observation path: {relative}") from error
    if actual_path != expected_path:
        raise AliasRegistryBuildError(f"observed archive path is absent or unsafe: {relative}")
    stat = actual_path.stat()
    if stat.st_size != entry.get("size") or stat.st_mtime_ns != entry.get("mtime_ns"):
        raise AliasRegistryBuildError(f"observed archive metadata drifted: {relative}")
    return actual_path


def build_artifacts(
    *,
    source_root: Path,
    observations: dict[str, Any],
    transactions: list[dict[str, Any]],
    pairs: list[dict[str, str]],
    source_commit: str,
    snapshot_sha256: str,
    declaration_sha256: str,
    observations_sha256: str,
    transactions_sha256: str,
    diagnostic_receipt_file: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not COMMIT_RX.fullmatch(source_commit):
        raise AliasRegistryBuildError("invalid source commit")
    for label, value in (
        ("snapshot", snapshot_sha256),
        ("declaration", declaration_sha256),
        ("observations", observations_sha256),
        ("transactions", transactions_sha256),
    ):
        if not SHA_RX.fullmatch(value):
            raise AliasRegistryBuildError(f"invalid {label} SHA-256")
    if Path(diagnostic_receipt_file).name != diagnostic_receipt_file or not diagnostic_receipt_file.endswith(
        ".json"
    ):
        raise AliasRegistryBuildError("invalid diagnostic receipt filename")
    if (
        not isinstance(observations, dict)
        or observations.get("protocol") != OBSERVER_PROTOCOL
        or observations.get("source_root") != str(source_root.resolve())
        or not isinstance(observations.get("entries"), dict)
    ):
        raise AliasRegistryBuildError("observation ledger contract mismatch")

    transaction_by_relative = {
        row["archive_relative_path"]: row for row in transactions
    }
    if len(transaction_by_relative) != len(transactions):
        raise AliasRegistryBuildError("duplicate transaction relative path")

    registry_entries: list[dict[str, Any]] = []
    diagnostic_entries: list[dict[str, Any]] = []
    seen_shas: set[str] = set()
    for pair in pairs:
        alias = pair["archive_relative_path"]
        canonical = pair["canonical_archive_relative_path"]
        alias_entry = observations["entries"].get(alias)
        canonical_entry = observations["entries"].get(canonical)
        transaction = transaction_by_relative.get(canonical)
        if not isinstance(alias_entry, dict) or alias_entry.get("present") is not True:
            raise AliasRegistryBuildError(f"alias observation is absent: {alias}")
        if not isinstance(canonical_entry, dict) or canonical_entry.get("present") is not True:
            raise AliasRegistryBuildError(f"canonical observation is absent: {canonical}")
        if transaction is None:
            raise AliasRegistryBuildError(f"canonical transaction is absent: {canonical}")
        if (
            alias_entry.get("baseline") is True
            or alias_entry.get("committed_archive_sha256") is not None
            or alias_entry.get("rejected_archive_sha256") is not None
        ):
            raise AliasRegistryBuildError(f"alias already has a disposition: {alias}")
        archive_sha256 = transaction.get("archive_sha256")
        archive_size = transaction.get("archive_size")
        if (
            not isinstance(archive_sha256, str)
            or not SHA_RX.fullmatch(archive_sha256)
            or archive_sha256 in seen_shas
            or isinstance(archive_size, bool)
            or not isinstance(archive_size, int)
            or archive_size < 0
        ):
            raise AliasRegistryBuildError(f"invalid canonical transaction identity: {canonical}")
        if (
            canonical_entry.get("committed_archive_sha256") != archive_sha256
            or alias_entry.get("size") != archive_size
            or canonical_entry.get("size") != archive_size
        ):
            raise AliasRegistryBuildError(f"alias/canonical metadata binding mismatch: {alias}")
        drop_id = transaction.get("drop_id")
        committed_at = transaction.get("committed_at_utc")
        if (
            not isinstance(drop_id, str)
            or not DROP_RX.fullmatch(drop_id)
            or not isinstance(committed_at, str)
        ):
            raise AliasRegistryBuildError(f"invalid canonical transaction metadata: {canonical}")
        try:
            parse_utc(committed_at)
        except ProductionError as error:
            raise AliasRegistryBuildError(
                f"invalid canonical transaction time: {canonical}"
            ) from error
        _checked_entry_path(source_root, alias, alias_entry)
        _checked_entry_path(source_root, canonical, canonical_entry)
        seen_shas.add(archive_sha256)
        registry_entries.append(
            {
                "archive_mtime_ns": alias_entry["mtime_ns"],
                "archive_relative_path": alias,
                "archive_sha256": archive_sha256,
                "archive_size": archive_size,
                "canonical_archive_relative_path": canonical,
                "canonical_drop_id": drop_id,
                "canonical_transaction_committed_at_utc": committed_at,
                "diagnostic_receipt_file": diagnostic_receipt_file,
                "diagnostic_receipt_sha256": "__BOUND_AFTER_RECEIPT_WRITE__",
                "reason_code": ALIAS_REASON_CODE,
            }
        )
        diagnostic_entries.append(
            {
                "archive_mtime_ns": alias_entry["mtime_ns"],
                "archive_relative_path": alias,
                "archive_size": archive_size,
                "canonical_archive_relative_path": canonical,
                "canonical_archive_sha256": archive_sha256,
                "canonical_drop_id": drop_id,
                "canonical_transaction_committed_at_utc": committed_at,
            }
        )

    diagnostic = {
        "protocol": DIAGNOSTIC_PROTOCOL,
        "status": "EXPLICIT_ARCHIVE_CONTENT_ALIASES_SUPPORTED",
        "source_commit": source_commit,
        "snapshot_sha256": snapshot_sha256,
        "inputs": {
            "declaration_sha256": declaration_sha256,
            "observations_file": "observations_before.json",
            "observations_sha256": observations_sha256,
            "transactions_sha256": transactions_sha256,
        },
        "alias_count": len(diagnostic_entries),
        "transaction_count": len(transactions),
        "entries": diagnostic_entries,
        "outcomes_read": False,
        "archive_payloads_opened": False,
        "alias_payload_hashes_read": False,
        "alias_payload_hash_verification_deferred_to_runner": True,
        "automatic_duplicate_disposition_enabled": False,
    }
    return diagnostic, {
        "protocol": ALIAS_PROTOCOL,
        "outcomes_read": False,
        "archive_payloads_opened": False,
        "entries": registry_entries,
    }


def write_new(path: Path, blob: bytes) -> None:
    if path.exists():
        raise AliasRegistryBuildError(f"output exists: {path.name}")
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    with temporary.open("xb") as handle:
        handle.write(blob)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--declaration", required=True, type=Path)
    parser.add_argument("--expect-declaration-sha256", required=True)
    parser.add_argument("--expect-source-commit", required=True)
    parser.add_argument("--expect-latest-snapshot-sha256", required=True)
    parser.add_argument("--expect-observations-sha256", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        source_root = args.source_root.resolve()
        state_root = args.state_root.resolve()
        if not source_root.is_dir() or not state_root.is_dir():
            raise AliasRegistryBuildError("source or state root is unavailable")
        pairs, declaration_sha = load_declaration(
            args.declaration.resolve(),
            args.expect_declaration_sha256,
            args.expect_source_commit,
            args.expect_latest_snapshot_sha256,
        )
        observations_path = state_root / "observations.json"
        observations_blob = observations_path.read_bytes()
        observations_sha = hash_bytes(observations_blob)
        if observations_sha != args.expect_observations_sha256:
            raise AliasRegistryBuildError("observation ledger SHA mismatch")
        observations = json.loads(observations_blob.decode("utf-8"))
        transactions, latest_sha = load_latest(state_root)
        if latest_sha != args.expect_latest_snapshot_sha256:
            raise AliasRegistryBuildError("LATEST snapshot changed")
        transactions_path = state_root / "snapshots" / latest_sha / "transactions.jsonl"
        transactions_sha = sha256(transactions_path)
        receipt_name = "archive_content_alias_diagnostic.json"
        diagnostic, registry = build_artifacts(
            source_root=source_root,
            observations=observations,
            transactions=transactions,
            pairs=pairs,
            source_commit=args.expect_source_commit,
            snapshot_sha256=latest_sha,
            declaration_sha256=declaration_sha,
            observations_sha256=observations_sha,
            transactions_sha256=transactions_sha,
            diagnostic_receipt_file=receipt_name,
        )
        output_dir = args.output_dir.resolve()
        output_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
        write_new(output_dir / "observations_before.json", observations_blob)
        receipt_path = output_dir / receipt_name
        receipt_blob = canonical_json(diagnostic)
        write_new(receipt_path, receipt_blob)
        receipt_sha = hash_bytes(receipt_blob)
        for row in registry["entries"]:
            row["diagnostic_receipt_sha256"] = receipt_sha
        registry_path = output_dir / "archive_content_alias_registry.json"
        registry_blob = canonical_json(registry)
        write_new(registry_path, registry_blob)
        summary = {
            "alias_count": len(registry["entries"]),
            "diagnostic_receipt_sha256": receipt_sha,
            "registry_sha256": hash_bytes(registry_blob),
            "snapshot_sha256": latest_sha,
            "outcomes_read": False,
            "archive_payloads_opened": False,
            "alias_payload_hashes_read": False,
        }
        write_new(output_dir / "build_summary.json", canonical_json(summary))
        write_new(output_dir / "BUILD_COMPLETE", b"")
        print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError, ProductionError, AliasRegistryBuildError) as error:
        print(f"ARCHIVE_CONTENT_ALIAS_REGISTRY_ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
