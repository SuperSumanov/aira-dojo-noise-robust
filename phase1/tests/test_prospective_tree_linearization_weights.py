from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import audit_prospective_tree_linearization_weights as producer
from phase1 import verify_prospective_tree_linearization_weights as verifier


ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_PROTOCOL = ROOT / "phase1" / "prospective_tree_linearization_weight_audit_v1.json"
PRODUCER_SOURCE = ROOT / "phase1" / "audit_prospective_tree_linearization_weights.py"
COMMIT = "b" * 40
SNAPSHOT = "a" * 64
SOURCE = "c" * 64


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def card(identifier: str, run: str, task: str, parent: str, depth: int) -> dict:
    code = f"print({identifier!r})\n"
    return {
        "card_id": identifier,
        "task": task,
        "run_id": run,
        "code": code,
        "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
        "lineage": {
            "depth": depth,
            "step": depth,
            "n_siblings": 0,
            "op": "Improve",
            "parent": parent,
        },
        "generation_started_at_utc": "2026-08-28T00:00:00Z",
        "source_sha256": SOURCE,
    }


def make_fixture(tmp_path: Path, rows: list[dict], *, threshold_zero: bool = True) -> dict:
    state = tmp_path / "state"
    snapshot = state / "snapshots" / SNAPSHOT
    intake = state / "intakes" / "drop-1"
    manifest = intake / "eligible_blind_manifest.jsonl"
    write_jsonl(manifest, rows)
    intake_summary = {
        "outputs": {"eligible_blind_manifest_sha256": sha(manifest)},
        "security": {"env_members_read": False, "live_event_journal_members_read": False},
        "blindness": {
            "labels_used_for_run_selection": False,
            "labels_used_for_endpoint_selection": False,
            "metrics_computed": [],
        },
    }
    intake_summary_path = intake / "summary.json"
    write_json(intake_summary_path, intake_summary)
    registry = snapshot / "intake_registry.jsonl"
    write_jsonl(
        registry,
        [{
            "drop_id": "drop-1",
            "intake_dir": str(intake.resolve()),
            "summary_sha256": sha(intake_summary_path),
        }],
    )
    by_run: dict[str, list[dict]] = {}
    for row in rows:
        by_run.setdefault(row["run_id"], []).append(row)
    run_rows = [
        {
            "run_id": run,
            "task": members[0]["task"],
            "drop_id": "drop-1",
            "flow_status": "scoreable",
            "endpoints": len(members),
            "generation_started_at_utc": "2026-08-28T00:00:00Z",
            "source_sha256": SOURCE,
        }
        for run, members in sorted(by_run.items())
    ]
    runs_path = snapshot / "accumulator" / "provisional_runs.jsonl"
    write_jsonl(runs_path, run_rows)
    tasks = len({row["task"] for row in rows})
    accumulator = {
        "protocol": "prospective_accumulator_v1",
        "inputs": {
            "registry_sha256": sha(registry),
            "intake_summaries": {"drop-1": sha(intake_summary_path)},
        },
        "outputs": {"provisional_runs_sha256": sha(runs_path)},
        "inventory": {
            "provisional_first960_runs": len(run_rows),
            "provisional_first960_endpoints": len(rows),
        },
        "task_support": {"provisional_first960": {"tasks": tasks}},
        "closure": {"provided": False},
        "security": {
            "label_vault_opened": False,
            "outcome_files_opened": [],
            "scorer_prediction_files_opened": [],
        },
    }
    write_json(snapshot / "accumulator" / "summary.json", accumulator)
    state.mkdir(parents=True, exist_ok=True)
    (state / "LATEST").write_text(SNAPSHOT + "\n", encoding="utf-8")

    protocol = json.loads(OFFICIAL_PROTOCOL.read_text(encoding="utf-8"))
    protocol["fixed_snapshot"] = {
        "sha256": SNAPSHOT,
        "provisional_first960_runs": len(run_rows),
        "eligible_endpoints": len(rows),
        "tasks": tasks,
        "closure_provided": False,
    }
    protocol["hard_integrity_gates"].update({
        "minimum_parent_present_endpoint_fraction": 0.0,
        "minimum_observed_unique_edges": 1,
        "minimum_physical_runs_with_observed_edges": 1,
        "minimum_tasks_with_observed_edges": 1,
    })
    if threshold_zero:
        protocol["materiality_thresholds"].update({
            "minimum_duplicate_branch_occurrence_fraction": 0.25,
            "minimum_unique_to_linearized_task_total_variation": 0.0,
            "minimum_unique_to_linearized_run_total_variation": 0.0,
        })
    protocol_path = tmp_path / "protocol.json"
    write_json(protocol_path, protocol)
    return {
        "state": state,
        "snapshot": snapshot,
        "manifest": manifest,
        "protocol": protocol_path,
        "protocol_sha": sha(protocol_path),
    }


def fork_rows() -> list[dict]:
    return [
        card("a", "run-1", "task-a", "missing-root", 1),
        card("b", "run-1", "task-a", "a", 2),
        card("c", "run-1", "task-a", "b", 3),
        card("d", "run-1", "task-a", "b", 3),
    ]


def build(fixture: dict) -> dict:
    return producer.build_receipt(
        fixture["state"],
        fixture["snapshot"],
        fixture["protocol"],
        fixture["protocol_sha"],
        COMMIT,
    )


