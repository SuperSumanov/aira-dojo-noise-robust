from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path

import pytest

from phase1 import endpoint_budget_label_efficiency_smoke as smoke
from phase1 import export_endpoint_budget_train_only_firewall as firewall
from phase1 import falsify_historical_run_split_breadth_pareto as graph_impl
from phase1 import verify_endpoint_budget_label_efficiency_smoke as verifier
from phase1.audit_senior_0819_decision_relation_taxonomy import DecisionRow


def edge(index: int, *, run: str | None = None, task: str | None = None):
    return graph_impl.engine.Edge(
        f"u{index}",
        f"v{index}",
        f"p{index}",
        task or f"task{index % 10}",
        run or f"run{index}",
    )


def row(index: int, *, evaluation: bool = False) -> DecisionRow:
    prefix = "eval" if evaluation else "train"
    run = f"{prefix}-run-{index}"
    return DecisionRow(
        first=f"{prefix}-good-{index}",
        second=f"{prefix}-bad-{index}",
        parent=f"{prefix}-parent-{index}",
        task=f"task-{index % 10}",
        split="train",
        first_run=run,
        second_run=run,
        parent_run=run,
        relation="verified_direct_sibling",
    )


def test_protocol_is_frozen_before_endpoint_budget_readout() -> None:
    path = Path("phase1/endpoint_budget_label_efficiency_smoke_v1.json")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    protocol, observed = smoke.load_protocol(path, digest)
    assert observed == digest
    assert protocol["known_before_freeze"][
        "endpoint_budget_matched_downstream_comparison_run_or_seen"
    ] is False
    assert protocol["population"]["senior_test_rows_forbidden"] is True
    assert protocol["population"]["train_only_firewall"][
        "raw_decision_path_passed_to_selection_or_fit"
    ] is False
    assert protocol["resources"]["critic_model_fits"] == 4


def test_protocol_rejects_prior_metric_readout(tmp_path: Path) -> None:
    source = json.loads(
        Path("phase1/endpoint_budget_label_efficiency_smoke_v1.json").read_text(
            encoding="utf-8"
        )
    )
    source["known_before_freeze"][
        "this_accuracy_logloss_brier_or_pairwise_prediction_seen"
    ] = True
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(smoke.SmokeError, match="metric seen"):
        smoke.load_protocol(path, digest)


def test_fold_assignment_fingerprint_has_one_row_per_physical_run() -> None:
    graph = graph_impl.graph_from_edges(
        [edge(0, run="shared-run"), edge(1, run="shared-run"), edge(2)]
    )
    expected = hashlib.sha256(
        "\n".join(
            f"{run}\0{smoke.run_fold(run)}" for run in sorted({"shared-run", "run2"})
        ).encode()
    ).hexdigest()
    assert smoke.fold_assignment_sha(graph) == expected


def test_selection_loader_accepts_only_orientation_free_firewall(tmp_path: Path) -> None:
    source_commit = "a" * 40
    protocol_sha = "b" * 64
    rows = [
        {
            "u": f"u{index:04d}",
            "v": f"v{index:04d}",
            "parent": f"p{index:04d}",
            "task": f"task{index % 10}",
            "physical_run": f"run{index:04d}",
            "source_split": "train",
        }
        for index in range(539)
    ]
    topology = {
        "protocol": smoke.FIREWALL_TOPOLOGY,
        "protocol_sha256": protocol_sha,
        "source_commit": source_commit,
        "rows": rows,
        "pair_orientation_emitted": False,
        "all_source_rows_train": True,
    }
    topology_path = tmp_path / "topology.json"
    topology_path.write_bytes(smoke.canonical_bytes(topology))
    topology_path.chmod(0o600)
    receipt = {
        "protocol": smoke.FIREWALL_RECEIPT,
        "status": "TRAIN_ONLY_FIREWALL_COMPLETE",
        "protocol_sha256": protocol_sha,
        "source_commit": source_commit,
        "topology_sha256": hashlib.sha256(topology_path.read_bytes()).hexdigest(),
        "labels_sha256": "c" * 64,
    }
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_bytes(smoke.canonical_bytes(receipt))
    receipt_path.chmod(0o600)
    full, train, evaluation, observed = smoke.load_firewall_population(
        argparse.Namespace(
            firewall_receipt=receipt_path,
            train_topology=topology_path,
            source_commit=source_commit,
        ),
        protocol_sha,
    )
    assert len(full.edges) == len(train.edges) + len(evaluation.edges) == 539
    assert observed == receipt
    assert not ({edge.run for edge in train.edges} & {edge.run for edge in evaluation.edges})


