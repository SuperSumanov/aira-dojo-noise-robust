from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path

import pytest

from phase1 import audit_prospective_tree_linearization_weights as upstream_producer
from phase1 import certify_tree_native_path_compatibility as producer
from phase1 import verify_tree_native_path_compatibility as verifier


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "phase1" / "tree_native_path_compatibility_contract_v1.json"
UPSTREAM_PROTOCOL = ROOT / "phase1" / "prospective_tree_linearization_weight_audit_v1.json"
PRODUCER_SOURCE = ROOT / "phase1" / "certify_tree_native_path_compatibility.py"
VERIFIER_SOURCE = ROOT / "phase1" / "verify_tree_native_path_compatibility.py"
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


def fork_rows() -> list[dict]:
    return [
        card("a", "run-1", "task-a", "missing-root", 1),
        card("b", "run-1", "task-a", "a", 2),
        card("c", "run-1", "task-a", "b", 3),
        card("d", "run-1", "task-a", "b", 3),
    ]


def make_state(tmp_path: Path, rows: list[dict]) -> tuple[Path, Path]:
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
    summary = {
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
        "task_support": {
            "provisional_first960": {"tasks": len({row["task"] for row in rows})}
        },
        "closure": {"provided": False},
        "security": {
            "label_vault_opened": False,
            "outcome_files_opened": [],
            "scorer_prediction_files_opened": [],
        },
    }
    write_json(snapshot / "accumulator" / "summary.json", summary)
    state.mkdir(parents=True, exist_ok=True)
    (state / "LATEST").write_text(SNAPSHOT + "\n", encoding="utf-8", newline="\n")
    return state, snapshot


def make_fixture(tmp_path: Path, rows: list[dict]) -> dict:
    state, snapshot = make_state(tmp_path, rows)
    run_count = len({row["run_id"] for row in rows})
    task_count = len({row["task"] for row in rows})

    old_protocol = json.loads(UPSTREAM_PROTOCOL.read_text(encoding="utf-8"))
    old_protocol["fixed_snapshot"] = {
        "sha256": SNAPSHOT,
        "provisional_first960_runs": run_count,
        "eligible_endpoints": len(rows),
        "tasks": task_count,
        "closure_provided": False,
    }
    old_protocol["hard_integrity_gates"].update({
        "minimum_parent_present_endpoint_fraction": 0.0,
        "minimum_observed_unique_edges": 1,
        "minimum_physical_runs_with_observed_edges": 1,
        "minimum_tasks_with_observed_edges": 1,
    })
    old_protocol["materiality_thresholds"].update({
        "minimum_duplicate_branch_occurrence_fraction": 0.0,
        "minimum_unique_to_linearized_task_total_variation": 0.0,
        "minimum_unique_to_linearized_run_total_variation": 0.0,
    })
    old_protocol_path = tmp_path / "old_protocol.json"
    write_json(old_protocol_path, old_protocol)
    upstream = upstream_producer.build_receipt(
        state, snapshot, old_protocol_path, sha(old_protocol_path), COMMIT
    )
    assert upstream["classification"] == "MULTI_AXIS_MATERIAL_LINEARIZATION_REWEIGHTING"

    repo = tmp_path / "repo"
    upstream_path = repo / "upstream.json"
    upstream_source = repo / "upstream.py"
    estimand_path = repo / "estimand.json"
    write_json(upstream_path, upstream)
    upstream_source.parent.mkdir(parents=True, exist_ok=True)
    upstream_source.write_text("# synthetic upstream source\n", encoding="utf-8", newline="\n")
    write_json(
        estimand_path,
        {
            "protocol": "decision-predictor-estimand-panel-v1",
            "status": "FROZEN_OUTCOME_BLIND_BEFORE_FIRST960_CLOSURE",
        },
    )

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    contract["fixed_snapshot"] = {
        "sha256": SNAPSHOT,
        "provisional_first960_runs": run_count,
        "eligible_endpoints": len(rows),
        "tasks": task_count,
        "closure_provided": False,
    }
    contract["upstream_bindings"] = {
        "linearization_receipt": {
            "path": "upstream.json",
            "sha256": sha(upstream_path),
            "required_classification": "MULTI_AXIS_MATERIAL_LINEARIZATION_REWEIGHTING",
        },
        "linearization_producer": {
            "path": "upstream.py",
            "sha256": sha(upstream_source),
        },
        "predictor_estimand_panel": {
            "path": "estimand.json",
            "sha256": sha(estimand_path),
            "remains_authoritative": True,
        },
    }
    contract_path = tmp_path / "contract.json"
    write_json(contract_path, contract)
    return {
        "state": state,
        "snapshot": snapshot,
        "repo": repo,
        "contract": contract_path,
        "contract_sha": sha(contract_path),
    }


