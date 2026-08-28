from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parents[2]
PHASE1 = ROOT / "phase1"
SNAPSHOT_887 = (
    "887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_historical_identifier_erased_887_protocol_and_runner_are_bound() -> None:
    protocol_path = (
        PHASE1 / "historical_train_future_identifier_erased_887_protocol_v1.json"
    )
    protocol = _json(protocol_path)
    assert _sha(protocol_path) == (
        "aa3b232c732c53bb24bf2fbac6932276d458f2e6a6ae20321edee0ff2d04ca1b"
    )
    assert protocol["status"] == "RESULT_BLIND_PROTOCOL_FROZEN"
    assert protocol["fixed_future_population"] == {
        "snapshot_sha256": SNAPSHOT_887,
        "intake_registry_sha256": (
            "37e41460c85661fd9afc6f8789a065088a9da88dde027b955ff4bc366d5bbcd8"
        ),
        "provisional_first960_runs_sha256": (
            "510d81820d7825fc6baa6db562b2371e50eb7d71d04cb1cc0bd17d095d6cdbca"
        ),
        "accumulator_summary_sha256": (
            "2f28b5b53cca5d6ea5ebf16f746a70f9c1de0e3197487a6ed78d41b4cb611302"
        ),
        "runs": 435,
        "endpoints": 11906,
        "structural_pairs": 3053,
        "tasks": 34,
        "closure": False,
    }
    assert [row["status"] for row in protocol["ordered_classification"]] == [
        "ZERO_IDENTIFIER_ERASED_LINKS",
        "LOW_IDENTIFIER_ERASED_OVERLAP_ONLY",
        "INTEGRITY_GATE_FAIL",
    ]
    assert protocol["prior_result_disclosure"]["new_435_run_result_was_read_before_freeze"] is False
    assert protocol["thresholds"]["strict_sensitivity_can_rescue_primary"] is False
    assert list(protocol["resources"].values()) == [0, 0, 0, 0]

    runner = (
        PHASE1
        / "scripts"
        / "run_historical_train_future_identifier_erased_887_20260828.sh"
    ).read_text(encoding="utf-8")
    assert f"readonly snapshot_sha={SNAPSHOT_887}" in runner
    assert (
        "readonly protocol_sha="
        "aa3b232c732c53bb24bf2fbac6932276d458f2e6a6ae20321edee0ff2d04ca1b"
    ) in runner
    assert "ZERO_IDENTIFIER_ERASED_LINKS" in runner
    assert "LOW_IDENTIFIER_ERASED_OVERLAP_ONLY" in runner
    assert "INTEGRITY_GATE_FAIL" in runner
    assert "gpu_api_model_fit_base_update=0/0/0/0" in runner


def test_task_balance_v3_is_future_only_and_cannot_rescue_887() -> None:
    protocol = _json(PHASE1 / "task_balance_forward_v3_future_protocol_v1.json")
    assert protocol["status"] == (
        "IMPLEMENTATION_FROZEN_FIRST_UNSEEN_SUCCESSOR_PENDING"
    )
    assert protocol["freeze_state"]["latest_snapshot_when_protocol_was_written"] == SNAPSHOT_887
    assert protocol["activation_rule"]["forbidden_current_snapshots"] == [
        SNAPSHOT_887
    ]
    assert protocol["activation_rule"]["manual_snapshot_choice_allowed"] is False
    assert protocol["activation_rule"]["skip_an_earlier_eligible_successor_allowed"] is False
    contract = protocol["v3_task_universe_contract"]
    assert contract["baseline_pair_task_set_must_be_subset_of_current"] is True
    assert contract["new_tasks_receive_explicit_baseline_pair_and_run_count_zero"] is True
    assert contract["removed_tasks_allowed"] is False
    assert contract["negative_pair_or_run_accrual_allowed"] is False
    assert contract["dominant_task_change_allowed"] is False
    assert contract["same_887_snapshot_v2_kill_can_be_rescued"] is False
    assert [row["status"] for row in protocol["primary_interpretation"]] == [
        "CAP_PASS",
        "CAP_FAIL",
    ]
    assert protocol["secondary_cannot_rescue_primary"] is True
    assert list(protocol["resources"].values()) == [0, 0, 0, 0]


def test_task_balance_887_failure_package_is_byte_bound() -> None:
    result = PHASE1 / "results" / "task_balance_structural_extension_887_20260828_1e5f949"
    bindings = _json(result / "source_bindings.json")
    assert _sha(result / "verification.json") == bindings["verification_json_sha256"]
    assert _sha(result / "access_attestation.txt") == bindings["access_attestation_sha256"]
    verification = _json(result / "verification.json")
    assert verification["status"] == "TASK_UNIVERSE_CHANGE_KILL_INDEPENDENTLY_VERIFIED"
    assert verification["claim"] == {
        "cap_or_directional_balance_adjudicated": False,
        "post_hoc_task_padding_used": False,
        "rerun_on_same_snapshot_authorized": False,
    }
    assert verification["task_universe"]["baseline_tasks"] == 30
    assert verification["task_universe"]["current_tasks"] == 34
    assert verification["task_universe"]["added_tasks"] == 4
    assert verification["task_universe"]["removed_tasks"] == 0
