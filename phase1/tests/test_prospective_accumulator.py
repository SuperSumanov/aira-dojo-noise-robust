from __future__ import annotations

import argparse
import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from phase1 import prospective_accumulator as accumulator
from phase1 import prospective_drop_intake as intake


RESULT_ROOT = (
    Path(__file__).parents[1] / "results" / "fixed_decision_scorer_v11_20260814"
)
RECEIPT = RESULT_ROOT / "freeze_receipt.json"
DENYLIST = RESULT_ROOT / "precutoff_endpoint_denylist.csv"
START = 1_786_661_000.0


def journal_nodes(tag: str, started: float) -> list[dict]:
    metric = {
        "competition_id": "spaceship-titanic",
        "is_lower_better": False,
        "gold_threshold": 0.9,
        "silver_threshold": 0.8,
        "bronze_threshold": 0.7,
    }
    return [
        {
            "step": 0,
            "id": f"root-{tag}",
            "code": "",
            "parents": [],
            "creation_time": started,
            "exec_time": 0,
            "exit_code": 0,
            "metric_info": {},
        },
        {
            "step": 1,
            "id": f"left-{tag}",
            "code": f"print('accumulator-left-{tag}')",
            "parents": [0],
            "creation_time": started + 1,
            "exec_time": 1,
            "exit_code": 0,
            "operators_used": ["draft"],
            "metric_info": {**metric, "score": 0.8, "validation_score": 0.7},
        },
        {
            "step": 2,
            "id": f"right-{tag}",
            "code": f"print('accumulator-right-{tag}')",
            "parents": [0],
            "creation_time": started + 2,
            "exec_time": 1,
            "exit_code": 0,
            "operators_used": ["improve"],
            "metric_info": {**metric, "score": 0.7, "validation_score": 0.6},
        },
    ]


def add_bytes(handle: tarfile.TarFile, name: str, blob: bytes, mtime: int) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(blob)
    info.mtime = mtime
    handle.addfile(info, io.BytesIO(blob))


def make_intake(tmp_path: Path, tag: str, started: float) -> Path:
    drop = tmp_path / f"drop-{tag}"
    drop.mkdir()
    archive = drop / f"{tag}.tar.gz"
    nodes = journal_nodes(tag, started)
    journal = ("\n".join(json.dumps(node, sort_keys=True) for node in nodes) + "\n").encode()
    root = f"batch/run-{tag}"
    with tarfile.open(archive, "w:gz") as handle:
        add_bytes(handle, f"{root}/checkpoint/journal.jsonl", journal, int(started + 30))
        add_bytes(handle, f"{root}/json/JOURNAL.jsonl", b'{"event":"ignored"}\n', int(started + 30))
        fake_secret = "sk" + "-" + "x" * 32
        add_bytes(
            handle,
            f"{root}/env_variables.json",
            json.dumps({"API_KEY": fake_secret}).encode(),
            int(started + 30),
        )
    output = tmp_path / f"intake-{tag}"
    intake.build(
        argparse.Namespace(
            drop_dir=drop,
            freeze_receipt=RECEIPT,
            precutoff_endpoint_denylist=DENYLIST,
            out_dir=output,
            repo_root=Path(__file__).parents[2],
            expect_freeze_receipt_sha256=accumulator.FREEZE_RECEIPT_SHA256,
            max_archive_bytes=8 * 1024 * 1024,
            max_total_archive_bytes=16 * 1024 * 1024,
            max_member_bytes=1024 * 1024,
            max_members_per_archive=128,
            max_total_member_bytes_per_archive=8 * 1024 * 1024,
            max_total_journal_bytes=8 * 1024 * 1024,
            max_archives=16,
        )
    )
    return output


def write_registry(path: Path, entries: list[tuple[str, Path]]) -> str:
    rows = []
    for drop_id, intake_dir in entries:
        summary = intake_dir / "summary.json"
        rows.append(
            {
                "drop_id": drop_id,
                "intake_dir": str(intake_dir.resolve()),
                "summary_sha256": hashlib.sha256(summary.read_bytes()).hexdigest(),
            }
        )
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8", newline="\n")
    return hashlib.sha256(text.encode()).hexdigest()


