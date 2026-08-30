from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

from phase1.prospective_production_runner import (
    ARCHIVE_CONSENSUS_PROTOCOL,
    ARCHIVE_CONSENSUS_PROTOCOL_SHA256,
    ALIAS_REASON_CODE,
    ProductionError,
    apply_archive_content_aliases,
    apply_structural_rejections,
    canonical_jsonl,
    empty_observations,
    intake_registry_bytes,
    load_latest,
    load_archive_content_aliases,
    load_structural_rejections,
    parse_transactions,
    ready_archives,
    safe_drop_id,
    score_registry_bytes,
    sha256_bytes,
    structural_rejection_specs,
    update_observations,
    verify_archive_consensus_receipt,
    verify_intake_binding,
    write_payload_manifest,
)


ARCHIVE_SHA = "a" * 64


def inventory(path: Path, *, size: int = 10, mtime: int = 200) -> dict[str, dict]:
    return {
        "0814/task.tar.gz": {
            "path": str(path.resolve()),
            "size": size,
            "mtime_ns": mtime * 1_000_000_000,
        }
    }


def transaction(tmp_path: Path, *, suffix: str = "") -> dict:
    return {
        "archive_relative_path": f"0814/task{suffix}.tar.gz",
        "archive_sha256": ("a" if not suffix else "b") * 64,
        "archive_size": 10,
        "committed_at_utc": "2026-08-14T00:00:00Z",
        "drop_id": f"0814-task{suffix}-" + (("a" if not suffix else "b") * 16),
        "intake_dir": str((tmp_path / f"intake{suffix}").resolve()),
        "intake_summary_sha256": "c" * 64,
        "score_dir": str((tmp_path / f"score{suffix}").resolve()),
        "score_summary_sha256": "d" * 64,
    }


def test_archive_requires_three_spaced_observations_and_age(tmp_path: Path):
    previous = empty_observations(tmp_path)
    previous = update_observations(previous, {}, 0.0, 300)
    current = inventory(tmp_path / "0814" / "task.tar.gz")
    observed = update_observations(previous, current, 300.0, 300)
    observed = update_observations(observed, current, 599.0, 300)
    assert observed["entries"]["0814/task.tar.gz"]["stable_observations"] == 1
    observed = update_observations(observed, current, 600.0, 300)
    observed = update_observations(observed, current, 900.0, 300)
    assert observed["entries"]["0814/task.tar.gz"]["stable_observations"] == 3
    assert ready_archives(
        observed,
        900.0,
        minimum_age_seconds=600,
        minimum_observations=3,
        minimum_stable_span_seconds=600,
    ) == ["0814/task.tar.gz"]


def test_archive_change_resets_observation_and_committed_change_fails(tmp_path: Path):
    previous = empty_observations(tmp_path)
    previous = update_observations(previous, {}, 0.0, 300)
    first = inventory(tmp_path / "0814" / "task.tar.gz")
    observed = update_observations(previous, first, 300.0, 300)
    changed = inventory(tmp_path / "0814" / "task.tar.gz", size=11, mtime=201)
    observed = update_observations(observed, changed, 600.0, 300)
    entry = observed["entries"]["0814/task.tar.gz"]
    assert entry["stable_observations"] == 1
    assert entry["first_stable_at_epoch"] == 600.0
    entry["committed_archive_sha256"] = ARCHIVE_SHA
    with pytest.raises(ProductionError, match="committed source archive metadata changed"):
        update_observations(observed, first, 900.0, 300)


