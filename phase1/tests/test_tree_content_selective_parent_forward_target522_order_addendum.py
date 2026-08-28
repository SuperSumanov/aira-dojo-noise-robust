from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path

from phase1 import audit_tree_content_selective_parent_forward_target522_order_addendum as producer
from phase1 import verify_tree_content_selective_parent_forward_target522_order_addendum as verifier


ROOT = Path(__file__).resolve().parents[2]
PHASE1 = ROOT / "phase1"
PROTOCOL = PHASE1 / "tree_content_selective_parent_forward_target522_order_addendum_v1.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protocol() -> dict:
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))


def test_protocol_is_frozen_before_every_target522_readout() -> None:
    value = protocol()
    assert digest(PROTOCOL) == producer.PROTOCOL_SHA256 == verifier.PROTOCOL_SHA256
    assert value["status"] == (
        "OUTCOME_BLIND_FROZEN_AFTER_DEVELOPMENT_ORDER_READOUT_BEFORE_TARGET522_CANDIDATE"
    )
    freeze = value["freeze_state"]
    unseen = (
        "target522_selection_complete_present",
        "target522_candidate_seen",
        "target522_increment_profile_seen",
        "target522_content_result_seen",
        "target522_max_prior_step_values_seen",
        "target522_paired_disagreement_seen",
        "target522_task_or_run_disagreement_breadth_seen",
    )
    assert all(freeze[name] is False for name in unseen)
    assert freeze["latest_snapshot_when_frozen"] == freeze["baseline_snapshot_sha256"]
    assert value["upstream_target522_contract"][
        "upstream_result_may_be_rescued_by_this_addendum"
    ] is False


def test_all_preexisting_dependencies_are_hash_bound() -> None:
    value = protocol()
    upstream = value["upstream_target522_contract"]
    for role in (
        "selection_protocol",
        "selection_monitor",
        "selective_protocol",
        "selective_producer",
        "selective_verifier",
    ):
        assert digest(ROOT / upstream[role]) == upstream[f"{role}_sha256"]
    for binding in value["immutable_helpers"].values():
        assert digest(ROOT / binding["path"]) == binding["sha256"]
    development = value["known_development_evidence"]
    root = ROOT / development["package_root"]
    assert digest(root / development["package_manifest"]) == development[
        "package_manifest_sha256"
    ]
    assert digest(root / development["formal_result"]) == development[
        "formal_result_sha256"
    ]
    assert digest(root / development["independent_verification"]) == development[
        "independent_verification_sha256"
    ]


def test_producer_and_verifier_independently_validate_frozen_protocol() -> None:
    produced_protocol, produced_development = producer.load_protocol(
        PROTOCOL, producer.PROTOCOL_SHA256, ROOT
    )
    checked_protocol, checked_development = verifier.load_protocol(
        PROTOCOL, verifier.PROTOCOL_SHA256, ROOT
    )
    assert produced_protocol == checked_protocol == protocol()
    assert produced_development == checked_development
    assert produced_development["valid_control"] == "max_prior_step"
    assert produced_development["formal_classification"] == (
        "DEVELOPMENT_ORDER_BASELINE_FALSIFICATION_INTEGRITY_FAIL"
    )


def _long_code(kind: str) -> str:
    if kind == "parent":
        return "\n".join(
            ["values = list(range(30))", "total = sum(values)"]
            + [f"total = total + {index}" for index in range(30)]
            + ["print(total)"]
        )
    return "\n".join(
        ["mapping = {str(i): i for i in range(30)}", "product = 1"]
        + [f"product = product * ({index} + 1)" for index in range(1, 30)]
        + ["print(mapping.get(str(product), 0))"]
    )


def test_independent_candidate_content_and_step_reconstructions_match() -> None:
    parent_code = _long_code("parent")
    alternative_code = _long_code("alternative")
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
    objects = {
        "parent": {"code": parent_code, "lineage": {"step": 0}},
        "alternative": {"code": alternative_code, "lineage": {"step": 1}},
        "child": {"code": parent_code + "\nprint(total / 2)\n", "lineage": {"step": 2}},
    }
    produced, produced_inventory = producer.build_rows(cards, objects)
    checked, checked_inventory = verifier.observations(cards, objects)
    assert produced_inventory == checked_inventory
    assert len(produced) == len(checked) == 1
    assert produced[0].task == checked[0].task == "task"
    assert produced[0].run == checked[0].run == "run"
    assert produced[0].parent == checked[0].parent == "parent"
    assert produced[0].content_prediction == checked[0].content == "parent"
    assert produced[0].content_margin == checked[0].margin
    assert produced[0].step_prediction == checked[0].step == "alternative"
    assert produced_inventory["recorded_parent_not_prior_step"] == 0


def _producer_row(content: bool, step: bool, *, task: str = "task", run: str = "run") -> producer.PairedRow:
    return producer.PairedRow(
        task=task,
        run=run,
        parent="parent",
        candidates=3,
        content_prediction="parent" if content else "wrong-content",
        content_margin=Fraction(1, 2),
        step_prediction="parent" if step else "wrong-step",
    )


def _verifier_row(content: bool, step: bool, *, task: str = "task", run: str = "run") -> verifier.IndependentRow:
    return verifier.IndependentRow(
        task=task,
        run=run,
        parent="parent",
        candidates=3,
        content="parent" if content else "wrong-content",
        margin=Fraction(1, 2),
        step="parent" if step else "wrong-step",
    )


