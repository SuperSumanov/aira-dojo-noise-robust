"""Independently verify the compact descriptive E1 collection archive.

This verifier deliberately imports neither the rollout worker nor the collection
producer.  It recomputes every published aggregate from the compact JSON/JSONL
files after the complete-coverage collector has opened the sealed receipts.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import pathlib
import re
import tempfile
from typing import Any


TASKS = ("spaceship-titanic", "tabular-playground-series-may-2022")
SCHEMA = "balanced-continuation-e1-collection-v1"
STATUS = "VERIFIED_COMPLETE_REAL_E1_COLLECTION_DESCRIPTIVE_ONLY"
PRACTICAL_DELTA = 0.01
FAILURE_UTILITY = 0.0
CREDENTIAL = re.compile(
    rb"sk-[A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{20,}|"
    rb"gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
    rb"AIza[0-9A-Za-z_-]{30,}|Bearer\s+[A-Za-z0-9._-]{24,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
)
FILES = {
    "rollouts.jsonl",
    "sibling_labels.jsonl",
    "task_diagnostics.jsonl",
    "summary.json",
    "sha256_manifest.json",
}
ROLLOUT_KEYS = {
    "schema_version", "global_order", "rollout_id", "block_id",
    "block_replicate", "rollout_seed", "task", "anchor_id", "sibling_id",
    "source_run_id", "warm_dsearch_utility_raw",
    "continuation_dsearch_utility_raw", "warm_dval_utility_raw",
    "continuation_dval_utility_raw", "warm_dval_utility_effective",
    "best_within_h_dval_utility_effective", "gain_over_warm_dval",
    "gain_exceeds_practical_delta", "failure_utility", "practical_delta",
    "candidate_wall_time_seconds", "candidate_processes_started",
    "operator_api_calls", "operator_usage",
}
SIBLING_KEYS = {
    "schema_version", "task", "sibling_id", "replicates", "balanced_vh_mean",
    "balanced_vh_sample_variance", "mean_gain_over_warm",
    "practical_success_probability",
}
TASK_KEYS = {
    "schema_version", "task", "rollouts", "replicate_winners",
    "replicate_ranking_agreement", "mean_gain_over_warm",
    "positive_gain_rollouts", "practical_gain_rollouts",
}
SUMMARY_KEYS = {
    "schema_version", "status", "coverage_gate", "source_commit", "tasks",
    "rollout_jobs", "candidate_execution_attempts", "candidate_processes_started",
    "operator_api_calls", "operator_retry_count", "candidate_retry_count",
    "analyze_operator_calls", "dtest_rows_read", "sealed_values_opened",
    "sealed_files_opened_after_coverage_gate", "failure_utility", "practical_delta",
    "total_candidate_wall_seconds", "realized_candidate_gpu_hours",
    "rollouts_with_positive_dval_gain", "rollouts_with_practical_dval_gain",
    "task_replicate_ranking_agreements", "primary_gate_claim_allowed",
    "e2_e3_unlocked", "interpretation",
}


class ArchiveVerificationError(RuntimeError):
    pass


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def checked_bytes(path: pathlib.Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ArchiveVerificationError(f"not a regular file: {path.name}")
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise ArchiveVerificationError(f"credential-shaped bytes: {path.name}")
    return raw


def finite_tree(value: Any, where: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ArchiveVerificationError(f"non-finite number in {where}")
    if isinstance(value, dict):
        for key, child in value.items():
            finite_tree(child, f"{where}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            finite_tree(child, f"{where}[{index}]")


def read_json(path: pathlib.Path) -> dict[str, Any]:
    value = json.loads(checked_bytes(path).decode("utf-8"))
    if not isinstance(value, dict):
        raise ArchiveVerificationError(f"JSON root is not an object: {path.name}")
    finite_tree(value, path.name)
    return value


def read_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(checked_bytes(path).decode("utf-8").splitlines(), 1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ArchiveVerificationError(f"JSONL row is not an object: {path.name}:{line_number}")
        finite_tree(value, f"{path.name}:{line_number}")
        rows.append(value)
    return rows


def close(left: Any, right: Any, where: str) -> None:
    if isinstance(left, bool) or isinstance(right, bool):
        if left is not right:
            raise ArchiveVerificationError(f"boolean mismatch: {where}")
        return
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if not math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-12):
            raise ArchiveVerificationError(f"numeric mismatch: {where}")
        return
    if left != right:
        raise ArchiveVerificationError(f"value mismatch: {where}")


def compare_record(actual: dict[str, Any], expected: dict[str, Any], where: str) -> None:
    if set(actual) != set(expected):
        raise ArchiveVerificationError(f"schema mismatch: {where}")
    for key in expected:
        close(actual[key], expected[key], f"{where}.{key}")


def mean(values: list[float]) -> float:
    if not values:
        raise ArchiveVerificationError("empty aggregate")
    return sum(values) / len(values)


def verify(result_dir: pathlib.Path, output: pathlib.Path) -> dict[str, Any]:
    result_dir = result_dir.resolve()
    output = output.resolve()
    if result_dir.is_symlink() or not result_dir.is_dir():
        raise ArchiveVerificationError("result directory is absent or symlinked")
    if output.exists() or output.is_symlink():
        raise ArchiveVerificationError("verification output already exists")
    actual_files = {path.name for path in result_dir.iterdir() if path.is_file()}
    if actual_files != FILES or any(path.is_dir() for path in result_dir.iterdir()):
        raise ArchiveVerificationError("compact collection inventory differs")

    manifest = read_json(result_dir / "sha256_manifest.json")
    expected_manifest = {
        name: sha256(result_dir / name)
        for name in FILES
        if name != "sha256_manifest.json"
    }
    if manifest != expected_manifest:
        raise ArchiveVerificationError("collection SHA manifest differs")

    rollouts = read_jsonl(result_dir / "rollouts.jsonl")
    siblings = read_jsonl(result_dir / "sibling_labels.jsonl")
    task_rows = read_jsonl(result_dir / "task_diagnostics.jsonl")
    summary = read_json(result_dir / "summary.json")
    if len(rollouts) != 8 or len(siblings) != 4 or len(task_rows) != 2:
        raise ArchiveVerificationError("collection row counts differ")
    if any(set(row) != ROLLOUT_KEYS or row["schema_version"] != SCHEMA for row in rollouts):
        raise ArchiveVerificationError("rollout schema differs")
    if any(set(row) != SIBLING_KEYS or row["schema_version"] != SCHEMA for row in siblings):
        raise ArchiveVerificationError("sibling schema differs")
    if any(set(row) != TASK_KEYS or row["schema_version"] != SCHEMA for row in task_rows):
        raise ArchiveVerificationError("task schema differs")
    if set(summary) != SUMMARY_KEYS:
        raise ArchiveVerificationError("summary schema differs")

    if sorted(row["global_order"] for row in rollouts) != list(range(8)):
        raise ArchiveVerificationError("global order differs")
    if len({row["rollout_id"] for row in rollouts}) != 8:
        raise ArchiveVerificationError("rollout IDs are not unique")
    if collections.Counter(row["task"] for row in rollouts) != {task: 4 for task in TASKS}:
        raise ArchiveVerificationError("task allocation differs")
    if len({row["block_id"] for row in rollouts}) != 4:
        raise ArchiveVerificationError("replicate block count differs")

    sibling_groups: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    block_groups: dict[tuple[str, int], list[dict[str, Any]]] = collections.defaultdict(list)
    for index, row in enumerate(sorted(rollouts, key=lambda item: item["global_order"])):
        if row["task"] not in TASKS or row["block_replicate"] not in (0, 1):
            raise ArchiveVerificationError(f"rollout identity differs at {index}")
        if row["failure_utility"] != FAILURE_UTILITY or row["practical_delta"] != PRACTICAL_DELTA:
            raise ArchiveVerificationError(f"frozen constants differ at {index}")
        raw_warm = row["warm_dval_utility_raw"]
        raw_cont = row["continuation_dval_utility_raw"]
        expected_warm = FAILURE_UTILITY if raw_warm is None else raw_warm
        expected_cont = FAILURE_UTILITY if raw_cont is None else raw_cont
        close(row["warm_dval_utility_effective"], expected_warm, f"rollout[{index}].warm")
        close(row["best_within_h_dval_utility_effective"], expected_cont, f"rollout[{index}].continuation")
        gain = float(expected_cont) - float(expected_warm)
        close(row["gain_over_warm_dval"], gain, f"rollout[{index}].gain")
        if row["gain_exceeds_practical_delta"] is not (gain >= PRACTICAL_DELTA):
            raise ArchiveVerificationError(f"practical indicator differs at {index}")
        walls = row["candidate_wall_time_seconds"]
        if not isinstance(walls, list) or len(walls) != 2 or any(
            isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0
            for value in walls
        ):
            raise ArchiveVerificationError(f"candidate wall accounting differs at {index}")
        if row["operator_api_calls"] != 1 or not isinstance(row["operator_usage"], list):
            raise ArchiveVerificationError(f"operator accounting differs at {index}")
        sibling_groups[(row["task"], row["sibling_id"])].append(row)
        block_groups[(row["task"], row["block_replicate"])].append(row)
    if any(len(rows) != 2 for rows in sibling_groups.values()) or len(sibling_groups) != 4:
        raise ArchiveVerificationError("sibling replicate coverage differs")
    if any(len(rows) != 2 for rows in block_groups.values()) or len(block_groups) != 4:
        raise ArchiveVerificationError("block sibling coverage differs")

    expected_siblings = []
    for (task, sibling), rows in sorted(sibling_groups.items()):
        rows.sort(key=lambda row: row["block_replicate"])
        values = [float(row["best_within_h_dval_utility_effective"]) for row in rows]
        gains = [float(row["gain_over_warm_dval"]) for row in rows]
        expected_siblings.append({
            "schema_version": SCHEMA,
            "task": task,
            "sibling_id": sibling,
            "replicates": 2,
            "balanced_vh_mean": mean(values),
            "balanced_vh_sample_variance": (values[0] - values[1]) ** 2 / 2,
            "mean_gain_over_warm": mean(gains),
            "practical_success_probability": mean([
                float(row["gain_exceeds_practical_delta"]) for row in rows
            ]),
        })
    for actual, expected in zip(sorted(siblings, key=lambda row: (row["task"], row["sibling_id"])), expected_siblings):
        compare_record(actual, expected, f"sibling[{expected['task']}:{expected['sibling_id']}]")

    expected_tasks = []
    for task in TASKS:
        rows = [row for row in rollouts if row["task"] == task]
        winners = []
        for replicate in (0, 1):
            block = block_groups[(task, replicate)]
            values = [row["best_within_h_dval_utility_effective"] for row in block]
            winners.append(
                "tie" if values[0] == values[1]
                else max(block, key=lambda row: row["best_within_h_dval_utility_effective"])["sibling_id"]
            )
        expected_tasks.append({
            "schema_version": SCHEMA,
            "task": task,
            "rollouts": 4,
            "replicate_winners": winners,
            "replicate_ranking_agreement": winners[0] == winners[1],
            "mean_gain_over_warm": mean([float(row["gain_over_warm_dval"]) for row in rows]),
            "positive_gain_rollouts": sum(row["gain_over_warm_dval"] > 0 for row in rows),
            "practical_gain_rollouts": sum(row["gain_exceeds_practical_delta"] for row in rows),
        })
    actual_tasks = {row["task"]: row for row in task_rows}
    for expected in expected_tasks:
        if expected["task"] not in actual_tasks:
            raise ArchiveVerificationError("task diagnostic missing")
        compare_record(actual_tasks[expected["task"]], expected, f"task[{expected['task']}]")

    expected_summary = {
        "schema_version": SCHEMA,
        "status": STATUS,
        "tasks": list(TASKS),
        "rollout_jobs": 8,
        "candidate_execution_attempts": 16,
        "candidate_processes_started": sum(row["candidate_processes_started"] for row in rollouts),
        "operator_api_calls": 8,
        "operator_retry_count": 0,
        "candidate_retry_count": 0,
        "analyze_operator_calls": 0,
        "dtest_rows_read": 0,
        "sealed_values_opened": True,
        "sealed_files_opened_after_coverage_gate": 16,
        "failure_utility": FAILURE_UTILITY,
        "practical_delta": PRACTICAL_DELTA,
        "total_candidate_wall_seconds": sum(
            sum(row["candidate_wall_time_seconds"]) for row in rollouts
        ),
        "realized_candidate_gpu_hours": sum(
            sum(row["candidate_wall_time_seconds"]) for row in rollouts
        ) / 3600,
        "rollouts_with_positive_dval_gain": sum(row["gain_over_warm_dval"] > 0 for row in rollouts),
        "rollouts_with_practical_dval_gain": sum(row["gain_exceeds_practical_delta"] for row in rollouts),
        "task_replicate_ranking_agreements": sum(
            row["replicate_ranking_agreement"] for row in expected_tasks
        ),
        "primary_gate_claim_allowed": False,
        "e2_e3_unlocked": False,
        "interpretation": "E1 is an engineering smoke and descriptive effect-size probe only",
    }
    if summary.get("coverage_gate") != {
        "all_eight_assignment_rollouts_present": True,
        "all_eight_independent_worker_receipts_present": True,
        "no_inflight_rollouts": True,
        "unique_workspace_paths": 8,
        "unique_workspace_tokens": 8,
        "candidate_execution_attempts": 16,
        "operator_calls": 8,
        "retry_count": 0,
        "dtest_rows_read": 0,
        "sealed_values_opened_before_coverage_gate": False,
    }:
        raise ArchiveVerificationError("coverage gate differs")
    if not isinstance(summary.get("source_commit"), str) or len(summary["source_commit"]) != 40:
        raise ArchiveVerificationError("source commit differs")
    for key, value in expected_summary.items():
        close(summary.get(key), value, f"summary.{key}")

    receipt = {
        "status": "VERIFIED_INDEPENDENT_E1_ARCHIVE_ANALYSIS",
        "producer_imported": False,
        "collection_sha256_manifest_verified": True,
        "rollout_rows_recomputed": 8,
        "sibling_rows_recomputed": 4,
        "task_rows_recomputed": 2,
        "summary_recomputed": True,
        "source_commit": summary["source_commit"],
        "collection_summary_sha256": sha256(result_dir / "summary.json"),
        "primary_gate_claim_allowed": False,
        "e2_e3_unlocked": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".tmp", dir=output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(receipt, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, output)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return receipt


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--result-dir", required=True, type=pathlib.Path)
    result.add_argument("--output", required=True, type=pathlib.Path)
    return result


def main() -> int:
    try:
        args = parser().parse_args()
        verify(args.result_dir, args.output)
    except (ArchiveVerificationError, OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f"VERIFY_E1_ARCHIVE_ERROR: {error}", file=os.sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
