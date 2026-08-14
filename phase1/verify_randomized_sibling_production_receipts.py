"""Verify outcome-blind scheduler receipts against a frozen sibling assignment.

This module never imports the assignment producer.  It first reconstructs the frozen assignment
through the independent assignment verifier, then checks two external scheduler attestations:

1. complete eligible sets whose SHA-256 lottery reproduces every selected parent and propensity;
2. one committed, slot-for-slot budget transaction bound to every randomized assignment.

Passing this verifier proves internal receipt consistency.  It does not authenticate who produced
the scheduler receipts, execute candidates, read outcomes, or authorize production activation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

from phase1 import verify_randomized_sibling_logging_manifest as assignment_verifier


SELECTION_SCHEMA = "randomized-sibling-selection-batch-v1"
BUDGET_SCHEMA = "randomized-sibling-budget-transaction-v1"
SELECTION_DESIGN = "sha256-top-m-without-replacement"
STATUS = "VERIFIED_RANDOMIZED_SIBLING_PRODUCTION_RECEIPT_CONSISTENCY"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
FORBIDDEN_KEY_FRAGMENTS = (
    "grade",
    "label",
    "score",
    "reward",
    "metric",
    "prediction",
    "stdout",
    "stderr",
    "runtime",
    "self_report",
    "submission",
    "accuracy",
    "loss",
    "timeout",
    "return_code",
    "exit_code",
)
SELECTION_KEYS = {
    "schema_version",
    "created_utc",
    "selection_batch_id",
    "selection_seed",
    "selection_design",
    "policy_contract_sha256",
    "eligible_parents",
    "selected_parent_count",
    "outcome_blind",
}
ELIGIBLE_PARENT_KEYS = {
    "task",
    "physical_run_id",
    "parent_id",
    "generation_started_at_utc",
    "source_sha256",
}
BUDGET_KEYS = {
    "schema_version",
    "created_utc",
    "transaction_id",
    "transaction_state",
    "production_window_id",
    "scheduler_source_commit",
    "policy_contract_sha256",
    "assignment_manifest_sha256",
    "assignment_summary_sha256",
    "ledger_before_total_candidate_execution_slots",
    "ledger_after_standard_candidate_execution_slots",
    "ledger_after_randomized_candidate_execution_slots",
    "ledger_after_total_candidate_execution_slots",
    "slot_bindings",
    "outcome_blind",
}
SLOT_BINDING_KEYS = {
    "displaced_standard_slot_id",
    "randomized_slot_id",
    "assignment_id",
}


class ReceiptVerificationError(RuntimeError):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def safe_read(path: Path) -> bytes:
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise ReceiptVerificationError(f"credential-shaped bytes in {path.name}")
    return raw


def reject_outcome_keys(value: Any, where: str) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise ReceiptVerificationError(f"non-string key in {where}")
            if any(fragment in key.lower() for fragment in FORBIDDEN_KEY_FRAGMENTS):
                raise ReceiptVerificationError(f"outcome-bearing key in {where}")
            reject_outcome_keys(nested, where)
    elif isinstance(value, list):
        for nested in value:
            reject_outcome_keys(nested, where)


def required_text(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReceiptVerificationError(f"{key} must be a non-empty string")
    return value


def required_hash(
    row: dict[str, Any], key: str, pattern: re.Pattern[str] = HEX64
) -> str:
    value = required_text(row, key)
    if not pattern.fullmatch(value):
        raise ReceiptVerificationError(f"invalid {key}")
    return value


def required_nonnegative_int(row: dict[str, Any], key: str) -> int:
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReceiptVerificationError(f"{key} must be a non-negative integer")
    return value


def parse_utc(value: str, key: str) -> dt.datetime:
    if not value.endswith("Z"):
        raise ReceiptVerificationError(f"{key} must have a UTC Z suffix")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ReceiptVerificationError(f"invalid {key}") from exc
    if parsed.tzinfo != dt.timezone.utc:
        raise ReceiptVerificationError(f"{key} must be UTC")
    return parsed


def assignment_state(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    if not root.is_dir():
        raise ReceiptVerificationError("assignment root is not a directory")
    files = {path.name for path in root.iterdir() if path.is_file()}
    if files != assignment_verifier.EXPECTED_FILES:
        raise ReceiptVerificationError("assignment artifact file set mismatch")
    hash_manifest_raw = safe_read(root / "sha256_manifest.json")
    hash_manifest = json.loads(hash_manifest_raw)
    expected_hashed = assignment_verifier.EXPECTED_FILES - {"sha256_manifest.json"}
    if not isinstance(hash_manifest, dict) or set(hash_manifest) != expected_hashed:
        raise ReceiptVerificationError("assignment hash manifest schema mismatch")
    for name in expected_hashed:
        if hash_manifest[name] != digest(safe_read(root / name)):
            raise ReceiptVerificationError(f"assignment artifact hash mismatch: {name}")

    parents_raw = safe_read(root / "parents.input.jsonl")
    config_raw = safe_read(root / "config.input.json")
    parents = assignment_verifier.read_parents(parents_raw)
    config = assignment_verifier.read_config(config_raw, {row["task"] for row in parents})
    for row in parents:
        if row["operator_contract_sha256"] != config["operator_contract_sha256"]:
            raise ReceiptVerificationError("assignment operator contract mismatch")
        if row["evaluator_contract_sha256"] != config["evaluator_contract_sha256"]:
            raise ReceiptVerificationError("assignment evaluator contract mismatch")
    assignments, task_support = assignment_verifier.independently_rebuild(parents, config)
    expected_assignment_bytes = "".join(
        assignment_verifier.canonical(row) + "\n" for row in assignments
    ).encode("utf-8")
    if safe_read(root / "assignment_manifest.jsonl") != expected_assignment_bytes:
        raise ReceiptVerificationError("assignment bytes fail independent reconstruction")

    planned_slots = len(assignments)
    displaced_slots = sum(row["displaced_candidate_execution_slots"] for row in parents)
    unique_codes = {sibling["code_sha256"] for row in parents for sibling in row["siblings"]}
    expected_summary = {
        "protocol": assignment_verifier.PROTOCOL,
        "status": assignment_verifier.STATUS,
        "created_utc": config["created_utc"],
        "contains_outcomes": False,
        "outcomes_read": False,
        "parents_input_sha256": digest(parents_raw),
        "config_input_sha256": digest(config_raw),
        "source_commit": config["source_commit"],
        "seed": config["seed"],
        "policy_contract_sha256": config["policy_contract_sha256"],
        "operator_contract_sha256": config["operator_contract_sha256"],
        "evaluator_contract_sha256": config["evaluator_contract_sha256"],
        "task_count": len({row["task"] for row in parents}),
        "parent_count": len(parents),
        "sibling_count": 2 * len(parents),
        "unique_sibling_code_sha256_count": len(unique_codes),
        "calibration_parent_count": sum(config["calibration_parents_per_task"].values()),
        "rollout_jobs": planned_slots,
        "planned_candidate_execution_slots": planned_slots,
        "displaced_candidate_execution_slots": displaced_slots,
        "declared_slot_ledger_matches_plan": True,
        "actual_production_budget_decrement_verified": False,
        "upstream_selection_probability_verified_by_assignment": False,
        "budget_conservation_basis": "input-declared-displaced-slots-equal-planned-slots",
        "continuation_horizon": 1,
        "retry_count": 0,
        "fresh_workspace_required": True,
        "adaptive_allocation_allowed": False,
        "task_support": task_support,
    }
    if json.loads(safe_read(root / "summary.json")) != expected_summary:
        raise ReceiptVerificationError("assignment summary fails independent reconstruction")
    return parents, config, assignments


def parent_identity(row: dict[str, Any]) -> tuple[str, str]:
    return row["physical_run_id"], row["parent_id"]


def eligible_parent(value: Any, receipt_created: dt.datetime) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != ELIGIBLE_PARENT_KEYS:
        raise ReceiptVerificationError("eligible parent schema mismatch")
    row = {
        "task": required_text(value, "task"),
        "physical_run_id": required_text(value, "physical_run_id"),
        "parent_id": required_text(value, "parent_id"),
        "generation_started_at_utc": required_text(value, "generation_started_at_utc"),
        "source_sha256": required_hash(value, "source_sha256"),
    }
    generated = parse_utc(row["generation_started_at_utc"], "generation_started_at_utc")
    if generated > receipt_created:
        raise ReceiptVerificationError("selection receipt predates an eligible parent")
    return row


def selection_order_key(seed: int, batch_id: str, row: dict[str, Any]) -> str:
    material = "|".join(
        (
            SELECTION_SCHEMA,
            str(seed),
            batch_id,
            row["task"],
            row["physical_run_id"],
            row["parent_id"],
            row["source_sha256"],
        )
    ).encode("utf-8")
    return digest(material)


def verify_selection_receipts(
    path: Path, parents: list[dict[str, Any]], policy_sha256: str
) -> tuple[list[dict[str, Any]], int]:
    raw = safe_read(path)
    if not raw or not raw.endswith(b"\n"):
        raise ReceiptVerificationError("selection receipt JSONL must be non-empty and newline-terminated")
    parent_map = {parent_identity(row): row for row in parents}
    selected_map: dict[tuple[str, str], tuple[str, float, dict[str, Any]]] = {}
    seen_eligible: set[tuple[str, str]] = set()
    seen_batch_ids: set[str] = set()
    receipts: list[dict[str, Any]] = []
    eligible_total = 0

    for line_no, encoded_line in enumerate(raw.splitlines(keepends=True), 1):
        if encoded_line == b"\n":
            raise ReceiptVerificationError("blank selection receipt line")
        try:
            value = json.loads(encoded_line)
        except json.JSONDecodeError as exc:
            raise ReceiptVerificationError(f"invalid selection JSON at line {line_no}") from exc
        reject_outcome_keys(value, f"selection line {line_no}")
        if not isinstance(value, dict) or set(value) != SELECTION_KEYS:
            raise ReceiptVerificationError("selection receipt schema mismatch")
        if value.get("schema_version") != SELECTION_SCHEMA:
            raise ReceiptVerificationError("selection schema version mismatch")
        if value.get("selection_design") != SELECTION_DESIGN:
            raise ReceiptVerificationError("unsupported selection design")
        if value.get("outcome_blind") is not True:
            raise ReceiptVerificationError("selection receipt must be outcome blind")
        created_text = required_text(value, "created_utc")
        created = parse_utc(created_text, "selection created_utc")
        batch_id = required_text(value, "selection_batch_id")
        if batch_id in seen_batch_ids:
            raise ReceiptVerificationError("duplicate selection batch ID")
        seen_batch_ids.add(batch_id)
        seed = required_nonnegative_int(value, "selection_seed")
        if required_hash(value, "policy_contract_sha256") != policy_sha256:
            raise ReceiptVerificationError("selection policy contract mismatch")
        raw_eligible = value.get("eligible_parents")
        if not isinstance(raw_eligible, list) or not raw_eligible:
            raise ReceiptVerificationError("selection eligible set must be non-empty")
        eligible = [eligible_parent(row, created) for row in raw_eligible]
        keys = [parent_identity(row) for row in eligible]
        if len(keys) != len(set(keys)):
            raise ReceiptVerificationError("duplicate parent inside selection eligible set")
        overlap = seen_eligible.intersection(keys)
        if overlap:
            raise ReceiptVerificationError("eligible parent appears in multiple selection batches")
        seen_eligible.update(keys)
        selected_count = required_nonnegative_int(value, "selected_parent_count")
        if selected_count == 0 or selected_count > len(eligible):
            raise ReceiptVerificationError("selected parent count is outside eligible support")
        canonical_line = (canonical(value) + "\n").encode("utf-8")
        if encoded_line != canonical_line:
            raise ReceiptVerificationError("selection receipt line is not canonical JSON")
        receipt_sha256 = digest(canonical_line)
        ordered = sorted(eligible, key=lambda row: selection_order_key(seed, batch_id, row))
        probability = selected_count / len(eligible)
        for row in ordered[:selected_count]:
            key = parent_identity(row)
            if key in selected_map:
                raise ReceiptVerificationError("parent selected more than once")
            selected_map[key] = (receipt_sha256, probability, row)
        receipts.append(
            {
                "receipt_sha256": receipt_sha256,
                "created": created,
                "eligible_count": len(eligible),
                "selected_count": selected_count,
            }
        )
        eligible_total += len(eligible)

    if set(selected_map) != set(parent_map):
        raise ReceiptVerificationError("selected parents do not exactly equal assignment parents")
    for key, parent in parent_map.items():
        receipt_sha256, probability, eligible = selected_map[key]
        if parent["upstream_selection_receipt_sha256"] != receipt_sha256:
            raise ReceiptVerificationError("parent selection receipt hash mismatch")
        if not math.isclose(
            parent["upstream_selection_probability_attested"],
            probability,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise ReceiptVerificationError("parent selection probability mismatch")
        for field in ELIGIBLE_PARENT_KEYS:
            if parent[field] != eligible[field]:
                raise ReceiptVerificationError("selected parent identity does not match assignment")
    return receipts, eligible_total


def verify_budget_receipt(
    path: Path,
    root: Path,
    config: dict[str, Any],
    assignments: list[dict[str, Any]],
    latest_selection_time: dt.datetime,
) -> dict[str, Any]:
    raw = safe_read(path)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReceiptVerificationError("invalid budget receipt JSON") from exc
    reject_outcome_keys(value, "budget receipt")
    if not isinstance(value, dict) or set(value) != BUDGET_KEYS:
        raise ReceiptVerificationError("budget receipt schema mismatch")
    if raw != (canonical(value) + "\n").encode("utf-8"):
        raise ReceiptVerificationError("budget receipt is not canonical JSON")
    if value.get("schema_version") != BUDGET_SCHEMA:
        raise ReceiptVerificationError("budget schema version mismatch")
    if value.get("transaction_state") != "committed":
        raise ReceiptVerificationError("budget transaction is not committed")
    if value.get("outcome_blind") is not True:
        raise ReceiptVerificationError("budget receipt must be outcome blind")
    created = parse_utc(required_text(value, "created_utc"), "budget created_utc")
    if created < latest_selection_time:
        raise ReceiptVerificationError("budget transaction predates selection receipt")
    required_text(value, "transaction_id")
    required_text(value, "production_window_id")
    required_hash(value, "scheduler_source_commit", HEX40)
    if required_hash(value, "policy_contract_sha256") != config["policy_contract_sha256"]:
        raise ReceiptVerificationError("budget policy contract mismatch")
    if required_hash(value, "assignment_manifest_sha256") != digest(
        safe_read(root / "assignment_manifest.jsonl")
    ):
        raise ReceiptVerificationError("budget assignment manifest hash mismatch")
    if required_hash(value, "assignment_summary_sha256") != digest(
        safe_read(root / "summary.json")
    ):
        raise ReceiptVerificationError("budget assignment summary hash mismatch")

    before = required_nonnegative_int(value, "ledger_before_total_candidate_execution_slots")
    standard_after = required_nonnegative_int(
        value, "ledger_after_standard_candidate_execution_slots"
    )
    randomized_after = required_nonnegative_int(
        value, "ledger_after_randomized_candidate_execution_slots"
    )
    total_after = required_nonnegative_int(
        value, "ledger_after_total_candidate_execution_slots"
    )
    expected_ids = {row["assignment_id"] for row in assignments}
    bindings = value.get("slot_bindings")
    if not isinstance(bindings, list) or len(bindings) != len(assignments):
        raise ReceiptVerificationError("budget slot binding count mismatch")
    displaced: set[str] = set()
    randomized: set[str] = set()
    bound_assignment_ids: set[str] = set()
    for binding in bindings:
        if not isinstance(binding, dict) or set(binding) != SLOT_BINDING_KEYS:
            raise ReceiptVerificationError("budget slot binding schema mismatch")
        displaced_id = required_text(binding, "displaced_standard_slot_id")
        randomized_id = required_text(binding, "randomized_slot_id")
        assignment_id = required_hash(binding, "assignment_id")
        if displaced_id in displaced or randomized_id in randomized:
            raise ReceiptVerificationError("duplicate slot identity in budget transaction")
        if assignment_id in bound_assignment_ids:
            raise ReceiptVerificationError("duplicate assignment in budget transaction")
        displaced.add(displaced_id)
        randomized.add(randomized_id)
        bound_assignment_ids.add(assignment_id)
    if bound_assignment_ids != expected_ids:
        raise ReceiptVerificationError("budget transaction does not bind the exact assignment set")
    slots = len(assignments)
    if before < slots or before - standard_after != slots:
        raise ReceiptVerificationError("standard production budget decrement mismatch")
    if randomized_after != slots:
        raise ReceiptVerificationError("randomized budget reservation mismatch")
    if total_after != standard_after + randomized_after or total_after != before:
        raise ReceiptVerificationError("total candidate budget is not conserved")
    return {
        "receipt_sha256": digest(raw),
        "created": created,
        "before": before,
        "standard_after": standard_after,
        "randomized_after": randomized_after,
        "total_after": total_after,
    }


def verify(args: argparse.Namespace) -> int:
    root = Path(args.assignment_root).resolve()
    selection_path = Path(args.selection_receipts).resolve()
    budget_path = Path(args.budget_receipt).resolve()
    output = Path(args.receipt).resolve()
    temporary = output.with_name(output.name + f".tmp-{os.getpid()}")
    if output.exists() or temporary.exists():
        raise ReceiptVerificationError("output receipt path must not pre-exist")

    parents, config, assignments = assignment_state(root)
    selection_receipts, eligible_total = verify_selection_receipts(
        selection_path, parents, config["policy_contract_sha256"]
    )
    latest_selection_time = max(row["created"] for row in selection_receipts)
    budget = verify_budget_receipt(
        budget_path, root, config, assignments, latest_selection_time
    )
    summary = {
        "status": STATUS,
        "producer_imported": False,
        "assignment_sha256_manifest": digest(safe_read(root / "sha256_manifest.json")),
        "selection_receipts_sha256": digest(safe_read(selection_path)),
        "budget_receipt_sha256": budget["receipt_sha256"],
        "selection_batch_count": len(selection_receipts),
        "eligible_parent_count": eligible_total,
        "selected_parent_count": len(parents),
        "rollout_jobs": len(assignments),
        "planned_candidate_execution_slots": len(assignments),
        "upstream_selection_probability_reconstructed_from_declared_eligible_sets": True,
        "committed_budget_decrement_internally_consistent": True,
        "budget_conserved_within_receipt": True,
        "upstream_selection_probability_verified_by_assignment": False,
        "actual_production_budget_decrement_verified": False,
        "contains_outcomes": False,
        "outcomes_read": False,
        "eligible_stream_completeness_verified": False,
        "external_scheduler_receipt_authenticity_verified": False,
        "production_activation_authorized": False,
        "causal_claim_allowed": False,
        "verification_scope": "internal-consistency-of-external-scheduler-receipts",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(output)
    print(canonical(summary))
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--assignment-root", required=True)
    result.add_argument("--selection-receipts", required=True)
    result.add_argument("--budget-receipt", required=True)
    result.add_argument("--receipt", required=True)
    return result


def main() -> int:
    try:
        return verify(parser().parse_args())
    except (ReceiptVerificationError, OSError, json.JSONDecodeError) as exc:
        print(f"PRODUCTION_RECEIPT_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
