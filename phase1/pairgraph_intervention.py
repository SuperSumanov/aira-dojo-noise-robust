#!/usr/bin/env python3
"""Finite-population pair-graph intervention on locked train-only OOF scores.

The script never accepts a frozen/test/held pair input.  It keeps the endpoint
universe, task composition, and outer-fold models fixed, then transports the
same OOF endpoint scores over cross-run pair graphs with and without matching
the preregistered raw-gap bins.
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
import platform
import random
import subprocess
import time
from pathlib import Path
from typing import Any, Iterable, Sequence


PROTOCOL = "pairgraph_v11_train_oof_descriptive_v1"
ARMS = ("fixed_frozen_global", "op_only_lr", "static_lr", "char_tfidf_lr")
HEADLINE_ARM = "char_tfidf_lr"
GAP_UPPERS = (1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1, math.inf)
HARD_THRESHOLD = 1e-2
MIN_CANDIDATES_PER_STRATUM = 5
BOOTSTRAP_REPS = 10_000
BOOTSTRAP_SEED = 9_887
EPSILON = 1e-12
EXPECTED = {
    "pairs": 4_263,
    "runs": 333,
    "tasks": 23,
    "parents": 2_293,
    "endpoints": 5_499,
}
GRAPH_NAMES = ("sibling", "crossrun_uniform_transport", "crossrun_gap_transport")
CONTRASTS = {
    "total_pairing_inflation": ("crossrun_uniform_transport", "sibling"),
    "gap_composition_component": (
        "crossrun_uniform_transport",
        "crossrun_gap_transport",
    ),
    "topology_residual": ("crossrun_gap_transport", "sibling"),
}


class IntegrityError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def atomic_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        raise IntegrityError(f"refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def reject_forbidden_path(path: Path, label: str) -> None:
    tokens = [token for token in ("frozen", "test", "held") if token in path.name.lower()]
    if tokens:
        raise IntegrityError(f"{label} path contains forbidden token(s): {tokens}")


def git_commit(repo_root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()


def task_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("desc") or "")
    return str(value or "")


def finite_float(value: Any, label: str) -> float:
    try:
        converted = float(value)
    except (TypeError, ValueError) as exc:
        raise IntegrityError(f"non-numeric {label}: {value!r}") from exc
    if not math.isfinite(converted):
        raise IntegrityError(f"non-finite {label}: {value!r}")
    return converted


def gap_bin(gap: float) -> int:
    if not math.isfinite(gap) or gap < 0:
        raise IntegrityError(f"invalid gap: {gap}")
    return bisect.bisect_right(GAP_UPPERS, gap)


def gap_label(index: int) -> str:
    lower = 0.0 if index == 0 else GAP_UPPERS[index - 1]
    upper = GAP_UPPERS[index]
    upper_text = "inf" if math.isinf(upper) else f"{upper:.12g}"
    return f"[{lower:.12g},{upper_text})"


def score_hit(delta: float) -> float:
    if not math.isfinite(delta):
        raise IntegrityError("non-finite score delta")
    if delta > 0:
        return 1.0
    if delta < 0:
        return 0.0
    return 0.5


def quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise IntegrityError("quantile of empty values")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def bootstrap_delta(
    per_task_left: dict[str, float],
    per_task_right: dict[str, float],
    reps: int = BOOTSTRAP_REPS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    tasks = sorted(set(per_task_left) & set(per_task_right))
    if not tasks:
        raise IntegrityError("no tasks for paired bootstrap")
    deltas = [per_task_left[task] - per_task_right[task] for task in tasks]
    rng = random.Random(seed)
    draws = []
    for _ in range(reps):
        draws.append(sum(deltas[rng.randrange(len(deltas))] for _ in tasks) / len(tasks))
    return {
        "tasks": len(tasks),
        "estimate": sum(deltas) / len(deltas),
        "ci95": [quantile(draws, 0.025), quantile(draws, 0.975)],
        "reps": reps,
        "seed": seed,
        "per_task": dict(zip(tasks, deltas)),
    }


def register_endpoint(
    endpoints: dict[str, dict[str, Any]],
    card_id: str,
    metadata: dict[str, Any],
    scores: dict[str, float],
) -> None:
    previous = endpoints.get(card_id)
    candidate = {**metadata, "scores": dict(scores)}
    if previous is None:
        endpoints[card_id] = candidate
        return
    for key in ("task", "fold", "run", "parent"):
        if previous[key] != candidate[key]:
            raise IntegrityError(f"endpoint metadata inconsistency for {card_id}: {key}")
    for arm in ARMS:
        if not math.isclose(
            previous["scores"][arm], candidate["scores"][arm], rel_tol=0.0, abs_tol=EPSILON
        ):
            raise IntegrityError(f"endpoint score inconsistency for {card_id}: {arm}")


def load_oof_and_pairs(
    oof_path: Path,
    pairs_path: Path,
    expected_oof_sha: str,
    expected_pairs_sha: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    reject_forbidden_path(oof_path, "OOF predictions")
    reject_forbidden_path(pairs_path, "training pairs")
    if sha256(oof_path) != expected_oof_sha.lower():
        raise IntegrityError("OOF predictions SHA mismatch")
    if sha256(pairs_path) != expected_pairs_sha.lower():
        raise IntegrityError("training pairs SHA mismatch")

    with oof_path.open(encoding="utf-8", newline="") as handle:
        raw_oof = list(csv.DictReader(handle))
    raw_pairs = [
        json.loads(line)
        for line in pairs_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    if len(raw_oof) != len(raw_pairs):
        raise IntegrityError("OOF/pair row count mismatch")

    required = {
        "row_index",
        "task",
        "run",
        "parent",
        "better",
        "worse",
        "gap_raw",
        "fold",
    }
    for arm in ARMS:
        required.update(
            {f"{arm}_better_score", f"{arm}_worse_score", f"{arm}_hit"}
        )
    if not raw_oof or not required <= set(raw_oof[0]):
        raise IntegrityError(f"OOF columns missing: {sorted(required - set(raw_oof[0] if raw_oof else {}))}")

    rows: list[dict[str, Any]] = []
    endpoints: dict[str, dict[str, Any]] = {}
    seen_pairs: set[tuple[str, str]] = set()
    for index, (source, pair) in enumerate(zip(raw_oof, raw_pairs)):
        if int(source["row_index"]) != index:
            raise IntegrityError(f"non-contiguous row_index at {index}")
        if pair.get("intask_split") != "train" or int(pair.get("budget", -1)) != 0:
            raise IntegrityError(f"non-train b0 row at {index}")
        expected_values = {
            "task": str(pair["task"]),
            "run": str(pair["run_id"]),
            "parent": str(pair["parent"]),
            "better": str(pair["better"]),
            "worse": str(pair["worse"]),
        }
        for key, expected in expected_values.items():
            if source[key] != expected:
                raise IntegrityError(f"OOF/pair mismatch at {index}: {key}")
        gap = finite_float(source["gap_raw"], f"gap row {index}")
        if not math.isclose(gap, finite_float(pair["gap_raw"], "pair gap"), rel_tol=0.0, abs_tol=EPSILON):
            raise IntegrityError(f"OOF/pair gap mismatch at {index}")
        better, worse = expected_values["better"], expected_values["worse"]
        canonical = tuple(sorted((better, worse)))
        if better == worse or canonical in seen_pairs:
            raise IntegrityError(f"duplicate/degenerate sibling pair at {index}")
        seen_pairs.add(canonical)
        scores: dict[str, dict[str, float]] = {}
        for arm in ARMS:
            left = finite_float(source[f"{arm}_better_score"], f"{arm} better score")
            right = finite_float(source[f"{arm}_worse_score"], f"{arm} worse score")
            recorded_hit = finite_float(source[f"{arm}_hit"], f"{arm} hit")
            computed_hit = score_hit(left - right)
            if not math.isclose(recorded_hit, computed_hit, rel_tol=0.0, abs_tol=EPSILON):
                raise IntegrityError(f"saved hit mismatch at row {index}: {arm}")
            scores[arm] = {"better": left, "worse": right}
        row = {
            "row_index": index,
            **expected_values,
            "gap": gap,
            "fold": int(source["fold"]),
            "scores": scores,
        }
        rows.append(row)
        metadata = {
            "task": row["task"],
            "fold": row["fold"],
            "run": row["run"],
            "parent": row["parent"],
        }
        register_endpoint(
            endpoints,
            better,
            metadata,
            {arm: scores[arm]["better"] for arm in ARMS},
        )
        register_endpoint(
            endpoints,
            worse,
            metadata,
            {arm: scores[arm]["worse"] for arm in ARMS},
        )

    audit = {
        "rows": len(rows),
        "pairs": len(rows),
        "runs": len({row["run"] for row in rows}),
        "tasks": len({row["task"] for row in rows}),
        "parents": len({row["parent"] for row in rows}),
        "endpoints": len(endpoints),
        "endpoint_score_tolerance": EPSILON,
        "separable_arms": list(ARMS),
    }
    if any(audit[key] != value for key, value in EXPECTED.items()):
        raise IntegrityError(f"unexpected OOF support: {audit}")
    return rows, endpoints, audit


def load_selected_grades(
    cards_path: Path,
    endpoints: dict[str, dict[str, Any]],
    expected_cards_sha: str,
) -> tuple[dict[str, float], dict[str, Any]]:
    reject_forbidden_path(cards_path, "cards")
    expected = set(endpoints)
    found: dict[str, float] = {}
    digest = hashlib.sha256()
    corpus_rows = 0
    with cards_path.open("rb") as handle:
        for raw_line in handle:
            digest.update(raw_line)
            corpus_rows += 1
            card = json.loads(raw_line)
            card_id = str(card["id"])
            if card_id not in expected:
                continue
            if card_id in found:
                raise IntegrityError(f"duplicate selected card: {card_id}")
            endpoint = endpoints[card_id]
            if task_name(card.get("task")) != endpoint["task"]:
                raise IntegrityError(f"selected card task mismatch: {card_id}")
            if str(card.get("run_id")) != endpoint["run"]:
                raise IntegrityError(f"selected card run mismatch: {card_id}")
            if str((card.get("lineage") or {}).get("parent_id")) != endpoint["parent"]:
                raise IntegrityError(f"selected card parent mismatch: {card_id}")
            found[card_id] = finite_float(
                (card.get("label") or {}).get("graded"), f"grade for {card_id}"
            )
    if digest.hexdigest() != expected_cards_sha.lower():
        raise IntegrityError("cards SHA mismatch")
    if set(found) != expected:
        raise IntegrityError(f"selected card coverage mismatch: {len(found)} != {len(expected)}")
    return found, {
        "corpus_rows": corpus_rows,
        "selected_cards": len(found),
        "retained_fields": ["id", "task", "graded"],
        "code_fields_retained": 0,
        "observation_fields_retained": 0,
        "non_allowlisted_cards_retained": 0,
    }


def load_orientation(path: Path, expected_sha: str, tasks: set[str]) -> dict[str, bool]:
    reject_forbidden_path(path, "task orientation")
    if sha256(path) != expected_sha.lower():
        raise IntegrityError("task orientation SHA mismatch")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not tasks <= set(raw):
        raise IntegrityError(f"missing task orientations: {sorted(tasks - set(raw))}")
    if any(not isinstance(raw[task], bool) for task in tasks):
        raise IntegrityError("task orientation values must be booleans")
    return {task: bool(raw[task]) for task in tasks}


def orient_pair(
    first: str,
    second: str,
    grades: dict[str, float],
    lower_is_better: bool,
) -> tuple[str, str, float] | None:
    first_grade, second_grade = grades[first], grades[second]
    if first_grade == second_grade:
        return None
    first_wins = first_grade < second_grade if lower_is_better else first_grade > second_grade
    better, worse = (first, second) if first_wins else (second, first)
    return better, worse, round(abs(first_grade - second_grade), 6)


def new_accumulator() -> dict[str, Any]:
    return {
        "count": 0,
        "gap_sum": 0.0,
        "hard_count": 0,
        "hit_sum": {arm: 0.0 for arm in ARMS},
    }


def add_pair(
    accumulator: dict[str, Any],
    gap: float,
    endpoint_scores: dict[str, dict[str, float]],
    better: str,
    worse: str,
) -> None:
    accumulator["count"] += 1
    accumulator["gap_sum"] += gap
    accumulator["hard_count"] += int(gap < HARD_THRESHOLD)
    for arm in ARMS:
        accumulator["hit_sum"][arm] += score_hit(
            endpoint_scores[better][arm] - endpoint_scores[worse][arm]
        )


def build_finite_populations(
    rows: Sequence[dict[str, Any]],
    endpoints: dict[str, dict[str, Any]],
    grades: dict[str, float],
    orientation: dict[str, bool],
) -> dict[str, Any]:
    endpoint_scores = {card_id: row["scores"] for card_id, row in endpoints.items()}
    sibling_strata: dict[tuple[str, int, int], dict[str, Any]] = collections.defaultdict(new_accumulator)
    for row in rows:
        oriented = orient_pair(
            row["better"], row["worse"], grades, orientation[row["task"]]
        )
        if oriented is None or oriented[:2] != (row["better"], row["worse"]):
            raise IntegrityError(f"sibling grade orientation mismatch at {row['row_index']}")
        if not math.isclose(oriented[2], row["gap"], rel_tol=0.0, abs_tol=EPSILON):
            raise IntegrityError(f"sibling grade gap mismatch at {row['row_index']}")
        key = (row["task"], row["fold"], gap_bin(row["gap"]))
        add_pair(sibling_strata[key], row["gap"], endpoint_scores, row["better"], row["worse"])

    grouped: dict[tuple[str, int], list[str]] = collections.defaultdict(list)
    for card_id, endpoint in endpoints.items():
        grouped[(endpoint["task"], endpoint["fold"])].append(card_id)

    candidate_cells: dict[tuple[str, int], dict[str, Any]] = collections.defaultdict(new_accumulator)
    candidate_strata: dict[tuple[str, int, int], dict[str, Any]] = collections.defaultdict(new_accumulator)
    candidate_digest = hashlib.sha256()
    equal_grade_pairs = 0
    same_run_pairs = 0
    for (task, fold), card_ids in sorted(grouped.items()):
        for first, second in itertools.combinations(sorted(card_ids), 2):
            if endpoints[first]["run"] == endpoints[second]["run"]:
                same_run_pairs += 1
                continue
            oriented = orient_pair(first, second, grades, orientation[task])
            if oriented is None:
                equal_grade_pairs += 1
                continue
            better, worse, gap = oriented
            key = (task, fold, gap_bin(gap))
            add_pair(candidate_cells[(task, fold)], gap, endpoint_scores, better, worse)
            add_pair(candidate_strata[key], gap, endpoint_scores, better, worse)
            candidate_digest.update(
                f"{task}\t{fold}\t{better}\t{worse}\t{gap:.6f}\n".encode("utf-8")
            )

    supported = {
        key
        for key, sibling in sibling_strata.items()
        if sibling["count"] > 0
        and candidate_strata.get(key, {}).get("count", 0) >= MIN_CANDIDATES_PER_STRATUM
    }
    common_rows = sum(sibling_strata[key]["count"] for key in sorted(supported))
    common_by_task = collections.Counter()
    for key in sorted(supported):
        common_by_task[key[0]] += sibling_strata[key]["count"]
    common_tasks = len(common_by_task)
    dominant_share = max(common_by_task.values(), default=0) / common_rows if common_rows else 1.0
    support = {
        "original_sibling_rows": len(rows),
        "sibling_strata": len(sibling_strata),
        "supported_strata": len(supported),
        "excluded_strata": len(sibling_strata) - len(supported),
        "common_sibling_rows": common_rows,
        "common_sibling_share": common_rows / len(rows),
        "common_tasks": common_tasks,
        "dominant_task_share": dominant_share,
        "crossrun_candidate_pairs": sum(item["count"] for item in candidate_cells.values()),
        "same_run_pairs_excluded": same_run_pairs,
        "equal_grade_pairs_excluded": equal_grade_pairs,
        "candidate_population_sha256": candidate_digest.hexdigest(),
        "min_candidates_per_stratum": MIN_CANDIDATES_PER_STRATUM,
    }
    return {
        "sibling_strata": dict(sibling_strata),
        "candidate_cells": dict(candidate_cells),
        "candidate_strata": dict(candidate_strata),
        "supported": supported,
        "support": support,
    }


def graph_metrics(populations: dict[str, Any], arm: str, graph: str) -> dict[str, Any]:
    sibling_strata = populations["sibling_strata"]
    candidate_cells = populations["candidate_cells"]
    candidate_strata = populations["candidate_strata"]
    supported = populations["supported"]
    task_numerator = collections.Counter()
    task_denominator = collections.Counter()
    total_numerator = 0.0
    total_denominator = 0.0
    gap_numerator = 0.0
    hard_numerator = 0.0

    if graph == "sibling":
        for key in sorted(supported):
            task = key[0]
            item = sibling_strata[key]
            weight = item["count"]
            numerator = item["hit_sum"][arm]
            total_numerator += numerator
            total_denominator += weight
            task_numerator[task] += numerator
            task_denominator[task] += weight
            gap_numerator += item["gap_sum"]
            hard_numerator += item["hard_count"]
    elif graph == "crossrun_uniform_transport":
        sibling_cell_weights = collections.Counter()
        for task, fold, bin_index in sorted(supported):
            sibling_cell_weights[(task, fold)] += sibling_strata[
                (task, fold, bin_index)
            ]["count"]
        for (task, fold), weight in sibling_cell_weights.items():
            population = candidate_cells[(task, fold)]
            mean_hit = population["hit_sum"][arm] / population["count"]
            mean_gap = population["gap_sum"] / population["count"]
            hard_share = population["hard_count"] / population["count"]
            total_numerator += mean_hit * weight
            total_denominator += weight
            task_numerator[task] += mean_hit * weight
            task_denominator[task] += weight
            gap_numerator += mean_gap * weight
            hard_numerator += hard_share * weight
    elif graph == "crossrun_gap_transport":
        for key in sorted(supported):
            task = key[0]
            weight = sibling_strata[key]["count"]
            population = candidate_strata[key]
            mean_hit = population["hit_sum"][arm] / population["count"]
            mean_gap = population["gap_sum"] / population["count"]
            hard_share = population["hard_count"] / population["count"]
            total_numerator += mean_hit * weight
            total_denominator += weight
            task_numerator[task] += mean_hit * weight
            task_denominator[task] += weight
            gap_numerator += mean_gap * weight
            hard_numerator += hard_share * weight
    else:
        raise IntegrityError(f"unknown graph: {graph}")

    per_task = {
        task: task_numerator[task] / task_denominator[task]
        for task in sorted(task_denominator)
    }
    return {
        "weighted_rows": total_denominator,
        "micro_accuracy": total_numerator / total_denominator,
        "task_macro_accuracy": sum(per_task.values()) / len(per_task),
        "mean_gap": gap_numerator / total_denominator,
        "hard_share": hard_numerator / total_denominator,
        "per_task": per_task,
    }


def make_stratum_rows(populations: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for key in sorted(populations["sibling_strata"]):
        task, fold, bin_index = key
        sibling = populations["sibling_strata"][key]
        candidate = populations["candidate_strata"].get(key, new_accumulator())
        row: dict[str, Any] = {
            "task": task,
            "fold": fold,
            "gap_bin": bin_index,
            "gap_interval": gap_label(bin_index),
            "supported": int(key in populations["supported"]),
            "sibling_count": sibling["count"],
            "candidate_count": candidate["count"],
            "sibling_mean_gap": sibling["gap_sum"] / sibling["count"],
            "candidate_mean_gap": (
                candidate["gap_sum"] / candidate["count"] if candidate["count"] else ""
            ),
        }
        for arm in ARMS:
            row[f"{arm}_sibling_accuracy"] = sibling["hit_sum"][arm] / sibling["count"]
            row[f"{arm}_candidate_accuracy"] = (
                candidate["hit_sum"][arm] / candidate["count"]
                if candidate["count"]
                else ""
            )
        output.append(row)
    return output


def make_per_task_rows(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for arm in ARMS:
        graphs = metrics[arm]
        tasks = sorted(graphs["sibling"]["per_task"])
        for task in tasks:
            sibling = graphs["sibling"]["per_task"][task]
            uniform = graphs["crossrun_uniform_transport"]["per_task"][task]
            matched = graphs["crossrun_gap_transport"]["per_task"][task]
            output.append(
                {
                    "arm": arm,
                    "task": task,
                    "sibling_accuracy": sibling,
                    "uniform_accuracy": uniform,
                    "gap_transport_accuracy": matched,
                    "total_pairing_inflation": uniform - sibling,
                    "gap_composition_component": uniform - matched,
                    "topology_residual": matched - sibling,
                }
            )
    return output


def compute_contrasts(metrics: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for arm in ARMS:
        output[arm] = {}
        for name, (left, right) in CONTRASTS.items():
            output[arm][name] = bootstrap_delta(
                metrics[arm][left]["per_task"], metrics[arm][right]["per_task"]
            )
        total = output[arm]["total_pairing_inflation"]["estimate"]
        component = output[arm]["gap_composition_component"]["estimate"]
        output[arm]["gap_component_share_of_positive_total"] = (
            component / total if total > 0 else None
        )
    return output


def make_gates(
    integrity: dict[str, bool],
    contrasts: dict[str, Any],
) -> dict[str, Any]:
    headline = contrasts[HEADLINE_ARM]
    total = headline["total_pairing_inflation"]
    gap = headline["gap_composition_component"]
    residual = headline["topology_residual"]
    positive_arms = sum(
        contrasts[arm]["total_pairing_inflation"]["estimate"] > 0 for arm in ARMS
    )
    positive_ci_arms = sum(
        contrasts[arm]["total_pairing_inflation"]["ci95"][0] > 0 for arm in ARMS
    )
    inflation = {
        "integrity_all": all(integrity.values()),
        "headline_delta_ge_005": total["estimate"] >= 0.05,
        "headline_ci_low_gt_0": total["ci95"][0] > 0,
        "positive_arms_ge_3": positive_arms >= 3,
        "positive_ci_arms_ge_2": positive_ci_arms >= 2,
        "positive_arms": positive_arms,
        "positive_ci_arms": positive_ci_arms,
    }
    inflation["all"] = all(value for key, value in inflation.items() if key not in {"positive_arms", "positive_ci_arms", "all"})
    gap_gate = {
        "inflation_supported": inflation["all"],
        "headline_gap_component_ge_003": gap["estimate"] >= 0.03,
        "headline_gap_ci_low_gt_0": gap["ci95"][0] > 0,
        "component_share_ge_050": (
            headline["gap_component_share_of_positive_total"] is not None
            and headline["gap_component_share_of_positive_total"] >= 0.50
        ),
    }
    gap_gate["all"] = all(gap_gate.values())
    topology_gate = {
        "integrity_all": all(integrity.values()),
        "headline_residual_ge_003": residual["estimate"] >= 0.03,
        "headline_residual_ci_low_gt_0": residual["ci95"][0] > 0,
    }
    topology_gate["all"] = all(topology_gate.values())
    return {"inflation": inflation, "gap_composition": gap_gate, "topology_residual": topology_gate}


def status_from_gates(gates: dict[str, Any]) -> str:
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--oof", required=True)
    parser.add_argument("--pairs", required=True)
    parser.add_argument("--cards", required=True)
    parser.add_argument("--orientation", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--expect-oof-sha256", required=True)
    parser.add_argument("--expect-pairs-sha256", required=True)
    parser.add_argument("--expect-cards-sha256", required=True)
    parser.add_argument("--expect-orientation-sha256", required=True)
    parser.add_argument("--wall-cap-s", type=float, default=600.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    repo_root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir)
    if (output_dir / "summary.json").exists():
        raise IntegrityError(f"append-only output already exists: {output_dir}")

    paths = {
        "oof": Path(args.oof),
        "pairs": Path(args.pairs),
        "cards": Path(args.cards),
        "orientation": Path(args.orientation),
    }
    expected_hashes = {
        "oof": args.expect_oof_sha256.lower(),
        "pairs": args.expect_pairs_sha256.lower(),
        "cards": args.expect_cards_sha256.lower(),
        "orientation": args.expect_orientation_sha256.lower(),
    }
    rows, endpoints, oof_audit = load_oof_and_pairs(
        paths["oof"], paths["pairs"], expected_hashes["oof"], expected_hashes["pairs"]
    )
    grades, card_audit = load_selected_grades(
        paths["cards"], endpoints, expected_hashes["cards"]
    )
    orientation = load_orientation(
        paths["orientation"], expected_hashes["orientation"], {row["task"] for row in rows}
    )
    populations = build_finite_populations(rows, endpoints, grades, orientation)
    support = populations["support"]
    support_integrity = {
        "common_share_ge_080": support["common_sibling_share"] >= 0.80,
        "common_tasks_ge_15": support["common_tasks"] >= 15,
        "dominant_task_le_030": support["dominant_task_share"] <= 0.30,
    }
    if not all(support_integrity.values()):
        summary = {
            "protocol": PROTOCOL,
            "status": "INSUFFICIENT_COMMON_SUPPORT",
            "frozen_read": False,
            "git_commit": git_commit(repo_root),
            "inputs": {key: {"path": str(path), "sha256": sha256(path)} for key, path in paths.items()},
            "oof_audit": oof_audit,
            "card_audit": card_audit,
            "support": support,
            "support_integrity": support_integrity,
            "metrics": {},
        }
        atomic_json(output_dir / "summary.json", summary)
        print("INSUFFICIENT_COMMON_SUPPORT", json.dumps(support, sort_keys=True))
        return

    metrics = {
        arm: {graph: graph_metrics(populations, arm, graph) for graph in GRAPH_NAMES}
        for arm in ARMS
    }
    contrasts = compute_contrasts(metrics)
    runtime_s = time.perf_counter() - started
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
            for arm in ARMS
            for graph in GRAPH_NAMES
            for metric in ("micro_accuracy", "task_macro_accuracy", "mean_gap", "hard_share")
        ),
        "frozen_read_false": True,
        "runtime_le_cap": runtime_s <= args.wall_cap_s,
    }
    gates = make_gates(integrity, contrasts)
    status = status_from_gates(gates)
    stratum_rows = make_stratum_rows(populations)
    per_task_rows = make_per_task_rows(metrics)
    atomic_csv(output_dir / "stratum_stats.csv", stratum_rows)
    atomic_csv(output_dir / "per_task.csv", per_task_rows)
    summary = {
        "protocol": PROTOCOL,
        "status": status,
        "frozen_read": False,
        "git_commit": git_commit(repo_root),
        "configuration": {
            "arms": list(ARMS),
            "headline_arm": HEADLINE_ARM,
            "graphs": list(GRAPH_NAMES),
            "gap_uppers": [*GAP_UPPERS[:-1], "inf"],
            "hard_threshold": HARD_THRESHOLD,
            "min_candidates_per_stratum": MIN_CANDIDATES_PER_STRATUM,
            "bootstrap_reps": BOOTSTRAP_REPS,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "endpoint_score_tolerance": EPSILON,
        },
        "inputs": {key: {"path": str(path), "sha256": sha256(path)} for key, path in paths.items()},
        "expected_hashes": expected_hashes,
        "oof_audit": oof_audit,
        "card_audit": card_audit,
        "support": support,
        "metrics": metrics,
        "contrasts": contrasts,
        "integrity": integrity,
        "gates": gates,
        "runtime_s": runtime_s,
        "wall_cap_s": args.wall_cap_s,
        "software": {"python": platform.python_version(), "platform": platform.platform()},
        "source_sha256": sha256(Path(__file__)),
    }
    atomic_json(output_dir / "summary.json", summary)
    summary["outputs"] = {
        "stratum_stats_sha256": sha256(output_dir / "stratum_stats.csv"),
        "per_task_sha256": sha256(output_dir / "per_task.csv"),
    }
    atomic_json(output_dir / "summary.json", summary)
    headline = contrasts[HEADLINE_ARM]
    print(
        status,
        f"common={support['common_sibling_rows']}",
        f"uniform_minus_sibling={headline['total_pairing_inflation']['estimate']:.6f}",
        f"uniform_minus_gap={headline['gap_composition_component']['estimate']:.6f}",
        f"gap_minus_sibling={headline['topology_residual']['estimate']:.6f}",
    )


if __name__ == "__main__":
    main()