def test_paired_table_is_exact_and_independently_reproduced() -> None:
    pattern = [(True, True)] * 5 + [(True, False)] * 6 + [(False, True)] * 2 + [(False, False)] * 3
    produced, _ = producer.paired_profile([_producer_row(*values) for values in pattern])
    checked, _ = verifier.paired_profile([_verifier_row(*values) for values in pattern])
    assert produced == checked
    assert produced["paired_correctness"] == {
        "both_correct": 5,
        "both_wrong": 3,
        "content_only_correct": 6,
        "step_only_correct": 2,
    }
    assert produced["content_errors"] == 5
    assert produced["step_errors"] == 9
    assert produced["content_to_step_error_ratio"] == producer.exact(Fraction(5, 9))


def _gate_inputs() -> tuple[dict, dict, dict, dict]:
    integrity = {"all_structural_bindings_exact": True}
    paired = {
        "comparable_rows": 500,
        "comparable_coverage": producer.exact(Fraction(1, 1)),
        "content_errors": 10,
        "step_errors": 100,
        "paired_correctness": {
            "both_correct": 390,
            "both_wrong": 10,
            "content_only_correct": 100,
            "step_only_correct": 0,
        },
    }
    task = {
        "conditionable_groups": 8,
        "fraction_net_content_positive": producer.exact(Fraction(1, 1)),
        "maximum_discordance_contribution_share": producer.exact(Fraction(1, 5)),
    }
    run = {
        "conditionable_groups": 30,
        "fraction_net_content_positive": producer.exact(Fraction(1, 1)),
        "maximum_discordance_contribution_share": producer.exact(Fraction(1, 10)),
    }
    return integrity, paired, task, run


def test_classification_precedence_forbids_rescue_and_posthoc_repair() -> None:
    value = protocol()
    required = value["upstream_target522_contract"][
        "required_upstream_classification_for_positive_addendum"
    ]
    integrity, paired, task, run = _gate_inputs()
    produced = producer.decisions(value, required, integrity, 500, paired, task, run)
    checked = verifier.classify(value, required, integrity, 500, paired, task, run)
    assert produced == checked
    assert produced[0] == "FORWARD_CONTENT_ADDS_BROADLY_BEYOND_MAX_PRIOR_STEP"

    assert producer.decisions(
        value,
        "FORWARD_SELECTIVE_PARENT_RECOVERY_BELOW_GATE",
        integrity,
        500,
        paired,
        task,
        run,
    )[0] == "FORWARD_SELECTIVE_PARENT_PRIMARY_NOT_CONFIRMED"

    insufficient = dict(paired)
    insufficient["comparable_rows"] = 399
    insufficient["comparable_coverage"] = producer.exact(Fraction(399, 500))
    assert producer.decisions(
        value, required, integrity, 500, insufficient, task, run
    )[0] == "FORWARD_ORDER_BASELINE_SUPPORT_INSUFFICIENT"

    assert producer.decisions(
        value, required, {"all_structural_bindings_exact": False}, 500, paired, task, run
    )[0] == "FORWARD_ORDER_BASELINE_ADDENDUM_INTEGRITY_FAIL"


def test_verifier_does_not_import_addendum_producer() -> None:
    source = (
        PHASE1 / "verify_tree_content_selective_parent_forward_target522_order_addendum.py"
    ).read_text(encoding="utf-8")
    module = "audit_tree_content_selective_parent_forward_target522_order_addendum"
    assert f"import {module}" not in source
    assert f"from phase1 import {module}" not in source
    assert "verify_tree_content_selective_parent_forward_target522" in source
    assert "verify_tree_within_stratum_forward_target522" in source


def test_runner_has_fixed_roots_repetitions_and_no_monitor_activation() -> None:
    runner = (
        PHASE1
        / "scripts"
        / "run_tree_content_selective_parent_forward_target522_order_addendum_formal_20260829.sh"
    ).read_text(encoding="utf-8")
    assert "latch-42f1044-after-887-v2" in runner
    assert "formal-349b9ca-target522-v1" in runner
    assert "readonly output=" in runner
    assert "OUTPUT_ROOT" not in runner
    assert runner.count("producer_a.json") >= 5
    assert runner.count("producer_b.json") >= 2
    assert runner.count("verifier_a.json") >= 4
    assert runner.count("verifier_b.json") >= 2
    assert "PYTHONHASHSEED=0" in runner
    assert "PYTHONHASHSEED=1" in runner
    assert "strace -ff" in runner
    assert "gpu_api_model_fit_base_update=0/0/0/0" in runner


def test_security_and_claim_boundaries_are_explicit() -> None:
    value = protocol()
    assert value["primary_population"]["identities_or_per_edge_values_emitted"] is False
    assert value["primary_population"]["baseline_abstentions_count_as_errors"] is False
    assert value["claim_boundary"]["development_and_forward_rows_may_be_pooled"] is False
    assert value["claim_boundary"]["recorded_parent_is_external_semantic_or_causal_truth"] is False
    assert value["claim_boundary"]["upstream_target522_failure_rescued"] is False
    assert value["security"]["prospective_first960_or_target300_values_read"] is False
    assert value["security"]["raw_senior_archives_opened"] is False
    assert value["security"]["gpu_api_model_fit_base_update"] == [0, 0, 0, 0]