def build(fixture: dict) -> dict:
    return producer.build_receipt(
        fixture["state"],
        fixture["snapshot"],
        fixture["contract"],
        fixture["contract_sha"],
        fixture["repo"],
        COMMIT,
    )


def test_shared_prefix_recovered_exactly(tmp_path: Path) -> None:
    receipt = build(make_fixture(tmp_path, fork_rows()))
    assert receipt["classification"] == producer.PASS
    assert receipt["inventory"]["observed_unique_edges"] == 3
    assert receipt["path_compatibility"]["path_records"] == 2
    assert receipt["path_compatibility"]["edge_occurrences"] == 4
    assert receipt["path_compatibility"]["edge_multiplicity_histogram"] == {"1": 2, "2": 1}
    assert receipt["exact_recovery"]["recovered_total_edge_mass"] == {
        "numerator": 3,
        "denominator": 1,
    }
    assert receipt["all_verification_gates_passed"] is True


def test_internal_occurrence_weights_are_exact_fractions() -> None:
    cards = {
        row["card_id"]: {
            "task": row["task"],
            "run": row["run_id"],
            "parent": row["lineage"]["parent"],
            "depth": row["lineage"]["depth"],
        }
        for row in fork_rows()
    }
    views = producer.construct_internal_views(cards)
    masses = [row["mass"] for row in views["edge_occurrences"] if row["edge_id"] == "b"]
    assert masses == [Fraction(1, 2), Fraction(1, 2)]
    assert sum(masses) == 1


def test_single_node_fragment_is_retained_without_edge_occurrence(tmp_path: Path) -> None:
    rows = fork_rows() + [card("solo", "run-2", "task-b", "missing", 1)]
    receipt = build(make_fixture(tmp_path, rows))
    assert receipt["inventory"]["observed_fragments"] == 2
    assert receipt["inventory"]["single_node_fragments"] == 1
    assert receipt["path_compatibility"]["path_records"] == 3
    assert receipt["path_compatibility"]["single_node_paths_retained"] == 1
    assert receipt["path_compatibility"]["edge_occurrences"] == 4


def test_observed_sibling_groups_are_separate_from_complete_choice_claim(tmp_path: Path) -> None:
    receipt = build(make_fixture(tmp_path, fork_rows()))
    assert receipt["inventory"]["observed_sibling_groups"] == 2
    assert receipt["inventory"]["multi_child_observed_sibling_groups"] == 1
    assert receipt["inventory"]["maximum_observed_sibling_group_size"] == 2
    assert receipt["claim_boundary"]["complete_source_tree_or_choice_set_proven"] is False


def test_independent_verifier_matches_without_importing_producer(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path, fork_rows())
    receipt = build(fixture)
    receipt_path = tmp_path / "receipt.json"
    write_json(receipt_path, receipt)
    result = verifier.verify(
        fixture["state"],
        fixture["snapshot"],
        fixture["contract"],
        fixture["contract_sha"],
        fixture["repo"],
        receipt_path,
        sha(receipt_path),
        PRODUCER_SOURCE,
        sha(PRODUCER_SOURCE),
        COMMIT,
    )
    assert result["status"] == "INDEPENDENT_TREE_NATIVE_PATH_COMPATIBILITY_PASS"
    assert result["security"]["imports_producer"] is False
    assert result["exact_recovery"]["canonical_total_edge_mass"] == 3


def test_verifier_rejects_receipt_tamper(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path, fork_rows())
    receipt = build(fixture)
    receipt["path_compatibility"]["edge_occurrences"] += 1
    receipt_path = tmp_path / "receipt.json"
    write_json(receipt_path, receipt)
    with pytest.raises(verifier.VerificationError, match="independent reconstruction"):
        verifier.verify(
            fixture["state"], fixture["snapshot"], fixture["contract"],
            fixture["contract_sha"], fixture["repo"], receipt_path, sha(receipt_path),
            PRODUCER_SOURCE, sha(PRODUCER_SOURCE), COMMIT,
        )


