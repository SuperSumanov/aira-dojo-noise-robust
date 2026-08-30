from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

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
