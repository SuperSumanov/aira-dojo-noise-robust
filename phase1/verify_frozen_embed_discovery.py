#!/usr/bin/env python3
"""Independent verifier for frozen-embedding discovery artifacts.

This file deliberately does not import the producer.  It reconstructs metrics,
controls, gates, split isolation, OOF run grouping, and feature-chunk provenance
from raw inputs and emitted artifacts.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import os
import random
import subprocess
import zlib
from pathlib import Path
from typing import Any, Sequence

import numpy as np


SEED = 887
BOOTSTRAP_REPS = 10_000
EPSILON = 1e-12


class VerificationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def tie_hit(margin: float) -> float:
    if margin > EPSILON:
        return 1.0
    if margin < -EPSILON:
        return 0.0
    return 0.5


def random_score(card_id: str) -> float:
    return (zlib.crc32(f"{SEED}:{card_id}".encode("utf-8")) & 0xFFFFFFFF) / 2**32


def cluster_summary(
    rows: Sequence[dict[str, Any]],
    values: Sequence[float],
    key: str,
    seed: int,
) -> tuple[float, list[float], dict[str, float]]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row, value in zip(rows, values):
        grouped[str(row[key])].append(float(value))
    means = {name: sum(items) / len(items) for name, items in sorted(grouped.items())}
    population = list(means.values())
    rng = random.Random(seed)
    draws = [
        sum(rng.choice(population) for _ in population) / len(population)
        for _ in range(BOOTSTRAP_REPS)
    ]
    draws.sort()
    interval = [draws[int(0.025 * BOOTSTRAP_REPS)], draws[int(0.975 * BOOTSTRAP_REPS)]]
    return sum(population) / len(population), interval, means


def summarize(
    rows: Sequence[dict[str, Any]], values: Sequence[float], seed_offset: int
) -> dict[str, Any]:
    run_macro, run_ci, per_run = cluster_summary(rows, values, "run", SEED + seed_offset)
    task_macro, task_ci, per_task = cluster_summary(
        rows, values, "task", SEED + seed_offset + 1
    )
    return {
        "overall": sum(values) / len(values),
        "run_macro": run_macro,
        "run_macro_ci95": run_ci,
        "task_macro": task_macro,
        "task_macro_ci95": task_ci,
        "per_run": per_run,
        "per_task": per_task,
    }


def parent_top1(
    rows: Sequence[dict[str, Any]], scores: dict[str, float]
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        grouped[str(row["parent"])].append(row)
    proxy_rows: list[dict[str, Any]] = []
    values: list[float] = []
    incomplete = 0
    for parent_rows in grouped.values():
        candidates = {
            str(row[key]) for row in parent_rows for key in ("better", "worse")
        }
        if len(parent_rows) != len(candidates) * (len(candidates) - 1) // 2:
            incomplete += 1
            continue
        losses = collections.Counter({candidate: 0 for candidate in candidates})
        for row in parent_rows:
            losses[str(row["worse"])] += 1
        truth = {candidate for candidate, value in losses.items() if value == min(losses.values())}
        maximum = max(scores[candidate] for candidate in candidates)
        predicted = {
            candidate for candidate in candidates if abs(scores[candidate] - maximum) <= EPSILON
        }
        values.append(len(predicted & truth) / len(predicted))
        proxy_rows.append({"run": parent_rows[0]["run"], "task": parent_rows[0]["task"]})
    output = summarize(proxy_rows, values, 40)
    output.update(
        {
            "complete_parents": len(values),
            "incomplete_parents": incomplete,
            "complete_share": len(values) / len(grouped),
        }
    )
    return output


def gap_utility(
    rows: Sequence[dict[str, Any]], hits: Sequence[float]
) -> dict[str, Any]:
    grouped: dict[str, list[tuple[dict[str, Any], float]]] = collections.defaultdict(list)
    for row, hit in zip(rows, hits):
        grouped[str(row["parent"])].append((row, float(hit)))
    proxy_rows: list[dict[str, Any]] = []
    values: list[float] = []
    for items in grouped.values():
        denominator = sum(float(row["gap_raw"]) for row, _ in items)
        values.append(
            sum(float(row["gap_raw"]) * hit for row, hit in items) / denominator
        )
        proxy_rows.append({"run": items[0][0]["run"], "task": items[0][0]["task"]})
    output = summarize(proxy_rows, values, 60)
    output["parents"] = len(values)
    output["definition"] = "mean_parent(sum(gap_raw*hit)/sum(gap_raw))"
    return output


def task_consistency(
    rows: Sequence[dict[str, Any]], hits: Sequence[float]
) -> dict[str, Any]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row, hit in zip(rows, hits):
        grouped[str(row["task"])].append(float(hit))
    supported = {
        task: {"pairs": len(values), "accuracy": sum(values) / len(values)}
        for task, values in sorted(grouped.items())
        if len(values) >= 20
    }
    nonchance = sum(item["accuracy"] >= 0.5 for item in supported.values())
    return {
        "minimum_pairs": 20,
        "supported_tasks": len(supported),
        "nonchance_tasks": nonchance,
        "nonchance_share": nonchance / len(supported) if supported else 0.0,
        "details": supported,
    }


def assert_close(actual: Any, expected: Any, label: str) -> None:
    if isinstance(expected, dict):
        if set(actual) != set(expected):
            raise VerificationError(f"{label} keys differ")
        for key in expected:
            assert_close(actual[key], expected[key], f"{label}.{key}")
    elif isinstance(expected, list):
        if len(actual) != len(expected):
            raise VerificationError(f"{label} lengths differ")
        for index, value in enumerate(expected):
            assert_close(actual[index], value, f"{label}[{index}]")
    elif isinstance(expected, (float, int)) and not isinstance(expected, bool):
        if not math.isclose(float(actual), float(expected), rel_tol=1e-10, abs_tol=1e-12):
            raise VerificationError(f"{label}: {actual!r} != {expected!r}")
    elif actual != expected:
        raise VerificationError(f"{label}: {actual!r} != {expected!r}")


def verify_features(
    feature_root: Path,
    manifest: list[dict[str, Any]],
    manifest_sha: str,
    commit: str,
    model_sha: str,
    worker_sha: str,
) -> dict[str, Any]:
    expected = {str(row["card_id"]): row for row in manifest}
    seen: set[str] = set()
    chunks = 0
    for shard in range(4):
        shard_dir = feature_root / f"shard_{shard}"
        metadata = json.loads((shard_dir / "metadata.json").read_text(encoding="utf-8"))
        if metadata.get("status") != "COMPLETE" or metadata.get("git_commit") != commit:
            raise VerificationError(f"shard {shard} status/commit mismatch")
        if metadata.get("source_sha256") != worker_sha:
            raise VerificationError(f"shard {shard} worker source mismatch")
        inputs = metadata.get("inputs") or {}
        if (
            inputs.get("manifest_sha256") != manifest_sha
            or inputs.get("model_weights_sha256") != model_sha
        ):
            raise VerificationError(f"shard {shard} input hash mismatch")
        config = metadata.get("config") or {}
        if config != {
            "shard": shard,
            "num_shards": 4,
            "max_len": 8192,
            "head_fraction": 0.25,
            "batch_size": 2,
            "chunk_size": 32,
            "limit_cards": 0,
        }:
            raise VerificationError(f"shard {shard} config mismatch")
        records = metadata.get("chunks") or []
        actual = sorted(path.name for path in shard_dir.glob("chunk_*.npz"))
        if [str(record["file"]) for record in records] != actual:
            raise VerificationError(f"shard {shard} chunk inventory mismatch")
        shard_ids: list[str] = []
        for record in records:
            path = shard_dir / str(record["file"])
            if sha256(path) != str(record["sha256"]):
                raise VerificationError(f"chunk hash mismatch: {path}")
            with np.load(path, allow_pickle=False) as data:
                ids = [str(value) for value in data["card_ids"].tolist()]
                matrix = np.asarray(data["features"])
                tokens = np.asarray(data["token_counts"])
                chars = np.asarray(data["code_chars"])
            if matrix.shape != (len(ids), 1792) or not np.isfinite(matrix).all():
                raise VerificationError(f"chunk matrix invalid: {path}")
            if tokens.shape != (len(ids),) or np.any(tokens <= 0) or np.any(tokens > 8192):
                raise VerificationError(f"chunk tokens invalid: {path}")
            for index, card_id in enumerate(ids):
                if card_id not in expected or card_id in seen:
                    raise VerificationError(f"duplicate/unexpected feature ID: {card_id}")
                if int(chars[index]) != int(expected[card_id]["code_chars"]):
                    raise VerificationError(f"code length mismatch: {card_id}")
                seen.add(card_id)
            shard_ids.extend(ids)
            chunks += 1
        assigned = sorted(
            str(row["card_id"]) for row in manifest if int(row["shard"]) == shard
        )
        if shard_ids != assigned:
            raise VerificationError(f"shard {shard} manifest projection mismatch")
    if seen != set(expected):
        raise VerificationError("feature endpoint coverage mismatch")
    return {"endpoints": len(seen), "chunks": chunks, "shards": 4}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--pairs", required=True, type=Path)
    parser.add_argument("--run-map", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--manifest-summary", required=True, type=Path)
    parser.add_argument("--feature-root", required=True, type=Path)
    parser.add_argument("--rank-source", required=True, type=Path)
    parser.add_argument("--worker-source", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--expect-commit", required=True)
    parser.add_argument("--expect-model-sha256", required=True)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if args.out.exists():
        raise FileExistsError(args.out)
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    commit = subprocess.check_output(
        ["git", "-C", str(args.repo_root), "rev-parse", "HEAD"], text=True
    ).strip()
    if commit != args.expect_commit or summary.get("git_commit") != commit:
        raise VerificationError("commit mismatch")
    if summary.get("frozen_read") is not False:
        raise VerificationError("discovery summary claims frozen input was read")
    if sha256(args.rank_source) != summary.get("source_sha256"):
        raise VerificationError("rank-source hash mismatch")
    if sha256(args.predictions) != summary.get("outputs", {}).get("oof_predictions_sha256"):
        raise VerificationError("prediction hash mismatch")

    manifest_raw = args.manifest.read_bytes()
    manifest_sha = hashlib.sha256(manifest_raw).hexdigest()
    manifest = [json.loads(line) for line in manifest_raw.decode("utf-8").splitlines() if line]
    manifest_summary = json.loads(args.manifest_summary.read_text(encoding="utf-8"))
    if manifest_summary.get("outputs", {}).get("manifest_sha256") != manifest_sha:
        raise VerificationError("manifest-summary hash mismatch")
    inputs = summary.get("inputs") or {}
    for label, path, digest in (
        ("pairs", args.pairs, inputs.get("pairs_sha256")),
        ("run_map", args.run_map, inputs.get("run_map_sha256")),
        ("manifest", args.manifest, inputs.get("manifest_sha256")),
        ("manifest_summary", args.manifest_summary, inputs.get("manifest_summary_sha256")),
    ):
        if sha256(path) != digest:
            raise VerificationError(f"{label} input hash mismatch")
    feature_verification = verify_features(
        args.feature_root,
        manifest,
        manifest_sha,
        commit,
        args.expect_model_sha256.lower(),
        sha256(args.worker_source),
    )

    raw_pairs = [
        json.loads(line)
        for line in args.pairs.read_text(encoding="utf-8").splitlines()
        if line
    ]
    with args.predictions.open("r", encoding="utf-8", newline="") as handle:
        emitted = list(csv.DictReader(handle))
    if len(raw_pairs) != len(emitted) or len(emitted) != 4263:
        raise VerificationError("pair/prediction row count mismatch")
    run_map = json.loads(args.run_map.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    hits: list[float] = []
    random_hits: list[float] = []
    scores: dict[str, float] = {}
    run_fold: dict[str, int] = {}
    endpoint_fold: dict[str, int] = {}
    unordered: set[tuple[str, str]] = set()
    for index, (raw, output) in enumerate(zip(raw_pairs, emitted)):
        better, worse = str(raw["better"]), str(raw["worse"])
        canonical = tuple(sorted((better, worse)))
        if canonical in unordered:
            raise VerificationError(f"duplicate/reverse pair at row {index}")
        unordered.add(canonical)
        expected_fields = {
            "row_index": str(index),
            "task": str(raw["task"]),
            "run": str(raw["run_id"]),
            "parent": str(raw["parent"]),
            "better": better,
            "worse": worse,
        }
        if any(output[key] != value for key, value in expected_fields.items()):
            raise VerificationError(f"raw/emitted identity mismatch at row {index}")
        if str(raw["intask_split"]) != "train" or int(raw["budget"]) != 0:
            raise VerificationError(f"non-training row at {index}")
        gap = float(raw["gap_raw"])
        if not math.isclose(float(output["gap_raw"]), gap, rel_tol=0.0, abs_tol=0.0):
            raise VerificationError(f"gap mismatch at row {index}")
        run = str(raw["run_id"])
        if run_map.get(better) != run or run_map.get(worse) != run:
            raise VerificationError(f"run-map mismatch at row {index}")
        fold = int(output["fold"])
        if not 0 <= fold < 5:
            raise VerificationError(f"invalid fold at row {index}")
        if run in run_fold and run_fold[run] != fold:
            raise VerificationError(f"run spans folds: {run}")
        run_fold[run] = fold
        better_score, worse_score = float(output["better_score"]), float(output["worse_score"])
        for card_id, score in ((better, better_score), (worse, worse_score)):
            if card_id in scores and not math.isclose(scores[card_id], score, rel_tol=0.0, abs_tol=1e-12):
                raise VerificationError(f"endpoint score inconsistency: {card_id}")
            scores[card_id] = score
            if card_id in endpoint_fold and endpoint_fold[card_id] != fold:
                raise VerificationError(f"endpoint spans folds: {card_id}")
            endpoint_fold[card_id] = fold
        margin = float(output["margin"])
        if not math.isclose(margin, better_score - worse_score, rel_tol=0.0, abs_tol=1e-12):
            raise VerificationError(f"margin algebra mismatch at row {index}")
        hit = float(output["hit"])
        if hit != tie_hit(margin):
            raise VerificationError(f"hit mismatch at row {index}")
        expected_random_margin = random_score(better) - random_score(worse)
        if not math.isclose(
            float(output["random_margin"]), expected_random_margin, rel_tol=0.0, abs_tol=1e-15
        ):
            raise VerificationError(f"random control mismatch at row {index}")
        random_hit = float(output["random_hit"])
        if random_hit != tie_hit(expected_random_margin):
            raise VerificationError(f"random hit mismatch at row {index}")
        rows.append(
            {
                "task": str(raw["task"]),
                "run": run,
                "parent": str(raw["parent"]),
                "better": better,
                "worse": worse,
                "gap_raw": gap,
            }
        )
        hits.append(hit)
        random_hits.append(random_hit)

    primary = summarize(rows, hits, 10)
    random_control = summarize(rows, random_hits, 20)
    top1 = parent_top1(rows, scores)
    utility = gap_utility(rows, hits)
    consistency = task_consistency(rows, hits)
    for label, actual, expected in (
        ("primary", primary, summary["primary_pair_accuracy"]),
        ("random", random_control, summary["random_control"]),
        ("top1", top1, summary["complete_parent_top1"]),
        ("gap_utility", utility, summary["parent_equal_gap_utility"]),
        ("task_consistency", consistency, summary["task_consistency"]),
    ):
        assert_close(actual, expected, label)

    task_counts = collections.Counter(row["task"] for row in rows)
    checks = {
        "pairs_eq_4263": len(rows) == 4263,
        "runs_ge_300": len(run_fold) >= 300,
        "tasks_eq_23": len(task_counts) == 23,
        "dominant_task_le_025": task_counts.most_common(1)[0][1] / len(rows) <= 0.25,
        "feature_coverage_exact": feature_verification["endpoints"] == len(scores),
        "fold_run_overlap_eq_0": len(run_fold) == len(set(run_fold)),
        "pair_accuracy_ge_054": primary["overall"] >= 0.54,
        "run_macro_ci_low_gt_050": primary["run_macro_ci95"][0] > 0.50,
        "task_macro_ci_low_gt_050": primary["task_macro_ci95"][0] > 0.50,
        "complete_parent_top1_ge_050": top1["overall"] >= 0.50,
        "complete_parent_share_ge_095": top1["complete_share"] >= 0.95,
        "parent_equal_gap_utility_ge_055": utility["overall"] >= 0.55,
        "supported_tasks_ge_15": consistency["supported_tasks"] >= 15,
        "task_nonchance_share_ge_060": consistency["nonchance_share"] >= 0.60,
        "random_pair_accuracy_in_047_053": 0.47 <= random_control["overall"] <= 0.53,
        "oracle_pair_accuracy_eq_1": summary.get("oracle_pair_accuracy") == 1.0,
        "finite": all(math.isfinite(value) for value in scores.values()),
        "converged": all(int(item["n_iter"]) < 2000 for item in summary["folds"]),
        "within_wall_cap": float(summary["runtime_s"])
        <= float(summary["configuration"]["wall_cap_s"]),
    }
    checks["all"] = all(checks.values())
    if checks != summary.get("discovery_gate"):
        raise VerificationError("reconstructed gate differs from producer gate")
    expected_status = "DISCOVERY_UNLOCK_RECOMMENDED" if checks["all"] else "DISCOVERY_NO_UNLOCK"
    if summary.get("status") != expected_status:
        raise VerificationError("status differs from reconstructed gate")
    verification = {
        "status": "VERIFIED_" + expected_status,
        "frozen_read": False,
        "git_commit": commit,
        "verifier_source_sha256": sha256(Path(__file__)),
        "summary_sha256": sha256(args.summary),
        "predictions_sha256": sha256(args.predictions),
        "rank_source_sha256": sha256(args.rank_source),
        "worker_source_sha256": sha256(args.worker_source),
        "feature_verification": feature_verification,
        "reconstructed_gate": checks,
        "headline": {
            "pair_accuracy": primary["overall"],
            "run_macro_ci95": primary["run_macro_ci95"],
            "task_macro_ci95": primary["task_macro_ci95"],
            "complete_parent_top1": top1["overall"],
            "parent_equal_gap_utility": utility["overall"],
        },
    }
    atomic_json(args.out, verification)
    print(
        verification["status"],
        f"pair_accuracy={primary['overall']:.6f}",
        f"gate_all={checks['all']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
