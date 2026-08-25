from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from phase1.build_structural_rejection_ledger import build_ledger
from phase1.build_archive_disposition_partition_receipt import (
    PartitionBuildError,
    build_receipt,
)
from phase1.verify_structural_rejection_ledger import (
    LedgerVerificationError,
    verify as verify_ledger,
)
from phase1.verify_archive_disposition_partition_receipt import (
    PartitionVerificationError,
    verify as verify_partition,
)


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "phase1/results/structural_rejection_ledger_v1_20260825"


def _ledger() -> dict[str, object]:
    return json.loads((RESULT / "ledger.json").read_text(encoding="utf-8"))


def _observation_entry(path: str) -> dict[str, object]:
    return {
        "baseline": False,
        "committed_archive_sha256": None,
        "committed_snapshot_sha256": None,
        "first_stable_at_epoch": 1.0,
        "last_observed_at_epoch": 2.0,
        "mtime_ns": 3,
        "path": f"/safe/source/{path}",
        "present": True,
        "rejected_archive_sha256": None,
        "rejection_reason_code": None,
        "rejection_registry_sha256": None,
        "size": 4,
        "stable_observations": 3,
    }


def _write_observations(tmp_path: Path, entries: dict[str, object]) -> tuple[Path, str]:
    path = tmp_path / "observations.json"
    path.write_text(
        json.dumps(
            {
                "baseline_sealed_at_epoch": 1.0,
                "entries": entries,
                "protocol": "prospective_archive_observer_v1",
                "source_root": "/safe/source",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_committed_ledger_is_independently_verified() -> None:
    receipt = verify_ledger(RESULT / "ledger.json", ROOT)
    assert receipt["status"] == "INDEPENDENT_STRUCTURAL_REJECTION_LEDGER_PASS"
    assert receipt["ledger_sha256"] == (
        "b194b1bc88e561e77f982ae6f46d5ea7cccb745cc960c26da2661ea0ce8bad03"
    )
    assert receipt["recomputed_counts"] == {
        "accepted_archive_transactions": 78,
        "baseline_archives": 128,
        "identity_related_rejections": 11,
        "mixed_disposition_competitions": 6,
        "observed_archives": 218,
        "pending_archives": 0,
        "rejected_archives": 12,
        "rejected_competitions": 6,
        "settled_archive_decisions": 90,
    }
    partition_sha = hashlib.sha256(
        (RESULT / "archive_disposition_partition.json").read_bytes()
    ).hexdigest()
    assert partition_sha == "aa161d4cf601bd323420336381f932818b4b4bbb310abedeb6951b852910f07c"
    partition_verify_sha = hashlib.sha256(
        (RESULT / "archive_disposition_partition_independent_verification.json").read_bytes()
    ).hexdigest()
    assert partition_verify_sha == (
        "ffa0974dcc09d7cf67c55f348ea601c39c84eb688c83535ff8ed5a62bf77b82e"
    )


def test_builder_reproduces_committed_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    expected = _ledger()
    gate = Path(expected["source_structural_gate"]["path"])
    partition = Path(expected["source_archive_partition_receipt"]["path"])
    registries = [Path(row["path"]) for row in expected["source_rejection_registries"]]
    assert build_ledger(gate, partition, registries) == expected


def test_verifier_rejects_prettier_counts(tmp_path: Path) -> None:
    mutated = _ledger()
    mutated["counts"]["rejected_archives"] = 11
    path = tmp_path / "mutated.json"
    path.write_text(json.dumps(mutated) + "\n", encoding="utf-8")
    with pytest.raises(LedgerVerificationError, match="counts mismatch"):
        verify_ledger(path, ROOT)


def test_all_rejected_competitions_have_mixed_dispositions() -> None:
    ledger = _ledger()
    assert ledger["fractions"]["mixed_disposition_over_rejected_competitions"] == {
        "denominator": 6,
        "numerator": 6,
        "value": 1.0,
    }
    assert all(
        row["accepted_archive_transactions"] > 0
        and row["rejected_archives"] > 0
        for row in ledger["rejected_competition_timelines"]
    )


def test_partition_builder_proves_exact_disjoint_cover(tmp_path: Path) -> None:
    baseline = _observation_entry("0801/base-1seeds.tar.gz")
    baseline["baseline"] = True
    accepted = _observation_entry("0802/accepted-2seeds.tar.gz")
    accepted["committed_archive_sha256"] = "a" * 64
    accepted["committed_snapshot_sha256"] = "b" * 64
    rejected = _observation_entry("0803/rejected-2seeds.tar.gz")
    rejected["rejected_archive_sha256"] = "c" * 64
    rejected["rejection_reason_code"] = "STRUCTURAL_REASON"
    rejected["rejection_registry_sha256"] = "d" * 64
    path, source_sha = _write_observations(
        tmp_path,
        {
            "0801/base-1seeds.tar.gz": baseline,
            "0802/accepted-2seeds.tar.gz": accepted,
            "0803/rejected-2seeds.tar.gz": rejected,
        },
    )
    receipt = build_receipt(path, source_sha, "b" * 64)
    assert receipt["counts"] == {
        "accepted_archive_transactions": 1,
        "baseline_archives": 1,
        "observed_archives": 3,
        "pending_archives": 0,
        "rejected_archives": 1,
    }
    receipt_path = tmp_path / "partition.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    receipt_sha = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    independent = verify_partition(path, source_sha, receipt_path, receipt_sha)
    assert independent["status"] == "INDEPENDENT_ARCHIVE_DISPOSITION_PARTITION_PASS"

    receipt["counts"]["pending_archives"] = 1
    bad_path = tmp_path / "bad_partition.json"
    bad_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
    bad_sha = hashlib.sha256(bad_path.read_bytes()).hexdigest()
    with pytest.raises(PartitionVerificationError, match="counts mismatch"):
        verify_partition(path, source_sha, bad_path, bad_sha)


def test_partition_builder_rejects_overlapping_dispositions(tmp_path: Path) -> None:
    overlap = _observation_entry("0802/overlap-2seeds.tar.gz")
    overlap["committed_archive_sha256"] = "a" * 64
    overlap["committed_snapshot_sha256"] = "b" * 64
    overlap["rejected_archive_sha256"] = "c" * 64
    overlap["rejection_reason_code"] = "STRUCTURAL_REASON"
    overlap["rejection_registry_sha256"] = "d" * 64
    path, source_sha = _write_observations(
        tmp_path, {"0802/overlap-2seeds.tar.gz": overlap}
    )
    with pytest.raises(PartitionBuildError, match="overlapping"):
        build_receipt(path, source_sha, "b" * 64)
