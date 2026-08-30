from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import prospective_production_runner as production
from phase1 import verify_prospective_snapshot_delta as verifier


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def transaction(index: int) -> dict:
    timestamp = f"2026-08-{14 + index:02d}T00:00:00Z"
    synthetic_state = Path.cwd().resolve() / "__snapshot_delta_test_state__"
    return {
        "archive_relative_path": f"batch/archive-{index}.tar.gz",
        "archive_sha256": digest(f"archive-{index}"),
        "archive_size": 100 + index,
        "committed_at_utc": timestamp,
        "drop_id": f"drop-{index}",
        "intake_dir": str(synthetic_state / "intakes" / f"drop-{index}"),
        "intake_summary_sha256": digest(f"intake-{index}"),
        "score_dir": str(synthetic_state / "scores" / f"drop-{index}"),
        "score_summary_sha256": digest(f"score-{index}"),
    }


def write_snapshot(root: Path, rows: list[dict], inventory: dict[str, int]) -> str:
    root.mkdir()
    transactions = verifier.canonical_jsonl(rows)
    (root / "transactions.jsonl").write_bytes(transactions)
    (root / "intake_registry.jsonl").write_bytes(
        verifier.expected_intake_projection(rows)
    )
    (root / "score_registry.jsonl").write_bytes(
        verifier.expected_score_projection(rows)
    )
    accumulator = root / "accumulator"
    accumulator.mkdir()
    (accumulator / "summary.json").write_text(
        json.dumps(
            {
                "inventory": inventory,
                "security": {"label_vault_opened": False},
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "runner_summary.json").write_text(
        json.dumps({"transactions": len(rows)}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payloads = sorted(
        path for path in root.rglob("*") if path.is_file() and path.name != "SHA256SUMS"
    )
    manifest = "".join(
        f"{verifier.sha256(path)}  {path.relative_to(root).as_posix()}\n"
        for path in payloads
    )
    (root / "SHA256SUMS").write_text(manifest, encoding="utf-8", newline="")
    return verifier.sha256(root / "SHA256SUMS")


def inventory(runs: int, endpoints: int, pairs: int, tasks: int = 2) -> dict[str, int]:
    return {
        "all_physical_runs": runs,
        "eligible_runs": runs,
        "eligible_endpoints": endpoints,
        "eligible_structural_pairs": pairs,
        "eligible_tasks": tasks,
    }


def arguments(prior: Path, prior_sha: str, current: Path, current_sha: str):
    return argparse.Namespace(
        prior_snapshot=prior,
        expect_prior_snapshot_sha256=prior_sha,
        current_snapshot=current,
        expect_current_snapshot_sha256=current_sha,
    )


def test_append_only_delta_passes_and_emits_aggregates_only(tmp_path: Path):
    prior = tmp_path / "prior"
    current = tmp_path / "current"
    prior_sha = write_snapshot(prior, [transaction(0)], inventory(1, 10, 3))
    current_sha = write_snapshot(
        current,
        [transaction(0), transaction(1)],
        inventory(2, 14, 5),
    )
    receipt = verifier.verify(arguments(prior, prior_sha, current, current_sha))
    assert receipt["transactions"]["appended"] == 1
    assert receipt["inventory"]["delta"]["eligible_endpoints"] == 4
    assert receipt["security"]["score_prediction_files_opened"] is False


def test_registry_projection_bytes_match_frozen_production_serialization():
    rows = [transaction(0), transaction(1)]
    intake = verifier.expected_intake_projection(rows)
    score = verifier.expected_score_projection(rows)
    assert intake == production.intake_registry_bytes(rows)
    assert score == production.score_registry_bytes(rows)
    assert b'": "' in intake and b', "' in intake
    assert b'": "' in score and b', "' in score


def test_mutated_historical_transaction_fails_prefix_gate(tmp_path: Path):
    prior = tmp_path / "prior"
    current = tmp_path / "current"
    prior_sha = write_snapshot(prior, [transaction(0)], inventory(1, 10, 3))
    changed = transaction(0)
    changed["archive_size"] += 1
    current_sha = write_snapshot(
        current,
        [changed, transaction(1)],
        inventory(2, 14, 5),
    )
    with pytest.raises(verifier.DeltaVerificationError, match="exact byte prefix"):
        verifier.verify(arguments(prior, prior_sha, current, current_sha))


def test_projection_mismatch_fails_closed(tmp_path: Path):
    prior = tmp_path / "prior"
    current = tmp_path / "current"
    prior_sha = write_snapshot(prior, [transaction(0)], inventory(1, 10, 3))
    current_sha = write_snapshot(
        current,
        [transaction(0), transaction(1)],
        inventory(2, 14, 5),
    )
    score_registry = current / "score_registry.jsonl"
    score_registry.write_bytes(score_registry.read_bytes() + b"\n")
    payloads = sorted(
        path for path in current.rglob("*") if path.is_file() and path.name != "SHA256SUMS"
    )
    (current / "SHA256SUMS").write_text(
        "".join(
            f"{verifier.sha256(path)}  {path.relative_to(current).as_posix()}\n"
            for path in payloads
        ),
        encoding="utf-8",
        newline="",
    )
    current_sha = verifier.sha256(current / "SHA256SUMS")
    with pytest.raises(verifier.DeltaVerificationError, match="score registry"):
        verifier.verify(arguments(prior, prior_sha, current, current_sha))


def test_structural_inventory_decline_fails_closed(tmp_path: Path):
    prior = tmp_path / "prior"
    current = tmp_path / "current"
    prior_sha = write_snapshot(prior, [transaction(0)], inventory(2, 10, 3))
    current_sha = write_snapshot(
        current,
        [transaction(0), transaction(1)],
        inventory(2, 9, 5),
    )
    with pytest.raises(verifier.DeltaVerificationError, match="inventory declined"):
        verifier.verify(arguments(prior, prior_sha, current, current_sha))


def test_payload_tamper_fails_manifest_gate(tmp_path: Path):
    prior = tmp_path / "prior"
    current = tmp_path / "current"
    prior_sha = write_snapshot(prior, [transaction(0)], inventory(1, 10, 3))
    current_sha = write_snapshot(
        current,
        [transaction(0), transaction(1)],
        inventory(2, 14, 5),
    )
    (current / "runner_summary.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(verifier.DeltaVerificationError, match="payload mismatch"):
        verifier.verify(arguments(prior, prior_sha, current, current_sha))


def test_duplicate_manifest_payload_fails_closed(tmp_path: Path):
    prior = tmp_path / "prior"
    current = tmp_path / "current"
    prior_sha = write_snapshot(prior, [transaction(0)], inventory(1, 10, 3))
    current_sha = write_snapshot(
        current,
        [transaction(0), transaction(1)],
        inventory(2, 14, 5),
    )
    manifest = current / "SHA256SUMS"
    first = manifest.read_text(encoding="utf-8").splitlines()[0]
    manifest.write_text(
        manifest.read_text(encoding="utf-8") + first + "\n",
        encoding="utf-8",
        newline="",
    )
    current_sha = verifier.sha256(manifest)
    with pytest.raises(verifier.DeltaVerificationError, match="duplicate manifest"):
        verifier.verify(arguments(prior, prior_sha, current, current_sha))


def test_output_must_not_overlap_snapshot_inputs(tmp_path: Path):
    prior = tmp_path / "prior"
    current = tmp_path / "current"
    prior.mkdir()
    current.mkdir()
    with pytest.raises(verifier.DeltaVerificationError, match="overlaps"):
        verifier.ensure_output_outside(prior / "receipt.json", (prior, current))


def test_execution_addendum_v2_freezes_failure_and_single_repair():
    addendum = json.loads(
        (
            Path(__file__).parents[1]
            / "prospective_snapshot_delta_receipt_execution_addendum_v2.json"
        ).read_text(encoding="utf-8")
    )
    assert addendum["failed_v1"]["manifest_sha256"] == (
        "ff5a27a190443f01d9cdb91f69286ec321b8ce125169d1eec9402758b50e2d8b"
    )
    assert addendum["permitted_change"] == (
        "Match the frozen production canonical JSONL separators while retaining "
        "sorted keys, UTF-8, final newlines, and NaN rejection."
    )
    assert addendum["scientific_protocol_changed"] is False
    assert addendum["same_root_repair_allowed"] is False
