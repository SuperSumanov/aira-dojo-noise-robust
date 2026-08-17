#!/usr/bin/env python3
"""Frozen confirmatory analysis for prospective score-channel replays."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import os
import platform
import random
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


PROTOCOL = "score-channel-prospective-analysis-v1"
SELECTION_PROTOCOL = "score-channel-parent-selection-v1"
SELECTION_ROW_SCHEMA = "score-channel-parent-selection-row-v1"
REPLAY_PROTOCOL = "score-channel-replay-manifest-v1"
REPLAY_ROW_SCHEMA = "score-channel-replay-candidate-v1"
RESULT_ROW_SCHEMA = "score-channel-replay-result-row-v1"
APPROVAL_PROTOCOL = "score-channel-replay-approval-v1"
INTAKE_PROTOCOL = "prospective_drop_intake_v1"
SEED = 20260813
BOOTSTRAPS = 10_000
CAP_SECONDS = 120

SELECTION_KEYS = {
    "schema_version", "task", "run_id", "parent_id", "source_intake",
    "selection_rank_in_run", "selection_key_sha256", "candidate_card_ids",
    "candidate_count", "candidate_identity_sha256",
}
REPLAY_KEYS = {
    "schema_version", "card_id", "competition", "task", "run_id", "parent",
    "code", "code_sha256", "source_intake", "selection_rank_in_run",
    "shard_id", "cap_seconds",
}
RESULT_KEYS = {
    "schema_version", "card_id", "competition", "task", "run_id", "parent",
    "source_intake", "selection_rank_in_run", "shard_id", "cap_seconds",
    "code_sha256", "rc", "wall_seconds", "stdout_val", "val_how",
    "stdout_bytes", "stderr_bytes", "stdout_sha256", "stderr_sha256",
    "sub_exists", "submission_bytes", "submission_sha256",
    "submission_line_count", "submission_header_sha256", "grader_rc",
    "sub_score", "grader_output_sha256", "execution_attempts",
    "manifest_sha256", "approval_sha256", "worker_source_commit",
}
VAULT_KEYS = {"card_id", "task", "run_id", "graded", "y_norm", "eligible_by_start_time"}


class AnalysisError(RuntimeError):
    """Fail-closed confirmatory-analysis error."""


def canonical(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def sha256_file(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            state.update(block)
    return state.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def valid_sha(value: Any, label: str, length: int = 64) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value.lower())
    ):
        raise AnalysisError(f"invalid {label}")
    return value.lower()


def finite(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        canonical(value)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise AnalysisError(f"cannot read canonical {label}") from error
    if not isinstance(value, dict):
        raise AnalysisError(f"{label} is not an object")
    return value


def read_rows(path: Path, label: str, *, allow_empty: bool = False) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise AnalysisError(f"cannot read {label}") from error
    if not lines and not allow_empty:
        raise AnalysisError(f"{label} is empty")
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(lines, 1):
        if not line:
            raise AnalysisError(f"blank line in {label}")
        try:
            row = json.loads(line)
            canonical(row)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise AnalysisError(f"invalid {label} line {number}") from error
        if not isinstance(row, dict):
            raise AnalysisError(f"non-object {label} line {number}")
        rows.append(row)
    return rows


def load_selection(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    summary_path = root / "summary.json"
    rows_path = root / "selected_parents.jsonl"
    summary = read_object(summary_path, "selection summary")
    if (
        summary.get("protocol") != SELECTION_PROTOCOL
        or summary.get("status") != "PARENT_GATE_PASS_REPLAY_APPROVAL_PENDING"
        or (summary.get("gates") or {}).get("parent_gate_pass") is not True
    ):
        raise AnalysisError("parent selection has not passed")
    expected = valid_sha(
        (summary.get("outputs") or {}).get("selected_parents_sha256"),
        "selected-parent SHA",
    )
    if sha256_file(rows_path) != expected:
        raise AnalysisError("selected-parent SHA mismatch")
    rows = read_rows(rows_path, "selected parents")
    seen_parents: set[tuple[str, str]] = set()
    seen_cards: set[str] = set()
    for row in rows:
        if set(row) != SELECTION_KEYS or row.get("schema_version") != SELECTION_ROW_SCHEMA:
            raise AnalysisError("selected-parent schema mismatch")
        key = (row.get("run_id"), row.get("parent_id"))
        cards = row.get("candidate_card_ids")
        if (
            any(not isinstance(value, str) or not value for value in key)
            or key in seen_parents
            or not isinstance(cards, list)
            or cards != sorted(set(cards))
            or len(cards) < 2
            or row.get("candidate_count") != len(cards)
            or sha256_text(canonical(cards)) != valid_sha(row.get("candidate_identity_sha256"), "candidate identity SHA")
            or any(not isinstance(card, str) or not card or card in seen_cards for card in cards)
        ):
            raise AnalysisError("invalid selected parent or candidate set")
        seen_parents.add(key)
        seen_cards.update(cards)
    counts = summary.get("counts") or {}
    if counts.get("selected_parents") != len(rows) or counts.get("selected_candidates") != len(seen_cards):
        raise AnalysisError("selection counts changed")
    return rows, summary


def load_replay(root: Path, selection_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    summary_path = root / "summary.json"
    manifest_path = root / "replay_manifest.jsonl"
    summary = read_object(summary_path, "replay summary")
    if (
        summary.get("protocol") != REPLAY_PROTOCOL
        or summary.get("status") != "REPLAY_MANIFEST_FROZEN_APPROVAL_PENDING"
        or (summary.get("matrix") or {}).get("cap_seconds") != CAP_SECONDS
        or (summary.get("matrix") or {}).get("shards") != 4
        or (summary.get("budget") or {}).get("gpu_jobs_submitted") != 0
    ):
        raise AnalysisError("replay summary contract mismatch")
    inputs = summary.get("inputs") or {}
    if (
        inputs.get("parent_selection_summary_sha256") != sha256_file(selection_root / "summary.json")
        or inputs.get("selected_parents_sha256") != sha256_file(selection_root / "selected_parents.jsonl")
    ):
        raise AnalysisError("replay does not bind the selected parents")
    expected = valid_sha((summary.get("outputs") or {}).get("replay_manifest_sha256"), "replay manifest SHA")
    if sha256_file(manifest_path) != expected:
        raise AnalysisError("replay manifest SHA mismatch")
    rows = read_rows(manifest_path, "replay manifest")
    seen: set[str] = set()
    for row in rows:
        if set(row) != REPLAY_KEYS or row.get("schema_version") != REPLAY_ROW_SCHEMA:
            raise AnalysisError("replay row schema mismatch")
        card = row.get("card_id")
        code = row.get("code")
        if (
            not isinstance(card, str) or not card or card in seen
            or row.get("cap_seconds") != CAP_SECONDS
            or row.get("competition") != row.get("task")
            or not isinstance(code, str) or not code
            or sha256_text(code) != valid_sha(row.get("code_sha256"), "code SHA")
        ):
            raise AnalysisError("invalid replay candidate")
        seen.add(card)
    counts = summary.get("counts") or {}
    if counts.get("planned_candidate_replays") != len(rows):
        raise AnalysisError("replay candidate count mismatch")
    return rows, summary


def load_approval(path: Path, expected_sha: str, replay_root: Path, replay_summary: dict[str, Any]) -> tuple[dict[str, Any], str]:
    expected_sha = valid_sha(expected_sha, "approval SHA")
    if sha256_file(path) != expected_sha:
        raise AnalysisError("approval SHA mismatch")
    value = read_object(path, "approval receipt")
    outputs = replay_summary.get("outputs") or {}
    counts = replay_summary.get("counts") or {}
    budget = replay_summary.get("budget") or {}
    if (
        value.get("protocol") != APPROVAL_PROTOCOL
        or value.get("approved") is not True
        or value.get("cap_seconds") != CAP_SECONDS
        or value.get("shards") != 4
        or value.get("gpus_per_shard") != 1
        or value.get("base_llm_update") is not False
        or value.get("llm_api_calls") != 0
        or value.get("online_hf") is not True
        or value.get("fresh_workspace_per_candidate") is not True
        or value.get("replay_manifest_sha256") != outputs.get("replay_manifest_sha256")
        or value.get("replay_summary_sha256") != sha256_file(replay_root / "summary.json")
        or value.get("shard_sha256") != outputs.get("shard_sha256")
        or value.get("planned_candidate_replays") != counts.get("planned_candidate_replays")
        or value.get("cap_upper_bound_gpu_hours") != budget.get("cap_upper_bound_gpu_hours")
    ):
        raise AnalysisError("approval does not exactly bind the replay matrix")
    valid_sha(value.get("worker_source_commit"), "approved worker commit", length=40)
    return value, expected_sha


def load_orientation(path: Path, expected_sha: str, tasks: set[str]) -> tuple[dict[str, int], str]:
    expected_sha = valid_sha(expected_sha, "orientation SHA")
    if sha256_file(path) != expected_sha:
        raise AnalysisError("orientation SHA mismatch")
    value = read_object(path, "orientation registry")
    if value.get("protocol") != "score-channel-task-orientation-v1" or value.get("outcomes_read") is not False:
        raise AnalysisError("orientation registry contract mismatch")
    orientations = value.get("orientation")
    if not isinstance(orientations, dict) or any(
        isinstance(item, bool) or item not in {-1, 1} for item in orientations.values()
    ):
        raise AnalysisError("invalid task orientation values")
    if not tasks <= set(orientations):
        raise AnalysisError("selected task is absent from the frozen orientation registry")
    return {task: int(orientations[task]) for task in tasks}, expected_sha


def load_labels(
    intake_root: Path,
    selected: list[dict[str, Any]],
    selection_summary: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    wanted_by_intake: dict[str, set[str]] = collections.defaultdict(set)
    identity: dict[str, tuple[str, str]] = {}
    for parent in selected:
        for card in parent["candidate_card_ids"]:
            wanted_by_intake[parent["source_intake"]].add(card)
            identity[card] = (parent["task"], parent["run_id"])
    declared = (selection_summary.get("inputs") or {}).get("intake_summary_sha256")
    if not isinstance(declared, dict):
        raise AnalysisError("selection does not bind intake summaries")
    labels: dict[str, dict[str, Any]] = {}
    for intake, wanted in sorted(wanted_by_intake.items()):
        if intake not in declared:
            raise AnalysisError("selected intake is not bound")
        root = intake_root / intake
        summary_path = root / "summary.json"
        if sha256_file(summary_path) != valid_sha(declared[intake], "intake summary SHA"):
            raise AnalysisError("intake summary changed")
        summary = read_object(summary_path, "intake summary")
        if summary.get("protocol") != INTAKE_PROTOCOL or summary.get("status") != "PROSPECTIVE_DROP_INTAKE_COMPLETE":
            raise AnalysisError("selected intake is incomplete")
        vault_path = root / "label_vault.jsonl"
        if sha256_file(vault_path) != valid_sha((summary.get("outputs") or {}).get("label_vault_sha256"), "vault SHA"):
            raise AnalysisError("label-vault SHA mismatch")
        for row in read_rows(vault_path, "label vault", allow_empty=True):
            card = row.get("card_id")
            if card not in wanted:
                continue
            if (
                set(row) != VAULT_KEYS
                or card in labels
                or (row.get("task"), row.get("run_id")) != identity[card]
                or row.get("eligible_by_start_time") is not True
                or not finite(row.get("graded"))
                or not finite(row.get("y_norm"))
            ):
                raise AnalysisError("selected label row is invalid")
            labels[card] = row
    if set(labels) != set(identity):
        raise AnalysisError("not every selected candidate has one finite frozen label")
    return labels


def load_results(
    paths: list[Path], expected_shas: list[str], manifests: dict[str, dict[str, Any]],
    replay_summary: dict[str, Any], approval_sha: str, approved_worker_commit: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    if len(paths) != len(expected_shas) or len(paths) != 4:
        raise AnalysisError("exactly four result files and SHAs are required")
    shard_hashes = (replay_summary.get("outputs") or {}).get("shard_sha256")
    if not isinstance(shard_hashes, dict):
        raise AnalysisError("replay shard hashes are missing")
    results: dict[str, dict[str, Any]] = {}
    file_hashes: dict[str, str] = {}
    worker_commits: set[str] = set()
    seen_shards: set[int] = set()
    for path, expected in zip(paths, expected_shas, strict=True):
        expected = valid_sha(expected, "result file SHA")
        if sha256_file(path) != expected:
            raise AnalysisError("result file SHA mismatch")
        rows = read_rows(path, "replay results")
        file_shards = {row.get("shard_id") for row in rows}
        if len(file_shards) != 1:
            raise AnalysisError("one result file must contain exactly one shard")
        shard = next(iter(file_shards))
        if isinstance(shard, bool) or not isinstance(shard, int) or shard not in range(4) or shard in seen_shards:
            raise AnalysisError("invalid or duplicate result shard")
        seen_shards.add(shard)
        if len(rows) != (replay_summary.get("counts") or {}).get("shard_candidate_replays", {}).get(str(shard)):
            raise AnalysisError("result shard is incomplete")
        for row in rows:
            if set(row) != RESULT_KEYS or row.get("schema_version") != RESULT_ROW_SCHEMA:
                raise AnalysisError("result row schema mismatch")
            card = row.get("card_id")
            manifest = manifests.get(card)
            if manifest is None or card in results:
                raise AnalysisError("extra or duplicate replay result")
            for key in (
                "card_id", "competition", "task", "run_id", "parent", "source_intake",
                "selection_rank_in_run", "shard_id", "cap_seconds", "code_sha256",
            ):
                if row.get(key) != manifest.get(key):
                    raise AnalysisError(f"result/manifest mismatch for {key}")
            if (
                row.get("manifest_sha256") != shard_hashes.get(str(shard))
                or row.get("approval_sha256") != approval_sha
                or row.get("val_how") not in {None, "keyed", "bare"}
                or finite(row.get("stdout_val")) != (row.get("val_how") in {"keyed", "bare"})
                or (finite(row.get("sub_score")) and row.get("sub_exists") is not True)
            ):
                raise AnalysisError("result signal or binding contract mismatch")
            worker_commits.add(valid_sha(row.get("worker_source_commit"), "worker commit", length=40))
            results[card] = row
        file_hashes[str(shard)] = expected
    if (
        set(results) != set(manifests)
        or seen_shards != set(range(4))
        or worker_commits != {approved_worker_commit}
    ):
        raise AnalysisError("replay results are incomplete or use multiple worker commits")
    return results, dict(sorted(file_hashes.items()))


def expected_hit(signal: dict[str, float], truth: dict[str, float]) -> float:
    if set(signal) != set(truth) or not signal:
        raise AnalysisError("signal/truth support mismatch")
    best_signal = max(signal.values())
    chosen = [card for card, value in signal.items() if math.isclose(value, best_signal, rel_tol=0, abs_tol=1e-12)]
    best_truth = max(truth.values())
    winners = {card for card, value in truth.items() if math.isclose(value, best_truth, rel_tol=0, abs_tol=1e-12)}
    return sum(card in winners for card in chosen) / len(chosen)


def per_set_rows(
    selected: list[dict[str, Any]], labels: dict[str, dict[str, Any]],
    results: dict[str, dict[str, Any]], orientation: dict[str, int],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for parent in selected:
        cards = parent["candidate_card_ids"]
        common = [
            card for card in cards
            if finite(results[card].get("sub_score"))
            and results[card].get("val_how") == "keyed"
            and finite(results[card].get("stdout_val"))
        ]
        if len(common) < 2:
            continue
        task = parent["task"]
        sign = orientation[task]
        truth = {card: float(labels[card]["y_norm"]) for card in common}
        external = {card: sign * float(results[card]["sub_score"]) for card in common}
        stdout = {card: sign * float(results[card]["stdout_val"]) for card in common}
        a = expected_hit(external, truth)
        b = expected_hit(stdout, truth)
        output.append({
            "task": task,
            "run_id": parent["run_id"],
            "parent_id": parent["parent_id"],
            "selection_rank_in_run": parent["selection_rank_in_run"],
            "candidate_count": len(cards),
            "common_candidate_count": len(common),
            "external_top1_credit": a,
            "stdout_top1_credit": b,
            "delta": a - b,
        })
    return output


def clustered_ci(rows: list[dict[str, Any]], cluster_key: str, bootstraps: int, seed: int) -> list[float]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row in rows:
        grouped[str(row[cluster_key])].append(float(row["delta"]))
    keys = sorted(grouped)
    if not keys:
        raise AnalysisError("cannot bootstrap an empty headline")
    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(bootstraps):
        sampled = [rng.choice(keys) for _ in keys]
        values = [value for key in sampled for value in grouped[key]]
        draws.append(sum(values) / len(values))
    draws.sort()
    return [draws[int(0.025 * bootstraps)], draws[int(0.975 * bootstraps)]]


def exact_run_sign(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row in rows:
        grouped[row["run_id"]].append(float(row["delta"]))
    effects = [sum(values) / len(values) for values in grouped.values()]
    positive = sum(value > 1e-12 for value in effects)
    negative = sum(value < -1e-12 for value in effects)
    tied = len(effects) - positive - negative
    informative = positive + negative
    if informative:
        smaller = min(positive, negative)
        tail = sum(math.comb(informative, index) for index in range(smaller + 1)) / (2 ** informative)
        p_value = min(1.0, 2 * tail)
    else:
        p_value = 1.0
    return {
        "positive": positive,
        "negative": negative,
        "tied": tied,
        "informative": informative,
        "exact_p_two_sided": p_value,
    }


def summarize(
    rows: list[dict[str, Any]], selected: list[dict[str, Any]], replay: list[dict[str, Any]],
    results: dict[str, dict[str, Any]], bootstraps: int, seed: int,
) -> dict[str, Any]:
    total = len(replay)
    common_cards = {
        card for parent in rows
        for card in next(item["candidate_card_ids"] for item in selected if item["parent_id"] == parent["parent_id"] and item["run_id"] == parent["run_id"])
        if finite(results[card].get("sub_score")) and results[card].get("val_how") == "keyed"
    }
    if not rows:
        return {
            "status": "INSUFFICIENT_COMMON_CHANNEL_COVERAGE",
            "method_positive_claim_allowed": False,
            "counts": {
                "selected_parents": len(selected), "planned_replays": total,
                "common_parents": 0, "common_cards": 0,
            },
        }
    external = sum(row["external_top1_credit"] for row in rows) / len(rows)
    stdout = sum(row["stdout_top1_credit"] for row in rows) / len(rows)
    delta = external - stdout
    run_ci = clustered_ci(rows, "run_id", bootstraps, seed)
    task_ci = clustered_ci(rows, "task", bootstraps, seed)
    sign = exact_run_sign(rows)
    tasks = sorted({row["task"] for row in rows})
    per_task = {
        task: {
            "parents": sum(row["task"] == task for row in rows),
            "delta": sum(row["delta"] for row in rows if row["task"] == task)
            / sum(row["task"] == task for row in rows),
        }
        for task in tasks
    }
    loto: dict[str, float] = {}
    for held in tasks:
        kept = [row["delta"] for row in rows if row["task"] != held]
        if kept:
            loto[held] = sum(kept) / len(kept)
    no_loto_harm = bool(loto) and min(loto.values()) > -0.10
    criteria = {
        "direction_positive": delta > 0,
        "run_sign_p_lt_0_05": sign["exact_p_two_sided"] < 0.05,
        "run_clustered_ci_lower_gt_0": run_ci[0] > 0,
        "task_loto_all_gt_neg_0_10": no_loto_harm,
    }
    if delta <= 0:
        status = "SCORE_CHANNEL_MECHANISM_KILL"
    elif all(criteria.values()):
        status = "SCORE_CHANNEL_MECHANISM_GO"
    else:
        status = "SCORE_CHANNEL_MECHANISM_BORDERLINE"
    return {
        "status": status,
        "method_positive_claim_allowed": status == "SCORE_CHANNEL_MECHANISM_GO",
        "counts": {
            "selected_parents": len(selected),
            "planned_replays": total,
            "common_parents": len(rows),
            "common_cards": len(common_cards),
            "common_runs": len({row["run_id"] for row in rows}),
            "common_tasks": len(tasks),
            "finite_external_cards": sum(finite(row.get("sub_score")) for row in results.values()),
            "keyed_stdout_cards": sum(row.get("val_how") == "keyed" for row in results.values()),
            "both_channels_cards": sum(
                finite(row.get("sub_score")) and row.get("val_how") == "keyed"
                for row in results.values()
            ),
        },
        "headline": {
            "external_top1": external,
            "stdout_top1": stdout,
            "delta": delta,
            "run_clustered_ci95": run_ci,
            "task_clustered_ci95": task_ci,
            "run_sign": sign,
            "task_loto_delta": dict(sorted(loto.items())),
            "per_task": per_task,
        },
        "criteria": criteria,
    }


def repository_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    value = result.stdout.strip()
    if result.returncode or len(value) != 40:
        raise AnalysisError("cannot resolve analysis source commit")
    return value


def produce(args: argparse.Namespace) -> dict[str, Any]:
    if args.out_dir.exists():
        raise FileExistsError(f"refusing to overwrite output: {args.out_dir}")
    selected, selection_summary = load_selection(args.selection_dir)
    replay, replay_summary = load_replay(args.replay_dir, args.selection_dir)
    selection_cards = {card for parent in selected for card in parent["candidate_card_ids"]}
    manifests = {row["card_id"]: row for row in replay}
    if selection_cards != set(manifests):
        raise AnalysisError("selection/replay candidate identity mismatch")
    approval, approval_sha = load_approval(
        args.approval, args.expect_approval_sha256, args.replay_dir, replay_summary
    )
    orientation, orientation_sha = load_orientation(
        args.orientation, args.expect_orientation_sha256, {row["task"] for row in selected}
    )
    labels = load_labels(args.intake_root, selected, selection_summary)
    results, result_shas = load_results(
        args.result, args.expect_result_sha256, manifests, replay_summary, approval_sha,
        valid_sha(approval["worker_source_commit"], "approved worker commit", length=40),
    )
    rows = per_set_rows(selected, labels, results, orientation)
    decision = summarize(rows, selected, replay, results, args.bootstraps, args.seed)
    summary = {
        "protocol": PROTOCOL,
        **decision,
        "design": {
            "cap_seconds": CAP_SECONDS,
            "strict_common_support": "same parent and candidate subset with finite pristine sub_score and keyed stdout_val",
            "truth": "frozen y_norm; larger is better",
            "tie_handling": "expected top-1 credit across all abs_tol=1e-12 ties",
            "primary_cluster": "physical run",
            "secondary_cluster": "task",
            "bootstraps": args.bootstraps,
            "seed": args.seed,
            "no_optional_stopping": True,
        },
        "inputs": {
            "selection_summary_sha256": sha256_file(args.selection_dir / "summary.json"),
            "selected_parents_sha256": sha256_file(args.selection_dir / "selected_parents.jsonl"),
            "replay_summary_sha256": sha256_file(args.replay_dir / "summary.json"),
            "replay_manifest_sha256": sha256_file(args.replay_dir / "replay_manifest.jsonl"),
            "approval_sha256": approval_sha,
            "orientation_sha256": orientation_sha,
            "result_sha256_by_shard": result_shas,
        },
        "scope": {
            "base_llm_updated": False,
            "llm_api_calls": 0,
            "cap_swept": False,
            "task_or_parser_subset_replaces_headline": False,
        },
        "implementation": {
            "source_commit": repository_head(Path(__file__).resolve().parents[1]),
            "script_sha256": sha256_file(Path(__file__)),
            "python": platform.python_version(),
        },
    }
    args.out_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{args.out_dir.name}.tmp.", dir=args.out_dir.parent))
    try:
        with (temporary / "per_set.csv").open("x", encoding="utf-8", newline="") as handle:
            fields = [
                "task", "run_id", "parent_id", "selection_rank_in_run", "candidate_count",
                "common_candidate_count", "external_top1_credit", "stdout_top1_credit", "delta",
            ]
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        (temporary / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
            encoding="utf-8", newline="\n",
        )
        os.replace(temporary, args.out_dir)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return summary


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-dir", type=Path, required=True)
    parser.add_argument("--replay-dir", type=Path, required=True)
    parser.add_argument("--intake-root", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--expect-approval-sha256", required=True)
    parser.add_argument("--orientation", type=Path, required=True)
    parser.add_argument("--expect-orientation-sha256", required=True)
    parser.add_argument("--result", type=Path, action="append", required=True)
    parser.add_argument("--expect-result-sha256", action="append", required=True)
    parser.add_argument("--bootstraps", type=int, default=BOOTSTRAPS)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if args.bootstraps != BOOTSTRAPS or args.seed != SEED:
        print("SCORE_CHANNEL_ANALYSIS_ERROR: frozen bootstrap/seed mismatch", file=os.sys.stderr)
        return 2
    try:
        summary = produce(args)
    except (AnalysisError, FileExistsError, OSError) as error:
        print(f"SCORE_CHANNEL_ANALYSIS_ERROR: {error}", file=os.sys.stderr)
        return 2
    print(canonical({
        "status": summary["status"],
        "method_positive_claim_allowed": summary["method_positive_claim_allowed"],
        "counts": summary["counts"],
        "headline": summary.get("headline"),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
