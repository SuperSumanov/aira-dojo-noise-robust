#!/usr/bin/env python3
"""Independent verifier for pairgraph_v11_train_oof_descriptive_v1.

This file deliberately does not import pairgraph_intervention.  It reopens the
four locked inputs, rebuilds endpoint scores and finite cross-run populations,
then recomputes transport metrics, task bootstraps, gates, CSV rows, and status.
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence


PROTOCOL = "pairgraph_v11_train_oof_descriptive_v1"
ARMS = ("fixed_frozen_global", "op_only_lr", "static_lr", "char_tfidf_lr")
HEADLINE = "char_tfidf_lr"
UPPERS = (1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1, math.inf)
HARD = 1e-2
MINIMUM = 5
REPS = 10_000
SEED = 9_887
TOL = 1e-12
EXPECTED = {"pairs": 4263, "runs": 333, "tasks": 23, "parents": 2293, "endpoints": 5499}
GRAPHS = ("sibling", "crossrun_uniform_transport", "crossrun_gap_transport")
CONTRASTS = {
    "total_pairing_inflation": ("crossrun_uniform_transport", "sibling"),
    "gap_composition_component": ("crossrun_uniform_transport", "crossrun_gap_transport"),
    "topology_residual": ("crossrun_gap_transport", "sibling"),
}


class VerificationError(RuntimeError):
    pass


@dataclass
class Bucket:
    count: int = 0
    gap_sum: float = 0.0
    hard_count: int = 0
    hits: dict[str, float] = field(default_factory=lambda: {arm: 0.0 for arm in ARMS})

    def add(self, gap: float, better: str, worse: str, scores: dict[str, dict[str, float]]) -> None:
        self.count += 1
        self.gap_sum += gap
        self.hard_count += int(gap < HARD)
        for arm in ARMS:
            delta = scores[better][arm] - scores[worse][arm]
            self.hits[arm] += 1.0 if delta > 0 else (0.0 if delta < 0 else 0.5)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def reject(path: Path, label: str) -> None:
    bad = [item for item in ("frozen", "test", "held") if item in path.name.lower()]
    if bad:
        raise VerificationError(f"forbidden {label} path token: {bad}")


def finite(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise VerificationError(f"invalid {label}: {value!r}") from exc
    if not math.isfinite(result):
        raise VerificationError(f"nonfinite {label}: {value!r}")
    return result


def task_of(value: Any) -> str:
    return str(value.get("name") or value.get("desc") or "") if isinstance(value, dict) else str(value or "")


def bin_of(gap: float) -> int:
    if gap < 0 or not math.isfinite(gap):
        raise VerificationError(f"bad gap: {gap}")
    return bisect.bisect_right(UPPERS, gap)


def interval(index: int) -> str:
    low = 0.0 if index == 0 else UPPERS[index - 1]
    high = UPPERS[index]
    return f"[{low:.12g},{'inf' if math.isinf(high) else f'{high:.12g}'})"


def qtile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    at = (len(ordered) - 1) * probability
    low, high = math.floor(at), math.ceil(at)
    if low == high:
        return ordered[low]
    return ordered[low] * (high - at) + ordered[high] * (at - low)


def boot(left: dict[str, float], right: dict[str, float]) -> dict[str, Any]:
    tasks = sorted(set(left) & set(right))
    changes = [left[task] - right[task] for task in tasks]
    rng = random.Random(SEED)
    samples = [
        sum(changes[rng.randrange(len(changes))] for _ in tasks) / len(tasks)
        for _ in range(REPS)
    ]
    return {
        "tasks": len(tasks),
        "estimate": sum(changes) / len(changes),
        "ci95": [qtile(samples, 0.025), qtile(samples, 0.975)],
        "reps": REPS,
        "seed": SEED,
        "per_task": dict(zip(tasks, changes)),
    }


def orient(a: str, b: str, grades: dict[str, float], lower: bool) -> tuple[str, str, float] | None:
    ga, gb = grades[a], grades[b]
    if ga == gb:
        return None
    a_wins = ga < gb if lower else ga > gb
    better, worse = (a, b) if a_wins else (b, a)
    return better, worse, round(abs(ga - gb), 6)


def read_inputs(
    oof_path: Path,
    pair_path: Path,
    card_path: Path,
    orientation_path: Path,
    hashes: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, float], dict[str, bool], dict[str, Any], dict[str, Any]]:
    for label, path in (("oof", oof_path), ("pairs", pair_path), ("cards", card_path), ("orientation", orientation_path)):
        reject(path, label)
        if digest(path) != hashes[label]:
            raise VerificationError(f"{label} SHA mismatch")
    with oof_path.open(encoding="utf-8", newline="") as handle:
        oof = list(csv.DictReader(handle))
    pairs = [json.loads(line) for line in pair_path.read_text(encoding="utf-8").splitlines() if line]
    if len(oof) != len(pairs):
        raise VerificationError("OOF/pair length mismatch")

    endpoints: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    unique_pairs: set[tuple[str, str]] = set()
    for index, (record, pair) in enumerate(zip(oof, pairs)):
        if int(record["row_index"]) != index or pair.get("intask_split") != "train" or int(pair.get("budget", -1)) != 0:
            raise VerificationError(f"bad row contract: {index}")
        mapping = {"task": "task", "run": "run_id", "parent": "parent", "better": "better", "worse": "worse"}
        for left, right in mapping.items():
            if record[left] != str(pair[right]):
                raise VerificationError(f"pair metadata mismatch {index}: {left}")
        gap = finite(record["gap_raw"], "gap")
        if not math.isclose(gap, finite(pair["gap_raw"], "pair gap"), rel_tol=0.0, abs_tol=TOL):
            raise VerificationError(f"gap mismatch: {index}")
        canonical = tuple(sorted((record["better"], record["worse"])))
        if canonical in unique_pairs or canonical[0] == canonical[1]:
            raise VerificationError(f"duplicate pair: {index}")
        unique_pairs.add(canonical)
        row_scores: dict[str, dict[str, float]] = {}
        for arm in ARMS:
            better_score = finite(record[f"{arm}_better_score"], "better score")
            worse_score = finite(record[f"{arm}_worse_score"], "worse score")
            predicted_hit = 1.0 if better_score > worse_score else (0.0 if better_score < worse_score else 0.5)
            if not math.isclose(predicted_hit, finite(record[f"{arm}_hit"], "saved hit"), rel_tol=0.0, abs_tol=TOL):
                raise VerificationError(f"hit mismatch: {index} {arm}")
            row_scores[arm] = {"better": better_score, "worse": worse_score}
        row = {
            "row_index": index,
            "task": record["task"],
            "run": record["run"],
            "parent": record["parent"],
            "better": record["better"],
            "worse": record["worse"],
            "gap": gap,
            "fold": int(record["fold"]),
            "scores": row_scores,
        }
        rows.append(row)
        metadata = {key: row[key] for key in ("task", "fold", "run", "parent")}
        for side in ("better", "worse"):
            card_id = row[side]
            scores = {arm: row_scores[arm][side] for arm in ARMS}
            if card_id not in endpoints:
                endpoints[card_id] = {**metadata, "scores": scores}
            else:
                prior = endpoints[card_id]
                if any(prior[key] != metadata[key] for key in metadata):
                    raise VerificationError(f"endpoint metadata mismatch: {card_id}")
                if any(not math.isclose(prior["scores"][arm], scores[arm], rel_tol=0.0, abs_tol=TOL) for arm in ARMS):
                    raise VerificationError(f"endpoint score mismatch: {card_id}")

    audit = {
        "rows": len(rows),
        "pairs": len(rows),
        "runs": len({row["run"] for row in rows}),
        "tasks": len({row["task"] for row in rows}),
        "parents": len({row["parent"] for row in rows}),
        "endpoints": len(endpoints),
        "endpoint_score_tolerance": TOL,
        "separable_arms": list(ARMS),
    }
    if any(audit[key] != EXPECTED[key] for key in EXPECTED):
        raise VerificationError(f"unexpected support: {audit}")

    grades: dict[str, float] = {}
    corpus_rows = 0
    with card_path.open("rb") as handle:
        for raw in handle:
            corpus_rows += 1
            card = json.loads(raw)
            card_id = str(card["id"])
            if card_id not in endpoints:
                continue
            if card_id in grades:
                raise VerificationError(f"duplicate selected card: {card_id}")
            endpoint = endpoints[card_id]
            if task_of(card.get("task")) != endpoint["task"] or str(card.get("run_id")) != endpoint["run"]:
                raise VerificationError(f"selected context mismatch: {card_id}")
            if str((card.get("lineage") or {}).get("parent_id")) != endpoint["parent"]:
                raise VerificationError(f"selected parent mismatch: {card_id}")
            grades[card_id] = finite((card.get("label") or {}).get("graded"), "grade")
    if set(grades) != set(endpoints):
        raise VerificationError("selected grade coverage mismatch")
    card_audit = {
        "corpus_rows": corpus_rows,
        "selected_cards": len(grades),
        "retained_fields": ["id", "task", "graded"],
        "code_fields_retained": 0,
        "observation_fields_retained": 0,
        "non_allowlisted_cards_retained": 0,
    }
    orientations_raw = json.loads(orientation_path.read_text(encoding="utf-8"))
    tasks = {row["task"] for row in rows}
    if not tasks <= set(orientations_raw):
        raise VerificationError("missing orientations")
    if any(not isinstance(orientations_raw[task], bool) for task in tasks):
        raise VerificationError("orientation values are not booleans")
    orientations = {task: bool(orientations_raw[task]) for task in tasks}
    return rows, endpoints, grades, orientations, audit, card_audit


def enumerate_populations(
    rows: Sequence[dict[str, Any]],
    endpoints: dict[str, dict[str, Any]],
    grades: dict[str, float],
    orientations: dict[str, bool],
) -> dict[str, Any]:
    scores = {card_id: value["scores"] for card_id, value in endpoints.items()}
    sibling: dict[tuple[str, int, int], Bucket] = collections.defaultdict(Bucket)
    for row in rows:
        answer = orient(row["better"], row["worse"], grades, orientations[row["task"]])
        if answer is None or answer[:2] != (row["better"], row["worse"]):
            raise VerificationError(f"orientation mismatch: {row['row_index']}")
        if not math.isclose(answer[2], row["gap"], rel_tol=0.0, abs_tol=TOL):
            raise VerificationError(f"raw gap mismatch: {row['row_index']}")
        sibling[(row["task"], row["fold"], bin_of(row["gap"]))].add(
            row["gap"], row["better"], row["worse"], scores
        )

    groups: dict[tuple[str, int], list[str]] = collections.defaultdict(list)
    for card_id, endpoint in endpoints.items():
        groups[(endpoint["task"], endpoint["fold"])].append(card_id)
    cells: dict[tuple[str, int], Bucket] = collections.defaultdict(Bucket)
    strata: dict[tuple[str, int, int], Bucket] = collections.defaultdict(Bucket)
    population_hash = hashlib.sha256()
    same_run = 0
    equal_grade = 0
    for (task, fold), card_ids in sorted(groups.items()):
        for first, second in itertools.combinations(sorted(card_ids), 2):
            if endpoints[first]["run"] == endpoints[second]["run"]:
                same_run += 1
                continue
            answer = orient(first, second, grades, orientations[task])
            if answer is None:
                equal_grade += 1
                continue
            better, worse, gap = answer
            cells[(task, fold)].add(gap, better, worse, scores)
            strata[(task, fold, bin_of(gap))].add(gap, better, worse, scores)
            population_hash.update(f"{task}\t{fold}\t{better}\t{worse}\t{gap:.6f}\n".encode())
    supported = {key for key, item in sibling.items() if item.count and strata.get(key, Bucket()).count >= MINIMUM}
    common_rows = sum(sibling[key].count for key in sorted(supported))
    by_task = collections.Counter()
    for key in sorted(supported):
        by_task[key[0]] += sibling[key].count
    support = {
        "original_sibling_rows": len(rows),
        "sibling_strata": len(sibling),
        "supported_strata": len(supported),
        "excluded_strata": len(sibling) - len(supported),
        "common_sibling_rows": common_rows,
        "common_sibling_share": common_rows / len(rows),
        "common_tasks": len(by_task),
        "dominant_task_share": max(by_task.values(), default=0) / common_rows if common_rows else 1.0,
        "crossrun_candidate_pairs": sum(item.count for item in cells.values()),
        "same_run_pairs_excluded": same_run,
        "equal_grade_pairs_excluded": equal_grade,
        "candidate_population_sha256": population_hash.hexdigest(),
        "min_candidates_per_stratum": MINIMUM,
    }
    return {"sibling": sibling, "cells": cells, "strata": strata, "supported": supported, "support": support}


def evaluate(pop: dict[str, Any], arm: str, graph: str) -> dict[str, Any]:
    numerators = collections.Counter()
    denominators = collections.Counter()
    total = gap_total = hard_total = weight_total = 0.0
    if graph == "sibling":
        for key in sorted(pop["supported"]):
            task = key[0]
            item = pop["sibling"][key]
            numerators[task] += item.hits[arm]
            denominators[task] += item.count
            total += item.hits[arm]
            weight_total += item.count
            gap_total += item.gap_sum
            hard_total += item.hard_count
    elif graph == "crossrun_uniform_transport":
        weights = collections.Counter()
        for task, fold, index in sorted(pop["supported"]):
            weights[(task, fold)] += pop["sibling"][(task, fold, index)].count
        for (task, fold), weight in weights.items():
            item = pop["cells"][(task, fold)]
            accuracy = item.hits[arm] / item.count
            numerators[task] += accuracy * weight
            denominators[task] += weight
            total += accuracy * weight
            weight_total += weight
            gap_total += item.gap_sum / item.count * weight
            hard_total += item.hard_count / item.count * weight
    elif graph == "crossrun_gap_transport":
        for key in sorted(pop["supported"]):
            task = key[0]
            weight = pop["sibling"][key].count
            item = pop["strata"][key]
            accuracy = item.hits[arm] / item.count
            numerators[task] += accuracy * weight
            denominators[task] += weight
            total += accuracy * weight
            weight_total += weight
            gap_total += item.gap_sum / item.count * weight
            hard_total += item.hard_count / item.count * weight
    else:
        raise VerificationError(f"bad graph: {graph}")
    per_task = {task: numerators[task] / denominators[task] for task in sorted(denominators)}
    return {
        "weighted_rows": weight_total,
        "micro_accuracy": total / weight_total,
        "task_macro_accuracy": sum(per_task.values()) / len(per_task),
        "mean_gap": gap_total / weight_total,
        "hard_share": hard_total / weight_total,
        "per_task": per_task,
    }


def contrast_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for arm in ARMS:
        result[arm] = {}
        for name, (left, right) in CONTRASTS.items():
            result[arm][name] = boot(metrics[arm][left]["per_task"], metrics[arm][right]["per_task"])
        total = result[arm]["total_pairing_inflation"]["estimate"]
        component = result[arm]["gap_composition_component"]["estimate"]
        result[arm]["gap_component_share_of_positive_total"] = component / total if total > 0 else None
    return result


def derive_gates(integrity: dict[str, bool], contrasts: dict[str, Any]) -> dict[str, Any]:
    focus = contrasts[HEADLINE]
    total = focus["total_pairing_inflation"]
    component = focus["gap_composition_component"]
    residual = focus["topology_residual"]
    positive = sum(contrasts[arm]["total_pairing_inflation"]["estimate"] > 0 for arm in ARMS)
    positive_ci = sum(contrasts[arm]["total_pairing_inflation"]["ci95"][0] > 0 for arm in ARMS)
    inflation = {
        "integrity_all": all(integrity.values()),
        "headline_delta_ge_005": total["estimate"] >= 0.05,
        "headline_ci_low_gt_0": total["ci95"][0] > 0,
        "positive_arms_ge_3": positive >= 3,
        "positive_ci_arms_ge_2": positive_ci >= 2,
        "positive_arms": positive,
        "positive_ci_arms": positive_ci,
    }
    inflation["all"] = all(value for key, value in inflation.items() if key not in {"positive_arms", "positive_ci_arms", "all"})
    gap_gate = {
        "inflation_supported": inflation["all"],
        "headline_gap_component_ge_003": component["estimate"] >= 0.03,
        "headline_gap_ci_low_gt_0": component["ci95"][0] > 0,
        "component_share_ge_050": focus["gap_component_share_of_positive_total"] is not None
        and focus["gap_component_share_of_positive_total"] >= 0.50,
    }
    gap_gate["all"] = all(gap_gate.values())
    topology = {
        "integrity_all": all(integrity.values()),
        "headline_residual_ge_003": residual["estimate"] >= 0.03,
        "headline_residual_ci_low_gt_0": residual["ci95"][0] > 0,
    }
    topology["all"] = all(topology.values())
    return {"inflation": inflation, "gap_composition": gap_gate, "topology_residual": topology}


def derive_status(gates: dict[str, Any]) -> str:
    if not gates["inflation"]["integrity_all"]:
        return "INVALID"
    if not gates["inflation"]["all"]:
        return "PAIRGRAPH_EFFECT_NOT_SUPPORTED"
    status = "PAIRGRAPH_INFLATION_SUPPORTED"
    if gates["gap_composition"]["all"]:
        status += "__GAP_COMPOSITION_SUPPORTED"
    if gates["topology_residual"]["all"]:
        status += "__TOPOLOGY_RESIDUAL_SUPPORTED"
    return status


def stratum_rows(pop: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key in sorted(pop["sibling"]):
        task, fold, index = key
        source = pop["sibling"][key]
        candidate = pop["strata"].get(key, Bucket())
        row: dict[str, Any] = {
            "task": task,
            "fold": fold,
            "gap_bin": index,
            "gap_interval": interval(index),
            "supported": int(key in pop["supported"]),
            "sibling_count": source.count,
            "candidate_count": candidate.count,
            "sibling_mean_gap": source.gap_sum / source.count,
            "candidate_mean_gap": candidate.gap_sum / candidate.count if candidate.count else "",
        }
        for arm in ARMS:
            row[f"{arm}_sibling_accuracy"] = source.hits[arm] / source.count
            row[f"{arm}_candidate_accuracy"] = candidate.hits[arm] / candidate.count if candidate.count else ""
        rows.append(row)
    return rows


def task_rows(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for arm in ARMS:
        for task in sorted(metrics[arm]["sibling"]["per_task"]):
            sibling = metrics[arm]["sibling"]["per_task"][task]
            uniform = metrics[arm]["crossrun_uniform_transport"]["per_task"][task]
            matched = metrics[arm]["crossrun_gap_transport"]["per_task"][task]
            rows.append({
                "arm": arm,
                "task": task,
                "sibling_accuracy": sibling,
                "uniform_accuracy": uniform,
                "gap_transport_accuracy": matched,
                "total_pairing_inflation": uniform - sibling,
                "gap_composition_component": uniform - matched,
                "topology_residual": matched - sibling,
            })
    return rows


def compare_value(actual: Any, expected: Any, path: str = "root") -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise VerificationError(f"dict mismatch at {path}")
        for key in expected:
            compare_value(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise VerificationError(f"list mismatch at {path}")
        for index, (left, right) in enumerate(zip(actual, expected)):
            compare_value(left, right, f"{path}[{index}]")
    elif isinstance(expected, float):
        if not isinstance(actual, (int, float)) or not math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=TOL):
            raise VerificationError(f"float mismatch at {path}: {actual} != {expected}")
    elif actual != expected:
        raise VerificationError(f"value mismatch at {path}: {actual!r} != {expected!r}")


def compare_csv(path: Path, expected: Sequence[dict[str, Any]]) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        actual = list(csv.DictReader(handle))
    if len(actual) != len(expected):
        raise VerificationError(f"CSV row count mismatch: {path}")
    for index, (left, right) in enumerate(zip(actual, expected)):
        if set(left) != set(right):
            raise VerificationError(f"CSV columns mismatch: {path}")
        for key, value in right.items():
            if left[key] != str(value):
                raise VerificationError(f"CSV mismatch {path}:{index}:{key}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oof", required=True)
    parser.add_argument("--pairs", required=True)
    parser.add_argument("--cards", required=True)
    parser.add_argument("--orientation", required=True)
    parser.add_argument("--result-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expect-oof-sha256", required=True)
    parser.add_argument("--expect-pairs-sha256", required=True)
    parser.add_argument("--expect-cards-sha256", required=True)
    parser.add_argument("--expect-orientation-sha256", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = {"oof": Path(args.oof), "pairs": Path(args.pairs), "cards": Path(args.cards), "orientation": Path(args.orientation)}
    hashes = {
        "oof": args.expect_oof_sha256.lower(),
        "pairs": args.expect_pairs_sha256.lower(),
        "cards": args.expect_cards_sha256.lower(),
        "orientation": args.expect_orientation_sha256.lower(),
    }
    result_dir = Path(args.result_dir)
    producer = json.loads((result_dir / "summary.json").read_text(encoding="utf-8"))
    if producer.get("protocol") != PROTOCOL or producer.get("frozen_read") is not False:
        raise VerificationError("producer protocol/frozen marker mismatch")
    rows, endpoints, grades, orientations, oof_audit, card_audit = read_inputs(
        paths["oof"], paths["pairs"], paths["cards"], paths["orientation"], hashes
    )
    pop = enumerate_populations(rows, endpoints, grades, orientations)
    support = pop["support"]
    support_integrity = {
        "common_share_ge_080": support["common_sibling_share"] >= 0.80,
        "common_tasks_ge_15": support["common_tasks"] >= 15,
        "dominant_task_le_030": support["dominant_task_share"] <= 0.30,
    }
    if not all(support_integrity.values()):
        if producer.get("status") != "INSUFFICIENT_COMMON_SUPPORT" or producer.get("metrics") != {}:
            raise VerificationError("insufficient-support producer mismatch")
        status = "VERIFIED_INSUFFICIENT_COMMON_SUPPORT"
        output = {"protocol": PROTOCOL, "status": status, "frozen_read": False, "support": support}
        atomic_json(Path(args.output), output)
        print(status)
        return

    metrics = {arm: {graph: evaluate(pop, arm, graph) for graph in GRAPHS} for arm in ARMS}
    contrasts = contrast_metrics(metrics)
    integrity = {
        **support_integrity,
        "oof_rows_exact": oof_audit["rows"] == EXPECTED["pairs"],
        "oof_runs_exact": oof_audit["runs"] == EXPECTED["runs"],
        "oof_tasks_exact": oof_audit["tasks"] == EXPECTED["tasks"],
        "oof_parents_exact": oof_audit["parents"] == EXPECTED["parents"],
        "oof_endpoints_exact": oof_audit["endpoints"] == EXPECTED["endpoints"],
        "selected_cards_exact": card_audit["selected_cards"] == EXPECTED["endpoints"],
        "endpoint_scores_consistent": True,
        "orientation_and_gap_exact": True,
        "crossrun_same_task_fold_only": True,
        "all_metrics_finite": all(
            math.isfinite(metrics[arm][graph][metric])
            for arm in ARMS for graph in GRAPHS
            for metric in ("micro_accuracy", "task_macro_accuracy", "mean_gap", "hard_share")
        ),
        "frozen_read_false": True,
        "runtime_le_cap": float(producer["runtime_s"]) <= float(producer["wall_cap_s"]),
    }
    gates = derive_gates(integrity, contrasts)
    status = derive_status(gates)
    expected_configuration = {
        "arms": list(ARMS),
        "headline_arm": HEADLINE,
        "graphs": list(GRAPHS),
        "gap_uppers": [*UPPERS[:-1], "inf"],
        "hard_threshold": HARD,
        "min_candidates_per_stratum": MINIMUM,
        "bootstrap_reps": REPS,
        "bootstrap_seed": SEED,
        "endpoint_score_tolerance": TOL,
    }
    for key, expected in (
        ("configuration", expected_configuration),
        ("oof_audit", oof_audit),
        ("card_audit", card_audit),
        ("support", support),
        ("metrics", metrics),
        ("contrasts", contrasts),
        ("integrity", integrity),
        ("gates", gates),
        ("status", status),
    ):
        compare_value(producer[key], expected, key)
    for label, path in paths.items():
        if producer["inputs"][label]["sha256"] != digest(path) or producer["expected_hashes"][label] != hashes[label]:
            raise VerificationError(f"producer input hash mismatch: {label}")
    stratum_expected = stratum_rows(pop)
    task_expected = task_rows(metrics)
    compare_csv(result_dir / "stratum_stats.csv", stratum_expected)
    compare_csv(result_dir / "per_task.csv", task_expected)
    if producer["outputs"]["stratum_stats_sha256"] != digest(result_dir / "stratum_stats.csv"):
        raise VerificationError("stratum output SHA mismatch")
    if producer["outputs"]["per_task_sha256"] != digest(result_dir / "per_task.csv"):
        raise VerificationError("per-task output SHA mismatch")
    verified_status = "VERIFIED_" + status
    output = {
        "protocol": PROTOCOL,
        "status": verified_status,
        "producer_status": status,
        "frozen_read": False,
        "producer_summary_sha256": digest(result_dir / "summary.json"),
        "stratum_stats_sha256": digest(result_dir / "stratum_stats.csv"),
        "per_task_sha256": digest(result_dir / "per_task.csv"),
        "oof_audit": oof_audit,
        "card_audit": card_audit,
        "support": support,
        "metrics": metrics,
        "contrasts": contrasts,
        "integrity": integrity,
        "gates": gates,
    }
    atomic_json(Path(args.output), output)
    print(verified_status)


if __name__ == "__main__":
    main()
