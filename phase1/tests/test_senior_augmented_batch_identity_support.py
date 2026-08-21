from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

import phase1.audit_senior_augmented_batch_identity_support as audit
import phase1.verify_senior_augmented_batch_identity_support as verifier


def add_file(archive: tarfile.TarFile, name: str, payload: bytes = b"opaque") -> None:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    archive.addfile(info, io.BytesIO(payload))


def make_archive(path: Path, batch: str, runs: list[str]) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for run in runs:
            add_file(archive, f"{batch}/{run}/env_variables.json", b"opaque-sensitive-payload")
            add_file(archive, f"{batch}/{run}/checkpoint/journal.jsonl", b"opaque-journal-payload")


def test_scan_archive_uses_header_identity(tmp_path: Path) -> None:
    day = tmp_path / "0726"
    day.mkdir()
    path = day / "batch.tar.gz"
    make_archive(path, "batch-a", ["run-a", "run-b"])
    result = audit.scan_archive(path, tmp_path)
    assert result["status"] == "ok"
    assert result["run_batches"] == {"run-a": "batch-a", "run-b": "batch-a"}
    assert result["env_member_headers_seen"] == 2
    assert result["checkpoint_journal_headers"] == 2


def test_validate_runs_keeps_full_source_run_basename() -> None:
    run_id = "family_seed_7_id_abcd1234__2026-08-08"
    rows = [
        {
            "cards": 1,
            "config_sha256": "a" * 64,
            "curve_order_sha256": "b" * 64,
            "dev_order_sha256": "c" * 64,
            "original_hold": False,
            "role": "train",
            "run_id": run_id,
            "task": "task",
        }
    ]
    parsed = audit.validate_runs(rows)
    assert parsed[run_id]["source_run_name"] == "family_seed_7_id_abcd1234"
    assert parsed[run_id]["launch_date"] == "2026-08-08"


def test_independent_verifier_uses_same_published_identity_contract() -> None:
    run_id = "family_seed_7_id_abcd1234__2026-08-08"
    parsed = verifier.RUN_RE.fullmatch(run_id)
    assert parsed is not None
    assert parsed.group(1) == "family_seed_7_id_abcd1234"


def test_independent_verifier_reproduces_fail_closed_archive_row(tmp_path: Path) -> None:
    day = tmp_path / "0730"
    day.mkdir()
    path = day / "unsafe.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        info = tarfile.TarInfo("batch/run/checkpoint/journal.jsonl")
        info.type = tarfile.SYMTYPE
        info.linkname = "../../outside"
        archive.addfile(info)
    assert verifier.scan_all([path], tmp_path, 1) == audit.scan_archives([path], tmp_path, 1)


def test_independent_verifier_skips_rejected_archives_during_join() -> None:
    run_id = "family_seed_1_id_abcd__2026-08-08"
    runs = [{"run_id": run_id, "task": "task", "original_hold": False}]
    archives = [
        {
            "relative_path": "0730/rejected.tar.gz",
            "status": "error",
            "error_type": "AuditError",
            "error_sha256": "a" * 64,
        },
        {
            "relative_path": "0808/valid.tar.gz",
            "status": "ok",
            "run_batches": {"family_seed_1_id_abcd": "family"},
        },
    ]
    rows, mapping = verifier.rebuild_run_batches(runs, archives)
    assert rows[0]["source_match_status"] == "unique"
    assert mapping[run_id] == verifier.domain_hash("senior-true-batch-v1", "0808", "family")


def test_scan_archive_rejects_link_member(tmp_path: Path) -> None:
    day = tmp_path / "0726"
    day.mkdir()
    path = day / "unsafe.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        info = tarfile.TarInfo("batch/run/checkpoint/journal.jsonl")
        info.type = tarfile.SYMTYPE
        info.linkname = "../../outside"
        archive.addfile(info)
    with pytest.raises(audit.AuditError, match="unsupported tar member type"):
        audit.scan_archive(path, tmp_path)


@pytest.mark.parametrize("name", ["../x/checkpoint/journal.jsonl", "/x/checkpoint/journal.jsonl", "x\\y"])
def test_safe_parts_rejects_unsafe_names(name: str) -> None:
    with pytest.raises(audit.AuditError):
        audit.safe_parts(name)


def test_attach_batches_fails_closed_on_missing_and_ambiguity() -> None:
    runs = {
        "family_seed_1_id_abcd__2026-07-26": {
            "task": "t",
            "original_hold": False,
            "source_run_name": "family_seed_1_id_abcd",
        },
        "other_seed_1_id_ef01__2026-07-26": {
            "task": "t",
            "original_hold": False,
            "source_run_name": "other_seed_1_id_ef01",
        },
    }
    sources = {"family_seed_1_id_abcd": {("0726", "a"), ("0726", "b")}}
    _, mapping, missing, ambiguous = audit.attach_batches(runs, sources)
    assert mapping == {}
    assert missing == 1
    assert ambiguous == 1


def test_validate_pairs_detects_cross_batch() -> None:
    runs = {
        "r1": {"task": "t"},
        "r2": {"task": "t"},
    }
    pairs = [
        {
            "original_split": "train",
            "pair_key_sha256": "a" * 64,
            "run_ids": ["r1", "r2"],
            "same_experiment_contract": True,
            "task": "t",
        }
    ]
    rows, counts = audit.validate_pairs(pairs, runs, {"r1": "x", "r2": "y"})
    assert counts["cross_batch"] == 1
    assert rows[0]["same_true_batch"] is False


def test_experiment_split_support_is_deterministic() -> None:
    rows = []
    index = 0
    for task_index in range(10):
        task = f"task-{task_index}"
        for batch_index in range(5):
            batch = f"batch-{task_index}-{batch_index}"
            for _ in range(50):
                rows.append(
                    {
                        "pair_key_sha256": f"{index:064x}",
                        "original_split": "train",
                        "task": task,
                        "batch_sha256": batch,
                        "identity_complete": True,
                        "same_true_batch": True,
                        "task_match": True,
                    }
                )
                index += 1
    split_1, metrics_1 = audit.assign_experiment_roles(rows)
    split_2, metrics_2 = audit.assign_experiment_roles(list(reversed(rows)))
    assert split_1 == split_2
    assert metrics_1 == metrics_2
    assert metrics_1["experiment_closed_dev_pairs"] == 500
    assert metrics_1["experiment_closed_train_pairs"] == 2000
    assert metrics_1["dev_tasks"] == 10
    assert metrics_1["train_dev_experiment_overlap"] == 0


def test_inventory_digest_is_order_stable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    day = tmp_path / "0726"
    day.mkdir()
    make_archive(day / "b.tar.gz", "b", ["r2"])
    make_archive(day / "a.tar.gz", "a", ["r1"])
    monkeypatch.setattr(audit, "SOURCE_DAYS", ("0726",))
    paths_1, digest_1 = audit.inventory_archives(tmp_path)
    paths_2, digest_2 = audit.inventory_archives(tmp_path)
    assert [path.name for path in paths_1] == ["a.tar.gz", "b.tar.gz"]
    assert [path.name for path in paths_2] == ["a.tar.gz", "b.tar.gz"]
    assert digest_1 == digest_2
