#!/usr/bin/env python3
"""Frozen historical train-only endpoint-budget label-efficiency smoke."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import time
from typing import Any, Iterable

from phase1 import audit_historical_independent_sibling_graph_gate as qualification
from phase1 import audit_yield_guarded_breadth_exact_budget_development_v1 as exact_dev
from phase1 import confirm_yield_guarded_breadth_forward_target522 as forward
from phase1 import falsify_historical_run_split_breadth_pareto as graph_source


PROTOCOL = "endpoint-budget-label-efficiency-smoke-v1"
SELECTION_PUBLIC = "endpoint-budget-label-efficiency-selection-public-v1"
SELECTION_PRIVATE = "endpoint-budget-label-efficiency-selection-private-v1"
FIT_RESULT = "endpoint-budget-label-efficiency-fit-result-v1"
FIT_PRIVATE = "endpoint-budget-label-efficiency-private-pair-witness-v1"
FIT_CELL = "endpoint-budget-label-efficiency-fit-cell-v1"
FIREWALL_RECEIPT = "endpoint-budget-train-only-firewall-receipt-v1"
FIREWALL_TOPOLOGY = "endpoint-budget-train-only-topology-v1"
FIREWALL_LABELS = "endpoint-budget-train-only-labels-v1"
FOLD_SALT = "endpoint-label-efficiency-v1"


class SmokeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeError(message)


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


def sha_bytes(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def identity_sha(kind: str, value: str) -> str:
    return hashlib.sha256((kind + "\0" + value).encode("utf-8")).hexdigest()


def pair_identity_sha(row: Any) -> str:
    return sha_bytes(
        {
            "endpoints": sorted((row.first, row.second)),
            "parent": row.parent,
            "task": row.task,
            "physical_run": row.first_run,
        }
    )


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
    require(isinstance(value, dict), f"object required: {path}")
    return value


def load_protocol(path: Path, expected_sha: str) -> tuple[dict[str, Any], str]:
    observed = file_sha(path)
    require(observed == expected_sha, "protocol SHA mismatch")
    value = object_file(path)
    require(value.get("protocol") == PROTOCOL, "protocol name")
    require(
        value.get("status")
        == "FROZEN_AFTER_TOPOLOGY_DIRECTION_BEFORE_THIS_COMPARISON_LABEL_READOUT",
        "protocol status",
    )
    known = value["known_before_freeze"]
    require(known["endpoint_budget_matched_downstream_comparison_run_or_seen"] is False, "prior readout")
    require(known["this_selection_witness_seen"] is False, "selection seen")
    require(known["this_accuracy_logloss_brier_or_pairwise_prediction_seen"] is False, "metric seen")
    require(value["population"]["senior_test_rows_forbidden"] is True, "test rows")
    require(value["population"]["prospective_rows_forbidden"] is True, "prospective rows")
    require(value["resources"] == {
        "gpu": 0,
        "paid_api_calls": 0,
        "base_model_updates": 0,
        "critic_model_fits": 4,
        "cpu_wall_time_expected_minutes": "20-45",
        "checkpoint_resume": "one mode-0600 atomic cell per completed arm-budget fit; completed cells are verified and reused",
    }, "resource contract")
    return value, observed


def run_fold(run: str) -> int:
    digest = hashlib.sha256((FOLD_SALT + "\0" + run).encode()).digest()
    return int.from_bytes(digest[:8], "big") % 5


def fold_assignment_sha(graph: Any) -> str:
    assignments = [
        f"{run}\0{run_fold(run)}"
        for run in sorted({edge.run for edge in graph.edges})
    ]
    return hashlib.sha256("\n".join(assignments).encode()).hexdigest()


def graph_from_edges(edges: Iterable[Any]) -> Any:
    return graph_source.graph_from_edges(list(edges))


def private_mode(path: Path) -> bool:
    return os.name == "nt" or path.stat().st_mode & 0o077 == 0


def load_firewall_population(
    args: argparse.Namespace, protocol_sha: str
) -> tuple[Any, Any, Any, dict[str, Any]]:
    receipt_path = args.firewall_receipt.resolve()
    topology_path = args.train_topology.resolve()
    require(private_mode(receipt_path) and private_mode(topology_path), "firewall private mode")
    receipt = object_file(receipt_path)
    topology = object_file(topology_path)
    require(
        receipt.get("protocol") == FIREWALL_RECEIPT
        and receipt.get("status") == "TRAIN_ONLY_FIREWALL_COMPLETE",
        "firewall receipt",
    )
    require(topology.get("protocol") == FIREWALL_TOPOLOGY, "firewall topology")
    require(
        receipt.get("protocol_sha256")
        == topology.get("protocol_sha256")
        == protocol_sha,
        "firewall protocol binding",
    )
    require(
        receipt.get("source_commit")
        == topology.get("source_commit")
        == args.source_commit,
        "firewall source binding",
    )
    require(file_sha(topology_path) == receipt["topology_sha256"], "topology SHA")
    require(
        topology.get("pair_orientation_emitted") is False
        and topology.get("all_source_rows_train") is True,
        "topology scope",
    )
    rows = topology["rows"]
    require(isinstance(rows, list) and len(rows) == 539, "topology row count")
    edges = []
    for row in rows:
        require(
            set(row) == {"u", "v", "parent", "task", "physical_run", "source_split"}
            and row["source_split"] == "train"
            and row["u"] < row["v"],
            "topology row schema",
        )
        edges.append(
            graph_source.engine.Edge(
                row["u"], row["v"], row["parent"], row["task"], row["physical_run"]
            )
        )
    full = graph_from_edges(edges)
    eval_edges = [edge for edge in full.edges if run_fold(edge.run) == 0]
    train_edges = [edge for edge in full.edges if run_fold(edge.run) != 0]
    require(len(eval_edges) + len(train_edges) == len(full.edges), "fold partition")
    train, evaluation = graph_from_edges(train_edges), graph_from_edges(eval_edges)
    train_runs = {edge.run for edge in train.edges}
    eval_runs = {edge.run for edge in evaluation.edges}
    train_endpoints = set(train.nodes)
    eval_endpoints = set(evaluation.nodes)
    train_parents = {edge.parent for edge in train.edges}
    eval_parents = {edge.parent for edge in evaluation.edges}
    require(not (train_runs & eval_runs), "outer run overlap")
    require(not (train_endpoints & eval_endpoints), "outer endpoint overlap")
    require(not (train_parents & eval_parents), "outer parent overlap")
    return full, train, evaluation, receipt


def graph_profile(graph: Any) -> dict[str, Any]:
    tasks = Counter(edge.task for edge in graph.edges)
    runs = Counter(edge.run for edge in graph.edges)
    return {
        "pairs": len(graph.edges),
        "endpoints": len(graph.nodes),
        "parents": len({edge.parent for edge in graph.edges}),
        "physical_runs": len(runs),
        "tasks": len(tasks),
        "maximum_single_task_pair_share": forward.ratio(max(tasks.values(), default=0), max(1, len(graph.edges))),
        "maximum_single_run_pair_share": forward.ratio(max(runs.values(), default=0), max(1, len(graph.edges))),
    }


def budgets(graph: Any, protocol: dict[str, Any]) -> list[int]:
    selection = protocol["selection"]
    denominator = int(selection["budget_fraction_denominator"])
    values = [
        math.floor(len(graph.nodes) * int(numerator) / denominator)
        for numerator in selection["six_checkpoint_numerators"]
    ]
    require(len(values) == 6 and values == sorted(set(values)) and values[0] >= 2, "budget closure")
    return values


def representative_uniform_seed(graph: Any, checkpoints: list[int]) -> tuple[int, list[str], dict[str, Any]]:
    rows, old_underfill = exact_dev.baseline_rows(graph, checkpoints)
    by_budget, integrated = exact_dev.summarize_baseline(rows, checkpoints)
    by_seed: dict[int, int] = defaultdict(int)
    for row in rows:
        by_seed[int(row["seed"])] += int(row["closed_edges"])
    median = graph_source.engine.nearest_rank(list(by_seed.values()), 0.5)
    candidates = [seed for seed, value in by_seed.items() if value == median]
    require(candidates, "representative seed")
    seed = min(candidates)
    order = [
        action[0]
        for action in exact_dev.exact_uniform_edge_actions(graph, seed, checkpoints[-1])
    ]
    require(len(order) == checkpoints[-1] and len(set(order)) == checkpoints[-1], "uniform exact order")
    metrics = [forward.metrics_for_selection(graph, set(order[:budget]), budget) for budget in checkpoints]
    require(sum(row["closed_edges"] for row in metrics) == median, "representative integrated yield")
    return seed, order, {
        "seeds": 256,
        "rows": len(rows),
        "historical_atomic_underfill_diagnostic_rows": old_underfill,
        "by_budget_nearest_rank_median": {str(key): value for key, value in by_budget.items()},
        "integrated_trajectory_nearest_rank_median": integrated,
        "representative_seed": seed,
        "representative_integrated_closed_edges": median,
        "representative_metrics": metrics,
    }


def selected_metrics(graph: Any, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        forward.metrics_for_selection(graph, set(entry["endpoint_ids"]), int(entry["budget"]))
        for entry in entries
    ]


def public_has_no_identities(public: dict[str, Any], graph: Any) -> bool:
    text = canonical_bytes(public).decode("utf-8")
    identities = set(graph.nodes)
    identities.update(edge.parent for edge in graph.edges)
    identities.update(edge.task for edge in graph.edges)
    identities.update(edge.run for edge in graph.edges)
    return not any(json.dumps(value, ensure_ascii=False) in text for value in identities)


def build_selection(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any] | None]:
    protocol, protocol_sha = load_protocol(args.protocol.resolve(), args.protocol_sha256)
    full, train, evaluation, firewall = load_firewall_population(args, protocol_sha)
    train_profile, eval_profile = graph_profile(train), graph_profile(evaluation)
    support_spec = protocol["support_gates_before_model_fit"]
    eval_share = eval_profile["maximum_single_task_pair_share"]
    support = {
        "minimum_outer_eval_pairs": eval_profile["pairs"] >= int(support_spec["minimum_outer_eval_pairs"]),
        "minimum_outer_eval_tasks": eval_profile["tasks"] >= int(support_spec["minimum_outer_eval_tasks"]),
        "maximum_single_outer_eval_task_pair_share": (
            eval_share["numerator"] * 20 <= eval_share["denominator"] * 7
        ),
        "outer_train_eval_run_endpoint_parent_overlap_zero": True,
    }
    public: dict[str, Any] = {
        "protocol": SELECTION_PUBLIC,
        "status": "COMPLETE",
        "protocol_sha256": protocol_sha,
        "analysis_source_commit": args.source_commit,
        "train_only_firewall_receipt_sha256": file_sha(
            args.firewall_receipt.resolve()
        ),
        "train_only_topology_sha256": firewall["topology_sha256"],
        "fold": {
            "count": 5,
            "outer_eval_fold": 0,
            "outer_train_folds": [1, 2, 3, 4],
            "assignment_sha256": fold_assignment_sha(full),
        },
        "population": {
            "full": graph_profile(full),
            "outer_train": train_profile,
            "outer_eval": eval_profile,
        },
        "support_gates": support,
        "selection": None,
        "private_selection_sha256": None,
        "classification": "ENDPOINT_BUDGET_LABEL_EFFICIENCY_SMOKE_LIMITED_SUPPORT",
        "scope": {
            "historical_train_rows_only": True,
            "senior_test_rows_used": False,
            "prospective_rows_or_values_used": False,
            "pair_orientation_gap_grade_code_prediction_runtime_used_for_selection": False,
            "public_identities_emitted": False,
            "gpu_api_model_fit_base_update": "0/0/0/0",
        },
    }
    if not all(support.values()):
        require(public_has_no_identities(public, full), "public identity leak")
        return public, None

    checkpoints = budgets(train, protocol)
    baseline, pointwise, integrated = forward.exact_baseline(train, checkpoints)
    seed, uniform_order, representative = representative_uniform_seed(train, checkpoints)
    require(baseline["by_budget_nearest_rank_median"] == representative["by_budget_nearest_rank_median"], "baseline repeat")
    require(baseline["integrated_trajectory_nearest_rank_median"] == representative["integrated_trajectory_nearest_rank_median"], "integrated repeat")
    floors = forward.fixed_floors(baseline, checkpoints)
    solver, solver_private = forward.solve_private(
        train,
        checkpoints,
        pointwise,
        int(floors["integrated_closed_edges"]),
        int(floors["integrated_tasks"]),
        int(floors["integrated_physical_runs"]),
        int(floors["terminal_parents"]),
        float(protocol["selection"]["yield_guarded_contract"]["solver_time_limit_seconds"]),
    )
    if solver.get("status") != "FEASIBLE_WITNESS" or solver_private is None:
        public["selection"] = {
            "checkpoints": checkpoints,
            "baseline": baseline,
            "fixed_floors": floors,
            "yield_guarded_solver": solver,
        }
        public["classification"] = (
            "ENDPOINT_BUDGET_LABEL_EFFICIENCY_SMOKE_SELECTION_INFEASIBLE"
            if solver.get("status") == "INFEASIBLE_PROVEN"
            else "ENDPOINT_BUDGET_LABEL_EFFICIENCY_SMOKE_SELECTION_UNRESOLVED"
        )
        require(public_has_no_identities(public, full), "public identity leak")
        return public, None

    yield_gates = forward.gates_for_witness(solver, baseline, floors)
    require(all(yield_gates.values()), "yield witness gates")
    yield_entries = solver_private["selected_endpoint_ids_by_checkpoint"]
    uniform_entries = [
        {"budget": budget, "endpoint_ids": sorted(uniform_order[:budget])}
        for budget in checkpoints
    ]
    require(selected_metrics(train, yield_entries) == solver["metrics"], "yield private metrics")
    uniform_metrics = selected_metrics(train, uniform_entries)
    fit_numerators = protocol["selection"]["smoke_fit_numerators"]
    fit_indices = [protocol["selection"]["six_checkpoint_numerators"].index(value) for value in fit_numerators]
    pair_minimum = int(support_spec["minimum_induced_train_pairs_at_each_smoke_budget"])
    pair_support = {
        arm: all(metrics[index]["closed_edges"] >= pair_minimum for index in fit_indices)
        for arm, metrics in (
            ("exact_b_uniform_edge", uniform_metrics),
            ("yield_guarded_breadth", solver["metrics"]),
        )
    }
    public["support_gates"].update(
        {f"minimum_induced_train_pairs_{arm}": value for arm, value in pair_support.items()}
    )
    public["selection"] = {
        "checkpoints": checkpoints,
        "smoke_fit_indices": fit_indices,
        "smoke_fit_numerators": fit_numerators,
        "baseline": baseline,
        "representative_uniform": representative,
        "fixed_floors": floors,
        "uniform_metrics": uniform_metrics,
        "yield_guarded_solver": solver,
        "yield_guarded_gates": yield_gates,
        "all_checkpoint_budgets_exact": all(
            row["selected_endpoints"] == row["budget"]
            for row in uniform_metrics + solver["metrics"]
        ),
    }
    if not all(pair_support.values()):
        public["classification"] = "ENDPOINT_BUDGET_LABEL_EFFICIENCY_SMOKE_LIMITED_INDUCED_PAIR_SUPPORT"
        require(public_has_no_identities(public, full), "public identity leak")
        return public, None
    private = {
        "protocol": SELECTION_PRIVATE,
        "protocol_sha256": protocol_sha,
        "fold": 0,
        "checkpoints": checkpoints,
        "representative_uniform_seed": seed,
        "arms": {
            "exact_b_uniform_edge": uniform_entries,
            "yield_guarded_breadth": yield_entries,
        },
        "identities_publicly_emitted": False,
    }
    private["selection_fingerprint_sha256"] = sha_bytes(private["arms"])
    public["private_selection_sha256"] = sha_bytes(private)
    public["classification"] = "ENDPOINT_BUDGET_LABEL_EFFICIENCY_SMOKE_SELECTION_READY"
    require(public_has_no_identities(public, full), "public identity leak")
    return public, private


def load_train_rows_and_codes(
    args: argparse.Namespace,
    protocol: dict[str, Any],
    needed_codes: set[str],
) -> tuple[list[Any], dict[str, str]]:
    receipt = object_file(args.firewall_receipt.resolve())
    labels_path = args.train_labels.resolve()
    require(private_mode(labels_path), "labels private mode")
    labels = object_file(labels_path)
    require(labels.get("protocol") == FIREWALL_LABELS, "labels protocol")
    require(
        labels.get("protocol_sha256") == receipt.get("protocol_sha256")
        and labels.get("source_commit") == receipt.get("source_commit") == args.source_commit,
        "labels binding",
    )
    require(file_sha(labels_path) == receipt["labels_sha256"], "labels SHA")
    require(
        labels.get("all_source_rows_train") is True
        and labels.get("senior_test_rows_emitted") == 0,
        "labels train-only scope",
    )
    rows = []
    for item in labels["rows"]:
        require(
            set(item)
            == {
                "better",
                "worse",
                "parent",
                "task",
                "physical_run",
                "source_split",
                "relation",
            }
            and item["source_split"] == "train"
            and item["relation"] == "verified_direct_sibling",
            "label row schema",
        )
        rows.append(
            qualification.relation.DecisionRow(
                first=item["better"],
                second=item["worse"],
                parent=item["parent"],
                task=item["task"],
                split="train",
                first_run=item["physical_run"],
                second_run=item["physical_run"],
                parent_run=item["physical_run"],
                relation="verified_direct_sibling",
            )
        )
    require(len(rows) == 539, "train label row count")

    cards_root = args.cards_root.resolve()
    card_path = cards_root / "cards.safe.json"
    security_path = cards_root / "security_scan.json"
    immutable = protocol["immutable_inputs"]
    require(
        file_sha(security_path) == immutable["senior_security_receipt"]["sha256"],
        "security receipt SHA",
    )
    security = object_file(security_path)
    require(
        security.get("status") == "CREDENTIAL_SCAN_AND_REDACTION_PASS"
        and security.get("remaining_credential_hits") == 0
        and security.get("private_key_markers") == 0
        and security.get("json_parsed_before_scan") is False,
        "security receipt status",
    )
    require(
        file_sha(card_path) == immutable["senior_safe_cards"]["sha256"]
        == security.get("safe_sha256"),
        "safe cards SHA",
    )
    codes: dict[str, str] = {}
    stream = qualification.relation.base.JsonObjectStream(card_path)
    try:
        for _run, card_rows in stream:
            for card in card_rows:
                identifier = card.get("id")
                if identifier in needed_codes:
                    code = card.get("code")
                    require(code is None or isinstance(code, str), "code schema")
                    codes[identifier] = (code or "")[:20000]
    finally:
        stream.close()
    require(set(codes) == needed_codes, "missing endpoint code")
    return rows, codes


def entries_by_budget(private: dict[str, Any], arm: str) -> dict[int, set[str]]:
    entries = private["arms"][arm]
    result: dict[int, set[str]] = {}
    previous: set[str] = set()
    for entry in entries:
        budget = int(entry["budget"])
        identifiers = entry["endpoint_ids"]
        require(isinstance(identifiers, list) and identifiers == sorted(set(identifiers)), "private IDs")
        selected = set(identifiers)
        require(len(selected) == budget and previous <= selected, "private exact nested")
        result[budget] = selected
        previous = selected
    return result


def bootstrap_interval(values: list[float], clusters: list[str], repetitions: int, seed: int) -> dict[str, float]:
    import numpy as np

    require(len(values) == len(clusters) and values, "bootstrap inputs")
    grouped: dict[str, list[float]] = defaultdict(list)
    for value, cluster in zip(values, clusters):
        grouped[cluster].append(float(value))
    keys = sorted(grouped)
    rng = np.random.default_rng(seed)
    draws = []
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


def fit_one(
    selected: set[str], train_rows: list[Any], eval_rows: list[Any], codes: dict[str, str]
) -> tuple[dict[str, Any], dict[str, list[Any]]]:
    import numpy as np
    from scipy.sparse import vstack
    from scipy.special import expit
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    induced = [row for row in train_rows if row.first in selected and row.second in selected]
    require(len(induced) >= 30, "induced pair support")
    eval_ids = {item for row in eval_rows for item in (row.first, row.second)}
    all_ids = sorted(selected | eval_ids)
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        max_features=30000,
        min_df=3,
        sublinear_tf=True,
    )
    fit_started = time.perf_counter()
    vectorizer.fit([codes[item] for item in sorted(selected)])
    train_ids = sorted(selected)
    train_matrix = vectorizer.transform([codes[item] for item in train_ids])
    train_position = {item: index for index, item in enumerate(train_ids)}
    positive = vstack(
        [
            train_matrix[train_position[row.first]] - train_matrix[train_position[row.second]]
            for row in induced
        ],
        format="csr",
    )
    features = vstack([positive, -positive], format="csr")
    labels = np.concatenate((np.ones(len(induced), dtype=int), np.zeros(len(induced), dtype=int)))
    model = LogisticRegression(
        C=0.5,
        max_iter=1500,
        solver="lbfgs",
        random_state=0,
    ).fit(features, labels)
    fit_seconds = time.perf_counter() - fit_started

    query_started = time.perf_counter()
    evaluation_ids = sorted(eval_ids)
    evaluation_matrix = vectorizer.transform([codes[item] for item in evaluation_ids])
    evaluation_position = {item: index for index, item in enumerate(evaluation_ids)}
    differences = vstack(
        [
            evaluation_matrix[evaluation_position[row.first]]
            - evaluation_matrix[evaluation_position[row.second]]
            for row in eval_rows
        ],
        format="csr",
    )
    scores = model.decision_function(differences)
    probabilities = expit(scores)
    query_seconds = time.perf_counter() - query_started
    epsilon = 1e-15
    clipped = np.clip(probabilities, epsilon, 1 - epsilon)
    correct = (scores > 0).astype(float)
    loss = -np.log(clipped)
    brier = (1.0 - probabilities) ** 2
    return {
        "selected_endpoints": len(selected),
        "induced_unique_train_pairs": len(induced),
        "outer_eval_pairs": len(eval_rows),
        "outer_eval_tasks": len({row.task for row in eval_rows}),
        "pairwise_accuracy": float(np.mean(correct)),
        "log_loss": float(np.mean(loss)),
        "brier_score": float(np.mean(brier)),
        "fit_seconds": fit_seconds,
        "query_seconds": query_seconds,
        "vocabulary_size": len(vectorizer.vocabulary_),
        "model_iterations": int(model.n_iter_[0]),
    }, {
        "correct": correct.tolist(),
        "log_loss": loss.tolist(),
        "brier": brier.tolist(),
        "probability": probabilities.tolist(),
    }


def pair_witness_rows(
    arm: str,
    budget: int,
    eval_rows: list[Any],
    probabilities: list[Any],
) -> list[dict[str, Any]]:
    require(len(probabilities) == len(eval_rows), "pair probability count")
    return [
        {
            "arm": arm,
            "endpoint_budget": budget,
            "pair_index": index,
            "pair_identity_sha256": pair_identity_sha(decision),
            "task_sha256": identity_sha("task", decision.task),
            "physical_run_sha256": identity_sha(
                "physical_run", decision.first_run
            ),
            "probability_first_better": float(probabilities[index]),
        }
        for index, decision in enumerate(eval_rows)
    ]


def arrays_from_pair_witness(rows: list[dict[str, Any]]) -> dict[str, list[Any]]:
    import numpy as np

    probabilities = np.asarray(
        [float(row["probability_first_better"]) for row in rows], dtype=float
    )
    require(
        probabilities.size > 0
        and bool(np.all(np.isfinite(probabilities)))
        and bool(np.all((probabilities >= 0) & (probabilities <= 1))),
        "checkpoint probabilities",
    )
    clipped = np.clip(probabilities, 1e-15, 1 - 1e-15)
    return {
        "correct": (probabilities > 0.5).astype(float).tolist(),
        "log_loss": (-np.log(clipped)).tolist(),
        "brier": ((1.0 - probabilities) ** 2).tolist(),
        "probability": probabilities.tolist(),
    }


def write_checkpoint_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    staging = path.parent / ".staging"
    staging.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = staging / f"{path.name}.{os.getpid()}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def build_fit(
    args: argparse.Namespace,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    protocol, protocol_sha = load_protocol(args.protocol.resolve(), args.protocol_sha256)
    public = object_file(args.selection_public.resolve())
    private_path = args.selection_private.resolve()
    private = object_file(private_path)
    require(public.get("protocol") == SELECTION_PUBLIC, "selection public protocol")
    require(public.get("classification") == "ENDPOINT_BUDGET_LABEL_EFFICIENCY_SMOKE_SELECTION_READY", "selection not ready")
    require(public.get("protocol_sha256") == protocol_sha, "selection protocol binding")
    require(file_sha(private_path) == public["private_selection_sha256"], "private selection SHA")
    require(private_path.stat().st_mode & 0o077 == 0, "private selection mode")
    require(private.get("protocol") == SELECTION_PRIVATE, "private protocol")
    require(private.get("protocol_sha256") == protocol_sha, "private protocol binding")
    require(private.get("selection_fingerprint_sha256") == sha_bytes(private["arms"]), "selection fingerprint")

    full, train, evaluation, _ = load_firewall_population(args, protocol_sha)
    checkpoints = budgets(train, protocol)
    require(private["checkpoints"] == checkpoints, "private checkpoints")
    arm_selections = {
        arm: entries_by_budget(private, arm)
        for arm in ("exact_b_uniform_edge", "yield_guarded_breadth")
    }
    train_nodes = set(train.nodes)
    require(all(selected <= train_nodes for values in arm_selections.values() for selected in values.values()), "selection outside train")
    all_needed = set(evaluation.nodes)
    all_needed.update(item for values in arm_selections.values() for selected in values.values() for item in selected)
    residual, codes = load_train_rows_and_codes(args, protocol, all_needed)
    topology_keys = {
        (edge.endpoints, edge.parent, edge.task, edge.run) for edge in full.edges
    }
    label_keys = {
        (row.unordered, row.parent, row.task, row.first_run) for row in residual
    }
    require(label_keys == topology_keys, "train label topology closure")
    train_rows = [row for row in residual if run_fold(row.first_run) != 0]
    eval_rows = [row for row in residual if run_fold(row.first_run) == 0]
    require(len(train_rows) == len(train.edges) and len(eval_rows) == len(evaluation.edges), "row graph alignment")
    require(all(row.split == "train" for row in train_rows + eval_rows), "frozen test access")
    eval_pair_keys = {(row.unordered, row.parent, row.task, row.first_run) for row in eval_rows}
    train_pair_keys = {(row.unordered, row.parent, row.task, row.first_run) for row in train_rows}
    require(not (train_pair_keys & eval_pair_keys), "outer pair overlap")
    eval_tasks = [identity_sha("task", row.task) for row in eval_rows]
    eval_runs = [identity_sha("physical_run", row.first_run) for row in eval_rows]
    fit_budgets = [
        checkpoints[protocol["selection"]["six_checkpoint_numerators"].index(value)]
        for value in protocol["selection"]["smoke_fit_numerators"]
    ]

    rows_out: list[dict[str, Any]] = []
    arrays: dict[tuple[str, int], dict[str, list[Any]]] = {}
    private_rows: list[dict[str, Any]] = []
    selection_public_sha = file_sha(args.selection_public.resolve())
    selection_private_sha = file_sha(private_path)
    checkpoint_root = args.checkpoint_dir.resolve()
    require(not checkpoint_root.is_symlink(), "checkpoint symlink")
    checkpoint_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(private_mode(checkpoint_root), "checkpoint private mode")
    expected_checkpoint_names = {
        f"{arm}__{budget}.json"
        for arm in ("exact_b_uniform_edge", "yield_guarded_breadth")
        for budget in fit_budgets
    }
    observed_names = {
        path.name
        for path in checkpoint_root.iterdir()
        if path.name != ".staging"
    }
    require(observed_names <= expected_checkpoint_names, "unexpected checkpoint entry")
    for arm in ("exact_b_uniform_edge", "yield_guarded_breadth"):
        for numerator, budget in zip(protocol["selection"]["smoke_fit_numerators"], fit_budgets):
            checkpoint_path = checkpoint_root / f"{arm}__{budget}.json"
            if checkpoint_path.exists():
                require(private_mode(checkpoint_path), "checkpoint cell mode")
                cell = object_file(checkpoint_path)
                require(
                    cell.get("protocol") == FIT_CELL
                    and cell.get("source_commit") == args.source_commit
                    and cell.get("protocol_sha256") == protocol_sha
                    and cell.get("selection_public_sha256") == selection_public_sha
                    and cell.get("selection_private_sha256") == selection_private_sha
                    and cell.get("arm") == arm
                    and cell.get("endpoint_budget") == budget
                    and cell.get("budget_numerator") == numerator,
                    "checkpoint cell binding",
                )
                metrics = cell["metrics"]
                pair_rows = cell["pair_rows"]
                per_pair = arrays_from_pair_witness(pair_rows)
            else:
                metrics, per_pair = fit_one(
                    arm_selections[arm][budget], train_rows, eval_rows, codes
                )
                pair_rows = pair_witness_rows(
                    arm, budget, eval_rows, per_pair["probability"]
                )
                cell = {
                    "protocol": FIT_CELL,
                    "source_commit": args.source_commit,
                    "protocol_sha256": protocol_sha,
                    "selection_public_sha256": selection_public_sha,
                    "selection_private_sha256": selection_private_sha,
                    "arm": arm,
                    "endpoint_budget": budget,
                    "budget_numerator": numerator,
                    "metrics": metrics,
                    "pair_rows": pair_rows,
                    "raw_identities_emitted": False,
                }
                write_checkpoint_atomic(checkpoint_path, cell)
            require(
                len(pair_rows) == len(eval_rows)
                and [row["pair_index"] for row in pair_rows]
                == list(range(len(eval_rows)))
                and all(
                    row["arm"] == arm
                    and row["endpoint_budget"] == budget
                    and row["pair_identity_sha256"] == pair_identity_sha(decision)
                    and row["task_sha256"] == identity_sha("task", decision.task)
                    and row["physical_run_sha256"]
                    == identity_sha("physical_run", decision.first_run)
                    for row, decision in zip(pair_rows, eval_rows)
                ),
                "checkpoint pair binding",
            )
            recomputed_metrics = {
                "pairwise_accuracy": sum(per_pair["correct"]) / len(eval_rows),
                "log_loss": sum(per_pair["log_loss"]) / len(eval_rows),
                "brier_score": sum(per_pair["brier"]) / len(eval_rows),
            }
            require(
                all(
                    math.isclose(
                        float(metrics[key]), value, rel_tol=1e-12, abs_tol=1e-12
                    )
                    for key, value in recomputed_metrics.items()
                ),
                "checkpoint aggregate metrics",
            )
            row = {
                "protocol": FIT_RESULT,
                "source_commit": args.source_commit,
                "protocol_sha256": protocol_sha,
                "selection_public_sha256": selection_public_sha,
                "selection_private_sha256": selection_private_sha,
                "outer_eval_fold": 0,
                "arm": arm,
                "budget_numerator": numerator,
                "budget_denominator": 32,
                "endpoint_budget": budget,
                **metrics,
                "gpu": 0,
                "api_calls": 0,
                "base_model_updates": 0,
            }
            rows_out.append(row)
            arrays[(arm, budget)] = per_pair
            private_rows.extend(pair_rows)

    comparisons: dict[str, Any] = {}
    repetitions = int(protocol["metrics"]["inference"]["task_clustered_paired_bootstrap_repetitions"])
    bootstrap_seed = int(protocol["metrics"]["inference"]["bootstrap_seed"])
    task_counts = Counter(eval_tasks)
    dominant_count = max(task_counts.values())
    dominant_task = min(
        task for task, count in task_counts.items() if count == dominant_count
    )
    keep = [index for index, task in enumerate(eval_tasks) if task != dominant_task]
    for budget in fit_budgets:
        uniform = arrays[("exact_b_uniform_edge", budget)]
        guarded = arrays[("yield_guarded_breadth", budget)]
        delta_accuracy = [b - a for a, b in zip(uniform["correct"], guarded["correct"])]
        delta_loss = [b - a for a, b in zip(uniform["log_loss"], guarded["log_loss"])]
        delta_brier = [b - a for a, b in zip(uniform["brier"], guarded["brier"])]
        comparisons[str(budget)] = {
            "yield_minus_uniform": {
                "pairwise_accuracy": sum(delta_accuracy) / len(delta_accuracy),
                "log_loss": sum(delta_loss) / len(delta_loss),
                "brier_score": sum(delta_brier) / len(delta_brier),
            },
            "accuracy_task_clustered_bootstrap": bootstrap_interval(
                delta_accuracy, eval_tasks, repetitions, bootstrap_seed + budget
            ),
            "accuracy_run_clustered_bootstrap": bootstrap_interval(
                delta_accuracy, eval_runs, repetitions, bootstrap_seed + 1000 + budget
            ),
            "drop_dominant_task": {
                "dropped_pair_count": dominant_count,
                "retained_pair_count": len(keep),
                "accuracy_delta_yield_minus_uniform": (
                    sum(delta_accuracy[index] for index in keep) / len(keep)
                ),
            },
        }
    terminal = comparisons[str(fit_budgets[-1])]
    advancement = {
        "accuracy_delta_positive_at_both_budgets": all(
            comparisons[str(budget)]["yield_minus_uniform"]["pairwise_accuracy"] > 0
            for budget in fit_budgets
        ),
        "terminal_log_loss_nonworse": terminal["yield_minus_uniform"]["log_loss"] <= 0,
        "terminal_brier_nonworse": terminal["yield_minus_uniform"]["brier_score"] <= 0,
        "drop_dominant_task_terminal_accuracy_delta_nonnegative": terminal["drop_dominant_task"]["accuracy_delta_yield_minus_uniform"] >= 0,
    }
    private_witness = {
        "protocol": FIT_PRIVATE,
        "protocol_sha256": protocol_sha,
        "source_commit": args.source_commit,
        "selection_public_sha256": selection_public_sha,
        "selection_private_sha256": selection_private_sha,
        "outer_eval_fold": 0,
        "outer_eval_pair_count": len(eval_rows),
        "arm_budget_count": len(rows_out),
        "rows": private_rows,
        "raw_identities_emitted": False,
    }
    summary = {
        "protocol": FIT_RESULT,
        "status": "COMPLETE",
        "protocol_sha256": protocol_sha,
        "source_commit": args.source_commit,
        "selection": {
            "public_sha256": selection_public_sha,
            "private_sha256": selection_private_sha,
            "fingerprint_sha256": private["selection_fingerprint_sha256"],
        },
        "fit_checkpoints": {
            name: file_sha(checkpoint_root / name)
            for name in sorted(expected_checkpoint_names)
        },
        "private_pair_witness_sha256": sha_bytes(private_witness),
        "population": {
            "outer_train_pairs": len(train_rows),
            "outer_eval_pairs": len(eval_rows),
            "outer_eval_tasks": len(set(eval_tasks)),
            "outer_eval_physical_runs": len(set(eval_runs)),
            "train_eval_pair_overlap": 0,
            "train_eval_endpoint_overlap": 0,
            "train_eval_physical_run_overlap": 0,
            "all_source_rows_intask_split_train": True,
        },
        "model_rows": rows_out,
        "paired_comparisons": comparisons,
        "dominant_task": {
            "identity_emitted": False,
            "pair_count": dominant_count,
            "pair_share": forward.ratio(dominant_count, len(eval_rows)),
        },
        "advancement_gates": advancement,
        "classification": (
            "HISTORICAL_SINGLE_FOLD_ENDPOINT_LABEL_EFFICIENCY_SMOKE_ADVANCES"
            if all(advancement.values())
            else "HISTORICAL_SINGLE_FOLD_ENDPOINT_LABEL_EFFICIENCY_SMOKE_DOES_NOT_ADVANCE"
        ),
        "scope": {
            "single_outer_fold_smoke_not_scientific_confirmation": True,
            "historical_source_rows_intask_split_train_only": True,
            "senior_test_rows_used": False,
            "prospective_first960_target300_target522_values_used": False,
            "public_identities_or_per_pair_predictions_emitted": False,
            "private_hashed_pair_witness_mode0600": True,
            "fit_checkpoint_resume_supported": True,
            "gpu_api_base_model_update": "0/0/0",
            "critic_model_fits": len(rows_out),
        },
    }
    require(public_has_no_identities(summary, full), "fit public identity leak")
    return summary, rows_out, private_witness


def write_json_exclusive(path: Path, value: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(canonical_bytes(value))


def write_csv_exclusive(path: Path, rows: list[dict[str, Any]]) -> None:
    require(rows, "CSV rows")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
        handle.write(buffer.getvalue())


def common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--firewall-receipt", type=Path, required=True)
    parser.add_argument("--train-topology", type=Path, required=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    selection = subparsers.add_parser("select")
    common_arguments(selection)
    selection.add_argument("--public-output", type=Path, required=True)
    selection.add_argument("--private-output", type=Path, required=True)
    fit = subparsers.add_parser("fit")
    common_arguments(fit)
    fit.add_argument("--train-labels", type=Path, required=True)
    fit.add_argument("--cards-root", type=Path, required=True)
    fit.add_argument("--selection-public", type=Path, required=True)
    fit.add_argument("--selection-private", type=Path, required=True)
    fit.add_argument("--checkpoint-dir", type=Path, required=True)
    fit.add_argument("--summary-output", type=Path, required=True)
    fit.add_argument("--runs-csv", type=Path, required=True)
    fit.add_argument("--private-pairs-output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    require(len(args.source_commit) == 40 and all(character in "0123456789abcdef" for character in args.source_commit), "source commit")
    if args.mode == "select":
        public, private = build_selection(args)
        if private is not None:
            write_json_exclusive(args.private_output.resolve(), private)
            require(file_sha(args.private_output.resolve()) == public["private_selection_sha256"], "written private SHA")
        else:
            require(not args.private_output.exists(), "private output on stop")
        write_json_exclusive(args.public_output.resolve(), public)
        print(json.dumps({
            "classification": public["classification"],
            "public_sha256": file_sha(args.public_output.resolve()),
            "private_written": private is not None,
            "scope": public["scope"],
        }, sort_keys=True))
    else:
        summary, rows, private_pairs = build_fit(args)
        write_json_exclusive(args.private_pairs_output.resolve(), private_pairs)
        require(
            file_sha(args.private_pairs_output.resolve())
            == summary["private_pair_witness_sha256"],
            "written private pair witness SHA",
        )
        write_json_exclusive(args.summary_output.resolve(), summary)
        write_csv_exclusive(args.runs_csv.resolve(), rows)
        print(json.dumps({
            "classification": summary["classification"],
            "summary_sha256": file_sha(args.summary_output.resolve()),
            "runs_csv_sha256": file_sha(args.runs_csv.resolve()),
            "private_pairs_sha256": file_sha(args.private_pairs_output.resolve()),
            "scope": summary["scope"],
        }, sort_keys=True))


if __name__ == "__main__":
    main()
