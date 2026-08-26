from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase1.build_archive_content_alias_registry import (
    AliasRegistryBuildError,
    build_artifacts,
    load_declaration,
)
from phase1.prospective_production_runner import (
    ProductionError,
    apply_archive_content_aliases,
    canonical_json,
    load_archive_content_aliases,
)
from phase1.verify_archive_content_alias_registry import AliasVerificationError, verify


COMMIT = "a" * 40
SNAPSHOT = "b" * 64


def _sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _fixture(tmp_path: Path, alias_payload: bytes = b"same"):
    source = tmp_path / "source"
    canonical = source / "0824" / "task.tar.gz"
    alias = source / "0824-alias" / "task.tar.gz"
    canonical.parent.mkdir(parents=True)
    alias.parent.mkdir(parents=True)
    canonical.write_bytes(b"same")
    alias.write_bytes(alias_payload)
    canonical_stat = canonical.stat()
    alias_stat = alias.stat()
    archive_sha = _sha(canonical.read_bytes())
    observations = {
        "protocol": "prospective_archive_observer_v1",
        "source_root": str(source.resolve()),
        "baseline_sealed_at_epoch": 1.0,
        "entries": {
            "0824/task.tar.gz": {
                "baseline": False,
                "committed_archive_sha256": archive_sha,
                "committed_snapshot_sha256": SNAPSHOT,
                "mtime_ns": canonical_stat.st_mtime_ns,
                "path": str(canonical.resolve()),
                "present": True,
                "rejected_archive_sha256": None,
                "rejection_reason_code": None,
                "rejection_registry_sha256": None,
                "size": canonical_stat.st_size,
            },
            "0824-alias/task.tar.gz": {
                "baseline": False,
                "committed_archive_sha256": None,
                "committed_snapshot_sha256": None,
                "mtime_ns": alias_stat.st_mtime_ns,
                "path": str(alias.resolve()),
                "present": True,
                "rejected_archive_sha256": None,
                "rejection_reason_code": None,
                "rejection_registry_sha256": None,
                "size": alias_stat.st_size,
            },
        },
    }
    transaction = {
        "archive_relative_path": "0824/task.tar.gz",
        "archive_sha256": archive_sha,
        "archive_size": canonical_stat.st_size,
        "committed_at_utc": "2026-08-25T00:00:00Z",
        "drop_id": "canonical-drop",
        "intake_dir": str((tmp_path / "intake").resolve()),
        "intake_summary_sha256": "c" * 64,
        "score_dir": str((tmp_path / "score").resolve()),
        "score_summary_sha256": "d" * 64,
    }
    pairs = [
        {
            "archive_relative_path": "0824-alias/task.tar.gz",
            "canonical_archive_relative_path": "0824/task.tar.gz",
        }
    ]
    return source, observations, [transaction], pairs


def _artifacts(tmp_path: Path, alias_payload: bytes = b"same"):
    source, observations, transactions, pairs = _fixture(tmp_path, alias_payload)
    diagnostic, registry = build_artifacts(
        source_root=source,
        observations=observations,
        transactions=transactions,
        pairs=pairs,
        source_commit=COMMIT,
        snapshot_sha256=SNAPSHOT,
        declaration_sha256="e" * 64,
        observations_sha256="f" * 64,
        transactions_sha256="1" * 64,
        diagnostic_receipt_file="diagnostic.json",
    )
    receipt = tmp_path / "diagnostic.json"
    receipt.write_bytes(canonical_json(diagnostic))
    for row in registry["entries"]:
        row["diagnostic_receipt_sha256"] = _sha(receipt.read_bytes())
    registry_path = tmp_path / "registry.json"
    registry_path.write_bytes(canonical_json(registry))
    return observations, transactions, diagnostic, registry_path


def test_builder_output_is_runner_accepted_and_explicitly_disposed(tmp_path: Path) -> None:
    observations, transactions, diagnostic, registry_path = _artifacts(tmp_path)
    assert diagnostic["alias_payload_hashes_read"] is False
    assert diagnostic["automatic_duplicate_disposition_enabled"] is False
    registry_sha = _sha(registry_path.read_bytes())
    rows, actual_sha = load_archive_content_aliases(registry_path, registry_sha)
    apply_archive_content_aliases(observations, transactions, rows, actual_sha)
    alias = observations["entries"]["0824-alias/task.tar.gz"]
    assert alias["rejected_archive_sha256"] == transactions[0]["archive_sha256"]
    assert len(transactions) == 1


def test_builder_does_not_claim_byte_equality_and_runner_fails_on_mismatch(
    tmp_path: Path,
) -> None:
    observations, transactions, diagnostic, registry_path = _artifacts(
        tmp_path, alias_payload=b"diff"
    )
    assert diagnostic["alias_payload_hash_verification_deferred_to_runner"] is True
    registry_sha = _sha(registry_path.read_bytes())
    rows, _ = load_archive_content_aliases(registry_path, registry_sha)
    with pytest.raises(ProductionError, match="content hash mismatch"):
        apply_archive_content_aliases(observations, transactions, rows, registry_sha)


def test_declaration_is_hash_bound_sorted_and_snapshot_bound(tmp_path: Path) -> None:
    value = {
        "protocol": "prospective_archive_content_alias_declaration_v1",
        "outcomes_read": False,
        "archive_payloads_opened": False,
        "source_commit": COMMIT,
        "snapshot_sha256": SNAPSHOT,
        "entries": [
            {
                "archive_relative_path": "0824-alias/task.tar.gz",
                "canonical_archive_relative_path": "0824/task.tar.gz",
            }
        ],
    }
    path = tmp_path / "declaration.json"
    blob = canonical_json(value)
    path.write_bytes(blob)
    pairs, actual = load_declaration(path, _sha(blob), COMMIT, SNAPSHOT)
    assert pairs == value["entries"]
    assert actual == _sha(blob)
    with pytest.raises(AliasRegistryBuildError, match="contract mismatch"):
        load_declaration(path, _sha(blob), COMMIT, "0" * 64)


