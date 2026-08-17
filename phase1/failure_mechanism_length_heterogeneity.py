#!/usr/bin/env python3
"""Train-only failure-category heterogeneity audit for raw code-byte length."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import sys
import zlib
from pathlib import Path
from typing import Any

import numpy as np

from phase1.audit_failure_risk_pair_support import (
    SupportError,
    card_parent,
    load_failures,
    locked,
    parse_roots,
    rows,
    scan_failure_code_metadata,
    task_name,
)
from phase1.source_opportunity_journal_status import sha256_bytes, sha256_file
from phase1.verify_failure_risk_pair_registry import EXPECTED_KEYS, HEX64


PROTOCOL = "failure-mechanism-length-heterogeneity-v1"
REGISTRY_SHA256 = "ee7c878c9b3390c08d309229ac6380bf86e6934b92aab269e42ce7c2ffd57747"
SEED = 20260818
BOOTSTRAPS = 10_000
PERMUTATIONS = 100_000
MIN_CATEGORY_PAIRS = 30


class AuditError(RuntimeError):
    pass


def load_registry(path: Path) -> list[dict[str, str]]:
    if not path.is_file() or sha256_file(path) != REGISTRY_SHA256:
        raise AuditError("locked code-free registry mismatch")
    result = []
    for line_number, row in enumerate(rows(path), 1):
        if set(row) != EXPECTED_KEYS or row.get("role") != "train_only":
            raise AuditError(f"registry schema mismatch at line {line_number}")
        if any(not isinstance(row.get(key), str) or not row[key] for key in EXPECTED_KEYS):
            raise AuditError("registry contains an empty field")
        for key in ("failure_code_sha256", "success_code_sha256", "failure_source_journal_sha256"):
            if not HEX64.fullmatch(row[key]):
                raise AuditError(f"invalid digest in {key}")
        result.append({key: str(value) for key, value in row.items()})
    if len(result) != 494 or len({row["parent_id"] for row in result}) != 494:
        raise AuditError("registry support changed")
    return result


def reconstruct(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registry = load_registry(Path(args.registry).resolve())
    cards_path = locked(args.cards, args.expect_cards_sha256)
    status_path = locked(args.status_per_child, args.expect_status_sha256)
    taxonomy_path = locked(args.taxonomy_per_child, args.expect_taxonomy_sha256)
    cards = {str(row["id"]): row for row in rows(cards_path)}
    failures = load_failures(status_path, taxonomy_path, 691)
    metadata, inventory = scan_failure_code_metadata(parse_roots(args.root), failures)
    if inventory["credential_target_journal_shas"] != 0:
        raise AuditError("credential-shaped target journal")

    output = []
    for row in registry:
        failure_id = row["failure_child_id"]
        success_id = row["success_child_id"]
        parent_id = row["parent_id"]
        failure = failures.get(failure_id)
        failure_meta = metadata.get(failure_id)
        success = cards.get(success_id)
        parent = cards.get(parent_id)
        if failure is None or failure_meta is None or success is None or parent is None:
            raise AuditError("registry identity is absent from locked inputs")
        if (
            failure["parent_id"] != parent_id
            or failure["failure_category"] != row["failure_category"]
            or failure_meta["code_sha256"] != row["failure_code_sha256"]
            or card_parent(success) != parent_id
            or str(parent.get("run_id")) != row["physical_run_id"]
            or str(success.get("run_id")) != row["physical_run_id"]
            or task_name(parent) != row["task"]
        ):
            raise AuditError("registry/input identity binding mismatch")
        success_code = success.get("code")
        if not isinstance(success_code, str) or not success_code.strip():
            raise AuditError("success code is empty")
        success_bytes = len(success_code.encode("utf-8"))
        success_sha = sha256_bytes(success_code.encode("utf-8"))
        if success_sha != row["success_code_sha256"]:
            raise AuditError("success code SHA mismatch")
        failure_bytes = int(failure_meta["code_bytes"])
        credit = 1.0 if success_bytes > failure_bytes else 0.0 if success_bytes < failure_bytes else 0.5
        hash_credit = float(int(hashlib.sha256(parent_id.encode("utf-8")).hexdigest(), 16) & 1)
        output.append(
            {
                "category": row["failure_category"],
                "task": row["task"],
                "run_id": row["physical_run_id"],
                "parent_id": parent_id,
                "failure_bytes": failure_bytes,
                "success_bytes": success_bytes,
                "delta_bytes": success_bytes - failure_bytes,
                "length_credit": credit,
                "hash_credit": hash_credit,
            }
        )
    return output, inventory


def clustered_ci(selected: list[dict[str, Any]], cluster_key: str, value_key: str, salt: str) -> list[float]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row in selected:
        grouped[str(row[cluster_key])].append(float(row[value_key]))
    keys = sorted(grouped)
    seed = SEED ^ zlib.crc32(salt.encode("utf-8"))
    rng = np.random.default_rng(seed)
    values = np.empty(BOOTSTRAPS, dtype=np.float64)
    for index in range(BOOTSTRAPS):
        sampled = rng.choice(keys, size=len(keys), replace=True)
        draw = [value for key in sampled for value in grouped[str(key)]]
        values[index] = np.mean(draw)
    return [float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))]


def heterogeneity_stat(categories: np.ndarray, values: np.ndarray, category_count: int) -> float:
    counts = np.bincount(categories, minlength=category_count).astype(np.float64)
    sums = np.bincount(categories, weights=values, minlength=category_count)
    means = sums / counts
    overall = float(np.mean(values))
    return float(np.sum(counts * np.square(means - overall)) / np.sum(counts))


def stratified_permutation_p(selected: list[dict[str, Any]], value_key: str) -> tuple[float, float]:
    category_names = sorted({str(row["category"]) for row in selected})
    category_index = {name: index for index, name in enumerate(category_names)}
    categories = np.array([category_index[str(row["category"])] for row in selected], dtype=np.int16)
    values = np.array([float(row[value_key]) for row in selected], dtype=np.float64)
    tasks = np.array([str(row["task"]) for row in selected], dtype=object)
    groups = [np.flatnonzero(tasks == task) for task in sorted(set(tasks))]
    observed = heterogeneity_stat(categories, values, len(category_names))
    counts = np.bincount(categories, minlength=len(category_names)).astype(np.float64)
    overall = float(np.mean(values))
    extreme = 0
    rng = np.random.default_rng(SEED ^ zlib.crc32(value_key.encode("utf-8")))
    batch_size = 1_000
    for start in range(0, PERMUTATIONS, batch_size):
        batch = min(batch_size, PERMUTATIONS - start)
        sums = np.zeros((batch, len(category_names)), dtype=np.float64)
        for indices in groups:
            random_keys = rng.random((batch, len(indices)))
            order = np.argsort(random_keys, axis=1)
            shuffled = values[indices][order]
            one_hot = np.eye(len(category_names), dtype=np.float64)[categories[indices]]
            sums += shuffled @ one_hot
        means = sums / counts
        stats = np.sum(counts * np.square(means - overall), axis=1) / np.sum(counts)
        extreme += int(np.count_nonzero(stats >= observed - 1e-15))
    return observed, (extreme + 1) / (PERMUTATIONS + 1)


def summarize(pairs: list[dict[str, Any]], inventory: dict[str, Any]) -> dict[str, Any]:
    category_counts = collections.Counter(str(row["category"]) for row in pairs)
    eligible_names = sorted(name for name, count in category_counts.items() if count >= MIN_CATEGORY_PAIRS)
    eligible = [row for row in pairs if row["category"] in eligible_names]
    per_category = {}
    for category in sorted(category_counts):
        selected = [row for row in pairs if row["category"] == category]
        per_category[category] = {
            "pairs": len(selected),
            "tasks": len({row["task"] for row in selected}),
            "physical_runs": len({row["run_id"] for row in selected}),
            "length_credit": float(np.mean([row["length_credit"] for row in selected])),
            "median_delta_bytes": float(np.median([row["delta_bytes"] for row in selected])),
            "task_clustered_ci": clustered_ci(selected, "task", "length_credit", f"task:{category}"),
            "run_clustered_ci": clustered_ci(selected, "run_id", "length_credit", f"run:{category}"),
        }
    eligible_values = [per_category[name]["length_credit"] for name in eligible_names]
    low_name = min(eligible_names, key=lambda name: per_category[name]["length_credit"])
    high_name = max(eligible_names, key=lambda name: per_category[name]["length_credit"])
    observed, p_value = stratified_permutation_p(eligible, "length_credit")
    control_observed, control_p = stratified_permutation_p(eligible, "hash_credit")
    spread = max(eligible_values) - min(eligible_values)
    criteria = {
        "pairs_eq_494": len(pairs) == 494,
        "eligible_categories_ge_3": len(eligible_names) >= 3,
        "extreme_categories_each_ge_30_pairs": min(
            per_category[low_name]["pairs"], per_category[high_name]["pairs"]
        ) >= MIN_CATEGORY_PAIRS,
        "extreme_categories_each_ge_4_tasks": min(
            per_category[low_name]["tasks"], per_category[high_name]["tasks"]
        ) >= 4,
        "category_credit_range_ge_0_15": spread >= 0.15,
        "task_stratified_permutation_p_le_0_01": p_value <= 0.01,
    }
    passed = all(criteria.values())
    return {
        "protocol": PROTOCOL,
        "status": (
            "VERIFIED_FAILURE_MECHANISM_LENGTH_HETEROGENEITY"
            if passed
            else "INSUFFICIENT_FAILURE_MECHANISM_LENGTH_HETEROGENEITY"
        ),
        "scope": {
            "role": "train_only",
            "frozen_endpoint_code_read": False,
            "numeric_grade_read": False,
            "raw_code_emitted": False,
            "search_utility_computed": False,
            "gpu": 0,
            "api_calls": 0,
            "base_llm_updated": False,
        },
        "pairs": len(pairs),
        "tasks": len({row["task"] for row in pairs}),
        "physical_runs": len({row["run_id"] for row in pairs}),
        "overall_length_credit": float(np.mean([row["length_credit"] for row in pairs])),
        "eligible_categories": eligible_names,
        "category_credit_range": spread,
        "lowest_category": low_name,
        "highest_category": high_name,
        "heterogeneity_statistic": observed,
        "task_stratified_permutation_p": p_value,
        "hash_negative_control_statistic": control_observed,
        "hash_negative_control_p": control_p,
        "per_category": per_category,
        "criteria": criteria,
        "failure_mechanism_heterogeneity_claim_allowed": passed,
        "method_effect_claim_allowed": False,
        "search_utility_claim_allowed": False,
        "journal_inventory": inventory,
        "configuration": {
            "seed": SEED,
            "bootstraps": BOOTSTRAPS,
            "permutations": PERMUTATIONS,
            "minimum_category_pairs": MIN_CATEGORY_PAIRS,
            "length_definition": "raw UTF-8 code bytes; greater predicts retained success; ties 0.5",
            "permutation": "shuffle credits within task over categories with >=30 pairs",
        },
    }


def write_atomic(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise AuditError("output exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--registry", required=True)
    value.add_argument("--cards", required=True)
    value.add_argument("--expect-cards-sha256", required=True)
    value.add_argument("--status-per-child", required=True)
    value.add_argument("--expect-status-sha256", required=True)
    value.add_argument("--taxonomy-per-child", required=True)
    value.add_argument("--expect-taxonomy-sha256", required=True)
    value.add_argument("--root", action="append", required=True)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        args = parser().parse_args()
        pairs, inventory = reconstruct(args)
        result = summarize(pairs, inventory)
        result["source_commit"] = args.source_commit
        result["registry_sha256"] = REGISTRY_SHA256
        result["inputs"] = {
            "cards_sha256": args.expect_cards_sha256,
            "status_per_child_sha256": args.expect_status_sha256,
            "taxonomy_per_child_sha256": args.expect_taxonomy_sha256,
        }
        write_atomic(Path(args.output).resolve(), result)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (AuditError, SupportError, OSError, json.JSONDecodeError) as exc:
        print(f"FAILURE_MECHANISM_LENGTH_HETEROGENEITY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
