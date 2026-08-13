#!/usr/bin/env python3
"""Independent full re-enumeration and refit verifier for TGCA discovery.

This file intentionally does not import ``phase1.tgca_discovery``.  It rebuilds the
finite populations, all three augmentation manifests, all 20 linear models, graph
statistics, paired metrics, and literal gates from the locked inputs.
"""

from __future__ import annotations

import argparse
import bisect
import collections
import csv
import hashlib
import itertools
import json
import math
import os
import random
import warnings
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np


PROTOCOL = "tgca_v11_train_oof_discovery_v1"
ARMS = (
    "sibling_only",
    "sibling_reweight_control",
    "uniform_crossrun_control",
    "tgca",
)
MODEL_SEED = 887
EDGE_SEED = 20_260_814
BOOTSTRAP_SEED = 20_260_815
BOOTSTRAP_REPS = 10_000
FOLDS = 5
GAP_UPPERS = (1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1, math.inf)
EPSILON = 1e-12
SCORE_ATOL = 1e-10
TASK_SUPPORT_MIN_PAIRS = 20
EXPECTED = {"pairs": 4263, "runs": 333, "tasks": 23, "parents": 2293, "endpoints": 5499}


class VerificationError(RuntimeError):
    pass


class UnionFind:
    def __init__(self, nodes: Iterable[str]):
        self.leader = {node: node for node in nodes}
        self.weight = {node: 1 for node in nodes}

    def root(self, node: str) -> str:
        trail = []
        while self.leader[node] != node:
            trail.append(node)
            node = self.leader[node]
        for item in trail:
            self.leader[item] = node
        return node

    def join(self, left: str, right: str) -> bool:
        a, b = self.root(left), self.root(right)
        if a == b:
            return False
        if self.weight[a] < self.weight[b] or (self.weight[a] == self.weight[b] and a > b):
            a, b = b, a
        self.leader[b] = a
        self.weight[a] += self.weight[b]
        return True

    def sizes(self) -> list[int]:
        return sorted(collections.Counter(self.root(node) for node in self.leader).values(), reverse=True)


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1 << 20)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def digest_json(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def reject_name(path: Path) -> None:
    if any(word in path.name.lower() for word in ("frozen", "test", "held")):
        raise VerificationError(f"forbidden input basename: {path.name}")


def task_of(value: Any) -> str:
    return str(value.get("name") or value.get("desc") or "") if isinstance(value, dict) else str(value or "")


def finite(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise VerificationError(f"invalid {label}") from error
    if not math.isfinite(result):
        raise VerificationError(f"non-finite {label}")
    return result


def bin_of(gap: float) -> int:
    if gap < 0 or not math.isfinite(gap):
        raise VerificationError("invalid gap")
    return bisect.bisect_right(GAP_UPPERS, gap)


def order_hash(*parts: object) -> str:
    return hashlib.sha256("\t".join(map(str, parts)).encode()).hexdigest()


def winner(first: str, second: str, grades: dict[str, float], minimize: bool):
    a, b = grades[first], grades[second]
    if a == b:
        return None
    first_is_better = a < b if minimize else a > b
    better, worse = (first, second) if first_is_better else (second, first)
    return better, worse, round(abs(a - b), 6)


def view(code: str) -> str:
    return code if len(code) <= 20_000 else code[:5_000] + "\n# <FIXED_HEAD_TAIL_TRUNCATION>\n" + code[-15_000:]


def read_inputs(args: argparse.Namespace):
    for path in (args.pairs, args.cards, args.fold_oof, args.orientation):
        reject_name(path)
    expected = {
        args.pairs: args.expect_pairs_sha256,
        args.cards: args.expect_cards_sha256,
        args.fold_oof: args.expect_fold_oof_sha256,
        args.orientation: args.expect_orientation_sha256,
        args.protocol_json: args.expect_protocol_sha256,
    }
    for path, wanted in expected.items():
        if digest_file(path) != wanted.lower():
            raise VerificationError(f"input SHA mismatch: {path}")
    protocol = json.loads(args.protocol_json.read_text(encoding="utf-8"))
    if protocol.get("protocol") != PROTOCOL or protocol.get("status") != "OUTCOME_BLIND_FROZEN":
        raise VerificationError("protocol status mismatch")

    pairs = [json.loads(line) for line in args.pairs.read_text(encoding="utf-8").splitlines() if line]
    with args.fold_oof.open(encoding="utf-8", newline="") as handle:
        folds = list(csv.DictReader(handle))
    if len(pairs) != len(folds):
        raise VerificationError("pair/fold length mismatch")
    rows = []
    metadata = {}
    seen_runs = {}
    seen_pairs = set()
    for index, (pair, fold_row) in enumerate(zip(pairs, folds)):
        if pair.get("intask_split") != "train" or int(pair.get("budget", -1)) != 0:
            raise VerificationError("non-train pair")
        identity = {
            "task": str(pair["task"]), "run": str(pair["run_id"]),
            "parent": str(pair["parent"]), "better": str(pair["better"]),
            "worse": str(pair["worse"]),
        }
        if int(fold_row["row_index"]) != index or any(str(fold_row[key]) != value for key, value in identity.items()):
            raise VerificationError(f"fold identity mismatch: {index}")
        fold = int(fold_row["fold"])
        if fold not in range(FOLDS):
            raise VerificationError("bad fold")
        if seen_runs.setdefault(identity["run"], fold) != fold:
            raise VerificationError("run split")
        unordered = tuple(sorted((identity["better"], identity["worse"])))
        if unordered in seen_pairs or unordered[0] == unordered[1]:
            raise VerificationError("duplicate pair")
        seen_pairs.add(unordered)
        gap = finite(pair["gap_raw"], "gap")
        rows.append({"row_index": index, **identity, "gap_raw": gap, "fold": fold})
        endpoint_meta = {key: identity[key] for key in ("task", "run", "parent")}
        endpoint_meta["fold"] = fold
        for side in ("better", "worse"):
            if metadata.setdefault(identity[side], endpoint_meta) != endpoint_meta:
                raise VerificationError("endpoint metadata mismatch")
    support = {
        "pairs": len(rows), "runs": len(seen_runs), "tasks": len({r["task"] for r in rows}),
        "parents": len({r["parent"] for r in rows}), "endpoints": len(metadata),
    }
    if support != EXPECTED:
        raise VerificationError(f"support mismatch: {support}")

    cards = {}
    for line in args.cards.open(encoding="utf-8"):
        card = json.loads(line)
        card_id = str(card["id"])
        if card_id not in metadata:
            continue
        if card_id in cards:
            raise VerificationError("duplicate card")
        meta = metadata[card_id]
        code = str(card.get("code") or "")
        lineage = card.get("lineage") or {}
        if (not code or task_of(card.get("task")) != meta["task"] or
                str(card.get("run_id")) != meta["run"] or
                str(lineage.get("parent_id")) != meta["parent"]):
            raise VerificationError(f"card metadata mismatch: {card_id}")
        cards[card_id] = {
            **meta,
            "code": code,
            "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
            "grade": finite((card.get("label") or {}).get("graded"), "grade"),
        }
    if set(cards) != set(metadata):
        raise VerificationError("card coverage")
    orientation_raw = json.loads(args.orientation.read_text(encoding="utf-8"))
    tasks = {row["task"] for row in rows}
    if not tasks <= set(orientation_raw) or any(not isinstance(orientation_raw[t], bool) for t in tasks):
        raise VerificationError("orientation coverage")
    orientation = {task: orientation_raw[task] for task in tasks}
    grades = {card_id: float(card["grade"]) for card_id, card in cards.items()}
    for row in rows:
        oriented = winner(row["better"], row["worse"], grades, orientation[row["task"]])
        if oriented is None or oriented[:2] != (row["better"], row["worse"]) or abs(oriented[2] - row["gap_raw"]) > EPSILON:
            raise VerificationError("pair orientation/gap mismatch")
    return rows, cards, orientation, support


def candidate_population(ids, cards, orientation):
    by_task = collections.defaultdict(list)
    for card_id in ids:
        by_task[cards[card_id]["task"]].append(card_id)
    grades = {card_id: cards[card_id]["grade"] for card_id in ids}
    output = []
    for task in sorted(by_task):
        for a, b in itertools.combinations(sorted(by_task[task]), 2):
            if cards[a]["run"] == cards[b]["run"]:
                continue
            oriented = winner(a, b, grades, orientation[task])
            if oriented is None:
                continue
            better, worse, gap = oriented
            output.append({
                "task": task, "better": better, "worse": worse, "gap_raw": gap,
                "gap_bin": bin_of(gap), "left": min(a, b), "right": max(a, b),
            })
    return output


def independent_selection(fold, base, population, ids):
    original = collections.defaultdict(list)
    targets = collections.Counter()
    degree = collections.Counter()
    graph = UnionFind(ids)
    for row in base:
        task = row["task"]
        original[task].append(row)
        targets[(task, bin_of(row["gap_raw"]))] += 1
        degree[row["better"]] += 1
        degree[row["worse"]] += 1
        graph.join(row["better"], row["worse"])
    by_cell = collections.defaultdict(list)
    by_task = collections.defaultdict(list)
    for row in population:
        by_cell[(row["task"], row["gap_bin"])].append(row)
        by_task[row["task"]].append(row)
    target_edges = []
    for task, gap_index in sorted(targets):
        pool = by_cell[(task, gap_index)]
        count = min(targets[(task, gap_index)], len(pool))
        ordered = sorted(pool, key=lambda row: (
            max(degree[row["left"]], degree[row["right"]]),
            degree[row["left"]] + degree[row["right"]],
            order_hash(EDGE_SEED, fold, "tgca", task, gap_index, row["left"], row["right"]),
        ))
        chosen = set()
        for row in ordered:
            if len(chosen) == count:
                break
            key = (row["left"], row["right"])
            if graph.root(key[0]) != graph.root(key[1]):
                chosen.add(key)
                graph.join(*key)
                target_edges.append(dict(row))
        for row in ordered:
            if len(chosen) == count:
                break
            key = (row["left"], row["right"])
            if key not in chosen:
                chosen.add(key)
                graph.join(*key)
                target_edges.append(dict(row))
        if len(chosen) != count:
            raise VerificationError("TGCA selection underflow")
    counts = collections.Counter(row["task"] for row in target_edges)
    reweight, uniform = [], []
    for task in sorted(original):
        count = counts[task]
        base_order = sorted(original[task], key=lambda row: order_hash(EDGE_SEED, fold, "reweight", task, row["row_index"]))
        uniform_order = sorted(by_task[task], key=lambda row: order_hash(EDGE_SEED, fold, "uniform", task, row["left"], row["right"]))
        if count > len(base_order) or count > len(uniform_order):
            raise VerificationError("control underflow")
        for row in base_order[:count]:
            item = dict(row)
            item.update({
                "gap_bin": bin_of(row["gap_raw"]),
                "left": min(row["better"], row["worse"]),
                "right": max(row["better"], row["worse"]),
            })
            reweight.append(item)
        uniform.extend(dict(row) for row in uniform_order[:count])
    return {
        "sibling_only": [], "sibling_reweight_control": reweight,
        "uniform_crossrun_control": uniform, "tgca": target_edges,
    }


def manifest_rows(fold, selected):
    output = []
    for arm in ARMS[1:]:
        for index, row in enumerate(selected[arm]):
            output.append({
                "fold": fold, "arm": arm, "edge_index": index, "task": row["task"],
                "better": row["better"], "worse": row["worse"],
                "gap_raw": float(row["gap_raw"]), "gap_bin": int(row["gap_bin"]),
                "left": row["left"], "right": row["right"],
                "source_row_index": row.get("row_index"),
            })
    return output


def component_summary(nodes, edges):
    unique = sorted({tuple(sorted(edge)) for edge in edges if edge[0] != edge[1]})
    graph = UnionFind(nodes)
    for edge in unique:
        graph.join(*edge)
    sizes = graph.sizes()
    return unique, len(sizes), sizes[0] if sizes else 0


def lambda_two(nodes, edges, component_count):
    if len(nodes) < 2 or component_count != 1:
        return 0.0
    from scipy import sparse
    from scipy.sparse import csgraph
    from scipy.sparse.linalg import eigsh

    position = {node: i for i, node in enumerate(nodes)}
    rr, cc = [], []
    for a, b in edges:
        rr.extend((position[a], position[b]))
        cc.extend((position[b], position[a]))
    adjacency = sparse.csr_matrix((np.ones(len(rr)), (rr, cc)), shape=(len(nodes), len(nodes)))
    lap = csgraph.laplacian(adjacency, normed=True)
    if len(nodes) <= 64:
        eigenvalues = np.linalg.eigvalsh(lap.toarray())[:2]
    else:
        eigenvalues = np.sort(eigsh(lap, k=2, which="SM", v0=np.linspace(1, 2, len(nodes)), tol=1e-9)[0])
    return float(max(0.0, eigenvalues[1]))


def independent_graph_rows(fold, base, selected, ids, cards):
    nodes = collections.defaultdict(list)
    base_task = collections.defaultdict(list)
    for card_id in ids:
        nodes[cards[card_id]["task"]].append(card_id)
    for row in base:
        base_task[row["task"]].append(row)
    output = []
    for arm in ARMS:
        added = collections.defaultdict(list)
        for row in selected[arm]:
            added[row["task"]].append(row)
        for task in sorted(nodes):
            node_list = sorted(nodes[task])
            edge_list = [(row["better"], row["worse"]) for row in base_task[task]]
            if arm != "sibling_reweight_control":
                edge_list.extend((row["better"], row["worse"]) for row in added[task])
            unique, components, largest = component_summary(node_list, edge_list)
            gap_counts = collections.Counter(row["gap_bin"] for row in added[task])
            output.append({
                "fold": fold, "task": task, "arm": arm, "nodes": len(node_list),
                "base_edges": len(base_task[task]), "augmentation_rows": len(added[task]),
                "unique_edges": len(unique), "components": components,
                "largest_component_nodes": largest,
                "largest_component_share": largest / len(node_list),
                "normalized_algebraic_connectivity": lambda_two(node_list, unique, components),
                "augmentation_gap_bins": json.dumps(dict(sorted(gap_counts.items()))),
            })
    return output


def refit_fold(base, selected, fit_ids, valid_ids, cards):
    from scipy import sparse
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    vectorizer = TfidfVectorizer(
        analyzer="char_wb", dtype=np.float64, max_features=30_000, min_df=3,
        ngram_range=(3, 5), sublinear_tf=True,
    )
    fit_matrix = vectorizer.fit_transform([view(cards[card_id]["code"]) for card_id in fit_ids])
    valid_matrix = vectorizer.transform([view(cards[card_id]["code"]) for card_id in valid_ids])
    location = {card_id: index for index, card_id in enumerate(fit_ids)}
    output = {}
    for arm in ARMS:
        training = [*base, *selected[arm]]
        better = np.asarray([location[row["better"]] for row in training])
        worse = np.asarray([location[row["worse"]] for row in training])
        difference = fit_matrix[better] - fit_matrix[worse]
        design = sparse.vstack([difference, -difference], format="csr")
        labels = np.r_[np.ones(len(training), dtype=np.int8), np.zeros(len(training), dtype=np.int8)]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model = LogisticRegression(
                C=0.5, fit_intercept=False, max_iter=2000, random_state=MODEL_SEED,
                solver="liblinear", tol=1e-6,
            ).fit(design, labels)
        if any(issubclass(item.category, ConvergenceWarning) for item in caught):
            raise VerificationError("refit convergence warning")
        values = np.asarray(valid_matrix @ model.coef_.reshape(-1), dtype=np.float64).reshape(-1)
        if not np.isfinite(values).all():
            raise VerificationError("non-finite refit")
        output[arm] = dict(zip(valid_ids, map(float, values)))
    return output


def producer_scores(path, rows):
    with path.open(encoding="utf-8", newline="") as handle:
        emitted = list(csv.DictReader(handle))
    if len(emitted) != len(rows):
        raise VerificationError("producer prediction count")
    scores = {arm: {} for arm in ARMS}
    for row, output in zip(rows, emitted):
        if int(output["row_index"]) != row["row_index"] or any(output[key] != str(row[key]) for key in ("task", "run", "parent", "better", "worse")):
            raise VerificationError("producer prediction identity")
        for arm in ARMS:
            for side in ("better", "worse"):
                card_id = row[side]
                value = finite(output[f"{arm}_{side}_score"], "producer score")
                previous = scores[arm].setdefault(card_id, value)
                if abs(previous - value) > SCORE_ATOL:
                    raise VerificationError("producer endpoint score inconsistency")
    return scores


def hit(value):
    return 1.0 if value > EPSILON else 0.0 if value < -EPSILON else 0.5


def quantile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return ordered[low]
    weight = position - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def clustered(records, key, seed):
    grouped = collections.defaultdict(list)
    for record in records:
        grouped[record[key]].append(record["value"])
    means = {name: sum(values) / len(values) for name, values in sorted(grouped.items())}
    population = list(means.values())
    rng = random.Random(seed)
    draws = [sum(population[rng.randrange(len(population))] for _ in population) / len(population) for _ in range(BOOTSTRAP_REPS)]
    return {
        "clusters": len(population), "estimate": sum(population) / len(population),
        "ci95": [quantile(draws, 0.025), quantile(draws, 0.975)],
        "per_cluster": means, "repetitions": BOOTSTRAP_REPS, "seed": seed,
    }


def summarize(records, offset):
    return {
        "overall": sum(item["value"] for item in records) / len(records), "records": len(records),
        "run": clustered(records, "run", BOOTSTRAP_SEED + offset),
        "task": clustered(records, "task", BOOTSTRAP_SEED + offset + 1),
    }


def calculate_metrics(rows, scores, offset):
    pair = [{
        "name": str(row["row_index"]), "run": row["run"], "task": row["task"],
        "value": hit(scores[row["better"]] - scores[row["worse"]]),
    } for row in rows]
    groups = collections.defaultdict(list)
    for row in rows:
        groups[row["parent"]].append(row)
    top, utility = [], []
    incomplete = 0
    for parent, items in sorted(groups.items()):
        candidates = {item[key] for item in items for key in ("better", "worse")}
        common = {"name": parent, "run": items[0]["run"], "task": items[0]["task"]}
        denominator = sum(item["gap_raw"] for item in items)
        utility.append({**common, "value": sum(item["gap_raw"] * hit(scores[item["better"]] - scores[item["worse"]]) for item in items) / denominator})
        if len(items) != len(candidates) * (len(candidates) - 1) // 2:
            incomplete += 1
            continue
        losses = collections.Counter({candidate: 0 for candidate in candidates})
        for item in items:
            losses[item["worse"]] += 1
        truth = {candidate for candidate in candidates if losses[candidate] == min(losses.values())}
        maximum = max(scores[candidate] for candidate in candidates)
        prediction = {candidate for candidate in candidates if abs(scores[candidate] - maximum) <= EPSILON}
        top.append({**common, "value": len(truth & prediction) / len(prediction)})
    return {
        "pair": summarize(pair, offset),
        "top1": {**summarize(top, offset + 10), "complete_parents": len(top), "incomplete_parents": incomplete},
        "utility": {**summarize(utility, offset + 20), "definition": "mean_parent(sum(gap_raw*hit)/sum(gap_raw))"},
        "_pair": pair, "_top1": top, "_utility": utility,
    }


def delta(left, right, offset):
    a = {item["name"]: item for item in left}
    b = {item["name"]: item for item in right}
    if set(a) != set(b):
        raise VerificationError("delta support")
    records = [{
        "name": name, "run": a[name]["run"], "task": a[name]["task"],
        "value": a[name]["value"] - b[name]["value"],
    } for name in sorted(a)]
    if any(a[name][key] != b[name][key] for name in a for key in ("run", "task")):
        raise VerificationError("delta cluster")
    return summarize(records, offset)


def gates(comparisons, rows, integrity):
    sibling = comparisons["tgca_minus_sibling_only"]
    reweight = comparisons["tgca_minus_sibling_reweight_control"]
    counts = collections.Counter(row["task"] for row in rows)
    supported = sorted(task for task, count in counts.items() if count >= TASK_SUPPORT_MIN_PAIRS)
    task_delta = sibling["utility"]["task"]["per_cluster"]
    values = {task: task_delta[task] for task in supported}
    nonnegative = sum(value >= 0 for value in values.values())
    positive = lambda item: item["run"]["ci95"][0] > 0 and item["task"]["ci95"][0] > 0
    conditions = {
        "tgca_minus_sibling_utility_effect": sibling["utility"]["overall"] >= 0.02 and positive(sibling["utility"]),
        "tgca_minus_reweight_utility_effect": reweight["utility"]["overall"] >= 0.015 and positive(reweight["utility"]),
        "tgca_minus_sibling_top1_effect": sibling["top1"]["overall"] >= 0.02 and positive(sibling["top1"]),
        "supported_tasks_ge_15": len(supported) >= 15,
        "dominant_task_share_le_025": max(counts.values()) / len(rows) <= 0.25,
        "nonnegative_task_utility_share_ge_060": nonnegative / len(supported) >= 0.6,
        "integrity_all": all(integrity.values()),
    }
    return {
        "conditions": conditions, "all": all(conditions.values()),
        "task_support_min_pairs": TASK_SUPPORT_MIN_PAIRS, "supported_tasks": len(supported),
        "supported_task_names": supported, "dominant_task_share": max(counts.values()) / len(rows),
        "nonnegative_task_utility": nonnegative,
        "nonnegative_task_utility_share": nonnegative / len(supported),
        "supported_task_utility_deltas": values,
    }


def compare_nested(left, right, path="root", tolerance=1e-11):
    if isinstance(left, dict) and isinstance(right, dict):
        if set(left) != set(right):
            raise VerificationError(f"key mismatch at {path}")
        for key in left:
            compare_nested(left[key], right[key], f"{path}.{key}", tolerance)
    elif isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            raise VerificationError(f"length mismatch at {path}")
        for index, (a, b) in enumerate(zip(left, right)):
            compare_nested(a, b, f"{path}[{index}]", tolerance)
    elif isinstance(left, (int, float)) and isinstance(right, (int, float)) and not isinstance(left, bool) and not isinstance(right, bool):
        if not math.isclose(float(left), float(right), rel_tol=0, abs_tol=tolerance):
            raise VerificationError(f"numeric mismatch at {path}: {left} != {right}")
    elif left != right:
        raise VerificationError(f"value mismatch at {path}: {left!r} != {right!r}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", required=True, type=Path)
    parser.add_argument("--cards", required=True, type=Path)
    parser.add_argument("--fold-oof", required=True, type=Path)
    parser.add_argument("--orientation", required=True, type=Path)
    parser.add_argument("--protocol-json", required=True, type=Path)
    parser.add_argument("--result-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expect-pairs-sha256", required=True)
    parser.add_argument("--expect-cards-sha256", required=True)
    parser.add_argument("--expect-fold-oof-sha256", required=True)
    parser.add_argument("--expect-orientation-sha256", required=True)
    parser.add_argument("--expect-protocol-sha256", required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    rows, cards, orientation, support = read_inputs(args)
    producer_summary = json.loads((args.result_dir / "summary.json").read_text(encoding="utf-8"))
    if producer_summary.get("protocol") != PROTOCOL:
        raise VerificationError("producer protocol")
    for name, digest in (
        ("oof_predictions.csv", producer_summary["outputs"]["oof_predictions_sha256"]),
        ("selected_edges.jsonl", producer_summary["outputs"]["selected_edges_sha256"]),
        ("graph_stats.csv", producer_summary["outputs"]["graph_stats_sha256"]),
        ("fit_runs.csv", producer_summary["outputs"]["fit_runs_sha256"]),
        ("per_task.csv", producer_summary["outputs"]["per_task_sha256"]),
    ):
        if digest_file(args.result_dir / name) != digest:
            raise VerificationError(f"producer output SHA: {name}")
    produced_scores = producer_scores(args.result_dir / "oof_predictions.csv", rows)
    produced_edges = [json.loads(line) for line in (args.result_dir / "selected_edges.jsonl").read_text(encoding="utf-8").splitlines() if line]
    with (args.result_dir / "graph_stats.csv").open(encoding="utf-8", newline="") as handle:
        produced_graph = list(csv.DictReader(handle))

    rebuilt_scores = {arm: {} for arm in ARMS}
    rebuilt_edges = []
    rebuilt_graph = []
    isolation = []
    for fold in range(FOLDS):
        base = [dict(row) for row in rows if row["fold"] != fold]
        validation = [dict(row) for row in rows if row["fold"] == fold]
        fit_ids = sorted({row[key] for row in base for key in ("better", "worse")})
        valid_ids = sorted({row[key] for row in validation for key in ("better", "worse")})
        fit_runs, valid_runs = {row["run"] for row in base}, {row["run"] for row in validation}
        fit_codes = {cards[card_id]["code_sha256"] for card_id in fit_ids}
        valid_codes = {cards[card_id]["code_sha256"] for card_id in valid_ids}
        overlap = {
            "run": len(fit_runs & valid_runs), "endpoint": len(set(fit_ids) & set(valid_ids)),
            "raw_code": len(fit_codes & valid_codes),
        }
        if any(overlap.values()):
            raise VerificationError(f"fold leakage: {fold}/{overlap}")
        isolation.append(overlap)
        population = candidate_population(fit_ids, cards, orientation)
        selected = independent_selection(fold, base, population, fit_ids)
        rebuilt_edges.extend(manifest_rows(fold, selected))
        rebuilt_graph.extend(independent_graph_rows(fold, base, selected, fit_ids, cards))
        scores = refit_fold(base, selected, fit_ids, valid_ids, cards)
        for arm in ARMS:
            rebuilt_scores[arm].update(scores[arm])
        print("VERIFIED_FOLD", fold, flush=True)
    compare_nested(rebuilt_edges, produced_edges, "selected_edges", tolerance=0)

    graph_fields_int = {"fold", "nodes", "base_edges", "augmentation_rows", "unique_edges", "components", "largest_component_nodes"}
    graph_fields_float = {"largest_component_share", "normalized_algebraic_connectivity"}
    normalized_graph = []
    for row in produced_graph:
        item = dict(row)
        for key in graph_fields_int:
            item[key] = int(item[key])
        for key in graph_fields_float:
            item[key] = float(item[key])
        normalized_graph.append(item)
    compare_nested(rebuilt_graph, normalized_graph, "graph_stats", tolerance=1e-8)

    maximum_score_difference = 0.0
    for arm in ARMS:
        if set(rebuilt_scores[arm]) != set(produced_scores[arm]):
            raise VerificationError("score support")
        for card_id in rebuilt_scores[arm]:
            difference = abs(rebuilt_scores[arm][card_id] - produced_scores[arm][card_id])
            maximum_score_difference = max(maximum_score_difference, difference)
            if difference > SCORE_ATOL:
                raise VerificationError(f"refit score mismatch: {arm}/{card_id}/{difference}")

    raw_metrics = {arm: calculate_metrics(rows, rebuilt_scores[arm], index * 100) for index, arm in enumerate(ARMS)}
    metrics = {arm: {key: value for key, value in raw_metrics[arm].items() if not key.startswith("_")} for arm in ARMS}
    comparisons = {}
    for index, control in enumerate(ARMS[:-1]):
        comparisons[f"tgca_minus_{control}"] = {
            "pair": delta(raw_metrics["tgca"]["_pair"], raw_metrics[control]["_pair"], 1000 + index * 100),
            "top1": delta(raw_metrics["tgca"]["_top1"], raw_metrics[control]["_top1"], 1010 + index * 100),
            "utility": delta(raw_metrics["tgca"]["_utility"], raw_metrics[control]["_utility"], 1020 + index * 100),
        }
    integrity = {
        "support_exact": support == EXPECTED,
        "five_folds_complete": len(isolation) == FOLDS,
        "fit_valid_run_overlap_zero": all(item["run"] == 0 for item in isolation),
        "fit_valid_endpoint_overlap_zero": all(item["endpoint"] == 0 for item in isolation),
        "fit_valid_raw_code_overlap_zero": all(item["raw_code"] == 0 for item in isolation),
        "control_counts_exact": all(
            len([row for row in rebuilt_edges if row["fold"] == fold and row["arm"] == arm])
            == len([row for row in rebuilt_edges if row["fold"] == fold and row["arm"] == "tgca"])
            for fold in range(FOLDS) for arm in ARMS[1:]
        ),
        "all_models_converged": True,
        "oof_score_coverage_exact": all(set(rebuilt_scores[arm]) == set(cards) for arm in ARMS),
        "frozen_read_false": True,
        "temporal_vault_read_false": True,
    }
    rebuilt_gates = gates(comparisons, rows, integrity)
    compare_nested(metrics, producer_summary["metrics"], "metrics")
    compare_nested(comparisons, producer_summary["comparisons"], "comparisons")
    compare_nested(integrity, producer_summary["integrity"], "integrity")
    compare_nested(rebuilt_gates, producer_summary["gates"], "gates")
    expected_status = "TGCA_DISCOVERY_INVALID" if not all(integrity.values()) else "TGCA_DISCOVERY_UNLOCK" if rebuilt_gates["all"] else "TGCA_DISCOVERY_NO_UNLOCK"
    if producer_summary["status"] != expected_status:
        raise VerificationError("status mismatch")
    output = {
        "status": "VERIFIED_" + expected_status,
        "protocol": PROTOCOL,
        "producer_status": producer_summary["status"],
        "maximum_refit_score_abs_difference": maximum_score_difference,
        "score_tolerance": SCORE_ATOL,
        "selected_edges_exact": True,
        "graph_statistics_exact_with_atol_1e_8": True,
        "metrics_exact_with_atol_1e_11": True,
        "gates_exact": True,
        "integrity": integrity,
        "frozen_read": False,
        "temporal_vault_read": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, args.output)
    print(output["status"], f"max_score_abs={maximum_score_difference:.3g}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
