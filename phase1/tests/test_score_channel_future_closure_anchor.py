from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase1 import score_channel_future_closure_anchor as anchor


ROOT = Path(__file__).parents[2]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def formal_fixture(tmp_path: Path) -> tuple[Path, Path]:
    result_root = tmp_path / "cohorts"
    formal = result_root / "formal-1"
    producer_a = formal / "producer_a"
    producer_b = formal / "producer_b"
    producer_a.mkdir(parents=True)
    producer_b.mkdir()
    runs = b'{"run_id":"run"}\n'
    archives = b'{"drop_id":"drop"}\n'
    for producer in (producer_a, producer_b):
        (producer / "cohort_runs.jsonl").write_bytes(runs)
        (producer / "cohort_archives.jsonl").write_bytes(archives)
    summary = {
        "protocol": anchor.COHORT_PROTOCOL,
        "status": "FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD",
        "closure": {
            "accepted_unique_physical_run_target": 300,
            "complete_boundary_archive_included": True,
            "remaining_runs_to_target": 0,
            "boundary_archive": "0824/archive.tar.gz",
        },
        "inventory": {"selected_physical_runs": 301, "selected_tasks": 50},
        "blindness": {
            "label_vault_opened": False,
            "score_or_outcome_opened": False,
            "truth_support_computed": False,
            "replay_submission_authorized": False,
        },
        "outputs": {
            "cohort_runs_sha256": hashlib.sha256(runs).hexdigest(),
            "cohort_archives_sha256": hashlib.sha256(archives).hexdigest(),
        },
    }
    write_json(producer_a / "summary.json", summary)
    write_json(producer_b / "summary.json", summary)
    verification = {
        "protocol": anchor.VERIFICATION_PROTOCOL,
        "status": "PASS_IDENTITY_CLOSED_TRUTH_UNREAD",
        "cohort_summary_sha256": digest(producer_a / "summary.json"),
        "cohort_runs_sha256": summary["outputs"]["cohort_runs_sha256"],
        "cohort_archives_sha256": summary["outputs"]["cohort_archives_sha256"],
        "label_vault_opened": False,
        "score_or_outcome_opened": False,
        "raw_archive_payload_opened": False,
        "replay_submission_authorized": False,
    }
    write_json(formal / "verification_a.json", verification)
    write_json(formal / "verification_b.json", verification)
    (formal / "producer_reproducibility.diff").write_bytes(b"")
    (formal / "verifier_reproducibility.diff").write_bytes(b"")
    (formal / "COMPLETE").write_text(
        "SCORE_CHANNEL_FUTURE_IDENTITY_COHORT_FORMAL_COMPLETE\n", encoding="utf-8"
    )
    (formal / "control_commit.txt").write_text("a" * 40 + "\n", encoding="utf-8")
    (formal / "latest_before.txt").write_text("b" * 64 + "\n", encoding="utf-8")
    (formal / "observations_before_sha256.txt").write_text("c" * 64 + "\n", encoding="utf-8")
    names = sorted(
        path.relative_to(formal).as_posix()
        for path in formal.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    (formal / "SHA256SUMS").write_text(
        "".join(f"{digest(formal / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )
    return result_root, formal


def test_first_closed_receipt_is_anchored_once(tmp_path: Path) -> None:
    result_root, formal = formal_fixture(tmp_path)
    document = anchor.build_anchor(formal, result_root, ROOT)
    target = result_root / "FIRST_CLOSED_COHORT_ANCHOR.json"
    assert anchor.publish(target, document) == document
    assert anchor.publish(target, document) == document
    assert json.loads(target.read_text(encoding="utf-8"))["selected_physical_runs"] == 301


def test_existing_anchor_rejects_different_closed_cohort(tmp_path: Path) -> None:
    result_root, formal = formal_fixture(tmp_path)
    target = result_root / "FIRST_CLOSED_COHORT_ANCHOR.json"
    document = anchor.build_anchor(formal, result_root, ROOT)
    anchor.publish(target, document)
    changed = {**document, "cohort_summary_sha256": "d" * 64}
    with pytest.raises(anchor.AnchorError, match="different receipt"):
        anchor.publish(target, changed)


def test_existing_anchor_rejects_noncore_metadata_tamper(tmp_path: Path) -> None:
    result_root, formal = formal_fixture(tmp_path)
    target = result_root / "FIRST_CLOSED_COHORT_ANCHOR.json"
    document = anchor.build_anchor(formal, result_root, ROOT)
    anchor.publish(target, document)
    tampered = {**document, "selected_tasks": document["selected_tasks"] + 1}
    target.chmod(0o600)
    write_json(target, tampered)
    target.chmod(0o444)
    with pytest.raises(anchor.AnchorError, match="different receipt"):
        anchor.publish(target, document)


def test_anchor_source_has_no_outcome_input_argument() -> None:
    source = (ROOT / "phase1" / "score_channel_future_closure_anchor.py").read_text(
        encoding="utf-8"
    )
    assert "--label-vault" not in source
    assert "--score" not in source
    assert "--outcome" not in source
