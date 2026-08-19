"""Independently recompute every compact E2-A row and frozen support verdict."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import pathlib
import re
import tempfile
from collections import Counter, defaultdict
from typing import Any


SCHEMA = "balanced-continuation-e2a-collection-v1"
TASKS = (
    "spaceship-titanic", "tabular-playground-series-may-2022",
    "spooky-author-identification", "us-patent-phrase-to-phrase-matching",
    "nomad2018-predict-transparent-conductors",
    "learning-agency-lab-automated-essay-scoring-2",
)
METRICS = {
    TASKS[0]: ("accuracy", 1), TASKS[1]: ("roc_auc", 1),
    TASKS[2]: ("multiclass_log_loss", -1), TASKS[3]: ("pearson", 1),
    TASKS[4]: ("mean_columnwise_rmsle", -1),
    TASKS[5]: ("quadratic_weighted_kappa", 1),
}
FILES = {
    "rollouts.jsonl", "parents.jsonl", "calibration.jsonl", "tasks.jsonl",
    "summary.json", "sha256_manifest.json",
}
CREDENTIAL = re.compile(
    rb"sk-[A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{20,}|"
    rb"gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
    rb"AIza[0-9A-Za-z_-]{30,}|Bearer\s+[A-Za-z0-9._-]{24,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
)


class ArchiveError(RuntimeError):
    pass


def sha(path: pathlib.Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            result.update(block)
    return result.hexdigest()


def read_bytes(path: pathlib.Path) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise ArchiveError(f"not a regular file: {path.name}")
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise ArchiveError(f"credential-shaped bytes: {path.name}")
    return raw


def finite_tree(value: Any, where: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ArchiveError(f"non-finite number: {where}")
    if isinstance(value, dict):
        for key, child in value.items(): finite_tree(child, f"{where}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value): finite_tree(child, f"{where}[{index}]")


def read_json(path: pathlib.Path) -> dict[str, Any]:
    value = json.loads(read_bytes(path))
    if not isinstance(value, dict):
        raise ArchiveError(f"JSON root differs: {path.name}")
    finite_tree(value, path.name)
    return value


def read_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    rows = []
    for number, line in enumerate(read_bytes(path).splitlines(), 1):
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ArchiveError(f"JSONL row differs: {path.name}:{number}")
        finite_tree(value, f"{path.name}:{number}")
        rows.append(value)
    return rows


def transform(task: str, score: float | None, valid: bool) -> float:
    if not valid or score is None:
        return 0.0
    metric, _ = METRICS[task]
    if metric in {"accuracy", "roc_auc"}: value = score
    elif metric == "multiclass_log_loss": value = math.exp(-score)
    elif metric in {"pearson", "quadratic_weighted_kappa"}: value = (score + 1.0) / 2.0
    elif metric == "mean_columnwise_rmsle": value = 1.0 / (1.0 + score)
    else: raise ArchiveError("unknown metric")
    if not 0.0 <= value <= 1.0:
        raise ArchiveError("analysis utility outside [0,1]")
    return value


def close(left: Any, right: Any, where: str) -> None:
    if isinstance(left, bool) or isinstance(right, bool):
        if left is not right: raise ArchiveError(f"boolean mismatch: {where}")
    elif isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if not math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-12):
            raise ArchiveError(f"numeric mismatch: {where}")
    elif left != right:
        raise ArchiveError(f"value mismatch: {where}")


def compare(actual: dict[str, Any], expected: dict[str, Any], where: str) -> None:
    if set(actual) != set(expected):
        raise ArchiveError(f"schema mismatch: {where}")
    for key, value in expected.items(): close(actual[key], value, f"{where}.{key}")


def winner(rows: list[dict[str, Any]]) -> str | None:
    if len(rows) != 2 or len({row["sibling_id"] for row in rows}) != 2:
        raise ArchiveError("non-exact sibling block")
    left, right = rows
    a = left["continuation_dval_analysis_utility"]
    b = right["continuation_dval_analysis_utility"]
    if a == b: return None
    return left["sibling_id"] if a > b else right["sibling_id"]


def verify(result_dir: pathlib.Path, output: pathlib.Path) -> dict[str, Any]:
    root = result_dir.resolve()
    output = output.resolve()
    if not root.is_dir() or root.is_symlink() or output.exists() or output.is_symlink():
        raise ArchiveError("archive/input receipt path differs")
    if {path.name for path in root.iterdir()} != FILES:
        raise ArchiveError("archive inventory differs")
    manifest = read_json(root / "sha256_manifest.json")
    if manifest != {name: sha(root / name) for name in FILES if name != "sha256_manifest.json"}:
        raise ArchiveError("archive hash manifest differs")
    rollouts = read_jsonl(root / "rollouts.jsonl")
    parents = read_jsonl(root / "parents.jsonl")
    calibration = read_jsonl(root / "calibration.jsonl")
    task_rows = read_jsonl(root / "tasks.jsonl")
    summary = read_json(root / "summary.json")
    if (len(rollouts), len(parents), len(calibration), len(task_rows)) != (60, 24, 6, 6):
        raise ArchiveError("archive row counts differ")
    if sorted(row["global_order"] for row in rollouts) != list(range(60)):
        raise ArchiveError("rollout global order differs")
    if len({row["rollout_id"] for row in rollouts}) != 60:
        raise ArchiveError("rollout IDs repeat")
    if Counter(row["task"] for row in rollouts) != Counter({task: 10 for task in TASKS}):
        raise ArchiveError("task rollout balance differs")
    if Counter(Counter(row["sibling_id"] for row in rollouts).values()) != Counter({1: 36, 2: 12}):
        raise ArchiveError("variable-K exposure differs")

    by_anchor_rep: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for index, row in enumerate(rollouts):
        if row.get("schema_version") != SCHEMA or row.get("task") not in TASKS:
            raise ArchiveError(f"rollout identity differs: {index}")
        if row["block_replicate"] not in (0, 1):
            raise ArchiveError("block replicate differs")
        for prefix in ("warm", "continuation"):
            score = row[f"{prefix}_dval_score_raw"]
            valid = row[f"{prefix}_dval_valid"]
            expected = transform(row["task"], score, valid)
            close(row[f"{prefix}_dval_analysis_utility"], expected, f"rollout[{index}].{prefix}")
            raw_oriented = row[f"{prefix}_dval_raw_oriented_utility"]
            orientation = METRICS[row["task"]][1]
            expected_raw = None if score is None else orientation * score
            close(raw_oriented, expected_raw, f"rollout[{index}].{prefix}.raw")
        gain = (
            row["continuation_dval_analysis_utility"]
            - row["warm_dval_analysis_utility"]
        )
        close(row["continuation_minus_warm_analysis_gain"], gain, f"rollout[{index}].gain")
        walls = row["candidate_wall_time_seconds"]
        if not isinstance(walls, list) or len(walls) != 2 or any(
            isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0
            for value in walls
        ):
            raise ArchiveError("candidate wall accounting differs")
        if row["operator_api_calls"] != 1 or not isinstance(row["operator_usage"], list):
            raise ArchiveError("operator accounting differs")
        if row["continuation_dval_valid"] and row["continuation_failure_class"] != "valid":
            raise ArchiveError("valid continuation failure class differs")
        by_anchor_rep[(row["anchor_id"], row["block_replicate"])].append(row)
    if len(by_anchor_rep) != 30 or any(len(rows) != 2 for rows in by_anchor_rep.values()):
        raise ArchiveError("block coverage differs")

    expected_parents = []
    for (anchor, replicate), rows in sorted(by_anchor_rep.items()):
        if replicate != 0: continue
        expected_parents.append({
            "schema_version": SCHEMA,
            "anchor_id": anchor,
            "task": rows[0]["task"],
            "source_run_id": rows[0]["source_run_id"],
            "sibling_ids": sorted(row["sibling_id"] for row in rows),
            "winner_sibling_id": winner(rows),
            "non_tie": winner(rows) is not None,
            "both_continuations_invalid": not any(row["continuation_dval_valid"] for row in rows),
        })
    for actual, expected in zip(sorted(parents, key=lambda row: row["anchor_id"]), expected_parents):
        compare(actual, expected, f"parent[{expected['anchor_id']}]")

    calibration_anchors = sorted(anchor for anchor, rep in by_anchor_rep if rep == 1)
    expected_calibration = []
    for anchor in calibration_anchors:
        first = sorted(by_anchor_rep[(anchor, 0)], key=lambda row: row["sibling_id"])
        second = sorted(by_anchor_rep[(anchor, 1)], key=lambda row: row["sibling_id"])
        if [row["sibling_id"] for row in first] != [row["sibling_id"] for row in second]:
            raise ArchiveError("calibration sibling mismatch")
        winners = [winner(first), winner(second)]
        informative = all(value is not None for value in winners)
        expected_calibration.append({
            "schema_version": SCHEMA,
            "anchor_id": anchor,
            "task": first[0]["task"],
            "source_run_id": first[0]["source_run_id"],
            "sibling_ids": [row["sibling_id"] for row in first],
            "replicate_winners": winners,
            "informative": informative,
            "winner_consistent": informative and winners[0] == winners[1],
            "per_sibling_validity_agreement": [
                left["continuation_dval_valid"] == right["continuation_dval_valid"]
                for left, right in zip(first, second)
            ],
            "per_sibling_raw_score_absolute_difference": [
                None if left["continuation_dval_score_raw"] is None
                or right["continuation_dval_score_raw"] is None
                else abs(left["continuation_dval_score_raw"] - right["continuation_dval_score_raw"])
                for left, right in zip(first, second)
            ],
            "per_sibling_analysis_utility_absolute_difference": [
                abs(left["continuation_dval_analysis_utility"] - right["continuation_dval_analysis_utility"])
                for left, right in zip(first, second)
            ],
        })
    for actual, expected in zip(sorted(calibration, key=lambda row: row["anchor_id"]), expected_calibration):
        compare(actual, expected, f"calibration[{expected['anchor_id']}]")

    expected_tasks = []
    for task in TASKS:
        broad = [row for row in rollouts if row["task"] == task and row["block_replicate"] == 0]
        task_parents = [row for row in expected_parents if row["task"] == task]
        valid_values = [
            row["continuation_dval_analysis_utility"]
            for row in broad if row["continuation_dval_valid"]
        ]
        valid_count = len(valid_values)
        expected_tasks.append({
            "schema_version": SCHEMA,
            "task": task,
            "broad_rollouts": 8,
            "broad_parents": 4,
            "non_tie_parent_count": sum(row["non_tie"] for row in task_parents),
            "valid_continuation_count": valid_count,
            "nonvalid_continuation_count": 8 - valid_count,
            "has_valid_and_nonvalid_continuations": 0 < valid_count < 8,
            "all_broad_continuations_valid": valid_count == 8,
            "valid_conditional_utility_has_variation": (
                len(valid_values) >= 2 and max(valid_values) > min(valid_values)
            ),
            "continuation_failure_classes": dict(sorted(Counter(
                row["continuation_failure_class"] for row in broad
            ).items())),
        })
    actual_tasks = {row["task"]: row for row in task_rows}
    for expected in expected_tasks:
        compare(actual_tasks[expected["task"]], expected, f"task[{expected['task']}]")

    total_wall = sum(sum(row["candidate_wall_time_seconds"]) for row in rollouts)
    gpu_hours = total_wall / 3600.0
    artifact_rate = sum(row["continuation_artifact_present"] for row in rollouts) / 60
    informative = sum(row["informative"] for row in expected_calibration)
    consistent = sum(row["winner_consistent"] for row in expected_calibration)
    tasks_nontie = sum(row["non_tie_parent_count"] >= 3 for row in expected_tasks)
    mixed = sum(row["has_valid_and_nonvalid_continuations"] for row in expected_tasks)
    varying = sum(row["valid_conditional_utility_has_variation"] for row in expected_tasks)
    all_valid = sum(row["all_broad_continuations_valid"] for row in expected_tasks)
    components = {
        "calibration_informative_at_least_5_of_6": informative >= 5,
        "calibration_winner_consistent_at_least_4_of_6": consistent >= 4,
        "tasks_with_at_least_3_non_tie_parents_at_least_4_of_6": tasks_nontie >= 4,
        "realized_candidate_gpu_hours_at_most_12_5": gpu_hours <= 12.5,
        "continuation_terminal_artifact_rate_at_least_0_50": artifact_rate >= 0.5,
    }
    label = all(components.values())
    hurdle = label and mixed >= 4 and varying >= 4
    quality = label and not hurdle and all_valid >= 4 and varying >= 4
    verdict = (
        "HURDLE_SUPPORT" if hurdle else "QUALITY_ONLY_SUPPORT" if quality
        else "LABEL_RESOURCE_SUPPORT_WITHOUT_METHOD_ROUTE" if label else "KILL"
    )
    expected_dynamic = {
        "verdict": verdict,
        "realized_candidate_gpu_hours": gpu_hours,
        "continuation_terminal_artifact_rate": artifact_rate,
        "calibration_informative_parents": informative,
        "calibration_winner_consistent_parents": consistent,
        "tasks_with_at_least_3_non_tie_parents": tasks_nontie,
        "tasks_with_valid_and_nonvalid_continuations": mixed,
        "tasks_with_valid_conditional_utility_variation": varying,
        "tasks_with_all_broad_continuations_valid": all_valid,
        "label_resource_gate_components": components,
        "label_resource_support": label,
        "hurdle_support": hurdle,
        "quality_only_support": quality,
        "e2b_requires_separate_preregistration": label,
    }
    fixed = {
        "schema_version": SCHEMA,
        "status": "VERIFIED_COMPLETE_REAL_E2A_COLLECTION",
        "tasks": list(TASKS),
        "gate_population": "broad_replicate_0_parent_balanced",
        "rollout_jobs": 60,
        "candidate_execution_attempts": 120,
        "operator_api_calls": 60,
        "operator_retry_count": 0,
        "candidate_retry_count": 0,
        "analyze_operator_calls": 0,
        "dtest_rows_read": 0,
        "sealed_values_opened": True,
        "sealed_files_opened_after_coverage_gate": 120,
        "post_outcome_replacement_count": 0,
        "primary_method_claim_allowed": False,
        "quality_only_operationalization": (
            "label gate passes, hurdle fails, at least four tasks have all broad "
            "continuations valid, and at least four tasks retain conditional variation"
        ),
    }
    for key, value in {**fixed, **expected_dynamic}.items():
        close(summary.get(key), value, f"summary.{key}")
    if not isinstance(summary.get("source_commit"), str) or len(summary["source_commit"]) != 40:
        raise ArchiveError("source commit differs")
    if summary.get("candidate_processes_started") != sum(
        row["candidate_processes_started"] for row in rollouts
    ):
        raise ArchiveError("candidate process summary differs")
    if summary.get("coverage_gate") != {
        "all_60_assignment_rollouts_present": True,
        "all_60_independent_worker_receipts_present": True,
        "no_inflight_rollouts": True,
        "unique_workspace_paths": 60,
        "unique_workspace_tokens": 60,
        "candidate_execution_attempts": 120,
        "operator_calls": 60,
        "retry_count": 0,
        "dtest_rows_read": 0,
        "sealed_values_opened_before_coverage_gate": False,
    }:
        raise ArchiveError("coverage gate differs")
    receipt = {
        "status": "VERIFIED_INDEPENDENT_E2A_ARCHIVE_AND_GATES",
        "producer_imported": False,
        "rollout_rows_recomputed": 60,
        "parent_rows_recomputed": 24,
        "calibration_rows_recomputed": 6,
        "task_rows_recomputed": 6,
        "summary_and_verdict_recomputed": True,
        "verdict": verdict,
        "source_commit": summary["source_commit"],
        "collection_summary_sha256": sha(root / "summary.json"),
        "primary_method_claim_allowed": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".tmp", dir=output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(receipt, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, output)
    finally:
        if os.path.exists(name): os.unlink(name)
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-dir", required=True, type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    try:
        verify(**vars(parser.parse_args()))
    except (ArchiveError, OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"VERIFY_E2A_ARCHIVE_ERROR: {exc}", file=os.sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
