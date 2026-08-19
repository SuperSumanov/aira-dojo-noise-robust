import csv
import hashlib
import json
import random
from pathlib import Path

import numpy as np
import pytest

from phase1 import compare_deployment_cost_runs as comparator
from phase1 import deployment_cost_attestation as producer
from phase1 import verify_deployment_cost_attestation as verifier


class LinearEstimator:
    def decision_function(self, matrix):
        return np.asarray(matrix)[:, 0]


def test_quantile_contract_matches_independent_verifier():
    values = [4.0, 1.0, 3.0, 2.0]
    for probability in (0.0, 0.25, 0.5, 0.75, 0.95, 1.0):
        assert producer.quantile(values, probability) == verifier.quantile(values, probability)


def test_query_pairs_are_canonical_and_duplicates_fail(tmp_path: Path):
    path = tmp_path / "pairs.jsonl"
    path.write_text(
        json.dumps({"better": "z", "worse": "a", "budget": 0, "intask_split": "test"})
        + "\n",
        encoding="utf-8",
    )
    assert producer.load_pairs(path, "test", canonical=True) == [("a", "z")]
    path.write_text(
        "\n".join(
            [
                json.dumps({"better": "z", "worse": "a", "budget": 0, "intask_split": "test"}),
                json.dumps({"better": "a", "worse": "z", "budget": 0, "intask_split": "test"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(producer.IntegrityError, match="duplicate/reversed"):
        producer.load_pairs(path, "test", canonical=True)


def test_explicit_antisymmetrization_is_exact():
    cards = {
        "a": producer.Card("x", {"depth": 0}, 10.0),
        "b": producer.Card("xxxx", {"depth": 0}, 20.0),
    }
    fitted = producer.FittedPredictor("static_lr", LinearEstimator())
    forward = producer.query_scores(fitted, cards, [("a", "b")])
    reverse = producer.query_scores(fitted, cards, [("b", "a")])
    assert forward[0] == -reverse[0]


def test_all_three_predictors_fit_and_query_with_finite_antisymmetric_scores():
    cards = {}
    train_pairs = []
    for index in range(12):
        identifier = f"train-{index}"
        cards[identifier] = producer.Card(
            f"import pandas as pd\nseed = {index}\nprint('shared token {index % 3}')\n",
            {"depth": index % 3, "step": index, "n_siblings": 2},
            10.0 + index,
        )
    for index in range(0, 12, 2):
        train_pairs.append((f"train-{index}", f"train-{index + 1}"))
    query_pairs = [("query-a", "query-b"), ("query-c", "query-d")]
    for index, identifier in enumerate(("query-a", "query-b", "query-c", "query-d")):
        cards[identifier] = producer.Card(
            f"import pandas as pd\nseed = {20 + index}\nprint('shared token {index % 2}')\n",
            {"depth": 1, "step": index, "n_siblings": 2},
            20.0 + index,
        )
    for model in producer.MODELS:
        fitted, fit_warnings = producer.fit_predictor(model, cards, train_pairs, seed=7)
        assert not fit_warnings
        forward = producer.query_scores(fitted, cards, query_pairs)
        reverse = producer.query_scores(
            fitted, cards, [(right, left) for left, right in query_pairs]
        )
        assert np.all(np.isfinite(forward))
        assert np.allclose(reverse, -forward, rtol=0, atol=1e-12)


def test_execution_reference_reports_three_cost_semantics():
    cards = {
        "a": producer.Card("", {}, 10.0),
        "b": producer.Card("", {}, 20.0),
        "c": producer.Card("", {}, 30.0),
    }
    rows, summary = producer.execution_reference(cards, [("a", "b"), ("a", "c")])
    assert [row["serial_runtime_s"] for row in rows] == [30.0, 40.0]
    assert [row["ideal_parallel_runtime_s"] for row in rows] == [20.0, 30.0]
    assert summary["pair_coverage"] == 1.0
    assert summary["unique_endpoints"] == 3


def test_summary_positive_gate_and_independent_reconstruction_match():
    config = {
        "init_trials": 2,
        "single_query_warmup": 1,
        "single_pair_sample": 2,
    }
    measurements = []
    receipts = []
    for model in producer.MODELS:
        digest = hashlib.sha256(bytes([2, 2])).hexdigest()
        for trial in range(2):
            measurements.append(
                {
                    "model": model,
                    "trial": str(trial),
                    "phase": "init",
                    "repeat": "0",
                    "item_index": "",
                    "n_items": "4",
                    "elapsed_s": str(1.0 + trial * 0.1),
                    "per_pair_ms": "",
                    "decision": "",
                    "decision_sha256": "",
                }
            )
            for item in range(2):
                measurements.append(
                    {
                        "model": model,
                        "trial": str(trial),
                        "phase": "single_query",
                        "repeat": "0",
                        "item_index": str(item),
                        "n_items": "1",
                        "elapsed_s": "0.001",
                        "per_pair_ms": "1.0",
                        "decision": "1",
                        "decision_sha256": "single",
                    }
                )
            receipts.append(
                {
                    "model": model,
                    "trial": trial,
                    "fit_warnings": [],
                    "sample_decision_sha256": digest,
                    "tie_count": 0,
                    "antisymmetry_fraction": 1.0,
                }
            )
    runtime = {
        "pair_coverage": 1.0,
        "pair_ideal_parallel_runtime_s": {"p50": 100.0},
        "pair_serial_runtime_s": {"p50": 150.0},
    }
    produced = producer.summarize(config, measurements, receipts, runtime)
    reconstructed = verifier.reconstruct_summary(config, measurements, receipts, runtime)
    verifier.compare(produced, reconstructed)
    assert produced["status"] == "DEPLOYMENT_COST_ADVANTAGE_SUPPORTED"


def test_normalized_hash_ignores_crlf_only(tmp_path: Path):
    left, right = tmp_path / "left.txt", tmp_path / "right.txt"
    left.write_bytes(b"a\r\nb\r\n")
    right.write_bytes(b"a\nb\n")
    assert producer.normalized_lf_sha256(left) == producer.normalized_lf_sha256(right)
    assert producer.sha256(left) != producer.sha256(right)


def test_independent_sample_manifest_reconstruction(tmp_path: Path):
    query = tmp_path / "query.jsonl"
    rows = [
        {"better": f"z-{index}", "worse": f"a-{index}", "budget": 0, "intask_split": "test"}
        for index in range(5)
    ]
    query.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    indices = sorted(random.Random(7).sample(range(5), 3))
    pairs = [(f"a-{index}", f"z-{index}") for index in indices]
    pair_sha = hashlib.sha256("\n".join(f"{a}|{z}" for a, z in pairs).encode()).hexdigest()
    manifest = tmp_path / "single_pair_sample.json"
    manifest.write_text(
        json.dumps({"seed": 7, "indices": indices, "pair_manifest_sha256": pair_sha}),
        encoding="utf-8",
    )
    result = verifier.verify_sample_manifest(query, manifest, seed=7, sample_size=3)
    assert result["passed"]
    assert result["sample_pairs"] == 3


def test_cross_run_environment_gate_requires_same_host_and_one_cpu():
    config = {
        "thread_contract": {
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    }
    hardware = {
        "hostname": "host-a",
        "platform": "linux-x",
        "python": "3.11",
        "numpy": "1",
        "scipy": "2",
        "sklearn": "3",
        "cpu_affinity": [0],
    }
    assert all(comparator.environment_checks(config, hardware, dict(hardware)).values())
    other = dict(hardware, hostname="host-b", cpu_affinity=[0, 1])
    checks = comparator.environment_checks(config, hardware, other)
    assert not checks["same_hostname"]
    assert not checks["same_single_cpu_affinity"]
