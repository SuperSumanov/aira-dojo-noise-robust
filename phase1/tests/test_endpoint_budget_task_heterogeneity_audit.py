import ast
import json
from pathlib import Path

import pytest

from phase1 import audit_endpoint_budget_task_heterogeneity as producer
from phase1 import verify_endpoint_budget_task_heterogeneity as verifier


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "phase1" / "endpoint_budget_task_heterogeneity_audit_v1.json"


def test_frozen_protocol_discloses_known_aggregate_and_unknown_task_readout() -> None:
    value = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert value["status"] == "FROZEN_AFTER_SMOKE_AGGREGATE_READOUT_BEFORE_TASK_LEVEL_READOUT"
    assert value["known_before_freeze"]["terminal_drop_dominant_task_accuracy_delta"] < 0
    assert value["known_before_freeze"]["overall_accuracy_delta_yield_minus_uniform"]["192"] > 0
    unknown = [key for key in value["known_before_freeze"] if key.endswith("_seen")]
    assert len(unknown) == 6
    assert all(value["known_before_freeze"][key] is False for key in unknown)
    assert value["interpretation"]["no_promotion_gate"] is True
    assert value["scope"]["may_rescue_failed_smoke"] is False
    assert value["resources"]["critic_model_fits"] == 0


@pytest.mark.parametrize("module", [producer, verifier])
def test_average_ranks_and_spearman_ties_are_deterministic(module) -> None:
    rank_function = getattr(module, "average_ranks", getattr(module, "ranks", None))
    correlation = getattr(module, "spearman", getattr(module, "rho", None))
    assert rank_function([3, 1, 1, 2]) == [4.0, 1.5, 1.5, 3.0]
    assert correlation([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)
    assert correlation([1, 1, 1], [1, 2, 3]) is None


@pytest.mark.parametrize("module", [producer, verifier])
def test_sign_counts_retain_zero(module) -> None:
    function = getattr(module, "sign_counts", getattr(module, "signs", None))
    assert function([-2, 0, 0.0, 3]) == {"negative": 1, "zero": 2, "positive": 1}


def test_independent_verifier_does_not_import_or_execute_producer() -> None:
    path = ROOT / "phase1" / "verify_endpoint_budget_task_heterogeneity.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "phase1.audit_endpoint_budget_task_heterogeneity" not in imported
    assert "subprocess" not in imported
    assert "audit_endpoint_budget_task_heterogeneity" not in source


def test_public_contract_forbids_identity_hashes_and_confirmation() -> None:
    assert producer.CLASSIFICATION == verifier.CLASSIFICATION
    assert producer.PUBLIC_PROTOCOL == verifier.PUBLIC_PROTOCOL
    assert producer.PRIVATE_PROTOCOL == verifier.PRIVATE_PROTOCOL
    value = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert "no raw or hashed task/run/pair identity" in value["outputs"]["public"]
    assert value["scope"]["scientific_confirmation"] is False
    assert value["scope"]["prospective_first960_target300_target522_values_forbidden"] is True
