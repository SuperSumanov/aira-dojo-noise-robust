import argparse
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import audit_transition_future_escrow_support as audit
from phase1 import verify_transition_future_escrow_support as verifier


SNAPSHOT_SHA = "a" * 64
SOURCE_SHA = "b" * 64


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _snapshot(tmp_path: Path, include_parent: bool = True) -> tuple[Path, Path]:
    state = tmp_path / "state"
    snapshot = state / "snapshots" / SNAPSHOT_SHA
    intake = state / "intakes" / "drop-1"
    generation = "2026-08-21T00:00:00Z"
    specifications = [
        ("a", "p", "Improve", 1),
        ("b", "p", "Improve", 2),
    ]
    if include_parent:
        specifications.insert(0, ("p", "root", "Draft", 0))
    rows = []
    for identifier, parent, operation, step in specifications:
        code = f"print('{identifier}')\n"
        rows.append(
            {
                "card_id": identifier,
                "task": "task",
                "run_id": "run",
                "code": code,
                "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
                "lineage": {
                    "depth": 0 if identifier == "p" else 1,
                    "step": step,
                    "n_siblings": 1 if identifier == "p" else 2,
                    "op": operation,
                    "parent": parent,
                },
                "generation_started_at_utc": generation,
                "source_sha256": SOURCE_SHA,
            }
        )
    manifest = intake / "eligible_blind_manifest.jsonl"
    _write_jsonl(manifest, rows)
    intake_summary = intake / "summary.json"
    _write_json(
        intake_summary,
        {
            "outputs": {"eligible_blind_manifest_sha256": _sha(manifest)},
            "security": {"env_members_read": False, "live_event_journal_members_read": False},
            "blindness": {
                "labels_used_for_run_selection": False,
                "labels_used_for_endpoint_selection": False,
                "metrics_computed": [],
            },
        },
    )
    _write_jsonl(
        snapshot / "intake_registry.jsonl",
        [{"drop_id": "drop-1", "intake_dir": str(intake.resolve()), "summary_sha256": _sha(intake_summary)}],
    )
    _write_jsonl(
        snapshot / "accumulator" / "provisional_runs.jsonl",
        [
            {
                "run_id": "run",
                "task": "task",
                "drop_id": "drop-1",
                "flow_status": "scoreable",
                "endpoints": len(rows),
                "generation_started_at_utc": generation,
                "source_sha256": SOURCE_SHA,
            }
        ],
    )
    _write_json(
        snapshot / "accumulator" / "summary.json",
        {
            "inventory": {
                "drops": 1,
                "eligible_runs": 1,
                "eligible_endpoints": len(rows),
                "provisional_first960_runs": 1,
                "provisional_first960_endpoints": len(rows),
                "provisional_first960_structural_pairs": 1,
            }
        },
    )
    (state / "LATEST").write_text(SNAPSHOT_SHA + "\n", encoding="utf-8")
    return state, snapshot


def _training(tmp_path: Path, overlap: bool = False) -> tuple[Path, Path, Path, dict[str, str]]:
    cards = tmp_path / "Cards.json"
    train = tmp_path / "train.jsonl"
    dev = tmp_path / "dev.jsonl"
    ids = ("a", "x", "q") if overlap else ("x", "y", "q")
    rows = [{"id": identifier, "code": f"print('train-{identifier}')\n"} for identifier in ids]
    if overlap:
        rows[0]["code"] = "print('a')\n"
    _write_json(cards, {"train-run": rows})
    _write_jsonl(train, [{"better": ids[0], "worse": ids[1], "parent": ids[2]}])
    _write_jsonl(dev, [])
    return cards, train, dev, {"cards": _sha(cards), "train": _sha(train), "dev": _sha(dev)}


def _summary(tmp_path: Path, include_parent: bool = True, overlap: bool = False):
    state, _snapshot_root = _snapshot(tmp_path, include_parent=include_parent)
    cards, train, dev, hashes = _training(tmp_path, overlap=overlap)
    result = audit.summarize(state, SNAPSHOT_SHA, cards, train, dev, hashes)
    return result, state, cards, train, dev, hashes


