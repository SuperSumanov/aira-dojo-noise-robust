from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from phase1.task_balance_guard_forward_validation import (
    ForwardValidationError,
    build_forward_validation,
    hhi,
    tv,
)
from phase1.verify_task_balance_guard_forward_validation import (
    ForwardVerificationError,
    verify,
)


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "phase1/results/task_balance_accrual_guard_7cda_20260825/guard.json"
RESULT_DIR = ROOT / "phase1/results/task_balance_guard_forward_8579_20260826"
OBSERVED = RESULT_DIR / "safe_structural_input.json"
RESULT = RESULT_DIR / "forward_validation.json"
INDEPENDENT = RESULT_DIR / "independent_verification.json"
BASE_SHA = "fd87246bb3656befba27de5a98c88f808ca39e178e7322d27ae9536fe4a751b0"
OBSERVED_SHA = "0422e068eba42f6769dd4edbe41b17a5c058804108febd8068518c28098c095e"
RESULT_SHA = "58126971bc846fa14561d3665a824c19b16a6dc2cf96da6e1fea378ff843e799"
INDEPENDENT_SHA = "b9990aabacf93f3b921ca11d523e88eb2036257ba2b1ae86a0e149dc7f7af0fb"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_committed_forward_result_and_independent_receipt_are_exact() -> None:
    assert _sha(BASE) == BASE_SHA
    assert _sha(OBSERVED) == OBSERVED_SHA
    assert _sha(RESULT) == RESULT_SHA
    assert _sha(INDEPENDENT) == INDEPENDENT_SHA

    computed = build_forward_validation(
        _load(BASE), BASE_SHA, _load(OBSERVED), OBSERVED_SHA
    )
    assert computed == _load(RESULT)
    receipt = verify(BASE, BASE_SHA, OBSERVED, OBSERVED_SHA, RESULT, RESULT_SHA)
    assert receipt == _load(INDEPENDENT)
    assert all(receipt["checks"].values())


def test_real_forward_result_preserves_improvement_and_failures() -> None:
    result = _load(RESULT)
    forward = result["frozen_guard_forward_result"]
    assert forward["future_dominant_pairs"] == 27
    assert forward["future_nondominant_pairs"] == 93
    assert forward["baseline_debt"] + 3 * 27 - 93 == 645
    assert forward["predicted_current_debt"] == forward["observed_current_debt"]
    assert forward["debt_delta"] == -12
    assert forward["debt_direction"] == "IMPROVED_BUT_UNCLEARED"
    assert forward["current_cap_pass"] is False
    assert forward["immediate_action_adherence"] == (
        "DEFINITELY_NOT_ADHERED_BEFORE_DEBT_CLEARANCE"
    )
    assert result["descriptive_secondary"]["pair_hhi_delta"] < 0
    assert result["descriptive_secondary"]["run_to_pair_tv_delta"] < 0
    assert result["descriptive_secondary"]["preregistered_for_this_forward_check"] is False


def _synthetic_guard() -> tuple[dict, str]:
    pair_counts = {"task-a": 10, "task-b": 10, "task-c": 10, "task-z": 70}
    guard = {
        "protocol": "prospective_task_balance_accrual_guard_v1",
        "status": "OUTCOME_BLIND_TASK_BALANCE_ACCRUAL_GUARD_READY",
        "snapshot_sha256": "1" * 64,
        "current": {
            "pairs": 100,
            "dominant_task": "task-z",
            "dominant_pairs": 70,
            "maximum_share": 0.25,
        },
        "exact_integer_envelope": {
            "imbalance_debt_numerator": 180,
            "minimum_future_nondominant_pairs_if_zero_future_dominant": 180,
        },
        "single_task_only_headroom": [
            {"task": task, "current_pairs": count}
            for task, count in sorted(pair_counts.items())
        ],
        "access_attestation": {
            "labels_grades_outcomes_or_predictions_read": False,
            "accuracy_effect_or_search_utility_computed": False,
            "gpu_or_api_calls": 0,
            "randomness_used": False,
        },
    }
    raw = json.dumps(guard, sort_keys=True).encode()
    return guard, hashlib.sha256(raw).hexdigest()


