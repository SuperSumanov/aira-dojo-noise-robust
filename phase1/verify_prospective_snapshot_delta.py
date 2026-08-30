#!/usr/bin/env python3
"""Verify an identity-free append-only delta between two production snapshots."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


SHA_RX = re.compile(r"[0-9a-f]{64}")
DROP_RX = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
TRANSACTION_KEYS = {
    "archive_relative_path",
    "archive_sha256",
    "archive_size",
    "committed_at_utc",
    "drop_id",
    "intake_dir",
    "intake_summary_sha256",
    "score_dir",
    "score_summary_sha256",
}
INVENTORY_FIELDS = (
    "all_physical_runs",
    "eligible_runs",
    "eligible_endpoints",
    "eligible_structural_pairs",
    "eligible_tasks",
)


class DeltaVerificationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA_RX.fullmatch(value) is None:
        raise DeltaVerificationError(f"invalid {label} SHA-256")
    return value


def parse_utc(value: Any) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise DeltaVerificationError("transaction timestamp is not canonical UTC")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise DeltaVerificationError("invalid transaction timestamp") from error
    if parsed.tzinfo != dt.timezone.utc:
        raise DeltaVerificationError("transaction timestamp is not UTC")
    return parsed


def verify_manifest(root: Path, expected_snapshot_sha: str) -> int:
    manifest = root / "SHA256SUMS"
    if not root.is_dir() or root.is_symlink() or not manifest.is_file() or manifest.is_symlink():
        raise DeltaVerificationError("unsafe or missing snapshot manifest")
    if sha256(manifest) != require_sha(expected_snapshot_sha, "snapshot"):
        raise DeltaVerificationError("snapshot manifest identity mismatch")
    count = 0
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\r\n]+)", line)
        if match is None:
            raise DeltaVerificationError(f"manifest schema mismatch at line {line_number}")
        relative = Path(match.group(2))
        if relative.is_absolute() or ".." in relative.parts or relative.name == "SHA256SUMS":
            raise DeltaVerificationError("unsafe manifest payload path")
        payload = root / relative
        if not payload.is_file() or payload.is_symlink() or sha256(payload) != match.group(1):
            raise DeltaVerificationError(f"manifest payload mismatch at line {line_number}")
        count += 1
    if count == 0:
        raise DeltaVerificationError("empty snapshot payload manifest")
    return count


def parse_transactions(path: Path) -> tuple[bytes, list[dict[str, Any]]]:
    blob = path.read_bytes()
    try:
        lines = blob.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise DeltaVerificationError("transaction registry is not UTF-8") from error
    if not lines or not blob.endswith(b"\n"):
        raise DeltaVerificationError("transaction registry is empty or lacks final newline")
    rows: list[dict[str, Any]] = []
    seen_drop: set[str] = set()
    seen_archive: set[str] = set()
    seen_path: set[str] = set()
    previous_time: dt.datetime | None = None
    for line_number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise DeltaVerificationError(f"invalid transaction JSON at line {line_number}") from error
        if not isinstance(row, dict) or set(row) != TRANSACTION_KEYS:
            raise DeltaVerificationError(f"transaction schema mismatch at line {line_number}")
        drop = row["drop_id"]
        archive_path = row["archive_relative_path"]
        if not isinstance(drop, str) or DROP_RX.fullmatch(drop) is None:
            raise DeltaVerificationError("invalid transaction drop ID")
        archive_relative = Path(str(archive_path))
        if (
            not isinstance(archive_path, str)
            or not archive_path
            or archive_relative.is_absolute()
            or ".." in archive_relative.parts
        ):
            raise DeltaVerificationError("invalid archive relative path")
        if drop in seen_drop or archive_path in seen_path:
            raise DeltaVerificationError("duplicate drop ID or archive path")
        seen_drop.add(drop)
        seen_path.add(archive_path)
        archive_sha = require_sha(row["archive_sha256"], "archive")
        if archive_sha in seen_archive:
            raise DeltaVerificationError("duplicate archive SHA-256")
        seen_archive.add(archive_sha)
        require_sha(row["intake_summary_sha256"], "intake summary")
        require_sha(row["score_summary_sha256"], "score summary")
        if (
            isinstance(row["archive_size"], bool)
            or not isinstance(row["archive_size"], int)
            or row["archive_size"] < 0
        ):
            raise DeltaVerificationError("invalid archive size")
        if not Path(str(row["intake_dir"])).is_absolute() or not Path(
            str(row["score_dir"])
        ).is_absolute():
            raise DeltaVerificationError("transaction output path is not absolute")
        timestamp = parse_utc(row["committed_at_utc"])
        if previous_time is not None and timestamp < previous_time:
            raise DeltaVerificationError("transaction commit order is not monotonic")
        previous_time = timestamp
        rows.append(row)
    return blob, rows


def canonical_jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(
        (
            json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            + "\n"
        ).encode("utf-8")
        for row in rows
    )


def expected_intake_projection(rows: list[dict[str, Any]]) -> bytes:
    return canonical_jsonl(
        [
            {
                "drop_id": row["drop_id"],
                "intake_dir": row["intake_dir"],
                "summary_sha256": row["intake_summary_sha256"],
            }
            for row in rows
        ]
    )


def expected_score_projection(rows: list[dict[str, Any]]) -> bytes:
    return canonical_jsonl(
        [
            {
                "drop_id": row["drop_id"],
                "intake_dir": row["intake_dir"],
                "intake_summary_sha256": row["intake_summary_sha256"],
                "score_dir": row["score_dir"],
                "score_summary_sha256": row["score_summary_sha256"],
            }
            for row in rows
        ]
    )


def load_snapshot(root: Path, expected_sha: str) -> dict[str, Any]:
    payload_count = verify_manifest(root, expected_sha)
    transaction_blob, transactions = parse_transactions(root / "transactions.jsonl")
    intake_blob = (root / "intake_registry.jsonl").read_bytes()
    score_blob = (root / "score_registry.jsonl").read_bytes()
    if intake_blob != expected_intake_projection(transactions):
        raise DeltaVerificationError("intake registry is not the transaction projection")
    if score_blob != expected_score_projection(transactions):
        raise DeltaVerificationError("score registry is not the transaction projection")
    accumulator = json.loads(
        (root / "accumulator" / "summary.json").read_text(encoding="utf-8")
    )
    runner = json.loads((root / "runner_summary.json").read_text(encoding="utf-8"))
    inventory = accumulator.get("inventory")
    security = accumulator.get("security")
    if not isinstance(inventory, dict) or not isinstance(security, dict):
        raise DeltaVerificationError("accumulator receipt schema mismatch")
    parsed_inventory: dict[str, int] = {}
    for field in INVENTORY_FIELDS:
        value = inventory.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise DeltaVerificationError(f"invalid accumulator inventory field: {field}")
        parsed_inventory[field] = value
    if security.get("label_vault_opened") is not False:
        raise DeltaVerificationError("accumulator label vault blindness mismatch")
    if runner.get("transactions") != len(transactions):
        raise DeltaVerificationError("runner transaction count mismatch")
    return {
        "payload_count": payload_count,
        "transaction_blob": transaction_blob,
        "transactions": transactions,
        "intake_blob": intake_blob,
        "score_blob": score_blob,
        "inventory": parsed_inventory,
    }


def verify(args: argparse.Namespace) -> dict[str, Any]:
    prior_sha = require_sha(args.expect_prior_snapshot_sha256, "prior snapshot")
    current_sha = require_sha(args.expect_current_snapshot_sha256, "current snapshot")
    if prior_sha == current_sha:
        raise DeltaVerificationError("prior and current snapshots must differ")
    prior = load_snapshot(args.prior_snapshot.resolve(), prior_sha)
    current = load_snapshot(args.current_snapshot.resolve(), current_sha)
    if len(current["transactions"]) <= len(prior["transactions"]):
        raise DeltaVerificationError("current snapshot has no appended transaction")
    for label in ("transaction_blob", "intake_blob", "score_blob"):
        if not current[label].startswith(prior[label]):
            raise DeltaVerificationError(f"prior {label} is not an exact byte prefix")
    transaction_delta = len(current["transactions"]) - len(prior["transactions"])
    inventory_delta: dict[str, int] = {}
    for field in INVENTORY_FIELDS:
        delta = current["inventory"][field] - prior["inventory"][field]
        if delta < 0:
            raise DeltaVerificationError(f"structural inventory declined: {field}")
        inventory_delta[field] = delta
    return {
        "status": "PROSPECTIVE_SNAPSHOT_APPEND_ONLY_DELTA_VERIFIED",
        "protocol": "prospective-snapshot-delta-receipt-v1",
        "prior_snapshot_sha256": prior_sha,
        "current_snapshot_sha256": current_sha,
        "payload_manifest_entries": {
            "prior": prior["payload_count"],
            "current": current["payload_count"],
        },
        "transactions": {
            "prior": len(prior["transactions"]),
            "current": len(current["transactions"]),
            "appended": transaction_delta,
            "prior_exact_byte_prefix": True,
        },
        "registry_projections": {
            "intake_exact_and_prefix_preserved": True,
            "score_exact_and_prefix_preserved": True,
        },
        "inventory": {
            "prior": prior["inventory"],
            "current": current["inventory"],
            "delta": inventory_delta,
        },
        "security": {
            "label_vault_opened": False,
            "score_prediction_files_opened": False,
            "outcomes_predictions_accuracy_utility_read": False,
            "archive_drop_run_endpoint_pair_candidate_identities_emitted": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prior-snapshot", required=True, type=Path)
    parser.add_argument("--expect-prior-snapshot-sha256", required=True)
    parser.add_argument("--current-snapshot", required=True, type=Path)
    parser.add_argument("--expect-current-snapshot-sha256", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError(f"refusing to overwrite delta receipt: {out}")
    receipt = verify(args)
    blob = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode("utf-8")
    out.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    with os.fdopen(fd, "wb") as handle:
        handle.write(blob)
    print(
        receipt["status"],
        f"transactions={receipt['transactions']['prior']}->{receipt['transactions']['current']}",
        "values_read=false",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
