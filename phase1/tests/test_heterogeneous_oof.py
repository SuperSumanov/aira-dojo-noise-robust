import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from phase1 import heterogeneous_oof as h


def card(card_id: str, code: str, op: str = "Draft", run: str = "r0"):
    return {
        "id": card_id,
        "task": "task",
        "run": run,
        "code": code,
        "lineage": {"depth": 1, "step": 2, "n_siblings": 3, "op": op},
    }


def row(index: int, better: str, worse: str, run: str, parent: str = "p"):
    return {
        "row_index": index,
        "task": "task",
        "run": run,
        "parent": parent,
        "better": better,
        "worse": worse,
        "gap_raw": 0.1,
    }


def test_code_view_and_operator_are_fixed():
    short = "x" * 20_000
    assert h.code_view(short) == short
    long = "a" * 5_000 + "m" * 100 + "z" * 15_000
    viewed = h.code_view(long)
    assert viewed.startswith("a" * 5_000)
    assert viewed.endswith("z" * 15_000)
    assert "m" not in viewed
    assert h.normalized_op("Debug") == "debug"
    assert h.normalized_op("unknown") == "other"


def test_static_features_are_decision_time_only():
    source = card("a", "import sklearn\nprint('x')\n", op="Improve")
    source["label"] = {"graded": 1.0}
    source["obs"] = {"runtime_s": 999, "stdout_tail": "secret", "val_at_low": 0.9}
    values = h.static_feature_dict(source)
    assert values["m_sklearn"] == 1.0
    assert values["op_improve"] == 1.0
    assert sum(values[f"op_{name}"] for name in h.OP_NAMES) == 1.0
    assert not any("runtime" in key or "stdout" in key or "val" in key for key in values)


def test_symmetric_design_is_exactly_antisymmetric():
    differences = np.asarray([[1.0, -2.0], [3.0, 4.0]])
    design, labels = h.symmetric_design(differences)
    assert np.array_equal(design[:2], differences)
    assert np.array_equal(design[2:], -differences)
    assert np.array_equal(labels, np.asarray([1, 1, 0, 0]))


def test_outer_isolation_rejects_run_and_endpoint_overlap():
    rows = [row(0, "a", "b", "r0"), row(1, "c", "d", "r1")]
    assert h.ensure_fit_valid_isolation(rows, [0], [1])["run_overlap"] == 0
    rows[1]["run"] = "r0"
    with pytest.raises(h.IntegrityError, match="run overlap"):
        h.ensure_fit_valid_isolation(rows, [0], [1])
    rows[1]["run"] = "r1"
    rows[1]["better"] = "a"
    with pytest.raises(h.IntegrityError, match="endpoint overlap"):
        h.ensure_fit_valid_isolation(rows, [0], [1])


def test_pair_logit_aggregation_preserves_direction():
    rows = [
        row(0, "a", "b", "r0"),
        row(1, "a", "c", "r0"),
        row(2, "b", "c", "r0"),
    ]
    scores = h.aggregate_pair_logits(rows, [0, 1, 2], [2.0, 3.0, 1.0])
    assert scores["a"] > scores["b"] > scores["c"]


def test_parent_rank_ensemble_is_label_free_and_ordered():
    rows = [
        row(0, "a", "b", "r0"),
        row(1, "a", "c", "r0"),
        row(2, "b", "c", "r0"),
    ]
    left = {"a": 3.0, "b": 2.0, "c": 1.0}
    right = {"a": 1.0, "b": 3.0, "c": 2.0}
    scores = h.parent_rank_ensemble(rows, left, right)
    assert scores["b"] > scores["a"] > scores["c"]


def test_orientation_oracle_is_strict_total_order():
    rows = [
        row(0, "a", "b", "r0"),
        row(1, "a", "c", "r0"),
        row(2, "b", "c", "r0"),
    ]
    scores = h.orientation_oracle_scores(rows)
    assert scores["a"] > scores["b"] > scores["c"]


def test_forbidden_pair_path_fails_closed():
    for name in ("decision_test.jsonl", "frozen_pairs.jsonl", "held.jsonl"):
        with pytest.raises(h.IntegrityError):
            h.reject_forbidden_path(Path(name), "pair")
    h.reject_forbidden_path(Path("decision_train.jsonl"), "pair")


