from __future__ import annotations

import argparse
import builtins
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import randomized_sibling_logging_manifest as producer
from phase1 import verify_randomized_sibling_production_receipts as receipt_verifier


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_json(path: Path, value: object, *, canonical: bool = False) -> None:
    if canonical:
        text = receipt_verifier.canonical(value) + "\n"
    else:
        text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def eligible_row(task: str, index: int) -> dict:
    marker = f"{task}-{index}"
    return {
        "task": task,
        "physical_run_id": f"run-{marker}",
        "parent_id": f"parent-{marker}",
        "generation_started_at_utc": f"2026-08-14T12:0{index}:00Z",
        "source_sha256": sha(f"source-{marker}"),
    }


def selection_batch(task: str, seed: int) -> dict:
    return {
        "schema_version": receipt_verifier.SELECTION_SCHEMA,
        "created_utc": "2026-08-14T13:00:00Z",
        "selection_batch_id": f"batch-{task}",
        "selection_seed": seed,
        "selection_design": receipt_verifier.SELECTION_DESIGN,
        "policy_contract_sha256": "b" * 64,
        "eligible_parents": [eligible_row(task, index) for index in range(4)],
        "selected_parent_count": 3,
        "outcome_blind": True,
    }


def selected_rows(batch: dict) -> list[dict]:
    return sorted(
        batch["eligible_parents"],
        key=lambda row: receipt_verifier.selection_order_key(
            batch["selection_seed"], batch["selection_batch_id"], row
        ),
    )[: batch["selected_parent_count"]]


def parent_row(row: dict, receipt_sha256: str, probability: float) -> dict:
    marker = f"{row['physical_run_id']}-{row['parent_id']}"
    return {
        "schema_version": producer.PARENT_SCHEMA,
        **row,
        "operator_contract_sha256": "c" * 64,
        "evaluator_contract_sha256": "d" * 64,
        "sibling_ids": [f"sibling-{marker}-a", f"sibling-{marker}-b"],
        "sibling_code_sha256": [sha(f"code-{marker}-a"), sha(f"code-{marker}-b")],
        "source_sibling_receipt_sha256": [
            sha(f"source-receipt-{marker}-a"),
            sha(f"source-receipt-{marker}-b"),
        ],
        "upstream_selection_probability_attested": probability,
        "upstream_selection_receipt_sha256": receipt_sha256,
        "displaced_candidate_execution_slots": 2,
    }


def base_config() -> dict:
    return {
        "schema_version": producer.CONFIG_SCHEMA,
        "created_utc": "2026-08-14T13:30:00Z",
        "source_commit": "a" * 40,
        "seed": 20260814,
        "continuation_horizon": 1,
        "execution_timeout_seconds": 600,
        "policy_contract_sha256": "b" * 64,
        "operator_contract_sha256": "c" * 64,
        "evaluator_contract_sha256": "d" * 64,
        "calibration_parents_per_task": {"task-a": 1, "task-b": 1},
        "workspace_policy": "fresh_per_rollout",
        "retry_count": 0,
        "adaptive_allocation_allowed": False,
    }


