#!/usr/bin/env python3
"""Independent standard-library verifier for the task heterogeneity audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


AUDIT_PROTOCOL = "endpoint-budget-task-heterogeneity-audit-v1"
PUBLIC_PROTOCOL = "endpoint-budget-task-heterogeneity-public-v1"
PRIVATE_PROTOCOL = "endpoint-budget-task-heterogeneity-private-v1"
VERIFY_PROTOCOL = "endpoint-budget-task-heterogeneity-independent-verification-v1"
CLASSIFICATION = "EXPLORATORY_TASK_HETEROGENEITY_AUDIT_COMPLETE_NOT_CONFIRMATORY"
FOLD_SALT = "endpoint-label-efficiency-v1"
ARMS = ("exact_b_uniform_edge", "yield_guarded_breadth")
COVERAGE = ("selected_endpoints", "selected_runs", "induced_pairs")
METRICS = ("accuracy", "log_loss", "brier")


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def file_sha(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "object required")
    return value


def run_fold(run: str) -> int:
    value = hashlib.sha256((FOLD_SALT + "\0" + run).encode("utf-8")).digest()
    return int.from_bytes(value[:8], "big") % 5


def identity_sha(kind: str, value: str) -> str:
    return hashlib.sha256((kind + "\0" + value).encode("utf-8")).hexdigest()


def pair_sha(row: dict[str, str]) -> str:
    payload = {
        "endpoints": sorted((row["u"], row["v"])),
        "parent": row["parent"],
        "task": row["task"],
        "physical_run": row["physical_run"],
    }
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def ranks(values: Iterable[float]) -> list[float]:
    numbers = [float(value) for value in values]
    order = sorted(range(len(numbers)), key=lambda index: (numbers[index], index))
    output = [0.0] * len(numbers)
    start = 0
    while start < len(order):
        stop = start + 1
        while stop < len(order) and numbers[order[stop]] == numbers[order[start]]:
            stop += 1
        value = (start + 1 + stop) / 2.0
        for position in range(start, stop):
            output[order[position]] = value
        start = stop
    return output


def rho(left: Iterable[float], right: Iterable[float]) -> float | None:
    x, y = ranks(left), ranks(right)
    require(len(x) == len(y) and len(x) > 1, "correlation support")
    xbar, ybar = sum(x) / len(x), sum(y) / len(y)
    dx, dy = [value - xbar for value in x], [value - ybar for value in y]
    xx, yy = sum(value * value for value in dx), sum(value * value for value in dy)
    if xx == 0.0 or yy == 0.0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / math.sqrt(xx * yy)


def signs(values: Iterable[int | float]) -> dict[str, int]:
    result = {"negative": 0, "zero": 0, "positive": 0}
    for value in values:
        result["negative" if value < 0 else "positive" if value > 0 else "zero"] += 1
    return result


def reduced_ratio(numerator: int, denominator: int) -> dict[str, Any]:
    divisor = math.gcd(numerator, denominator)
    return {
        "numerator": numerator // divisor,
        "denominator": denominator // divisor,
        "decimal_17g": format(numerator / denominator, ".17g"),
    }


def reconstruct(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    protocol_path = args.protocol.resolve()
    require(file_sha(protocol_path) == args.protocol_sha256, "protocol SHA")
    protocol = load(protocol_path)
    require(protocol.get("protocol") == AUDIT_PROTOCOL, "protocol name")
    require(
        protocol.get("status") == "FROZEN_AFTER_SMOKE_AGGREGATE_READOUT_BEFORE_TASK_LEVEL_READOUT",
        "freeze status",
    )
    bindings = protocol["input_bindings"]
    path_map = {
        "firewall_receipt": args.firewall_receipt.resolve(),
        "train_only_topology": args.train_topology.resolve(),
        "selection_public": args.selection_public.resolve(),
        "selection_private": args.selection_private.resolve(),
        "fit_summary": args.fit_summary.resolve(),
        "private_pair_witness": args.private_pairs.resolve(),
    }
    for name, path in path_map.items():
        require(file_sha(path) == bindings[f"{name}_sha256"], f"input SHA {name}")
    for name in ("train_only_topology", "selection_private", "private_pair_witness"):
        require(os.name == "nt" or path_map[name].stat().st_mode & 0o077 == 0, f"private mode {name}")
    source = {name: load(path) for name, path in path_map.items()}
    require(source["firewall_receipt"]["scope"]["senior_test_rows_exported"] == 0, "firewall")
    require(source["fit_summary"]["classification"].endswith("DOES_NOT_ADVANCE"), "smoke status")

    topology = source["train_only_topology"]["rows"]
    require(len(topology) == 539, "topology size")
    train = [row for row in topology if run_fold(row["physical_run"]) != 0]
    evaluation = [row for row in topology if run_fold(row["physical_run"]) == 0]
    require((len(train), len(evaluation)) == (401, 138), "split size")
    expected_eval = {
        pair_sha(row): (
            identity_sha("task", row["task"]),
            identity_sha("physical_run", row["physical_run"]),
        )
        for row in evaluation
    }
    require(len(expected_eval) == 138, "eval uniqueness")

    cells: dict[tuple[str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in source["private_pair_witness"]["rows"]:
        cell = (row["arm"], int(row["endpoint_budget"]))
        pair = row["pair_identity_sha256"]
        require(cell[0] in ARMS and cell[1] in (96, 192), "cell")
        require(pair in expected_eval and pair not in cells[cell], "pair closure")
        require((row["task_sha256"], row["physical_run_sha256"]) == expected_eval[pair], "pair fingerprints")
        probability = float(row["probability_first_better"])
        require(math.isfinite(probability) and 0.0 <= probability <= 1.0, "probability")
        cells[cell][pair] = row
    expected_cells = {(arm, budget) for arm in ARMS for budget in (96, 192)}
    require(set(cells) == expected_cells, "witness cells")
    require(all(set(value) == set(expected_eval) for value in cells.values()), "witness pair sets")

    endpoint_meta: dict[str, tuple[str, str]] = {}
    for row in train:
        require(row["source_split"] == "train" and row["u"] < row["v"], "train topology")
        for endpoint in (row["u"], row["v"]):
            meta = (row["task"], row["physical_run"])
            require(endpoint not in endpoint_meta or endpoint_meta[endpoint] == meta, "endpoint metadata")
            endpoint_meta[endpoint] = meta
    available = Counter(identity_sha("task", row["task"]) for row in train)

    selections: dict[tuple[str, int], set[str]] = {}
    for arm in ARMS:
        for entry in source["selection_private"]["arms"][arm]:
            budget = int(entry["budget"])
            endpoints = set(entry["endpoint_ids"])
            require(len(endpoints) == budget and all(endpoint in endpoint_meta for endpoint in endpoints), "selection")
            selections[(arm, budget)] = endpoints
    require(all(cell in selections for cell in expected_cells), "fit selections")

    coverage: dict[tuple[str, int], dict[str, Any]] = {}
    for cell in sorted(expected_cells):
        endpoints = selections[cell]
        endpoint_counts: Counter[str] = Counter()
        run_sets: dict[str, set[str]] = defaultdict(set)
        for endpoint in endpoints:
            task, run = endpoint_meta[endpoint]
            task_hash = identity_sha("task", task)
            endpoint_counts[task_hash] += 1
            run_sets[task_hash].add(identity_sha("physical_run", run))
        closed = [row for row in train if row["u"] in endpoints and row["v"] in endpoints]
        coverage[cell] = {
            "selected_endpoints": endpoint_counts,
            "selected_runs": Counter({task: len(values) for task, values in run_sets.items()}),
            "induced_pairs": Counter(identity_sha("task", row["task"]) for row in closed),
            "totals": {
                "selected_endpoints": len(endpoints),
                "selected_runs": len({endpoint_meta[endpoint][1] for endpoint in endpoints}),
                "induced_pairs": len(closed),
            },
        }

    tasks = sorted({value[0] for value in expected_eval.values()})
    require(len(tasks) == 20, "eval tasks")
    private_rows: list[dict[str, Any]] = []
    public_budgets: dict[str, Any] = {}
    for budget in (96, 192):
        per_task: list[dict[str, Any]] = []
        for task in tasks:
            pairs = sorted(pair for pair, value in expected_eval.items() if value[0] == task)
            net, loss, brier = 0, 0.0, 0.0
            for pair in pairs:
                pu = float(cells[("exact_b_uniform_edge", budget)][pair]["probability_first_better"])
                py = float(cells[("yield_guarded_breadth", budget)][pair]["probability_first_better"])
                net += int(py > 0.5) - int(pu > 0.5)
                cu, cy = min(max(pu, 1e-15), 1 - 1e-15), min(max(py, 1e-15), 1 - 1e-15)
                loss += -math.log(cy) + math.log(cu)
                brier += (1 - py) ** 2 - (1 - pu) ** 2
            count = len(pairs)
            row: dict[str, Any] = {
                "endpoint_budget": budget,
                "task_sha256": task,
                "evaluation_pairs": count,
                "net_correct_contribution": net,
                "evaluation_metric_delta_yield_minus_uniform": {
                    "accuracy": net / count,
                    "log_loss": loss / count,
                    "brier": brier / count,
                },
                "outer_train_available_pairs": int(available.get(task, 0)),
                "coverage": {},
                "coverage_delta_yield_minus_uniform": {},
            }
            for arm in ARMS:
                row["coverage"][arm] = {
                    name: int(coverage[(arm, budget)][name].get(task, 0)) for name in COVERAGE
                }
            for name in COVERAGE:
                row["coverage_delta_yield_minus_uniform"][name] = (
                    row["coverage"]["yield_guarded_breadth"][name]
                    - row["coverage"]["exact_b_uniform_edge"][name]
                )
            per_task.append(row)
            private_rows.append(row)

        total_pairs = sum(row["evaluation_pairs"] for row in per_task)
        total_net = sum(row["net_correct_contribution"] for row in per_task)
        metric_values = {
            metric: [row["evaluation_metric_delta_yield_minus_uniform"][metric] for row in per_task]
            for metric in METRICS
        }
        coverage_values = {
            name: [row["coverage_delta_yield_minus_uniform"][name] for row in per_task]
            for name in COVERAGE
        }
        loto = [
            (total_net - row["net_correct_contribution"]) / (total_pairs - row["evaluation_pairs"])
            for row in per_task
        ]
        positive = sorted(
            (row["net_correct_contribution"] for row in per_task if row["net_correct_contribution"] > 0),
            reverse=True,
        )
        positive_total = sum(positive)
        distribution: dict[str, Any] = {}
        available_total = sum(available.values())
        for arm in ARMS:
            induced = coverage[(arm, budget)]["induced_pairs"]
            induced_total = sum(induced.values())
            maximum = max(induced.values())
            distribution[arm] = {
                **coverage[(arm, budget)]["totals"],
                "induced_pair_task_l1_to_outer_train_availability": sum(
                    abs(induced.get(task, 0) / induced_total - available[task] / available_total)
                    for task in sorted(available)
                ),
                "maximum_single_task_induced_pair_share": reduced_ratio(maximum, induced_total),
                "represented_tasks_by_induced_pair": sum(value > 0 for value in induced.values()),
            }
        public_budgets[str(budget)] = {
            "evaluation_pairs": total_pairs,
            "evaluation_tasks": len(per_task),
            "overall_accuracy_delta_yield_minus_uniform": total_net / total_pairs,
            "task_macro_metric_delta_yield_minus_uniform": {
                metric: statistics.fmean(metric_values[metric]) for metric in METRICS
            },
            "task_net_correct_sign_counts": signs(row["net_correct_contribution"] for row in per_task),
            "coverage_delta_task_sign_counts": {
                name: signs(coverage_values[name]) for name in COVERAGE
            },
            "coverage_metric_spearman": {
                name: {metric: rho(coverage_values[name], metric_values[metric]) for metric in METRICS}
                for name in COVERAGE
            },
            "leave_one_task_out_accuracy_delta": {
                "minimum": min(loto),
                "median": statistics.median(loto),
                "maximum": max(loto),
                "sign_counts": signs(loto),
            },
            "gain_concentration": {
                "positive_contribution_total": positive_total,
                "negative_contribution_total": sum(
                    row["net_correct_contribution"] for row in per_task if row["net_correct_contribution"] < 0
                ),
                "largest_positive_share": positive[0] / positive_total if positive_total else None,
                "two_largest_positive_share": sum(positive[:2]) / positive_total if positive_total else None,
                "positive_contribution_hhi": (
                    sum((value / positive_total) ** 2 for value in positive) if positive_total else None
                ),
            },
            "train_distribution": distribution,
        }

    actual_private = load(args.private_result.resolve())
    analysis_commit = actual_private["analysis_source_commit"]
    require(len(analysis_commit) == 40 and all(c in "0123456789abcdef" for c in analysis_commit), "analysis commit")
    expected_private = {
        "protocol": PRIVATE_PROTOCOL,
        "protocol_sha256": args.protocol_sha256,
        "analysis_source_commit": analysis_commit,
        "artifact_source_commit": bindings["artifact_source_commit"],
        "raw_identities_emitted": False,
        "task_hashes_emitted_privately": True,
        "rows": private_rows,
    }
    require(canonical_bytes(actual_private) == canonical_bytes(expected_private), "private reconstruction")
    private_sha = file_sha(args.private_result.resolve())

    expected_public = {
        "protocol": PUBLIC_PROTOCOL,
        "protocol_sha256": args.protocol_sha256,
        "analysis_source_commit": analysis_commit,
        "artifact_source_commit": bindings["artifact_source_commit"],
        "input_sha256": bindings,
        "scope": {
            "historical_development_only": True,
            "single_outer_fold": 0,
            "senior_test_rows_used": False,
            "prospective_values_used": False,
            "gpu_api_model_fit_base_update": "0/0/0/0",
            "public_task_run_pair_identities_or_hashes_emitted": False,
            "may_rescue_failed_smoke": False,
        },
        "population": {
            "outer_train_pairs": len(train),
            "outer_train_tasks": len(available),
            "outer_eval_pairs": len(evaluation),
            "outer_eval_tasks": len(tasks),
        },
        "by_budget": public_budgets,
        "private_witness_sha256": private_sha,
        "classification": CLASSIFICATION,
        "interpretation": {
            "confirmatory_efficacy_claim_allowed": False,
            "task_removal_or_reweighting_allowed": False,
            "existing_two_arm_rule_may_scale": False,
            "separately_frozen_task_quota_rule_may_be_designed": True,
        },
        "status": "COMPLETE",
    }
    actual_public = load(args.public_result.resolve())
    require(canonical_bytes(actual_public) == canonical_bytes(expected_public), "public reconstruction")
    return actual_public, actual_private


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(canonical_bytes(value))


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    for name in (
        "protocol", "firewall-receipt", "train-topology", "selection-public",
        "selection-private", "fit-summary", "private-pairs", "public-result",
        "private-result", "output",
    ):
        value.add_argument(f"--{name}", type=Path, required=True)
    value.add_argument("--protocol-sha256", required=True)
    return value


def main() -> None:
    args = parser().parse_args()
    public, private = reconstruct(args)
    result = {
        "protocol": VERIFY_PROTOCOL,
        "protocol_sha256": args.protocol_sha256,
        "analysis_source_commit": public["analysis_source_commit"],
        "public_result_sha256": file_sha(args.public_result.resolve()),
        "private_result_sha256": file_sha(args.private_result.resolve()),
        "task_rows_reconstructed_exact": len(private["rows"]),
        "all_aggregate_fields_equal": True,
        "producer_module_imported": False,
        "model_refits": 0,
        "scope": {
            "historical_train_rows_only": True,
            "senior_test_rows_used": False,
            "prospective_values_used": False,
            "gpu_api_model_fit_base_update": "0/0/0/0",
        },
        "status": "INDEPENDENT_TASK_AND_AGGREGATE_RECONSTRUCTION_EXACT",
    }
    write_exclusive(args.output.resolve(), result)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