def test_train_card_loader_retains_only_allowlisted_fields(tmp_path: Path):
    selected_code = "print('selected')"
    selected = {
        "id": "a",
        "task": {"name": "task"},
        "run_id": "r0",
        "code": selected_code,
        "lineage": {"depth": 1, "step": 1, "n_siblings": 2, "op": "Draft"},
        "label": {"graded": 0.9},
        "obs": {"runtime_s": 100, "stdout_tail": "do not retain"},
    }
    excluded = {
        "id": "x",
        "task": {"name": "other"},
        "run_id": "rx",
        "code": "excluded",
        "lineage": {},
        "label": {"graded": 1.0},
        "obs": {"stdout_tail": "excluded"},
    }
    cards_path = tmp_path / "cards.jsonl"
    raw = "".join(json.dumps(item) + "\n" for item in (selected, excluded))
    cards_path.write_text(raw, encoding="utf-8", newline="\n")
    manifest = [
        {
            "card_id": "a",
            "task": "task",
            "run_id": "r0",
            "code_chars": len(selected_code),
            "code_sha256": hashlib.sha256(selected_code.encode()).hexdigest(),
        }
    ]
    loaded, audit = h.load_train_cards(
        cards_path, manifest, hashlib.sha256(raw.encode()).hexdigest()
    )
    assert set(loaded) == {"a"}
    assert set(loaded["a"]) == {"id", "task", "run", "code", "lineage"}
    assert audit["label_fields_retained"] == 0
    assert audit["post_execution_fields_retained"] == 0


def test_gate_thresholds_are_literal():
    metrics = {
        "pair": {"overall": 0.52},
        "top1": {"overall": 0.50},
        "utility": {"overall": 0.55},
        "task_consistency": {"supported_tasks": 15, "nonchance_share": 0.60},
    }
    comparison = {
        "top1": {"overall": 0.03, "run_macro_ci95": [1e-6, 0.1], "task_macro_ci95": [1e-6, 0.1]},
        "utility": {"overall": 0.02, "run_macro_ci95": [1e-6, 0.1], "task_macro_ci95": [1e-6, 0.1]},
    }
    gate = h.unlock_gate(metrics, comparison, {"integrity": True})
    assert gate["all"] is True
    comparison["top1"]["run_macro_ci95"][0] = 0.0
    assert h.unlock_gate(metrics, comparison, {"integrity": True})["all"] is False


def test_fold_checkpoint_resume_is_keyed_and_score_exact(tmp_path: Path):
    fold_dir = tmp_path / "fold_0"
    fold_dir.mkdir()
    score_path = fold_dir / "valid_scores.npz"
    np.savez_compressed(
        score_path,
        card_ids=np.asarray(["a", "b"]),
        **{arm: np.asarray([1.0, -1.0]) for arm in h.BASE_ARMS},
    )
    summary = {
        "status": "FOLD_COMPLETE",
        "fold": 0,
        "checkpoint_key": "key-a",
        "valid_scores_sha256": h.sha256(score_path),
    }
    (fold_dir / "fold_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    restored, loaded = h.run_fold(
        0, [], [], {}, np.empty((0, 0)), {}, [], tmp_path, "key-a"
    )
    assert loaded == summary
    assert restored["static_lr"] == {"a": 1.0, "b": -1.0}
    with pytest.raises(h.IntegrityError, match="checkpoint"):
        h.run_fold(0, [], [], {}, np.empty((0, 0)), {}, [], tmp_path, "key-b")


def test_linear_operator_fit_learns_opposite_directions():
    pytest.importorskip("sklearn")
    cards = {
        "a": card("a", "x", "Improve", "r0"),
        "b": card("b", "x", "Debug", "r0"),
        "c": card("c", "x", "Improve", "r1"),
        "d": card("d", "x", "Debug", "r1"),
    }
    ids = sorted(cards)
    names, op_indices = h.feature_names(cards[ids[0]])
    matrix = np.asarray(
        [[h.static_feature_dict(cards[item])[name] for name in names] for item in ids]
    )
    position = {item: index for index, item in enumerate(ids)}
    rows = [row(0, "a", "b", "r0"), row(1, "c", "d", "r1")]
    scores, diagnostic = h.fit_linear_scores(
        matrix, position, rows, [0], ["c", "d"], op_indices, 1.0
    )
    assert diagnostic["accepted"] is True
    assert scores["c"] > scores["d"]
