from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import verify_prospective_score_identity_migration as verifier


CURRENT_COMMIT = "1" * 40
CURRENT_TOP = "2" * 64
CURRENT_NESTED = "3" * 64


def write_json(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return verifier.sha256(path)


def make_score(root: Path, tag: str, epoch: str, nested_epoch: str | None) -> dict:
    score_dir = root / tag
    if epoch == "legacy":
        top_identity = (verifier.LEGACY_GIT_COMMIT, verifier.LEGACY_TOP_SOURCE_SHA256)
    else:
        top_identity = (CURRENT_COMMIT, CURRENT_TOP)
    outputs = {
        "nested_scorer_summary": None,
        "nested_scorer_summary_sha256": None,
    }
    if nested_epoch is not None:
        if nested_epoch == "legacy":
            nested_identity = (
                verifier.LEGACY_GIT_COMMIT,
                verifier.LEGACY_NESTED_SOURCE_SHA256,
            )
        else:
            nested_identity = (CURRENT_COMMIT, CURRENT_NESTED)
        nested_sha = write_json(
            score_dir / "scores" / "summary.json",
            {"git_commit": nested_identity[0], "source_sha256": nested_identity[1]},
        )
        outputs = {
            "nested_scorer_summary": "scores/summary.json",
            "nested_scorer_summary_sha256": nested_sha,
        }
    top_sha = write_json(
        score_dir / "summary.json",
        {
            "git_commit": top_identity[0],
            "source_sha256": top_identity[1],
            "outputs": outputs,
        },
    )
    return {
        "drop_id": tag,
        "intake_dir": str(root / f"intake-{tag}"),
        "intake_summary_sha256": hashlib.sha256(tag.encode()).hexdigest(),
        "score_dir": str(score_dir),
        "score_summary_sha256": top_sha,
    }


def make_args(tmp_path: Path, rows: list[dict], *, legacy: int, current: int, empty: int):
    registry = tmp_path / "registry.jsonl"
    registry.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return argparse.Namespace(
        registry=registry,
        expect_registry_sha256=verifier.sha256(registry),
        current_git_commit=CURRENT_COMMIT,
        current_top_source_sha256=CURRENT_TOP,
        current_nested_source_sha256=CURRENT_NESTED,
        expect_legacy_transactions=legacy,
        expect_current_transactions=current,
        expect_without_nested=empty,
        max_transactions=10,
    )


def test_exact_legacy_and_current_epochs_pass_without_score_values(tmp_path: Path):
    rows = [
        make_score(tmp_path, "legacy", "legacy", "legacy"),
        make_score(tmp_path, "current", "current", "current"),
        make_score(tmp_path, "empty", "legacy", None),
    ]
    receipt = verifier.verify(
        make_args(tmp_path, rows, legacy=2, current=1, empty=1)
    )
    assert receipt["top_level_epoch_counts"] == {"legacy": 2, "current": 1}
    assert receipt["security"]["blind_score_csv_opened"] is False


@pytest.mark.parametrize(
    ("top_epoch", "nested_epoch"),
    [("legacy", "current"), ("current", "legacy")],
)
def test_mixed_epoch_fails_closed(
    tmp_path: Path, top_epoch: str, nested_epoch: str
):
    rows = [make_score(tmp_path, "mixed", top_epoch, nested_epoch)]
    args = make_args(
        tmp_path,
        rows,
        legacy=int(top_epoch == "legacy"),
        current=int(top_epoch == "current"),
        empty=0,
    )
    with pytest.raises(verifier.VerificationError, match="mixed"):
        verifier.verify(args)


def test_unknown_top_identity_fails_closed(tmp_path: Path):
    row = make_score(tmp_path, "unknown", "current", "current")
    summary_path = Path(row["score_dir"]) / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["source_sha256"] = "4" * 64
    row["score_summary_sha256"] = write_json(summary_path, summary)
    with pytest.raises(verifier.VerificationError, match="unknown top-level"):
        verifier.verify(make_args(tmp_path, [row], legacy=0, current=1, empty=0))


def test_summary_hash_tamper_fails_closed(tmp_path: Path):
    row = make_score(tmp_path, "tamper", "legacy", "legacy")
    summary_path = Path(row["score_dir"]) / "summary.json"
    summary_path.write_text(
        summary_path.read_text(encoding="utf-8") + " ", encoding="utf-8"
    )
    with pytest.raises(verifier.VerificationError, match="SHA-256 mismatch"):
        verifier.verify(make_args(tmp_path, [row], legacy=1, current=0, empty=0))
