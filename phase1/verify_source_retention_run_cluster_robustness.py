#!/usr/bin/env python3
"""Independent reconstruction of source-retention run-cluster robustness."""

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


PROTOCOL = "source-retention-run-cluster-robustness-v1"
PASS = "RUN_CLUSTER_ROBUST_TASK_RETENTION_TRANSPORT"
FAIL = "TASK_RETENTION_TRANSPORT_NOT_RUN_CLUSTER_ROBUST"
SUPPORT = "INSUFFICIENT_RUN_CLUSTER_TASK_SUPPORT"
VERIFIED = "INDEPENDENT_RUN_CLUSTER_ROBUSTNESS_VERIFIED"
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
    "task", "train_parents", "frozen_parents", "train_runs", "frozen_runs",
    "eligible_run_robust", "train_parent_equal_retention",
    "frozen_parent_equal_retention", "train_run_equal_retention",
    "frozen_run_equal_retention",
)


class VerificationError(RuntimeError):
    pass


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def avg(values: Sequence[float]) -> float:
    if not values:
        raise VerificationError("empty average")
    return sum(values) / len(values)


def ranked(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    result = [0.0] * len(values)
    begin = 0
    while begin < len(order):
        end = begin + 1
        while end < len(order) and values[order[end]] == values[order[begin]]:
            end += 1
        score = (begin + 1 + end) / 2.0
        for position in range(begin, end):
            result[order[position]] = score
        begin = end
    return result


def rho(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    x, y = ranked(left), ranked(right)
    xm, ym = avg(x), avg(y)
    xss = sum((item - xm) ** 2 for item in x)
    yss = sum((item - ym) ** 2 for item in y)
    if xss <= 0 or yss <= 0:
        return None
    return sum((x[i] - xm) * (y[i] - ym) for i in range(len(x))) / math.sqrt(xss * yss)


def percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return ordered[low]
    fraction = position - low
    return ordered[low] * (1 - fraction) + ordered[high] * fraction


def permute(left: list[float], right: list[float], observed: float, count: int, seed: int) -> float:
    generator = random.Random(seed)
    candidate = list(right)
    extreme = 0
    for _ in range(count):
        generator.shuffle(candidate)
        value = rho(left, candidate)
        if value is not None and abs(value) >= abs(observed) - 1e-15:
            extreme += 1
    return (extreme + 1) / (count + 1)


def hierarchy(
    eligible: list[dict[str, Any]],
    task_runs: dict[str, dict[str, list[float]]],
    count: int,
    seed: int,
) -> dict[str, Any]:
    generator = random.Random(seed)
    estimates: list[float] = []
    for _ in range(count):
        selected = [generator.randrange(len(eligible)) for _ in range(len(eligible))]
        left: list[float] = []
        right: list[float] = []
        for index in selected:
            task = eligible[index]["task"]
            train = task_runs[task]["train"]
            frozen = task_runs[task]["frozen"]
            left.append(avg([train[generator.randrange(len(train))] for _ in range(len(train))]))
            right.append(avg([frozen[generator.randrange(len(frozen))] for _ in range(len(frozen))]))
        value = rho(left, right)
        if value is not None:
            estimates.append(value)
    return {
        "lower": percentile(estimates, 0.025) if estimates else None,
        "upper": percentile(estimates, 0.975) if estimates else None,
        "valid_replicates": len(estimates),
        "valid_fraction": len(estimates) / count,
    }


def load_protocol(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("protocol") != PROTOCOL or not SHA256.fullmatch(str(value.get("input_per_parent_sha256", ""))):
        raise VerificationError("protocol identity mismatch")
    tasks = value.get("primary_task_ids")
    if not isinstance(tasks, list) or tasks != sorted(set(tasks)):
        raise VerificationError("task universe mismatch")
    return value


def truth(value: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise VerificationError("invalid boolean")


def whole(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise VerificationError("invalid integer") from exc
    if result < 0:
        raise VerificationError("negative integer")
    return result


def finite(value: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise VerificationError("invalid float") from exc
    if not math.isfinite(result):
        raise VerificationError("nonfinite float")
    return result


def read_rows(path: Path, protocol: dict[str, Any]) -> list[dict[str, Any]]:
    if sha(path) != protocol["input_per_parent_sha256"]:
        raise VerificationError("input SHA mismatch")
    rows: list[dict[str, Any]] = []
    keys: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != UPSTREAM_FIELDS:
            raise VerificationError("upstream schema mismatch")
        for row in reader:
            role, task, run_id, parent = (row[name] for name in ("role", "task", "run_id", "parent"))
            if role not in ROLES or not task or not run_id or not parent or (role, parent) in keys:
                raise VerificationError("row identity mismatch")
            keys.add((role, parent))
            source = whole(row["source_declared_size"])
            raw_count = whole(row["raw_card_child_count"])
            finite_count = whole(row["finite_card_child_count"])
            retention = finite(row["finite_source_retention"])
            if source <= 0 or not 0 <= finite_count <= raw_count <= source:
                raise VerificationError("count relationship mismatch")
            if not math.isclose(retention, finite_count / source, abs_tol=1e-12):
                raise VerificationError("retention relationship mismatch")
            flags = (
                "source_size_consistent", "source_size_not_smaller_than_raw",
                "raw_context_consistent", "endpoints_all_finite", "endpoint_fidelity",
                "declared_matches_finite", "parent_context_consistent",
            )
            if not all(truth(row[name]) for name in flags):
                raise VerificationError("upstream structural gate mismatch")
            rows.append({"role": role, "task": task, "run_id": run_id, "retention": retention})
    if len(rows) != protocol["expected_parent_rows"]:
        raise VerificationError("row count mismatch")
    if dict(sorted(Counter(row["role"] for row in rows).items())) != protocol["expected_role_parent_counts"]:
        raise VerificationError("role count mismatch")
    return rows


def task_table(rows: list[dict[str, Any]], protocol: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, dict[str, list[float]]]]:
    tasks = set(protocol["primary_task_ids"])
    parents: dict[tuple[str, str], list[float]] = defaultdict(list)
    run_parents: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in rows:
        if row["task"] in tasks and row["role"] in ("train", "frozen"):
            parents[(row["task"], row["role"])].append(row["retention"])
            run_parents[(row["task"], row["role"], row["run_id"])].append(row["retention"])
    task_runs = {task: {"train": [], "frozen": []} for task in protocol["primary_task_ids"]}
    for (task, role, _run), values in sorted(run_parents.items()):
        task_runs[task][role].append(avg(values))
    output: list[dict[str, Any]] = []
    for task in protocol["primary_task_ids"]:
        train_parent = parents[(task, "train")]
        frozen_parent = parents[(task, "frozen")]
        train_run = task_runs[task]["train"]
        frozen_run = task_runs[task]["frozen"]
        output.append({
            "task": task,
            "train_parents": len(train_parent),
            "frozen_parents": len(frozen_parent),
            "train_runs": len(train_run),
            "frozen_runs": len(frozen_run),
            "eligible_run_robust": len(train_run) >= protocol["minimum_train_runs_per_task"]
            and len(frozen_run) >= protocol["minimum_frozen_runs_per_task"],
            "train_parent_equal_retention": avg(train_parent),
            "frozen_parent_equal_retention": avg(frozen_parent),
            "train_run_equal_retention": avg(train_run),
            "frozen_run_equal_retention": avg(frozen_run),
        })
    return output, task_runs


def tertile(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if len(rows) < 6:
        return None
    ordered = sorted(rows, key=lambda row: (row["train_run_equal_retention"], row["task"]))
    width = len(ordered) // 3
    low, high = ordered[:width], ordered[-width:]
    low_value = avg([row["frozen_run_equal_retention"] for row in low])
    high_value = avg([row["frozen_run_equal_retention"] for row in high])
    return {
        "tertile_width": width,
        "train_defined_low_tasks": [row["task"] for row in low],
        "train_defined_high_tasks": [row["task"] for row in high],
        "frozen_low_run_equal_mean": low_value,
        "frozen_high_run_equal_mean": high_value,
        "frozen_high_minus_low": high_value - low_value,
    }


def reconstruct(rows: list[dict[str, Any]], protocol: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    table, task_runs = task_table(rows, protocol)
    eligible = [row for row in table if row["eligible_run_robust"]]
    left = [row["train_run_equal_retention"] for row in eligible]
    right = [row["frozen_run_equal_retention"] for row in eligible]
    point = rho(left, right)
    support_ok = len(eligible) >= protocol["minimum_robust_tasks"]
    p_value = None
    interval = None
    loto: dict[str, float | None] = {}
    if support_ok and point is not None:
        p_value = permute(left, right, point, protocol["permutation_repetitions"], protocol["permutation_seed"])
        interval = hierarchy(eligible, task_runs, protocol["bootstrap_repetitions"], protocol["bootstrap_seed"])
        for index, row in enumerate(eligible):
            loto[row["task"]] = rho(left[:index] + left[index + 1 :], right[:index] + right[index + 1 :])
    finite_loto = [value for value in loto.values() if value is not None]
    minimum_loto = min(finite_loto) if loto and len(finite_loto) == len(loto) else None
    criteria = {
        "robust_tasks_ge_minimum": support_ok,
        "primary_rho_ge_minimum": point is not None and point >= protocol["minimum_primary_rho"],
        "permutation_p_lt_alpha": p_value is not None and p_value < protocol["significance_alpha"],
        "hierarchical_bootstrap_valid_fraction_ge_minimum": interval is not None
        and interval["valid_fraction"] >= protocol["minimum_bootstrap_valid_fraction"],
        "hierarchical_bootstrap_lower_gt_zero": interval is not None
        and interval["lower"] is not None and interval["lower"] > 0,
        "all_loto_rho_gt_minimum": minimum_loto is not None and minimum_loto > protocol["minimum_loto_rho"],
    }
    status = SUPPORT if not support_ok else PASS if all(criteria.values()) else FAIL
    return table, {
        "status": status,
        "support": {
            "frozen_v1_tasks": len(protocol["primary_task_ids"]),
            "run_robust_tasks": len(eligible),
            "run_robust_task_ids": [row["task"] for row in eligible],
            "minimum_train_runs_per_task": protocol["minimum_train_runs_per_task"],
            "minimum_frozen_runs_per_task": protocol["minimum_frozen_runs_per_task"],
        },
        "primary": {
            "metric": protocol["metric"],
            "spearman_rho": point,
            "permutation_two_sided_p": p_value,
            "task_run_hierarchical_bootstrap_95_ci": interval,
            "leave_one_task_out_rho": loto,
            "minimum_leave_one_task_out_rho": minimum_loto,
        },
        "train_defined_tertile_contrast": tertile(eligible),
        "criteria": criteria,
    }


def verify_table(path: Path, expected: list[dict[str, Any]]) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != TASK_FIELDS:
            raise VerificationError("artifact task schema mismatch")
        actual = list(reader)
    if len(actual) != len(expected):
        raise VerificationError("artifact task rows mismatch")
    for observed, target in zip(actual, expected):
        for field in TASK_FIELDS:
            wanted = target[field]
            value = observed[field]
            if isinstance(wanted, bool):
                if value != str(wanted):
                    raise VerificationError(f"task bool mismatch {field}")
            elif isinstance(wanted, int):
                if whole(value) != wanted:
                    raise VerificationError(f"task int mismatch {field}")
            elif isinstance(wanted, float):
                if finite(value) != wanted:
                    raise VerificationError(f"task float mismatch {field}")
            elif value != wanted:
                raise VerificationError(f"task text mismatch {field}")


def verify(args: argparse.Namespace) -> int:
    artifact = Path(args.artifact).resolve()
    protocol_path = Path(args.protocol).resolve()
    input_path = Path(args.per_parent).resolve()
    output = Path(args.output).resolve()
    if output.exists() or not artifact.is_dir() or not HEX40.fullmatch(args.source_commit):
        raise VerificationError("invalid invocation")
    manifest = json.loads((artifact / "sha256_manifest.json").read_text(encoding="utf-8"))
    expected_files = {"input_sha256.txt", "per_task_run.csv", "protocol.json", "source_commit.txt", "summary.json"}
    if set(manifest) != expected_files:
        raise VerificationError("manifest file set mismatch")
    for name, expected_sha in manifest.items():
        if not SHA256.fullmatch(expected_sha) or sha(artifact / name) != expected_sha:
            raise VerificationError(f"manifest hash mismatch: {name}")
    if (artifact / "protocol.json").read_bytes() != protocol_path.read_bytes():
        raise VerificationError("protocol bytes mismatch")
    protocol = load_protocol(protocol_path)
    rows = read_rows(input_path, protocol)
    table, science = reconstruct(rows, protocol)
    verify_table(artifact / "per_task_run.csv", table)
    summary = json.loads((artifact / "summary.json").read_text(encoding="utf-8"))
    if summary.get("protocol") != PROTOCOL or summary.get("source_commit") != args.source_commit:
        raise VerificationError("summary identity mismatch")
    for key in ("status", "support", "primary", "train_defined_tertile_contrast", "criteria"):
        if summary.get(key) != science[key]:
            raise VerificationError(f"scientific reconstruction mismatch: {key}")
    if summary.get("claim_allowed") is not (science["status"] == PASS):
        raise VerificationError("claim gate mismatch")
    scope = summary.get("scope") or {}
    if scope.get("post_result_robustness_not_new_confirmation") is not True or any(
        scope.get(field) is not False
        for field in (
            "candidate_code_read", "numeric_outcome_read", "pair_orientation_read",
            "prospective_outcome_read", "missing_at_random_claim", "causal_task_effect_claim",
            "predictor_or_search_utility_claim",
        )
    ):
        raise VerificationError("scope mismatch")
    receipt = {
        "status": VERIFIED,
        "producer_status": science["status"],
        "imports_producer": False,
        "parent_rows": len(rows),
        "run_robust_tasks": science["support"]["run_robust_tasks"],
        "primary_spearman_rho": science["primary"]["spearman_rho"],
        "maximum_reconstruction_difference": 0.0,
        "artifact_summary_sha256": sha(artifact / "summary.json"),
        "artifact_manifest_sha256": sha(artifact / "sha256_manifest.json"),
        "prospective_outcome_read": False,
    }
    output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"SOURCE_RETENTION_RUN_CLUSTER_VERIFY_PASS status={science['status']}")
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--artifact", required=True)
    value.add_argument("--protocol", required=True)
    value.add_argument("--per-parent", required=True)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--output", required=True)
    return value


if __name__ == "__main__":
    raise SystemExit(verify(parser().parse_args()))
