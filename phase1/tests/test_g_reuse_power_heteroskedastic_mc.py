import json

import numpy as np
import pytest

from phase1.g_reuse_power_heteroskedastic_mc import SimulationError, simulate, wilson
from phase1.verify_g_reuse_power_heteroskedastic_mc import VerificationError, verify


def test_simulation_is_deterministic():
    counts = np.asarray([30, 80, 150, 300], dtype=float)
    args = (counts, 0.04, 0.2, 0.01, 0.5, 3, 3.182446, 2000, 200, 17)
    assert simulate(*args) == simulate(*args)


def test_more_effect_has_more_power_for_fixed_draws():
    counts = np.asarray([100] * 12, dtype=float)
    low = simulate(counts, 0.01, 0.2, 0.01, 0.5, 3, 2.200985, 10000, 1000, 23)
    high = simulate(counts, 0.04, 0.2, 0.01, 0.5, 3, 2.200985, 10000, 1000, 23)
    assert high["power"] > low["power"]


def test_wilson_contains_observed_rate():
    low, high = wilson(300, 1000)
    assert low < 0.3 < high


def test_invalid_scenario_rejected():
    with pytest.raises(SimulationError):
        simulate(np.asarray([10, 20], dtype=float), 0.2, 0.1, 0, 0, 3, 1.96, 10, 10, 1)


def test_verifier_accepts_independently_recomputed_receipt(tmp_path):
    input_path = tmp_path / "input.json"
    protocol_path = tmp_path / "protocol.json"
    result_path = tmp_path / "result.json"
    input_path.write_text("{}\n", encoding="utf-8")
    import hashlib
    input_sha = hashlib.sha256(input_path.read_bytes()).hexdigest()
    protocol = {
        "input": {"sha256": input_sha},
        "classification": "TEST",
        "fixed": {"simulation_seeds": [1, 2], "trials_per_replication": 1000},
        "gates": {"maximum_replication_absolute_difference": 0.01,
                  "maximum_mean_mc_vs_analytic_absolute_difference": 0.01,
                  "maximum_wilson_95_half_width": 0.05},
        "scenarios": {"reference": {"analytic_power": 0.3}},
    }
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    protocol_sha = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    rows = []
    for successes in (300, 304):
        low, high = wilson(successes, 1000)
        rows.append({"power": successes / 1000, "successes": successes, "trials": 1000,
                     "wilson_95": [low, high], "wilson_95_half_width": (high - low) / 2})
    result = {
        "all_gates_pass": True, "classification": "TEST", "input_sha256": input_sha,
        "protocol_sha256": protocol_sha,
        "resources": {"gpu_jobs": 0, "model_fits": 0, "paid_api_calls": 0,
                      "protected_values_read": 0},
        "scenarios": {"reference": {"analytic_power": 0.3, "mean_mc_power": 0.302,
                                      "replications": rows,
                                      "gates": {"replication_difference": True,
                                                "analytic_difference": True,
                                                "mc_half_width": True}}},
    }
    result_path.write_text(json.dumps(result), encoding="utf-8")
    assert verify(protocol_path, input_path, result_path)["verification_pass"] is True


def test_verifier_rejects_tampered_power(tmp_path):
    input_path = tmp_path / "input.json"
    protocol_path = tmp_path / "protocol.json"
    result_path = tmp_path / "result.json"
    input_path.write_text("{}", encoding="utf-8")
    import hashlib
    input_sha = hashlib.sha256(input_path.read_bytes()).hexdigest()
    protocol = {"input": {"sha256": input_sha}, "classification": "TEST",
                "fixed": {"simulation_seeds": [1, 2], "trials_per_replication": 10},
                "gates": {"maximum_replication_absolute_difference": 1,
                          "maximum_mean_mc_vs_analytic_absolute_difference": 1,
                          "maximum_wilson_95_half_width": 1},
                "scenarios": {"s": {"analytic_power": 0.5}}}
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    protocol_sha = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    low, high = wilson(5, 10)
    row = {"power": 0.6, "successes": 5, "trials": 10, "wilson_95": [low, high],
           "wilson_95_half_width": (high - low) / 2}
    result = {"all_gates_pass": True, "classification": "TEST", "input_sha256": input_sha,
              "protocol_sha256": protocol_sha,
              "resources": {"gpu_jobs": 0, "model_fits": 0, "paid_api_calls": 0,
                            "protected_values_read": 0},
              "scenarios": {"s": {"analytic_power": 0.5, "mean_mc_power": 0.5,
                                    "replications": [row, row],
                                    "gates": {"replication_difference": True,
                                              "analytic_difference": True,
                                              "mc_half_width": True}}}}
    result_path.write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(VerificationError):
        verify(protocol_path, input_path, result_path)
