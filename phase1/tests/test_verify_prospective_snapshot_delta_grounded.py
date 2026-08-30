from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import verify_prospective_snapshot_delta as primary
from phase1 import verify_prospective_snapshot_delta_grounded as grounded


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def transaction(index: int) -> dict:
    state = Path.cwd().resolve() / "__grounded_snapshot_delta_state__"
    return {
        "archive_relative_path": f"batch/archive-{index}.tar.gz",
        "archive_sha256": digest(f"archive-{index}"),
        "archive_size": 100 + index,
        "committed_at_utc": f"2026-08-{14 + index:02d}T00:00:00Z",
        "drop_id": f"drop-{index}",
        "intake_dir": str(state / "intakes" / f"drop-{index}"),
        "intake_summary_sha256": digest(f"intake-{index}"),
        "score_dir": str(state / "scores" / f"drop-{index}"),
        "score_summary_sha256": digest(f"score-{index}"),
    }


def inventory(runs: int, endpoints: int, pairs: int) -> dict[str, int]:
    return {
        "all_physical_runs": runs,
        "eligible_runs": runs,
        "eligible_endpoints": endpoints,
        "eligible_structural_pairs": pairs,
        "eligible_tasks": 2,
    }


def write_snapshot(root: Path, rows: list[dict], counts: dict[str, int]) -> str:
    root.mkdir()
    (root / "transactions.jsonl").write_bytes(primary.canonical_jsonl(rows))
    (root / "intake_registry.jsonl").write_bytes(
        primary.expected_intake_projection(rows)
    )
    (root / "score_registry.jsonl").write_bytes(
        primary.expected_score_projection(rows)
    )
    accumulator = root / "accumulator"
    accumulator.mkdir()
    (accumulator / "summary.json").write_text(
        json.dumps(
            {
                "inventory": counts,
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
    (root / "SHA256SUMS").write_text(
        "".join(
            f"{primary.sha256(path)}  {path.relative_to(root).as_posix()}\n"
            for path in payloads
        ),
        encoding="utf-8",
        newline="",
    )
    return primary.sha256(root / "SHA256SUMS")


def fixture(tmp_path: Path):
    prior = tmp_path / "prior"
    current = tmp_path / "current"
    prior_sha = write_snapshot(prior, [transaction(0)], inventory(1, 10, 3))
    current_sha = write_snapshot(
        current,
        [transaction(0), transaction(1)],
        inventory(2, 14, 5),
    )
    primary_args = argparse.Namespace(
        prior_snapshot=prior,
        expect_prior_snapshot_sha256=prior_sha,
        current_snapshot=current,
        expect_current_snapshot_sha256=current_sha,
    )
    candidate = tmp_path / "candidate.json"
    candidate.write_text(
        json.dumps(primary.verify(primary_args), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="",
    )
    candidate_sha = grounded.sha256(candidate)
    args = argparse.Namespace(
        prior_snapshot=prior,
        expect_prior_snapshot_sha256=prior_sha,
        current_snapshot=current,
        expect_current_snapshot_sha256=current_sha,
        candidate=candidate,
        expect_candidate_sha256=candidate_sha,
    )
    return args, candidate


def test_grounded_verifier_reconstructs_candidate_without_identities(tmp_path: Path):
    args, _ = fixture(tmp_path)
    result = grounded.verify(args)
    assert result["status"] == "GROUNDED_PROSPECTIVE_SNAPSHOT_DELTA_VERIFIED"
    assert result["transactions"]["appended"] == 1
    assert result["inventory_delta"]["eligible_endpoints"] == 4
    assert result["security"] == grounded.EXPECTED_SECURITY


def test_grounded_verifier_rejects_candidate_delta_mutation(tmp_path: Path):
    args, candidate = fixture(tmp_path)
    value = json.loads(candidate.read_text(encoding="utf-8"))
    value["inventory"]["delta"]["eligible_endpoints"] += 1
    candidate.write_text(
        json.dumps(value, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="",
    )
    args.expect_candidate_sha256 = grounded.sha256(candidate)
    with pytest.raises(grounded.GroundedDeltaError, match="does not match"):
        grounded.verify(args)


def test_grounded_verifier_rejects_extra_candidate_field(tmp_path: Path):
    args, candidate = fixture(tmp_path)
    value = json.loads(candidate.read_text(encoding="utf-8"))
    value["archive_names"] = []
    candidate.write_text(
        json.dumps(value, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="",
    )
    args.expect_candidate_sha256 = grounded.sha256(candidate)
    with pytest.raises(grounded.GroundedDeltaError, match="does not match"):
        grounded.verify(args)


def test_grounded_verifier_rejects_candidate_hash_mismatch(tmp_path: Path):
    args, _ = fixture(tmp_path)
    args.expect_candidate_sha256 = "0" * 64
    with pytest.raises(grounded.GroundedDeltaError, match="identity mismatch"):
        grounded.verify(args)


def test_grounded_source_does_not_import_primary_or_production():
    source = Path(grounded.__file__).read_text(encoding="utf-8")
    assert "verify_prospective_snapshot_delta as" not in source
    assert "prospective_production_runner" not in source


def test_grounded_output_must_not_overlap_inputs(tmp_path: Path):
    prior = tmp_path / "prior"
    candidate = tmp_path / "candidate.json"
    prior.mkdir()
    candidate.write_text("{}\n", encoding="utf-8")
    with pytest.raises(grounded.GroundedDeltaError, match="overlaps"):
        grounded.ensure_output_outside(prior / "receipt.json", (prior, candidate))
