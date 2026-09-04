from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from phase1.validate_g_reuse_effect_protocol import (
    ProtocolError,
    load_protocol,
    validate_protocol,
)
from phase1.verify_g_reuse_effect_protocol import independently_verify


REPO = Path(__file__).resolve().parents[2]
PROTOCOL = REPO / "phase1" / "g_reuse_effect_protocol_v1.json"


def load() -> dict:
    value, _ = load_protocol(PROTOCOL)
    return value


def test_canonical_protocol_is_frozen_and_effect_blocked() -> None:
    receipt = validate_protocol(load())
    assert receipt["status"] == "FROZEN_AWAITING_SOURCE_G0_AND_GPU_APPROVAL"
    assert receipt["ready_for_fit"] is False
    assert receipt["core_planned_fits"] == 15
    assert receipt["conditional_cost_planned_fits"] == 3
    assert receipt["gpu_paid_api_model_fit_base_update"] == [0, 0, 0, 0]


def test_independent_verifier_agrees_on_hash_counts_and_blocked_state() -> None:
    value, raw = load_protocol(PROTOCOL)
    primary = validate_protocol(value)
    independent = independently_verify(PROTOCOL)
    expected_hash = hashlib.sha256(raw).hexdigest()
    assert independent["protocol_sha256"] == expected_hash
    assert primary["core_planned_fits"] == independent["core_planned_fits"] == 15
    assert primary["conditional_cost_planned_fits"] == independent["conditional_cost_planned_fits"] == 3
    assert primary["ready_for_fit"] is independent["ready_for_fit"] is False


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("authorization", "gpu_jobs"), 1),
        (("pending_contract", "same_producer_cards_global_local_split_source_received"), True),
        (("pending_contract", "exact_gpu_hours"), 1.0),
        (("core_stage", "seeds"), [6, 7]),
        (("core_stage", "planned_fits"), 14),
        (("core_gates", "full_minus_lbudget_point_minimum"), 0.01),
        (("hash_control", "true_global_orientation_read"), True),
        (("hash_control", "global_rows_order_tokens_updates_match_full"), False),
        (("conditional_cost_stage", "try_other_budget_points_after_failure"), True),
        (("conditional_cost_stage", "spectral_minus_full_task_ci_lower_strictly_greater_than"), -0.02),
    ],
)
def test_mutations_fail_closed(path: tuple[str, str], value: object) -> None:
    mutated = copy.deepcopy(load())
    mutated[path[0]][path[1]] = value
    with pytest.raises(ProtocolError):
        validate_protocol(mutated)


def test_arm_mutation_fails_closed() -> None:
    mutated = copy.deepcopy(load())
    mutated["core_stage"]["arms"][3]["id"] = "post-result-rescue"
    with pytest.raises(ProtocolError):
        validate_protocol(mutated)


def test_unknown_root_or_arm_field_fails_closed() -> None:
    mutated = copy.deepcopy(load())
    mutated["post_result_override"] = True
    with pytest.raises(ProtocolError, match="root schema drift"):
        validate_protocol(mutated)

    mutated = copy.deepcopy(load())
    mutated["core_stage"]["arms"][0]["hidden_shortcut"] = True
    with pytest.raises(ProtocolError, match="arm schema drift"):
        validate_protocol(mutated)


def test_duplicate_json_key_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "duplicate.json"
    target.write_text('{"protocol":"g-reuse-effect-v1","protocol":"changed"}\n', encoding="utf-8")
    with pytest.raises(ProtocolError, match="duplicate JSON key"):
        load_protocol(target)


def test_json_round_trip_does_not_change_protocol_semantics(tmp_path: Path) -> None:
    value = load()
    target = tmp_path / "roundtrip.json"
    target.write_text(json.dumps(value, ensure_ascii=True), encoding="utf-8")
    reloaded, _ = load_protocol(target)
    assert validate_protocol(reloaded)["ready_for_fit"] is False
