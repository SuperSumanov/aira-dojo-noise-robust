from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path

from phase1 import audit_tree_content_selective_parent_recovery_887 as producer
from phase1 import verify_tree_content_selective_parent_recovery_887 as verifier


ROOT = Path(__file__).parents[2]
PHASE1 = ROOT / "phase1"
PROTOCOL_PATH = PHASE1 / "tree_content_selective_parent_recovery_887_protocol_v1.json"


def _row(*, correct: bool, margin: Fraction, run: str = "run", task: str = "task") -> producer.EdgeRecord:
    return producer.EdgeRecord(
        task=task,
        run=run,
        candidates=3,
        unique_top=True,
        correct=correct,
        top_score=Fraction(9, 10),
        margin=margin,
    )


def test_protocol_freezes_unseen_margin_readout_and_run_split() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    assert protocol["status"] == (
        "OUTCOME_BLIND_DEVELOPMENT_SPLIT_FROZEN_BEFORE_MARGIN_READOUT"
    )
    assert protocol["freeze_state"] == {
        "snapshot_sha256": (
            "887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697"
        ),
        "snapshot_runs": 435,
        "snapshot_endpoints": 11906,
        "snapshot_tasks": 34,
        "target522_candidate_seen": False,
        "latest_snapshot_when_frozen": (
            "887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697"
        ),
        "margin_distribution_seen": False,
        "margin_correctness_profile_seen": False,
        "selected_margin_threshold_seen": False,
        "chronological_test_profile_seen": False,
    }
    split = protocol["run_disjoint_split"]
    assert split["train_runs"] == 290
    assert split["test_runs"] == 145
    assert split["edge_level_random_split_allowed"] is False
    assert split["test_labels_used_for_threshold_selection"] is False
    assert protocol["confidence_rule"]["train_precision_target"] == "99/100"
    assert protocol["primary_gates"]["minimum_test_precision"] == "49/50"
    assert protocol["primary_gates"]["minimum_test_coverage"] == "1/2"
    assert list(protocol["resources"].values()) == [0, 0, 0, 0]


def test_protocol_dependency_hashes_are_exact() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    bindings = protocol["immutable_inputs"]
    for role in (
        "producer_snapshot_loader",
        "independent_snapshot_loader",
        "producer_fingerprint",
        "independent_fingerprint",
    ):
        path = ROOT / bindings[role]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == bindings[f"{role}_sha256"]


def test_threshold_selection_maximizes_support_subject_to_train_precision() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    rows = (
        [_row(correct=True, margin=Fraction(1, 2)) for _ in range(500)]
        + [_row(correct=True, margin=Fraction(1, 10)) for _ in range(100)]
        + [_row(correct=False, margin=Fraction(1, 10)) for _ in range(10)]
    )
    selected = producer.select_threshold(rows, protocol)
    assert selected["selected"] is True
    assert selected["threshold"] == producer.exact(Fraction(1, 2))
    assert selected["accepted_edges"] == 500
    assert selected["correct_edges"] == 500
    assert selected["precision"] == producer.exact(Fraction(1, 1))

    independent = [
        verifier.Observation(
            task=row.task,
            run=row.run,
            candidate_count=row.candidates,
            unique=row.unique_top,
            right=row.correct,
            best=row.top_score,
            gap=row.margin,
        )
        for row in rows
    ]
    assert verifier.threshold_choice(independent, protocol) == selected


def test_threshold_selection_fails_closed_without_minimum_support() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    rows = [_row(correct=True, margin=Fraction(1, 2)) for _ in range(499)]
    selected = producer.select_threshold(rows, protocol)
    assert selected["selected"] is False
    assert selected["threshold"] is None
    assert selected["accepted_edges"] == 0


def test_selective_profile_and_three_wrong_denominators_are_distinct() -> None:
    rows = (
        [_row(correct=True, margin=Fraction(1, 2)) for _ in range(50)]
        + [
            producer.EdgeRecord(
                task="task",
                run="run",
                candidates=5,
                unique_top=True,
                correct=False,
                top_score=Fraction(9, 10),
                margin=Fraction(1, 2),
            )
        ]
        + [_row(correct=True, margin=Fraction(1, 10)) for _ in range(49)]
    )
    profile = producer.evaluate(rows, Fraction(1, 2))
    assert profile["selected_edges"] == 51
    assert profile["selected_correct_edges"] == 50
    assert profile["selected_precision"] == producer.exact(Fraction(50, 51))
    assert profile["selected_coverage"] == producer.exact(Fraction(51, 100))

    wrong_children = 1
    wrong_alternatives = sum(row.candidates - 1 for row in rows)
    micro = Fraction(wrong_children, wrong_alternatives)
    uniform = Fraction(1, rows[50].candidates - 1) / len(rows)
    adversarial = Fraction(wrong_children, len(rows))
    assert micro != uniform
    assert uniform != adversarial