def _verifier_args(
    tmp_path: Path,
    state: Path,
    cards: Path,
    train: Path,
    dev: Path,
    hashes: dict[str, str],
    producer: Path,
) -> argparse.Namespace:
    return argparse.Namespace(
        state_root=state,
        expect_snapshot_sha=SNAPSHOT_SHA,
        training_cards=cards,
        expect_training_cards_sha=hashes["cards"],
        train_pairs=train,
        expect_train_pairs_sha=hashes["train"],
        dev_pairs=dev,
        expect_dev_pairs_sha=hashes["dev"],
        producer=producer,
        output=tmp_path / "verification.json",
    )


def test_source_novel_parent_covered_support(tmp_path: Path) -> None:
    result, *_rest = _summary(tmp_path)
    assert result["status"] == audit.STATUS_NOVEL
    assert result["inventory"]["pairs"] == 1
    assert result["inventory"]["pairs_with_parent_source"] == 1
    assert result["inventory"]["source_novel_parent_covered_pairs"] == 1
    assert result["inventory"]["pair_parent_source_coverage"] == 1.0
    assert result["overlap"] == {
        "blind_card_ids_in_training_support": 0,
        "blind_code_sha_in_training_support": 0,
        "blind_run_ids_in_training_support": 0,
        "zero_run_overlap": True,
    }


def test_training_support_overlap_blocks_independence(tmp_path: Path) -> None:
    result, *_rest = _summary(tmp_path, overlap=True)
    assert result["status"] == audit.STATUS_OVERLAP
    assert result["overlap"]["blind_card_ids_in_training_support"] == 1
    assert result["overlap"]["blind_code_sha_in_training_support"] == 1
    assert result["inventory"]["source_novel_parent_covered_pairs"] == 0


def test_missing_parent_is_zero_coverage_not_division_error(tmp_path: Path) -> None:
    result, *_rest = _summary(tmp_path, include_parent=False)
    assert result["inventory"]["pairs_with_parent_source"] == 0
    assert result["inventory"]["pair_parent_source_coverage"] == 0.0
    assert result["inventory"]["dominant_covered_pair_task_share"] == 0.0


def test_snapshot_rejects_extra_label_field(tmp_path: Path) -> None:
    state, snapshot = _snapshot(tmp_path)
    registry_path = snapshot / "intake_registry.jsonl"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    intake = Path(registry["intake_dir"])
    manifest = intake / "eligible_blind_manifest.jsonl"
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    rows[0]["label"] = 1
    _write_jsonl(manifest, rows)
    summary_path = intake / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["outputs"]["eligible_blind_manifest_sha256"] = _sha(manifest)
    _write_json(summary_path, summary)
    registry["summary_sha256"] = _sha(summary_path)
    _write_jsonl(registry_path, [registry])
    cards, train, dev, hashes = _training(tmp_path)
    with pytest.raises(audit.SupportAuditError, match="schema mismatch"):
        audit.summarize(state, SNAPSHOT_SHA, cards, train, dev, hashes)


def test_snapshot_rejects_card_run_metadata_mismatch(tmp_path: Path) -> None:
    state, snapshot = _snapshot(tmp_path)
    runs_path = snapshot / "accumulator" / "provisional_runs.jsonl"
    run = json.loads(runs_path.read_text(encoding="utf-8"))
    run["task"] = "wrong-task"
    _write_jsonl(runs_path, [run])
    cards, train, dev, hashes = _training(tmp_path)
    with pytest.raises(audit.SupportAuditError, match="card/run accounting mismatch"):
        audit.summarize(state, SNAPSHOT_SHA, cards, train, dev, hashes)


def test_independent_verifier_matches_every_field_and_rejects_tamper(tmp_path: Path) -> None:
    result, state, cards, train, dev, hashes = _summary(tmp_path)
    producer = tmp_path / "producer.json"
    _write_json(producer, result)
    args = _verifier_args(tmp_path, state, cards, train, dev, hashes, producer)
    receipt = verifier.verify(args)
    assert receipt["producer_imported"] is False
    assert receipt["all_fields_exact"] is True
    assert receipt["support_status"] == audit.STATUS_NOVEL

    tampered = json.loads(producer.read_text(encoding="utf-8"))
    tampered["inventory"]["pairs"] += 1
    _write_json(producer, tampered)
    with pytest.raises(verifier.VerificationError, match="differs"):
        verifier.verify(args)
