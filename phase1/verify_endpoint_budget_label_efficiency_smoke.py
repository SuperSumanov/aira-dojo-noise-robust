#!/usr/bin/env python3
"""Independent aggregate verifier for the endpoint-budget label-efficiency smoke."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

from phase1 import falsify_historical_run_split_breadth_pareto as graph_source


PROTOCOL = "endpoint-budget-label-efficiency-smoke-v1"
SELECTION_PUBLIC = "endpoint-budget-label-efficiency-selection-public-v1"
SELECTION_PRIVATE = "endpoint-budget-label-efficiency-selection-private-v1"
FIT_RESULT = "endpoint-budget-label-efficiency-fit-result-v1"
FIT_PRIVATE = "endpoint-budget-label-efficiency-private-pair-witness-v1"
VERIFY_RESULT = "endpoint-budget-label-efficiency-independent-verification-v1"
FIREWALL_RECEIPT = "endpoint-budget-train-only-firewall-receipt-v1"
FIREWALL_TOPOLOGY = "endpoint-budget-train-only-topology-v1"
FOLD_SALT = "endpoint-label-efficiency-v1"


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


def read_object(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object required: {path}")
    return value


def run_fold(run: str) -> int:
    digest = hashlib.sha256((FOLD_SALT + "\0" + run).encode()).digest()
    return int.from_bytes(digest[:8], "big") % 5


def identity_sha(kind: str, value: str) -> str:
    return hashlib.sha256((kind + "\0" + value).encode("utf-8")).hexdigest()


def pair_sha(edge: Any) -> str:
    return hashlib.sha256(
        canonical_bytes(
            {
                "endpoints": sorted((edge.u, edge.v)),
                "parent": edge.parent,
                "task": edge.task,
                "physical_run": edge.run,
            }
        )
    ).hexdigest()


def close(left: Any, right: Any, context: str) -> None:
    if isinstance(left, dict) and isinstance(right, dict):
        require(set(left) == set(right), f"{context} keys")
        for key in left:
            close(left[key], right[key], f"{context}.{key}")
        return
    if isinstance(left, list) and isinstance(right, list):
        require(len(left) == len(right), f"{context} length")
        for index, (first, second) in enumerate(zip(left, right)):
            close(first, second, f"{context}[{index}]")
        return
    if isinstance(left, bool) or isinstance(right, bool):
        require(left is right, context)
        return
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        require(
            math.isfinite(float(left))
            and math.isfinite(float(right))
            and math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12),
            context,
        )
        return
    require(left == right, context)


def bootstrap_interval(
    values: list[float], clusters: list[str], repetitions: int, seed: int
) -> dict[str, float]:
    import numpy as np

    require(len(values) == len(clusters) and values, "bootstrap inputs")
    grouped: dict[str, list[float]] = defaultdict(list)
    for value, cluster in zip(values, clusters):
        grouped[cluster].append(float(value))
    keys = sorted(grouped)
    rng = np.random.default_rng(seed)
    draws: list[float] = []
    for _ in range(repetitions):
        sampled = rng.choice(len(keys), size=len(keys), replace=True)
        combined = [value for index in sampled for value in grouped[keys[int(index)]]]
        draws.append(float(np.mean(combined)))
    return {
        "point": float(np.mean(values)),
        "lo": float(np.quantile(draws, 0.025)),
        "hi": float(np.quantile(draws, 0.975)),
        "clusters": len(keys),
        "repetitions": repetitions,
    }


def reconstruct(
    receipt_path: Path, topology_path: Path, protocol_sha: str
) -> tuple[Any, Any, Any, dict[str, Any]]:
    receipt = read_object(receipt_path)
    topology = read_object(topology_path)
    require(
        receipt.get("protocol") == FIREWALL_RECEIPT
        and receipt.get("status") == "TRAIN_ONLY_FIREWALL_COMPLETE",
        "firewall receipt",
    )
    require(topology.get("protocol") == FIREWALL_TOPOLOGY, "firewall topology")
    require(
        receipt.get("protocol_sha256") == topology.get("protocol_sha256") == protocol_sha,
        "firewall protocol binding",
    )
    require(file_sha(topology_path) == receipt["topology_sha256"], "topology SHA")
    require(
        topology.get("pair_orientation_emitted") is False
        and topology.get("all_source_rows_train") is True,
        "topology scope",
    )
    edges = []
    for row in topology["rows"]:
        require(
            set(row) == {"u", "v", "parent", "task", "physical_run", "source_split"}
            and row["u"] < row["v"]
            and row["source_split"] == "train",
            "topology schema",
        )
        edges.append(
            graph_source.engine.Edge(
                row["u"], row["v"], row["parent"], row["task"], row["physical_run"]
            )
        )
    require(len(edges) == 539, "full residual pair count")
    full = graph_source.graph_from_edges(edges)
    train = graph_source.graph_from_edges(
        [edge for edge in full.edges if run_fold(edge.run) != 0]
    )
    evaluation = graph_source.graph_from_edges(
        [edge for edge in full.edges if run_fold(edge.run) == 0]
    )
    require(
        not ({edge.run for edge in train.edges} & {edge.run for edge in evaluation.edges}),
        "run overlap",
    )
    require(not (set(train.nodes) & set(evaluation.nodes)), "endpoint overlap")
    require(
        not (
            {edge.parent for edge in train.edges}
            & {edge.parent for edge in evaluation.edges}
        ),
        "parent overlap",
    )
    return full, train, evaluation, receipt


def private_selections(value: dict[str, Any]) -> dict[tuple[str, int], set[str]]:
    result: dict[tuple[str, int], set[str]] = {}
    for arm in ("exact_b_uniform_edge", "yield_guarded_breadth"):
        previous: set[str] = set()
        for entry in value["arms"][arm]:
            budget = int(entry["budget"])
            selected = set(entry["endpoint_ids"])
            require(
                entry["endpoint_ids"] == sorted(selected)
                and len(selected) == budget
                and previous <= selected,
                "selection exact nested",
            )
            result[(arm, budget)] = selected
            previous = selected
    return result


def verify(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        name: Path(value).resolve()
        for name, value in {
            "protocol": args.protocol,
            "firewall_receipt": args.firewall_receipt,
            "train_topology": args.train_topology,
            "selection_public": args.selection_public,
            "selection_private": args.selection_private,
            "summary": args.summary,
            "runs_csv": args.runs_csv,
            "private_pairs": args.private_pairs,
        }.items()
    }
    require(file_sha(paths["protocol"]) == args.protocol_sha256, "protocol SHA")
    protocol = read_object(paths["protocol"])
    require(protocol.get("protocol") == PROTOCOL, "protocol name")
    require(
        protocol["known_before_freeze"][
            "endpoint_budget_matched_downstream_comparison_run_or_seen"
        ]
        is False,
        "pre-readout freeze",
    )
    require(
        protocol["metrics"]["private_pair_witness"][
            "independent_verifier_model_refits"
        ]
        == 0,
        "verifier refit contract",
    )
    public = read_object(paths["selection_public"])
    private = read_object(paths["selection_private"])
    summary = read_object(paths["summary"])
    pair_witness = read_object(paths["private_pairs"])
    require(public.get("protocol") == SELECTION_PUBLIC, "selection public")
    require(public.get("classification") == "ENDPOINT_BUDGET_LABEL_EFFICIENCY_SMOKE_SELECTION_READY", "selection ready")
    require(private.get("protocol") == SELECTION_PRIVATE, "selection private")
    require(summary.get("protocol") == FIT_RESULT and summary.get("status") == "COMPLETE", "fit summary")
    require(pair_witness.get("protocol") == FIT_PRIVATE, "pair witness")
    require(
        all(
            value.get("protocol_sha256") == args.protocol_sha256
            for value in (public, private, summary, pair_witness)
        ),
        "protocol bindings",
    )
    require(
        public["analysis_source_commit"]
        == summary["source_commit"]
        == pair_witness["source_commit"],
        "source commit bindings",
    )
    require(
        file_sha(paths["selection_private"]) == public["private_selection_sha256"],
        "selection private binding",
    )
    require(
        file_sha(paths["private_pairs"]) == summary["private_pair_witness_sha256"],
        "pair witness binding",
    )
    checkpoint_root = Path(args.checkpoint_dir).resolve()
    require(
        checkpoint_root.is_dir()
        and not checkpoint_root.is_symlink()
        and (
            os.name == "nt" or checkpoint_root.stat().st_mode & 0o077 == 0
        ),
        "checkpoint root",
    )
    expected_checkpoint_hashes = summary["fit_checkpoints"]
    observed_checkpoint_names = {
        path.name for path in checkpoint_root.iterdir() if path.name != ".staging"
    }
    require(
        observed_checkpoint_names == set(expected_checkpoint_hashes),
        "checkpoint files",
    )
    require(
        all(
            file_sha(checkpoint_root / name) == expected
            and (os.name == "nt" or (checkpoint_root / name).stat().st_mode & 0o077 == 0)
            for name, expected in expected_checkpoint_hashes.items()
        ),
        "checkpoint hashes",
    )
    require(paths["selection_private"].stat().st_mode & 0o077 == 0, "selection private mode")
    require(paths["private_pairs"].stat().st_mode & 0o077 == 0, "pair witness mode")

    require(
        os.name == "nt"
        or (
            paths["firewall_receipt"].stat().st_mode & 0o077 == 0
            and paths["train_topology"].stat().st_mode & 0o077 == 0
        ),
        "firewall private mode",
    )
    full, train, evaluation, firewall = reconstruct(
        paths["firewall_receipt"],
        paths["train_topology"],
        args.protocol_sha256,
    )
    require(
        file_sha(paths["firewall_receipt"])
        == public["train_only_firewall_receipt_sha256"],
        "public firewall receipt binding",
    )
    require(
        firewall["source_commit"] == summary["source_commit"],
        "firewall source commit",
    )
    expected_pairs = {
        pair_sha(edge): {
            "task_sha256": identity_sha("task", edge.task),
            "physical_run_sha256": identity_sha("physical_run", edge.run),
        }
        for edge in evaluation.edges
    }
    require(len(expected_pairs) == len(evaluation.edges), "evaluation pair uniqueness")
    selections = private_selections(private)
    fit_numerators = protocol["selection"]["smoke_fit_numerators"]
    checkpoints = public["selection"]["checkpoints"]
    fit_budgets = [
        checkpoints[protocol["selection"]["six_checkpoint_numerators"].index(value)]
        for value in fit_numerators
    ]
    expected_cells = {
        (arm, budget)
        for arm in ("exact_b_uniform_edge", "yield_guarded_breadth")
        for budget in fit_budgets
    }
    observed: dict[tuple[str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    indices: dict[tuple[str, int], set[int]] = defaultdict(set)
    for row in pair_witness["rows"]:
        cell = (row["arm"], int(row["endpoint_budget"]))
        require(cell in expected_cells, "unexpected witness cell")
        pair = row["pair_identity_sha256"]
        require(pair in expected_pairs and pair not in observed[cell], "witness pair closure")
        index = int(row["pair_index"])
        require(index not in indices[cell], "witness pair index uniqueness")
        indices[cell].add(index)
        require(row["task_sha256"] == expected_pairs[pair]["task_sha256"], "task fingerprint")
        require(
            row["physical_run_sha256"]
            == expected_pairs[pair]["physical_run_sha256"],
            "run fingerprint",
        )
        probability = float(row["probability_first_better"])
        require(math.isfinite(probability) and 0 <= probability <= 1, "probability")
        observed[cell][pair] = row
    require(set(observed) == expected_cells, "witness cells")
    require(
        all(set(rows) == set(expected_pairs) for rows in observed.values()),
        "witness evaluation set",
    )
    require(
        all(values == set(range(len(evaluation.edges))) for values in indices.values()),
        "witness pair indices",
    )
    require(
        pair_witness["outer_eval_pair_count"] == len(evaluation.edges)
        and pair_witness["arm_budget_count"] == len(expected_cells)
        and pair_witness["raw_identities_emitted"] is False,
        "witness census",
    )

    model_rows = {
        (row["arm"], int(row["endpoint_budget"])): row
        for row in summary["model_rows"]
    }
    require(set(model_rows) == expected_cells, "model cells")
    with paths["runs_csv"].open(newline="", encoding="utf-8") as handle:
        csv_rows = list(csv.DictReader(handle))
    require(len(csv_rows) == len(summary["model_rows"]), "CSV rows")
    for csv_row, summary_row in zip(csv_rows, summary["model_rows"]):
        require(set(csv_row) == set(summary_row), "CSV columns")
        require(all(csv_row[key] == str(value) for key, value in summary_row.items()), "CSV summary equality")

    arrays: dict[tuple[str, int], dict[str, dict[str, float]]] = {}
    for cell, records in observed.items():
        values: dict[str, dict[str, float]] = {}
        for pair, row in records.items():
            probability = float(row["probability_first_better"])
            clipped = min(max(probability, 1e-15), 1 - 1e-15)
            values[pair] = {
                "correct": float(probability > 0.5),
                "log_loss": -math.log(clipped),
                "brier": (1.0 - probability) ** 2,
            }
        arrays[cell] = values
        model = model_rows[cell]
        selected = selections[cell]
        induced = sum(
            edge.u in selected and edge.v in selected for edge in train.edges
        )
        expected_metrics = {
            "selected_endpoints": len(selected),
            "induced_unique_train_pairs": induced,
            "outer_eval_pairs": len(evaluation.edges),
            "outer_eval_tasks": len({edge.task for edge in evaluation.edges}),
            "pairwise_accuracy": sum(item["correct"] for item in values.values()) / len(values),
            "log_loss": sum(item["log_loss"] for item in values.values()) / len(values),
            "brier_score": sum(item["brier"] for item in values.values()) / len(values),
        }
        for key, value in expected_metrics.items():
            close(model[key], value, f"model.{cell}.{key}")
        require(
            float(model["fit_seconds"]) >= 0
            and float(model["query_seconds"]) >= 0
            and int(model["vocabulary_size"]) > 0
            and int(model["model_iterations"]) > 0,
            "model diagnostics",
        )

    repetitions = int(
        protocol["metrics"]["inference"][
            "task_clustered_paired_bootstrap_repetitions"
        ]
    )
    seed = int(protocol["metrics"]["inference"]["bootstrap_seed"])
    pair_order = sorted(expected_pairs)
    tasks = [expected_pairs[pair]["task_sha256"] for pair in pair_order]
    runs = [expected_pairs[pair]["physical_run_sha256"] for pair in pair_order]
    task_counts = Counter(tasks)
    dominant_count = max(task_counts.values())
    dominant = min(task for task, count in task_counts.items() if count == dominant_count)
    keep = [index for index, task in enumerate(tasks) if task != dominant]
    comparisons: dict[str, Any] = {}
    for budget in fit_budgets:
        uniform = arrays[("exact_b_uniform_edge", budget)]
        guarded = arrays[("yield_guarded_breadth", budget)]
        delta_accuracy = [
            guarded[pair]["correct"] - uniform[pair]["correct"]
            for pair in pair_order
        ]
        delta_loss = [
            guarded[pair]["log_loss"] - uniform[pair]["log_loss"]
            for pair in pair_order
        ]
        delta_brier = [
            guarded[pair]["brier"] - uniform[pair]["brier"]
            for pair in pair_order
        ]
        comparisons[str(budget)] = {
            "yield_minus_uniform": {
                "pairwise_accuracy": sum(delta_accuracy) / len(delta_accuracy),
                "log_loss": sum(delta_loss) / len(delta_loss),
                "brier_score": sum(delta_brier) / len(delta_brier),
            },
            "accuracy_task_clustered_bootstrap": bootstrap_interval(
                delta_accuracy, tasks, repetitions, seed + budget
            ),
            "accuracy_run_clustered_bootstrap": bootstrap_interval(
                delta_accuracy, runs, repetitions, seed + 1000 + budget
            ),
            "drop_dominant_task": {
                "dropped_pair_count": dominant_count,
                "retained_pair_count": len(keep),
                "accuracy_delta_yield_minus_uniform": sum(
                    delta_accuracy[index] for index in keep
                )
                / len(keep),
            },
        }
    close(summary["paired_comparisons"], comparisons, "paired comparisons")
    terminal = comparisons[str(fit_budgets[-1])]
    advancement = {
        "accuracy_delta_positive_at_both_budgets": all(
            comparisons[str(budget)]["yield_minus_uniform"]["pairwise_accuracy"] > 0
            for budget in fit_budgets
        ),
        "terminal_log_loss_nonworse": terminal["yield_minus_uniform"]["log_loss"] <= 0,
        "terminal_brier_nonworse": terminal["yield_minus_uniform"]["brier_score"] <= 0,
        "drop_dominant_task_terminal_accuracy_delta_nonnegative": terminal[
            "drop_dominant_task"
        ]["accuracy_delta_yield_minus_uniform"]
        >= 0,
    }
    require(summary["advancement_gates"] == advancement, "advancement gates")
    expected_class = (
        "HISTORICAL_SINGLE_FOLD_ENDPOINT_LABEL_EFFICIENCY_SMOKE_ADVANCES"
        if all(advancement.values())
        else "HISTORICAL_SINGLE_FOLD_ENDPOINT_LABEL_EFFICIENCY_SMOKE_DOES_NOT_ADVANCE"
    )
    require(summary["classification"] == expected_class, "classification")
    require(summary["scope"]["senior_test_rows_used"] is False, "test scope")
    require(
        summary["scope"]["prospective_first960_target300_target522_values_used"]
        is False,
        "prospective scope",
    )
    public_text = canonical_bytes(summary).decode("utf-8")
    identities = set(full.nodes)
    identities.update(edge.parent for edge in full.edges)
    identities.update(edge.task for edge in full.edges)
    identities.update(edge.run for edge in full.edges)
    require(
        not any(json.dumps(identity, ensure_ascii=False) in public_text for identity in identities),
        "public identity leak",
    )
    private_text = canonical_bytes(pair_witness).decode("utf-8")
    require(
        not any(json.dumps(identity, ensure_ascii=False) in private_text for identity in identities),
        "private raw identity leak",
    )
    return {
        "protocol": VERIFY_RESULT,
        "status": "INDEPENDENT_AGGREGATE_RECOMPUTATION_EXACT",
        "protocol_sha256": args.protocol_sha256,
        "summary_sha256": file_sha(paths["summary"]),
        "runs_csv_sha256": file_sha(paths["runs_csv"]),
        "private_pair_witness_sha256": file_sha(paths["private_pairs"]),
        "classification": summary["classification"],
        "all_aggregate_fields_equal": True,
        "evaluation_pair_set_reconstructed": True,
        "producer_module_imported": False,
        "model_refits": 0,
        "scope": {
            "historical_train_rows_only": True,
            "senior_test_rows_used": False,
            "prospective_values_used": False,
            "gpu_api_model_fit_base_update": "0/0/0/0",
        },
    }


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(canonical_bytes(value))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--firewall-receipt", type=Path, required=True)
    parser.add_argument("--train-topology", type=Path, required=True)
    parser.add_argument("--selection-public", type=Path, required=True)
    parser.add_argument("--selection-private", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--runs-csv", type=Path, required=True)
    parser.add_argument("--private-pairs", type=Path, required=True)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify(args)
    write_exclusive(args.output.resolve(), result)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