def test_firewall_has_no_model_or_selection_dependency() -> None:
    source = Path(firewall.__file__).read_text(encoding="utf-8")
    assert "sklearn" not in source
    assert "endpoint_budget_label_efficiency_smoke" not in source
    assert '"senior_test_rows_emitted": 0' in source


def test_independent_pair_fingerprint_matches_oriented_source_row() -> None:
    decision = row(3, evaluation=True)
    graph_edge = graph_impl.engine.Edge(
        decision.second,
        decision.first,
        decision.parent,
        decision.task,
        decision.first_run,
    )
    assert smoke.pair_identity_sha(decision) == verifier.pair_sha(graph_edge)


def test_verifier_does_not_import_fit_producer() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")
    assert "from phase1 import endpoint_budget_label_efficiency_smoke" not in source
    assert "import endpoint_budget_label_efficiency_smoke" not in source


def test_private_entries_require_exact_nested_budgets() -> None:
    private = {
        "arms": {
            "arm": [
                {"budget": 2, "endpoint_ids": ["a", "b"]},
                {"budget": 3, "endpoint_ids": ["a", "b", "c"]},
            ]
        }
    }
    assert smoke.entries_by_budget(private, "arm") == {
        2: {"a", "b"},
        3: {"a", "b", "c"},
    }
    private["arms"]["arm"][1]["endpoint_ids"] = ["a", "c", "d"]
    with pytest.raises(smoke.SmokeError, match="private exact nested"):
        smoke.entries_by_budget(private, "arm")


def test_public_identity_guard_catches_all_identity_levels() -> None:
    graph = graph_impl.graph_from_edges([edge(0)])
    assert smoke.public_has_no_identities({"aggregate": 1}, graph)
    for identity in ("u0", "p0", "task0", "run0"):
        assert not smoke.public_has_no_identities({"leak": identity}, graph)


def test_csv_writer_creates_parent_and_refuses_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "runs.csv"
    smoke.write_csv_exclusive(path, [{"arm": "a", "score": 1}])
    with path.open(newline="", encoding="utf-8") as handle:
        assert list(csv.DictReader(handle)) == [{"arm": "a", "score": "1"}]
    with pytest.raises(FileExistsError):
        smoke.write_csv_exclusive(path, [{"arm": "b", "score": 2}])


def test_fit_checkpoint_is_atomic_private_and_non_overwriting(tmp_path: Path) -> None:
    path = tmp_path / "checkpoints" / "cell.json"
    smoke.write_checkpoint_atomic(path, {"protocol": smoke.FIT_CELL, "value": 1})
    assert json.loads(path.read_text(encoding="utf-8"))["value"] == 1
    if os.name != "nt":
        assert path.stat().st_mode & 0o077 == 0
    assert not list((path.parent / ".staging").iterdir())
    with pytest.raises(FileExistsError):
        smoke.write_checkpoint_atomic(path, {"protocol": smoke.FIT_CELL, "value": 2})


def test_fixed_pairwise_model_smoke_is_finite_and_orientation_aware() -> None:
    pytest.importorskip("numpy")
    pytest.importorskip("scipy")
    pytest.importorskip("sklearn")
    train_rows = [row(index) for index in range(40)]
    eval_rows = [row(index, evaluation=True) for index in range(20)]
    selected = {
        endpoint
        for decision in train_rows
        for endpoint in (decision.first, decision.second)
    }
    codes: dict[str, str] = {}
    for decision in train_rows + eval_rows:
        codes[decision.first] = (
            "validated ensemble cross validation feature engineering robust solution"
        )
        codes[decision.second] = (
            "placeholder constant prediction broken baseline incomplete solution"
        )
    metrics, arrays = smoke.fit_one(selected, train_rows, eval_rows, codes)
    assert metrics["induced_unique_train_pairs"] == 40
    assert metrics["outer_eval_pairs"] == 20
    assert metrics["pairwise_accuracy"] > 0.5
    assert all(math.isfinite(metrics[key]) for key in ("log_loss", "brier_score"))
    assert set(arrays) == {"correct", "log_loss", "brier", "probability"}
    assert all(len(values) == 20 for values in arrays.values())
