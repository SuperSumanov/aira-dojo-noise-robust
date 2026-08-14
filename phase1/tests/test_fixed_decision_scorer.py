import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from phase1 import fixed_decision_scorer as scorer
from phase1 import verify_fixed_decision_scorer as verifier


def card(card_id: str, code: str, op: str, run: str) -> dict:
    return {
        "id": card_id,
        "task": "task",
        "run": run,
        "code": code,
        "lineage": {"depth": 1, "step": 2, "n_siblings": 2, "op": op},
    }


def test_feature_contract_matches_independent_verifier():
    sample = card(
        "a",
        "import sklearn\nfrom xgboost import XGBClassifier\n# seed\nprint('x')\n",
        "Improve",
        "r1",
    )
    assert scorer.static_feature_dict(sample) == verifier.static_feature_dict(sample)
    assert scorer.code_view("x" * 20_000) == "x" * 20_000
    long = "a" * 5_000 + "middle" + "z" * 15_000
    assert "middle" not in scorer.code_view(long)
    assert scorer.code_view(long) == verifier.code_view(long)


def test_symmetric_design_is_exactly_antisymmetric():
    differences = np.asarray([[1.0, -2.0], [3.0, 4.0]])
    design, labels = scorer.symmetric_design(differences)
    assert np.array_equal(design[:2], differences)
    assert np.array_equal(design[2:], -differences)
    assert np.array_equal(labels, np.asarray([1, 1, 0, 0]))


def test_forbidden_train_inputs_fail_closed():
    for name in ("decision_test.jsonl", "frozen.jsonl", "held_pairs.jsonl"):
        with pytest.raises(scorer.IntegrityError):
            scorer.reject_forbidden_path(Path(name), "input")
    scorer.reject_forbidden_path(Path("decision_train.jsonl"), "input")


def blind_row(
    card_id: str = "a",
    run: str = "journal:" + "a" * 64,
    started: str = "2026-08-14T01:00:01Z",
) -> dict:
    code = "print('blind')"
    return {
        "card_id": card_id,
        "task": "task",
        "run_id": run,
        "code": code,
        "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
        "lineage": {"depth": 1, "step": 2, "n_siblings": 3, "op": "Draft", "parent": "p"},
        "generation_started_at_utc": started,
        "source_sha256": "a" * 64,
    }


def write_manifest(path: Path, rows: list[dict]) -> str:
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8", newline="\n")
    return hashlib.sha256(text.encode()).hexdigest()


def test_blind_manifest_accepts_only_strict_future_code_schema(tmp_path: Path):
    path = tmp_path / "blind.jsonl"
    digest = write_manifest(path, [blind_row()])
    cards, audit = scorer.load_blind_manifest(
        path,
        digest,
        {"old:0"},
        datetime(2026, 8, 14, 1, 0, 0, tzinfo=timezone.utc),
    )
    assert set(cards) == {"a"}
    assert audit["labels_read"] is False
    assert audit["post_execution_fields_read"] is False

    leaked = blind_row()
    leaked["label"] = {"graded": 1.0}
    digest = write_manifest(path, [leaked])
    with pytest.raises(scorer.IntegrityError, match="schema"):
        scorer.load_blind_manifest(
            path, digest, set(), datetime(2026, 8, 14, 1, 0, tzinfo=timezone.utc)
        )


def test_blind_manifest_rejects_old_run_and_nonfuture_time(tmp_path: Path):
    path = tmp_path / "blind.jsonl"
    digest = write_manifest(path, [blind_row(run="old:0")])
    with pytest.raises(scorer.IntegrityError, match="pre-cutoff"):
        scorer.load_blind_manifest(
            path, digest, {"old:0"}, datetime(2026, 8, 14, 1, 0, tzinfo=timezone.utc)
        )
    digest = write_manifest(path, [blind_row(started="2026-08-14T01:00:00Z")])
    with pytest.raises(scorer.IntegrityError, match="non-prospective"):
        scorer.load_blind_manifest(
            path, digest, set(), datetime(2026, 8, 14, 1, 0, tzinfo=timezone.utc)
        )


def test_blind_manifest_rejects_precutoff_endpoint_and_exact_code(tmp_path: Path):
    path = tmp_path / "blind.jsonl"
    row = blind_row()
    digest = write_manifest(path, [row])
    activated = datetime(2026, 8, 14, 1, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(scorer.IntegrityError, match="endpoint ID"):
        scorer.load_blind_manifest(path, digest, set(), activated, {row["card_id"]}, set())
    with pytest.raises(scorer.IntegrityError, match="exact code"):
        scorer.load_blind_manifest(path, digest, set(), activated, set(), {row["code_sha256"]})


def test_blind_manifest_rejects_spoofed_run_identity_and_lineage_types(tmp_path: Path):
    path = tmp_path / "blind.jsonl"
    activated = datetime(2026, 8, 14, 1, 0, 0, tzinfo=timezone.utc)
    row = blind_row(run="journal:" + "b" * 64)
    digest = write_manifest(path, [row])
    with pytest.raises(scorer.IntegrityError, match="run/source identity"):
        scorer.load_blind_manifest(path, digest, set(), activated)

    row = blind_row()
    row["lineage"]["depth"] = "1"
    digest = write_manifest(path, [row])
    with pytest.raises(scorer.IntegrityError, match="lineage depth"):
        scorer.load_blind_manifest(path, digest, set(), activated)


def test_bundle_roundtrip_matches_fitted_endpoint_scores(tmp_path: Path):
    pytest.importorskip("scipy")
    pytest.importorskip("sklearn")
    cards = {
        "a": card("a", "import sklearn\nmodel = RandomForestClassifier()\n# alpha alpha", "Improve", "r1"),
        "b": card("b", "print('baseline')\n# beta beta", "Debug", "r1"),
        "c": card("c", "import sklearn\nmodel = RandomForestClassifier()\n# alpha gamma", "Improve", "r2"),
        "d": card("d", "print('baseline')\n# beta delta", "Debug", "r2"),
        "e": card("e", "import sklearn\nmodel = RandomForestClassifier()\n# alpha epsilon", "Improve", "r3"),
        "f": card("f", "print('baseline')\n# beta zeta", "Debug", "r3"),
    }
    rows = [
        {"better": "a", "worse": "b"},
        {"better": "c", "worse": "d"},
        {"better": "e", "worse": "f"},
    ]
    arrays, _, fitted = scorer.fit_bundle(cards, rows)
    path = tmp_path / "scorer.npz"
    scorer.atomic_npz(path, **arrays)
    restored = scorer.load_bundle(path)
    rescored = scorer.score_cards(cards, restored)
    for card_id in cards:
        for arm in ("static_lr", "char_tfidf_lr"):
            assert rescored[card_id][arm] == pytest.approx(fitted[card_id][arm], abs=1e-12)
