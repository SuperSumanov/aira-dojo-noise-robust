from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from phase1 import decision_semantic_exact_config_support as producer
from phase1 import verify_decision_semantic_exact_config_support as verifier


def pair(
    better: str,
    worse: str,
    *,
    split: str,
    parent: str,
    task: str,
) -> dict:
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


def support_fixture() -> tuple[list[dict], list[dict], list[dict], dict, dict, dict]:
    draft = [
        pair("dt-good", "dt-bad", split="train", parent="dt-parent", task="task-a"),
        pair("dx-good", "dx-bad", split="test", parent="dx-parent", task="task-b"),
    ]
    improve = [
        pair("it-good", "it-bad", split="train", parent="it-parent", task="task-a"),
        pair("ix-good", "ix-bad", split="test", parent="ix-parent", task="task-c"),
    ]
    merged = [*draft, *improve]
    configs = {
        name: (task, "client", "gpu", 120, 180)
        for name, task in {
            "dt-good": "task-a",
            "dt-bad": "task-a",
            "dx-good": "task-b",
            "dx-bad": "task-b",
            "it-good": "task-a",
            "it-bad": "task-a",
            "ix-good": "task-c",
            "ix-bad": "task-c",
        }.items()
    }
    # One deliberately ineligible pair: only the client differs.
    configs["dx-bad"] = ("task-b", "other-client", "gpu", 120, 180)
    run_of = {
        "dt-good": "run-train-1",
        "dt-bad": "run-train-1",
        "it-good": "run-train-2",
        "it-bad": "run-train-2",
        "dx-good": "run-test-1",
        "dx-bad": "run-test-1",
        "ix-good": "run-test-2",
        "ix-bad": "run-test-2",
    }
    inventory = {
        "run_groups": 676,
        "cards": 31742,
        "needed_cards": 8,
        "duplicate_card_ids": 0,
    }
    return merged, draft, improve, configs, run_of, inventory


def test_support_summary_filters_only_exact_config_and_matches_independent_rebuild() -> None:
    merged, draft, improve, configs, run_of, inventory = support_fixture()
    produced, eligible, per_task = producer.summarize(
        merged, draft, improve, configs, run_of, inventory
    )
    rebuilt, independently_eligible, independently_per_task = verifier.independent_summary(
        merged, draft, improve, configs, run_of
    )

    assert produced == rebuilt
    assert eligible == independently_eligible
    assert per_task == independently_per_task
    assert produced["mismatch"]["pairs"] == 1
    assert produced["mismatch"]["by_field"] == {"client": 1}
    assert produced["mismatch"]["by_semantics_split"]["draft_test"] == 1
    assert produced["eligible_inventory"]["merged"] == {"train": 2, "test": 1, "total": 3}
    assert produced["eligible_support"]["merged"]["all"] == {
        "pairs": 3,
        "endpoints": 6,
        "physical_runs": 3,
        "tasks": 2,
        "task_parent_keys": 3,
        "exact_config_strata": 2,
    }
    assert produced["status"] == "V2_INSUFFICIENT_EXACT_CONFIG_SUPPORT"


@pytest.mark.parametrize(
    ("index", "replacement", "field"),
    [
        (0, "task-z", "task"),
        (1, "other-client", "client"),
        (2, "other-gpu", "hardware"),
        (3, 240, "time_limit"),
        (4, 360, "execution_timeout"),
    ],
)
def test_each_provenance_field_is_part_of_exact_config(
    index: int, replacement: object, field: str
) -> None:
    row = pair("a", "b", split="train", parent="p", task="task-a")
    base = ["task-a", "client", "gpu", 120, 180]
    changed = list(base)
    changed[index] = replacement
    configs = {"a": tuple(base), "b": tuple(changed)}
    assert producer.exact(row, configs) is False
    assert producer.mismatch_fields(row, configs) == (field,)
    assert verifier.exact(row, configs) is False
    assert verifier.changed(row, configs) == (field,)


def test_filtered_train_test_run_overlap_fails_closed() -> None:
    merged, draft, improve, configs, run_of, inventory = support_fixture()
    run_of["ix-good"] = "run-train-1"
    run_of["ix-bad"] = "run-train-1"
    with pytest.raises(producer.SupportError, match="filtered integrity"):
        producer.summarize(merged, draft, improve, configs, run_of, inventory)


def test_raw_component_identity_overlap_fails_closed() -> None:
    merged, draft, improve, configs, run_of, inventory = support_fixture()
    improve = [dict(draft[0])]
    merged = [*draft, *improve]
    with pytest.raises(producer.SupportError, match="raw integrity"):
        producer.summarize(merged, draft, improve, configs, run_of, inventory)


def test_credential_scan_catches_shape_across_chunk_boundary(tmp_path: Path) -> None:
    path = tmp_path / "cross-boundary.bin"
    path.write_bytes(b"x" * ((1 << 20) - 3) + b" sk-" + b"A" * 20)
    with pytest.raises(producer.SupportError, match="credential-shaped"):
        producer.scan_credential_shapes(path, "fixture")


def test_pair_schema_is_exact_and_blank_rows_fail_closed(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.jsonl"
    row = pair("a", "b", split="train", parent="p", task="task-a")
    row["extra"] = True
    schema_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(producer.SupportError, match="schema mismatch"):
        producer.read_rows(schema_path)

    blank_path = tmp_path / "blank.jsonl"
    blank_path.write_text("\n", encoding="utf-8")
    with pytest.raises(producer.SupportError, match="blank pair row"):
        producer.read_rows(blank_path)


def test_independent_verifier_does_not_import_producer() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")
    imported: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not any(name.endswith("decision_semantic_exact_config_support") for name in imported)
