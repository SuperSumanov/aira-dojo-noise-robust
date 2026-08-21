#!/usr/bin/env python3
"""Independent verifier for the source-retention transport audit.

This module intentionally does not import ``phase1.source_retention_transport``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence


PROTOCOL = "source-retention-transport-v1"
PASS = "VERIFIED_TASK_CONDITIONED_SOURCE_RETENTION_TRANSPORT"
FAIL = "NO_VERIFIED_SOURCE_RETENTION_TRANSPORT"
SUPPORT = "INSUFFICIENT_TASK_SUPPORT"
VERIFIED = "INDEPENDENT_SOURCE_RETENTION_TRANSPORT_VERIFIED"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ROLES = ("train", "frozen", "extension")
UPSTREAM_FIELDS = (
    "role", "task", "run_id", "parent", "pair_rows", "unique_edges",
    "published_endpoint_count", "declared_set_size", "raw_card_child_count",
    "finite_card_child_count", "source_declared_size", "source_size_consistent",
    "source_size_not_smaller_than_raw", "raw_context_consistent",
    "endpoints_all_finite", "endpoint_fidelity", "declared_matches_finite",
    "finite_endpoint_coverage", "pair_graph_coverage_over_finite",
    "raw_source_retention", "finite_source_retention", "raw_equals_source",
    "finite_equals_source", "parent_card_present", "parent_context_consistent",
    "parent_children_declared_count", "parent_children_contains_raw",
    "source_size_gt_five",
)
TASK_FIELDS = (
    "task", "train_parents", "frozen_parents", "extension_parents",
    "eligible_primary", "train_finite_source_retention",
    "frozen_finite_source_retention", "extension_finite_source_retention",
    "train_raw_source_retention", "frozen_raw_source_retention",
    "extension_raw_source_retention", "train_parent_present_share",
    "frozen_parent_present_share", "extension_parent_present_share",
)


class VerificationError(RuntimeError):
    pass


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def average(values: Sequence[float]) -> float:
    if not values:
        raise VerificationError("empty average")
    return sum(values) / len(values)


def ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    output = [0.0] * len(values)
    start = 0
    while start < len(order):
        stop = start + 1
        while stop < len(order) and values[order[stop]] == values[order[start]]:
            stop += 1
        value = (start + 1 + stop) / 2.0
        for position in range(start, stop):
            output[order[position]] = value
        start = stop
    return output


def correlation(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    x = ranks(left)
    y = ranks(right)
    xbar = average(x)
    ybar = average(y)
    xss = sum((value - xbar) ** 2 for value in x)
    yss = sum((value - ybar) ** 2 for value in y)
    if xss <= 0 or yss <= 0:
        return None
    return sum((x[i] - xbar) * (y[i] - ybar) for i in range(len(x))) / math.sqrt(xss * yss)


def percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise VerificationError("empty percentile")
    position = (len(ordered) - 1) * probability
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    fraction = position - low
    return ordered[low] * (1 - fraction) + ordered[high] * fraction


def permutation(left: list[float], right: list[float], observed: float, count: int, seed: int) -> float:
    generator = random.Random(seed)
    candidate = list(right)
    extreme = 0
    threshold = abs(observed) - 1e-15
    for _ in range(count):
        generator.shuffle(candidate)
        value = correlation(left, candidate)
        if value is not None and abs(value) >= threshold:
            extreme += 1
    return (extreme + 1) / (count + 1)


def bootstrap(left: list[float], right: list[float], count: int, seed: int) -> dict[str, Any]:
    generator = random.Random(seed)
    values: list[float] = []
    for _ in range(count):
        selected = [generator.randrange(len(left)) for _ in range(len(left))]
        value = correlation([left[i] for i in selected], [right[i] for i in selected])
        if value is not None:
            values.append(value)
    return {
        "lower": percentile(values, 0.025) if values else None,
        "upper": percentile(values, 0.975) if values else None,
        "valid_replicates": len(values),
        "valid_fraction": len(values) / count,
    }


def load_protocol(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("protocol") != PROTOCOL:
        raise VerificationError("protocol mismatch")
    if not SHA256.fullmatch(str(value.get("input_per_parent_sha256", ""))):
        raise VerificationError("protocol input SHA invalid")
    roles = value.get("expected_role_parent_counts")
    if (
        not isinstance(roles, dict)
        or set(roles) != set(ROLES)
        or any(isinstance(count, bool) or not isinstance(count, int) or count < 0 for count in roles.values())
        or sum(roles.values()) != value.get("expected_parent_rows")
    ):
        raise VerificationError("protocol role counts invalid")
    return value


def boolean(value: str, where: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise VerificationError(f"invalid bool {where}")


def integer(value: str, where: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise VerificationError(f"invalid int {where}") from exc
    if result < 0:
        raise VerificationError(f"negative int {where}")
    return result


def number(value: str, where: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise VerificationError(f"invalid float {where}") from exc
    if not math.isfinite(result):
        raise VerificationError(f"nonfinite float {where}")
    return result


def load_parent_rows(path: Path, protocol: dict[str, Any]) -> list[dict[str, Any]]:
    if digest(path) != protocol["input_per_parent_sha256"]:
        raise VerificationError("input SHA mismatch")
    output: list[dict[str, Any]] = []
    keys: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != UPSTREAM_FIELDS:
            raise VerificationError("upstream fields mismatch")
        for line_number, row in enumerate(reader, 2):
            role, task, run_id, parent = (row[name] for name in ("role", "task", "run_id", "parent"))
            if role not in ROLES or not task or not run_id or not parent:
                raise VerificationError(f"identity mismatch at {line_number}")
            key = (role, parent)
            if key in keys:
                raise VerificationError("duplicate role-parent")
            keys.add(key)
            source = integer(row["source_declared_size"], "source")
            raw_count = integer(row["raw_card_child_count"], "raw")
            finite_count = integer(row["finite_card_child_count"], "finite")
            raw = number(row["raw_source_retention"], "raw retention")
            finite = number(row["finite_source_retention"], "finite retention")
            if source <= 0 or not 0 <= finite_count <= raw_count <= source:
                raise VerificationError("source counts invalid")
            if not math.isclose(raw, raw_count / source, abs_tol=1e-12):
                raise VerificationError("raw ratio mismatch")
            if not math.isclose(finite, finite_count / source, abs_tol=1e-12):
                raise VerificationError("finite ratio mismatch")
            flags = {name: boolean(row[name], name) for name in (
                "source_size_consistent", "source_size_not_smaller_than_raw",
                "raw_context_consistent", "endpoints_all_finite", "endpoint_fidelity",
                "declared_matches_finite", "parent_card_present", "parent_context_consistent",
                "parent_children_contains_raw",
            )}
            mandatory = (
                "source_size_consistent", "source_size_not_smaller_than_raw",
                "raw_context_consistent", "endpoints_all_finite", "endpoint_fidelity",
                "declared_matches_finite", "parent_context_consistent",
            )
            if not all(flags[name] for name in mandatory):
                raise VerificationError("upstream structural gate false")
            if flags["parent_card_present"] and not flags["parent_children_contains_raw"]:
                raise VerificationError("parent declaration false")
            output.append({
                "role": role,
                "task": task,
                "run_id": run_id,
                "parent": parent,
                "finite_source_retention": finite,
                "raw_source_retention": raw,
                "parent_card_present": flags["parent_card_present"],
            })
    if len(output) != protocol["expected_parent_rows"]:
        raise VerificationError("row count mismatch")
    if dict(sorted(Counter(row["role"] for row in output).items())) != protocol["expected_role_parent_counts"]:
        raise VerificationError("role count mismatch")
    return output


def independent_task_rows(rows: list[dict[str, Any]], protocol: dict[str, Any]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: {role: [] for role in ROLES})
    for row in rows:
        buckets[row["task"]][row["role"]].append(row)
    result: list[dict[str, Any]] = []
    for task in sorted(buckets):
        item: dict[str, Any] = {"task": task}
        for role in ROLES:
            selected = buckets[task][role]
            item[f"{role}_parents"] = len(selected)
            for metric in ("finite_source_retention", "raw_source_retention"):
                item[f"{role}_{metric}"] = average([row[metric] for row in selected]) if selected else None
            item[f"{role}_parent_present_share"] = (
                average([float(row["parent_card_present"]) for row in selected]) if selected else None
            )
            present = [row["finite_source_retention"] for row in selected if row["parent_card_present"]]
            if role in ("train", "frozen"):
                item[f"{role}_parent_present_finite_source_retention"] = average(present) if present else None
        item["eligible_primary"] = (
            item["train_parents"] >= protocol["minimum_train_parents_per_task"]
            and item["frozen_parents"] >= protocol["minimum_frozen_parents_per_task"]
        )
        result.append(item)
    return result


def profile(task_rows: list[dict[str, Any]], train_key: str, frozen_key: str) -> tuple[list[str], list[float], list[float], float | None]:
    selected = [row for row in task_rows if row["eligible_primary"] and row.get(train_key) is not None and row.get(frozen_key) is not None]
    tasks = [row["task"] for row in selected]
    train = [float(row[train_key]) for row in selected]
    frozen = [float(row[frozen_key]) for row in selected]
    return tasks, train, frozen, correlation(train, frozen)


def tertiles(eligible: list[dict[str, Any]]) -> dict[str, Any] | None:
    if len(eligible) < 6:
        return None
    ordered = sorted(eligible, key=lambda row: (float(row["train_finite_source_retention"]), row["task"]))
    width = len(ordered) // 3
    low = ordered[:width]
    high = ordered[-width:]
    low_mean = average([float(row["frozen_finite_source_retention"]) for row in low])
    high_mean = average([float(row["frozen_finite_source_retention"]) for row in high])
    return {
        "tertile_width": width,
        "train_defined_low_tasks": [row["task"] for row in low],
        "train_defined_high_tasks": [row["task"] for row in high],
        "frozen_low_task_equal_mean": low_mean,
        "frozen_high_task_equal_mean": high_mean,
        "frozen_high_minus_low": high_mean - low_mean,
    }


def expected_science(rows: list[dict[str, Any]], protocol: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    task_rows = independent_task_rows(rows, protocol)
    eligible = [row for row in task_rows if row["eligible_primary"]]
    tasks, train, frozen, rho = profile(
        task_rows, "train_finite_source_retention", "frozen_finite_source_retention"
    )
    support_ok = len(eligible) >= protocol["minimum_common_tasks"]
    p_value = None
    interval = None
    loto: dict[str, float | None] = {}
    if support_ok and rho is not None:
        p_value = permutation(train, frozen, rho, protocol["permutation_repetitions"], protocol["permutation_seed"])
        interval = bootstrap(train, frozen, protocol["bootstrap_repetitions"], protocol["bootstrap_seed"])
        for index, task in enumerate(tasks):
            loto[task] = correlation(train[:index] + train[index + 1 :], frozen[:index] + frozen[index + 1 :])
    finite_loto = [value for value in loto.values() if value is not None]
    min_loto = min(finite_loto) if loto and len(finite_loto) == len(loto) else None
    criteria = {
        "eligible_common_tasks_ge_minimum": support_ok,
        "primary_rho_ge_minimum": rho is not None and rho >= protocol["minimum_primary_rho"],
        "permutation_p_lt_alpha": p_value is not None and p_value < protocol["significance_alpha"],
        "bootstrap_valid_fraction_ge_minimum": interval is not None
        and interval["valid_fraction"] >= protocol["minimum_bootstrap_valid_fraction"],
        "bootstrap_lower_gt_zero": interval is not None and interval["lower"] is not None and interval["lower"] > 0,
        "all_loto_rho_gt_minimum": min_loto is not None and min_loto > protocol["minimum_loto_rho"],
    }
    status = SUPPORT if not support_ok else PASS if all(criteria.values()) else FAIL
    _, _, _, raw_rho = profile(task_rows, "train_raw_source_retention", "frozen_raw_source_retention")
    present_tasks, _, _, present_rho = profile(
        task_rows,
        "train_parent_present_finite_source_retention",
        "frozen_parent_present_finite_source_retention",
    )
    return task_rows, {
        "status": status,
        "support": {
            "all_tasks": len(task_rows),
            "eligible_common_tasks": len(eligible),
            "eligible_task_ids": tasks,
            "minimum_train_parents_per_task": protocol["minimum_train_parents_per_task"],
            "minimum_frozen_parents_per_task": protocol["minimum_frozen_parents_per_task"],
        },
        "primary": {
            "metric": protocol["metric"],
            "spearman_rho": rho,
            "permutation_two_sided_p": p_value,
            "bootstrap_95_ci": interval,
            "leave_one_task_out_rho": loto,
            "minimum_leave_one_task_out_rho": min_loto,
        },
        "train_defined_tertile_contrast": tertiles(eligible),
        "sensitivities": {
            "raw_source_retention_spearman_rho": raw_rho,
            "parent_present_only_finite_retention_spearman_rho": present_rho,
            "parent_present_only_tasks": present_tasks,
        },
        "criteria": criteria,
    }


def compare_task_table(path: Path, expected: list[dict[str, Any]]) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != TASK_FIELDS:
            raise VerificationError("artifact task fields mismatch")
        actual = list(reader)
    if len(actual) != len(expected):
        raise VerificationError("artifact task row count mismatch")
    for observed, wanted in zip(actual, expected):
        for field in TASK_FIELDS:
            target = wanted[field]
            value = observed[field]
            if target is None:
                if value != "":
                    raise VerificationError(f"expected empty task field {field}")
            elif isinstance(target, bool):
                if value != str(target):
                    raise VerificationError(f"task boolean mismatch {field}")
            elif isinstance(target, int):
                if integer(value, field) != target:
                    raise VerificationError(f"task integer mismatch {field}")
            elif isinstance(target, float):
                if number(value, field) != target:
                    raise VerificationError(f"task float mismatch {field}")
            elif value != str(target):
                raise VerificationError(f"task text mismatch {field}")


def verify(args: argparse.Namespace) -> int:
    artifact = Path(args.artifact).resolve()
    protocol_path = Path(args.protocol).resolve()
    parent_path = Path(args.per_parent).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise VerificationError("verification output exists")
    if not artifact.is_dir() or not HEX40.fullmatch(args.source_commit):
        raise VerificationError("invalid artifact or commit")
    manifest = json.loads((artifact / "sha256_manifest.json").read_text(encoding="utf-8"))
    expected_files = {
        "input_sha256.txt", "per_task.csv", "protocol.json", "source_commit.txt", "summary.json"
    }
    if set(manifest) != expected_files:
        raise VerificationError("artifact manifest file set mismatch")
    for name, expected_sha in manifest.items():
        if not SHA256.fullmatch(str(expected_sha)) or digest(artifact / name) != expected_sha:
            raise VerificationError(f"artifact hash mismatch: {name}")
    if (artifact / "protocol.json").read_bytes() != protocol_path.read_bytes():
        raise VerificationError("artifact protocol bytes mismatch")
    if (artifact / "source_commit.txt").read_text(encoding="utf-8") != args.source_commit + "\n":
        raise VerificationError("artifact source commit mismatch")
    protocol = load_protocol(protocol_path)
    if (artifact / "input_sha256.txt").read_text(encoding="utf-8") != protocol["input_per_parent_sha256"] + "\n":
        raise VerificationError("artifact input receipt mismatch")
    rows = load_parent_rows(parent_path, protocol)
    task_rows, science = expected_science(rows, protocol)
    compare_task_table(artifact / "per_task.csv", task_rows)
    summary = json.loads((artifact / "summary.json").read_text(encoding="utf-8"))
    if summary.get("protocol") != PROTOCOL or summary.get("source_commit") != args.source_commit:
        raise VerificationError("summary identity mismatch")
    for key in (
        "status", "support", "primary", "train_defined_tertile_contrast", "sensitivities", "criteria"
    ):
        if summary.get(key) != science[key]:
            raise VerificationError(f"independent scientific reconstruction mismatch: {key}")
    if summary.get("claim_allowed") is not (science["status"] == PASS):
        raise VerificationError("claim gate mismatch")
    expected_scope = {
        "candidate_code_read": False,
        "numeric_outcome_read": False,
        "pair_orientation_read": False,
        "prospective_outcome_read": False,
        "missing_at_random_claim": False,
        "causal_task_effect_claim": False,
        "complete_choice_set_claim": False,
        "predictor_or_search_utility_claim": False,
        "first_or_only_claim": False,
        "gpu_hours": 0,
        "api_calls": 0,
        "base_llm_updates": 0,
    }
    if summary.get("scope") != expected_scope:
        raise VerificationError("scope contract mismatch")
    expected_inputs = {
        "per_parent_sha256": protocol["input_per_parent_sha256"],
        "parent_rows": len(rows),
        "role_parent_counts": dict(sorted(Counter(row["role"] for row in rows).items())),
        "role_run_counts": {
            role: len({row["run_id"] for row in rows if row["role"] == role}) for role in ROLES
        },
    }
    if summary.get("inputs") != expected_inputs:
        raise VerificationError("input reconstruction mismatch")
    receipt = {
        "status": VERIFIED,
        "producer_status": science["status"],
        "imports_producer": False,
        "parent_rows": len(rows),
        "eligible_common_tasks": science["support"]["eligible_common_tasks"],
        "primary_spearman_rho": science["primary"]["spearman_rho"],
        "maximum_reconstruction_difference": 0.0,
        "artifact_summary_sha256": digest(artifact / "summary.json"),
        "artifact_manifest_sha256": digest(artifact / "sha256_manifest.json"),
        "prospective_outcome_read": False,
    }
    output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"SOURCE_RETENTION_TRANSPORT_INDEPENDENT_VERIFY_PASS "
        f"status={science['status']} tasks={science['support']['eligible_common_tasks']}"
    )
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--artifact", required=True)
    result.add_argument("--protocol", required=True)
    result.add_argument("--per-parent", required=True)
    result.add_argument("--source-commit", required=True)
    result.add_argument("--output", required=True)
    return result


if __name__ == "__main__":
    raise SystemExit(verify(parser().parse_args()))
