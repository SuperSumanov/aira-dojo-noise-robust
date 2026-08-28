from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path

from phase1 import audit_tree_content_selective_parent_forward_target522 as producer
from phase1 import verify_tree_content_selective_parent_forward_target522 as verifier


ROOT = Path(__file__).parents[2]
PHASE1 = ROOT / "phase1"
PROTOCOL_PATH = PHASE1 / "tree_content_selective_parent_forward_target522_v1.json"


def _producer_row(
    *, correct: bool, margin: Fraction, candidates: int = 3, run: str = "run", task: str = "task"
) -> producer.EdgeRecord:
    return producer.EdgeRecord(
        task=task,
        run=run,
        candidates=candidates,
        unique_top=True,
        correct=correct,
        top_score=Fraction(9, 10),
        margin=margin,
    )


def test_protocol_freezes_fixed_threshold_before_candidate() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    assert protocol["status"] == (
        "OUTCOME_BLIND_FROZEN_AFTER_887_RESULT_BEFORE_TARGET522_CANDIDATE"
    )
    freeze = protocol["freeze_state"]
    assert freeze["latest_snapshot_when_frozen"] == freeze["baseline_snapshot_sha256"]
    assert freeze["target522_candidate_seen"] is False
    assert freeze["target522_increment_profile_seen"] is False
    fixed = protocol["fixed_development_rule"]
    assert fixed["threshold"] == "1006/16929"
    assert fixed["threshold_reselection_on_future_allowed"] is False
    assert fixed["future_task_rebalancing_or_filtering_allowed"] is False
    assert fixed["future_cumulative_population_rescue_allowed"] is False
    assert protocol["activation_rule"]["manual_candidate_or_alternate_selection_root_allowed"] is False


