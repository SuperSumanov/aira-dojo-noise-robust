from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import audit_senior_0819_pair_benchmark_integrity as producer
from phase1 import verify_senior_0819_pair_benchmark_integrity as verifier


ROOT = Path(__file__).parents[2]
PHASE1 = ROOT / "phase1"
FROZEN_PROTOCOL = PHASE1 / "senior_0819_pair_benchmark_integrity_v1.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decision_row(better: str, worse: str, parent: str, split: str, task: str) -> dict:
    return {
        "better": better,
        "budget": 0,
        "clears_tau": None,
        "gap_raw": 1.0,
        "intask_split": split,
        "loto_fold": task,
        "parent": parent,
        "set_size": 2,
        "src": "decision",
        "task": task,
        "worse": worse,
    }


def value_row(better: str, worse: str, split: str, task: str) -> dict:
    return {
        "agrees_with_quality": True,
        "better": better,
        "budget_secs": 60.0,
        "budget_steps": 20,
        "clears_tau": None,
        "gap_raw": 1.0,
        "intask_split": split,
        "loto_fold": task,
        "src": "value",
        "steps_to_best": [1, 2],
        "subtree_sizes": [2, 1],
        "task": task,
        "worse": worse,
    }


def card(identifier: str, task: str, parent: str | None) -> dict:
    return {
        "id": identifier,
        "task": {"name": task},
        "lineage": {"parent_id": parent},
        "code": "print(1)",
        "label": {"grade": 0.5},
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def fixture(tmp_path: Path) -> dict[str, Path | str]:
    cards = {
        "train-run-a": [
            card("train-parent-a", "task-a", None),
            card("train-good-a", "task-a", "train-parent-a"),
            card("train-bad-a", "task-a", "train-parent-a"),
        ],
        "train-run-b": [
            card("train-root-b", "task-b", None),
            card("train-leaf-b", "task-b", "train-root-b"),
        ],
        "test-run-a": [
            card("test-parent-a", "task-a", None),
            card("test-good-a", "task-a", "test-parent-a"),
            card("test-bad-a", "task-a", "test-parent-a"),
        ],
        "test-run-b": [
            card("test-parent-b", "task-b", None),
            card("test-good-b", "task-b", "test-parent-b"),
            card("test-bad-b", "task-b", "test-parent-b"),
        ],
    }
    cards_path = tmp_path / "cards.json"
    cards_path.write_text(json.dumps(cards, sort_keys=True), encoding="utf-8")
    split_path = tmp_path / "split.json"
    split_path.write_text(
        json.dumps(
            {
                "all": ["train-run-a", "train-run-b", "test-run-a", "test-run-b"],
                "hold": ["test-run-a", "test-run-b"],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    decision = [
        decision_row("train-good-a", "train-bad-a", "train-parent-a", "train", "task-a"),
        decision_row("test-good-a", "test-bad-a", "test-parent-a", "test", "task-a"),
        decision_row("test-good-b", "test-bad-b", "test-parent-b", "test", "task-b"),
    ]
    value = [value_row("train-root-b", "train-leaf-b", "train", "task-b")]
    hardware = list(value)
    mixed = [decision[0], value[0], decision[1], decision[2]]
    paths = {
        "cards": cards_path,
        "run_split": split_path,
        "decision": tmp_path / "decision.jsonl",
        "value": tmp_path / "value.jsonl",
        "value_hardware_time": tmp_path / "hardware.jsonl",
        "mixed": tmp_path / "mixed.jsonl",
    }
    write_jsonl(paths["decision"], decision)
    write_jsonl(paths["value"], value)
    write_jsonl(paths["value_hardware_time"], hardware)
    write_jsonl(paths["mixed"], mixed)

    protocol = json.loads(FROZEN_PROTOCOL.read_text(encoding="utf-8"))
    protocol["source"]["senior_branch_commit"] = "a" * 40
    for role, path in paths.items():
        protocol["immutable_inputs"][role]["sha256"] = sha(path)
    protocol["immutable_inputs"]["run_split"]["all_runs_reported"] = 4
    protocol["immutable_inputs"]["run_split"]["held_runs_reported"] = 2
    counts = {
        "decision": (3, 1, 2),
        "value": (1, 1, 0),
        "value_hardware_time": (1, 1, 0),
        "mixed": (4, 2, 2),
    }
    for role, (rows, train, test) in counts.items():
        protocol["immutable_inputs"][role].update(
            {"rows": rows, "train_rows": train, "test_rows": test}
        )
    protocol["broad_support_gates"] = {
        "minimum_test_pairs": 2,
        "minimum_test_tasks": 2,
        "minimum_test_physical_runs": 2,
        "minimum_test_endpoints": 4,
        "minimum_test_components": 2,
        "maximum_single_task_pair_share": "1/2",
        "maximum_single_run_pair_share": "1/2",
        "maximum_single_component_pair_share": "1/2",
    }
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    scan_path = tmp_path / "scan.json"
    scan_path.write_text(
        json.dumps(
            {
                "status": "CREDENTIAL_SCAN_AND_REDACTION_PASS",
                "input_sha256": sha(cards_path),
                "safe_sha256": sha(cards_path),
                "remaining_credential_hits": 0,
                "private_key_markers": 0,
                "json_parsed_before_scan": False,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return {
        **paths,
        "protocol": protocol_path,
        "protocol_sha": sha(protocol_path),
        "scan": scan_path,
        "source_commit": "a" * 40,
    }


def namespace(data: dict[str, Path | str]) -> argparse.Namespace:
    return argparse.Namespace(
        protocol=data["protocol"],
        protocol_sha256=data["protocol_sha"],
        source_commit=data["source_commit"],
        cards=data["cards"],
        cards_security_receipt=data["scan"],
        run_split=data["run_split"],
        mixed=data["mixed"],
        decision=data["decision"],
        value=data["value"],
        value_hardware_time=data["value_hardware_time"],
    )


def test_synthetic_end_to_end_is_strong_and_independently_equal(tmp_path: Path) -> None:
    data = fixture(tmp_path)
    args = namespace(data)
    produced = producer.audit(args)
    assert produced["classification"] == (
        "HISTORICAL_RUN_ENDPOINT_DISJOINT_EXACT_TEST_PRESERVATION_BROAD_SUPPORT"
    )
    assert all(produced["hard_integrity_gates"].values())
    assert all(produced["broad_support_gates"].values())
    assert produced["dataset_integrity_profiles"]["mixed"]["train_test_endpoint_overlap"] == 0
    assert produced["dataset_integrity_profiles"]["mixed"]["train_test_physical_run_overlap"] == 0
    assert produced["mixed_train_source_support"]["membership_multiplicity_zero"] == 0
    assert produced["mixed_train_source_support"]["actual_sampling_origin_uniquely_recoverable"] is False
    assert verifier.recompute(args) == produced


def test_exact_test_preservation_failure_is_not_rescued(tmp_path: Path) -> None:
    data = fixture(tmp_path)
    mixed_path = data["mixed"]
    rows = [json.loads(line) for line in mixed_path.read_text(encoding="utf-8").splitlines()]
    rows[-1]["gap_raw"] = 2.0
    write_jsonl(mixed_path, rows)
    protocol = json.loads(data["protocol"].read_text(encoding="utf-8"))
    protocol["immutable_inputs"]["mixed"]["sha256"] = sha(mixed_path)
    data["protocol"].write_text(json.dumps(protocol, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    data["protocol_sha"] = sha(data["protocol"])
    result = producer.audit(namespace(data))
    assert result["hard_integrity_gates"]["mixed_test_exactly_preserves_decision_test_multiset"] is False
    assert result["classification"] == "HISTORICAL_PAIR_BENCHMARK_INTEGRITY_GATE_FAIL"


def test_bad_run_split_assignment_fails_closed(tmp_path: Path) -> None:
    data = fixture(tmp_path)
    mixed_path = data["mixed"]
    rows = [json.loads(line) for line in mixed_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["intask_split"] = "test"
    write_jsonl(mixed_path, rows)
    protocol = json.loads(data["protocol"].read_text(encoding="utf-8"))
    protocol["immutable_inputs"]["mixed"]["sha256"] = sha(mixed_path)
    protocol["immutable_inputs"]["mixed"]["train_rows"] = 1
    protocol["immutable_inputs"]["mixed"]["test_rows"] = 3
    data["protocol"].write_text(json.dumps(protocol, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    data["protocol_sha"] = sha(data["protocol"])
    with pytest.raises(producer.PairIntegrityError, match="split assignment mismatch"):
        producer.audit(namespace(data))


def test_conflicting_orientation_is_detected() -> None:
    rows = [
        producer.PairRef("a", "b", "t", "train", "r1", "r1", None, "one"),
        producer.PairRef("b", "a", "t", "train", "r1", "r1", None, "two"),
    ]
    profile = producer.pair_profile(rows)
    assert profile["conflicting_orientation_unordered_pairs"] == 1
    assert profile["duplicate_unordered_pair_rows"] == 1


def test_independent_verifier_does_not_import_producer() -> None:
    source = (PHASE1 / "verify_senior_0819_pair_benchmark_integrity.py").read_text(
        encoding="utf-8"
    )
    assert "import audit_senior_0819_pair_benchmark_integrity" not in source
    assert "from phase1 import audit_senior_0819_pair_benchmark_integrity" not in source
    assert '"producer_imported": False' in source


def test_frozen_protocol_has_honest_claim_and_resource_boundaries() -> None:
    protocol = json.loads(FROZEN_PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["status"] == producer.PROTOCOL_STATUS
    assert protocol["known_before_freeze"]["report_accuracy_and_scaling_values_seen"] is True
    assert protocol["known_before_freeze"]["train_test_endpoint_overlap_seen"] is False
    assert protocol["claim_boundary"]["test_was_used_for_periodic_validation_or_checkpoint_selection"] is True
    assert protocol["claim_boundary"]["clean_scaling_confirmation"] is False
    assert protocol["security"]["prospective_first960_or_target300_values_read"] is False
    assert protocol["resources"] == {
        "gpu_jobs": 0,
        "api_calls": 0,
        "model_fits": 0,
        "base_llm_updates": 0,
    }