def test_exact_structural_rejection_is_bound_and_skipped(tmp_path: Path):
    archive = tmp_path / "0814" / "task.tar.gz"
    archive.parent.mkdir()
    archive.write_bytes(b"structural-only")
    stat = archive.stat()
    current = {
        "0814/task.tar.gz": {
            "path": str(archive.resolve()),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
    }
    observed = update_observations(empty_observations(tmp_path), current, 300.0, 300)
    entry = observed["entries"]["0814/task.tar.gz"]
    entry["baseline"] = False
    row = {
        "archive_mtime_ns": stat.st_mtime_ns,
        "archive_relative_path": "0814/task.tar.gz",
        "archive_sha256": sha256_bytes(b"structural-only"),
        "archive_size": stat.st_size,
        "diagnostic_receipt_file": "diagnostic_receipt.json",
        "diagnostic_receipt_sha256": "d" * 64,
        "reason_code": "JOURNAL_TASK_IDENTITY_ABSENT_ALL_CHECKPOINTS",
    }
    apply_structural_rejections(observed, [row], "e" * 64)
    assert entry["rejected_archive_sha256"] == row["archive_sha256"]
    assert ready_archives(observed, 1000.0, 1, 1, 1) == []

    preserved = update_observations(observed, current, 1000.0, 300)
    assert (
        preserved["entries"]["0814/task.tar.gz"]["rejection_registry_sha256"]
        == "e" * 64
    )

    entry["committed_archive_sha256"] = row["archive_sha256"]
    with pytest.raises(ProductionError, match="committed archive cannot be"):
        apply_structural_rejections(observed, [row], "e" * 64)


def test_sequential_immutable_rejection_registries_preserve_each_binding(tmp_path: Path):
    first = tmp_path / "0814" / "first.tar.gz"
    second = tmp_path / "0815" / "second.tar.gz"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"first-structural-only")
    second.write_bytes(b"second-structural-only")
    current = {}
    for relative, archive in (("0814/first.tar.gz", first), ("0815/second.tar.gz", second)):
        stat = archive.stat()
        current[relative] = {
            "path": str(archive.resolve()),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
    observed = update_observations(empty_observations(tmp_path), current, 300.0, 300)
    for entry in observed["entries"].values():
        entry["baseline"] = False

    def rejection(relative: str, archive: Path) -> dict:
        stat = archive.stat()
        return {
            "archive_mtime_ns": stat.st_mtime_ns,
            "archive_relative_path": relative,
            "archive_sha256": sha256_bytes(archive.read_bytes()),
            "archive_size": stat.st_size,
            "diagnostic_receipt_file": "diagnostic_receipt.json",
            "diagnostic_receipt_sha256": "d" * 64,
            "reason_code": "JOURNAL_TASK_IDENTITY_ABSENT_ALL_CHECKPOINTS",
        }

    apply_structural_rejections(
        observed, [rejection("0814/first.tar.gz", first)], "a" * 64
    )
    apply_structural_rejections(
        observed, [rejection("0815/second.tar.gz", second)], "b" * 64
    )
    assert observed["entries"]["0814/first.tar.gz"]["rejection_registry_sha256"] == "a" * 64
    assert observed["entries"]["0815/second.tar.gz"]["rejection_registry_sha256"] == "b" * 64
    assert ready_archives(observed, 1000.0, 1, 1, 1) == []


def test_extra_rejection_registry_lists_are_paired_and_append_only(tmp_path: Path):
    first, second, third = (tmp_path / name for name in ("first.json", "second.json", "third.json"))
    args = Namespace(
        structural_rejection_registry=first,
        expect_structural_rejection_registry_sha256="a" * 64,
        additional_structural_rejection_registry=second,
        expect_additional_structural_rejection_registry_sha256="b" * 64,
        extra_structural_rejection_registry=[third],
        expect_extra_structural_rejection_registry_sha256=["c" * 64],
    )
    assert structural_rejection_specs(args) == [
        (first, "a" * 64),
        (second, "b" * 64),
        (third, "c" * 64),
    ]
    args.expect_extra_structural_rejection_registry_sha256 = []
    with pytest.raises(ProductionError, match="path/SHA count mismatch"):
        structural_rejection_specs(args)


def test_rejected_archive_change_or_disappearance_fails_closed(tmp_path: Path):
    observed = update_observations(
        empty_observations(tmp_path),
        inventory(tmp_path / "0814" / "task.tar.gz"),
        300.0,
        300,
    )
    entry = observed["entries"]["0814/task.tar.gz"]
    entry["baseline"] = False
    entry["rejected_archive_sha256"] = ARCHIVE_SHA
    entry["rejection_reason_code"] = "JOURNAL_TASK_IDENTITY_ABSENT_ALL_CHECKPOINTS"
    entry["rejection_registry_sha256"] = "e" * 64
    with pytest.raises(ProductionError, match="rejected source archive metadata changed"):
        update_observations(
            observed,
            inventory(tmp_path / "0814" / "task.tar.gz", size=11),
            600.0,
            300,
        )
    with pytest.raises(ProductionError, match="protected source archive disappeared"):
        update_observations(observed, {}, 600.0, 300)


def test_structural_rejection_registry_is_hash_bound_and_strict(tmp_path: Path):
    row = {
        "archive_mtime_ns": 123,
        "archive_relative_path": "0814/task.tar.gz",
        "archive_sha256": "a" * 64,
        "archive_size": 10,
        "diagnostic_receipt_file": "diagnostic_receipt.json",
        "diagnostic_receipt_sha256": sha256_bytes(b"receipt"),
        "reason_code": "JOURNAL_TASK_IDENTITY_ABSENT_ALL_CHECKPOINTS",
    }
    payload = {
        "protocol": "prospective_structural_rejection_v1",
        "outcomes_read": False,
        "entries": [row],
    }
    path = tmp_path / "rejections.json"
    (tmp_path / "diagnostic_receipt.json").write_bytes(b"receipt")
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    path.write_bytes(blob)
    rows, actual = load_structural_rejections(path, sha256_bytes(blob))
    assert rows == [row]
    assert actual == sha256_bytes(blob)
    with pytest.raises(ProductionError, match="registry SHA mismatch"):
        load_structural_rejections(path, "f" * 64)
    payload["outcomes_read"] = True
    tampered = json.dumps(payload, sort_keys=True).encode("utf-8")
    path.write_bytes(tampered)
    with pytest.raises(ProductionError, match="registry contract mismatch"):
        load_structural_rejections(path, sha256_bytes(tampered))


def test_baseline_change_or_disappearance_fails_closed(tmp_path: Path):
    first = inventory(tmp_path / "0814" / "task.tar.gz")
    observed = update_observations(empty_observations(tmp_path), first, 300.0, 300)
    with pytest.raises(ProductionError, match="baseline source archive metadata changed"):
        update_observations(
            observed,
            inventory(tmp_path / "0814" / "task.tar.gz", size=11),
            600.0,
            300,
        )
    with pytest.raises(ProductionError, match="protected source archive disappeared"):
        update_observations(observed, {}, 600.0, 300)


def test_initial_inventory_is_baseline_but_late_path_with_preserved_mtime_is_ready(
    tmp_path: Path,
):
    observed = update_observations(
        empty_observations(tmp_path),
        inventory(tmp_path / "0814" / "task.tar.gz", mtime=100),
        200.0,
        300,
    )
    entry = observed["entries"]["0814/task.tar.gz"]
    entry["stable_observations"] = 99
    entry["last_observed_at_epoch"] = 1000.0
    assert ready_archives(
        observed,
        1000.0,
        600,
        3,
        600,
    ) == []

    late_value = next(
        iter(inventory(tmp_path / "0815" / "late.tar.gz", mtime=100).values())
    )
    combined = {
        **inventory(tmp_path / "0814" / "task.tar.gz", mtime=100),
        "0815/late.tar.gz": late_value,
    }
    observed = update_observations(observed, combined, 1600.0, 300)
    observed = update_observations(observed, combined, 1900.0, 300)
    observed = update_observations(observed, combined, 2200.0, 300)
    assert observed["entries"]["0815/late.tar.gz"]["baseline"] is False
    assert ready_archives(observed, 2200.0, 600, 3, 600) == ["0815/late.tar.gz"]


def test_transaction_snapshot_binds_registry_projections(tmp_path: Path):
    state = tmp_path / "state"
    stage = tmp_path / "stage"
    stage.mkdir()
    rows = [transaction(tmp_path)]
    transaction_blob = canonical_jsonl(rows)
    (stage / "transactions.jsonl").write_bytes(transaction_blob)
    (stage / "intake_registry.jsonl").write_bytes(intake_registry_bytes(rows))
    (stage / "score_registry.jsonl").write_bytes(score_registry_bytes(rows))
    (stage / "runner_summary.json").write_text("{}\n", encoding="utf-8")
    _, snapshot_sha = write_payload_manifest(stage)
    snapshot = state / "snapshots" / snapshot_sha
    snapshot.parent.mkdir(parents=True)
    stage.rename(snapshot)
    (state / "LATEST").write_text(snapshot_sha + "\n", encoding="ascii")

    loaded, loaded_sha = load_latest(state)
    assert loaded == rows
    assert loaded_sha == snapshot_sha
    assert sha256_bytes(transaction_blob) != snapshot_sha

    (snapshot / "score_registry.jsonl").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ProductionError, match="payload hash mismatch"):
        load_latest(state)


