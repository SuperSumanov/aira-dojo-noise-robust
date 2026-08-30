#!/usr/bin/env python3
"""Non-importing verifier for an aggregate prospective snapshot-delta receipt."""

from __future__ import annotations

import argparse
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
EXPECTED_SECURITY = {
    "archive_drop_run_endpoint_pair_candidate_identities_emitted": False,
    "label_vault_opened": False,
    "outcomes_predictions_accuracy_utility_read": False,
    "score_prediction_files_opened": False,
}
CANDIDATE_KEYS = {
    "status",
    "protocol",
    "prior_snapshot_sha256",
    "current_snapshot_sha256",
    "payload_manifest_entries",
    "transactions",
    "registry_projections",
    "inventory",
    "security",
}


class GroundedDeltaError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA_RX.fullmatch(value) is None:
        raise GroundedDeltaError(f"invalid {label} SHA-256")
    return value


def verify_manifest(root: Path, expected: str) -> int:
    manifest = root / "SHA256SUMS"
    if not root.is_dir() or root.is_symlink() or not manifest.is_file() or manifest.is_symlink():
        raise GroundedDeltaError("unsafe or missing snapshot manifest")
    if sha256(manifest) != require_sha(expected, "snapshot"):
        raise GroundedDeltaError("snapshot manifest identity mismatch")
    seen: set[str] = set()
    count = 0
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\r\n]+)", line)
        if match is None:
            raise GroundedDeltaError(f"manifest schema mismatch at line {line_number}")
        relative = Path(match.group(2))
        key = relative.as_posix()
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.name == "SHA256SUMS"
            or key in seen
        ):
            raise GroundedDeltaError("unsafe or duplicate manifest payload path")
        seen.add(key)
        payload = root / relative
        if not payload.is_file() or payload.is_symlink() or sha256(payload) != match.group(1):
            raise GroundedDeltaError(f"manifest payload mismatch at line {line_number}")
        count += 1
    if count == 0:
        raise GroundedDeltaError("empty snapshot payload manifest")
    return count