def test_shared_prefix_multiplicity_and_exact_threshold(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path, fork_rows())
    receipt = build(fixture)
    assert receipt["classification"] == "MULTI_AXIS_MATERIAL_LINEARIZATION_REWEIGHTING"
    assert receipt["inventory"]["observed_unique_edges"] == 3
    assert receipt["linearization"]["root_to_leaf_trajectory_count"] == 2
    assert receipt["linearization"]["branch_linearized_edge_occurrences"] == 4
    assert receipt["linearization"]["duplicate_edge_occurrences"] == 1
    assert receipt["linearization"]["duplicate_branch_occurrence_fraction"] == 0.25
    assert receipt["linearization"]["edge_multiplicity"]["histogram"] == {"1": 2, "2": 1}


def test_chain_has_no_linearization_duplication(tmp_path: Path) -> None:
    rows = [
        card("a", "run-1", "task-a", "missing-root", 1),
        card("b", "run-1", "task-a", "a", 2),
        card("c", "run-1", "task-a", "b", 3),
    ]
    receipt = build(make_fixture(tmp_path, rows))
    assert receipt["classification"] == "NO_OBSERVED_LINEARIZATION_DUPLICATION"
    assert receipt["linearization"]["branch_linearized_edge_occurrences"] == 2
    assert receipt["linearization"]["duplicate_edge_occurrences"] == 0


def test_independent_verifier_reconstructs_without_importing_producer(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path, fork_rows())
    receipt = build(fixture)
    receipt_path = tmp_path / "receipt.json"
    write_json(receipt_path, receipt)
    result = verifier.verify(
        fixture["state"],
        fixture["snapshot"],
        fixture["protocol"],
        fixture["protocol_sha"],
        receipt_path,
        sha(receipt_path),
        PRODUCER_SOURCE,
        sha(PRODUCER_SOURCE),
        COMMIT,
    )
    assert result["status"] == "INDEPENDENT_TREE_LINEARIZATION_WEIGHT_AUDIT_PASS"
    assert result["security"]["imports_producer"] is False
    assert result["observed_unique_edges"] == 3


def test_verifier_rejects_result_tamper(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path, fork_rows())
    receipt = build(fixture)
    receipt["linearization"]["duplicate_edge_occurrences"] = 2
    receipt_path = tmp_path / "receipt.json"
    write_json(receipt_path, receipt)
    with pytest.raises(verifier.VerificationError, match="mismatch"):
        verifier.verify(
            fixture["state"], fixture["snapshot"], fixture["protocol"],
            fixture["protocol_sha"], receipt_path, sha(receipt_path),
            PRODUCER_SOURCE, sha(PRODUCER_SOURCE), COMMIT,
        )


def test_cross_run_parent_fails_closed(tmp_path: Path) -> None:
    rows = [
        card("a", "run-1", "task-a", "missing-root", 1),
        card("b", "run-2", "task-a", "a", 2),
    ]
    fixture = make_fixture(tmp_path, rows)
    with pytest.raises(producer.AuditError, match="crosses physical runs"):
        build(fixture)


def test_cycle_fails_closed(tmp_path: Path) -> None:
    rows = [
        card("a", "run-1", "task-a", "b", 1),
        card("b", "run-1", "task-a", "a", 2),
    ]
    fixture = make_fixture(tmp_path, rows)
    with pytest.raises(producer.AuditError, match="cycle"):
        build(fixture)


def test_blind_schema_with_label_fails_closed(tmp_path: Path) -> None:
    rows = fork_rows()
    rows[0] = {**rows[0], "label": 1}
    fixture = make_fixture(tmp_path, rows)
    with pytest.raises(producer.AuditError, match="schema"):
        build(fixture)


def test_protocol_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path, fork_rows())
    with pytest.raises(producer.AuditError, match="protocol SHA"):
        producer.build_receipt(
            fixture["state"], fixture["snapshot"], fixture["protocol"],
            "0" * 64, COMMIT,
        )


def test_aggregate_receipt_emits_no_identifiers_or_code(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path, fork_rows())
    rendered = json.dumps(build(fixture), sort_keys=True)
    for forbidden in ("run-1", "task-a", "missing-root", "print('a')", "print('b')"):
        assert forbidden not in rendered
    assert "task_run_card_parent_or_code_values_emitted" in rendered


def test_gate_failure_precedes_materiality(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path, fork_rows())
    protocol = json.loads(fixture["protocol"].read_text(encoding="utf-8"))
    protocol["hard_integrity_gates"]["minimum_observed_unique_edges"] = 4
    write_json(fixture["protocol"], protocol)
    fixture["protocol_sha"] = sha(fixture["protocol"])
    receipt = build(fixture)
    assert receipt["classification"] == "LINEARIZATION_AUDIT_GATE_FAIL"
    assert receipt["pre_registered_gate"]["materiality"]["duplicate_fraction_at_least_threshold"] is True


def test_result_is_byte_deterministic(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path, fork_rows())
    first = build(fixture)
    second = build(fixture)
    assert json.dumps(first, sort_keys=True, separators=(",", ":")) == json.dumps(
        second, sort_keys=True, separators=(",", ":")
    )
