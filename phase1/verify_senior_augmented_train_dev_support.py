#!/usr/bin/env python3
"""Independent verifier for anonymized senior augmented train/dev support."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


DEV_DOMAIN = "augmented-dev-v1|20260819"
CURVE_DOMAIN = "augmented-curve-v1|20260819"
FRACTIONS = (0.25, 0.50, 0.75, 1.00)
SHA256 = re.compile(r"[0-9a-f]{64}")
RUN_FIELDS = {"cards", "config_sha256", "curve_order_sha256", "dev_order_sha256", "original_hold", "role", "run_id", "task"}
PAIR_FIELDS = {"original_split", "pair_key_sha256", "run_ids", "same_experiment_contract", "task"}


class VerificationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(domain: str, task: str, run_id: str) -> str:
    return hashlib.sha256(f"{domain}|{task}|{run_id}".encode()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise VerificationError(f"blank line at {path.name}:{line_number}")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise VerificationError("non-object JSONL row")
            rows.append(value)
    return rows


def validate_runs(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    run_map: dict[str, dict[str, Any]] = {}
    by_task: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        if set(row) != RUN_FIELDS:
            raise VerificationError("run fields mismatch")
        run_id = row["run_id"]
        task = row["task"]
        if not all(isinstance(value, str) and value for value in (run_id, task)) or run_id in run_map:
            raise VerificationError("run identity invalid")
        if not isinstance(row["cards"], int) or isinstance(row["cards"], bool) or row["cards"] < 1:
            raise VerificationError("run card count invalid")
        if not isinstance(row["original_hold"], bool):
            raise VerificationError("hold flag invalid")
        if row["role"] not in {"test_hold", "excluded_low_support", "dev", "train"}:
            raise VerificationError("run role invalid")
        if row["original_hold"] != (row["role"] == "test_hold"):
            raise VerificationError("hold role mismatch")
        for key in ("config_sha256", "curve_order_sha256", "dev_order_sha256"):
            if not isinstance(row[key], str) or not SHA256.fullmatch(row[key]):
                raise VerificationError("run digest invalid")
        if row["dev_order_sha256"] != stable_hash(DEV_DOMAIN, task, run_id):
            raise VerificationError("dev order digest mismatch")
        if row["curve_order_sha256"] != stable_hash(CURVE_DOMAIN, task, run_id):
            raise VerificationError("curve order digest mismatch")
        run_map[run_id] = row
        if not row["original_hold"]:
            by_task[task].append(row)
    for task, task_rows in by_task.items():
        if len(task_rows) < 5:
            if any(row["role"] != "excluded_low_support" for row in task_rows):
                raise VerificationError("low-support role mismatch")
            continue
        ordered = sorted(task_rows, key=lambda row: row["dev_order_sha256"])
        dev_count = max(1, math.floor(0.2 * len(ordered)))
        expected_dev = {row["run_id"] for row in ordered[:dev_count]}
        for row in ordered:
            expected_role = "dev" if row["run_id"] in expected_dev else "train"
            if row["role"] != expected_role:
                raise VerificationError("dev assignment mismatch")
    return run_map


def validate_pairs(rows: list[dict[str, Any]], run_map: dict[str, dict[str, Any]]) -> None:
    keys: set[str] = set()
    for row in rows:
        if set(row) != PAIR_FIELDS:
            raise VerificationError("pair fields mismatch")
        if row["original_split"] not in {"train", "test"}:
            raise VerificationError("pair split invalid")
        if not isinstance(row["pair_key_sha256"], str) or not SHA256.fullmatch(row["pair_key_sha256"]):
            raise VerificationError("pair digest invalid")
        if row["pair_key_sha256"] in keys:
            raise VerificationError("pair digest duplicated")
        keys.add(row["pair_key_sha256"])
        run_ids = row["run_ids"]
        if not isinstance(run_ids, list) or not 1 <= len(run_ids) <= 2 or run_ids != sorted(set(run_ids)):
            raise VerificationError("pair run list invalid")
        if any(run_id not in run_map for run_id in run_ids):
            raise VerificationError("pair run missing")
        if any(run_map[run_id]["task"] != row["task"] for run_id in run_ids):
            raise VerificationError("pair task mismatch")
        expected_contract = len({run_map[run_id]["config_sha256"] for run_id in run_ids}) == 1
        if row["same_experiment_contract"] is not expected_contract:
            raise VerificationError("pair contract flag mismatch")


def derive(run_rows: list[dict[str, Any]], pairs: list[dict[str, Any]]) -> dict[str, Any]:
    run_map = {row["run_id"]: row for row in run_rows}
    split_inconsistency = 0
    train_pairs = []
    test_pairs = 0
    for pair in pairs:
        roles = {run_map[run_id]["role"] for run_id in pair["run_ids"]}
        if pair["original_split"] == "test":
            test_pairs += 1
            split_inconsistency += roles != {"test_hold"}
        else:
            train_pairs.append(pair)
            split_inconsistency += "test_hold" in roles
    dev = []
    full = []
    cross = 0
    for pair in train_pairs:
        roles = {run_map[run_id]["role"] for run_id in pair["run_ids"]}
        if roles == {"dev"}:
            dev.append(pair)
        elif roles == {"train"}:
            full.append(pair)
        else:
            cross += 1
    dev_tasks = collections.Counter(row["task"] for row in dev)
    full_tasks = collections.Counter(row["task"] for row in full)
    large_dev_tasks = sum(value >= 20 for value in dev_tasks.values())
    train_runs_by_task: dict[str, list[str]] = collections.defaultdict(list)
    for row in run_rows:
        if row["role"] == "train":
            train_runs_by_task[row["task"]].append(row["run_id"])
    fraction_counts: dict[str, int] = {}
    for fraction in FRACTIONS:
        selected: set[str] = set()
        for task, run_ids in train_runs_by_task.items():
            ordered = sorted(run_ids, key=lambda run_id: run_map[run_id]["curve_order_sha256"])
            selected.update(ordered[: max(1, math.ceil(fraction * len(ordered)))])
        fraction_counts[f"{fraction:.2f}"] = sum(all(run_id in selected for run_id in pair["run_ids"]) for pair in full)
    values = list(fraction_counts.values())
    dev_contract = sum(row["same_experiment_contract"] for row in dev) / len(dev) if dev else None
    full_contract = sum(row["same_experiment_contract"] for row in full) / len(full) if full else None
    criteria = {
        "original_train_pairs_ge_2500": len(train_pairs) >= 2500,
        "original_split_inconsistency_eq_0": split_inconsistency == 0,
        "train_dev_hold_overlap_eq_0": all(not row["original_hold"] for row in run_rows if row["role"] in {"train", "dev"}),
        "dev_pairs_ge_400": len(dev) >= 400,
        "dev_tasks_ge_8": len(dev_tasks) >= 8,
        "dominant_dev_task_share_le_0_35": bool(dev) and max(dev_tasks.values()) / len(dev) <= 0.35,
        "full_train_pairs_ge_2000": len(full) >= 2000,
        "quarter_train_pairs_ge_300": values[0] >= 300,
        "fraction_pair_counts_strictly_increasing": all(left < right for left, right in zip(values, values[1:])),
        "full_and_dev_same_experiment_share_ge_0_95": dev_contract is not None and full_contract is not None and dev_contract >= 0.95 and full_contract >= 0.95,
        "dev_tasks_with_ge_20_pairs_ge_6": large_dev_tasks >= 6,
    }
    return {
        "status": "TRAIN_ONLY_DEV_LEARNING_CURVE_SUPPORT_FEASIBLE" if all(criteria.values()) else "INSUFFICIENT_TRAIN_ONLY_DEV_SUPPORT",
        "inventory": {
            "current_runs": len(run_rows),
            "current_tasks": len({row["task"] for row in run_rows}),
            "original_train_pairs": len(train_pairs),
            "original_test_pairs_structure_only": test_pairs,
            "split_inconsistency": split_inconsistency,
            "dev_runs": sum(row["role"] == "dev" for row in run_rows),
            "train_runs": sum(row["role"] == "train" for row in run_rows),
            "test_hold_runs": sum(row["role"] == "test_hold" for row in run_rows),
            "excluded_low_support_runs": sum(row["role"] == "excluded_low_support" for row in run_rows),
            "dev_pairs": len(dev),
            "full_train_pairs": len(full),
            "cross_train_dev_or_excluded_pairs": cross,
            "dev_tasks": len(dev_tasks),
            "full_train_tasks": len(full_tasks),
            "dominant_dev_task_share": max(dev_tasks.values()) / len(dev) if dev else None,
            "dev_tasks_with_ge_20_pairs": large_dev_tasks,
            "dev_same_experiment_contract_share": dev_contract,
            "full_train_same_experiment_contract_share": full_contract,
        },
        "fraction_train_pair_counts": fraction_counts,
        "dev_pairs_per_task": dict(sorted(dev_tasks.items())),
        "full_train_pairs_per_task": dict(sorted(full_tasks.items())),
        "criteria": criteria,
    }


def verify(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.artifact).resolve()
    expected_files = {"summary.json", "run_manifest.jsonl", "pair_structure.jsonl", "sha256_manifest.json"}
    if {path.name for path in root.iterdir() if path.is_file()} != expected_files:
        raise VerificationError("artifact filenames mismatch")
    manifest = load_json(root / "sha256_manifest.json")
    for name in expected_files - {"sha256_manifest.json"}:
        if manifest.get(name) != sha256_file(root / name):
            raise VerificationError(f"artifact digest mismatch for {name}")
    summary = load_json(root / "summary.json")
    run_rows = load_jsonl(root / "run_manifest.jsonl")
    pairs = load_jsonl(root / "pair_structure.jsonl")
    run_map = validate_runs(run_rows)
    validate_pairs(pairs, run_map)
    expected = derive(run_rows, pairs)
    for key, value in expected.items():
        if summary.get(key) != value:
            raise VerificationError(f"summary mismatch for {key}")
    scope = summary.get("scope", {})
    forbidden = ("model_trained", "pair_orientation_used_for_effect", "numeric_grade_used", "numeric_grade_emitted", "raw_code_emitted", "frozen_test_used_for_validation")
    if any(scope.get(key) is not False for key in forbidden) or scope.get("gpu") != 0 or scope.get("api_calls") != 0:
        raise VerificationError("scope mismatch")
    return {
        "protocol": "independent-senior-augmented-train-dev-support-verifier-v1",
        "status": "INDEPENDENT_TRAIN_DEV_SUPPORT_ARTIFACT_VERIFIED",
        "producer_status": expected["status"],
        "runs": len(run_rows),
        "pairs": len(pairs),
        "dev_pairs": expected["inventory"]["dev_pairs"],
        "full_train_pairs": expected["inventory"]["full_train_pairs"],
        "producer_imported": False,
        "summary_sha256": sha256_file(root / "summary.json"),
    }


def main() -> int:
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--artifact", required=True)
        parser.add_argument("--output", required=True)
        args = parser.parse_args()
        result = verify(args)
        output = Path(args.output).resolve()
        if output.exists():
            raise VerificationError("verification output exists")
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (VerificationError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"SENIOR_AUGMENTED_TRAIN_DEV_SUPPORT_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
