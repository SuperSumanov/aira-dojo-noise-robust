from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase1 import global_pair_hash_orientation_control as producer
from phase1 import verify_global_pair_hash_orientation_control as verifier


REPO = Path(__file__).resolve().parents[2]
PROTOCOL = REPO / "phase1" / "global_local_calibration_candidate_protocol_v2.json"
PROTOCOL_SHA = producer.FROZEN_PROTOCOL_SHA256


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def source_rows() -> list[dict]:
    return [
        {
            "better": "task-a__card-1",
            "worse": "task-a__card-2",
            "task": "task-a",
            "intask_split": "train",
            "src": "batch-a",
            "gap_raw": 0.9,
            "agrees_with_quality": True,
        },
        {
            "better": "task-a__card-3",
            "worse": "task-a__card-1",
            "task": "task-a",
            "intask_split": "train",
            "src": "batch-a",
            "gap_raw": 0.2,
            "agrees_with_quality": True,
        },
        {
            "better": "task-b__card-1",
            "worse": "task-b__card-2",
            "task": "task-b",
            "intask_split": "train",
            "src": "batch-b",
            "gap_raw": 0.5,
            "agrees_with_quality": False,
        },
    ]


def build(tmp_path: Path, rows: list[dict] | None = None, name: str = "source.jsonl") -> Path:
    path = tmp_path / name
    write_rows(path, source_rows() if rows is None else rows)
    return path


def run(tmp_path: Path, source: Path, name: str = "output") -> tuple[Path, dict]:
    output = tmp_path / name
    summary = producer.produce(PROTOCOL, PROTOCOL_SHA, source, digest(source), output)
    return output, summary


def load_overlay(output: Path) -> list[dict]:
    return [json.loads(line) for line in (output / "orientation_overlay.jsonl").read_text(encoding="utf-8").splitlines()]


def test_overlay_is_deterministic_grade_free_and_independently_verified(tmp_path: Path) -> None:
    source = build(tmp_path)
    first, summary_a = run(tmp_path, source, "first")
    second, summary_b = run(tmp_path, source, "second")
    assert (first / "orientation_overlay.jsonl").read_bytes() == (second / "orientation_overlay.jsonl").read_bytes()
    assert {key: value for key, value in summary_a.items() if key != "implementation"} == {
        key: value for key, value in summary_b.items() if key != "implementation"
    }
    rows = load_overlay(first)
    assert [row["source_row_number"] for row in rows] == [1, 2, 3]
    assert all(set(row) == producer.OUTPUT_KEYS for row in rows)
    blob = (first / "orientation_overlay.jsonl").read_text(encoding="utf-8")
    assert "gap_raw" not in blob and "agrees_with_quality" not in blob
    receipt = verifier.verify(
        PROTOCOL, PROTOCOL_SHA, source, digest(source), first, tmp_path / "receipt.json"
    )
    assert receipt["status"] == "PASS_HASH_ORIENTATION_OVERLAY_EFFECT_BLOCKED"
    assert receipt["producer_module_imported"] is False
    assert receipt["effect_submission_authorized"] is False


def test_swapping_true_orientation_does_not_change_hash_orientation(tmp_path: Path) -> None:
    original = source_rows()
    swapped = [dict(row) for row in original]
    for row in swapped:
        row["better"], row["worse"] = row["worse"], row["better"]
        row["gap_raw"] = -row["gap_raw"]
        row["agrees_with_quality"] = not row["agrees_with_quality"]
    source_a = build(tmp_path, original, "a.jsonl")
    source_b = build(tmp_path, swapped, "b.jsonl")
    out_a, _ = run(tmp_path, source_a, "out-a")
    out_b, _ = run(tmp_path, source_b, "out-b")
    assert (out_a / "orientation_overlay.jsonl").read_bytes() == (
        out_b / "orientation_overlay.jsonl"
    ).read_bytes()


def test_changing_only_outcome_metadata_keeps_overlay_byte_identical(tmp_path: Path) -> None:
    original = source_rows()
    changed = [dict(row) for row in original]
    for row in changed:
        row["gap_raw"] = -999.0
        row["agrees_with_quality"] = not row["agrees_with_quality"]
        row["new_outcome_annotation"] = {"winner": row["worse"], "score": 123.0}
    source_a = build(tmp_path, original, "a.jsonl")
    source_b = build(tmp_path, changed, "b.jsonl")
    out_a, _ = run(tmp_path, source_a, "out-a")
    out_b, _ = run(tmp_path, source_b, "out-b")
    assert (out_a / "orientation_overlay.jsonl").read_bytes() == (
        out_b / "orientation_overlay.jsonl"
    ).read_bytes()


def test_non_train_row_fails_instead_of_silently_filtering(tmp_path: Path) -> None:
    rows = source_rows()
    rows[-1]["intask_split"] = "test"
    source = build(tmp_path, rows)
    with pytest.raises(producer.HashControlError, match="train-only"):
        run(tmp_path, source)


def test_duplicate_unordered_pair_fails_closed(tmp_path: Path) -> None:
    rows = source_rows()
    duplicate = dict(rows[0])
    duplicate["better"], duplicate["worse"] = duplicate["worse"], duplicate["better"]
    rows.append(duplicate)
    source = build(tmp_path, rows)
    with pytest.raises(producer.HashControlError, match="duplicate unordered"):
        run(tmp_path, source)


def test_endpoint_reused_across_tasks_fails_closed(tmp_path: Path) -> None:
    rows = source_rows()
    rows.append({
        "better": "task-a__card-1",
        "worse": "task-c__card-2",
        "task": "task-c",
        "intask_split": "train",
    })
    source = build(tmp_path, rows)
    with pytest.raises(producer.HashControlError, match="endpoint reused across tasks"):
        run(tmp_path, source)


def test_independent_verifier_rejects_tampering(tmp_path: Path) -> None:
    source = build(tmp_path)
    output, _ = run(tmp_path, source)
    rows = load_overlay(output)
    rows[0]["hash_better"], rows[0]["hash_worse"] = rows[0]["hash_worse"], rows[0]["hash_better"]
    write_rows(output / "orientation_overlay.jsonl", rows)
    with pytest.raises(verifier.VerificationError, match="reconstruction mismatch"):
        verifier.verify(
            PROTOCOL, PROTOCOL_SHA, source, digest(source), output, tmp_path / "receipt.json"
        )


def test_independent_verifier_rejects_summary_privacy_tampering(tmp_path: Path) -> None:
    source = build(tmp_path)
    output, _ = run(tmp_path, source)
    summary_path = output / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["privacy"]["grade_derived_commitment_written"] = True
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    with pytest.raises(verifier.VerificationError, match="summary reconstruction mismatch"):
        verifier.verify(
            PROTOCOL, PROTOCOL_SHA, source, digest(source), output, tmp_path / "receipt.json"
        )


def test_sha_arguments_are_normalized_without_changing_receipt(tmp_path: Path) -> None:
    source = build(tmp_path)
    output, _ = run(tmp_path, source)
    receipt = verifier.verify(
        PROTOCOL,
        PROTOCOL_SHA.upper(),
        source,
        digest(source).upper(),
        output,
        tmp_path / "receipt.json",
    )
    assert receipt["candidate_protocol_sha256"] == PROTOCOL_SHA
    assert receipt["global_train_sha256"] == digest(source)


def test_verifier_does_not_import_producer() -> None:
    source = (REPO / "phase1" / "verify_global_pair_hash_orientation_control.py").read_text(encoding="utf-8")
    assert "from phase1 import global_pair_hash_orientation_control" not in source
    assert "import global_pair_hash_orientation_control" not in source
