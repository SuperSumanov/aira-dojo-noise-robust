from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np
import pytest

from phase1 import decision_semantic_mixture as producer
from phase1 import verify_decision_semantic_mixture as verifier


def pair(better: str, worse: str, *, split: str, parent: str, task: str = "task-a") -> dict:
    return {
        "better": better,
        "worse": worse,
        "task": task,
        "parent": parent,
        "src": "decision",
        "intask_split": split,
        "loto_fold": task,
        "gap_raw": 0.1,
        "budget": 0,
        "set_size": 2,
        "clears_tau": None,
    }


def integrity_fixture() -> tuple[list[dict], list[dict], list[dict], dict, dict, dict, dict]:
    draft = [pair("d-better", "d-worse", split="train", parent="draft-parent")]
    improve = [pair("i-better", "i-worse", split="test", parent="improve-parent")]
    merged = [*draft, *improve]
    runs = {
        "d-better": "run-train",
        "d-worse": "run-train",
        "i-better": "run-test",
        "i-worse": "run-test",
    }
    config = {
        key: ("task-a", "client", "gpu", 120, 180)
        for key in runs
    }
    inventory = {"run_groups": 2, "cards": 4, "needed_cards": 4, "duplicate_card_ids": 0}
    expected = {
        "card_run_groups": 2,
        "cards": 4,
        "merged_train": 1,
        "merged_test": 1,
        "draft_train": 1,
        "draft_test": 0,
        "improve_train": 0,
        "improve_test": 1,
    }
    return merged, draft, improve, runs, config, inventory, expected


def test_integrity_accepts_exact_union_and_run_disjoint_split() -> None:
    merged, draft, improve, runs, config, inventory, expected = integrity_fixture()
    result = producer.verify_integrity(
        merged, draft, improve, runs, config, inventory, expected_counts=expected
    )
    assert all(result["checks"].values())
    assert result["train_test_endpoint_overlap"] == 0
    assert result["train_test_run_overlap"] == 0


def test_integrity_rejects_execution_config_mismatch() -> None:
    merged, draft, improve, runs, config, inventory, expected = integrity_fixture()
    config["i-worse"] = ("task-a", "other-client", "gpu", 120, 180)
    with pytest.raises(producer.DiscoveryError, match="exact_execution_config"):
        producer.verify_integrity(
            merged, draft, improve, runs, config, inventory, expected_counts=expected
        )


def test_integrity_rejects_component_overlap() -> None:
    merged, draft, improve, runs, config, inventory, expected = integrity_fixture()
    improve = [dict(draft[0])]
    merged = [*draft, *improve]
    expected.update(merged_train=2, merged_test=0, improve_train=1, improve_test=0)
    with pytest.raises(producer.DiscoveryError, match="draft_improve_pair_identity_disjoint"):
        producer.verify_integrity(
            merged, draft, improve, runs, config, inventory, expected_counts=expected
        )


def test_fixed_mix_metrics_count_zero_margin_as_tie_and_error() -> None:
    rows = [
        pair("a", "b", split="test", parent="p1", task="task-a"),
        pair("c", "d", split="test", parent="p2", task="task-b"),
    ]
    margins = {
        "pooled": np.array([1.0, -1.0]),
        "specialist": np.array([-1.0, 1.0]),
        "semantic_mix": np.array([0.0, 0.0]),
    }
    metrics, task_rows = producer.arm_metrics(rows, ["draft", "improve"], margins)
    assert metrics["merged"]["semantic_mix"]["micro_accuracy"] == 0.0
    assert metrics["merged"]["semantic_mix"]["ties"] == 2
    assert len([row for row in task_rows if row["subset"] == "merged"]) == 2


def synthetic_training_fixture() -> tuple[dict[str, str], list[dict], list[dict], list[dict]]:
    codes: dict[str, str] = {}
    draft: list[dict] = []
    improve: list[dict] = []
    for kind, target in (("draft", draft), ("improve", improve)):
        for index in range(6):
            better = f"{kind}-train-good-{index}"
            worse = f"{kind}-train-bad-{index}"
            codes[better] = "import sklearn\ngood_model cross_validation robust_feature\n" * 3
            codes[worse] = "import pandas\nbad_baseline constant_guess weak_feature\n" * 3
            target.append(pair(better, worse, split="train", parent=f"{kind}-train-{index}"))
        for index in range(2):
            better = f"{kind}-test-good-{index}"
            worse = f"{kind}-test-bad-{index}"
            codes[better] = "good_model cross_validation robust_feature\n" * 3
            codes[worse] = "bad_baseline constant_guess weak_feature\n" * 3
            target.append(pair(better, worse, split="test", parent=f"{kind}-test-{index}"))
    return codes, [*draft, *improve], draft, improve


def test_analysis_is_deterministic_on_synthetic_fixture() -> None:
    codes, merged, draft, improve = synthetic_training_fixture()
    first, first_tasks = producer.analyze(codes, merged, draft, improve)
    second, second_tasks = producer.analyze(codes, merged, draft, improve)
    assert first == second
    assert first_tasks == second_tasks
    assert first["representation"]["features"] > 0
    assert first["metrics"]["merged"]["pooled"]["pairs"] == 4


def test_independent_full_refit_matches_producer_on_synthetic_fixture() -> None:
    codes, merged, draft, improve = synthetic_training_fixture()
    produced, produced_tasks = producer.analyze(codes, merged, draft, improve)
    independently, independent_tasks = verifier.rebuild(codes, merged, draft, improve)
    assert independently == produced
    assert independent_tasks == produced_tasks


def test_secret_scan_fails_before_json_parse(tmp_path: Path) -> None:
    path = tmp_path / "not-json"
    path.write_bytes(b"broken sk-" + b"A" * 20)
    with pytest.raises(producer.DiscoveryError, match="credential-shaped"):
        producer.scan_secret(path)


def test_verifier_source_does_not_import_producer() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")
    names: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    assert not any(name.endswith("decision_semantic_mixture") for name in names)


def test_pair_json_schema_is_exact(tmp_path: Path) -> None:
    path = tmp_path / "pairs.jsonl"
    row = pair("a", "b", split="train", parent="p")
    row["unexpected"] = True
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(producer.DiscoveryError, match="schema mismatch"):
        producer.read_pairs(path)


def test_v2_inputs_are_bound_to_verified_exact_config_support() -> None:
    assert producer.PROTOCOL == verifier.PROTOCOL == "decision-semantic-mixture-discovery-v2-exact-config"
    assert producer.EXPECTED == verifier.IDENTITIES
    assert producer.EXPECTED_COUNTS == {
        "card_run_groups": 676,
        "cards": 31742,
        "merged_train": 5240,
        "merged_test": 931,
        "draft_train": 3196,
        "draft_test": 314,
        "improve_train": 2044,
        "improve_test": 617,
    }
    assert producer.SUPPORT_GATE == verifier.SUPPORT_GATE
    assert producer.SUPPORT_GATE["source_commit"] == "21a4d4e4e81e780259fbf300112b561ae0fc1116"
    assert producer.SUPPORT_GATE["status"] == "V2_EXACT_CONFIG_SUPPORT_ELIGIBLE"
