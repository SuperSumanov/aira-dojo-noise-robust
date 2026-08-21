#!/usr/bin/env python3
"""Run-equal and task-by-run bootstrap stress test for source-retention transport."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import random
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence


PROTOCOL = "source-retention-run-cluster-robustness-v1"
STATUS_PASS = "RUN_CLUSTER_ROBUST_TASK_RETENTION_TRANSPORT"
STATUS_FAIL = "TASK_RETENTION_TRANSPORT_NOT_RUN_CLUSTER_ROBUST"
STATUS_SUPPORT = "INSUFFICIENT_RUN_CLUSTER_TASK_SUPPORT"
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


class RobustnessError(RuntimeError):
    pass


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def load_protocol(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("protocol") != PROTOCOL:
        raise RobustnessError("invalid protocol")
    if not SHA256.fullmatch(str(value.get("input_per_parent_sha256", ""))):
        raise RobustnessError("invalid input SHA")
    integer_fields = (
        "bootstrap_repetitions", "bootstrap_seed", "expected_parent_rows",
        "minimum_frozen_runs_per_task", "minimum_robust_tasks",
        "minimum_train_runs_per_task", "permutation_repetitions", "permutation_seed",
    )
    for field in integer_fields:
        item = value.get(field)
        if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
            raise RobustnessError(f"invalid protocol integer: {field}")
    role_counts = value.get("expected_role_parent_counts")
    if (
        not isinstance(role_counts, dict)
        or set(role_counts) != set(ROLES)
        or any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in role_counts.values())
        or sum(role_counts.values()) != value["expected_parent_rows"]
    ):
        raise RobustnessError("invalid role counts")
    tasks = value.get("primary_task_ids")
    if (
        not isinstance(tasks, list)
        or len(tasks) != len(set(tasks))
        or tasks != sorted(tasks)
        or not all(isinstance(task, str) and task for task in tasks)
    ):
        raise RobustnessError("invalid frozen task universe")
    for field in (
        "minimum_bootstrap_valid_fraction", "minimum_loto_rho",
        "minimum_primary_rho", "significance_alpha",
    ):
        item = value.get(field)
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)):
            raise RobustnessError(f"invalid protocol float: {field}")
    if value.get("metric") != "run_equal_finite_source_retention":
        raise RobustnessError("metric changed")
    return value


def parse_bool(value: str, where: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise RobustnessError(f"invalid bool at {where}")


def parse_int(value: str, where: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise RobustnessError(f"invalid int at {where}") from exc
    if result < 0:
        raise RobustnessError(f"negative int at {where}")
    return result


def parse_float(value: str, where: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise RobustnessError(f"invalid float at {where}") from exc
    if not math.isfinite(result):
        raise RobustnessError(f"nonfinite float at {where}")
    return result


def load_rows(path: Path, protocol: dict[str, Any]) -> list[dict[str, Any]]:
    if digest(path) != protocol["input_per_parent_sha256"]:
        raise RobustnessError("input SHA mismatch")
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != UPSTREAM_FIELDS:
            raise RobustnessError("upstream fields mismatch")
        for line_number, raw in enumerate(reader, 2):
            role, task, run_id, parent = (raw[name] for name in ("role", "task", "run_id", "parent"))
            if role not in ROLES or not task or not run_id or not parent:
                raise RobustnessError(f"invalid identity row {line_number}")
            key = (role, parent)
            if key in seen:
                raise RobustnessError("duplicate role-parent")
            seen.add(key)
            source = parse_int(raw["source_declared_size"], "source")
            raw_count = parse_int(raw["raw_card_child_count"], "raw count")
            finite_count = parse_int(raw["finite_card_child_count"], "finite count")
            retention = parse_float(raw["finite_source_retention"], "retention")
            if source <= 0 or not 0 <= finite_count <= raw_count <= source:
                raise RobustnessError("invalid source counts")
            if not math.isclose(retention, finite_count / source, abs_tol=1e-12):
                raise RobustnessError("retention count mismatch")
            required_flags = (
                "source_size_consistent", "source_size_not_smaller_than_raw",
                "raw_context_consistent", "endpoints_all_finite", "endpoint_fidelity",
                "declared_matches_finite", "parent_context_consistent",
            )
            if not all(parse_bool(raw[field], field) for field in required_flags):
                raise RobustnessError("upstream structural gate failed")
            rows.append({
                "role": role,
                "task": task,
                "run_id": run_id,
                "parent": parent,
                "retention": retention,
            })
    if len(rows) != protocol["expected_parent_rows"]:
        raise RobustnessError("parent row count mismatch")
    if dict(sorted(Counter(row["role"] for row in rows).items())) != protocol["expected_role_parent_counts"]:
        raise RobustnessError("role counts mismatch")
    available_tasks = {row["task"] for row in rows}
    if not set(protocol["primary_task_ids"]) <= available_tasks:
        raise RobustnessError("frozen task universe absent from input")
    return rows


def mean(values: Sequence[float]) -> float:
    if not values:
        raise RobustnessError("empty mean")
    return sum(values) / len(values)


def rank(values: Sequence[float]) -> list[float]:
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


def spearman(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    x = rank(left)
    y = rank(right)
    xbar = mean(x)
    ybar = mean(y)
    xss = sum((value - xbar) ** 2 for value in x)
    yss = sum((value - ybar) ** 2 for value in y)
    if xss <= 0 or yss <= 0:
        return None
    return sum((x[i] - xbar) * (y[i] - ybar) for i in range(len(x))) / math.sqrt(xss * yss)


def quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise RobustnessError("empty quantile")
    location = (len(ordered) - 1) * probability
    low = math.floor(location)
    high = math.ceil(location)
    if low == high:
        return ordered[low]
    fraction = location - low
    return ordered[low] * (1 - fraction) + ordered[high] * fraction


def permutation_p(left: list[float], right: list[float], observed: float, count: int, seed: int) -> float:
    rng = random.Random(seed)
    candidate = list(right)
    extreme = 0
    threshold = abs(observed) - 1e-15
    for _ in range(count):
        rng.shuffle(candidate)
        value = spearman(left, candidate)
        if value is not None and abs(value) >= threshold:
            extreme += 1
    return (extreme + 1) / (count + 1)


def build_task_rows(rows: list[dict[str, Any]], protocol: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, dict[str, list[float]]]]:
    frozen_tasks = set(protocol["primary_task_ids"])
    parent_values: dict[tuple[str, str], list[float]] = defaultdict(list)
    run_parents: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in rows:
        if row["task"] not in frozen_tasks or row["role"] not in ("train", "frozen"):
            continue
        parent_values[(row["task"], row["role"])].append(row["retention"])
        run_parents[(row["task"], row["role"], row["run_id"])].append(row["retention"])
    task_runs: dict[str, dict[str, list[float]]] = {
        task: {"train": [], "frozen": []} for task in protocol["primary_task_ids"]
    }
    for (task, role, _run), values in sorted(run_parents.items()):
        task_runs[task][role].append(mean(values))
    output: list[dict[str, Any]] = []
    for task in protocol["primary_task_ids"]:
        train_parent = parent_values[(task, "train")]
        frozen_parent = parent_values[(task, "frozen")]
        train_runs = task_runs[task]["train"]
        frozen_runs = task_runs[task]["frozen"]
        output.append({
            "task": task,
            "train_parents": len(train_parent),
            "frozen_parents": len(frozen_parent),
            "train_runs": len(train_runs),
            "frozen_runs": len(frozen_runs),
            "eligible_run_robust": (
                len(train_runs) >= protocol["minimum_train_runs_per_task"]
                and len(frozen_runs) >= protocol["minimum_frozen_runs_per_task"]
            ),
            "train_parent_equal_retention": mean(train_parent),
            "frozen_parent_equal_retention": mean(frozen_parent),
            "train_run_equal_retention": mean(train_runs),
            "frozen_run_equal_retention": mean(frozen_runs),
        })
    return output, task_runs


def hierarchical_bootstrap(
    eligible: list[dict[str, Any]],
    task_runs: dict[str, dict[str, list[float]]],
    repetitions: int,
    seed: int,
) -> dict[str, Any]:
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(repetitions):
        selected = [rng.randrange(len(eligible)) for _ in range(len(eligible))]
        train_profile: list[float] = []
        frozen_profile: list[float] = []
        for index in selected:
            task = eligible[index]["task"]
            train = task_runs[task]["train"]
            frozen = task_runs[task]["frozen"]
            train_profile.append(mean([train[rng.randrange(len(train))] for _ in range(len(train))]))
            frozen_profile.append(mean([frozen[rng.randrange(len(frozen))] for _ in range(len(frozen))]))
        value = spearman(train_profile, frozen_profile)
        if value is not None:
            estimates.append(value)
    return {
        "lower": quantile(estimates, 0.025) if estimates else None,
        "upper": quantile(estimates, 0.975) if estimates else None,
        "valid_replicates": len(estimates),
        "valid_fraction": len(estimates) / repetitions,
    }


def tertile(eligible: list[dict[str, Any]]) -> dict[str, Any] | None:
    if len(eligible) < 6:
        return None
    ordered = sorted(eligible, key=lambda row: (row["train_run_equal_retention"], row["task"]))
    width = len(ordered) // 3
    low = ordered[:width]
    high = ordered[-width:]
    low_mean = mean([row["frozen_run_equal_retention"] for row in low])
    high_mean = mean([row["frozen_run_equal_retention"] for row in high])
    return {
        "tertile_width": width,
        "train_defined_low_tasks": [row["task"] for row in low],
        "train_defined_high_tasks": [row["task"] for row in high],
        "frozen_low_run_equal_mean": low_mean,
        "frozen_high_run_equal_mean": high_mean,
        "frozen_high_minus_low": high_mean - low_mean,
    }


def analyze(rows: list[dict[str, Any]], protocol: dict[str, Any], source_commit: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    task_rows, task_runs = build_task_rows(rows, protocol)
    eligible = [row for row in task_rows if row["eligible_run_robust"]]
    train = [row["train_run_equal_retention"] for row in eligible]
    frozen = [row["frozen_run_equal_retention"] for row in eligible]
    rho = spearman(train, frozen)
    support = len(eligible) >= protocol["minimum_robust_tasks"]
    p_value = None
    interval = None
    loto: dict[str, float | None] = {}
    if support and rho is not None:
        p_value = permutation_p(
            train, frozen, rho, protocol["permutation_repetitions"], protocol["permutation_seed"]
        )
        interval = hierarchical_bootstrap(
            eligible, task_runs, protocol["bootstrap_repetitions"], protocol["bootstrap_seed"]
        )
        for index, row in enumerate(eligible):
            loto[row["task"]] = spearman(
                train[:index] + train[index + 1 :],
                frozen[:index] + frozen[index + 1 :],
            )
    finite_loto = [value for value in loto.values() if value is not None]
    min_loto = min(finite_loto) if loto and len(finite_loto) == len(loto) else None
    criteria = {
        "robust_tasks_ge_minimum": support,
        "primary_rho_ge_minimum": rho is not None and rho >= protocol["minimum_primary_rho"],
        "permutation_p_lt_alpha": p_value is not None and p_value < protocol["significance_alpha"],
        "hierarchical_bootstrap_valid_fraction_ge_minimum": interval is not None
        and interval["valid_fraction"] >= protocol["minimum_bootstrap_valid_fraction"],
        "hierarchical_bootstrap_lower_gt_zero": interval is not None
        and interval["lower"] is not None and interval["lower"] > 0,
        "all_loto_rho_gt_minimum": min_loto is not None and min_loto > protocol["minimum_loto_rho"],
    }
    status = STATUS_SUPPORT if not support else STATUS_PASS if all(criteria.values()) else STATUS_FAIL
    role_counts = Counter(row["role"] for row in rows)
    summary = {
        "protocol": PROTOCOL,
        "source_commit": source_commit,
        "status": status,
        "inputs": {
            "per_parent_sha256": protocol["input_per_parent_sha256"],
            "parent_rows": len(rows),
            "role_parent_counts": dict(sorted(role_counts.items())),
            "frozen_v1_task_universe": protocol["primary_task_ids"],
        },
        "support": {
            "frozen_v1_tasks": len(protocol["primary_task_ids"]),
            "run_robust_tasks": len(eligible),
            "run_robust_task_ids": [row["task"] for row in eligible],
            "minimum_train_runs_per_task": protocol["minimum_train_runs_per_task"],
            "minimum_frozen_runs_per_task": protocol["minimum_frozen_runs_per_task"],
        },
        "primary": {
            "metric": protocol["metric"],
            "spearman_rho": rho,
            "permutation_two_sided_p": p_value,
            "task_run_hierarchical_bootstrap_95_ci": interval,
            "leave_one_task_out_rho": loto,
            "minimum_leave_one_task_out_rho": min_loto,
        },
        "train_defined_tertile_contrast": tertile(eligible),
        "criteria": criteria,
        "claim_allowed": status == STATUS_PASS,
        "scope": {
            "post_result_robustness_not_new_confirmation": True,
            "candidate_code_read": False,
            "numeric_outcome_read": False,
            "pair_orientation_read": False,
            "prospective_outcome_read": False,
            "missing_at_random_claim": False,
            "causal_task_effect_claim": False,
            "predictor_or_search_utility_claim": False,
            "gpu_hours": 0,
            "api_calls": 0,
            "base_llm_updates": 0,
        },
    }
    return summary, task_rows


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=TASK_FIELDS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue().encode()


def write_output(output: Path, protocol_path: Path, input_path: Path, commit: str, summary: dict[str, Any], task_rows: list[dict[str, Any]]) -> None:
    if output.exists():
        raise RobustnessError("output exists")
    staging = output.with_name(f".{output.name}.tmp-{os.getpid()}")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        files = {
            "input_sha256.txt": (digest(input_path) + "\n").encode(),
            "per_task_run.csv": csv_bytes(task_rows),
            "protocol.json": protocol_path.read_bytes(),
            "source_commit.txt": (commit + "\n").encode(),
            "summary.json": json_bytes(summary),
        }
        for name, blob in files.items():
            (staging / name).write_bytes(blob)
        manifest = {name: hashlib.sha256(blob).hexdigest() for name, blob in sorted(files.items())}
        (staging / "sha256_manifest.json").write_bytes(json_bytes(manifest))
        staging.replace(output)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def run(args: argparse.Namespace) -> int:
    if not HEX40.fullmatch(args.source_commit):
        raise RobustnessError("invalid source commit")
    protocol_path = Path(args.protocol).resolve()
    input_path = Path(args.per_parent).resolve()
    protocol = load_protocol(protocol_path)
    rows = load_rows(input_path, protocol)
    summary, task_rows = analyze(rows, protocol, args.source_commit)
    write_output(Path(args.output).resolve(), protocol_path, input_path, args.source_commit, summary, task_rows)
    print(
        f"SOURCE_RETENTION_RUN_CLUSTER_COMPLETE status={summary['status']} "
        f"tasks={summary['support']['run_robust_tasks']} outcome_read=false"
    )
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--protocol", required=True)
    value.add_argument("--per-parent", required=True)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--output", required=True)
    return value


if __name__ == "__main__":
    raise SystemExit(run(parser().parse_args()))
