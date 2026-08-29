#!/usr/bin/env python3
"""Frozen, historical-only task heterogeneity audit for endpoint acquisition.

The public output contains aggregates only.  Raw identities, hashed task identities,
and per-pair probabilities remain in the mode-0600 private witness.
"""

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


PROTOCOL = "endpoint-budget-task-heterogeneity-audit-v1"
PUBLIC_PROTOCOL = "endpoint-budget-task-heterogeneity-public-v1"
PRIVATE_PROTOCOL = "endpoint-budget-task-heterogeneity-private-v1"
CLASSIFICATION = "EXPLORATORY_TASK_HETEROGENEITY_AUDIT_COMPLETE_NOT_CONFIRMATORY"
FOLD_SALT = "endpoint-label-efficiency-v1"
ARMS = ("exact_b_uniform_edge", "yield_guarded_breadth")
METRIC_NAMES = ("accuracy", "log_loss", "brier")
COVERAGE_NAMES = ("selected_endpoints", "selected_runs", "induced_pairs")


class AuditError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


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


def object_file(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def private_mode(path: Path) -> bool:
    return os.name == "nt" or path.stat().st_mode & 0o077 == 0


def run_fold(run: str) -> int:
    digest = hashlib.sha256((FOLD_SALT + "\0" + run).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % 5


def identity_sha(kind: str, value: str) -> str:
    return hashlib.sha256((kind + "\0" + value).encode("utf-8")).hexdigest()


def pair_sha(row: dict[str, str]) -> str:
    value = {
        "endpoints": sorted((row["u"], row["v"])),
        "parent": row["parent"],
        "task": row["task"],
        "physical_run": row["physical_run"],
    }
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def average_ranks(values: Iterable[float]) -> list[float]:
    items = [float(value) for value in values]
    order = sorted(range(len(items)), key=lambda index: (items[index], index))
    ranks = [0.0] * len(items)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and items[order[end]] == items[order[cursor]]:
            end += 1
        average = (cursor + 1 + end) / 2.0
        for position in range(cursor, end):
            ranks[order[position]] = average
        cursor = end
    return ranks


def spearman(left: Iterable[float], right: Iterable[float]) -> float | None:
    x = average_ranks(left)
    y = average_ranks(right)
    require(len(x) == len(y) and len(x) > 1, "correlation support")
    x_mean = sum(x) / len(x)
    y_mean = sum(y) / len(y)
    x_centered = [value - x_mean for value in x]
    y_centered = [value - y_mean for value in y]
    x_ss = sum(value * value for value in x_centered)
    y_ss = sum(value * value for value in y_centered)
    if x_ss == 0.0 or y_ss == 0.0:
        return None
    return sum(a * b for a, b in zip(x_centered, y_centered)) / math.sqrt(x_ss * y_ss)


def sign_counts(values: Iterable[int | float]) -> dict[str, int]:
    output = {"negative": 0, "zero": 0, "positive": 0}
    for value in values:
        if value < 0:
            output["negative"] += 1
        elif value > 0:
            output["positive"] += 1
        else:
            output["zero"] += 1
    return output


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    require(denominator > 0, "ratio denominator")
    divisor = math.gcd(numerator, denominator)
    return {
        "numerator": numerator // divisor,
        "denominator": denominator // divisor,
        "decimal_17g": format(numerator / denominator, ".17g"),
    }


def load_and_validate(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    protocol_path = args.protocol.resolve()
    require(file_sha(protocol_path) == args.protocol_sha256, "audit protocol SHA")
    protocol = object_file(protocol_path)
    require(protocol.get("protocol") == PROTOCOL, "audit protocol name")
    require(
        protocol.get("status")
        == "FROZEN_AFTER_SMOKE_AGGREGATE_READOUT_BEFORE_TASK_LEVEL_READOUT",
        "audit freeze status",
    )
    known = protocol["known_before_freeze"]
    for key in (
        "task_level_sign_counts_seen",
        "task_level_coverage_deltas_seen",
        "task_level_metric_deltas_seen",
        "coverage_metric_correlations_seen",
        "leave_one_task_out_distribution_seen",
        "positive_gain_concentration_seen",
    ):
        require(known[key] is False, f"result already seen: {key}")
    require(protocol["resources"] == {
        "gpu": 0,
        "paid_api_calls": 0,
        "critic_model_fits": 0,
        "base_model_updates": 0,
        "expected_cpu_minutes": "less than 5",
    }, "resource contract")

    paths = {
        "firewall_receipt": args.firewall_receipt.resolve(),
        "train_only_topology": args.train_topology.resolve(),
        "selection_public": args.selection_public.resolve(),
        "selection_private": args.selection_private.resolve(),
        "fit_summary": args.fit_summary.resolve(),
        "private_pair_witness": args.private_pairs.resolve(),
    }
    bindings = protocol["input_bindings"]
    for key, path in paths.items():
        require(file_sha(path) == bindings[f"{key}_sha256"], f"input SHA: {key}")
    for key in ("train_only_topology", "selection_private", "private_pair_witness"):
        require(private_mode(paths[key]), f"private mode: {key}")

    values = {key: object_file(path) for key, path in paths.items()}
    artifact_commit = bindings["artifact_source_commit"]
    require(len(args.analysis_source_commit) == 40, "analysis source commit length")
    require(all(character in "0123456789abcdef" for character in args.analysis_source_commit), "analysis source commit hex")
    require(
        values["train_only_topology"].get("source_commit")
        == values["fit_summary"].get("source_commit")
        == values["private_pair_witness"].get("source_commit")
        == artifact_commit,
        "artifact source commit",
    )
    require(
        values["firewall_receipt"].get("scope", {}).get("senior_test_rows_exported") == 0,
        "senior test firewall",
    )
    require(
        values["fit_summary"].get("classification")
        == "HISTORICAL_SINGLE_FOLD_ENDPOINT_LABEL_EFFICIENCY_SMOKE_DOES_NOT_ADVANCE",
        "smoke classification",
    )
    require(
        values["fit_summary"].get("scope", {}).get("prospective_first960_target300_target522_values_used") is False,
        "prospective values forbidden",
    )
    require(
        values["private_pair_witness"].get("raw_identities_emitted") is False,
        "pair witness identities",
    )
    require(
        values["selection_private"].get("identities_publicly_emitted") is False,
        "selection privacy",
    )
    return protocol, values


def reconstruct(protocol: dict[str, Any], values: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    topology = values["train_only_topology"]
    rows = topology.get("rows")
    require(isinstance(rows, list) and len(rows) == 539, "topology rows")
    for row in rows:
        require(
            set(row) == {"u", "v", "parent", "task", "physical_run", "source_split"}
            and row["source_split"] == "train"
            and row["u"] < row["v"],
            "topology row schema",
        )
    train_rows = [row for row in rows if run_fold(row["physical_run"]) != 0]
    eval_rows = [row for row in rows if run_fold(row["physical_run"]) == 0]
    require(len(train_rows) == 401 and len(eval_rows) == 138, "fold row counts")

    eval_expected = {
        pair_sha(row): {
            "task_sha256": identity_sha("task", row["task"]),
            "physical_run_sha256": identity_sha("physical_run", row["physical_run"]),
        }
        for row in eval_rows
    }
    require(len(eval_expected) == len(eval_rows), "evaluation pair uniqueness")

    witness_cells: dict[tuple[str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in values["private_pair_witness"]["rows"]:
        cell = (row["arm"], int(row["endpoint_budget"]))
        require(cell[0] in ARMS and cell[1] in (96, 192), "witness cell")
        pair = row["pair_identity_sha256"]
        require(pair in eval_expected and pair not in witness_cells[cell], "witness pair")
        require(row["task_sha256"] == eval_expected[pair]["task_sha256"], "witness task")
        require(row["physical_run_sha256"] == eval_expected[pair]["physical_run_sha256"], "witness run")
        probability = float(row["probability_first_better"])
        require(math.isfinite(probability) and 0.0 <= probability <= 1.0, "probability")
        witness_cells[cell][pair] = row
    expected_cells = {(arm, budget) for arm in ARMS for budget in (96, 192)}
    require(set(witness_cells) == expected_cells, "complete witness cells")
    require(all(set(cell) == set(eval_expected) for cell in witness_cells.values()), "common evaluation pairs")

    node_meta: dict[str, tuple[str, str]] = {}
    for row in train_rows:
        for endpoint in (row["u"], row["v"]):
            observed = (row["task"], row["physical_run"])
            require(endpoint not in node_meta or node_meta[endpoint] == observed, "endpoint task/run uniqueness")
            node_meta[endpoint] = observed
    available_pairs = Counter(identity_sha("task", row["task"]) for row in train_rows)

    private_selection = values["selection_private"]
    selection_by_cell: dict[tuple[str, int], set[str]] = {}
    for arm in ARMS:
        entries = private_selection["arms"][arm]
        require(isinstance(entries, list), "selection arm entries")
        for entry in entries:
            budget = int(entry["budget"])
            endpoints = list(entry["endpoint_ids"])
            require(len(endpoints) == budget and len(set(endpoints)) == budget, "exact endpoint budget")
            require(all(endpoint in node_meta for endpoint in endpoints), "selection endpoint closure")
            selection_by_cell[(arm, budget)] = set(endpoints)
    require(all(cell in selection_by_cell for cell in expected_cells), "fit-budget selections")

    coverage: dict[tuple[str, int], dict[str, Any]] = {}
    for cell in sorted(expected_cells):
        endpoints = selection_by_cell[cell]
        endpoint_counts: Counter[str] = Counter()
        selected_run_sets: dict[str, set[str]] = defaultdict(set)
        for endpoint in endpoints:
            task, run = node_meta[endpoint]
            task_hash = identity_sha("task", task)
            endpoint_counts[task_hash] += 1
            selected_run_sets[task_hash].add(identity_sha("physical_run", run))
        induced = [row for row in train_rows if row["u"] in endpoints and row["v"] in endpoints]
        induced_counts = Counter(identity_sha("task", row["task"]) for row in induced)
        coverage[cell] = {
            "selected_endpoints": endpoint_counts,
            "selected_runs": Counter({key: len(value) for key, value in selected_run_sets.items()}),
            "induced_pairs": induced_counts,
            "totals": {
                "selected_endpoints": len(endpoints),
                "selected_runs": len({node_meta[endpoint][1] for endpoint in endpoints}),
                "induced_pairs": len(induced),
            },
        }

    task_rows: list[dict[str, Any]] = []
    by_budget_public: dict[str, Any] = {}
    eval_tasks = sorted({entry["task_sha256"] for entry in eval_expected.values()})
    require(len(eval_tasks) == 20, "evaluation task count")
    for budget in (96, 192):
        uniform = witness_cells[("exact_b_uniform_edge", budget)]
        breadth = witness_cells[("yield_guarded_breadth", budget)]
        budget_rows: list[dict[str, Any]] = []
        for task_hash in eval_tasks:
            pairs = sorted(pair for pair, meta in eval_expected.items() if meta["task_sha256"] == task_hash)
            require(pairs, "task evaluation support")
            correct_delta = 0
            log_loss_delta = 0.0
            brier_delta = 0.0
            for pair in pairs:
                p_uniform = float(uniform[pair]["probability_first_better"])
                p_breadth = float(breadth[pair]["probability_first_better"])
                correct_delta += int(p_breadth > 0.5) - int(p_uniform > 0.5)
                clipped_uniform = min(max(p_uniform, 1e-15), 1.0 - 1e-15)
                clipped_breadth = min(max(p_breadth, 1e-15), 1.0 - 1e-15)
                log_loss_delta += -math.log(clipped_breadth) + math.log(clipped_uniform)
                brier_delta += (1.0 - p_breadth) ** 2 - (1.0 - p_uniform) ** 2
            count = len(pairs)
            row: dict[str, Any] = {
                "endpoint_budget": budget,
                "task_sha256": task_hash,
                "evaluation_pairs": count,
                "net_correct_contribution": correct_delta,
                "evaluation_metric_delta_yield_minus_uniform": {
                    "accuracy": correct_delta / count,
                    "log_loss": log_loss_delta / count,
                    "brier": brier_delta / count,
                },
                "outer_train_available_pairs": int(available_pairs.get(task_hash, 0)),
                "coverage": {},
                "coverage_delta_yield_minus_uniform": {},
            }
            for arm in ARMS:
                row["coverage"][arm] = {
                    name: int(coverage[(arm, budget)][name].get(task_hash, 0))
                    for name in COVERAGE_NAMES
                }
            for name in COVERAGE_NAMES:
                row["coverage_delta_yield_minus_uniform"][name] = (
                    row["coverage"]["yield_guarded_breadth"][name]
                    - row["coverage"]["exact_b_uniform_edge"][name]
                )
            budget_rows.append(row)
            task_rows.append(row)

        total_pairs = sum(row["evaluation_pairs"] for row in budget_rows)
        total_net = sum(row["net_correct_contribution"] for row in budget_rows)
        require(total_pairs == 138, "budget evaluation pair count")
        overall_delta = total_net / total_pairs
        expected_delta = float(
            values["fit_summary"]["paired_comparisons"][str(budget)]["yield_minus_uniform"]["pairwise_accuracy"]
        )
        require(math.isclose(overall_delta, expected_delta, rel_tol=0.0, abs_tol=1e-15), "summary accuracy delta")

        metric_vectors = {
            metric: [row["evaluation_metric_delta_yield_minus_uniform"][metric] for row in budget_rows]
            for metric in METRIC_NAMES
        }
        coverage_vectors = {
            name: [row["coverage_delta_yield_minus_uniform"][name] for row in budget_rows]
            for name in COVERAGE_NAMES
        }
        correlations = {
            coverage_name: {
                metric: spearman(coverage_vectors[coverage_name], metric_vectors[metric])
                for metric in METRIC_NAMES
            }
            for coverage_name in COVERAGE_NAMES
        }

        loto_values = [
            (total_net - row["net_correct_contribution"]) / (total_pairs - row["evaluation_pairs"])
            for row in budget_rows
        ]
        positive = sorted(
            (row["net_correct_contribution"] for row in budget_rows if row["net_correct_contribution"] > 0),
            reverse=True,
        )
        positive_total = sum(positive)
        concentration = {
            "positive_contribution_total": positive_total,
            "negative_contribution_total": sum(
                row["net_correct_contribution"]
                for row in budget_rows
                if row["net_correct_contribution"] < 0
            ),
            "largest_positive_share": (positive[0] / positive_total if positive_total else None),
            "two_largest_positive_share": (sum(positive[:2]) / positive_total if positive_total else None),
            "positive_contribution_hhi": (
                sum((value / positive_total) ** 2 for value in positive) if positive_total else None
            ),
        }

        distribution: dict[str, Any] = {}
        available_total = sum(available_pairs.values())
        require(available_total == len(train_rows), "available task total")
        all_train_tasks = sorted(available_pairs)
        for arm in ARMS:
            induced_counts = coverage[(arm, budget)]["induced_pairs"]
            induced_total = sum(induced_counts.values())
            require(induced_total > 0, "induced pair support")
            distance = sum(
                abs(induced_counts.get(task, 0) / induced_total - available_pairs[task] / available_total)
                for task in all_train_tasks
            )
            maximum = max(induced_counts.values())
            distribution[arm] = {
                **coverage[(arm, budget)]["totals"],
                "induced_pair_task_l1_to_outer_train_availability": distance,
                "maximum_single_task_induced_pair_share": ratio(maximum, induced_total),
                "represented_tasks_by_induced_pair": sum(value > 0 for value in induced_counts.values()),
            }

        by_budget_public[str(budget)] = {
            "evaluation_pairs": total_pairs,
            "evaluation_tasks": len(budget_rows),
            "overall_accuracy_delta_yield_minus_uniform": overall_delta,
            "task_macro_metric_delta_yield_minus_uniform": {
                metric: statistics.fmean(metric_vectors[metric]) for metric in METRIC_NAMES
            },
            "task_net_correct_sign_counts": sign_counts(
                row["net_correct_contribution"] for row in budget_rows
            ),
            "coverage_delta_task_sign_counts": {
                name: sign_counts(coverage_vectors[name]) for name in COVERAGE_NAMES
            },
            "coverage_metric_spearman": correlations,
            "leave_one_task_out_accuracy_delta": {
                "minimum": min(loto_values),
                "median": statistics.median(loto_values),
                "maximum": max(loto_values),
                "sign_counts": sign_counts(loto_values),
            },
            "gain_concentration": concentration,
            "train_distribution": distribution,
        }

    private_output = {
        "protocol": PRIVATE_PROTOCOL,
        "protocol_sha256": protocol["_observed_sha256"],
        "analysis_source_commit": protocol["_analysis_source_commit"],
        "artifact_source_commit": protocol["input_bindings"]["artifact_source_commit"],
        "raw_identities_emitted": False,
        "task_hashes_emitted_privately": True,
        "rows": task_rows,
    }
    private_sha = hashlib.sha256(canonical_bytes(private_output)).hexdigest()

    public_output = {
        "protocol": PUBLIC_PROTOCOL,
        "protocol_sha256": protocol["_observed_sha256"],
        "analysis_source_commit": protocol["_analysis_source_commit"],
        "artifact_source_commit": protocol["input_bindings"]["artifact_source_commit"],
        "input_sha256": protocol["input_bindings"],
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
            "outer_train_pairs": len(train_rows),
            "outer_train_tasks": len(available_pairs),
            "outer_eval_pairs": len(eval_rows),
            "outer_eval_tasks": len(eval_tasks),
        },
        "by_budget": by_budget_public,
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

    forbidden_values = set()
    for row in rows:
        forbidden_values.update(
            (row["u"], row["v"], row["parent"], row["task"], row["physical_run"])
        )
        forbidden_values.update(
            (
                identity_sha("task", row["task"]),
                identity_sha("physical_run", row["physical_run"]),
                pair_sha(row),
            )
        )

    def string_values(value: Any) -> set[str]:
        if isinstance(value, str):
            return {value}
        if isinstance(value, dict):
            result: set[str] = set()
            for item in value.values():
                result.update(string_values(item))
            return result
        if isinstance(value, list):
            result = set()
            for item in value:
                result.update(string_values(item))
            return result
        return set()

    require(not (string_values(public_output) & forbidden_values), "public identity/hash leak")
    return public_output, private_output


def write_exclusive(path: Path, value: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(canonical_bytes(value))


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--protocol", type=Path, required=True)
    value.add_argument("--protocol-sha256", required=True)
    value.add_argument("--analysis-source-commit", required=True)
    value.add_argument("--firewall-receipt", type=Path, required=True)
    value.add_argument("--train-topology", type=Path, required=True)
    value.add_argument("--selection-public", type=Path, required=True)
    value.add_argument("--selection-private", type=Path, required=True)
    value.add_argument("--fit-summary", type=Path, required=True)
    value.add_argument("--private-pairs", type=Path, required=True)
    value.add_argument("--public-output", type=Path, required=True)
    value.add_argument("--private-output", type=Path, required=True)
    return value


def main() -> None:
    args = parser().parse_args()
    protocol, values = load_and_validate(args)
    protocol["_observed_sha256"] = args.protocol_sha256
    protocol["_analysis_source_commit"] = args.analysis_source_commit
    public, private = reconstruct(protocol, values)
    write_exclusive(args.private_output.resolve(), private)
    require(file_sha(args.private_output.resolve()) == public["private_witness_sha256"], "private write SHA")
    write_exclusive(args.public_output.resolve(), public)
    print(json.dumps({
        "classification": public["classification"],
        "public_sha256": file_sha(args.public_output.resolve()),
        "private_sha256": file_sha(args.private_output.resolve()),
        "scope": public["scope"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
