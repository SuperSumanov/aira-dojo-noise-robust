import argparse
import hashlib
import json
from pathlib import Path

import pytest

from phase1.temporal_prediction_escrow import EscrowError, load_pairs, load_views, run, sha256_file
from phase1.verify_temporal_prediction_escrow import verify


ROOT = Path(__file__).parents[2]
SCORER = ROOT / "phase1" / "results" / "fixed_decision_scorer_v11_20260814"
BUNDLE_SHA = "c4b9713d5a994c90ac8e24674154ae78d39f7c7961473078c1c7d61ce1c15d23"
RECEIPT_SHA = "cfab01a80536a50ef21c47ac269c7ce54a11a3b1f0b6daa5700873cbb02ce178"
DENYLIST_SHA = "2f0cc4f3dc203801c569237716ba82cbc2bde2f854b67eee6efa9452e92447e6"


def view(card_id: str, code: str) -> dict:
    return {
        "card_id": card_id,
        "task": "synthetic-task",
        "run_id": "synthetic-run",
        "code": code,
        "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
        "lineage": {"parent": "parent", "depth": 1, "step": 2, "n_siblings": 1, "op": "Debug"},
        "source_archive_sha256": "a" * 64,
        "source_journal_sha256": "b" * 64,
        "prospective_status": "EXCLUDED_NO_POSTACTIVATION_GENERATION_PROOF",
    }


def write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    views = tmp_path / "views.jsonl"
    structure = tmp_path / "structure.jsonl"
    rows = [view("synthetic-a", "import pandas as pd\nprint('alpha')"), view("synthetic-b", "import numpy as np\nprint('beta')")]
    views.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    structure.write_text(
        json.dumps(
            {
                "task": "synthetic-task",
                "run_id": "synthetic-run",
                "parent": "parent",
                "left": "synthetic-a",
                "right": "synthetic-b",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return views, structure


def test_prediction_escrow_roundtrip_and_independent_verifier(tmp_path: Path) -> None:
    views, structure = write_inputs(tmp_path)

    def args(output: Path) -> argparse.Namespace:
        return argparse.Namespace(
            blind_views=views,
            expect_blind_views_sha256=sha256_file(views),
            structure=structure,
            expect_structure_sha256=sha256_file(structure),
            bundle=SCORER / "fixed_scorer.npz",
            expect_bundle_sha256=BUNDLE_SHA,
            freeze_receipt=SCORER / "freeze_receipt.json",
            expect_receipt_sha256=RECEIPT_SHA,
            denylist=SCORER / "precutoff_endpoint_denylist.csv",
            expect_denylist_sha256=DENYLIST_SHA,
            repo_root=ROOT,
            output=output,
        )

    assert run(args(tmp_path / "a")) == 0
    assert run(args(tmp_path / "b")) == 0
    for name in ("endpoint_scores.csv", "pair_predictions.jsonl", "summary.json", "sha256_manifest.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    summary = json.loads((tmp_path / "a" / "summary.json").read_text())
    assert summary["inventory"]["endpoints"] == 2
    assert summary["inventory"]["pairs"] == 1
    assert summary["scope"]["label_vault_read"] is False
    verify_args = argparse.Namespace(
        blind_views=views,
        expect_blind_views_sha256=sha256_file(views),
        structure=structure,
        expect_structure_sha256=sha256_file(structure),
        bundle=SCORER / "fixed_scorer.npz",
        expect_bundle_sha256=BUNDLE_SHA,
        artifact=tmp_path / "a",
        output=tmp_path / "verify.json",
    )
    assert verify(verify_args) == 0
    assert json.loads((tmp_path / "verify.json").read_text())["max_abs_score_difference"] == {
        "char_tfidf_lr": 0.0,
        "static_lr": 0.0,
    }


def test_blind_view_rejects_label_field(tmp_path: Path) -> None:
    row = view("synthetic-a", "print('x')")
    row["label"] = {"graded": 1.0}
    path = tmp_path / "views.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(EscrowError, match="schema mismatch"):
        load_views(path, set(), set())


def test_structure_rejects_duplicate_unordered_pair(tmp_path: Path) -> None:
    cards = {
        "a": {"task": "t", "run": "r", "parent": "p"},
        "b": {"task": "t", "run": "r", "parent": "p"},
    }
    path = tmp_path / "structure.jsonl"
    rows = [
        {"task": "t", "run_id": "r", "parent": "p", "left": "a", "right": "b"},
        {"task": "t", "run_id": "r", "parent": "p", "left": "b", "right": "a"},
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    with pytest.raises(EscrowError, match="duplicate unordered"):
        load_pairs(path, cards)