def test_transaction_registry_rejects_duplicate_archive_identity(tmp_path: Path):
    first = transaction(tmp_path)
    second = transaction(tmp_path, suffix="-second")
    second["archive_sha256"] = first["archive_sha256"]
    with pytest.raises(ProductionError, match="duplicate transaction identity"):
        parse_transactions(canonical_jsonl([first, second]))


def test_intake_and_independent_consensus_receipts_are_strictly_bound(tmp_path: Path):
    archive = tmp_path / "spaceship-titanic-2seeds.tar.gz"
    archive.write_bytes(b"immutable-archive")
    archive_sha = sha256_bytes(archive.read_bytes())
    intake = tmp_path / "intake"
    intake.mkdir()
    summary = {
        "configuration": {
            "archive_selection": "explicit_names",
            "selected_archive_names": [archive.name],
            "archive_consensus_fallback_protocol": ARCHIVE_CONSENSUS_PROTOCOL,
            "archive_consensus_fallback_protocol_sha256": (
                ARCHIVE_CONSENSUS_PROTOCOL_SHA256
            ),
        },
        "inventory": {"archive_consensus_fallback_runs": 1},
    }
    (intake / "summary.json").write_text(json.dumps(summary) + "\n", encoding="utf-8")
    (intake / "archive_manifest.tsv").write_text(
        f"name\tsize\tsha256\n{archive.name}\t{archive.stat().st_size}\t{archive_sha}\n",
        encoding="utf-8",
    )
    intake_sha, fallback_runs = verify_intake_binding(intake, archive, archive_sha)
    assert fallback_runs == 1

    receipt = {
        "status": "ARCHIVE_CONSENSUS_INDEPENDENT_VERIFICATION_PASS",
        "archive_sha256": archive_sha,
        "intake_summary_sha256": intake_sha,
        "archive_consensus_fallback_journals": 1,
        "security": {
            "env_or_key_members_opened": False,
            "live_event_journals_opened": False,
            "label_vault_opened": False,
            "outcomes_predictions_accuracy_utility_read": False,
            "competition_identities_emitted": False,
        },
    }
    receipt_path = tmp_path / "verification.json"
    receipt_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
    assert len(verify_archive_consensus_receipt(
        receipt_path, archive_sha, intake_sha, fallback_runs
    )) == 64

    receipt["security"]["label_vault_opened"] = True
    receipt_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
    with pytest.raises(ProductionError, match="verification receipt mismatch"):
        verify_archive_consensus_receipt(receipt_path, archive_sha, intake_sha, fallback_runs)


