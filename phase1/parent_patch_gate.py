#!/usr/bin/env python3
"""Pre-registered sparse parent-to-child patch critic discovery gate.

The frozen pair file is opened only when every discovery gate passes.  Card labels,
execution logs, runtime, and self-reported scores are deliberately not loaded.
"""

from __future__ import annotations

import argparse
import collections
import csv
import dataclasses
import difflib
import hashlib
import json
import math
import os
import platform
import random
import subprocess
import sys
import time
import zlib
from pathlib import Path
from typing import Any, Iterable, Sequence


SEED = 887
N_FEATURES = 2**18
TEXT_LIMIT = 20_000
BOOTSTRAP_REPS = 4_000
EPSILON = 1e-12


class IntegrityError(RuntimeError):
    """Raised when a fail-closed data-integrity check fails."""


class TimeCapExceeded(RuntimeError):
    """Raised when the engineering wall-clock cap is exceeded."""


@dataclasses.dataclass(frozen=True)
class Card:
    card_id: str
    code: str
    parent_id: str | None
    operator: str
    run_id: str
    task: str


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
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def line_delta(parent: str, child: str, operator: str) -> str:
    """Return deterministic ADD/DEL lines with no unchanged context or hunk positions."""
    before = parent.splitlines()
    after = child.splitlines()
    output = ["OP " + (operator or "MISSING")]
    matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in {"delete", "replace"}:
            output.extend("DEL " + line for line in before[i1:i2])
        if tag in {"insert", "replace"}:
            output.extend("ADD " + line for line in after[j1:j2])
    return "\n".join(output)


def tie_hit(margin: float) -> float:
    if margin > EPSILON:
        return 1.0
    if margin < -EPSILON:
        return 0.0
    return 0.5


def task_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("desc") or "")
    return str(value or "")


def load_pairs(path: Path, expected_split: str) -> tuple[list[dict[str, Any]], str]:
    rows: list[dict[str, Any]] = []
    required = {"better", "worse", "parent", "task", "budget", "intask_split"}
    with path.open("rb") as handle:
        raw = handle.read()
    digest = hashlib.sha256(raw).hexdigest()
    for line_number, raw_line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        row = json.loads(raw_line)
        missing = required - set(row)
        if missing:
            raise IntegrityError(f"{path}:{line_number} missing keys {sorted(missing)}")
        if int(row["budget"]) != 0:
            raise IntegrityError(f"{path}:{line_number} is not budget 0")
        if row["intask_split"] != expected_split:
            raise IntegrityError(
                f"{path}:{line_number} split={row['intask_split']!r}, expected {expected_split!r}"
            )
        if row["better"] == row["worse"]:
            raise IntegrityError(f"{path}:{line_number} has identical endpoints")
        rows.append(row)
    if not rows:
        raise IntegrityError(f"{path} is empty")
    return rows, digest


def needed_card_ids(rows: Sequence[dict[str, Any]]) -> set[str]:
    return {
        str(row[key])
        for row in rows
        for key in ("better", "worse", "parent")
        if row.get(key)
    }


def load_card_subset(path: Path, needed: set[str]) -> tuple[dict[str, Card], str, int]:
    cards: dict[str, Card] = {}
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as handle:
        for raw_line in handle:
            digest.update(raw_line)
            total += 1
            row = json.loads(raw_line)
            card_id = str(row["id"])
            if card_id not in needed:
                continue
            lineage = row.get("lineage") or {}
            cards[card_id] = Card(
                card_id=card_id,
                code=str(row.get("code") or ""),
                parent_id=(str(lineage["parent_id"]) if lineage.get("parent_id") else None),
                operator=str(lineage.get("op") or "MISSING"),
                run_id=str(row.get("run_id") or ""),
                task=task_name(row.get("task")),
            )
    return cards, digest.hexdigest(), total


