from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import source_opportunity_failure_taxonomy as producer
from phase1 import verify_source_opportunity_failure_taxonomy as verifier


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def make_artifact(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "journals"
    journal = root / "run" / "checkpoint" / "journal.jsonl"
    write_jsonl(
        journal,
        [
            {"step": 0, "id": "root", "parents": [], "metric_info": {"competition_id": "task-a"}},
            {
                "step": 1,
                "id": "child",
                "parents": [0],
                "exit_code": 1,
                "term_out": "ValueError: shape mismatch",
                "metric_info": {"competition_id": "task-a"},
            },
        ],
    )
    journal_sha = hashlib.sha256(journal.read_bytes()).hexdigest()
    status = tmp_path / "status.jsonl"
    write_jsonl(
        status,
        [
            {
                "child_id": "task-a__child",
                "role": "train",
                "status": "UNIQUE_NODE_RECOVERED",
                "category": "EXECUTION_ERROR",
                "parent_match": True,
                "source_journal_sha256": journal_sha,
            }
        ],
    )
    status_sha = hashlib.sha256(status.read_bytes()).hexdigest()
    artifact = tmp_path / "artifact"
    assert producer.run(
        argparse.Namespace(
            status_per_child=str(status),
            expect_status_sha256=status_sha,
            expect_targets=1,
            root=[f"synthetic={root}"],
            source_commit="a" * 40,
            output=str(artifact),
        )
    ) == 0
    return artifact, status_sha


def args(artifact: Path, status_sha: str) -> argparse.Namespace:
    return argparse.Namespace(
        artifact=str(artifact),
        expect_source_commit="a" * 40,
        expect_status_sha256=status_sha,
        expect_targets=1,
        output=str(artifact.parent / "verification.json"),
    )


def refresh_manifest(artifact: Path, name: str) -> None:
    manifest_path = artifact / "sha256_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest[name] = hashlib.sha256((artifact / name).read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_independent_verifier_recomputes_insufficient_fixture(tmp_path: Path) -> None:
    artifact, status_sha = make_artifact(tmp_path)
    result = verifier.verify(args(artifact, status_sha))
    assert result["status"] == "INDEPENDENT_FAILURE_TAXONOMY_VERIFIED_AS_INSUFFICIENT"
    assert result["targets"] == 1
    assert result["producer_imported"] is False


def test_independent_verifier_rejects_raw_diagnostic_field(tmp_path: Path) -> None:
    artifact, status_sha = make_artifact(tmp_path)
    path = artifact / "per_child.jsonl"
    row = json.loads(path.read_text())
    row["term_out"] = "raw text must never be present"
    write_jsonl(path, [row])
    refresh_manifest(artifact, "per_child.jsonl")
    with pytest.raises(verifier.VerificationError, match="fields"):
        verifier.verify(args(artifact, status_sha))


def test_independent_verifier_rejects_summary_count_tamper(tmp_path: Path) -> None:
    artifact, status_sha = make_artifact(tmp_path)
    path = artifact / "summary.json"
    summary = json.loads(path.read_text())
    summary["structured_category_nodes"] = 0
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    refresh_manifest(artifact, "summary.json")
    with pytest.raises(verifier.VerificationError, match="structured_category_nodes"):
        verifier.verify(args(artifact, status_sha))
