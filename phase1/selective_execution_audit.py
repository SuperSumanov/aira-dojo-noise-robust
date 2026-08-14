#!/usr/bin/env python3
"""Retrospective, registered selective-execution audit on v11 run-OOF scores.

The policy reads only endpoint identities and pre-execution OOF scores when it
selects parents.  Ground-truth orientation and score gap are attached only when
metrics are evaluated.  This analysis never opens frozen/test/first-960 files.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import random
import shutil
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PROTOCOL = "selective_execution_v11_retrospective_discovery_v1"
EXPECTED_INPUT_SHA256 = "fc57c03a1c96ce7be19a4db764a539082258fe4c69a2ec8653b41ff85626cb45"
EXPECTED_ROWS = 4_263
EXPECTED_PARENTS = 2_293
EXPECTED_EXACT_TWO = 1_520
EXPECTED_RUNS = 294
EXPECTED_TASKS = 23
EXPECTED_FOLDS = {0: 285, 1: 215, 2: 222, 3: 373, 4: 425}
EXPECTED_DOMINANT = 336
EXPECTED_QUOTA = 295
PRIMARY_Q = 0.20
CURVE_Q = (0.05, 0.10, 0.20, 0.40, 0.60, 0.80, 1.00)
BOOTSTRAPS = 10_000
TASK_SEED = 20_260_814
RUN_SEED = 20_260_815
EPSILON = 1e-12

ARMS = ("char_tfidf_lr", "static_lr", "fixed_frozen_global")
REQUIRED_BASE_FIELDS = {
    "row_index",
    "task",
    "run",
    "parent",
    "better",
    "worse",
    "gap_raw",
    "fold",
}
FORBIDDEN_PATH_WORDS = (
    "decision_frozen",
    "decision_test",
    "first960",
    "first-960",
    "held_pairs",
    "test_pairs",
    "cards_current",
    "stdout",
    "runtime",
    "self_report",
    "external_score",
)


class AuditError(RuntimeError):
    """Fail-closed audit error."""


@dataclass(frozen=True)
class Pair:
    row_index: int
    task: str
    run: str
    parent: str
    lo: str
    hi: str
    true_vote: int
    gap: float
    fold: int
    votes: Mapping[str, int]
    confidence: Mapping[str, float]
    percentiles: Mapping[str, float] | None = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_hex(*parts: str) -> str:
    payload = "\x00".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def finite_float(value: str, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise AuditError(f"invalid float for {label}") from error
    if not math.isfinite(number):
        raise AuditError(f"non-finite float for {label}")
    return number


def strict_int(value: str, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise AuditError(f"invalid integer for {label}") from error
    if str(number) != str(value).strip():
        raise AuditError(f"non-canonical integer for {label}")
    return number


def vote(delta: float) -> int:
    if delta > EPSILON:
        return 1
    if delta < -EPSILON:
        return -1
    return 0


def hit(prediction: int, truth: int) -> float:
    if prediction == 0:
        return 0.5
    return float(prediction == truth)


def assert_safe_input(path: Path) -> None:
    lowered = str(path).replace("\\", "/").lower()
    bad = [word for word in FORBIDDEN_PATH_WORDS if word in lowered]
    if bad:
        raise AuditError(f"forbidden input-path token: {bad[0]}")
    if path.name != "oof_predictions.csv":
        raise AuditError("input basename must be oof_predictions.csv")


def load_exact_two(path: Path) -> tuple[list[Pair], dict[str, Any]]:
    assert_safe_input(path)
    input_sha = sha256_file(path)
    if input_sha != EXPECTED_INPUT_SHA256:
        raise AuditError("OOF input SHA-256 mismatch")

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        required = set(REQUIRED_BASE_FIELDS)
        for arm in ARMS:
            required.update(
                {
                    f"{arm}_better_score",
                    f"{arm}_worse_score",
                    f"{arm}_hit",
                }
            )
        if not required <= fields:
            raise AuditError(f"missing CSV fields: {sorted(required - fields)}")
        raw_rows = list(reader)

    if len(raw_rows) != EXPECTED_ROWS:
        raise AuditError("row-count mismatch")
    if [strict_int(row["row_index"], "row_index") for row in raw_rows] != list(range(EXPECTED_ROWS)):
        raise AuditError("row_index is not canonical and contiguous")

    grouped: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for row in raw_rows:
        parent = row["parent"]
        if not parent or not row["task"] or not row["run"]:
            raise AuditError("blank structural identity")
        grouped[parent].append(row)
    if len(grouped) != EXPECTED_PARENTS:
        raise AuditError("parent-count mismatch")

    for parent, rows in grouped.items():
        structural = {(row["task"], row["run"], row["fold"]) for row in rows}
        if len(structural) != 1:
            raise AuditError(f"parent crosses task/run/fold: {parent}")

    pairs: list[Pair] = []
    for parent, rows in grouped.items():
        if len(rows) != 1:
            continue
        row = rows[0]
        better, worse = row["better"], row["worse"]
        if not better or not worse or better == worse:
            raise AuditError(f"invalid endpoint identity: {parent}")
        lo, hi = sorted((better, worse))
        true_vote = 1 if better == hi else -1
        gap = finite_float(row["gap_raw"], "gap_raw")
        if gap <= 0.0:
            raise AuditError(f"non-positive exact-two gap: {parent}")
        fold = strict_int(row["fold"], "fold")

        votes: dict[str, int] = {}
        confidence: dict[str, float] = {}
        for arm in ARMS:
            better_score = finite_float(row[f"{arm}_better_score"], f"{arm} better score")
            worse_score = finite_float(row[f"{arm}_worse_score"], f"{arm} worse score")
            score_by_id = {better: better_score, worse: worse_score}
            delta = score_by_id[hi] - score_by_id[lo]
            votes[arm] = vote(delta)
            confidence[arm] = abs(delta)
            published = finite_float(row[f"{arm}_hit"], f"{arm} published hit")
            recomputed = hit(votes[arm], true_vote)
            if abs(published - recomputed) > EPSILON:
                raise AuditError(f"published hit mismatch: {parent} {arm}")

        pairs.append(
            Pair(
                row_index=strict_int(row["row_index"], "row_index"),
                task=row["task"],
                run=row["run"],
                parent=parent,
                lo=lo,
                hi=hi,
                true_vote=true_vote,
                gap=gap,
                fold=fold,
                votes=votes,
                confidence=confidence,
            )
        )

    pairs.sort(key=lambda item: item.row_index)
    fold_counts = collections.Counter(pair.fold for pair in pairs)
    task_counts = collections.Counter(pair.task for pair in pairs)
    if len(pairs) != EXPECTED_EXACT_TWO:
        raise AuditError("exact-two count mismatch")
    if len({pair.run for pair in pairs}) != EXPECTED_RUNS:
        raise AuditError("exact-two run count mismatch")
    if len(task_counts) != EXPECTED_TASKS:
        raise AuditError("exact-two task count mismatch")
    if dict(sorted(fold_counts.items())) != EXPECTED_FOLDS:
        raise AuditError("exact-two fold counts mismatch")
    if task_counts.most_common(1)[0][1] != EXPECTED_DOMINANT:
        raise AuditError("exact-two dominant task mismatch")
    quota = sum(math.floor(PRIMARY_Q * count) for count in task_counts.values())
    if quota != EXPECTED_QUOTA:
        raise AuditError("task quota mismatch")

    audit = {
        "input_sha256": input_sha,
        "rows": len(raw_rows),
        "parents": len(grouped),
        "exact_two_parents": len(pairs),
        "exact_two_runs": len({pair.run for pair in pairs}),
        "exact_two_tasks": len(task_counts),
        "fold_counts": {str(key): value for key, value in sorted(fold_counts.items())},
        "task_counts": dict(sorted(task_counts.items())),
        "dominant_task": task_counts.most_common(1)[0][0],
        "dominant_count": task_counts.most_common(1)[0][1],
        "dominant_share": task_counts.most_common(1)[0][1] / len(pairs),
        "q20_quota": quota,
    }
    return attach_percentiles(pairs), audit


def midrank_percentiles(items: Sequence[tuple[str, float]]) -> dict[str, float]:
    ordered = sorted(items, key=lambda item: (item[1], item[0]))
    output: dict[str, float] = {}
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][1] == ordered[start][1]:
            end += 1
        percentile = ((start + 1) + end) / (2.0 * len(ordered))
        for index in range(start, end):
            output[ordered[index][0]] = percentile
        start = end
    return output


def attach_percentiles(pairs: Sequence[Pair]) -> list[Pair]:
    ranks: dict[tuple[str, int], dict[str, float]] = {}
    for arm in ARMS:
        for fold in EXPECTED_FOLDS:
            subset = [(pair.parent, pair.confidence[arm]) for pair in pairs if pair.fold == fold]
            ranks[(arm, fold)] = midrank_percentiles(subset)
    output = []
    for pair in pairs:
        percentiles = {arm: ranks[(arm, pair.fold)][pair.parent] for arm in ARMS}
        output.append(
            Pair(
                row_index=pair.row_index,
                task=pair.task,
                run=pair.run,
                parent=pair.parent,
                lo=pair.lo,
                hi=pair.hi,
                true_vote=pair.true_vote,
                gap=pair.gap,
                fold=pair.fold,
                votes=pair.votes,
                confidence=pair.confidence,
                percentiles=percentiles,
            )
        )
    return output


def unanimous_vote(pair: Pair) -> int:
    votes = [pair.votes[arm] for arm in ARMS]
    return votes[0] if votes[0] != 0 and len(set(votes)) == 1 else 0


def committee_confidence(pair: Pair) -> float:
    if pair.percentiles is None:
        raise AuditError("percentiles are missing")
    return min(pair.percentiles[arm] for arm in ARMS)


def group_by_task(pairs: Iterable[Pair]) -> dict[str, list[Pair]]:
    grouped: dict[str, list[Pair]] = collections.defaultdict(list)
    for pair in pairs:
        grouped[pair.task].append(pair)
    return dict(grouped)


def ranked_take(rows: Sequence[Pair], count: int, score, namespace: str) -> list[Pair]:
    return sorted(
        rows,
        key=lambda pair: (-float(score(pair)), stable_hex(PROTOCOL, namespace, pair.parent), pair.parent),
    )[:count]


def crc_take(rows: Sequence[Pair], count: int, namespace: str) -> list[Pair]:
    return sorted(rows, key=lambda pair: (stable_hex(PROTOCOL, namespace, pair.parent), pair.parent))[:count]


def build_policies(pairs: Sequence[Pair], q: float = PRIMARY_Q) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
    by_task = group_by_task(pairs)
    primary: dict[str, int] = {}
    quotas: dict[str, int] = {}
    eligible_by_task: dict[str, list[Pair]] = {}
    for task, rows in by_task.items():
        quota = math.floor(q * len(rows))
        quotas[task] = quota
        eligible = [pair for pair in rows if unanimous_vote(pair) != 0]
        eligible_by_task[task] = eligible
        for pair in ranked_take(eligible, quota, committee_confidence, f"tri_q{q:.2f}"):
            primary[pair.parent] = unanimous_vote(pair)

    realized = collections.Counter(pair.task for pair in pairs if pair.parent in primary)
    char_margin: dict[str, int] = {}
    unanimous_crc: dict[str, int] = {}
    char_crc: dict[str, int] = {}
    for task, rows in by_task.items():
        count = realized[task]
        if count == 0:
            continue
        for pair in ranked_take(
            rows,
            count,
            lambda item: (item.percentiles or {})["char_tfidf_lr"],
            "char_margin_matched",
        ):
            char_margin[pair.parent] = pair.votes["char_tfidf_lr"]
        for pair in crc_take(eligible_by_task[task], count, "unanimous_crc_matched"):
            unanimous_crc[pair.parent] = unanimous_vote(pair)
        for pair in crc_take(rows, count, "char_crc_matched"):
            char_crc[pair.parent] = pair.votes["char_tfidf_lr"]

    random_primary = {
        pair.parent: (1 if int(stable_hex(PROTOCOL, "random_on_primary", pair.parent), 16) & 1 else -1)
        for pair in pairs
        if pair.parent in primary
    }
    oracle_all = {pair.parent: pair.true_vote for pair in pairs}
    random_all = {
        pair.parent: (1 if int(stable_hex(PROTOCOL, "random_all", pair.parent), 16) & 1 else -1)
        for pair in pairs
    }
    policies = {
        "tri_unanimous_q20": primary,
        "char_margin_matched": char_margin,
        "unanimous_crc_matched": unanimous_crc,
        "char_crc_matched": char_crc,
        "random_on_primary": random_primary,
        "oracle_all": oracle_all,
        "random_all": random_all,
    }
    return policies, quotas


def percentile_interval(values: list[float]) -> list[float]:
    values.sort()
    return [values[int(0.025 * len(values))], values[int(0.975 * len(values))]]


def bootstrap_macro(values: Mapping[str, float], seed: int, samples: int = BOOTSTRAPS) -> list[float]:
    keys = sorted(values)
    if not keys:
        raise AuditError("cannot bootstrap empty values")
    rng = random.Random(seed)
    draws = []
    for _ in range(samples):
        draws.append(statistics.fmean(values[rng.choice(keys)] for _ in keys))
    return percentile_interval(draws)


def policy_metrics(pairs: Sequence[Pair], predictions: Mapping[str, int], seed_offset: int) -> dict[str, Any]:
    selected = [pair for pair in pairs if pair.parent in predictions]
    if not selected:
        return {
            "selected": 0,
            "runs": 0,
            "tasks": 0,
            "coverage": 0.0,
            "candidate_executions": 2 * len(pairs),
            "candidate_saving_fraction": 0.0,
            "micro_accuracy": None,
            "run_macro_accuracy": None,
            "task_macro_accuracy": None,
        }
    outcomes = {pair.parent: hit(predictions[pair.parent], pair.true_vote) for pair in selected}
    by_task: dict[str, list[float]] = collections.defaultdict(list)
    by_run: dict[str, list[float]] = collections.defaultdict(list)
    selected_by_task: collections.Counter[str] = collections.Counter()
    for pair in selected:
        value = outcomes[pair.parent]
        by_task[pair.task].append(value)
        by_run[pair.run].append(value)
        selected_by_task[pair.task] += 1
    task_accuracy = {key: statistics.fmean(values) for key, values in by_task.items()}
    run_accuracy = {key: statistics.fmean(values) for key, values in by_run.items()}
    all_gap_by_task: dict[str, float] = collections.defaultdict(float)
    lost_gap_by_task: dict[str, float] = collections.defaultdict(float)
    for pair in pairs:
        all_gap_by_task[pair.task] += pair.gap
    for pair in selected:
        lost_gap_by_task[pair.task] += pair.gap * (1.0 - outcomes[pair.parent])
    loss_ratio = {
        task: lost_gap_by_task[task] / total for task, total in all_gap_by_task.items()
    }
    selected_gap = sum(pair.gap for pair in selected)
    selected_correct_gap = sum(pair.gap * outcomes[pair.parent] for pair in selected)
    dominant_task, dominant_count = selected_by_task.most_common(1)[0]
    task_macro = statistics.fmean(task_accuracy.values())
    loto = [
        statistics.fmean(value for task, value in task_accuracy.items() if task != dropped)
        for dropped in task_accuracy
        if len(task_accuracy) > 1
    ]
    return {
        "selected": len(selected),
        "selected_parent_sha256": hashlib.sha256(
            "\n".join(sorted(pair.parent for pair in selected)).encode("utf-8")
        ).hexdigest(),
        "runs": len(by_run),
        "tasks": len(by_task),
        "dominant_task": dominant_task,
        "dominant_count": dominant_count,
        "dominant_share": dominant_count / len(selected),
        "coverage": len(selected) / len(pairs),
        "candidate_executions": 2 * len(pairs) - len(selected),
        "candidate_saving_fraction": len(selected) / (2.0 * len(pairs)),
        "micro_accuracy": statistics.fmean(outcomes.values()),
        "run_macro_accuracy": statistics.fmean(run_accuracy.values()),
        "run_macro_ci95": bootstrap_macro(run_accuracy, RUN_SEED + seed_offset),
        "task_macro_accuracy": task_macro,
        "task_macro_ci95": bootstrap_macro(task_accuracy, TASK_SEED + seed_offset),
        "task_macro_loto_range": [min(loto), max(loto)] if loto else [task_macro, task_macro],
        "selected_gap_weighted_accuracy": selected_correct_gap / selected_gap,
        "task_macro_total_gap_loss_ratio": statistics.fmean(loss_ratio.values()),
        "per_task_accuracy": dict(sorted(task_accuracy.items())),
        "per_task_selected": dict(sorted(selected_by_task.items())),
        "per_task_total_gap_loss_ratio": dict(sorted(loss_ratio.items())),
    }


def task_delta(
    left: Mapping[str, Any], right: Mapping[str, Any], seed_offset: int
) -> dict[str, Any]:
    left_task = left.get("per_task_accuracy", {})
    right_task = right.get("per_task_accuracy", {})
    common = sorted(set(left_task) & set(right_task))
    if not common:
        raise AuditError("no common tasks for policy comparison")
    values = {task: float(left_task[task]) - float(right_task[task]) for task in common}
    return {
        "tasks": len(common),
        "task_macro_delta": statistics.fmean(values.values()),
        "task_macro_delta_ci95": bootstrap_macro(values, TASK_SEED + seed_offset),
        "per_task_delta": values,
    }


def curve_policy(pairs: Sequence[Pair], q: float, committee: bool) -> dict[str, int]:
    selected: dict[str, int] = {}
    for task, rows in group_by_task(pairs).items():
        quota = math.floor(q * len(rows))
        if committee:
            eligible = [pair for pair in rows if unanimous_vote(pair) != 0]
            chosen = ranked_take(eligible, quota, committee_confidence, f"curve_tri_{q:.2f}")
            selected.update({pair.parent: unanimous_vote(pair) for pair in chosen})
        else:
            chosen = ranked_take(
                rows,
                quota,
                lambda item: (item.percentiles or {})["char_tfidf_lr"],
                f"curve_char_{q:.2f}",
            )
            selected.update({pair.parent: pair.votes["char_tfidf_lr"] for pair in chosen})
    return selected


def central_curve_metrics(pairs: Sequence[Pair], predictions: Mapping[str, int]) -> dict[str, Any]:
    selected = [pair for pair in pairs if pair.parent in predictions]
    if not selected:
        return {"selected": 0, "coverage": 0.0, "micro_accuracy": None, "task_macro_accuracy": None}
    by_task: dict[str, list[float]] = collections.defaultdict(list)
    values = []
    for pair in selected:
        value = hit(predictions[pair.parent], pair.true_vote)
        values.append(value)
        by_task[pair.task].append(value)
    return {
        "selected": len(selected),
        "coverage": len(selected) / len(pairs),
        "candidate_saving_fraction": len(selected) / (2.0 * len(pairs)),
        "micro_accuracy": statistics.fmean(values),
        "task_macro_accuracy": statistics.fmean(statistics.fmean(v) for v in by_task.values()),
        "tasks": len(by_task),
    }


def make_gate(
    audit: Mapping[str, Any], metrics: Mapping[str, Mapping[str, Any]], comparisons: Mapping[str, Any]
) -> tuple[dict[str, bool], dict[str, bool], str, str]:
    primary = metrics["tri_unanimous_q20"]
    random_all = metrics["random_all"]
    oracle = metrics["oracle_all"]
    char_delta = comparisons["primary_minus_char_margin_matched"]
    crc_delta = comparisons["primary_minus_unanimous_crc_matched"]
    integrity = {
        "input_sha_exact": audit["input_sha256"] == EXPECTED_INPUT_SHA256,
        "structure_exact": (
            audit["rows"] == EXPECTED_ROWS
            and audit["parents"] == EXPECTED_PARENTS
            and audit["exact_two_parents"] == EXPECTED_EXACT_TWO
            and audit["exact_two_runs"] == EXPECTED_RUNS
            and audit["exact_two_tasks"] == EXPECTED_TASKS
        ),
        "oracle_accuracy_eq_1": oracle["micro_accuracy"] == 1.0,
        "oracle_gap_loss_eq_0": oracle["task_macro_total_gap_loss_ratio"] == 0.0,
        "random_all_micro_in_047_053": 0.47 <= random_all["micro_accuracy"] <= 0.53,
        "frozen_or_first960_read_false": True,
    }
    scientific = {
        "selected_ge_228": primary["selected"] >= 228,
        "runs_ge_100": primary["runs"] >= 100,
        "tasks_ge_20": primary["tasks"] >= 20,
        "dominant_share_le_025": primary["dominant_share"] <= 0.25,
        "candidate_saving_ge_0075": primary["candidate_saving_fraction"] >= 0.075,
        "micro_accuracy_ge_058": primary["micro_accuracy"] >= 0.58,
        "run_macro_accuracy_ge_058": primary["run_macro_accuracy"] >= 0.58,
        "task_macro_accuracy_ge_058": primary["task_macro_accuracy"] >= 0.58,
        "run_ci_low_gt_050": primary["run_macro_ci95"][0] > 0.50,
        "task_ci_low_gt_050": primary["task_macro_ci95"][0] > 0.50,
        "char_delta_ge_002": char_delta["task_macro_delta"] >= 0.02,
        "char_delta_ci_low_gt_0": char_delta["task_macro_delta_ci95"][0] > 0.0,
        "selected_gap_weighted_accuracy_ge_060": primary["selected_gap_weighted_accuracy"] >= 0.60,
        "task_macro_gap_loss_le_008": primary["task_macro_total_gap_loss_ratio"] <= 0.08,
    }
    verdict = (
        "SELECTIVE_EXECUTION_DISCOVERY_UNLOCK"
        if all(integrity.values()) and all(scientific.values())
        else "SELECTIVE_EXECUTION_DISCOVERY_NO_UNLOCK"
    )
    margin_verdict = (
        "MARGIN_ENRICHMENT_SUPPORTED"
        if crc_delta["task_macro_delta"] >= 0.02 and crc_delta["task_macro_delta_ci95"][0] > 0.0
        else "MARGIN_ENRICHMENT_NOT_SUPPORTED"
    )
    return integrity, scientific, verdict, margin_verdict


def atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_selected(path: Path, pairs: Sequence[Pair], policies: Mapping[str, Mapping[str, int]]) -> None:
    fields = ["parent", "task", "run", "fold"] + [f"{name}_vote" for name in policies]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for pair in sorted(pairs, key=lambda item: item.parent):
            row: dict[str, Any] = {
                "parent": pair.parent,
                "task": pair.task,
                "run": pair.run,
                "fold": pair.fold,
            }
            for name, prediction in policies.items():
                row[f"{name}_vote"] = prediction.get(pair.parent, "")
            writer.writerow(row)


def write_per_task(path: Path, metrics: Mapping[str, Mapping[str, Any]]) -> None:
    fields = ["policy", "task", "selected", "accuracy", "total_gap_loss_ratio"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for policy, result in metrics.items():
            selected = result.get("per_task_selected", {})
            accuracy = result.get("per_task_accuracy", {})
            loss = result.get("per_task_total_gap_loss_ratio", {})
            for task in sorted(loss):
                writer.writerow(
                    {
                        "policy": policy,
                        "task": task,
                        "selected": selected.get(task, 0),
                        "accuracy": "" if task not in accuracy else format(accuracy[task], ".17g"),
                        "total_gap_loss_ratio": format(loss[task], ".17g"),
                    }
                )


def write_curves(path: Path, curves: Sequence[Mapping[str, Any]]) -> None:
    fields = [
        "family",
        "q",
        "selected",
        "coverage",
        "candidate_saving_fraction",
        "micro_accuracy",
        "task_macro_accuracy",
        "tasks",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in curves:
            writer.writerow(row)


def run(input_csv: Path, output_dir: Path) -> dict[str, Any]:
    started = time.monotonic()
    if output_dir.exists():
        raise AuditError("refusing to overwrite output directory")
    output_dir.mkdir(parents=True)
    try:
        pairs, audit = load_exact_two(input_csv)
        policies, quotas = build_policies(pairs)
        metrics = {
            name: policy_metrics(pairs, predictions, 100 * index)
            for index, (name, predictions) in enumerate(policies.items())
        }
        comparisons = {
            "primary_minus_char_margin_matched": task_delta(
                metrics["tri_unanimous_q20"], metrics["char_margin_matched"], 1_000
            ),
            "primary_minus_unanimous_crc_matched": task_delta(
                metrics["tri_unanimous_q20"], metrics["unanimous_crc_matched"], 2_000
            ),
            "primary_minus_char_crc_matched": task_delta(
                metrics["tri_unanimous_q20"], metrics["char_crc_matched"], 3_000
            ),
        }
        curves = []
        for family, committee in (("char_margin", False), ("tri_unanimous", True)):
            for q in CURVE_Q:
                row = central_curve_metrics(pairs, curve_policy(pairs, q, committee))
                row.update({"family": family, "q": q})
                curves.append(row)
        integrity, scientific, verdict, margin_verdict = make_gate(audit, metrics, comparisons)
        write_selected(output_dir / "selected_parents.csv", pairs, policies)
        write_per_task(output_dir / "per_task.csv", metrics)
        write_curves(output_dir / "risk_coverage.csv", curves)
        summary = {
            "protocol": PROTOCOL,
            "evidence_level": "retrospective_registered_discovery_not_independent_confirmation",
            "input": str(input_csv),
            "input_audit": audit,
            "parameters": {
                "arms": list(ARMS),
                "primary_q": PRIMARY_Q,
                "curve_q": list(CURVE_Q),
                "bootstrap_samples": BOOTSTRAPS,
                "task_seed": TASK_SEED,
                "run_seed": RUN_SEED,
                "confidence": "fold_midrank_percentile_of_abs_endpoint_score_margin",
                "committee_confidence": "minimum_of_three_arm_percentiles",
                "task_quotas": dict(sorted(quotas.items())),
            },
            "frozen_or_first960_read": False,
            "policies": metrics,
            "comparisons": comparisons,
            "risk_coverage": curves,
            "integrity_gates": integrity,
            "scientific_gates": scientific,
            "margin_enrichment_verdict": margin_verdict,
            "verdict": verdict,
            "runtime_s": time.monotonic() - started,
        }
        atomic_json(output_dir / "summary.json", summary)
        print(
            f"{verdict} selected={metrics['tri_unanimous_q20']['selected']} "
            f"task_macro={metrics['tri_unanimous_q20']['task_macro_accuracy']:.6f} "
            f"saving={metrics['tri_unanimous_q20']['candidate_saving_fraction']:.6f}",
            flush=True,
        )
        return summary
    except Exception:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run(args.input, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