def fixture(
    tmp_path: Path, *, attested_probability: float = 0.75
) -> tuple[Path, Path, Path, Path, list[dict], dict]:
    batches = [selection_batch("task-a", 101), selection_batch("task-b", 202)]
    selection_path = tmp_path / "selection_receipts.jsonl"
    selection_path.write_text(
        "".join(receipt_verifier.canonical(batch) + "\n" for batch in batches),
        encoding="utf-8",
        newline="\n",
    )
    parents: list[dict] = []
    for batch in batches:
        receipt_sha256 = sha(receipt_verifier.canonical(batch) + "\n")
        parents.extend(
            parent_row(row, receipt_sha256, attested_probability)
            for row in selected_rows(batch)
        )
    config = base_config()
    for task in ("task-a", "task-b"):
        task_rows = [row for row in parents if row["task"] == task]
        calibration = sorted(
            task_rows,
            key=lambda row: producer.hash_order(
                config["seed"],
                "calibration",
                task,
                row["physical_run_id"],
                row["parent_id"],
            ),
        )[0]
        calibration["displaced_candidate_execution_slots"] = 4

    parents_path = tmp_path / "parents.jsonl"
    parents_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in parents),
        encoding="utf-8",
        newline="\n",
    )
    config_path = tmp_path / "config.json"
    write_json(config_path, config)
    assignment_root = tmp_path / "assignment"
    assert producer.build(
        argparse.Namespace(
            parents=str(parents_path), config=str(config_path), output=str(assignment_root)
        )
    ) == 0

    assignments = [
        json.loads(line)
        for line in (assignment_root / "assignment_manifest.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    budget = {
        "schema_version": receipt_verifier.BUDGET_SCHEMA,
        "created_utc": "2026-08-14T14:00:00Z",
        "transaction_id": "transaction-001",
        "transaction_state": "committed",
        "production_window_id": "window-001",
        "scheduler_source_commit": "e" * 40,
        "policy_contract_sha256": config["policy_contract_sha256"],
        "assignment_manifest_sha256": hashlib.sha256(
            (assignment_root / "assignment_manifest.jsonl").read_bytes()
        ).hexdigest(),
        "assignment_summary_sha256": hashlib.sha256(
            (assignment_root / "summary.json").read_bytes()
        ).hexdigest(),
        "ledger_before_total_candidate_execution_slots": 40,
        "ledger_after_standard_candidate_execution_slots": 40 - len(assignments),
        "ledger_after_randomized_candidate_execution_slots": len(assignments),
        "ledger_after_total_candidate_execution_slots": 40,
        "slot_bindings": [
            {
                "displaced_standard_slot_id": f"standard-slot-{index:03d}",
                "randomized_slot_id": f"randomized-slot-{index:03d}",
                "assignment_id": row["assignment_id"],
            }
            for index, row in enumerate(assignments)
        ],
        "outcome_blind": True,
    }
    budget_path = tmp_path / "budget_receipt.json"
    write_json(budget_path, budget, canonical=True)
    return assignment_root, selection_path, budget_path, tmp_path / "verified.json", batches, budget


def run_verifier(
    assignment_root: Path, selection_path: Path, budget_path: Path, receipt_path: Path
) -> int:
    return receipt_verifier.verify(
        argparse.Namespace(
            assignment_root=str(assignment_root),
            selection_receipts=str(selection_path),
            budget_receipt=str(budget_path),
            receipt=str(receipt_path),
        )
    )


def test_exact_selection_and_budget_receipts_verify_but_do_not_authorize(tmp_path: Path) -> None:
    assignment_root, selection_path, budget_path, receipt_path, _, _ = fixture(tmp_path)
    assert run_verifier(assignment_root, selection_path, budget_path, receipt_path) == 0
    result = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert result["status"] == receipt_verifier.STATUS
    assert result["selection_batch_count"] == 2
    assert result["eligible_parent_count"] == 8
    assert result["selected_parent_count"] == 6
    assert result["rollout_jobs"] == 16
    assert result["upstream_selection_probability_reconstructed_from_declared_eligible_sets"] is True
    assert result["committed_budget_decrement_internally_consistent"] is True
    assert result["budget_conserved_within_receipt"] is True
    assert result["upstream_selection_probability_verified_by_assignment"] is False
    assert result["actual_production_budget_decrement_verified"] is False
    assert result["contains_outcomes"] is False
    assert result["eligible_stream_completeness_verified"] is False
    assert result["external_scheduler_receipt_authenticity_verified"] is False
    assert result["production_activation_authorized"] is False
    assert result["causal_claim_allowed"] is False


def test_attested_probability_must_match_reconstructed_lottery(tmp_path: Path) -> None:
    assignment_root, selection_path, budget_path, receipt_path, _, _ = fixture(
        tmp_path, attested_probability=0.5
    )
    with pytest.raises(receipt_verifier.ReceiptVerificationError, match="probability mismatch"):
        run_verifier(assignment_root, selection_path, budget_path, receipt_path)


def test_selected_parent_set_must_exactly_match_assignment(tmp_path: Path) -> None:
    assignment_root, selection_path, budget_path, receipt_path, batches, _ = fixture(tmp_path)
    selection_path.write_text(
        receipt_verifier.canonical(batches[0]) + "\n", encoding="utf-8", newline="\n"
    )
    with pytest.raises(receipt_verifier.ReceiptVerificationError, match="exactly equal"):
        run_verifier(assignment_root, selection_path, budget_path, receipt_path)


def test_budget_must_conserve_total_slots(tmp_path: Path) -> None:
    assignment_root, selection_path, budget_path, receipt_path, _, budget = fixture(tmp_path)
    budget["ledger_after_total_candidate_execution_slots"] -= 1
    write_json(budget_path, budget, canonical=True)
    with pytest.raises(receipt_verifier.ReceiptVerificationError, match="not conserved"):
        run_verifier(assignment_root, selection_path, budget_path, receipt_path)


def test_budget_rejects_duplicate_displaced_slot(tmp_path: Path) -> None:
    assignment_root, selection_path, budget_path, receipt_path, _, budget = fixture(tmp_path)
    budget["slot_bindings"][1]["displaced_standard_slot_id"] = budget["slot_bindings"][0][
        "displaced_standard_slot_id"
    ]
    write_json(budget_path, budget, canonical=True)
    with pytest.raises(receipt_verifier.ReceiptVerificationError, match="duplicate slot"):
        run_verifier(assignment_root, selection_path, budget_path, receipt_path)


def test_budget_rejects_assignment_substitution(tmp_path: Path) -> None:
    assignment_root, selection_path, budget_path, receipt_path, _, budget = fixture(tmp_path)
    budget["slot_bindings"][0]["assignment_id"] = "f" * 64
    write_json(budget_path, budget, canonical=True)
    with pytest.raises(receipt_verifier.ReceiptVerificationError, match="exact assignment set"):
        run_verifier(assignment_root, selection_path, budget_path, receipt_path)


def test_outcome_key_is_rejected_before_budget_schema_check(tmp_path: Path) -> None:
    assignment_root, selection_path, budget_path, receipt_path, _, budget = fixture(tmp_path)
    budget["score"] = 0.9
    write_json(budget_path, budget, canonical=True)
    with pytest.raises(receipt_verifier.ReceiptVerificationError, match="outcome-bearing key"):
        run_verifier(assignment_root, selection_path, budget_path, receipt_path)


def test_noncanonical_selection_receipt_is_rejected(tmp_path: Path) -> None:
    assignment_root, selection_path, budget_path, receipt_path, batches, _ = fixture(tmp_path)
    selection_path.write_text(
        json.dumps(batches[0], sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    with pytest.raises(receipt_verifier.ReceiptVerificationError, match="not canonical JSON"):
        run_verifier(assignment_root, selection_path, budget_path, receipt_path)


def test_selection_receipt_cannot_predate_eligible_parent(tmp_path: Path) -> None:
    assignment_root, selection_path, budget_path, receipt_path, batches, _ = fixture(tmp_path)
    batches[0]["created_utc"] = "2026-08-14T11:00:00Z"
    selection_path.write_text(
        "".join(receipt_verifier.canonical(batch) + "\n" for batch in batches),
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(receipt_verifier.ReceiptVerificationError, match="predates an eligible"):
        run_verifier(assignment_root, selection_path, budget_path, receipt_path)


def test_budget_transaction_must_be_committed(tmp_path: Path) -> None:
    assignment_root, selection_path, budget_path, receipt_path, _, budget = fixture(tmp_path)
    budget["transaction_state"] = "prepared"
    write_json(budget_path, budget, canonical=True)
    with pytest.raises(receipt_verifier.ReceiptVerificationError, match="not committed"):
        run_verifier(assignment_root, selection_path, budget_path, receipt_path)


def test_credential_shape_is_rejected_before_budget_parse(tmp_path: Path) -> None:
    assignment_root, selection_path, budget_path, receipt_path, _, _ = fixture(tmp_path)
    budget_path.write_bytes(b"not-json sk-" + b"A" * 20 + b"\n")
    with pytest.raises(receipt_verifier.ReceiptVerificationError, match="credential-shaped"):
        run_verifier(assignment_root, selection_path, budget_path, receipt_path)


def test_verifier_does_not_import_assignment_producer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assignment_root, selection_path, budget_path, receipt_path, _, _ = fixture(tmp_path)
    original_import = builtins.__import__

    def guarded_import(name: str, *args, **kwargs):
        if name.endswith("randomized_sibling_logging_manifest") and not name.endswith(
            "verify_randomized_sibling_logging_manifest"
        ):
            raise AssertionError("production receipt verifier imported assignment producer")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    assert run_verifier(assignment_root, selection_path, budget_path, receipt_path) == 0
