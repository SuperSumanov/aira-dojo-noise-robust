"""Independently reconstruct a randomized sibling logging assignment artifact.

This verifier intentionally shares no imports with the assignment producer.  It re-parses the
strict inputs, re-derives calibration membership, order, seeds, IDs, propensities and slot ledger,
then compares the canonical assignment bytes and every summary field.
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
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


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
EXPECTED_FILES = {
    "parents.input.jsonl",
    "config.input.json",
    "assignment_manifest.jsonl",
    "summary.json",
    "command.txt",
    "sha256_manifest.json",
}


class VerificationError(RuntimeError):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def safe_read(path: Path) -> bytes:
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise VerificationError(f"credential-shaped bytes in {path.name}")
    return raw


def reject_keys(value: Any, where: str) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise VerificationError(f"non-string key in {where}")
            if any(fragment in key.lower() for fragment in FORBIDDEN_KEY_FRAGMENTS):
                raise VerificationError(f"forbidden outcome-bearing key in {where}")
            reject_keys(nested, where)
    elif isinstance(value, list):
        for nested in value:
            reject_keys(nested, where)


def text(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise VerificationError(f"invalid {key}")
    return value


def hex_value(row: dict[str, Any], key: str, pattern: re.Pattern[str] = HEX64) -> str:
    value = text(row, key)
    if not pattern.fullmatch(value):
        raise VerificationError(f"invalid {key}")
    return value


def utc(value: str, key: str) -> str:
    if not value.endswith("Z"):
        raise VerificationError(f"invalid {key}")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise VerificationError(f"invalid {key}") from exc
    if parsed.tzinfo != dt.timezone.utc:
        raise VerificationError(f"invalid {key}")
    return value


def pair(row: dict[str, Any], key: str, hashes: bool) -> tuple[str, str]:
    value = row.get(key)
    if not isinstance(value, list) or len(value) != 2:
        raise VerificationError(f"invalid {key}")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise VerificationError(f"invalid {key}")
    if value[0] == value[1]:
        raise VerificationError(f"invalid {key}")
    if hashes and any(not HEX64.fullmatch(item) for item in value):
        raise VerificationError(f"invalid {key}")
    return value[0], value[1]


def read_parents(raw: bytes) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    parent_ids: set[tuple[str, str]] = set()
    all_siblings: set[str] = set()
    for line_no, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise VerificationError(f"invalid parent JSON at line {line_no}") from exc
        reject_keys(value, f"parent line {line_no}")
        if not isinstance(value, dict) or set(value) != PARENT_KEYS:
            raise VerificationError("parent schema mismatch")
        if value.get("schema_version") != PARENT_SCHEMA:
            raise VerificationError("parent version mismatch")
        row: dict[str, Any] = {
            "schema_version": PARENT_SCHEMA,
            "task": text(value, "task"),
            "physical_run_id": text(value, "physical_run_id"),
            "parent_id": text(value, "parent_id"),
            "generation_started_at_utc": utc(
                text(value, "generation_started_at_utc"), "generation_started_at_utc"
            ),
            "source_sha256": hex_value(value, "source_sha256"),
            "operator_contract_sha256": hex_value(value, "operator_contract_sha256"),
            "evaluator_contract_sha256": hex_value(value, "evaluator_contract_sha256"),
            "upstream_selection_receipt_sha256": hex_value(
                value, "upstream_selection_receipt_sha256"
            ),
        }
        siblings = pair(value, "sibling_ids", False)
        codes = pair(value, "sibling_code_sha256", True)
        receipts = pair(value, "source_sibling_receipt_sha256", True)
        row["siblings"] = [
            {"sibling_id": sid, "code_sha256": code, "receipt_sha256": receipt}
            for sid, code, receipt in sorted(zip(siblings, codes, receipts), key=lambda item: item[0])
        ]
        probability = value.get("upstream_selection_probability_attested")
        if (
            isinstance(probability, bool)
            or not isinstance(probability, (int, float))
            or not math.isfinite(float(probability))
            or not 0 < float(probability) <= 1
        ):
            raise VerificationError("invalid upstream probability")
        row["upstream_selection_probability_attested"] = float(probability)
        slots = value.get("displaced_candidate_execution_slots")
        if isinstance(slots, bool) or not isinstance(slots, int) or slots <= 0:
            raise VerificationError("invalid displaced slots")
        row["displaced_candidate_execution_slots"] = slots
        parent_key = (row["physical_run_id"], row["parent_id"])
        if parent_key in parent_ids:
            raise VerificationError("duplicate parent")
        parent_ids.add(parent_key)
        for sibling_id in siblings:
            if sibling_id in all_siblings:
                raise VerificationError("duplicate sibling")
            all_siblings.add(sibling_id)
        result.append(row)
    if not result:
        raise VerificationError("empty parents")
    return result


def read_config(raw: bytes, tasks: set[str]) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise VerificationError("invalid config JSON") from exc
    reject_keys(value, "config")
    if not isinstance(value, dict) or set(value) != CONFIG_KEYS:
        raise VerificationError("config schema mismatch")
    if value.get("schema_version") != CONFIG_SCHEMA:
        raise VerificationError("config version mismatch")
    utc(text(value, "created_utc"), "created_utc")
    hex_value(value, "source_commit", HEX40)
    for key in (
        "policy_contract_sha256",
        "operator_contract_sha256",
        "evaluator_contract_sha256",
    ):
        hex_value(value, key)
    seed = value.get("seed")
    timeout = value.get("execution_timeout_seconds")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise VerificationError("invalid seed")
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
        raise VerificationError("invalid timeout")
    if value.get("continuation_horizon") != 1:
        raise VerificationError("invalid horizon")
    if value.get("retry_count") != 0:
        raise VerificationError("invalid retry count")
    if value.get("workspace_policy") != "fresh_per_rollout":
        raise VerificationError("invalid workspace policy")
    if value.get("adaptive_allocation_allowed") is not False:
        raise VerificationError("adaptive allocation enabled")
    quotas = value.get("calibration_parents_per_task")
    if not isinstance(quotas, dict) or set(quotas) != tasks:
        raise VerificationError("quota tasks mismatch")
    for quota in quotas.values():
        if isinstance(quota, bool) or not isinstance(quota, int) or quota < 0:
            raise VerificationError("invalid quota")
    return value


def ordering(seed: int, domain: str, *parts: str) -> str:
    return digest("|".join((PROTOCOL, domain, str(seed), *parts)).encode("utf-8"))


def seed_for(seed: int, run_id: str, parent_id: str, sibling_id: str, replicate: int) -> int:
    raw = "|".join(
        (PROTOCOL, "rollout-seed", str(seed), run_id, parent_id, sibling_id, str(replicate))
    ).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big") % (2**31 - 1)


def independently_rebuild(
    parents: list[dict[str, Any]], config: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in parents:
        by_task[row["task"]].append(row)
    calibration: set[tuple[str, str]] = set()
    task_support: dict[str, dict[str, Any]] = {}
    for task in sorted(by_task):
        ordered = sorted(
            by_task[task],
            key=lambda row: ordering(
                config["seed"], "calibration", task, row["physical_run_id"], row["parent_id"]
            ),
        )
        quota = config["calibration_parents_per_task"][task]
        if quota > len(ordered):
            raise VerificationError("quota exceeds task support")
        for row in ordered[:quota]:
            calibration.add((row["physical_run_id"], row["parent_id"]))
        task_support[task] = {
            "parent_count": len(ordered),
            "calibration_parent_count": quota,
            "calibration_probability": quota / len(ordered),
            "planned_candidate_execution_slots": 2 * len(ordered) + 2 * quota,
        }

    blocks: list[tuple[dict[str, Any], int]] = []
    for row in parents:
        parent_key = (row["physical_run_id"], row["parent_id"])
        repetitions = 2 if parent_key in calibration else 1
        if row["displaced_candidate_execution_slots"] != 2 * repetitions:
            raise VerificationError("parent displaced-slot mismatch")
        for replicate in range(repetitions):
            blocks.append((row, replicate))
    blocks.sort(
        key=lambda item: ordering(
            config["seed"],
            "block-order",
            item[0]["physical_run_id"],
            item[0]["parent_id"],
            str(item[1]),
        )
    )

    task_counts = Counter(row["task"] for row in parents)
    assignments: list[dict[str, Any]] = []
    ids: set[str] = set()
    seeds: set[int] = set()
    for row, replicate in blocks:
        parent_key = (row["physical_run_id"], row["parent_id"])
        is_calibration = parent_key in calibration
        calibration_probability = (
            config["calibration_parents_per_task"][row["task"]] / task_counts[row["task"]]
        )
        siblings = sorted(
            row["siblings"],
            key=lambda sibling: ordering(
                config["seed"],
                "within-block-order",
                row["physical_run_id"],
                row["parent_id"],
                str(replicate),
                sibling["sibling_id"],
            ),
        )
        block_id = digest(
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
            rollout_seed = seed_for(
                config["seed"],
                row["physical_run_id"],
                row["parent_id"],
                sibling["sibling_id"],
                replicate,
            )
            assignment_id = digest(
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
                        str(rollout_seed),
                    )
                ).encode("utf-8")
            )
            if assignment_id in ids or rollout_seed in seeds:
                raise VerificationError("derived collision")
            ids.add(assignment_id)
            seeds.add(rollout_seed)
            replicate_probability = 1.0 if replicate == 0 else calibration_probability
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
                    "conditional_calibration_probability": calibration_probability,
                    "replicate_inclusion_probability": replicate_probability,
                    "joint_inclusion_probability": (
                        row["upstream_selection_probability_attested"] * replicate_probability
                    ),
                    "order_probability": 0.5,
                    "rollout_seed": rollout_seed,
                    "continuation_horizon": 1,
                    "planned_candidate_execution_slots": 1,
                    "retry_count": 0,
                    "fresh_workspace_required": True,
                }
            )
    return assignments, task_support


def verify(args: argparse.Namespace) -> int:
    root = Path(args.result).resolve()
    receipt = Path(args.receipt).resolve()
    temporary = receipt.with_name(receipt.name + f".tmp-{os.getpid()}")
    if receipt.exists() or temporary.exists():
        raise VerificationError("receipt path must not pre-exist")
    if not root.is_dir():
        raise VerificationError("result root is not a directory")
    actual_files = {path.name for path in root.iterdir() if path.is_file()}
    if actual_files != EXPECTED_FILES:
        raise VerificationError("artifact file set mismatch")

    hash_manifest = json.loads(safe_read(root / "sha256_manifest.json"))
    hash_names = EXPECTED_FILES - {"sha256_manifest.json"}
    if not isinstance(hash_manifest, dict) or set(hash_manifest) != hash_names:
        raise VerificationError("hash manifest schema mismatch")
    for name in hash_names:
        if hash_manifest[name] != digest(safe_read(root / name)):
            raise VerificationError(f"artifact hash mismatch: {name}")

    parents_raw = safe_read(root / "parents.input.jsonl")
    config_raw = safe_read(root / "config.input.json")
    parents = read_parents(parents_raw)
    tasks = {row["task"] for row in parents}
    config = read_config(config_raw, tasks)
    for row in parents:
        if row["operator_contract_sha256"] != config["operator_contract_sha256"]:
            raise VerificationError("operator contract mismatch")
        if row["evaluator_contract_sha256"] != config["evaluator_contract_sha256"]:
            raise VerificationError("evaluator contract mismatch")

    assignments, task_support = independently_rebuild(parents, config)
    canonical_bytes = "".join(canonical(row) + "\n" for row in assignments).encode("utf-8")
    if safe_read(root / "assignment_manifest.jsonl") != canonical_bytes:
        raise VerificationError("assignment bytes do not match independent reconstruction")
    planned_slots = len(assignments)
    displaced_slots = sum(row["displaced_candidate_execution_slots"] for row in parents)
    if planned_slots != displaced_slots:
        raise VerificationError("global slot budget mismatch")
    unique_codes = {sibling["code_sha256"] for row in parents for sibling in row["siblings"]}
    expected_summary = {
        "protocol": PROTOCOL,
        "status": STATUS,
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
        "task_count": len(tasks),
        "parent_count": len(parents),
        "sibling_count": 2 * len(parents),
        "unique_sibling_code_sha256_count": len(unique_codes),
        "calibration_parent_count": sum(config["calibration_parents_per_task"].values()),
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
        "task_support": task_support,
    }
    summary = json.loads(safe_read(root / "summary.json"))
    if summary != expected_summary:
        raise VerificationError("summary does not match independent reconstruction")

    verification = {
        "status": "VERIFIED_OUTCOME_BLIND_RANDOMIZED_SIBLING_ASSIGNMENT",
        "producer_imported": False,
        "result_sha256_manifest": digest(safe_read(root / "sha256_manifest.json")),
        "parent_count": len(parents),
        "task_count": len(tasks),
        "rollout_jobs": len(assignments),
        "planned_candidate_execution_slots": planned_slots,
        "displaced_candidate_execution_slots": displaced_slots,
        "declared_slot_ledger_matches_plan": True,
        "actual_production_budget_decrement_verified": False,
        "contains_outcomes": False,
        "independent_reconstruction_exact": True,
    }
    receipt.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(
        json.dumps(verification, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(receipt)
    print(canonical(verification))
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--result", required=True)
    result.add_argument("--receipt", required=True)
    return result


def main() -> int:
    try:
        return verify(parser().parse_args())
    except (VerificationError, OSError, json.JSONDecodeError) as exc:
        print(f"VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