def test_independent_verifier_does_not_import_producer() -> None:
    source = (
        PHASE1 / "verify_tree_content_selective_parent_recovery_887.py"
    ).read_text(encoding="utf-8")
    assert "audit_tree_content_selective_parent_recovery_887" not in source
    assert "verify_tree_within_stratum_forward_target522" in source
    assert "verify_prospective_fuzzy_code_clones" in source
    assert "producer_imported" in source


def test_producer_and_independent_candidate_recomputation_match_synthetic() -> None:
    parent_code = "\n".join(
        ["values = list(range(20))", "total = sum(values)"]
        + [f"total = total + {index}" for index in range(20)]
        + ["print(total)"]
    )
    alternative_code = "\n".join(
        ["values = {str(i): i for i in range(20)}", "total = 1"]
        + [f"total = total * ({index} + 1)" for index in range(1, 20)]
        + ["print(values.get(str(total), 0))"]
    )
    child_code = parent_code + "\nprint(total / 2)\n"
    graph = {
        "parent": {"task": "task", "run": "run", "parent": "outside-a", "depth": 0},
        "alternative": {
            "task": "task",
            "run": "run",
            "parent": "outside-b",
            "depth": 0,
        },
        "child": {"task": "task", "run": "run", "parent": "parent", "depth": 1},
    }
    payloads = {
        "parent": {"code": parent_code},
        "alternative": {"code": alternative_code},
        "child": {"code": child_code},
    }
    blind = producer.snapshot_impl.BlindSnapshot(
        snapshot_sha256="0" * 64,
        cards=graph,
        card_payloads=payloads,
        card_raw_rows={},
        runs={},
        run_raw_rows={},
        registry_raw_rows=(),
        bindings={},
    )
    view = verifier.snapshot_check.SnapshotView(
        sha256="0" * 64,
        graph_cards=graph,
        card_objects=payloads,
        card_lines={},
        run_objects={},
        run_lines={},
        registry_lines=(),
        bindings={},
    )
    producer_fingerprints, producer_by_run = producer.fingerprint_population(blind)
    verifier_fingerprints, verifier_by_run = verifier.fingerprints(view)
    assert producer_fingerprints == verifier_fingerprints
    assert producer_by_run == verifier_by_run
    produced, produced_inventory = producer.edge_records(
        blind, producer_fingerprints, producer_by_run
    )
    verified, verified_inventory = verifier.observations(
        view, verifier_fingerprints, verifier_by_run
    )
    assert produced_inventory == verified_inventory
    assert len(produced) == len(verified) == 1
    assert produced[0].task == verified[0].task
    assert produced[0].run == verified[0].run
    assert produced[0].candidates == verified[0].candidate_count
    assert produced[0].unique_top == verified[0].unique
    assert produced[0].correct == verified[0].right
    assert produced[0].top_score == verified[0].best
    assert produced[0].margin == verified[0].gap


def test_output_security_contract_forbids_identity_and_prospective_values() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    assert protocol["verification"]["raw_identity_or_per_edge_output_allowed"] is False
    boundary = protocol["claim_boundary"]
    assert boundary["recorded_parent_is_external_semantic_or_causal_truth"] is False
    assert boundary["orphan_edges_are_validated_or_repaired"] is False
    assert boundary["future_target522_confirmation_claimed"] is False
    assert boundary["predictor_accuracy_or_search_utility_computed"] is False


def test_formal_runner_binds_protocol_implementations_and_four_recomputations() -> None:
    runner = (
        PHASE1
        / "scripts"
        / "run_tree_content_selective_parent_recovery_887_20260828.sh"
    ).read_text(encoding="utf-8")
    assert "readonly protocol_sha=a9fe1b26cec20b6725f19e30e605755aa2e854033ec0462c4a39d18e0f80f97c" in runner
    assert "readonly producer_sha=b30ecf9aca9f6e763ee7b03178f56f4749bfa84b81cd2db46e7a7f77b21b055e" in runner
    assert "readonly verifier_sha=b53ee68eeb8d40bd365c188f1b6dc635c5307a130e415c2f90726bd100f85ffb" in runner
    assert runner.count("producer_a.json") >= 5
    assert runner.count("producer_b.json") >= 2
    assert runner.count("verification_a.json") >= 4
    assert runner.count("verification_b.json") >= 2
    assert "PYTHONHASHSEED=0" in runner
    assert "PYTHONHASHSEED=1" in runner
    assert "tree-within-stratum-forward-target522/.*/candidate" in runner
    assert "gpu_api_model_fit_base_update=0/0/0/0" in runner