def test_protocol_dependency_hashes_and_development_certificate_are_exact() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    for binding in protocol["immutable_inputs"].values():
        path = ROOT / binding["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == binding["sha256"]
    development = json.loads(
        (ROOT / protocol["immutable_inputs"]["development_summary"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    assert development["classification"] == (
        "DEVELOPMENT_TIME_SPLIT_HIGH_PRECISION_SELECTIVE_PARENT_RECOVERY"
    )
    assert development["threshold_selection"]["threshold"] == producer.exact(
        Fraction(1006, 16929)
    )
    assert all(development["support_gates"].values())
    assert all(development["primary_gates"].values())


def test_fixed_threshold_profile_and_wrong_denominators() -> None:
    threshold = Fraction(1, 4)
    rows = (
        [_producer_row(correct=True, margin=Fraction(1, 2)) for _ in range(50)]
        + [_producer_row(correct=False, margin=Fraction(1, 2), candidates=5)]
        + [_producer_row(correct=True, margin=Fraction(1, 10)) for _ in range(49)]
    )
    profile = producer.evaluate(rows, threshold)
    assert profile["selected_edges"] == 51
    assert profile["selected_correct_edges"] == 50
    assert profile["selected_precision"] == producer.exact(Fraction(50, 51))
    assert profile["selected_coverage"] == producer.exact(Fraction(51, 100))
    controls = producer.wrong_pointer_controls(rows, threshold)
    assert controls["confident_wrong_unique_top_children"] == 1
    assert controls["all_wrong_alternative_micro_false_acceptance"] != controls[
        "uniform_one_wrong_substitution_per_child_expected_false_acceptance"
    ]
    assert controls["uniform_one_wrong_substitution_per_child_expected_false_acceptance"] != controls[
        "child_level_adversarial_vulnerability"
    ]


def test_strong_and_precision_only_classification_order() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    result_profile = {
        "selected_precision": producer.exact(Fraction(99, 100)),
        "selected_coverage": producer.exact(Fraction(3, 4)),
        "unfiltered_precision": producer.exact(Fraction(9, 10)),
    }
    group = {
        "fraction_at_or_above_reference": producer.exact(Fraction(1, 1)),
        "maximum_accepted_contribution_share": producer.exact(Fraction(1, 10)),
    }
    hard = {"selection": True, "selected_edges_at_least_minimum": True}
    classification, primary = producer.classify(
        result_profile, group, group, hard, protocol
    )
    assert all(primary.values())
    assert classification == (
        "FORWARD_TIME_GENERALIZED_HIGH_PRECISION_SELECTIVE_PARENT_RECOVERY"
    )

    low_coverage = dict(result_profile)
    low_coverage["selected_coverage"] = producer.exact(Fraction(1, 4))
    hard["selected_edges_at_least_minimum"] = False
    classification, primary = producer.classify(
        low_coverage, group, group, hard, protocol
    )
    assert primary["forward_precision"] is True
    assert primary["forward_coverage"] is False
    assert classification == (
        "FORWARD_TIME_GENERALIZED_HIGH_PRECISION_WITHOUT_FULL_PRIMARY_GATE"
    )


def test_producer_and_independent_candidate_margin_recomputation_match() -> None:
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
    cards = {
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
    produced_fingerprints, produced, produced_inventory = producer.edge_records(cards, payloads)
    verified_fingerprints, verified, verified_inventory = verifier.observations(cards, payloads)
    assert produced_fingerprints == verified_fingerprints
    assert produced_inventory == verified_inventory
    assert len(produced) == len(verified) == 1
    assert produced[0].task == verified[0].task
    assert produced[0].run == verified[0].run
    assert produced[0].candidates == verified[0].candidate_count
    assert produced[0].unique_top == verified[0].unique
    assert produced[0].correct == verified[0].right
    assert produced[0].top_score == verified[0].best
    assert produced[0].margin == verified[0].gap


def test_independent_verifier_does_not_import_new_producer() -> None:
    source = (
        PHASE1 / "verify_tree_content_selective_parent_forward_target522.py"
    ).read_text(encoding="utf-8")
    assert "import audit_tree_content_selective_parent_forward_target522" not in source
    assert "from phase1 import audit_tree_content_selective_parent_forward_target522" not in source
    assert "verify_tree_content_lineage_forward_target522" in source
    assert "verify_tree_within_stratum_forward_target522" in source
    assert "producer_imported" in source


def test_output_and_claim_security_contract() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    population = protocol["primary_population"]
    assert population["baseline_rows_in_estimand"] is False
    assert population["identities_or_per_edge_values_emitted"] is False
    boundary = protocol["claim_boundary"]
    assert boundary["recorded_parent_is_external_semantic_or_causal_truth"] is False
    assert boundary["orphan_edges_are_validated_or_repaired"] is False
    assert boundary["predictor_accuracy_effect_or_search_utility_computed"] is False
    assert protocol["security"]["prospective_label_grade_outcome_prediction_values_read"] is False
    assert protocol["resources"]["gpu_jobs"] == 0
    assert protocol["resources"]["api_calls"] == 0
    assert protocol["resources"]["model_fits"] == 0
    assert protocol["resources"]["base_llm_updates"] == 0


def test_runner_and_monitor_bind_four_recomputations_and_wait_blindly() -> None:
    runner = (
        PHASE1
        / "scripts"
        / "run_tree_content_selective_parent_forward_target522_formal_20260829.sh"
    ).read_text(encoding="utf-8")
    monitor = (
        PHASE1
        / "scripts"
        / "monitor_tree_content_selective_parent_forward_target522_formal_20260829.sh"
    ).read_text(encoding="utf-8")
    assert runner.count("producer_a.json") >= 5
    assert runner.count("producer_b.json") >= 2
    assert runner.count("verifier_a.json") >= 4
    assert runner.count("verifier_b.json") >= 2
    assert "PYTHONHASHSEED=0" in runner
    assert "PYTHONHASHSEED=1" in runner
    assert "strace -ff" in runner
    assert "gpu_api_model_fit_base_update=0/0/0/0" in runner
    before_complete = monitor.split('if test -f "$selection/COMPLETE"; then', 1)[0]
    assert "candidate.tsv" not in before_complete
    assert "READY" not in before_complete
    assert "formal_runner.sh" in monitor
    assert "flock -n 9" in monitor
    assert "1006/16929" in monitor
