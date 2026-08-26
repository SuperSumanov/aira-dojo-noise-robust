#!/usr/bin/env python3
"""Independently verify one explicit archive-content alias disposition bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any


DECLARATION_PROTOCOL = "prospective_archive_content_alias_declaration_v1"
DIAGNOSTIC_PROTOCOL = "prospective_archive_content_alias_diagnostic_v1"
REGISTRY_PROTOCOL = "prospective_archive_content_alias_v1"
OBSERVER_PROTOCOL = "prospective_archive_observer_v1"
REASON_CODE = "ARCHIVE_BYTES_DUPLICATE_COMMITTED_TRANSACTION"
SHA_RX = re.compile(r"[0-9a-f]{64}")
DECLARATION_KEYS = {
    "protocol",
    "outcomes_read",
    "archive_payloads_opened",
    "source_commit",
    "snapshot_sha256",
    "entries",
}
REGISTRY_ROW_KEYS = {
    "archive_mtime_ns",
    "archive_relative_path",
    "archive_sha256",
    "archive_size",
    "canonical_archive_relative_path",
    "canonical_drop_id",
    "canonical_transaction_committed_at_utc",
    "diagnostic_receipt_file",
    "diagnostic_receipt_sha256",
    "reason_code",
}


class AliasVerificationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AliasVerificationError(f"cannot parse JSON object: {path.name}") from error
    if not isinstance(value, dict):
        raise AliasVerificationError(f"JSON root is not an object: {path.name}")
    return value


def validate_relative(value: Any) -> str:
    if not isinstance(value, str):
        raise AliasVerificationError("archive relative path is not a string")
    parts = PurePosixPath(value).parts
    if (
        len(parts) != 2
        or any(part in {"", ".", ".."} for part in parts)
        or "\\" in value
        or not value.endswith(".tar.gz")
        or any(character in value for character in "\r\n\t")
    ):
        raise AliasVerificationError("invalid archive relative path")
    return value


def parse_transactions(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_relative: set[str] = set()
    seen_sha: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line:
            raise AliasVerificationError(f"blank transaction line {line_number}")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise AliasVerificationError(f"invalid transaction line {line_number}") from error
        if not isinstance(row, dict):
            raise AliasVerificationError(f"transaction is not an object at line {line_number}")
        relative = validate_relative(row.get("archive_relative_path"))
        archive_sha = row.get("archive_sha256")
        if (
            not isinstance(archive_sha, str)
            or not SHA_RX.fullmatch(archive_sha)
            or relative in seen_relative
            or archive_sha in seen_sha
        ):
            raise AliasVerificationError(f"invalid transaction identity at line {line_number}")
        seen_relative.add(relative)
        seen_sha.add(archive_sha)
        rows.append(row)
    if not rows:
        raise AliasVerificationError("transaction registry is empty")
    return rows


def checked_archive(source_root: Path, relative: str, entry: dict[str, Any]) -> Path:
    expected = (source_root / PurePosixPath(relative)).resolve()
    raw = Path(entry.get("path", ""))
    if raw.is_symlink() or not raw.is_file():
        raise AliasVerificationError(f"archive path is absent or unsafe: {relative}")
    actual = raw.resolve()
    if actual != expected:
        raise AliasVerificationError(f"archive path is absent or unsafe: {relative}")
    stat = actual.stat()
    if stat.st_size != entry.get("size") or stat.st_mtime_ns != entry.get("mtime_ns"):
        raise AliasVerificationError(f"archive metadata drifted: {relative}")
    return actual


def stable_sha256(path: Path, expected_size: int, expected_mtime_ns: int) -> str:
    before = path.stat()
    if before.st_size != expected_size or before.st_mtime_ns != expected_mtime_ns:
        raise AliasVerificationError(f"archive metadata changed before hash: {path.name}")
    digest = sha256(path)
    after = path.stat()
    if after.st_size != before.st_size or after.st_mtime_ns != before.st_mtime_ns:
        raise AliasVerificationError(f"archive metadata changed during hash: {path.name}")
    return digest


def verify(
    *,
    source_root: Path,
    state_root: Path,
    declaration_path: Path,
    expected_declaration_sha256: str,
    registry_path: Path,
    expected_registry_sha256: str,
    expected_source_commit: str,
    expected_snapshot_sha256: str,
    expected_disposition: str,
) -> dict[str, Any]:
    for label, value in (
        ("declaration", expected_declaration_sha256),
        ("registry", expected_registry_sha256),
        ("snapshot", expected_snapshot_sha256),
    ):
        if not SHA_RX.fullmatch(value):
            raise AliasVerificationError(f"invalid expected {label} SHA-256")
    if expected_disposition not in {"unapplied", "applied"}:
        raise AliasVerificationError("invalid expected disposition")
    if sha256(declaration_path) != expected_declaration_sha256:
        raise AliasVerificationError("declaration SHA mismatch")
    if sha256(registry_path) != expected_registry_sha256:
        raise AliasVerificationError("registry SHA mismatch")
    declaration = read_object(declaration_path)
    registry = read_object(registry_path)
    if (
        set(declaration) != DECLARATION_KEYS
        or declaration.get("protocol") != DECLARATION_PROTOCOL
        or declaration.get("source_commit") != expected_source_commit
        or declaration.get("snapshot_sha256") != expected_snapshot_sha256
        or declaration.get("outcomes_read") is not False
        or declaration.get("archive_payloads_opened") is not False
        or not isinstance(declaration.get("entries"), list)
        or not declaration["entries"]
    ):
        raise AliasVerificationError("declaration contract mismatch")
    if (
        set(registry) != {"protocol", "outcomes_read", "archive_payloads_opened", "entries"}
        or registry.get("protocol") != REGISTRY_PROTOCOL
        or registry.get("outcomes_read") is not False
        or registry.get("archive_payloads_opened") is not False
        or not isinstance(registry.get("entries"), list)
        or not registry["entries"]
    ):
        raise AliasVerificationError("registry contract mismatch")
    if len(declaration["entries"]) != len(registry["entries"]):
        raise AliasVerificationError("declaration/registry count mismatch")

    receipt_names = {row.get("diagnostic_receipt_file") for row in registry["entries"]}
    receipt_shas = {row.get("diagnostic_receipt_sha256") for row in registry["entries"]}
    if len(receipt_names) != 1 or len(receipt_shas) != 1:
        raise AliasVerificationError("registry diagnostic binding is not singular")
    receipt_name = next(iter(receipt_names))
    receipt_sha = next(iter(receipt_shas))
    if (
        not isinstance(receipt_name, str)
        or Path(receipt_name).name != receipt_name
        or not isinstance(receipt_sha, str)
        or not SHA_RX.fullmatch(receipt_sha)
    ):
        raise AliasVerificationError("invalid registry diagnostic binding")
    receipt_path = registry_path.parent / receipt_name
    if sha256(receipt_path) != receipt_sha:
        raise AliasVerificationError("diagnostic receipt SHA mismatch")
    diagnostic = read_object(receipt_path)
    expected_diagnostic_flags = {
        "outcomes_read": False,
        "archive_payloads_opened": False,
        "alias_payload_hashes_read": False,
        "alias_payload_hash_verification_deferred_to_runner": True,
        "automatic_duplicate_disposition_enabled": False,
    }
    if (
        diagnostic.get("protocol") != DIAGNOSTIC_PROTOCOL
        or diagnostic.get("status") != "EXPLICIT_ARCHIVE_CONTENT_ALIASES_SUPPORTED"
        or diagnostic.get("source_commit") != expected_source_commit
        or diagnostic.get("snapshot_sha256") != expected_snapshot_sha256
        or any(diagnostic.get(key) is not value for key, value in expected_diagnostic_flags.items())
        or diagnostic.get("alias_count") != len(registry["entries"])
        or diagnostic.get("transaction_count") is None
        or not isinstance(diagnostic.get("entries"), list)
        or len(diagnostic.get("entries", [])) != len(registry["entries"])
    ):
        raise AliasVerificationError("diagnostic receipt contract mismatch")
    inputs = diagnostic.get("inputs")
    if not isinstance(inputs, dict) or inputs.get("declaration_sha256") != expected_declaration_sha256:
        raise AliasVerificationError("diagnostic input binding mismatch")
    observations_file = inputs.get("observations_file")
    if not isinstance(observations_file, str) or Path(observations_file).name != observations_file:
        raise AliasVerificationError("invalid pre-application observation binding")
    observations_before_path = registry_path.parent / observations_file
    if sha256(observations_before_path) != inputs.get("observations_sha256"):
        raise AliasVerificationError("pre-application observation SHA mismatch")

    latest = (state_root / "LATEST").read_text(encoding="ascii").strip()
    if latest != expected_snapshot_sha256:
        raise AliasVerificationError("LATEST snapshot changed")
    snapshot_root = state_root / "snapshots" / latest
    manifest = snapshot_root / "SHA256SUMS"
    if sha256(manifest) != latest:
        raise AliasVerificationError("snapshot manifest identity mismatch")
    transactions_path = snapshot_root / "transactions.jsonl"
    if sha256(transactions_path) != inputs.get("transactions_sha256"):
        raise AliasVerificationError("transaction registry SHA mismatch")
    transactions = parse_transactions(transactions_path)
    if diagnostic.get("transaction_count") != len(transactions):
        raise AliasVerificationError("transaction count changed")
    transaction_by_relative = {row["archive_relative_path"]: row for row in transactions}
    observations_before = read_object(observations_before_path)
    observations_current = read_object(state_root / "observations.json")
    for name, observations in (
        ("pre-application", observations_before),
        ("current", observations_current),
    ):
        if (
            observations.get("protocol") != OBSERVER_PROTOCOL
            or observations.get("source_root") != str(source_root.resolve())
            or not isinstance(observations.get("entries"), dict)
        ):
            raise AliasVerificationError(f"{name} observation contract mismatch")

    declared_pairs = []
    total_bytes = 0
    for index, (declaration_row, registry_row, diagnostic_row) in enumerate(
        zip(declaration["entries"], registry["entries"], diagnostic["entries"], strict=True),
        1,
    ):
        if (
            not isinstance(declaration_row, dict)
            or set(declaration_row)
            != {"archive_relative_path", "canonical_archive_relative_path"}
            or not isinstance(registry_row, dict)
            or set(registry_row) != REGISTRY_ROW_KEYS
            or not isinstance(diagnostic_row, dict)
        ):
            raise AliasVerificationError(f"entry schema mismatch at entry {index}")
        alias = validate_relative(declaration_row.get("archive_relative_path"))
        canonical = validate_relative(declaration_row.get("canonical_archive_relative_path"))
        if alias == canonical or PurePosixPath(alias).name != PurePosixPath(canonical).name:
            raise AliasVerificationError(f"declared basename mismatch at entry {index}")
        declared_pairs.append(alias)
        if registry_row.get("archive_relative_path") != alias or registry_row.get(
            "canonical_archive_relative_path"
        ) != canonical:
            raise AliasVerificationError(f"registry pair mismatch at entry {index}")
        if registry_row.get("reason_code") != REASON_CODE:
            raise AliasVerificationError(f"registry reason mismatch at entry {index}")
        transaction = transaction_by_relative.get(canonical)
        if transaction is None or alias in transaction_by_relative:
            raise AliasVerificationError(f"transaction partition mismatch at entry {index}")
        archive_sha = registry_row.get("archive_sha256")
        archive_size = registry_row.get("archive_size")
        expected_diagnostic_row = {
            "archive_mtime_ns": registry_row.get("archive_mtime_ns"),
            "archive_relative_path": alias,
            "archive_size": archive_size,
            "canonical_archive_relative_path": canonical,
            "canonical_archive_sha256": archive_sha,
            "canonical_drop_id": registry_row.get("canonical_drop_id"),
            "canonical_transaction_committed_at_utc": registry_row.get(
                "canonical_transaction_committed_at_utc"
            ),
        }
        if diagnostic_row != expected_diagnostic_row:
            raise AliasVerificationError(f"diagnostic entry mismatch at entry {index}")
        if (
            transaction.get("archive_sha256") != archive_sha
            or transaction.get("archive_size") != archive_size
            or transaction.get("drop_id") != registry_row.get("canonical_drop_id")
            or transaction.get("committed_at_utc")
            != registry_row.get("canonical_transaction_committed_at_utc")
        ):
            raise AliasVerificationError(f"canonical transaction mismatch at entry {index}")
        before_alias = observations_before["entries"].get(alias)
        before_canonical = observations_before["entries"].get(canonical)
        current_alias = observations_current["entries"].get(alias)
        current_canonical = observations_current["entries"].get(canonical)
        if not all(
            isinstance(entry, dict)
            for entry in (before_alias, before_canonical, current_alias, current_canonical)
        ):
            raise AliasVerificationError(f"observation entry absent at entry {index}")
        if (
            before_alias.get("baseline") is True
            or before_alias.get("committed_archive_sha256") is not None
            or before_alias.get("rejected_archive_sha256") is not None
            or before_canonical.get("committed_archive_sha256") != archive_sha
            or current_canonical.get("committed_archive_sha256") != archive_sha
        ):
            raise AliasVerificationError(f"observation partition mismatch at entry {index}")
        if (
            before_alias.get("size") != archive_size
            or before_alias.get("mtime_ns") != registry_row.get("archive_mtime_ns")
            or before_canonical.get("size") != archive_size
            or current_alias.get("size") != archive_size
            or current_alias.get("mtime_ns") != registry_row.get("archive_mtime_ns")
            or current_canonical.get("size") != archive_size
        ):
            raise AliasVerificationError(f"observation metadata mismatch at entry {index}")
        expected_rejection = (
            (None, None, None)
            if expected_disposition == "unapplied"
            else (archive_sha, REASON_CODE, expected_registry_sha256)
        )
        current_rejection = (
            current_alias.get("rejected_archive_sha256"),
            current_alias.get("rejection_reason_code"),
            current_alias.get("rejection_registry_sha256"),
        )
        if current_alias.get("committed_archive_sha256") is not None or current_rejection != expected_rejection:
            raise AliasVerificationError(f"alias disposition mismatch at entry {index}")
        alias_path = checked_archive(source_root, alias, current_alias)
        canonical_path = checked_archive(source_root, canonical, current_canonical)
        if (
            stable_sha256(
                alias_path,
                archive_size,
                registry_row["archive_mtime_ns"],
            )
            != archive_sha
            or stable_sha256(
                canonical_path,
                archive_size,
                current_canonical["mtime_ns"],
            )
            != archive_sha
        ):
            raise AliasVerificationError(f"archive byte identity mismatch at entry {index}")
        total_bytes += archive_size
    if declared_pairs != sorted(declared_pairs) or len(set(declared_pairs)) != len(declared_pairs):
        raise AliasVerificationError("alias entries are not unique and sorted")
    pending = {
        relative
        for relative, entry in observations_current["entries"].items()
        if entry.get("present") is True
        and entry.get("baseline") is not True
        and entry.get("committed_archive_sha256") is None
        and entry.get("rejected_archive_sha256") is None
    }
    expected_pending = set(declared_pairs) if expected_disposition == "unapplied" else set()
    if pending != expected_pending:
        raise AliasVerificationError("unexpected pending archive partition")
    return {
        "protocol": "prospective_archive_content_alias_independent_verification_v1",
        "status": "ARCHIVE_CONTENT_ALIAS_REGISTRY_VERIFIED",
        "source_commit": expected_source_commit,
        "snapshot_sha256": expected_snapshot_sha256,
        "registry_sha256": expected_registry_sha256,
        "alias_count": len(declared_pairs),
        "alias_total_bytes": total_bytes,
        "byte_identical_aliases": len(declared_pairs),
        "canonical_transactions": len(declared_pairs),
        "transaction_count": len(transactions),
        "new_transactions_created": 0,
        "expected_disposition": expected_disposition,
        "outcomes_read": False,
        "archive_payloads_extracted": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--declaration", required=True, type=Path)
    parser.add_argument("--expect-declaration-sha256", required=True)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--expect-registry-sha256", required=True)
    parser.add_argument("--expect-source-commit", required=True)
    parser.add_argument("--expect-latest-snapshot-sha256", required=True)
    parser.add_argument("--expected-disposition", choices=("unapplied", "applied"), required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = verify(
            source_root=args.source_root.resolve(),
            state_root=args.state_root.resolve(),
            declaration_path=args.declaration.resolve(),
            expected_declaration_sha256=args.expect_declaration_sha256,
            registry_path=args.registry.resolve(),
            expected_registry_sha256=args.expect_registry_sha256,
            expected_source_commit=args.expect_source_commit,
            expected_snapshot_sha256=args.expect_latest_snapshot_sha256,
            expected_disposition=args.expected_disposition,
        )
        output = args.output.resolve()
        if output.exists():
            raise AliasVerificationError("output exists")
        temporary = output.with_name(output.name + f".tmp-{os.getpid()}")
        temporary.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, output)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, AliasVerificationError) as error:
        print(f"ARCHIVE_CONTENT_ALIAS_VERIFICATION_ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
