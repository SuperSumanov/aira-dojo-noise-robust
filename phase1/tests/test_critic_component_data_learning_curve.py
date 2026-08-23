from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest

from phase1 import critic_component_data_learning_curve as producer
from phase1 import verify_critic_component_data_learning_curve as verifier


CONTRACT = Path(__file__).parents[1] / "critic_component_data_learning_curve_v1.json"
LAUNCHER = Path(__file__).parents[1] / "scripts" / "run_critic_component_data_learning_curve_20260823.sh"


def test_contract_hash_and_closed_input_surface() -> None:
    assert producer.sha256_file(CONTRACT) == producer.CONTRACT_SHA256
    contract = producer.verify_contract(CONTRACT)
    assert contract["status"] == "PREREGISTERED_RETROSPECTIVE_DEV_ONLY_NOT_RUN"
    assert contract["access_contract"]["pair_inputs"] == ["component_clean_train", "component_clean_dev"]
    assert contract["access_contract"]["cards_container_full_json_parsed"] is True
    assert contract["access_contract"]["nonretained_card_fields_referenced"] is False
    assert "heldout_test_pairs" in contract["access_contract"]["forbidden_inputs"]
    parameters = inspect.signature(producer.analyze).parameters
    assert set(parameters) == {"cards_path", "train_path", "dev_path", "contract_path"}


def test_launcher_has_no_test_pair_path_or_gpu_submission() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")
    assert "heldout_test.jsonl" not in source
    assert "sbatch" not in source
    assert '"$cards" "$train" "$dev"' in source
    assert "OMP_NUM_THREADS=1" in source
    assert 'cd "$repo"' in source
    assert "! -name run.log" in source
    assert source.index("! -name run.log") < source.index("COMPONENT_CURVE_FORMAL_COMPLETE")


def test_component_selection_is_nested_and_order_invariant() -> None:
    inventory = {
        "a" * 64: {"task": "t1", "pairs": 5},
        "b" * 64: {"task": "t1", "pairs": 3},
        "c" * 64: {"task": "t2", "pairs": 4},
        "d" * 64: {"task": "t2", "pairs": 2},
        "e" * 64: {"task": "t3", "pairs": 6},
    }
    selected = [
        set(producer.selected_components(inventory, 20, 20260823, fraction))
        for fraction in (0.25, 0.5, 0.75, 1.0)
    ]
    assert all(left <= right for left, right in zip(selected, selected[1:]))
    assert selected[-1] == set(inventory)
    assert len({inventory[item]["task"] for item in selected[0]}) == 3
    reversed_inventory = dict(reversed(list(inventory.items())))
    assert producer.selected_components(inventory, 20, 20260823, 0.5) == producer.selected_components(
        reversed_inventory, 20, 20260823, 0.5
    )


def synthetic_matrix(positive: bool) -> tuple[dict[tuple[int, float], dict], dict]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    fractions = contract["selection"]["fractions"]
    seeds = contract["selection"]["seeds"]
    matrix = {}
    for seed_index, seed in enumerate(seeds):
        for fraction_index, fraction in enumerate(fractions):
            if positive:
                loss = 0.72 - 0.06 * fraction_index + (0.002 * seed_index if fraction < 1.0 else 0.0)
                accuracy = 0.50 + 0.07 * fraction_index - (0.002 * seed_index if fraction < 1.0 else 0.0)
            else:
                loss = 0.60 + 0.01 * fraction_index
                accuracy = 0.58 - 0.01 * fraction_index
            tasks = {
                f"task-{task_index}": {
                    "pairs": 10,
                    "log_loss": loss + task_index * 0.001,
                    "accuracy": accuracy + task_index * 0.001,
                }
                for task_index in range(4)
            }
            matrix[(seed, fraction)] = {
                "metrics": {
                    "task_macro_log_loss": sum(item["log_loss"] for item in tasks.values()) / len(tasks),
                    "task_macro_accuracy": sum(item["accuracy"] for item in tasks.values()) / len(tasks),
                },
                "task_metrics": tasks,
            }
    return matrix, contract


def test_positive_and_negative_decision_controls() -> None:
    matrix, contract = synthetic_matrix(True)
    result = producer.evaluate_curve(matrix, contract)
    independent = verifier.decision(matrix, contract)
    assert result == independent
    assert result["proper_score_positive"] is True
    assert result["top1_positive"] is True
    matrix, contract = synthetic_matrix(False)
    result = producer.evaluate_curve(matrix, contract)
    assert result["proper_score_positive"] is False
    assert result["top1_positive"] is False
    assert result["any_predeclared_positive"] is False


def test_verifier_rejects_numeric_tamper() -> None:
    assert verifier.close_enough({"value": 1.0}, {"value": 1.0}) == 0.0
    with pytest.raises(verifier.VerificationError, match="numeric mismatch"):
        verifier.close_enough({"value": 1.0}, {"value": 1.0001})


def test_independent_verifier_does_not_import_producer() -> None:
    source = inspect.getsource(verifier)
    assert "from phase1 import critic_component_data_learning_curve" not in source
    assert "from phase1.critic_component_data_learning_curve" not in source


def test_python_sources_have_no_json_literal_names() -> None:
    for module in (producer, verifier):
        tree = ast.parse(inspect.getsource(module))
        invalid = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} & {"true", "false", "null"}
        assert invalid == set()


def test_output_overwrite_is_fail_closed(tmp_path: Path) -> None:
    output = tmp_path / "already-there"
    output.mkdir()
    with pytest.raises(producer.CurveError, match="already exists"):
        producer.write_artifacts(output, {}, [], [], [])
