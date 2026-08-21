#!/usr/bin/env python3
"""Audit whether task-level source retention transports from train to frozen runs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence


PROTOCOL = "source-retention-transport-v1"
STATUS_PASS = "VERIFIED_TASK_CONDITIONED_SOURCE_RETENTION_TRANSPORT"
STATUS_FAIL = "NO_VERIFIED_SOURCE_RETENTION_TRANSPORT"
STATUS_SUPPORT = "INSUFFICIENT_TASK_SUPPORT"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-(?:ws-)?[A-Za-z0-9._-]{16,}|"
    rb"hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    rb"AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|"
    rb"Bearer\s+[A-Za-z0-9._~-]{20,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
ROLES = ("train", "frozen", "extension")
UPSTREAM_FIELDS = (
    "role",
    "task",
    "run_id",
    "parent",
    "pair_rows",
    "unique_edges",
    "published_endpoint_count",
    "declared_set_size",
    "raw_card_child_count",
    "finite_card_child_count",
    "source_declared_size",
    "source_size_consistent",
    "source_size_not_smaller_than_raw",
    "raw_context_consistent",
    "endpoints_all_finite",
    "endpoint_fidelity",
    "declared_matches_finite",
    "finite_endpoint_coverage",
    "pair_graph_coverage_over_finite",
    "raw_source_retention",
    "finite_source_retention",
    "raw_equals_source",
    "finite_equals_source",
    "parent_card_present",
    "parent_context_consistent",
    "parent_children_declared_count",
    "parent_children_contains_raw",
    "source_size_gt_five",
)
TASK_FIELDS = (
    "task",
    "train_parents",
    "frozen_parents",
    "extension_parents",
    "eligible_primary",
    "train_finite_source_retention",
    "frozen_finite_source_retention",
    "extension_finite_source_retention",
    "train_raw_source_retention",
    "frozen_raw_source_retention",
    "extension_raw_source_retention",
    "train_parent_present_share",
    "frozen_parent_present_share",
    "extension_parent_present_share",
)


class TransportError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_file(path: Path) -> None:
    overlap = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            payload = overlap + chunk
            if CREDENTIAL.search(payload):
                raise TransportError(f"credential-shaped bytes refused in {path.name}")
            overlap = payload[-256:]


def load_protocol(path: Path) -> dict[str, Any]:
    scan_file(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("protocol") != PROTOCOL:
        raise TransportError("invalid protocol")
    required_ints = (
        "bootstrap_repetitions",
        "bootstrap_seed",
        "expected_parent_rows",
        "minimum_common_tasks",
        "minimum_frozen_parents_per_task",
        "minimum_train_parents_per_task",
        "permutation_repetitions",
        "permutation_seed",
    )
    for key in required_ints:
        item = value.get(key)
        if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
            raise TransportError(f"invalid protocol integer: {key}")
    for key in (
        "minimum_bootstrap_valid_fraction",
        "minimum_loto_rho",
        "minimum_primary_rho",
        "significance_alpha",
    ):
        item = value.get(key)
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)):
            raise TransportError(f"invalid protocol float: {key}")
    expected_sha = value.get("input_per_parent_sha256")
    expected_roles = value.get("expected_role_parent_counts")
    if not isinstance(expected_sha, str) or not SHA256.fullmatch(expected_sha):
        raise TransportError("invalid input SHA in protocol")
    if (
        not isinstance(expected_roles, dict)
        or set(expected_roles) != set(ROLES)
        or any(
            isinstance(count, bool) or not isinstance(count, int) or count < 0
            for count in expected_roles.values()
        )
        or sum(expected_roles.values()) != value["expected_parent_rows"]
    ):
        raise TransportError("invalid frozen role counts")
    if value.get("metric") != "finite_source_retention":
        raise TransportError("unexpected primary metric")
    if not (0 < float(value["significance_alpha"]) < 1):
        raise TransportError("invalid alpha")
    if not (0 < float(value["minimum_bootstrap_valid_fraction"]) <= 1):
        raise TransportError("invalid bootstrap valid fraction")
    return value


def parse_bool(value: str, where: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise TransportError(f"invalid boolean at {where}")


def parse_int(value: str, where: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise TransportError(f"invalid integer at {where}") from exc
    if result < 0:
        raise TransportError(f"negative integer at {where}")
    return result


def parse_float(value: str, where: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise TransportError(f"invalid float at {where}") from exc
    if not math.isfinite(result):
        raise TransportError(f"non-finite float at {where}")
    return result


def load_rows(path: Path, protocol: dict[str, Any]) -> list[dict[str, Any]]:
    if sha256_file(path) != protocol["input_per_parent_sha256"]:
        raise TransportError("per-parent input SHA mismatch")
    scan_file(path)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != UPSTREAM_FIELDS:
            raise TransportError("per-parent fields mismatch")
        for line_number, raw in enumerate(reader, 2):
            role = raw["role"]
            task = raw["task"]
            run_id = raw["run_id"]
            parent = raw["parent"]
            if role not in ROLES or not task or not run_id or not parent:
                raise TransportError(f"invalid identity at row {line_number}")
            key = (role, parent)
            if key in seen:
                raise TransportError(f"duplicate role-parent at row {line_number}")
            seen.add(key)
            source_size = parse_int(raw["source_declared_size"], f"row {line_number}:source")
            raw_count = parse_int(raw["raw_card_child_count"], f"row {line_number}:raw")
            finite_count = parse_int(raw["finite_card_child_count"], f"row {line_number}:finite")
            if source_size <= 0 or not (0 <= finite_count <= raw_count <= source_size):
                raise TransportError(f"invalid source counts at row {line_number}")
            raw_retention = parse_float(raw["raw_source_retention"], f"row {line_number}:raw_retention")
            finite_retention = parse_float(
                raw["finite_source_retention"], f"row {line_number}:finite_retention"
            )
            if not (0 <= raw_retention <= 1 and 0 <= finite_retention <= 1):
                raise TransportError(f"retention outside [0,1] at row {line_number}")
            if not math.isclose(raw_retention, raw_count / source_size, abs_tol=1e-12):
                raise TransportError(f"raw retention/count mismatch at row {line_number}")
            if not math.isclose(finite_retention, finite_count / source_size, abs_tol=1e-12):
                raise TransportError(f"finite retention/count mismatch at row {line_number}")
            structural = {
                name: parse_bool(raw[name], f"row {line_number}:{name}")
                for name in (
                    "source_size_consistent",
                    "source_size_not_smaller_than_raw",
                    "raw_context_consistent",
                    "endpoints_all_finite",
                    "endpoint_fidelity",
                    "declared_matches_finite",
                    "parent_card_present",
                    "parent_context_consistent",
                    "parent_children_contains_raw",
                )
            }
            mandatory = (
                "source_size_consistent",
                "source_size_not_smaller_than_raw",
                "raw_context_consistent",
                "endpoints_all_finite",
                "endpoint_fidelity",
                "declared_matches_finite",
                "parent_context_consistent",
            )
            if not all(structural[name] for name in mandatory):
                raise TransportError(f"upstream structural gate failed at row {line_number}")
            if structural["parent_card_present"] and not structural["parent_children_contains_raw"]:
                raise TransportError(f"parent child declaration failed at row {line_number}")
            rows.append(
                {
                    "role": role,
                    "task": task,
                    "run_id": run_id,
                    "parent": parent,
                    "finite_source_retention": finite_retention,
                    "raw_source_retention": raw_retention,
                    "parent_card_present": structural["parent_card_present"],
                }
            )
    if len(rows) != int(protocol["expected_parent_rows"]):
        raise TransportError("per-parent row count mismatch")
    role_counts = Counter(row["role"] for row in rows)
    if dict(sorted(role_counts.items())) != protocol["expected_role_parent_counts"]:
        raise TransportError("role parent counts mismatch")
    return rows


def mean(values: Sequence[float]) -> float:
    if not values:
        raise TransportError("mean of empty sequence")
    return sum(values) / len(values)


def average_ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        rank = (start + 1 + end) / 2.0
        for position in range(start, end):
            ranks[order[position]] = rank
        start = end
    return ranks


def pearson(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    left_mean = mean(left)
    right_mean = mean(right)
    left_ss = sum((value - left_mean) ** 2 for value in left)
    right_ss = sum((value - right_mean) ** 2 for value in right)
    if left_ss <= 0 or right_ss <= 0:
        return None
    numerator = sum(
        (left[index] - left_mean) * (right[index] - right_mean)
        for index in range(len(left))
    )
    return numerator / math.sqrt(left_ss * right_ss)


def spearman(left: Sequence[float], right: Sequence[float]) -> float | None:
    return pearson(average_ranks(left), average_ranks(right))


def quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise TransportError("quantile of empty sequence")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def permutation_p(
    left: Sequence[float],
    right: Sequence[float],
    observed: float,
    repetitions: int,
    seed: int,
) -> float:
    rng = random.Random(seed)
    permuted = list(right)
    extreme = 0
    threshold = abs(observed) - 1e-15
    for _ in range(repetitions):
        rng.shuffle(permuted)
        value = spearman(left, permuted)
        if value is not None and abs(value) >= threshold:
            extreme += 1
    return (extreme + 1) / (repetitions + 1)


def paired_bootstrap(
    left: Sequence[float],
    right: Sequence[float],
    repetitions: int,
    seed: int,
) -> dict[str, Any]:
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(repetitions):
        indices = [rng.randrange(len(left)) for _ in range(len(left))]
        value = spearman([left[index] for index in indices], [right[index] for index in indices])
        if value is not None:
            estimates.append(value)
    return {
        "lower": quantile(estimates, 0.025) if estimates else None,
        "upper": quantile(estimates, 0.975) if estimates else None,
        "valid_replicates": len(estimates),
        "valid_fraction": len(estimates) / repetitions,
    }


def aggregate_tasks(rows: Sequence[dict[str, Any]], protocol: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: {role: [] for role in ROLES}
    )
    for row in rows:
        grouped[row["task"]][row["role"]].append(row)
    output: list[dict[str, Any]] = []
    for task in sorted(grouped):
        roles = grouped[task]
        item: dict[str, Any] = {"task": task}
        for role in ROLES:
            role_rows = roles[role]
            item[f"{role}_parents"] = len(role_rows)
            for metric in ("finite_source_retention", "raw_source_retention"):
                item[f"{role}_{metric}"] = (
                    mean([float(row[metric]) for row in role_rows]) if role_rows else None
                )
            item[f"{role}_parent_present_share"] = (
                mean([float(bool(row["parent_card_present"])) for row in role_rows])
                if role_rows
                else None
            )
        item["eligible_primary"] = (
            item["train_parents"] >= protocol["minimum_train_parents_per_task"]
            and item["frozen_parents"] >= protocol["minimum_frozen_parents_per_task"]
        )
        output.append(item)
    return output


def profile_correlation(
    task_rows: Sequence[dict[str, Any]], metric: str, parent_present_only: bool = False
) -> dict[str, Any]:
    selected = [row for row in task_rows if row["eligible_primary"]]
    tasks: list[str] = []
    train: list[float] = []
    frozen: list[float] = []
    for row in selected:
        if parent_present_only:
            # This sensitivity is filled from separately aggregated rows.
            train_key = "train_parent_present_finite_source_retention"
            frozen_key = "frozen_parent_present_finite_source_retention"
        else:
            train_key = f"train_{metric}"
            frozen_key = f"frozen_{metric}"
        if row.get(train_key) is None or row.get(frozen_key) is None:
            continue
        tasks.append(str(row["task"]))
        train.append(float(row[train_key]))
        frozen.append(float(row[frozen_key]))
    return {"tasks": tasks, "train": train, "frozen": frozen, "rho": spearman(train, frozen)}


def add_parent_present_sensitivity(
    task_rows: list[dict[str, Any]], rows: Sequence[dict[str, Any]]
) -> None:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        if row["parent_card_present"]:
            grouped[(row["task"], row["role"])].append(float(row["finite_source_retention"]))
    for task_row in task_rows:
        for role in ("train", "frozen"):
            values = grouped[(task_row["task"], role)]
            task_row[f"{role}_parent_present_finite_source_retention"] = (
                mean(values) if values else None
            )


def tertile_contrast(eligible: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    if len(eligible) < 6:
        return None
    ordered = sorted(
        eligible,
        key=lambda row: (float(row["train_finite_source_retention"]), str(row["task"])),
    )
    width = len(ordered) // 3
    low = ordered[:width]
    high = ordered[-width:]
    low_frozen = mean([float(row["frozen_finite_source_retention"]) for row in low])
    high_frozen = mean([float(row["frozen_finite_source_retention"]) for row in high])
    return {
        "tertile_width": width,
        "train_defined_low_tasks": [str(row["task"]) for row in low],
        "train_defined_high_tasks": [str(row["task"]) for row in high],
        "frozen_low_task_equal_mean": low_frozen,
        "frozen_high_task_equal_mean": high_frozen,
        "frozen_high_minus_low": high_frozen - low_frozen,
    }


def analyze(rows: Sequence[dict[str, Any]], protocol: dict[str, Any], source_commit: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    task_rows = aggregate_tasks(rows, protocol)
    add_parent_present_sensitivity(task_rows, rows)
    eligible = [row for row in task_rows if row["eligible_primary"]]
    support_ok = len(eligible) >= int(protocol["minimum_common_tasks"])
    primary = profile_correlation(task_rows, "finite_source_retention")
    rho = primary["rho"]
    permutation = None
    bootstrap = None
    loto: dict[str, float | None] = {}
    if support_ok and rho is not None:
        permutation = permutation_p(
            primary["train"],
            primary["frozen"],
            rho,
            int(protocol["permutation_repetitions"]),
            int(protocol["permutation_seed"]),
        )
        bootstrap = paired_bootstrap(
            primary["train"],
            primary["frozen"],
            int(protocol["bootstrap_repetitions"]),
            int(protocol["bootstrap_seed"]),
        )
        for index, task in enumerate(primary["tasks"]):
            loto[task] = spearman(
                primary["train"][:index] + primary["train"][index + 1 :],
                primary["frozen"][:index] + primary["frozen"][index + 1 :],
            )
    finite_loto = [float(value) for value in loto.values() if value is not None]
    min_loto = min(finite_loto) if len(finite_loto) == len(loto) and loto else None
    alpha = float(protocol["significance_alpha"])
    criteria = {
        "eligible_common_tasks_ge_minimum": support_ok,
        "primary_rho_ge_minimum": rho is not None and rho >= float(protocol["minimum_primary_rho"]),
        "permutation_p_lt_alpha": permutation is not None and permutation < alpha,
        "bootstrap_valid_fraction_ge_minimum": bootstrap is not None
        and bootstrap["valid_fraction"] >= float(protocol["minimum_bootstrap_valid_fraction"]),
        "bootstrap_lower_gt_zero": bootstrap is not None
        and bootstrap["lower"] is not None
        and bootstrap["lower"] > 0,
        "all_loto_rho_gt_minimum": min_loto is not None
        and min_loto > float(protocol["minimum_loto_rho"]),
    }
    if not support_ok:
        status = STATUS_SUPPORT
    elif all(criteria.values()):
        status = STATUS_PASS
    else:
        status = STATUS_FAIL
    raw_profile = profile_correlation(task_rows, "raw_source_retention")
    parent_profile = profile_correlation(
        task_rows, "finite_source_retention", parent_present_only=True
    )
    role_counts = Counter(row["role"] for row in rows)
    role_runs = {
        role: len({row["run_id"] for row in rows if row["role"] == role}) for role in ROLES
    }
    summary = {
        "protocol": PROTOCOL,
        "source_commit": source_commit,
        "status": status,
        "inputs": {
            "per_parent_sha256": protocol["input_per_parent_sha256"],
            "parent_rows": len(rows),
            "role_parent_counts": dict(sorted(role_counts.items())),
            "role_run_counts": role_runs,
        },
        "support": {
            "all_tasks": len(task_rows),
            "eligible_common_tasks": len(eligible),
            "eligible_task_ids": primary["tasks"],
            "minimum_train_parents_per_task": protocol["minimum_train_parents_per_task"],
            "minimum_frozen_parents_per_task": protocol["minimum_frozen_parents_per_task"],
        },
        "primary": {
            "metric": protocol["metric"],
            "spearman_rho": rho,
            "permutation_two_sided_p": permutation,
            "bootstrap_95_ci": bootstrap,
            "leave_one_task_out_rho": loto,
            "minimum_leave_one_task_out_rho": min_loto,
        },
        "train_defined_tertile_contrast": tertile_contrast(eligible),
        "sensitivities": {
            "raw_source_retention_spearman_rho": raw_profile["rho"],
            "parent_present_only_finite_retention_spearman_rho": parent_profile["rho"],
            "parent_present_only_tasks": parent_profile["tasks"],
        },
        "criteria": criteria,
        "claim_allowed": status == STATUS_PASS,
        "scope": {
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
        },
    }
    return summary, task_rows


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def task_csv_bytes(rows: Iterable[dict[str, Any]]) -> bytes:
    import io

    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=TASK_FIELDS, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue().encode("utf-8")


def write_artifact(
    output: Path,
    protocol_path: Path,
    input_path: Path,
    source_commit: str,
    summary: dict[str, Any],
    task_rows: list[dict[str, Any]],
) -> None:
    if output.exists():
        raise TransportError("output already exists")
    staging = output.with_name(f".{output.name}.tmp-{os.getpid()}")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        files = {
            "input_sha256.txt": (sha256_file(input_path) + "\n").encode(),
            "per_task.csv": task_csv_bytes(task_rows),
            "protocol.json": protocol_path.read_bytes(),
            "source_commit.txt": (source_commit + "\n").encode(),
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
    protocol_path = Path(args.protocol).resolve()
    input_path = Path(args.per_parent).resolve()
    output = Path(args.output).resolve()
    if not HEX40.fullmatch(args.source_commit):
        raise TransportError("source commit must be full lowercase Git SHA")
    protocol = load_protocol(protocol_path)
    rows = load_rows(input_path, protocol)
    summary, task_rows = analyze(rows, protocol, args.source_commit)
    write_artifact(output, protocol_path, input_path, args.source_commit, summary, task_rows)
    print(
        f"SOURCE_RETENTION_TRANSPORT_COMPLETE status={summary['status']} "
        f"eligible_tasks={summary['support']['eligible_common_tasks']} "
        f"outcome_read=false"
    )
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--protocol", required=True)
    result.add_argument("--per-parent", required=True)
    result.add_argument("--source-commit", required=True)
    result.add_argument("--output", required=True)
    return result


if __name__ == "__main__":
    raise SystemExit(run(parser().parse_args()))