def test_cross_run_parent_fails_closed(tmp_path: Path) -> None:
    rows = [
        card("a", "run-1", "task-a", "missing", 1),
        card("b", "run-2", "task-a", "a", 2),
    ]
    cards = {
        row["card_id"]: {
            "task": row["task"], "run": row["run_id"],
            "parent": row["lineage"]["parent"], "depth": row["lineage"]["depth"],
        }
        for row in rows
    }
    assert tmp_path.exists()
    with pytest.raises(producer.ContractError, match="crosses physical runs"):
        producer.construct_internal_views(cards)


def test_cycle_fails_closed_before_certificate(tmp_path: Path) -> None:
    rows = [
        card("a", "run-1", "task-a", "b", 1),
        card("b", "run-1", "task-a", "a", 2),
    ]
    state, snapshot = make_state(tmp_path, rows)
    cards = {
        row["card_id"]: {
            "task": row["task"], "run": row["run_id"],
            "parent": row["lineage"]["parent"], "depth": row["lineage"]["depth"],
        }
        for row in rows
    }
    assert state.exists() and snapshot.exists()
    with pytest.raises(producer.ContractError, match="no fragment roots"):
        producer.construct_internal_views(cards)


def test_blind_schema_with_label_fails_closed(tmp_path: Path) -> None:
    rows = fork_rows()
    rows[0] = {**rows[0], "label": 1}
    state, snapshot = make_state(tmp_path, rows)
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    contract["fixed_snapshot"] = {
        "sha256": SNAPSHOT,
        "provisional_first960_runs": 1,
        "eligible_endpoints": 4,
        "tasks": 1,
        "closure_provided": False,
    }
    contract_path = tmp_path / "contract.json"
    write_json(contract_path, contract)
    with pytest.raises(producer.ContractError, match="schema"):
        producer.load_population(state, snapshot, contract)


def test_protocol_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path, fork_rows())
    with pytest.raises(producer.ContractError, match="protocol SHA"):
        producer.build_receipt(
            fixture["state"], fixture["snapshot"], fixture["contract"], "0" * 64,
            fixture["repo"], COMMIT,
        )


def test_upstream_hash_drift_fails_closed(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path, fork_rows())
    (fixture["repo"] / "upstream.json").write_text("{}\n", encoding="utf-8", newline="\n")
    with pytest.raises(producer.ContractError, match="linearization_receipt SHA"):
        build(fixture)


def test_estimand_status_drift_fails_closed(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path, fork_rows())
    contract = json.loads(fixture["contract"].read_text(encoding="utf-8"))
    estimand_path = fixture["repo"] / "estimand.json"
    write_json(
        estimand_path,
        {"protocol": "decision-predictor-estimand-panel-v1", "status": "CHANGED"},
    )
    contract["upstream_bindings"]["predictor_estimand_panel"]["sha256"] = sha(estimand_path)
    write_json(fixture["contract"], contract)
    fixture["contract_sha"] = sha(fixture["contract"])
    with pytest.raises(producer.ContractError, match="estimand binding"):
        build(fixture)


def test_aggregate_receipt_emits_no_identity_or_code(tmp_path: Path) -> None:
    rendered = json.dumps(build(make_fixture(tmp_path, fork_rows())), sort_keys=True)
    for forbidden in ("run-1", "task-a", "missing-root", "print('a')", '"edge_id"', '"path_id"'):
        assert forbidden not in rendered
    assert "identity_code_or_per_path_values_written" in rendered


def test_result_is_byte_deterministic(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path, fork_rows())
    first = build(fixture)
    second = build(fixture)
    assert json.dumps(first, sort_keys=True, separators=(",", ":")) == json.dumps(
        second, sort_keys=True, separators=(",", ":")
    )


def test_verifier_source_does_not_import_producer() -> None:
    source = VERIFIER_SOURCE.read_text(encoding="utf-8")
    assert "import certify_tree_native_path_compatibility" not in source
    assert "from phase1 import certify_tree_native_path_compatibility" not in source
