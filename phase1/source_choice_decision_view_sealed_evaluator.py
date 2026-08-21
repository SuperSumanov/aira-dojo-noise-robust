#!/usr/bin/env python3
"""Aggregate-only evaluator for the sanitized source-choice decision view."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any


MODEL_SCHEMA = "source-choice-decision-group-v1"
CLUSTER_SCHEMA = "source-choice-cluster-manifest-v1"
LABEL_SCHEMA = "source-choice-label-vault-v2"
PREDICTION_SCHEMA = "source-choice-selection-v1"
MODEL_GROUP_FIELDS = {"schema_version", "group_id", "task", "source_size", "candidates"}
MODEL_CANDIDATE_FIELDS = {
    "candidate_id_sha256",
    "code",
    "code_sha256",
    "operator",
    "step",
    "depth",
}
CLUSTER_FIELDS = {
    "schema_version",
    "group_id",
    "role",
    "task",
    "run_id_sha256",
    "parent_id_sha256",
    "source_size",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class EvaluationError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def file_hash(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def require_hash(value: Any, where: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise EvaluationError(f"invalid SHA-256: {where}")
    return value


def rows(path: Path, where: str) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    with path.open("rb") as handle:
        for number, line in enumerate(handle, 1):
            if not line.endswith(b"\n"):
                raise EvaluationError(f"unterminated JSONL: {where}:{number}")
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise EvaluationError(f"invalid JSONL: {where}:{number}") from exc
            if not isinstance(value, dict) or canonical(value) + b"\n" != line:
                raise EvaluationError(f"non-canonical object: {where}:{number}")
            output.append(value)
    if not output:
        raise EvaluationError(f"empty input: {where}")
    return output


def bound_path(raw: str, expected: str, where: str) -> Path:
    path = Path(raw).resolve()
    if not path.is_file() or file_hash(path) != require_hash(expected, where):
        raise EvaluationError(f"hash binding failed: {where}")
    return path


def evaluate(arguments: argparse.Namespace) -> dict[str, Any]:
    input_path = bound_path(arguments.inputs, arguments.expected_input_sha256, "inputs")
    cluster_path = bound_path(
        arguments.cluster_manifest,
        arguments.expected_cluster_manifest_sha256,
        "cluster manifest",
    )
    vault_path = bound_path(arguments.vault, arguments.expected_vault_sha256, "vault")
    prediction_path = Path(arguments.predictions).resolve()
    if not prediction_path.is_file():
        raise EvaluationError("prediction file missing")

    groups: dict[str, dict[str, Any]] = {}
    all_candidate_ids: set[str] = set()
    for number, group in enumerate(rows(input_path, "groups"), 1):
        if set(group) != MODEL_GROUP_FIELDS or group.get("schema_version") != MODEL_SCHEMA:
            raise EvaluationError(f"model group exact fields/schema invalid: {number}")
        group_id = require_hash(group.get("group_id"), f"group {number}")
        task = group.get("task")
        source_size = group.get("source_size")
        candidates = group.get("candidates")
        if (
            group_id in groups
            or not isinstance(task, str)
            or not task
            or isinstance(source_size, bool)
            or not isinstance(source_size, int)
            or source_size < 2
            or not isinstance(candidates, list)
            or len(candidates) != source_size
        ):
            raise EvaluationError(f"model group invalid: {number}")
        candidate_ids: list[str] = []
        for candidate_number, candidate in enumerate(candidates, 1):
            if not isinstance(candidate, dict) or set(candidate) != MODEL_CANDIDATE_FIELDS:
                raise EvaluationError(
                    f"model candidate exact fields invalid: {number}:{candidate_number}"
                )
            candidate_id = require_hash(candidate.get("candidate_id_sha256"), "candidate")
            code = candidate.get("code")
            code_hash = require_hash(candidate.get("code_sha256"), "code")
            operator = candidate.get("operator")
            step = candidate.get("step")
            depth = candidate.get("depth")
            if (
                not isinstance(code, str)
                or not code
                or hashlib.sha256(code.encode("utf-8")).hexdigest() != code_hash
                or not isinstance(operator, str)
                or not operator
                or isinstance(step, bool)
                or not isinstance(step, int)
                or isinstance(depth, bool)
                or not isinstance(depth, int)
                or candidate_id in all_candidate_ids
            ):
                raise EvaluationError(f"model candidate code invalid: {number}:{candidate_number}")
            all_candidate_ids.add(candidate_id)
            candidate_ids.append(candidate_id)
        if candidate_ids != sorted(candidate_ids) or len(candidate_ids) != len(set(candidate_ids)):
            raise EvaluationError(f"candidate order/identity invalid: {number}")
        groups[group_id] = {
            "task": task,
            "source_size": source_size,
            "candidate_ids": set(candidate_ids),
        }

    clusters: dict[str, dict[str, Any]] = {}
    for number, cluster in enumerate(rows(cluster_path, "cluster manifest"), 1):
        if set(cluster) != CLUSTER_FIELDS or cluster.get("schema_version") != CLUSTER_SCHEMA:
            raise EvaluationError(f"cluster exact fields/schema invalid: {number}")
        group_id = require_hash(cluster.get("group_id"), "cluster group")
        if group_id in clusters:
            raise EvaluationError("duplicate cluster group")
        clusters[group_id] = cluster
    selected_clusters: dict[str, dict[str, Any]] = {}
    selected_roles: set[str] = set()
    for group_id, group in groups.items():
        cluster = clusters.get(group_id)
        if (
            cluster is None
            or cluster.get("role") not in {"frozen", "extension"}
            or cluster.get("task") != group["task"]
            or cluster.get("source_size") != group["source_size"]
        ):
            raise EvaluationError("group/cluster closure invalid")
        require_hash(cluster.get("run_id_sha256"), "cluster run")
        require_hash(cluster.get("parent_id_sha256"), "cluster parent")
        selected_clusters[group_id] = cluster
        selected_roles.add(cluster["role"])
    if len(selected_roles) != 1:
        raise EvaluationError("evaluation input mixes roles")

    labels: dict[str, str] = {}
    for number, label in enumerate(rows(vault_path, "vault"), 1):
        if set(label) != {
            "schema_version",
            "group_id",
            "task",
            "run_id_sha256",
            "winner_candidate_sha256",
        } or label.get("schema_version") != LABEL_SCHEMA:
            raise EvaluationError(f"vault schema invalid: {number}")
        group_id = require_hash(label.get("group_id"), "vault group")
        winner = require_hash(label.get("winner_candidate_sha256"), "vault winner")
        group = groups.get(group_id)
        cluster = selected_clusters.get(group_id)
        if (
            group is None
            or cluster is None
            or group_id in labels
            or label.get("task") != group["task"]
            or label.get("run_id_sha256") != cluster["run_id_sha256"]
            or winner not in group["candidate_ids"]
        ):
            raise EvaluationError(f"vault/group closure invalid: {number}")
        labels[group_id] = winner
    if set(labels) != set(groups):
        raise EvaluationError("vault coverage differs")

    predictions: dict[str, str] = {}
    for number, prediction in enumerate(rows(prediction_path, "predictions"), 1):
        if set(prediction) != {
            "schema_version",
            "group_id",
            "selected_candidate_sha256",
        } or prediction.get("schema_version") != PREDICTION_SCHEMA:
            raise EvaluationError(f"prediction schema invalid: {number}")
        group_id = require_hash(prediction.get("group_id"), "prediction group")
        selected = require_hash(prediction.get("selected_candidate_sha256"), "prediction")
        if (
            group_id not in groups
            or group_id in predictions
            or selected not in groups[group_id]["candidate_ids"]
        ):
            raise EvaluationError(f"prediction closure invalid: {number}")
        predictions[group_id] = selected
    if set(predictions) != set(groups):
        raise EvaluationError("prediction coverage differs")

    task_hits: collections.Counter[str] = collections.Counter()
    task_totals: collections.Counter[str] = collections.Counter()
    run_hits: collections.Counter[str] = collections.Counter()
    run_totals: collections.Counter[str] = collections.Counter()
    chance_sum = 0.0
    for group_id in sorted(groups):
        task = groups[group_id]["task"]
        run = selected_clusters[group_id]["run_id_sha256"]
        hit = int(predictions[group_id] == labels[group_id])
        task_hits[task] += hit
        task_totals[task] += 1
        run_hits[run] += hit
        run_totals[run] += 1
        chance_sum += 1.0 / groups[group_id]["source_size"]
    total = len(groups)
    hits = sum(task_hits.values())
    per_task = {
        task: {
            "groups": task_totals[task],
            "hits": task_hits[task],
            "accuracy": task_hits[task] / task_totals[task],
        }
        for task in sorted(task_totals)
    }
    task_macro = sum(value["accuracy"] for value in per_task.values()) / len(per_task)
    run_values = [run_hits[run] / run_totals[run] for run in run_totals]
    metrics = [hits / total, task_macro, sum(run_values) / len(run_values), chance_sum / total]
    if any(not math.isfinite(value) for value in metrics):
        raise EvaluationError("non-finite aggregate")
    return {
        "protocol": "source-choice-decision-view-sealed-evaluator-v1",
        "status": "SOURCE_CHOICE_DECISION_VIEW_SEALED_EVALUATION_COMPLETE",
        "role": next(iter(selected_roles)),
        "input_sha256": arguments.expected_input_sha256,
        "cluster_manifest_sha256": arguments.expected_cluster_manifest_sha256,
        "prediction_sha256": file_hash(prediction_path),
        "vault_sha256_opaque": arguments.expected_vault_sha256,
        "groups": total,
        "tasks": len(per_task),
        "runs": len(run_totals),
        "hits": hits,
        "accuracy": hits / total,
        "uniform_expected_accuracy": chance_sum / total,
        "task_macro_accuracy": task_macro,
        "run_macro_accuracy": sum(run_values) / len(run_values),
        "per_task": per_task,
        "per_group_truth_emitted": False,
        "winner_candidate_ids_emitted": False,
    }


def atomic_json(path: Path, value: Any) -> None:
    if path.exists():
        raise EvaluationError("evaluation output already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode() + b"\n")
    os.replace(temporary, path)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--inputs", required=True)
    value.add_argument("--cluster-manifest", required=True)
    value.add_argument("--predictions", required=True)
    value.add_argument("--vault", required=True)
    value.add_argument("--expected-input-sha256", required=True)
    value.add_argument("--expected-cluster-manifest-sha256", required=True)
    value.add_argument("--expected-vault-sha256", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        arguments = parser().parse_args()
        result = evaluate(arguments)
        atomic_json(Path(arguments.output).resolve(), result)
        print(result["status"])
        return 0
    except EvaluationError as exc:
        print(f"SOURCE_CHOICE_DECISION_VIEW_EVALUATOR_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
