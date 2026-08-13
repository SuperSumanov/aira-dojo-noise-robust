import hashlib
import json
from pathlib import Path

import pytest

from phase1 import pairgraph_intervention as p
from phase1 import verify_pairgraph_intervention as v


def test_gap_bins_are_right_open_at_frozen_edges():
    assert p.gap_bin(0.0) == 0
    assert p.gap_bin(0.000099999) == 0
    assert p.gap_bin(0.0001) == 1
    assert p.gap_bin(0.01) == 5
    assert p.gap_bin(0.3) == 8
    assert p.gap_label(0) == "[0,0.0001)"
    assert p.gap_label(8) == "[0.3,inf)"
    with pytest.raises(p.IntegrityError):
        p.gap_bin(-1.0)


def test_orientation_respects_metric_direction_and_rounding():
    grades = {"a": 0.9, "b": 0.1}
    assert p.orient_pair("a", "b", grades, False) == ("a", "b", 0.8)
    assert p.orient_pair("a", "b", grades, True) == ("b", "a", 0.8)
    assert p.orient_pair("a", "b", {"a": 1.0, "b": 1.0}, False) is None


def test_score_tie_and_endpoint_consistency_fail_closed():
    assert p.score_hit(1.0) == 1.0
    assert p.score_hit(-1.0) == 0.0
    assert p.score_hit(0.0) == 0.5
    endpoints = {}
    metadata = {"task": "t", "fold": 0, "run": "r", "parent": "q"}
    scores = {arm: 1.0 for arm in p.ARMS}
    p.register_endpoint(endpoints, "a", metadata, scores)
    p.register_endpoint(endpoints, "a", metadata, dict(scores))
    changed = dict(scores)
    changed[p.HEADLINE_ARM] += 1e-3
    with pytest.raises(p.IntegrityError, match="score inconsistency"):
        p.register_endpoint(endpoints, "a", metadata, changed)


def synthetic_population():
    grades = {
        "a1": 0.9,
        "a0": 0.1,
        "b1": 0.8,
        "b0": 0.2,
        "c1": 0.7,
        "c0": 0.3,
    }
    endpoints = {}
    rows = []
    for index, (run, parent, better, worse) in enumerate(
        (("r1", "p1", "a1", "a0"), ("r2", "p2", "b1", "b0"), ("r3", "p3", "c1", "c0"))
    ):
        for card_id in (better, worse):
            endpoints[card_id] = {
                "task": "t",
                "fold": 0,
                "run": run,
                "parent": parent,
                "scores": {arm: grades[card_id] for arm in p.ARMS},
            }
        rows.append(
            {
                "row_index": index,
                "task": "t",
                "fold": 0,
                "run": run,
                "parent": parent,
                "better": better,
                "worse": worse,
                "gap": round(grades[better] - grades[worse], 6),
            }
        )
    return rows, endpoints, grades


def test_finite_population_is_crossrun_and_transport_exact():
    rows, endpoints, grades = synthetic_population()
    populations = p.build_finite_populations(rows, endpoints, grades, {"t": False})
    assert populations["support"]["common_sibling_rows"] == 3
    assert populations["support"]["crossrun_candidate_pairs"] == 12
    assert populations["support"]["same_run_pairs_excluded"] == 3
    assert len(populations["supported"]) == 1
    for graph in p.GRAPH_NAMES:
        metrics = p.graph_metrics(populations, p.HEADLINE_ARM, graph)
        assert metrics["weighted_rows"] == 3
        assert metrics["micro_accuracy"] == 1.0
        assert metrics["task_macro_accuracy"] == 1.0
    assert p.graph_metrics(populations, p.HEADLINE_ARM, "sibling")["hard_share"] == 0.0


def test_independent_population_implementation_matches_synthetic_fixture():
    rows, endpoints, grades = synthetic_population()
    producer = p.build_finite_populations(rows, endpoints, grades, {"t": False})
    verifier = v.enumerate_populations(rows, endpoints, grades, {"t": False})
    assert producer["support"] == verifier["support"]
    for arm in p.ARMS:
        for graph in p.GRAPH_NAMES:
            left = p.graph_metrics(producer, arm, graph)
            right = v.evaluate(verifier, arm, graph)
            assert left == right


