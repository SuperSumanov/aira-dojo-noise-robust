from __future__ import annotations

import json
from pathlib import Path

import pytest

from phase1.prospective_production_runner import (
    ProductionError,
    canonical_jsonl,
    empty_observations,
    intake_registry_bytes,
    load_latest,
    parse_transactions,
    ready_archives,
    safe_drop_id,
    score_registry_bytes,
    sha256_bytes,
    update_observations,
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


def test_monitor_runner_enters_the_frozen_repo_for_every_invocation():
    script = (
        Path(__file__).parents[1]
        / "scripts"
        / "run_prospective_production_monitor_20260814.sh"
    ).read_text(encoding="utf-8")
    assert 'runner() {\n  (\n    cd "$repo_root"' in script
    assert '(cd "$repo_root" && runner' not in script