def test_safe_drop_id_is_deterministic_and_bounded():
    drop_id = safe_drop_id("0814/任务 name.tar.gz", ARCHIVE_SHA)
    assert drop_id == safe_drop_id("0814/任务 name.tar.gz", ARCHIVE_SHA)
    assert drop_id.endswith("-" + ARCHIVE_SHA[:16])
    assert len(drop_id) <= 128
    assert "/" not in drop_id and "任务" not in drop_id


def test_parse_transactions_rejects_blank_lines(tmp_path: Path):
    blob = canonical_jsonl([transaction(tmp_path)]) + b"\n"
    with pytest.raises(ProductionError, match="blank transaction registry line"):
        parse_transactions(blob)


def alias_fixture(tmp_path: Path) -> tuple[dict, list[dict], dict, Path]:
    source = tmp_path / "source"
    canonical = source / "0824" / "task.tar.gz"
    alias = source / "0824-copy" / "task.tar.gz"
    canonical.parent.mkdir(parents=True)
    alias.parent.mkdir(parents=True)
    payload = b"identical-archive-bytes"
    canonical.write_bytes(payload)
    alias.write_bytes(payload)
    archive_sha = sha256_bytes(payload)
    observed = update_observations(empty_observations(source), {}, 0.0, 300)
    current = {}
    for relative, path in (("0824/task.tar.gz", canonical), ("0824-copy/task.tar.gz", alias)):
        stat = path.stat()
        current[relative] = {
            "path": str(path.resolve()),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
    observed = update_observations(observed, current, 300.0, 300)
    canonical_entry = observed["entries"]["0824/task.tar.gz"]
    canonical_entry["committed_archive_sha256"] = archive_sha
    canonical_entry["committed_snapshot_sha256"] = "f" * 64
    canonical_transaction = transaction(tmp_path)
    canonical_transaction.update(
        {
            "archive_relative_path": "0824/task.tar.gz",
            "archive_sha256": archive_sha,
            "archive_size": len(payload),
            "drop_id": "canonical-drop",
            "committed_at_utc": "2026-08-25T00:00:00Z",
        }
    )
    alias_stat = alias.stat()
    receipt = tmp_path / "diagnostic_receipt.json"
    receipt.write_text("{}\n", encoding="utf-8")
    row = {
        "archive_mtime_ns": alias_stat.st_mtime_ns,
        "archive_relative_path": "0824-copy/task.tar.gz",
        "archive_sha256": archive_sha,
        "archive_size": len(payload),
        "canonical_archive_relative_path": "0824/task.tar.gz",
        "canonical_drop_id": "canonical-drop",
        "canonical_transaction_committed_at_utc": "2026-08-25T00:00:00Z",
        "diagnostic_receipt_file": receipt.name,
        "diagnostic_receipt_sha256": sha256_bytes(receipt.read_bytes()),
        "reason_code": ALIAS_REASON_CODE,
    }
    return observed, [canonical_transaction], row, receipt


def test_archive_content_alias_registry_is_hash_and_receipt_bound(tmp_path: Path):
    _, _, row, _ = alias_fixture(tmp_path)
    payload = {
        "protocol": "prospective_archive_content_alias_v1",
        "outcomes_read": False,
        "archive_payloads_opened": False,
        "entries": [row],
    }
    path = tmp_path / "aliases.json"
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    path.write_bytes(blob)
    rows, actual = load_archive_content_aliases(path, sha256_bytes(blob))
    assert rows == [row]
    assert actual == sha256_bytes(blob)
    with pytest.raises(ProductionError, match="registry SHA mismatch"):
        load_archive_content_aliases(path, "0" * 64)


def test_archive_content_alias_registry_rejects_empty_unsafe_or_unsorted_entries(
    tmp_path: Path,
):
    _, _, row, _ = alias_fixture(tmp_path)

    def write_and_load(entries: list[dict]) -> None:
        path = tmp_path / "aliases.json"
        blob = json.dumps(
            {
                "protocol": "prospective_archive_content_alias_v1",
                "outcomes_read": False,
                "archive_payloads_opened": False,
                "entries": entries,
            },
            sort_keys=True,
        ).encode("utf-8")
        path.write_bytes(blob)
        load_archive_content_aliases(path, sha256_bytes(blob))

    with pytest.raises(ProductionError, match="contract mismatch"):
        write_and_load([])

    unsafe = dict(row)
    unsafe["archive_relative_path"] = "../task.tar.gz"
    with pytest.raises(ProductionError, match="invalid archive alias path"):
        write_and_load([unsafe])

    second = dict(row)
    second["archive_relative_path"] = "0823/task.tar.gz"
    second["canonical_archive_relative_path"] = "0822/task.tar.gz"
    second["archive_sha256"] = "a" * 64
    with pytest.raises(ProductionError, match="not sorted"):
        write_and_load([row, second])


def test_archive_content_alias_is_explicitly_excluded_without_new_transaction(tmp_path: Path):
    observed, transactions, row, _ = alias_fixture(tmp_path)
    before = json.loads(json.dumps(transactions))
    apply_archive_content_aliases(observed, transactions, [row], "e" * 64)
    alias = observed["entries"][row["archive_relative_path"]]
    assert alias["committed_archive_sha256"] is None
    assert alias["rejected_archive_sha256"] == row["archive_sha256"]
    assert alias["rejection_reason_code"] == ALIAS_REASON_CODE
    assert alias["rejection_registry_sha256"] == "e" * 64
    assert transactions == before
    apply_archive_content_aliases(observed, transactions, [row], "e" * 64)


def test_archive_content_alias_fails_on_content_or_canonical_drift(tmp_path: Path):
    observed, transactions, row, _ = alias_fixture(tmp_path)
    Path(observed["entries"][row["archive_relative_path"]]["path"]).write_bytes(
        b"different"
    )
    with pytest.raises(ProductionError, match="content hash mismatch"):
        apply_archive_content_aliases(observed, transactions, [row], "e" * 64)

    observed, transactions, row, _ = alias_fixture(tmp_path / "second")
    transactions[0]["drop_id"] = "changed-drop"
    with pytest.raises(ProductionError, match="transaction binding mismatch"):
        apply_archive_content_aliases(observed, transactions, [row], "e" * 64)


def test_archive_content_alias_disposition_is_protected_by_observation_ledger(tmp_path: Path):
    observed, transactions, row, _ = alias_fixture(tmp_path)
    apply_archive_content_aliases(observed, transactions, [row], "e" * 64)
    alias = observed["entries"][row["archive_relative_path"]]
    with pytest.raises(ProductionError, match="rejected source archive metadata changed"):
        update_observations(
            observed,
            {
                "0824/task.tar.gz": {
                    "path": observed["entries"]["0824/task.tar.gz"]["path"],
                    "size": observed["entries"]["0824/task.tar.gz"]["size"],
                    "mtime_ns": observed["entries"]["0824/task.tar.gz"]["mtime_ns"],
                },
                row["archive_relative_path"]: {
                    "path": alias["path"],
                    "size": alias["size"] + 1,
                    "mtime_ns": alias["mtime_ns"],
                },
            },
            600.0,
            300,
        )


def test_monitor_runner_enters_the_frozen_repo_for_every_invocation():
    script = (
        Path(__file__).parents[1]
        / "scripts"
        / "run_prospective_production_monitor_20260814.sh"
    ).read_text(encoding="utf-8")
    assert 'runner() {\n  (\n    cd "$repo_root"' in script
    assert '(cd "$repo_root" && runner' not in script
