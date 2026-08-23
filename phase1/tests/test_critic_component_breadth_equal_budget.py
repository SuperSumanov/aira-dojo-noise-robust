from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest

from phase1 import critic_component_breadth_equal_budget as producer
from phase1 import verify_critic_component_breadth_equal_budget as verifier


CONTRACT = Path(__file__).parents[1] / "critic_component_breadth_equal_budget_v1.json"
LAUNCHER = Path(__file__).parents[1] / "scripts" / "run_critic_component_breadth_equal_budget_20260823.sh"


def row(task: str, component: str, index: int) -> dict:
    return {
        "task": task,
        "parent": f"parent-{task}-{index}",
        "better": f"card-{task}-{index}-a",
        "worse": f"card-{task}-{index}-b",
        "pair_component_id": component,
    }


def test_contract_hash_and_closed_input_surface() -> None:
    assert producer.sha256_file(CONTRACT) == producer.CONTRACT_SHA256
    contract = producer.verify_contract(CONTRACT)
    assert contract["status"] == "PREREGISTERED_RETROSPECTIVE_DEV_ONLY_NOT_RUN"
    assert contract["selection"]["pair_orientation_used_for_selection"] is False
    assert contract["access_contract"]["pair_inputs"] == ["component_clean_train", "component_clean_dev"]
    assert "heldout_test_pairs" in contract["access_contract"]["forbidden_inputs"]
    assert set(inspect.signature(producer.analyze).parameters) == {
        "cards_path", "train_path", "dev_path", "contract_path"
    }


def test_launcher_has_no_test_path_gpu_or_api() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")
    assert "heldout_test.jsonl" not in source
    assert "sbatch" not in source
    assert "api_key" not in source.lower()
    assert '"$cards" "$train" "$dev"' in source
    assert "OMP_NUM_THREADS=1" in source
    assert 'cd "$repo"' in source


def test_breadth_selection_is_exact_and_orientation_invariant() -> None:
    groups = {
        "a" * 64: [row("t", "a" * 64, index) for index in range(6)],
        "b" * 64: [row("t", "b" * 64, 10 + index) for index in range(3)],
        "c" * 64: [row("t", "c" * 64, 20 + index) for index in range(2)],
        "d" * 64: [row("t", "d" * 64, 30)],
    }
    broad = producer.choose_broad(groups, 6, 20260823)
    concentrated = producer.choose_concentrated(groups, 6, 20260823)
    random = producer.choose_random(groups, 6, 20260823)
    assert {len(items) for items in (broad, concentrated, random)} == {6}
    assert len({item["pair_component_id"] for item in broad}) == 4
    assert len({item["pair_component_id"] for item in concentrated}) == 1
    swapped = {
        component: [{**item, "better": item["worse"], "worse": item["better"]} for item in rows]
        for component, rows in groups.items()
    }
    swapped_broad = producer.choose_broad(swapped, 6, 20260823)
    assert {producer.pair_identity(item) for item in broad} == {
        producer.pair_identity(item) for item in swapped_broad
    }


def synthetic_matrix(positive: bool) -> tuple[dict[tuple[int, str], dict], dict]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    matrix = {}
    for seed_index, seed in enumerate(contract["selection"]["seeds"]):
        for arm in ("broad", "concentrated", "random"):
            if positive:
                base_loss = {"broad": 0.54, "random": 0.57, "concentrated": 0.61}[arm]
                base_accuracy = {"broad": 0.64, "random": 0.60, "concentrated": 0.56}[arm]
            else:
                base_loss = {"broad": 0.62, "random": 0.59, "concentrated": 0.56}[arm]
                base_accuracy = {"broad": 0.54, "random": 0.57, "concentrated": 0.61}[arm]
            tasks = {
                f"task-{index}": {
                    "pairs": 10,
                    "log_loss": base_loss + 0.001 * index + 0.0001 * seed_index,
                    "accuracy": base_accuracy + 0.001 * index - 0.0001 * seed_index,
                }
                for index in range(8)
            }
            matrix[(seed, arm)] = {
                "metrics": {
                    "task_macro_log_loss": sum(item["log_loss"] for item in tasks.values()) / len(tasks),
                    "task_macro_accuracy": sum(item["accuracy"] for item in tasks.values()) / len(tasks),
                },
                "task_metrics": tasks,
            }
    return matrix, contract


def test_positive_and_negative_decision_controls() -> None:
    matrix, contract = synthetic_matrix(True)
    result = producer.evaluate(matrix, contract)
    independent = verifier.decision(matrix, contract)
    assert result == independent
    assert result["proper_score_positive"] is True
    assert result["top1_positive"] is True
    matrix, contract = synthetic_matrix(False)
    result = producer.evaluate(matrix, contract)
    assert result["proper_score_positive"] is False
    assert result["top1_positive"] is False
    assert result["any_predeclared_positive"] is False


def test_verifier_rejects_numeric_tamper() -> None:
    assert verifier.close_enough({"value": 1.0}, {"value": 1.0}) == 0.0
    with pytest.raises(verifier.VerificationError, match="numeric mismatch"):
        verifier.close_enough({"value": 1.0}, {"value": 1.001})


def test_independent_verifier_does_not_import_producer() -> None:
    source = inspect.getsource(verifier)
    assert "from phase1 import critic_component_breadth_equal_budget" not in source
    assert "from phase1.critic_component_breadth_equal_budget" not in source


def test_python_sources_have_no_json_literal_names() -> None:
    for module in (producer, verifier):
        tree = ast.parse(inspect.getsource(module))
        invalid = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} & {"true", "false", "null"}
        assert invalid == set()


def test_output_overwrite_is_fail_closed(tmp_path: Path) -> None:
    output = tmp_path / "already-there"
    output.mkdir()
    with pytest.raises(producer.BreadthError, match="already exists"):
        producer.write_artifacts(output, {}, [], [], [], [])