def audit_pair_rows(
    rows: Sequence[dict[str, Any]],
    cards: dict[str, Card],
    run_map: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    oriented = collections.Counter((str(row["better"]), str(row["worse"])) for row in rows)
    duplicate_rows = sum(count - 1 for count in oriented.values())
    directions: dict[tuple[str, str], set[tuple[str, str]]] = collections.defaultdict(set)
    for better, worse in oriented:
        directions[tuple(sorted((better, worse)))].add((better, worse))
    reversed_conflicts = sum(len(values) > 1 for values in directions.values())
    if duplicate_rows or reversed_conflicts:
        raise IntegrityError(
            f"duplicate_rows={duplicate_rows}, reversed_conflicts={reversed_conflicts}"
        )

    eligible: list[dict[str, Any]] = []
    endpoint_missing = 0
    parent_missing = 0
    malformed = 0
    for source in rows:
        better_id = str(source["better"])
        worse_id = str(source["worse"])
        parent_id = str(source["parent"])
        if better_id not in cards or worse_id not in cards:
            endpoint_missing += 1
            continue
        better = cards[better_id]
        worse = cards[worse_id]
        if better.parent_id != parent_id or worse.parent_id != parent_id:
            malformed += 1
            continue
        if better.run_id != worse.run_id or better.task != worse.task:
            malformed += 1
            continue
        if better.task != str(source["task"]):
            malformed += 1
            continue
        if run_map.get(better_id) != better.run_id or run_map.get(worse_id) != worse.run_id:
            malformed += 1
            continue
        if source.get("run_id") and str(source["run_id"]) != better.run_id:
            malformed += 1
            continue
        if parent_id not in cards:
            parent_missing += 1
            continue
        parent = cards[parent_id]
        if parent.run_id != better.run_id or parent.task != better.task:
            malformed += 1
            continue
        if run_map.get(parent_id) != parent.run_id:
            malformed += 1
            continue
        row = dict(source)
        row["run"] = better.run_id
        row["parent"] = parent_id
        eligible.append(row)

    if endpoint_missing or malformed:
        raise IntegrityError(
            f"endpoint_missing={endpoint_missing}, malformed={malformed}, parent_missing={parent_missing}"
        )
    tasks = collections.Counter(str(row["task"]) for row in eligible)
    runs = {str(row["run"]) for row in eligible}
    parents = {str(row["parent"]) for row in eligible}
    parent_rows: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in eligible:
        parent_rows[str(row["parent"])].append(row)
    incomplete_parent_sets = 0
    for grouped_rows in parent_rows.values():
        candidates = {
            str(row[key]) for row in grouped_rows for key in ("better", "worse")
        }
        expected_pairs = len(candidates) * (len(candidates) - 1) // 2
        incomplete_parent_sets += len(grouped_rows) != expected_pairs
    audit = {
        "raw_rows": len(rows),
        "eligible_rows": len(eligible),
        "parent_missing_rows": parent_missing,
        "parent_coverage": len(eligible) / len(rows),
        "duplicate_rows": duplicate_rows,
        "reversed_conflicts": reversed_conflicts,
        "runs": len(runs),
        "tasks": len(tasks),
        "parents": len(parents),
        "incomplete_parent_sets": incomplete_parent_sets,
        "complete_parent_share": 1.0 - incomplete_parent_sets / len(parents),
        "dominant_task": tasks.most_common(1)[0][0],
        "dominant_task_share": tasks.most_common(1)[0][1] / len(eligible),
        "per_task_rows": dict(sorted(tasks.items())),
    }
    return eligible, audit


def deterministic_random_score(card_id: str) -> float:
    return (zlib.crc32(f"{SEED}:{card_id}".encode("utf-8")) & 0xFFFFFFFF) / 2**32


def parent_top1_records(
    rows: Sequence[dict[str, Any]], scores: dict[str, float]
) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        groups[str(row["parent"])].append(row)
    output: dict[str, dict[str, Any]] = {}
    for parent, parent_rows in groups.items():
        candidates = {
            str(row[key]) for row in parent_rows for key in ("better", "worse")
        }
        expected_pairs = len(candidates) * (len(candidates) - 1) // 2
        if len(parent_rows) != expected_pairs:
            continue
        losses = collections.Counter({candidate: 0 for candidate in candidates})
        for row in parent_rows:
            losses[str(row["worse"])] += 1
        minimum_losses = min(losses.values())
        true_top = {candidate for candidate, value in losses.items() if value == minimum_losses}
        maximum_score = max(scores[candidate] for candidate in candidates)
        predicted_top = {
            candidate
            for candidate in candidates
            if abs(scores[candidate] - maximum_score) <= EPSILON
        }
        output[parent] = {
            "value": len(predicted_top & true_top) / len(predicted_top),
            "run": str(parent_rows[0]["run"]),
            "task": str(parent_rows[0]["task"]),
            "n_candidates": len(candidates),
            "true_ties": len(true_top),
            "predicted_ties": len(predicted_top),
        }
    return output


def macro_by_cluster(
    rows: Sequence[dict[str, Any]], values: Sequence[float], key: str
) -> tuple[float, dict[str, float]]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row, value in zip(rows, values):
        grouped[str(row[key])].append(float(value))
    means = {cluster: sum(items) / len(items) for cluster, items in grouped.items()}
    return sum(means.values()) / len(means), means


def bootstrap_cluster_means(
    cluster_means: dict[str, float], seed: int, reps: int = BOOTSTRAP_REPS
) -> list[float]:
    values = [cluster_means[key] for key in sorted(cluster_means)]
    rng = random.Random(seed)
    draws = [sum(rng.choice(values) for _ in values) / len(values) for _ in range(reps)]
    draws.sort()
    return [draws[int(0.025 * reps)], draws[int(0.975 * reps)]]


def summarize_pair_values(
    rows: Sequence[dict[str, Any]], values: Sequence[float], seed_offset: int
) -> dict[str, Any]:
    overall = sum(values) / len(values)
    run_macro, per_run = macro_by_cluster(rows, values, "run")
    task_macro, per_task = macro_by_cluster(rows, values, "task")
    return {
        "overall": overall,
        "run_macro": run_macro,
        "task_macro": task_macro,
        "run_macro_ci95": bootstrap_cluster_means(per_run, SEED + seed_offset),
        "task_macro_ci95": bootstrap_cluster_means(per_task, SEED + seed_offset + 1),
        "per_task": dict(sorted(per_task.items())),
    }


def summarize_parent_values(
    records: dict[str, dict[str, Any]], seed_offset: int
) -> dict[str, Any]:
    values = [float(record["value"]) for record in records.values()]
    proxy_rows = [
        {"run": record["run"], "task": record["task"]} for record in records.values()
    ]
    return {
        "overall": sum(values) / len(values),
        **{
            key: value
            for key, value in summarize_pair_values(proxy_rows, values, seed_offset).items()
            if key != "overall"
        },
        "parents": len(values),
    }


def supported_task_consistency(
    rows: Sequence[dict[str, Any]], differences: Sequence[float], minimum_rows: int
) -> dict[str, Any]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row, value in zip(rows, differences):
        grouped[str(row["task"])].append(float(value))
    supported = {
        task: {"n": len(values), "difference": sum(values) / len(values)}
        for task, values in sorted(grouped.items())
        if len(values) >= minimum_rows
    }
    nonnegative = sum(item["difference"] >= 0.0 for item in supported.values())
    return {
        "minimum_rows": minimum_rows,
        "supported_tasks": len(supported),
        "nonnegative_tasks": nonnegative,
        "nonnegative_share": nonnegative / len(supported) if supported else 0.0,
        "details": supported,
    }


def discovery_gate(
    audit: dict[str, Any], comparison: dict[str, Any], runtime_s: float, finite: bool
) -> dict[str, bool]:
    pair_difference = comparison["pair_difference"]
    parent_difference = comparison["parent_top1_difference"]
    consistency = comparison["task_consistency"]
    checks = {
        "parent_coverage_ge_090": audit["parent_coverage"] >= 0.90,
        "runs_ge_300": audit["runs"] >= 300,
        "tasks_ge_20": audit["tasks"] >= 20,
        "dominant_task_le_025": audit["dominant_task_share"] <= 0.25,
        "patch_pair_accuracy_ge_054": comparison["patch"]["pair_accuracy"]["overall"] >= 0.54,
        "pair_gain_ge_002": pair_difference["overall"] >= 0.020,
        "parent_top1_gain_ge_003": parent_difference["overall"] >= 0.030,
        "run_ci_low_gt_0": pair_difference["run_macro_ci95"][0] > 0.0,
        "task_ci_low_gt_0": pair_difference["task_macro_ci95"][0] > 0.0,
        "supported_tasks_ge_10": consistency["supported_tasks"] >= 10,
        "task_nonnegative_share_ge_060": consistency["nonnegative_share"] >= 0.60,
        "finite": finite,
        "oracle_eq_1": comparison["oracle_pair_accuracy"] == 1.0,
        "within_wall_cap": runtime_s <= 900.0,
    }
    checks["all"] = all(checks.values())
    return checks


def frozen_gate(audit: dict[str, Any], comparison: dict[str, Any]) -> dict[str, bool]:
    pair_difference = comparison["pair_difference"]
    parent_difference = comparison["parent_top1_difference"]
    consistency = comparison["task_consistency"]
    checks = {
        "parent_coverage_ge_090": audit["parent_coverage"] >= 0.90,
        "run_overlap_eq_0": audit["train_frozen_run_overlap"] == 0,
        "endpoint_overlap_eq_0": audit["train_frozen_endpoint_overlap"] == 0,
        "patch_pair_accuracy_ge_056": comparison["patch"]["pair_accuracy"]["overall"] >= 0.56,
        "pair_gain_ge_003": pair_difference["overall"] >= 0.030,
        "parent_top1_gain_ge_004": parent_difference["overall"] >= 0.040,
        "run_ci_low_gt_0": pair_difference["run_macro_ci95"][0] > 0.0,
        "task_ci_low_gt_0": pair_difference["task_macro_ci95"][0] > 0.0,
        "task_nonnegative_share_ge_060": consistency["nonnegative_share"] >= 0.60,
    }
    checks["all"] = all(checks.values())
    return checks


def write_predictions(
    path: Path,
    split: str,
    rows: Sequence[dict[str, Any]],
    predictions: dict[str, dict[str, Any]],
) -> None:
    fields = [
        "split",
        "row_index",
        "task",
        "run",
        "parent",
        "better",
        "worse",
        "absolute_better_score",
        "absolute_worse_score",
        "absolute_margin",
        "absolute_hit",
        "patch_better_score",
        "patch_worse_score",
        "patch_margin",
        "patch_hit",
        "random_margin",
        "random_hit",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, row in enumerate(rows):
            record: dict[str, Any] = {
                "split": split,
                "row_index": index,
                "task": row["task"],
                "run": row["run"],
                "parent": row["parent"],
                "better": row["better"],
                "worse": row["worse"],
            }
            for arm in ("absolute", "patch"):
                record[f"{arm}_better_score"] = predictions[arm]["scores"][row["better"]]
                record[f"{arm}_worse_score"] = predictions[arm]["scores"][row["worse"]]
                record[f"{arm}_margin"] = predictions[arm]["margins"][index]
                record[f"{arm}_hit"] = predictions[arm]["hits"][index]
            random_margin = deterministic_random_score(row["better"]) - deterministic_random_score(
                row["worse"]
            )
            record["random_margin"] = random_margin
            record["random_hit"] = tie_hit(random_margin)
            writer.writerow(record)


def comparison_summary(
    rows: Sequence[dict[str, Any]],
    predictions: dict[str, dict[str, Any]],
    supported_task_minimum: int,
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    parent_records: dict[str, dict[str, dict[str, Any]]] = {}
    for arm_index, arm in enumerate(("absolute", "patch")):
        parent_records[arm] = parent_top1_records(rows, predictions[arm]["scores"])
        output[arm] = {
            "pair_accuracy": summarize_pair_values(
                rows, predictions[arm]["hits"], 20 + arm_index * 10
            ),
            "parent_top1": summarize_parent_values(
                parent_records[arm], 40 + arm_index * 10
            ),
        }
    pair_difference = [
        patch - absolute
        for patch, absolute in zip(predictions["patch"]["hits"], predictions["absolute"]["hits"])
    ]
    parent_difference_records: dict[str, dict[str, Any]] = {}
    for parent in sorted(parent_records["absolute"]):
        if parent not in parent_records["patch"]:
            raise IntegrityError(f"parent support differs between arms: {parent}")
        absolute = parent_records["absolute"][parent]
        patch = parent_records["patch"][parent]
        parent_difference_records[parent] = {
            **patch,
            "value": float(patch["value"]) - float(absolute["value"]),
        }
    random_scores = {
        card_id: deterministic_random_score(card_id)
        for row in rows
        for card_id in (str(row["better"]), str(row["worse"]))
    }
    random_hits = [
        tie_hit(random_scores[str(row["better"])] - random_scores[str(row["worse"])] )
        for row in rows
    ]
    output["random"] = {
        "pair_accuracy": summarize_pair_values(rows, random_hits, 80),
        "parent_top1": summarize_parent_values(parent_top1_records(rows, random_scores), 90),
    }
    output["pair_difference"] = summarize_pair_values(rows, pair_difference, 100)
    output["parent_top1_difference"] = summarize_parent_values(
        parent_difference_records, 110
    )
    output["task_consistency"] = supported_task_consistency(
        rows, pair_difference, supported_task_minimum
    )
    output["oracle_pair_accuracy"] = 1.0
    return output


def run_experiment(args: argparse.Namespace, result: dict[str, Any]) -> int:
    import numpy as np
    import scipy
    from scipy import sparse
    import sklearn
    from sklearn.feature_extraction.text import HashingVectorizer, TfidfTransformer
    from sklearn.linear_model import SGDClassifier
    from sklearn.model_selection import GroupKFold

    started = time.monotonic()
    stage_times: dict[str, float] = {}

    def mark(stage: str) -> None:
        elapsed = time.monotonic() - started
        stage_times[stage] = elapsed
        if elapsed > args.wall_cap_s:
            raise TimeCapExceeded(f"wall cap exceeded after {stage}: {elapsed:.3f}s")

    result["software"] = {
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "sklearn": sklearn.__version__,
    }
    train_raw, train_sha = load_pairs(args.train_pairs, "train")
    needed = needed_card_ids(train_raw)
    cards, cards_sha, corpus_rows = load_card_subset(args.cards, needed)
    run_map = json.loads(args.run_map.read_text(encoding="utf-8"))
    train_rows, train_audit = audit_pair_rows(train_raw, cards, run_map)
    mark("load_and_audit_train")

    if train_audit["parent_coverage"] < 0.90:
        raise IntegrityError(f"train parent coverage {train_audit['parent_coverage']:.6f} < 0.90")
    if train_audit["runs"] < 300 or train_audit["tasks"] < 20:
        raise IntegrityError(
            f"insufficient train support runs={train_audit['runs']} tasks={train_audit['tasks']}"
        )

    result["inputs"].update(
        {
            "cards_sha256": cards_sha,
            "cards_corpus_rows": corpus_rows,
            "run_map_sha256": sha256(args.run_map),
            "train_pairs_sha256": train_sha,
            "prereg_sha256": sha256(args.prereg),
            "source_sha256": sha256(Path(__file__)),
        }
    )
    result["train_audit"] = train_audit

    def build_texts(
        pair_rows: Sequence[dict[str, Any]], card_table: dict[str, Card]
    ) -> tuple[list[str], dict[str, int], dict[str, list[str]], dict[str, Any]]:
        candidate_ids = sorted(
            {
                str(row[key])
                for row in pair_rows
                for key in ("better", "worse")
            }
        )
        position = {card_id: index for index, card_id in enumerate(candidate_ids)}
        absolute: list[str] = []
        patch: list[str] = []
        patch_ratios: list[float] = []
        empty = 0
        for card_id in candidate_ids:
            card = card_table[card_id]
            parent = card_table[card.parent_id or ""]
            delta = line_delta(
                parent.code[:TEXT_LIMIT], card.code[:TEXT_LIMIT], card.operator
            )
            if len(delta.splitlines()) <= 1:
                empty += 1
            patch_ratios.append(len(delta) / max(min(len(card.code), TEXT_LIMIT), 1))
            absolute.append(card.code[:TEXT_LIMIT])
            patch.append(delta[:TEXT_LIMIT])
        representation = {
            "candidate_ids": len(candidate_ids),
            "empty_patch_share": empty / len(candidate_ids),
            "median_patch_to_code_chars": float(np.median(patch_ratios)),
            "p90_patch_to_code_chars": float(np.quantile(patch_ratios, 0.9)),
        }
        return candidate_ids, position, {"absolute": absolute, "patch": patch}, representation

    vectorizer = HashingVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        n_features=N_FEATURES,
        alternate_sign=False,
        norm=None,
        lowercase=False,
        dtype=np.float32,
    )

    candidate_ids, position, texts, representation = build_texts(train_rows, cards)
    count_matrices = {
        arm: vectorizer.transform(values).tocsr() for arm, values in texts.items()
    }
    result["representation"] = representation
    mark("build_train_representations")

    def fit_predict(
        counts: Any,
        fit_rows: Sequence[dict[str, Any]],
        eval_rows: Sequence[dict[str, Any]],
        candidate_position: dict[str, int],
        model_seed: int,
    ) -> tuple[list[float], dict[str, float], int]:
        fit_candidate_positions = sorted(
            {
                candidate_position[str(row[key])]
                for row in fit_rows
                for key in ("better", "worse")
            }
        )
        transformer = TfidfTransformer(sublinear_tf=True, smooth_idf=True, norm="l2")
        transformer.fit(counts[fit_candidate_positions])
        matrix = transformer.transform(counts).tocsr()
        better = np.array(
            [candidate_position[str(row["better"])] for row in fit_rows], dtype=np.int64
        )
        worse = np.array(
            [candidate_position[str(row["worse"])] for row in fit_rows], dtype=np.int64
        )
        positive = matrix[better] - matrix[worse]
        x_train = sparse.vstack([positive, -positive], format="csr")
        y_train = np.concatenate(
            [np.ones(len(fit_rows), dtype=np.int8), np.zeros(len(fit_rows), dtype=np.int8)]
        )
        per_parent = collections.Counter(str(row["parent"]) for row in fit_rows)
        base_weights = np.array(
            [0.5 / per_parent[str(row["parent"])] for row in fit_rows], dtype=np.float64
        )
        sample_weight = np.concatenate([base_weights, base_weights])
        model = SGDClassifier(
            loss="log_loss",
            penalty="l2",
            alpha=1e-5,
            max_iter=2_000,
            tol=1e-4,
            average=True,
            fit_intercept=False,
            random_state=model_seed,
        )
        model.fit(x_train, y_train, sample_weight=sample_weight)
        eval_better = np.array(
            [candidate_position[str(row["better"])] for row in eval_rows], dtype=np.int64
        )
        eval_worse = np.array(
            [candidate_position[str(row["worse"])] for row in eval_rows], dtype=np.int64
        )
        margins = np.asarray(
            model.decision_function(matrix[eval_better] - matrix[eval_worse]), dtype=float
        ).reshape(-1)
        eval_candidates = sorted(
            {
                str(row[key])
                for row in eval_rows
                for key in ("better", "worse")
            }
        )
        eval_positions = [candidate_position[card_id] for card_id in eval_candidates]
        candidate_scores = np.asarray(
            model.decision_function(matrix[eval_positions]), dtype=float
        ).reshape(-1)
        return (
            margins.tolist(),
            dict(zip(eval_candidates, candidate_scores.tolist())),
            int(model.n_iter_),
        )

    groups = np.array([str(row["run"]) for row in train_rows])
    splitter = GroupKFold(n_splits=5)
    predictions: dict[str, dict[str, Any]] = {
        arm: {
            "margins": [math.nan] * len(train_rows),
            "hits": [math.nan] * len(train_rows),
            "scores": {},
            "folds": [],
        }
        for arm in ("absolute", "patch")
    }
    fold_assignment = [-1] * len(train_rows)
    for fold, (fit_indices, valid_indices) in enumerate(
        splitter.split(np.zeros(len(train_rows)), groups=groups)
    ):
        fit_rows = [train_rows[int(index)] for index in fit_indices]
        valid_rows = [train_rows[int(index)] for index in valid_indices]
        fit_runs = {str(row["run"]) for row in fit_rows}
        valid_runs = {str(row["run"]) for row in valid_rows}
        if fit_runs & valid_runs:
            raise IntegrityError(f"fold {fold} has physical-run overlap")
        for index in valid_indices:
            fold_assignment[int(index)] = fold
        for arm_index, arm in enumerate(("absolute", "patch")):
            margins, scores, n_iter = fit_predict(
                count_matrices[arm],
                fit_rows,
                valid_rows,
                position,
                SEED + fold * 10 + arm_index,
            )
            for local_index, global_index in enumerate(valid_indices):
                predictions[arm]["margins"][int(global_index)] = margins[local_index]
                predictions[arm]["hits"][int(global_index)] = tie_hit(margins[local_index])
            for card_id, score in scores.items():
                existing = predictions[arm]["scores"].get(card_id)
                if existing is not None and not math.isclose(existing, score, abs_tol=EPSILON):
                    raise IntegrityError(f"OOF score mismatch for {arm}/{card_id}")
                predictions[arm]["scores"][card_id] = score
            predictions[arm]["folds"].append(
                {
                    "fold": fold,
                    "fit_rows": len(fit_rows),
                    "valid_rows": len(valid_rows),
                    "fit_runs": len(fit_runs),
                    "valid_runs": len(valid_runs),
                    "n_iter": n_iter,
                }
            )
        mark(f"oof_fold_{fold}")

    if any(fold < 0 for fold in fold_assignment):
        raise IntegrityError("not every discovery row received an OOF fold")
    finite = all(
        math.isfinite(float(value))
        for arm in predictions.values()
        for key in ("margins", "hits")
        for value in arm[key]
    )
    discovery = comparison_summary(train_rows, predictions, supported_task_minimum=20)
    discovery["fold_assignment_counts"] = dict(
        sorted(collections.Counter(fold_assignment).items())
    )
    runtime_before_gate = time.monotonic() - started
    gate = discovery_gate(train_audit, discovery, runtime_before_gate, finite)
    result["discovery"] = discovery
    result["discovery_gate"] = gate
    result["stage_times_s"] = stage_times
    write_predictions(args.out_dir / "oof_predictions.csv", "discovery", train_rows, predictions)
    result["outputs"]["oof_predictions_sha256"] = sha256(
        args.out_dir / "oof_predictions.csv"
    )
    atomic_json(args.out_dir / "summary.json", result)
    mark("discovery_written")

    if not gate["all"]:
        result["status"] = "DISCOVERY_NO_UNLOCK"
        result["frozen_read"] = False
        result["stage_times_s"] = stage_times
        result["runtime_s"] = time.monotonic() - started
        atomic_json(args.out_dir / "summary.json", result)
        print("PARENT_PATCH_DISCOVERY_NO_UNLOCK", json.dumps(gate, sort_keys=True))
        return 0

    frozen_raw, frozen_sha = load_pairs(args.frozen_pairs, "test")
    result["frozen_read"] = True
    combined_needed = needed_card_ids(train_raw) | needed_card_ids(frozen_raw)
    all_cards, second_cards_sha, second_corpus_rows = load_card_subset(args.cards, combined_needed)
    if second_cards_sha != cards_sha or second_corpus_rows != corpus_rows:
        raise IntegrityError("cards changed between discovery and frozen unlock")
    frozen_rows, frozen_audit = audit_pair_rows(frozen_raw, all_cards, run_map)
    train_runs = {str(row["run"]) for row in train_rows}
    frozen_runs = {str(row["run"]) for row in frozen_rows}
    train_endpoints = {
        str(row[key]) for row in train_rows for key in ("better", "worse")
    }
    frozen_endpoints = {
        str(row[key]) for row in frozen_rows for key in ("better", "worse")
    }
    frozen_audit["train_frozen_run_overlap"] = len(train_runs & frozen_runs)
    frozen_audit["train_frozen_endpoint_overlap"] = len(train_endpoints & frozen_endpoints)
    if frozen_audit["train_frozen_run_overlap"] or frozen_audit["train_frozen_endpoint_overlap"]:
        raise IntegrityError("train/frozen overlap after unlock")
    if frozen_audit["parent_coverage"] < 0.90:
        raise IntegrityError(f"frozen parent coverage {frozen_audit['parent_coverage']:.6f} < 0.90")
    mark("load_and_audit_frozen")

    all_rows = [*train_rows, *frozen_rows]
    all_candidate_ids, all_position, all_texts, frozen_representation = build_texts(
        all_rows, all_cards
    )
    all_counts = {
        arm: vectorizer.transform(values).tocsr() for arm, values in all_texts.items()
    }
    mark("build_frozen_representations")
    frozen_predictions: dict[str, dict[str, Any]] = {}
    for arm_index, arm in enumerate(("absolute", "patch")):
        margins, scores, n_iter = fit_predict(
            all_counts[arm],
            train_rows,
            frozen_rows,
            all_position,
            SEED + 500 + arm_index,
        )
        frozen_predictions[arm] = {
            "margins": margins,
            "hits": [tie_hit(margin) for margin in margins],
            "scores": scores,
            "n_iter": n_iter,
        }
        mark(f"frozen_fit_{arm}")

    frozen = comparison_summary(frozen_rows, frozen_predictions, supported_task_minimum=10)
    frozen["representation"] = frozen_representation
    frozen_checks = frozen_gate(frozen_audit, frozen)
    write_predictions(
        args.out_dir / "frozen_predictions.csv", "frozen", frozen_rows, frozen_predictions
    )
    result["inputs"]["frozen_pairs_sha256"] = frozen_sha
    result["frozen_read"] = True
    result["frozen_audit"] = frozen_audit
    result["frozen"] = frozen
    result["frozen_gate"] = frozen_checks
    result["outputs"]["frozen_predictions_sha256"] = sha256(
        args.out_dir / "frozen_predictions.csv"
    )
    result["status"] = (
        "SPARSE_PATCH_GREEN" if frozen_checks["all"] else "SPARSE_PATCH_NOT_GREEN"
    )
    result["stage_times_s"] = stage_times
    result["runtime_s"] = time.monotonic() - started
    atomic_json(args.out_dir / "summary.json", result)
    print("PARENT_PATCH_FINAL", result["status"], json.dumps(frozen_checks, sort_keys=True))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", required=True, type=Path)
    parser.add_argument("--run-map", required=True, type=Path)
    parser.add_argument("--train-pairs", required=True, type=Path)
    parser.add_argument("--frozen-pairs", required=True, type=Path)
    parser.add_argument("--prereg", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--wall-cap-s", type=float, default=900.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=args.repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"cannot resolve git commit: {error}") from error
    result: dict[str, Any] = {
        "protocol": "parent_patch_sparse_v3",
        "seed": SEED,
        "git_commit": commit,
        "command": [sys.executable, *sys.argv],
        "inputs": {
            "cards": str(args.cards),
            "run_map": str(args.run_map),
            "train_pairs": str(args.train_pairs),
            "frozen_pairs": str(args.frozen_pairs),
            "prereg": str(args.prereg),
        },
        "config": {
            "folds": 5,
            "n_features": N_FEATURES,
            "text_limit": TEXT_LIMIT,
            "ngram_range": [3, 5],
            "alpha": 1e-5,
            "parent_equal_weight": True,
            "wall_cap_s": args.wall_cap_s,
            "gpu_count": 0,
            "api_calls": 0,
        },
        "outputs": {},
        "frozen_read": False,
        "status": "RUNNING",
    }
    atomic_json(args.out_dir / "summary.json", result)
    try:
        return run_experiment(args, result)
    except TimeCapExceeded as error:
        result["status"] = "ENGINEERING_TIMEOUT"
        result["error"] = str(error)
        atomic_json(args.out_dir / "summary.json", result)
        print("PARENT_PATCH_ENGINEERING_TIMEOUT", error, file=sys.stderr)
        return 3
    except IntegrityError as error:
        result["status"] = "INVALID"
        result["error"] = str(error)
        atomic_json(args.out_dir / "summary.json", result)
        print("PARENT_PATCH_INVALID", error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