def args_for(registry: Path, output: Path, **overrides) -> argparse.Namespace:
    values = {
        "registry": registry,
        "freeze_receipt": RECEIPT,
        "precutoff_endpoint_denylist": DENYLIST,
        "out_dir": output,
        "repo_root": Path(__file__).parents[2],
        "closure_receipt": None,
        "expect_closure_receipt_sha256": None,
        "max_drops": 16,
        "max_endpoints": 1000,
        "max_structural_pairs": 1000,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_collecting_state_is_label_blind_and_provisional(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(accumulator, "FIRST_PILOT", 1)
    monkeypatch.setattr(accumulator, "FIRST_CONFIRM", 2)
    first = make_intake(tmp_path, "first", START)
    registry = tmp_path / "registry.jsonl"
    write_registry(registry, [("drop-first", first)])
    output = tmp_path / "accumulator"

    assert accumulator.build(args_for(registry, output)) == 0
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "PROSPECTIVE_COHORT_COLLECTING"
    assert summary["inventory"]["eligible_runs"] == 1
    assert summary["inventory"]["eligible_endpoints"] == 2
    assert summary["inventory"]["eligible_structural_pairs"] == 1
    assert summary["security"]["label_vault_opened"] is False
    assert "label_vault.jsonl" not in summary["security"]["opened_basenames"]
    assert not (output / "frozen_runs.jsonl").exists()


def test_late_arrival_order_stays_provisional_until_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(accumulator, "FIRST_PILOT", 1)
    monkeypatch.setattr(accumulator, "FIRST_CONFIRM", 2)
    late = make_intake(tmp_path, "late", START + 100)
    early = make_intake(tmp_path, "early", START + 10)
    registry = tmp_path / "registry.jsonl"
    registry_sha = write_registry(registry, [("drop-late", late), ("drop-early", early)])

    provisional = tmp_path / "provisional"
    accumulator.build(args_for(registry, provisional))
    provisional_summary = json.loads((provisional / "summary.json").read_text(encoding="utf-8"))
    assert provisional_summary["status"] == "PROSPECTIVE_COHORT_AWAITING_CLOSURE"
    first_run = read_jsonl(provisional / "provisional_first240_runs.jsonl")[0]
    assert first_run["drop_id"] == "drop-early"

    closure = tmp_path / "closure_receipt.json"
    closure.write_text(
        json.dumps(
            {
                "status": "PROSPECTIVE_ACCRUAL_CLOSED",
                "protocol": "prospective_decision_v1",
                "closed_at_utc": "2026-08-14T00:45:00Z",
                "registry_sha256": registry_sha,
                "all_scheduled_runs_uploaded": True,
                "outcomes_read": False,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    closure_sha = hashlib.sha256(closure.read_bytes()).hexdigest()
    frozen = tmp_path / "frozen"
    accumulator.build(
        args_for(
            registry,
            frozen,
            closure_receipt=closure,
            expect_closure_receipt_sha256=closure_sha,
        )
    )
    frozen_summary = json.loads((frozen / "summary.json").read_text(encoding="utf-8"))
    assert frozen_summary["status"] == "PROSPECTIVE_FIRST960_IDENTITY_FROZEN"
    assert [row["drop_id"] for row in read_jsonl(frozen / "frozen_runs.jsonl")] == [
        "drop-early",
        "drop-late",
    ]


def test_duplicate_intake_source_fails_closed(tmp_path: Path):
    first = make_intake(tmp_path, "duplicate", START)
    registry = tmp_path / "registry.jsonl"
    write_registry(registry, [("drop-a", first), ("drop-b", first)])

    with pytest.raises(accumulator.AccumulatorError, match="source archive"):
        accumulator.build(args_for(registry, tmp_path / "output"))
    assert not (tmp_path / "output").exists()


def test_closure_registry_hash_mismatch_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(accumulator, "FIRST_CONFIRM", 1)
    first = make_intake(tmp_path, "closure", START)
    registry = tmp_path / "registry.jsonl"
    write_registry(registry, [("drop-closure", first)])
    closure = tmp_path / "closure_receipt.json"
    closure.write_text(
        json.dumps(
            {
                "status": "PROSPECTIVE_ACCRUAL_CLOSED",
                "protocol": "prospective_decision_v1",
                "closed_at_utc": "2026-08-14T00:45:00Z",
                "registry_sha256": "0" * 64,
                "all_scheduled_runs_uploaded": True,
                "outcomes_read": False,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    closure_sha = hashlib.sha256(closure.read_bytes()).hexdigest()
    output = tmp_path / "output"
    with pytest.raises(accumulator.AccumulatorError, match="closure receipt gate"):
        accumulator.build(
            args_for(
                registry,
                output,
                closure_receipt=closure,
                expect_closure_receipt_sha256=closure_sha,
            )
        )
    assert not output.exists()
