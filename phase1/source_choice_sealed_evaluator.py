#!/usr/bin/env python3
"""Aggregate-only evaluator for sealed source-choice winner labels."""

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


GROUP_SCHEMA = "source-choice-group-v1"
LABEL_SCHEMA = "source-choice-label-vault-v1"
PREDICTION_SCHEMA = "source-choice-selection-v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class EvaluationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def rows(path: Path, where: str) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise EvaluationError(f"invalid JSONL: {where}:{number}") from exc
            if not isinstance(value, dict) or canonical(value) + b"\n" != line.encode("utf-8"):
                raise EvaluationError(f"non-canonical object: {where}:{number}")
            output.append(value)
    if not output:
        raise EvaluationError(f"empty input: {where}")
    return output


def require_hash(value: str, where: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise EvaluationError(f"invalid SHA-256: {where}")
    return value


def evaluate(arguments: argparse.Namespace) -> dict[str, Any]:
    input_path = Path(arguments.inputs).resolve()
    prediction_path = Path(arguments.predictions).resolve()
    vault_path = Path(arguments.vault).resolve()
    for path in (input_path, prediction_path, vault_path):
        if not path.is_file():
            raise EvaluationError(f"missing evaluator input: {path.name}")
    expected_input = require_hash(arguments.expected_input_sha256, "inputs")
    expected_vault = require_hash(arguments.expected_vault_sha256, "vault")
    if sha256(input_path) != expected_input or sha256(vault_path) != expected_vault:
        raise EvaluationError("sealed evaluator hash binding failed")

    groups: dict[str, dict[str, Any]] = {}
    for number, group in enumerate(rows(input_path, "groups"), 1):
        if group.get("schema_version") != GROUP_SCHEMA or group.get("role") not in {
            "frozen", "extension"
        }:
            raise EvaluationError(f"group schema/role invalid: {number}")
        if "winner_candidate_sha256" in group:
            raise EvaluationError("public evaluator input contains winner label")
        group_id = require_hash(group.get("group_id"), f"group {number}")
        candidates = group.get("candidates")
        if not isinstance(candidates, list) or len(candidates) < 2:
            raise EvaluationError(f"candidate set invalid: {number}")
        candidate_ids = [require_hash(row.get("candidate_id_sha256"), "candidate") for row in candidates]
        if candidate_ids != sorted(candidate_ids) or len(candidate_ids) != len(set(candidate_ids)):
            raise EvaluationError(f"candidate order/identity invalid: {number}")
        if group_id in groups:
            raise EvaluationError("duplicate group")
        groups[group_id] = {
            "task": group.get("task"),
            "run_id_sha256": require_hash(group.get("run_id_sha256"), "run"),
            "candidate_ids": set(candidate_ids),
        }

    labels: dict[str, str] = {}
    for number, label in enumerate(rows(vault_path, "vault"), 1):
        if label.get("schema_version") != LABEL_SCHEMA:
            raise EvaluationError(f"vault schema invalid: {number}")
        group_id = require_hash(label.get("group_id"), f"vault group {number}")
        winner = require_hash(label.get("winner_candidate_sha256"), f"vault winner {number}")
        group = groups.get(group_id)
        if (
            group is None
            or group_id in labels
            or label.get("task") != group["task"]
            or label.get("run_id_sha256") != group["run_id_sha256"]
            or winner not in group["candidate_ids"]
        ):
            raise EvaluationError(f"vault/group closure invalid: {number}")
        labels[group_id] = winner
    if set(labels) != set(groups):
        raise EvaluationError("vault does not exactly cover public groups")

    predictions: dict[str, str] = {}
    for number, prediction in enumerate(rows(prediction_path, "predictions"), 1):
        if prediction.get("schema_version") != PREDICTION_SCHEMA or set(prediction) != {
            "schema_version", "group_id", "selected_candidate_sha256"
        }:
            raise EvaluationError(f"prediction schema invalid: {number}")
        group_id = require_hash(prediction.get("group_id"), f"prediction group {number}")
        selected = require_hash(
            prediction.get("selected_candidate_sha256"), f"prediction candidate {number}"
        )
        if group_id not in groups or group_id in predictions or selected not in groups[group_id]["candidate_ids"]:
            raise EvaluationError(f"prediction closure invalid: {number}")
        predictions[group_id] = selected
    if set(predictions) != set(groups):
        raise EvaluationError("predictions do not exactly cover groups")

    task_hits: collections.Counter[str] = collections.Counter()
    task_totals: collections.Counter[str] = collections.Counter()
    run_hits: collections.Counter[str] = collections.Counter()
    run_totals: collections.Counter[str] = collections.Counter()
    for group_id in sorted(groups):
        task = groups[group_id]["task"]
        run = groups[group_id]["run_id_sha256"]
        if not isinstance(task, str) or not task:
            raise EvaluationError("group task invalid")
        hit = int(predictions[group_id] == labels[group_id])
        task_hits[task] += hit
        task_totals[task] += 1
        run_hits[run] += hit
        run_totals[run] += 1
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
    task_macro = sum(row["accuracy"] for row in per_task.values()) / len(per_task)
    run_accuracies = [run_hits[run] / run_totals[run] for run in run_totals]
    if not math.isfinite(task_macro) or any(not math.isfinite(value) for value in run_accuracies):
        raise EvaluationError("non-finite aggregate")
    return {
        "protocol": "source-choice-sealed-evaluator-v1",
        "status": "SOURCE_CHOICE_SEALED_EVALUATION_COMPLETE",
        "input_sha256": expected_input,
        "prediction_sha256": sha256(prediction_path),
        "vault_sha256_opaque": expected_vault,
        "groups": total,
        "tasks": len(per_task),
        "runs": len(run_totals),
        "hits": hits,
        "accuracy": hits / total,
        "task_macro_accuracy": task_macro,
        "run_macro_accuracy": sum(run_accuracies) / len(run_accuracies),
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
    value.add_argument("--predictions", required=True)
    value.add_argument("--vault", required=True)
    value.add_argument("--expected-input-sha256", required=True)
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
        print(f"SOURCE_CHOICE_SEALED_EVALUATOR_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