def _synthetic_observed(
    guard_sha: str, increments: dict[str, int]
) -> tuple[dict, str]:
    baseline_pairs = {"task-a": 10, "task-b": 10, "task-c": 10, "task-z": 70}
    current_pairs = {
        task: baseline_pairs[task] + increments[task] for task in baseline_pairs
    }
    total = sum(current_pairs.values())
    dominant = "task-z"
    future_dominant = increments[dominant]
    future_nondominant = sum(increments.values()) - future_dominant
    debt = max(0, 4 * current_pairs[dominant] - total)
    violations = sorted(task for task, count in current_pairs.items() if 4 * count > total)
    baseline_runs = {"task-a": 1, "task-b": 1, "task-c": 1, "task-z": 7}
    current_runs = {"task-a": 2, "task-b": 2, "task-c": 1, "task-z": 7}
    observed = {
        "protocol": "task_balance_guard_forward_structural_input_v1",
        "status": "OUTCOME_BLIND_FORWARD_INPUT_EXTRACTED",
        "baseline_snapshot_sha256": "1" * 64,
        "current_snapshot_sha256": "2" * 64,
        "source_sha256": {"baseline_guard": guard_sha},
        "chronology": {
            "baseline_runs": 10,
            "current_runs": 12,
            "new_runs": 2,
            "baseline_run_id_set_subset_of_current": True,
            "baseline_run_id_sequence_is_subsequence": True,
            "common_rows_equal_when_joined_by_run_id": True,
            "baseline_is_byte_prefix_of_current": False,
            "new_runs_before_old_baseline_tail": 1,
        },
        "pair_inventory": {
            "baseline_pairs": 100,
            "current_pairs": total,
            "new_pairs": sum(increments.values()),
            "tasks": 4,
            "dominant_task": dominant,
            "baseline_dominant_pairs": 70,
            "current_dominant_pairs": current_pairs[dominant],
            "future_dominant_pairs": future_dominant,
            "future_nondominant_pairs": future_nondominant,
            "baseline_debt": 180,
            "predicted_current_debt": max(
                0, 180 + 3 * future_dominant - future_nondominant
            ),
            "observed_current_debt": debt,
            "current_dominant_share": current_pairs[dominant] / total,
            "current_cap_pass": not violations,
            "current_cap_violating_tasks": violations,
            "strict_zero_dominant_immediate_action_adhered": future_dominant == 0,
            "pair_increments_by_task": dict(sorted(increments.items())),
        },
        "run_inventory": {
            "baseline_runs_by_task": baseline_runs,
            "current_runs_by_task": current_runs,
        },
        "descriptive_secondary": {
            "baseline_run_hhi": hhi(baseline_runs),
            "current_run_hhi": hhi(current_runs),
            "baseline_pair_hhi": hhi(baseline_pairs),
            "current_pair_hhi": hhi(current_pairs),
            "baseline_run_to_pair_tv": tv(baseline_runs, baseline_pairs),
            "current_run_to_pair_tv": tv(current_runs, current_pairs),
        },
        "access_attestation": {
            "labels_grades_outcomes_or_winner_orientation_read": False,
            "prediction_values_read_or_aggregated": False,
            "raw_archive_payload_read": False,
            "gpu_jobs": 0,
            "api_calls": 0,
            "model_fits": 0,
            "base_llm_updates": 0,
        },
    }
    raw = json.dumps(observed, sort_keys=True).encode()
    return observed, hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize(
    ("increments", "direction", "adherence"),
    [
        (
            {"task-a": 60, "task-b": 60, "task-c": 60, "task-z": 0},
            "CLEARED",
            "ADHERED_NO_DOMINANT_INCREMENT",
        ),
        (
            {"task-a": 0, "task-b": 0, "task-c": 0, "task-z": 10},
            "WORSENED",
            "DEFINITELY_NOT_ADHERED_BEFORE_DEBT_CLEARANCE",
        ),
        (
            {"task-a": 61, "task-b": 60, "task-c": 60, "task-z": 1},
            "IMPROVED_BUT_UNCLEARED",
            "ORDER_UNOBSERVED_CANNOT_DETERMINE",
        ),
    ],
)
def test_synthetic_debt_and_adherence_boundaries(
    increments: dict[str, int], direction: str, adherence: str
) -> None:
    guard, guard_sha = _synthetic_guard()
    observed, observed_sha = _synthetic_observed(guard_sha, increments)
    result = build_forward_validation(guard, guard_sha, observed, observed_sha)
    forward = result["frozen_guard_forward_result"]
    assert forward["debt_direction"] == direction
    assert forward["immediate_action_adherence"] == adherence


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["chronology"].update(
            {"baseline_run_id_set_subset_of_current": False}
        ),
        lambda value: value["pair_inventory"]["pair_increments_by_task"].update(
            {"task-a": -1}
        ),
        lambda value: value["access_attestation"].update(
            {"prediction_values_read_or_aggregated": True}
        ),
        lambda value: value["run_inventory"]["current_runs_by_task"].update(
            {"AI4Code": 0}
        ),
    ],
)
def test_producer_fails_closed_on_structural_or_access_mutation(mutation) -> None:
    guard = _load(BASE)
    observed = _load(OBSERVED)
    mutation(observed)
    with pytest.raises(ForwardValidationError):
        build_forward_validation(guard, BASE_SHA, observed, OBSERVED_SHA)


def test_independent_verifier_rejects_mutated_forward_result(tmp_path: Path) -> None:
    result = _load(RESULT)
    result["frozen_guard_forward_result"]["debt_delta"] = -13
    path = tmp_path / "mutated.json"
    path.write_text(json.dumps(result) + "\n", encoding="utf-8")
    with pytest.raises(ForwardVerificationError, match="frozen guard result"):
        verify(BASE, BASE_SHA, OBSERVED, OBSERVED_SHA, path, _sha(path))


def test_result_manifest_and_rejected_first_attempt_are_preserved() -> None:
    rows = {}
    for line in (RESULT_DIR / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest_value, relative = line.split("  ./", maxsplit=1)
        rows[relative] = digest_value
    assert set(rows) == {
        "README.md",
        "failed_attempt_v1.json",
        "forward_validation.json",
        "independent_verification.json",
        "preflight_13.txt",
        "safe_structural_input.json",
    }
    for relative, digest_value in rows.items():
        assert _sha(RESULT_DIR / relative) == digest_value

    failure = _load(RESULT_DIR / "failed_attempt_v1.json")
    assert failure["status"] == "REJECTED_OVERSTRONG_BYTE_PREFIX_INVARIANT"
    assert failure["diagnosis"]["raw_byte_prefix"] is False
    assert failure["diagnosis"]["old_run_id_set_subset_of_current"] is True
    assert failure["diagnosis"]["old_run_id_sequence_is_subsequence"] is True
    assert failure["diagnosis"]["old_rows_equal_when_joined_by_run_id"] is True
