from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import phase1.tfidf_retrospective_utility_audit as audit
import phase1.tfidf_retrospective_component_utility_audit as component_audit
import phase1.verify_tfidf_retrospective_utility_audit as verifier
import phase1.verify_tfidf_retrospective_component_utility_audit as component_verifier


def write_json(path: Path, value: object) -> dict[str, object]:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.write_bytes(payload)
    return {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> dict[str, object]:
    payload = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows
    ).encode()
    path.write_bytes(payload)
    return {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def card(card_id: str, task: str, grade: float, higher: bool) -> dict[str, object]:
    return {
        "id": card_id,
        "task": {"name": task, "higher_is_better": higher},
        "label": {"graded": grade},
    }


def pair(
    *,
    split: str,
    index: int,
    task: str,
    parent: str,
    semantics: str,
    better: str,
    worse: str,
    margin: float,
) -> dict[str, object]:
    return {
        "better": better,
        "better_run": f"run-{better}",
        "correct": margin > 0,
        "index": index,
        "margin": margin,
        "parent": parent,
        "semantics": semantics,
        "split": split,
        "task": task,
        "tie": False,
        "worse": worse,
        "worse_run": f"run-{worse}",
    }


def parent_rows(split: str, task: str, parent: str, semantics: str, prefix: str) -> list[dict[str, object]]:
    if task == "task-a":
        oriented = (("1", "2", 1.0), ("1", "3", 2.0), ("2", "3", 1.0))
    else:
        oriented = (("1", "2", 2.0), ("1", "3", 1.0), ("2", "3", -1.0))
    return [
        pair(
            split=split,
            index=-1,
            task=task,
            parent=parent,
            semantics=semantics,
            better=f"{prefix}{better}",
            worse=f"{prefix}{worse}",
            margin=margin,
        )
        for better, worse, margin in oriented
    ]


def valid_fixture(tmp_path: Path) -> dict[str, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    cards = []
    rows = []
    for split in ("dev", "test"):
        a_prefix = f"{split}-a"
        b_prefix = f"{split}-b"
        cards.extend(
            [
                card(a_prefix + "1", "task-a", 1.0, True),
                card(a_prefix + "2", "task-a", 0.4, True),
                card(a_prefix + "3", "task-a", 0.2, True),
                card(b_prefix + "1", "task-b", 0.1, False),
                card(b_prefix + "2", "task-b", 0.5, False),
                card(b_prefix + "3", "task-b", 0.8, False),
            ]
        )
        split_rows = parent_rows(split, "task-a", f"{split}-pa", "Draft", a_prefix)
        split_rows += parent_rows(split, "task-b", f"{split}-pb", "Improve", b_prefix)
        for index, row in enumerate(split_rows):
            row["index"] = index
        rows.extend(split_rows)

    cards_path = tmp_path / "cards.json"
    cards_identity = write_json(cards_path, {"run-all": cards})
    pairs_path = tmp_path / "pairs.jsonl"
    pairs_identity = write_jsonl(pairs_path, rows)
    summary_path = tmp_path / "tfidf_summary.json"
    summary = {
        "protocol": "critic-component-char-tfidf-baseline-v1",
        "status": "BASELINE_VALID",
        "model": {"anti_symmetry_max_abs": 0.0},
        "metrics": {
            split: {
                "merged": {
                    "pairs": len([row for row in rows if row["split"] == split]),
                    "micro_accuracy": sum(
                        row["correct"] for row in rows if row["split"] == split
                    )
                    / len([row for row in rows if row["split"] == split]),
                }
            }
            for split in ("dev", "test")
        },
    }
    summary_identity = write_json(summary_path, summary)
    cost_path = tmp_path / "cost.json"
    cost = {
        "protocol": "deployment_cost_attestation_v2",
        "status": "DEPLOYMENT_COST_ADVANTAGE_SUPPORTED",
        "scope": {
            "accuracy_computed": False,
            "prospective_vault_opened": False,
            "gpu_used": False,
            "api_used": False,
        },
        "models": {
            "tfidf_lr": {
                "query_p95_fraction_of_execution_parallel_p50": 0.0002,
                "initialization_break_even_parallel_pairs": 1,
                "initialization_s": {"p50": 10.0},
                "single_pair_query_ms": {"p50": 1.0, "p95": 2.0},
                "execution_parallel_p50_over_query_p50": 1000.0,
            }
        },
        "runtime_reference": {"pair_ideal_parallel_runtime_s": {"p50": 100.0}},
    }
    cost_identity = write_json(cost_path, cost)
    protocol_path = tmp_path / "protocol.json"
    protocol = {
        "protocol": audit.PROTOCOL,
        "status": "FROZEN_BEFORE_GRADE_GAP_AND_PARENT_UTILITY_READ",
        "bootstrap": {"replicates": 1000, "task_seed": 17},
        "frozen_inputs": {
            "cards": cards_identity,
            "tfidf_per_pair": pairs_identity,
            "tfidf_summary": summary_identity,
            "cost_summary": cost_identity,
        },
        "cost_contract": {
            "model": "tfidf_lr",
            "require_query_p95_fraction_of_execution_parallel_p50_below": 0.01,
            "require_initialization_break_even_parallel_pairs_at_most": 1,
        },
        "tolerances": {
            "grade": 1e-12,
            "margin_consistency": 1e-9,
            "prediction_tie": 1e-12,
        },
        "primary_positive_gates": {
            "test_tasks_at_least": 2,
            "test_parents_at_least": 2,
            "test_pair_gap_weighted_accuracy_task_cluster_ci95_lower_gt": 0.5,
            "test_parent_gain_capture_task_cluster_ci95_lower_gt": 0.0,
        },
        "claim_boundary": {"confirmatory": False},
    }
    write_json(protocol_path, protocol)
    return {
        "protocol": protocol_path,
        "cards": cards_path,
        "pairs": pairs_path,
        "summary": summary_path,
        "cost": cost_path,
    }


def run_analyze(paths: dict[str, Path]):
    return audit.analyze(
        paths["protocol"],
        paths["cards"],
        paths["pairs"],
        paths["summary"],
        paths["cost"],
    )


def produce(paths: dict[str, Path], output: Path) -> None:
    summary, pairs, parents = run_analyze(paths)
    audit.write_outputs(output, summary, pairs, parents)


def independently_verify(paths: dict[str, Path], output: Path) -> dict[str, object]:
    return verifier.verify(
        paths["protocol"],
        paths["cards"],
        paths["pairs"],
        paths["summary"],
        paths["cost"],
        output,
    )


def test_valid_fixture_has_positive_pair_and_parent_utility(tmp_path: Path) -> None:
    summary, pairs, parents = run_analyze(valid_fixture(tmp_path))
    assert summary["status"] == "RETROSPECTIVE_COST_UTILITY_POSITIVE"
    assert summary["primary_positive_gates_pass"] is True
    assert summary["metrics"]["test"]["merged"]["tasks"] == 2
    assert summary["metrics"]["test"]["merged"]["parents"] == 2
    assert len(pairs) == 12
    assert len(parents) == 4


def test_rejects_tampered_frozen_input_identity(tmp_path: Path) -> None:
    paths = valid_fixture(tmp_path)
    paths["pairs"].write_text(paths["pairs"].read_text() + "\n")
    with pytest.raises(audit.AuditError, match="identity mismatch"):
        run_analyze(paths)


def test_rejects_wrong_raw_grade_orientation(tmp_path: Path) -> None:
    paths = valid_fixture(tmp_path)
    cards = json.loads(paths["cards"].read_text())
    for value in cards["run-all"]:
        if value["id"] == "test-a1":
            value["label"]["graded"] = 0.0
    identity = write_json(paths["cards"], cards)
    protocol = json.loads(paths["protocol"].read_text())
    protocol["frozen_inputs"]["cards"] = identity
    write_json(paths["protocol"], protocol)
    with pytest.raises(audit.AuditError, match="orientation"):
        run_analyze(paths)


def test_rejects_disconnected_or_inconsistent_parent_graph() -> None:
    truth = {
        name: {"utility": utility}
        for name, utility in {"a": 3.0, "b": 2.0, "c": 1.0, "d": 0.0}.items()
    }
    disconnected = [
        {"better": "a", "worse": "b", "margin": 1.0},
        {"better": "c", "worse": "d", "margin": 1.0},
    ]
    with pytest.raises(audit.AuditError, match="disconnected"):
        audit.parent_prediction(
            disconnected,
            truth,
            margin_tolerance=1e-9,
            grade_tolerance=1e-12,
            tie_tolerance=1e-12,
        )

    inconsistent = [
        {"better": "a", "worse": "b", "margin": 1.0},
        {"better": "b", "worse": "c", "margin": 1.0},
        {"better": "a", "worse": "c", "margin": 3.0},
    ]
    with pytest.raises(audit.AuditError, match="inconsistent"):
        audit.parent_prediction(
            inconsistent,
            truth,
            margin_tolerance=1e-9,
            grade_tolerance=1e-12,
            tie_tolerance=1e-12,
        )


def test_rejects_margin_correct_mismatch(tmp_path: Path) -> None:
    paths = valid_fixture(tmp_path)
    rows = [json.loads(line) for line in paths["pairs"].read_text().splitlines()]
    rows[0]["correct"] = not rows[0]["correct"]
    identity = write_jsonl(paths["pairs"], rows)
    protocol = json.loads(paths["protocol"].read_text())
    protocol["frozen_inputs"]["tfidf_per_pair"] = identity
    write_json(paths["protocol"], protocol)
    with pytest.raises(audit.AuditError, match="margin/correct/tie"):
        run_analyze(paths)


def test_output_is_immutable(tmp_path: Path) -> None:
    paths = valid_fixture(tmp_path)
    summary, pairs, parents = run_analyze(paths)
    output = tmp_path / "output"
    audit.write_outputs(output, summary, pairs, parents)
    assert (output / "artifact_manifest.json").is_file()
    with pytest.raises(audit.AuditError, match="already exists"):
        audit.write_outputs(output, summary, pairs, parents)


def test_independent_verifier_recomputes_complete_artifact(tmp_path: Path) -> None:
    paths = valid_fixture(tmp_path)
    output = tmp_path / "output"
    produce(paths, output)
    receipt = independently_verify(paths, output)
    assert receipt["status"] == "TFIDF_RETROSPECTIVE_UTILITY_INDEPENDENTLY_VERIFIED"
    assert receipt["producer_imported"] is False
    assert receipt["primary_positive_gates_pass"] is True
    assert receipt["utility_pairs"] == 12
    assert receipt["utility_parents"] == 4


def test_independent_verifier_rejects_manifest_consistent_parent_tamper(
    tmp_path: Path,
) -> None:
    paths = valid_fixture(tmp_path)
    output = tmp_path / "output"
    produce(paths, output)
    parent_path = output / "per_parent_utility.jsonl"
    rows = [json.loads(line) for line in parent_path.read_text().splitlines()]
    rows[0]["selected_minus_random"] += 0.125
    identity = write_jsonl(parent_path, rows)
    manifest_path = output / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["per_parent_utility.jsonl"] = identity["sha256"]
    write_json(manifest_path, manifest)
    with pytest.raises(verifier.VerificationError, match="parent utility rows differ"):
        independently_verify(paths, output)


def test_independent_verifier_rejects_cost_scope_claim() -> None:
    protocol = {
        "cost_contract": {
            "model": "tfidf_lr",
            "require_query_p95_fraction_of_execution_parallel_p50_below": 0.01,
            "require_initialization_break_even_parallel_pairs_at_most": 1,
        }
    }
    cost = {
        "protocol": "deployment_cost_attestation_v2",
        "status": "DEPLOYMENT_COST_ADVANTAGE_SUPPORTED",
        "scope": {
            "accuracy_computed": True,
            "prospective_vault_opened": False,
            "gpu_used": False,
            "api_used": False,
        },
        "models": {
            "tfidf_lr": {
                "query_p95_fraction_of_execution_parallel_p50": 0.0002,
                "initialization_break_even_parallel_pairs": 1,
            }
        },
    }
    with pytest.raises(verifier.VerificationError, match="cost source summary"):
        verifier.validate_cost_summary(cost, protocol)


def v2_fixture(tmp_path: Path) -> dict[str, Path]:
    paths = valid_fixture(tmp_path)
    cards_root = json.loads(paths["cards"].read_text())
    rows = [json.loads(line) for line in paths["pairs"].read_text().splitlines()]
    for split in ("dev", "test"):
        prefix = f"{split}-a"
        cards_root["run-all"].extend(
            [
                card(prefix + "4", "task-a", 0.15, True),
                card(prefix + "5", "task-a", 0.05, True),
            ]
        )
        rows.append(
            pair(
                split=split,
                index=6,
                task="task-a",
                parent=f"{split}-pa",
                semantics="Draft",
                better=prefix + "4",
                worse=prefix + "5",
                margin=0.25,
            )
        )
    cards_identity = write_json(paths["cards"], cards_root)
    pairs_identity = write_jsonl(paths["pairs"], rows)
    tfidf_summary = json.loads(paths["summary"].read_text())
    for split in ("dev", "test"):
        selected = [row for row in rows if row["split"] == split]
        tfidf_summary["metrics"][split]["merged"] = {
            "pairs": len(selected),
            "micro_accuracy": sum(row["correct"] for row in selected)
            / len(selected),
        }
    summary_identity = write_json(paths["summary"], tfidf_summary)
    cost_identity = {
        "bytes": paths["cost"].stat().st_size,
        "sha256": hashlib.sha256(paths["cost"].read_bytes()).hexdigest(),
    }
    _, structure = component_audit.partition_components(rows)
    protocol = {
        "protocol": component_audit.PROTOCOL,
        "status": component_audit.STATUS,
        "bootstrap": {"replicates": 1000, "task_seed": 17},
        "frozen_inputs": {
            "cards": cards_identity,
            "tfidf_per_pair": pairs_identity,
            "tfidf_summary": summary_identity,
            "cost_summary": cost_identity,
        },
        "cost_contract": {
            "model": "tfidf_lr",
            "require_query_p95_fraction_of_execution_parallel_p50_below": 0.01,
            "require_initialization_break_even_parallel_pairs_at_most": 1,
        },
        "tolerances": {
            "grade": 1e-12,
            "margin_consistency": 1e-9,
            "prediction_tie": 1e-12,
        },
        "expected_structure": structure,
        "predecessor": {
            "status": "V1_INVALID_STRUCTURAL_GRAPH_ASSUMPTION",
            "aggregate_utility_output_emitted": False,
        },
        "primary_positive_gates": {
            "test_tasks_at_least": 2,
            "test_decision_components_at_least": 3,
            "test_pair_gap_weighted_accuracy_task_cluster_ci95_lower_gt": 0.5,
            "test_component_gain_capture_task_cluster_ci95_lower_gt": 0.0,
        },
        "claim_boundary": {
            "confirmatory": False,
            "utility_aggregate_observed_before_v2_freeze": False,
        },
    }
    write_json(paths["protocol"], protocol)
    return paths


def run_component_analyze(paths: dict[str, Path]):
    return component_audit.analyze(
        paths["protocol"],
        paths["cards"],
        paths["pairs"],
        paths["summary"],
        paths["cost"],
    )


def test_v2_partitions_disconnected_parent_without_dropping_pairs(
    tmp_path: Path,
) -> None:
    paths = v2_fixture(tmp_path)
    summary, pairs, components = run_component_analyze(paths)
    assert len(pairs) == 14
    assert len(components) == 6
    assert summary["structure"]["disconnected_parent_groups"] == 2
    assert summary["structure"]["all_pairs_assigned_exactly_once"] is True
    assert summary["metrics"]["test"]["merged"]["decision_components"] == 3
    assert summary["primary_positive_gates_pass"] is True


def test_v2_independent_verifier_recomputes_components(tmp_path: Path) -> None:
    paths = v2_fixture(tmp_path)
    summary, pairs, components = run_component_analyze(paths)
    output = tmp_path / "v2-output"
    component_audit.write_outputs(output, summary, pairs, components)
    receipt = component_verifier.verify(
        paths["protocol"],
        paths["cards"],
        paths["pairs"],
        paths["summary"],
        paths["cost"],
        output,
    )
    assert receipt["producer_imported"] is False
    assert receipt["utility_pairs"] == 14
    assert receipt["utility_components"] == 6
    assert receipt["primary_positive_gates_pass"] is True


def test_v2_rejects_frozen_structure_mismatch(tmp_path: Path) -> None:
    paths = v2_fixture(tmp_path)
    protocol = json.loads(paths["protocol"].read_text())
    protocol["expected_structure"]["decision_components"] += 1
    write_json(paths["protocol"], protocol)
    with pytest.raises(component_audit.ComponentAuditError, match="structural receipt"):
        run_component_analyze(paths)


def test_v2_verifier_rejects_manifest_consistent_component_tamper(
    tmp_path: Path,
) -> None:
    paths = v2_fixture(tmp_path)
    summary, pairs, components = run_component_analyze(paths)
    output = tmp_path / "v2-output"
    component_audit.write_outputs(output, summary, pairs, components)
    component_path = output / "per_component_utility.jsonl"
    rows = [json.loads(line) for line in component_path.read_text().splitlines()]
    rows[0]["selected_minus_random"] += 0.125
    identity = write_jsonl(component_path, rows)
    manifest_path = output / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["per_component_utility.jsonl"] = identity["sha256"]
    write_json(manifest_path, manifest)
    with pytest.raises(component_verifier.ComponentVerificationError, match="component rows differ"):
        component_verifier.verify(
            paths["protocol"],
            paths["cards"],
            paths["pairs"],
            paths["summary"],
            paths["cost"],
            output,
        )


def test_v2_outputs_are_byte_identical_across_python_hash_seeds(
    tmp_path: Path,
) -> None:
    paths = v2_fixture(tmp_path)
    outputs = []
    for seed in ("11", "29"):
        output = tmp_path / f"hash-seed-{seed}"
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = seed
        subprocess.run(
            [
                sys.executable,
                "-m",
                "phase1.tfidf_retrospective_component_utility_audit",
                str(paths["protocol"]),
                str(paths["cards"]),
                str(paths["pairs"]),
                str(paths["summary"]),
                str(paths["cost"]),
                str(output),
            ],
            check=True,
            cwd=Path(__file__).resolve().parents[2],
            env=environment,
            capture_output=True,
            text=True,
        )
        outputs.append(output)
    names = {
        "summary.json",
        "per_pair_utility.jsonl",
        "per_component_utility.jsonl",
        "per_task.csv",
        "artifact_manifest.json",
    }
    assert {
        name: (outputs[0] / name).read_bytes() for name in names
    } == {
        name: (outputs[1] / name).read_bytes() for name in names
    }