def test_builder_rejects_previously_disposed_alias(tmp_path: Path) -> None:
    source, observations, transactions, pairs = _fixture(tmp_path)
    observations["entries"]["0824-alias/task.tar.gz"]["rejected_archive_sha256"] = "9" * 64
    with pytest.raises(AliasRegistryBuildError, match="already has a disposition"):
        build_artifacts(
            source_root=source,
            observations=observations,
            transactions=transactions,
            pairs=pairs,
            source_commit=COMMIT,
            snapshot_sha256=SNAPSHOT,
            declaration_sha256="e" * 64,
            observations_sha256="f" * 64,
            transactions_sha256="1" * 64,
            diagnostic_receipt_file="diagnostic.json",
        )


def test_independent_verifier_checks_unapplied_and_applied_partition(tmp_path: Path) -> None:
    source, observations, transactions, pairs = _fixture(tmp_path)
    state = tmp_path / "state"
    snapshots = state / "snapshots"
    snapshots.mkdir(parents=True)
    transaction_blob = b"".join(
        (json.dumps(row, sort_keys=True) + "\n").encode("utf-8") for row in transactions
    )
    manifest_blob = (
        f"{_sha(transaction_blob)}  transactions.jsonl\n".encode("utf-8")
    )
    snapshot = _sha(manifest_blob)
    snapshot_root = snapshots / snapshot
    snapshot_root.mkdir()
    (snapshot_root / "transactions.jsonl").write_bytes(transaction_blob)
    (snapshot_root / "SHA256SUMS").write_bytes(manifest_blob)
    (state / "LATEST").write_text(snapshot + "\n", encoding="ascii")
    observations_blob = canonical_json(observations)
    (state / "observations.json").write_bytes(observations_blob)

    declaration = {
        "protocol": "prospective_archive_content_alias_declaration_v1",
        "outcomes_read": False,
        "archive_payloads_opened": False,
        "source_commit": COMMIT,
        "snapshot_sha256": snapshot,
        "entries": pairs,
    }
    declaration_path = tmp_path / "declaration.json"
    declaration_path.write_bytes(canonical_json(declaration))
    declaration_sha = _sha(declaration_path.read_bytes())
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "observations_before.json").write_bytes(observations_blob)
    diagnostic, registry = build_artifacts(
        source_root=source,
        observations=observations,
        transactions=transactions,
        pairs=pairs,
        source_commit=COMMIT,
        snapshot_sha256=snapshot,
        declaration_sha256=declaration_sha,
        observations_sha256=_sha(observations_blob),
        transactions_sha256=_sha(transaction_blob),
        diagnostic_receipt_file="diagnostic.json",
    )
    diagnostic_path = bundle / "diagnostic.json"
    diagnostic_path.write_bytes(canonical_json(diagnostic))
    for row in registry["entries"]:
        row["diagnostic_receipt_sha256"] = _sha(diagnostic_path.read_bytes())
    registry_path = bundle / "registry.json"
    registry_path.write_bytes(canonical_json(registry))
    registry_sha = _sha(registry_path.read_bytes())

    before = verify(
        source_root=source,
        state_root=state,
        declaration_path=declaration_path,
        expected_declaration_sha256=declaration_sha,
        registry_path=registry_path,
        expected_registry_sha256=registry_sha,
        expected_source_commit=COMMIT,
        expected_snapshot_sha256=snapshot,
        expected_disposition="unapplied",
    )
    assert before["byte_identical_aliases"] == 1
    assert before["new_transactions_created"] == 0

    rows, _ = load_archive_content_aliases(registry_path, registry_sha)
    apply_archive_content_aliases(observations, transactions, rows, registry_sha)
    (state / "observations.json").write_bytes(canonical_json(observations))
    after = verify(
        source_root=source,
        state_root=state,
        declaration_path=declaration_path,
        expected_declaration_sha256=declaration_sha,
        registry_path=registry_path,
        expected_registry_sha256=registry_sha,
        expected_source_commit=COMMIT,
        expected_snapshot_sha256=snapshot,
        expected_disposition="applied",
    )
    assert after["expected_disposition"] == "applied"
    assert after["canonical_transactions"] == 1

    unknown = source / "0825" / "new.tar.gz"
    unknown.parent.mkdir()
    unknown.write_bytes(b"new archive")
    stat = unknown.stat()
    observations["entries"]["0825/new.tar.gz"] = {
        "baseline": False,
        "committed_archive_sha256": None,
        "committed_snapshot_sha256": None,
        "mtime_ns": stat.st_mtime_ns,
        "path": str(unknown.resolve()),
        "present": True,
        "rejected_archive_sha256": None,
        "rejection_reason_code": None,
        "rejection_registry_sha256": None,
        "size": stat.st_size,
    }
    (state / "observations.json").write_bytes(canonical_json(observations))
    with pytest.raises(AliasVerificationError, match="unexpected pending archive partition"):
        verify(
            source_root=source,
            state_root=state,
            declaration_path=declaration_path,
            expected_declaration_sha256=declaration_sha,
            registry_path=registry_path,
            expected_registry_sha256=registry_sha,
            expected_source_commit=COMMIT,
            expected_snapshot_sha256=snapshot,
            expected_disposition="applied",
        )
