import copy

import pytest

from phase1 import tgca_discovery as module


def edge(index, task, better, worse, gap):
    return {
        "row_index": index,
        "task": task,
        "better": better,
        "worse": worse,
        "gap_raw": gap,
    }


def candidate(task, better, worse, gap):
    return {
        "task": task,
        "better": better,
        "worse": worse,
        "gap_raw": gap,
        "gap_bin": module.gap_bin(gap),
        "left": min(better, worse),
        "right": max(better, worse),
    }


def test_gap_bins_are_right_open_and_fixed():
    assert module.gap_bin(0.0) == 0
    assert module.gap_bin(0.00009999) == 0
    assert module.gap_bin(0.0001) == 1
    assert module.gap_bin(0.01) == 5
    assert module.gap_bin(0.3) == 8
    with pytest.raises(module.IntegrityError):
        module.gap_bin(-1.0)


def test_tgca_connects_components_and_controls_have_exact_task_counts():
    base = [
        edge(0, "t", "a1", "a0", 0.02),
        edge(1, "t", "b1", "b0", 0.02),
        edge(2, "t", "c1", "c0", 0.02),
    ]
    candidates = [
        candidate("t", "a1", "b0", 0.02),
        candidate("t", "b1", "c0", 0.02),
        candidate("t", "a1", "c0", 0.02),
        candidate("t", "b1", "a0", 0.02),
    ]
    ids = ["a0", "a1", "b0", "b1", "c0", "c1"]
    selections, audit = module.select_augmentations(0, base, candidates, ids)
    assert audit["augmentation_rows"] == 3
    assert all(len(selections[arm]) == 3 for arm in module.ARMS[1:])
    graph = module.graph_components(
        ids,
        [(row["better"], row["worse"]) for row in base + selections["tgca"]],
    )
    assert graph["components"] == 1
    assert graph["largest_component_share"] == 1.0


def test_tgca_underfills_cell_without_cross_bin_refill():
    base = [
        edge(0, "t", "a1", "a0", 0.02),
        edge(1, "t", "b1", "b0", 0.02),
        edge(2, "t", "c1", "c0", 0.001),
    ]
    candidates = [
        candidate("t", "a1", "b0", 0.02),
        candidate("t", "b1", "c0", 0.001),
        candidate("t", "a1", "c0", 0.001),
    ]
    ids = ["a0", "a1", "b0", "b1", "c0", "c1"]
    selections, audit = module.select_augmentations(1, base, candidates, ids)
    assert len(selections["tgca"]) == 2
    cell = audit["tgca_cells"][f"t|{module.gap_bin(0.02)}"]
    assert cell == {
        "sibling_target": 2,
        "candidate_population": 1,
        "selected": 1,
        "bridges_at_selection": 1,
    }
    assert all(len(selections[arm]) == 2 for arm in module.ARMS[1:])


def test_fold_isolation_detects_raw_code_duplicate():
    rows = [
        {**edge(0, "t", "a", "b", 0.1), "run": "r0", "parent": "p0", "fold": 0},
        {**edge(1, "t", "c", "d", 0.1), "run": "r1", "parent": "p1", "fold": 1},
    ]
    cards = {
        "a": {"code_sha256": "same"},
        "b": {"code_sha256": "b"},
        "c": {"code_sha256": "same"},
        "d": {"code_sha256": "d"},
    }
    with pytest.raises(module.IntegrityError, match="outer-fold leakage"):
        module.fold_isolation(0, rows, cards)


def comparison(delta):
    metric = {
        "overall": delta,
        "run": {"ci95": [delta / 2, delta * 1.5]},
        "task": {"ci95": [delta / 2, delta * 1.5], "per_cluster": {f"t{i}": delta for i in range(15)}},
    }
    return {"pair": copy.deepcopy(metric), "top1": copy.deepcopy(metric), "utility": metric}


def test_literal_unlock_gates_require_all_effects_and_integrity():
    rows = [
        {"task": f"t{i}", "row_index": i * module.TASK_SUPPORT_MIN_PAIRS + j}
        for i in range(15)
        for j in range(module.TASK_SUPPORT_MIN_PAIRS)
    ]
    comparisons = {
        "tgca_minus_sibling_only": comparison(0.025),
        "tgca_minus_sibling_reweight_control": comparison(0.02),
    }
    gates = module.make_gates({}, comparisons, rows, {"ok": True})
    assert gates["all"] is True
    comparisons["tgca_minus_sibling_only"]["top1"]["task"]["ci95"][0] = -0.001
    assert module.make_gates({}, comparisons, rows, {"ok": True})["all"] is False
    assert module.make_gates({}, comparisons, rows, {"ok": False})["all"] is False


def test_forbidden_pair_paths_fail_closed():
    from pathlib import Path

    for name in ("decision_frozen.jsonl", "pairs_test.csv", "held.jsonl"):
        with pytest.raises(module.IntegrityError):
            module.reject_forbidden_path(Path(name), "input")
    module.reject_forbidden_path(Path("decision_train.jsonl"), "input")


def test_independent_verifier_does_not_import_producer():
    from pathlib import Path

    source = Path(module.__file__).with_name("verify_tgca_discovery.py").read_text(
        encoding="utf-8"
    )
    assert "import tgca_discovery" not in source
    assert "from phase1 import tgca_discovery" not in source