def canonical_jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(
        (
            json.dumps(
                row,
                ensure_ascii=False,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
        for row in rows
    )


def parse_transactions(path: Path) -> tuple[bytes, list[dict[str, Any]]]:
    blob = path.read_bytes()
    if not blob.endswith(b"\n"):
        raise GroundedDeltaError("transaction registry lacks final newline")
    try:
        rows = [json.loads(line) for line in blob.decode("utf-8").splitlines()]
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GroundedDeltaError("invalid transaction registry") from error
    if not rows:
        raise GroundedDeltaError("empty transaction registry")
    seen_drop: set[str] = set()
    seen_archive: set[str] = set()
    seen_path: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != TRANSACTION_KEYS:
            raise GroundedDeltaError("transaction schema mismatch")
        drop = row["drop_id"]
        archive = row["archive_sha256"]
        archive_path = row["archive_relative_path"]
        if not isinstance(drop, str) or DROP_RX.fullmatch(drop) is None:
            raise GroundedDeltaError("invalid transaction drop ID")
        if not isinstance(archive_path, str):
            raise GroundedDeltaError("invalid archive path")
        relative = Path(archive_path)
        if not archive_path or relative.is_absolute() or ".." in relative.parts:
            raise GroundedDeltaError("unsafe archive path")
        require_sha(archive, "archive")
        require_sha(row["intake_summary_sha256"], "intake summary")
        require_sha(row["score_summary_sha256"], "score summary")
        if drop in seen_drop or archive in seen_archive or archive_path in seen_path:
            raise GroundedDeltaError("duplicate transaction identity")
        seen_drop.add(drop)
        seen_archive.add(archive)
        seen_path.add(archive_path)
        if (
            isinstance(row["archive_size"], bool)
            or not isinstance(row["archive_size"], int)
            or row["archive_size"] < 0
        ):
            raise GroundedDeltaError("invalid archive size")
        if not Path(str(row["intake_dir"])).is_absolute() or not Path(
            str(row["score_dir"])
        ).is_absolute():
            raise GroundedDeltaError("transaction output path is not absolute")
    return blob, rows


def intake_projection(rows: list[dict[str, Any]]) -> bytes:
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


def score_projection(rows: list[dict[str, Any]]) -> bytes:
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
    transaction_blob, rows = parse_transactions(root / "transactions.jsonl")
    intake_blob = (root / "intake_registry.jsonl").read_bytes()
    score_blob = (root / "score_registry.jsonl").read_bytes()
    if intake_blob != intake_projection(rows):
        raise GroundedDeltaError("intake projection mismatch")
    if score_blob != score_projection(rows):
        raise GroundedDeltaError("score projection mismatch")
    summary = json.loads(
        (root / "accumulator" / "summary.json").read_text(encoding="utf-8")
    )
    runner = json.loads((root / "runner_summary.json").read_text(encoding="utf-8"))
    inventory = summary.get("inventory")
    security = summary.get("security")
    if not isinstance(inventory, dict) or not isinstance(security, dict):
        raise GroundedDeltaError("accumulator summary schema mismatch")
    parsed_inventory: dict[str, int] = {}
    for field in INVENTORY_FIELDS:
        value = inventory.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise GroundedDeltaError(f"invalid inventory field: {field}")
        parsed_inventory[field] = value
    if security.get("label_vault_opened") is not False:
        raise GroundedDeltaError("label-vault blindness mismatch")
    if runner.get("transactions") != len(rows):
        raise GroundedDeltaError("runner transaction count mismatch")
    return {
        "payload_count": payload_count,
        "transaction_blob": transaction_blob,
        "transactions": rows,
        "intake_blob": intake_blob,
        "score_blob": score_blob,
        "inventory": parsed_inventory,
    }


def verify(args: argparse.Namespace) -> dict[str, Any]:
    prior_sha = require_sha(args.expect_prior_snapshot_sha256, "prior snapshot")
    current_sha = require_sha(args.expect_current_snapshot_sha256, "current snapshot")
    candidate_sha = require_sha(args.expect_candidate_sha256, "candidate")
    if prior_sha == current_sha:
        raise GroundedDeltaError("snapshot identities must differ")
    candidate_path = args.candidate.resolve()
    if (
        not candidate_path.is_file()
        or candidate_path.is_symlink()
        or sha256(candidate_path) != candidate_sha
    ):
        raise GroundedDeltaError("candidate receipt identity mismatch")
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    prior = load_snapshot(args.prior_snapshot.resolve(), prior_sha)
    current = load_snapshot(args.current_snapshot.resolve(), current_sha)
    if len(current["transactions"]) <= len(prior["transactions"]):
        raise GroundedDeltaError("current snapshot has no appended transaction")
    for field in ("transaction_blob", "intake_blob", "score_blob"):
        if not current[field].startswith(prior[field]):
            raise GroundedDeltaError(f"prior {field} is not an exact byte prefix")
    delta = {
        field: current["inventory"][field] - prior["inventory"][field]
        for field in INVENTORY_FIELDS
    }
    if any(value < 0 for value in delta.values()):
        raise GroundedDeltaError("structural inventory declined")
    expected_transactions = {
        "prior": len(prior["transactions"]),
        "current": len(current["transactions"]),
        "appended": len(current["transactions"]) - len(prior["transactions"]),
        "prior_exact_byte_prefix": True,
    }
    if (
        not isinstance(candidate, dict)
        or set(candidate) != CANDIDATE_KEYS
        or candidate.get("status") != "PROSPECTIVE_SNAPSHOT_APPEND_ONLY_DELTA_VERIFIED"
        or candidate.get("protocol") != "prospective-snapshot-delta-receipt-v1"
        or candidate.get("prior_snapshot_sha256") != prior_sha
        or candidate.get("current_snapshot_sha256") != current_sha
        or candidate.get("transactions") != expected_transactions
        or candidate.get("payload_manifest_entries")
        != {"prior": prior["payload_count"], "current": current["payload_count"]}
        or candidate.get("registry_projections")
        != {
            "intake_exact_and_prefix_preserved": True,
            "score_exact_and_prefix_preserved": True,
        }
        or candidate.get("inventory")
        != {
            "prior": prior["inventory"],
            "current": current["inventory"],
            "delta": delta,
        }
        or candidate.get("security") != EXPECTED_SECURITY
    ):
        raise GroundedDeltaError("candidate receipt does not match independent reconstruction")
    return {
        "status": "GROUNDED_PROSPECTIVE_SNAPSHOT_DELTA_VERIFIED",
        "prior_snapshot_sha256": prior_sha,
        "current_snapshot_sha256": current_sha,
        "candidate_receipt_sha256": candidate_sha,
        "payload_manifest_entries": {
            "prior": prior["payload_count"],
            "current": current["payload_count"],
        },
        "transactions": expected_transactions,
        "inventory_delta": delta,
        "security": EXPECTED_SECURITY,
    }


def ensure_output_outside(out: Path, protected: tuple[Path, ...]) -> None:
    resolved = out.resolve()
    for root in protected:
        item = root.resolve()
        if resolved == item or item in resolved.parents or resolved in item.parents:
            raise GroundedDeltaError("output path overlaps protected input")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prior-snapshot", required=True, type=Path)
    parser.add_argument("--expect-prior-snapshot-sha256", required=True)
    parser.add_argument("--current-snapshot", required=True, type=Path)
    parser.add_argument("--expect-current-snapshot-sha256", required=True)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--expect-candidate-sha256", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError(f"refusing to overwrite grounded receipt: {out}")
    ensure_output_outside(
        out,
        (
            args.prior_snapshot.resolve(),
            args.current_snapshot.resolve(),
            args.candidate.resolve(),
        ),
    )
    result = verify(args)
    blob = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode("utf-8")
    out.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    with os.fdopen(fd, "wb") as handle:
        handle.write(blob)
    print(
        result["status"],
        f"transactions={result['transactions']['prior']}->{result['transactions']['current']}",
        "values_read=false",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
