import copy

from phase1.verify_source_opportunity_hurdle_baseline import (
    ARMS,
    rebuild_parent_rows,
    reconstruct_results,
    tie_mean,
)


def test_independent_tie_mean():
    assert tie_mean([(2.0, 0.0), (2.0, 1.0), (1.0, 1.0)]) == 0.5


def _candidate(parent, task, run, child, scoreable, quality, feasibility):
    scores = {
        "quality_static": quality,
        "quality_tfidf": quality,
        "scoreability_static": feasibility,
        "scoreability_tfidf": feasibility,
        "hurdle_static": quality * feasibility,
        "hurdle_tfidf": quality * feasibility,
    }
    return {
        "role": "frozen", "parent": parent, "task": task, "run_id": run,
        "child_id": child, "scoreable": scoreable,
        "utility": 0.8 if scoreable else 0.0, **scores,
    }


def test_rebuild_parent_rows_is_order_invariant():
    candidates = [
        _candidate("p", "task", "run", "bad", False, 0.9, 0.1),
        _candidate("p", "task", "run", "good", True, 0.7, 0.9),
    ]
    first = rebuild_parent_rows(candidates)
    second = rebuild_parent_rows(list(reversed(candidates)))
    assert first == second
    assert first[0]["quality_tfidf_utility"] == 0.0
    assert first[0]["hurdle_tfidf_utility"] == 0.8


def test_reconstructed_gate_uses_frozen_headline_not_static_swap():
    rows = []
    for index in range(12):
        candidates = [
            _candidate(f"p{index}", f"task{index // 6}", f"run{index}", f"bad{index}", False, 0.9, 0.1),
            _candidate(f"p{index}", f"task{index // 6}", f"run{index}", f"good{index}", True, 0.7, 0.9),
        ]
        rows.extend(rebuild_parent_rows(candidates))
    result, _ = reconstruct_results(copy.deepcopy(rows))
    assert result["method_positive_claim_allowed"] is True
    assert result["status"] == "VERIFIED_POSITIVE_HURDLE_METHOD"
