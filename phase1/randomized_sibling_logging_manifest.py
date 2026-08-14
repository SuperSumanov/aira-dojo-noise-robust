"""Freeze an outcome-blind, budget-conserving randomized sibling schedule.

The producer accepts identities and hashes only.  It does not accept code, labels, scores,
execution output, or an outcome path.  Real execution is a separate, explicitly gated step.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


PROTOCOL = "randomized-sibling-logging-v1"
STATUS = "OUTCOME_BLIND_RANDOMIZED_ASSIGNMENT_FROZEN"
PARENT_SCHEMA = "randomized-sibling-parent-v1"
CONFIG_SCHEMA = "randomized-sibling-config-v1"
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
    "runtime",
    "self_report",
)
PARENT_KEYS = {
    "schema_version",
    "task",
    "physical_run_id",
    "parent_id",
    "generation_started_at_utc",
    "source_sha256",
    "operator_contract_sha256",
    "evaluator_contract_sha256",
    "sibling_ids",
    "sibling_code_sha256",
    "source_sibling_receipt_sha256",
    "upstream_selection_probability_attested",
    "upstream_selection_receipt_sha256",
    "displaced_candidate_execution_slots",
}
CONFIG_KEYS = {
    "schema_version",
    "created_utc",
    "source_commit",
    "seed",
    "continuation_horizon",
    "execution_timeout_seconds",
    "policy_contract_sha256",
    "operator_contract_sha256",
    "evaluator_contract_sha256",
    "calibration_parents_per_task",
    "workspace_policy",
    "retry_count",
    "adaptive_allocation_allowed",
}


class AssignmentError(RuntimeError):
    pass


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def checked_bytes(path: Path) -> bytes:
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise AssignmentError(f"credential-shaped bytes refused before parsing: {path.name}")
    return raw


def reject_forbidden_keys(value: Any, where: str) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise AssignmentError(f"non-string key in {where}")
            lowered = key.lower()
            if any(fragment in lowered for fragment in FORBIDDEN_KEY_FRAGMENTS):
                raise AssignmentError(f"forbidden outcome-bearing key in {where}")
            reject_forbidden_keys(nested, where)
    elif isinstance(value, list):
        for nested in value:
            reject_forbidden_keys(nested, where)


def require_string(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AssignmentError(f"{key} must be a non-empty string")
    return value


def require_hash(row: dict[str, Any], key: str, pattern: re.Pattern[str] = HEX64) -> str:
    value = require_string(row, key)
    if not pattern.fullmatch(value):
        raise AssignmentError(f"invalid {key}")
    return value


def parse_utc(value: str, key: str) -> str:
    if not value.endswith("Z"):
        raise AssignmentError(f"{key} must be UTC with Z suffix")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise AssignmentError(f"invalid {key}") from exc
    if parsed.tzinfo != dt.timezone.utc:
        raise AssignmentError(f"{key} must be UTC")
    return value


def parse_string_pair(row: dict[str, Any], key: str, *, hashes: bool) -> tuple[str, str]:
    value = row.get(key)
    if not isinstance(value, list) or len(value) != 2:
        raise AssignmentError(f"{key} must contain exactly two values")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise AssignmentError(f"{key} values must be non-empty strings")
    if value[0] == value[1]:
        raise AssignmentError(f"{key} values must be distinct")
    if hashes and any(not HEX64.fullmatch(item) for item in value):
        raise AssignmentError(f"{key} values must be SHA-256")
    return value[0], value[1]


def parse_parents(raw: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    parent_keys: set[tuple[str, str]] = set()
    sibling_ids: set[str] = set()
    for line_no, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AssignmentError(f"invalid parent JSON at line {line_no}") from exc
        reject_forbidden_keys(value, f"parent line {line_no}")
        if not isinstance(value, dict) or set(value) != PARENT_KEYS:
            raise AssignmentError(f"parent line {line_no} schema mismatch")
        if value.get("schema_version") != PARENT_SCHEMA:
            raise AssignmentError(f"parent line {line_no} schema version mismatch")
        row: dict[str, Any] = {
            "schema_version": PARENT_SCHEMA,
            "task": require_string(value, "task"),
            "physical_run_id": require_string(value, "physical_run_id"),
            "parent_id": require_string(value, "parent_id"),
            "generation_started_at_utc": parse_utc(
                require_string(value, "generation_started_at_utc"),
                "generation_started_at_utc",
            ),
            "source_sha256": require_hash(value, "source_sha256"),
            "operator_contract_sha256": require_hash(value, "operator_contract_sha256"),
            "evaluator_contract_sha256": require_hash(value, "evaluator_contract_sha256"),
            "upstream_selection_receipt_sha256": require_hash(
                value, "upstream_selection_receipt_sha256"
            ),
        }
        ids = parse_string_pair(value, "sibling_ids", hashes=False)
        codes = parse_string_pair(value, "sibling_code_sha256", hashes=True)
        receipts = parse_string_pair(value, "source_sibling_receipt_sha256", hashes=True)
        sibling_triples = sorted(zip(ids, codes, receipts), key=lambda item: item[0])
        row["siblings"] = [
            {"sibling_id": sibling_id, "code_sha256": code_sha, "receipt_sha256": receipt_sha}
            for sibling_id, code_sha, receipt_sha in sibling_triples
        ]
        probability = value.get("upstream_selection_probability_attested")
        if (
            isinstance(probability, bool)
            or not isinstance(probability, (int, float))
            or not math.isfinite(float(probability))
            or not 0 < float(probability) <= 1
        ):
            raise AssignmentError(
                "upstream_selection_probability_attested must be finite in (0,1]"
            )
        row["upstream_selection_probability_attested"] = float(probability)
        slots = value.get("displaced_candidate_execution_slots")
        if isinstance(slots, bool) or not isinstance(slots, int) or slots <= 0:
            raise AssignmentError("displaced_candidate_execution_slots must be a positive integer")
        row["displaced_candidate_execution_slots"] = slots

        parent_key = (row["physical_run_id"], row["parent_id"])
        if parent_key in parent_keys:
            raise AssignmentError("duplicate physical-run parent")
        parent_keys.add(parent_key)
        for sibling_id in ids:
            if sibling_id in sibling_ids:
                raise AssignmentError("duplicate sibling identity across parents")
            sibling_ids.add(sibling_id)
        rows.append(row)
    if not rows:
        raise AssignmentError("parent input is empty")
    return rows


def parse_config(raw: bytes, tasks: set[str]) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AssignmentError("invalid config JSON") from exc
    reject_forbidden_keys(value, "config")
    if not isinstance(value, dict) or set(value) != CONFIG_KEYS:
        raise AssignmentError("config schema mismatch")
    if value.get("schema_version") != CONFIG_SCHEMA:
        raise AssignmentError("config schema version mismatch")
    parse_utc(require_string(value, "created_utc"), "created_utc")
    require_hash(value, "source_commit", HEX40)
    for key in (
        "policy_contract_sha256",
        "operator_contract_sha256",
        "evaluator_contract_sha256",
    ):
        require_hash(value, key)
    seed = value.get("seed")
    timeout = value.get("execution_timeout_seconds")
    horizon = value.get("continuation_horizon")
    retry_count = value.get("retry_count")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise AssignmentError("seed must be a non-negative integer")
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
        raise AssignmentError("execution_timeout_seconds must be positive")
    if horizon != 1:
        raise AssignmentError("v1 fixes continuation_horizon=1")
    if retry_count != 0:
        raise AssignmentError("v1 fixes retry_count=0")
    if value.get("workspace_policy") != "fresh_per_rollout":
        raise AssignmentError("workspace_policy must be fresh_per_rollout")
    if value.get("adaptive_allocation_allowed") is not False:
        raise AssignmentError("adaptive allocation must be false")
    quotas = value.get("calibration_parents_per_task")
    if not isinstance(quotas, dict) or set(quotas) != tasks:
        raise AssignmentError("calibration quota tasks must exactly match parent tasks")
    for task, quota in quotas.items():
        if isinstance(quota, bool) or not isinstance(quota, int) or quota < 0:
            raise AssignmentError(f"invalid calibration quota for {task}")
    return value


def hash_order(seed: int, domain: str, *parts: str) -> str:
    raw = "|".join((PROTOCOL, domain, str(seed), *parts)).encode("utf-8")
    return sha256_bytes(raw)


def rollout_seed(seed: int, run_id: str, parent_id: str, sibling_id: str, replicate: int) -> int:
    raw = "|".join(
        (PROTOCOL, "rollout-seed", str(seed), run_id, parent_id, sibling_id, str(replicate))
    ).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big") % (2**31 - 1)


def calibration_keys(
    parents: Iterable[dict[str, Any]], config: dict[str, Any]
) -> tuple[set[tuple[str, str]], dict[str, dict[str, Any]]]:
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in parents:
        by_task[row["task"]].append(row)
    selected: set[tuple[str, str]] = set()
    task_summary: dict[str, dict[str, Any]] = {}
    for task in sorted(by_task):
        rows = sorted(
            by_task[task],
            key=lambda row: hash_order(
                config["seed"], "calibration", task, row["physical_run_id"], row["parent_id"]
            ),
        )
        quota = config["calibration_parents_per_task"][task]
        if quota > len(rows):
            raise AssignmentError(f"calibration quota exceeds support for {task}")
        for row in rows[:quota]:
            selected.add((row["physical_run_id"], row["parent_id"]))
        task_summary[task] = {
            "parent_count": len(rows),
            "calibration_parent_count": quota,
            "calibration_probability": quota / len(rows),
            "planned_candidate_execution_slots": 2 * len(rows) + 2 * quota,
        }
    return selected, task_summary


def build_assignments(
    parents: list[dict[str, Any]], config: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    calibration, task_summary = calibration_keys(parents, config)
    blocks: list[tuple[dict[str, Any], int]] = []
    for row in parents:
        key = (row["physical_run_id"], row["parent_id"])
        repetitions = 2 if key in calibration else 1
        expected_slots = 2 * repetitions
        if row["displaced_candidate_execution_slots"] != expected_slots:
            raise AssignmentError(
                f"displaced-slot ledger mismatch for {row['physical_run_id']}:{row['parent_id']}"
            )
        for replicate in range(repetitions):
            blocks.append((row, replicate))
    blocks.sort(
        key=lambda item: hash_order(
            config["seed"],
            "block-order",
            item[0]["physical_run_id"],
            item[0]["parent_id"],
            str(item[1]),
        )
    )

    assignments: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_seeds: set[int] = set()
    task_counts = Counter(row["task"] for row in parents)
    for row, replicate in blocks:
        parent_key = (row["physical_run_id"], row["parent_id"])
        is_calibration = parent_key in calibration
        conditional_calibration_probability = (
            config["calibration_parents_per_task"][row["task"]] / task_counts[row["task"]]
        )
        siblings = sorted(
            row["siblings"],
            key=lambda sibling: hash_order(
                config["seed"],
                "within-block-order",
                row["physical_run_id"],
                row["parent_id"],
                str(replicate),
                sibling["sibling_id"],
            ),
        )
        block_id = sha256_bytes(
            "|".join(
                (
                    PROTOCOL,
                    "block",
                    config["policy_contract_sha256"],
                    row["physical_run_id"],
                    row["parent_id"],
                    str(replicate),
                )
            ).encode("utf-8")
        )
        for position, sibling in enumerate(siblings):
            rseed = rollout_seed(
                config["seed"],
                row["physical_run_id"],
                row["parent_id"],
                sibling["sibling_id"],
                replicate,
            )
            assignment_id = sha256_bytes(
                "|".join(
                    (
                        PROTOCOL,
                        "assignment",
                        config["policy_contract_sha256"],
                        row["source_sha256"],
                        row["physical_run_id"],
                        row["parent_id"],
                        sibling["sibling_id"],
                        sibling["code_sha256"],
                        str(replicate),
                        str(rseed),
                    )
                ).encode("utf-8")
            )
            if rseed in seen_seeds or assignment_id in seen_ids:
                raise AssignmentError("derived rollout seed or assignment ID collision")
            seen_seeds.add(rseed)
            seen_ids.add(assignment_id)
            replicate_inclusion_probability = (
                1.0 if replicate == 0 else conditional_calibration_probability
            )
            assignments.append(
                {
                    "protocol": PROTOCOL,
                    "assignment_id": assignment_id,
                    "global_order": len(assignments),
                    "block_id": block_id,
                    "replicate": replicate,
                    "position_within_block": position,
                    "task": row["task"],
                    "physical_run_id": row["physical_run_id"],
                    "parent_id": row["parent_id"],
                    "generation_started_at_utc": row["generation_started_at_utc"],
                    "source_sha256": row["source_sha256"],
                    "sibling_id": sibling["sibling_id"],
                    "sibling_code_sha256": sibling["code_sha256"],
                    "source_sibling_receipt_sha256": sibling["receipt_sha256"],
                    "upstream_selection_receipt_sha256": row[
                        "upstream_selection_receipt_sha256"
                    ],
                    "policy_contract_sha256": config["policy_contract_sha256"],
                    "operator_contract_sha256": config["operator_contract_sha256"],
                    "evaluator_contract_sha256": config["evaluator_contract_sha256"],
                    "calibration_parent": is_calibration,
                    "upstream_selection_probability_attested": row[
                        "upstream_selection_probability_attested"
                    ],
                    "conditional_calibration_probability": conditional_calibration_probability,
                    "replicate_inclusion_probability": replicate_inclusion_probability,
                    "joint_inclusion_probability": (
                        row["upstream_selection_probability_attested"]
                        * replicate_inclusion_probability
                    ),
                    "order_probability": 0.5,
                    "rollout_seed": rseed,
                    "continuation_horizon": 1,
                    "planned_candidate_execution_slots": 1,
                    "retry_count": 0,
                    "fresh_workspace_required": True,
                }
            )
    return assignments, task_summary


def write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8", newline="\n")


def build(args: argparse.Namespace) -> int:
    parents_path = Path(args.parents).resolve()
    config_path = Path(args.config).resolve()
    output = Path(args.output).resolve()
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if output.exists() or staging.exists():
        raise AssignmentError("output and staging paths must not pre-exist")

    parents_raw = checked_bytes(parents_path)
    config_raw = checked_bytes(config_path)
    parents = parse_parents(parents_raw)
    tasks = {row["task"] for row in parents}
    config = parse_config(config_raw, tasks)
    for row in parents:
        if row["operator_contract_sha256"] != config["operator_contract_sha256"]:
            raise AssignmentError("parent/operator contract mismatch")
        if row["evaluator_contract_sha256"] != config["evaluator_contract_sha256"]:
            raise AssignmentError("parent/evaluator contract mismatch")

    assignments, task_summary = build_assignments(parents, config)
    planned_slots = len(assignments)
    displaced_slots = sum(row["displaced_candidate_execution_slots"] for row in parents)
    if planned_slots != displaced_slots:
        raise AssignmentError("global displaced-slot ledger mismatch")
    unique_code_hashes = {sibling["code_sha256"] for row in parents for sibling in row["siblings"]}
    summary = {
        "protocol": PROTOCOL,
        "status": STATUS,
        "created_utc": config["created_utc"],
        "contains_outcomes": False,
        "outcomes_read": False,
        "parents_input_sha256": sha256_bytes(parents_raw),
        "config_input_sha256": sha256_bytes(config_raw),
        "source_commit": config["source_commit"],
        "seed": config["seed"],
        "policy_contract_sha256": config["policy_contract_sha256"],
        "operator_contract_sha256": config["operator_contract_sha256"],
        "evaluator_contract_sha256": config["evaluator_contract_sha256"],
        "task_count": len(tasks),
        "parent_count": len(parents),
        "sibling_count": 2 * len(parents),
        "unique_sibling_code_sha256_count": len(unique_code_hashes),
        "calibration_parent_count": sum(
            config["calibration_parents_per_task"].values()
        ),
        "rollout_jobs": len(assignments),
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
        "task_support": task_summary,
    }

    staging.mkdir(parents=True)
    try:
        (staging / "parents.input.jsonl").write_bytes(parents_raw)
        (staging / "config.input.json").write_bytes(config_raw)
        assignment_text = "".join(canonical_json(row) + "\n" for row in assignments)
        write_text(staging / "assignment_manifest.jsonl", assignment_text)
        write_text(staging / "summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")
        write_text(staging / "command.txt", " ".join(sys.argv) + "\n")
        hashes = {
            path.name: sha256_bytes(path.read_bytes())
            for path in sorted(staging.iterdir())
            if path.is_file()
        }
        write_text(staging / "sha256_manifest.json", json.dumps(hashes, indent=2, sort_keys=True) + "\n")
        staging.replace(output)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    print(canonical_json(summary))
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--parents", required=True)
    result.add_argument("--config", required=True)
    result.add_argument("--output", required=True)
    return result


def main() -> int:
    try:
        return build(parser().parse_args())
    except (AssignmentError, OSError) as exc:
        print(f"ASSIGNMENT_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
