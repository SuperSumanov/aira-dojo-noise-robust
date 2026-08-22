from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

import phase1.validate_senior_source_provenance_manifest as contract


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> str:
    payload = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows
    ).encode()
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def expected_row(run_id: str, task: str = "task-a") -> dict[str, object]:
    return {
        "cards": 3,
        "config_sha256": "a" * 64,
        "curve_order_sha256": "b" * 64,
        "dev_order_sha256": "c" * 64,
        "original_hold": False,
        "role": "train",
        "run_id": run_id,
        "task": task,
    }


def provenance_row(
    run_id: str,
    archive_sha256: str,
    task: str = "task-a",
    batch_id: str = "batch-a",
) -> dict[str, object]:
    return {
        "archive_path": "0808/task-a.tar.gz",
        "archive_sha256": archive_sha256,
        "batch_id": batch_id,
        "producer_commit": "d" * 40,
        "run_id": run_id,
        "source_date": "2026-08-08",
        "task": task,
    }


def make_archive(path: Path, entries: list[tuple[str, str]], unsafe_link: bool = False) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w:gz") as archive:
        for batch_id, source_run_name in entries:
            name = f"{batch_id}/{source_run_name}/checkpoint/journal.jsonl"
            info = tarfile.TarInfo(name)
            if unsafe_link:
                info.type = tarfile.SYMTYPE
                info.linkname = "../../outside"
                archive.addfile(info)
            else:
                payload = b"opaque payload that must never be read"
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
    return contract.sha256_file(path)


def valid_fixture(tmp_path: Path) -> tuple[Path, str, Path, str, Path, str]:
    run_id = "family_seed_7_id_abcd1234__2026-08-08"
    source_root = tmp_path / "sources"
    archive = source_root / "0808" / "task-a.tar.gz"
    archive_sha = make_archive(archive, [("batch-a", "family_seed_7_id_abcd1234")])
    expected = tmp_path / "runs.jsonl"
    expected_sha = write_jsonl(expected, [expected_row(run_id)])
    provenance = tmp_path / "provenance.jsonl"
    provenance_sha = write_jsonl(provenance, [provenance_row(run_id, archive_sha)])
    return expected, expected_sha, provenance, provenance_sha, source_root, run_id


def test_valid_manifest_gets_deterministic_verified_receipt(tmp_path: Path) -> None:
    expected, expected_sha, provenance, provenance_sha, source_root, _ = valid_fixture(tmp_path)
    first = contract.validate(expected, expected_sha, provenance, provenance_sha, source_root)
    second = contract.validate(expected, expected_sha, provenance, provenance_sha, source_root)
    assert first == second
    assert first["formal_status"] == "PROVENANCE_VERIFIED"
    assert first["inventory"]["provenance_rows"] == 1
    assert first["archives"][0]["referenced_runs"] == 1
    assert first["access_attestation"]["tar_member_payloads_opened"] is False


def test_manifest_requires_exact_coverage(tmp_path: Path) -> None:
    expected, expected_sha, provenance, provenance_sha, source_root, run_id = valid_fixture(tmp_path)
    second_id = "other_seed_1_id_ef012345__2026-08-08"
    expected_sha = write_jsonl(expected, [expected_row(run_id), expected_row(second_id)])
    with pytest.raises(contract.ContractError, match="does not cover 1 expected runs"):
        contract.validate(expected, expected_sha, provenance, provenance_sha, source_root)


def test_manifest_rejects_task_mismatch(tmp_path: Path) -> None:
    expected, expected_sha, provenance, _, source_root, run_id = valid_fixture(tmp_path)
    archive_sha = contract.sha256_file(source_root / "0808" / "task-a.tar.gz")
    provenance_sha = write_jsonl(provenance, [provenance_row(run_id, archive_sha, task="task-b")])
    with pytest.raises(contract.ContractError, match="task does not match"):
        contract.validate(expected, expected_sha, provenance, provenance_sha, source_root)