def test_low_candidate_stratum_is_removed_from_all_graphs():
    rows, endpoints, grades = synthetic_population()
    endpoints = {key: value for key, value in endpoints.items() if key.startswith(("a", "b"))}
    rows = rows[:2]
    grades = {key: value for key, value in grades.items() if key in endpoints}
    populations = p.build_finite_populations(rows, endpoints, grades, {"t": False})
    assert populations["support"]["common_sibling_rows"] == 0
    assert populations["supported"] == set()


def test_selected_card_loader_retains_only_allowlisted_grade(tmp_path: Path):
    selected = {
        "id": "a",
        "task": {"name": "t"},
        "run_id": "r",
        "lineage": {"parent_id": "p"},
        "label": {"graded": 0.7},
        "code": "do not retain",
        "obs": {"runtime": 9, "stdout": "do not retain"},
    }
    excluded = {
        "id": "x",
        "task": {"name": "x"},
        "run_id": "rx",
        "lineage": {"parent_id": "px"},
        "label": {"graded": 1.0},
        "code": "excluded",
    }
    raw = "".join(json.dumps(item) + "\n" for item in (selected, excluded))
    path = tmp_path / "cards.jsonl"
    path.write_text(raw, encoding="utf-8", newline="\n")
    endpoints = {
        "a": {
            "task": "t",
            "run": "r",
            "parent": "p",
            "fold": 0,
            "scores": {arm: 0.0 for arm in p.ARMS},
        }
    }
    grades, audit = p.load_selected_grades(
        path, endpoints, hashlib.sha256(raw.encode()).hexdigest()
    )
    assert grades == {"a": 0.7}
    assert audit["retained_fields"] == ["id", "task", "graded"]
    assert audit["code_fields_retained"] == 0
    assert audit["observation_fields_retained"] == 0
    assert audit["non_allowlisted_cards_retained"] == 0


def test_task_bootstrap_is_reproducible_and_paired():
    left = {"a": 0.8, "b": 0.6, "c": 0.4}
    right = {"a": 0.5, "b": 0.5, "c": 0.5}
    first = p.bootstrap_delta(left, right, reps=100, seed=17)
    second = p.bootstrap_delta(left, right, reps=100, seed=17)
    assert first == second
    assert first["estimate"] == pytest.approx(0.1)
    assert first["tasks"] == 3


def test_literal_gates_require_replication_and_integrity():
    contrasts = {}
    for arm in p.ARMS:
        contrasts[arm] = {
            "total_pairing_inflation": {"estimate": 0.06, "ci95": [0.01, 0.1]},
            "gap_composition_component": {"estimate": 0.04, "ci95": [0.01, 0.08]},
            "topology_residual": {"estimate": 0.02, "ci95": [-0.01, 0.05]},
            "gap_component_share_of_positive_total": 2 / 3,
        }
    gates = p.make_gates({"integrity": True}, contrasts)
    assert gates["inflation"]["all"] is True
    assert gates["gap_composition"]["all"] is True
    assert gates["topology_residual"]["all"] is False
    assert p.status_from_gates(gates) == "PAIRGRAPH_INFLATION_SUPPORTED__GAP_COMPOSITION_SUPPORTED"
    contrasts[p.ARMS[0]]["total_pairing_inflation"]["estimate"] = -0.01
    contrasts[p.ARMS[1]]["total_pairing_inflation"]["estimate"] = -0.01
    assert p.make_gates({"integrity": True}, contrasts)["inflation"]["all"] is False
    assert p.make_gates({"integrity": False}, contrasts)["inflation"]["all"] is False


def test_forbidden_paths_and_verifier_independence():
    for name in ("decision_frozen.jsonl", "held_pairs.csv", "test.csv"):
        with pytest.raises(p.IntegrityError):
            p.reject_forbidden_path(Path(name), "input")
    p.reject_forbidden_path(Path("decision_train.jsonl"), "input")
    verifier = Path(p.__file__).with_name("verify_pairgraph_intervention.py").read_text(
        encoding="utf-8"
    )
    assert not any(
        line.strip().startswith(("import pairgraph_intervention", "from phase1 import pairgraph_intervention"))
        for line in verifier.splitlines()
    )