def test_manifest_rejects_date_proxy(tmp_path: Path) -> None:
    expected, expected_sha, provenance, _, source_root, run_id = valid_fixture(tmp_path)
    archive_sha = contract.sha256_file(source_root / "0808" / "task-a.tar.gz")
    row = provenance_row(run_id, archive_sha)
    row["source_date"] = "2026-08-09"
    provenance_sha = write_jsonl(provenance, [row])
    with pytest.raises(contract.ContractError, match="source_date does not match"):
        contract.validate(expected, expected_sha, provenance, provenance_sha, source_root)


def test_manifest_rejects_archive_hash_mismatch(tmp_path: Path) -> None:
    expected, expected_sha, provenance, _, source_root, run_id = valid_fixture(tmp_path)
    provenance_sha = write_jsonl(provenance, [provenance_row(run_id, "e" * 64)])
    with pytest.raises(contract.ContractError, match="archive SHA-256 mismatch"):
        contract.validate(expected, expected_sha, provenance, provenance_sha, source_root)


def test_manifest_requires_exact_batch_and_run_header(tmp_path: Path) -> None:
    expected, expected_sha, provenance, _, source_root, run_id = valid_fixture(tmp_path)
    archive_sha = contract.sha256_file(source_root / "0808" / "task-a.tar.gz")
    provenance_sha = write_jsonl(
        provenance, [provenance_row(run_id, archive_sha, batch_id="invented-batch")]
    )
    with pytest.raises(contract.ContractError, match="exactly one matching"):
        contract.validate(expected, expected_sha, provenance, provenance_sha, source_root)


def test_manifest_rejects_duplicate_journal_header(tmp_path: Path) -> None:
    expected, expected_sha, provenance, _, source_root, run_id = valid_fixture(tmp_path)
    archive = source_root / "0808" / "task-a.tar.gz"
    archive_sha = make_archive(
        archive,
        [
            ("batch-a", "family_seed_7_id_abcd1234"),
            ("batch-a", "family_seed_7_id_abcd1234"),
        ],
    )
    provenance_sha = write_jsonl(provenance, [provenance_row(run_id, archive_sha)])
    with pytest.raises(contract.ContractError, match="exactly one matching"):
        contract.validate(expected, expected_sha, provenance, provenance_sha, source_root)


def test_manifest_rejects_unsafe_tar_member(tmp_path: Path) -> None:
    expected, expected_sha, provenance, _, source_root, run_id = valid_fixture(tmp_path)
    archive = source_root / "0808" / "task-a.tar.gz"
    archive_sha = make_archive(
        archive, [("batch-a", "family_seed_7_id_abcd1234")], unsafe_link=True
    )
    provenance_sha = write_jsonl(provenance, [provenance_row(run_id, archive_sha)])
    with pytest.raises(contract.ContractError, match="unsupported tar member type"):
        contract.validate(expected, expected_sha, provenance, provenance_sha, source_root)


def test_manifest_rejects_noncanonical_or_unsorted_rows(tmp_path: Path) -> None:
    expected, _, provenance, _, source_root, run_id = valid_fixture(tmp_path)
    second_id = "aaa_seed_1_id_ef012345__2026-08-08"
    archive = source_root / "0808" / "task-a.tar.gz"
    archive_sha = make_archive(
        archive,
        [
            ("batch-a", "family_seed_7_id_abcd1234"),
            ("batch-a", "aaa_seed_1_id_ef012345"),
        ],
    )
    expected_sha = write_jsonl(expected, [expected_row(run_id), expected_row(second_id)])
    provenance_sha = write_jsonl(
        provenance,
        [provenance_row(run_id, archive_sha), provenance_row(second_id, archive_sha)],
    )
    with pytest.raises(contract.ContractError, match="sorted by run_id"):
        contract.validate(expected, expected_sha, provenance, provenance_sha, source_root)


def test_manifest_rejects_extra_schema_field(tmp_path: Path) -> None:
    expected, expected_sha, provenance, _, source_root, run_id = valid_fixture(tmp_path)
    archive_sha = contract.sha256_file(source_root / "0808" / "task-a.tar.gz")
    row = provenance_row(run_id, archive_sha)
    row["grade"] = 1.0
    provenance_sha = write_jsonl(provenance, [row])
    with pytest.raises(contract.ContractError, match="schema mismatch"):
        contract.validate(expected, expected_sha, provenance, provenance_sha, source_root)
