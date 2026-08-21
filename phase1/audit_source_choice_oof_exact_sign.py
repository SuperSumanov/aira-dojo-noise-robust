#!/usr/bin/env python3
"""Recompute OOF task sign tests with exact rational arithmetic."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import os
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any


class ExactSignError(RuntimeError):
    pass


def need(condition: bool, message: str) -> None:
    if not condition:
        raise ExactSignError(message)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def object_json(path: Path, where: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExactSignError(f"invalid JSON: {where}") from exc
    need(isinstance(value, dict), f"non-object JSON: {where}")
    return value


def exact_sign(values: list[Fraction]) -> dict[str, Any]:
    positive = sum(value > 0 for value in values)
    negative = sum(value < 0 for value in values)
    zero = sum(value == 0 for value in values)
    n = positive + negative
    numerator = 2 ** n if n == 0 else sum(math.comb(n, item) for item in range(positive, n + 1))
    denominator = 2 ** n
    return {
        "positive": positive,
        "negative": negative,
        "zero": zero,
        "one_sided_p": numerator / denominator,
        "one_sided_p_exact": f"{numerator}/{denominator}",
    }


def audit(summary_path: Path, predictions_path: Path) -> dict[str, Any]:
    summary = object_json(summary_path, "OOF summary")
    need(
        summary.get("protocol") == "source-choice-oof-tfidf-v1"
        and summary.get("status") == "SOURCE_CHOICE_OOF_TFIDF_COMPLETE",
        "OOF summary semantics differ",
    )
    need(
        summary.get("outputs", {}).get("predictions.csv") == digest(predictions_path),
        "prediction receipt differs",
    )
    expected_fields = {
        "split", "fold", "arm", "group_id", "task", "run_id_sha256", "source_size",
        "selected_candidate_sha256", "hit", "winner_rank",
    }
    task_terms: dict[str, dict[str, list[Fraction]]] = {
        "task_loto": collections.defaultdict(list),
        "run_grouped_5fold": collections.defaultdict(list),
    }
    group_ids: dict[str, set[str]] = {key: set() for key in task_terms}
    with predictions_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        need(set(reader.fieldnames or []) == expected_fields, "prediction fields differ")
        for row in reader:
            if row["arm"] != "tfidf_pairwise_lr":
                continue
            split = row["split"]
            need(split in task_terms, "prediction split differs")
            group_id = row["group_id"]
            need(group_id not in group_ids[split], "duplicate TF-IDF prediction")
            group_ids[split].add(group_id)
            hit = int(row["hit"])
            source_size = int(row["source_size"])
            need(hit in {0, 1} and source_size >= 2, "prediction value differs")
            task_terms[split][row["task"]].append(
                Fraction(hit, 1) - Fraction(1, source_size)
            )
    expected_groups = summary["census"]["groups"]
    need(all(len(values) == expected_groups for values in group_ids.values()), "prediction coverage differs")

    split_audits: dict[str, Any] = {}
    for split in task_terms:
        exact_task_points = [
            sum(task_terms[split][task], Fraction(0, 1)) / len(task_terms[split][task])
            for task in sorted(task_terms[split])
        ]
        exact = exact_sign(exact_task_points)
        reported = summary["metrics"][split]["tfidf_pairwise_lr"]["task_sign"]
        split_audits[split] = {
            "tasks": len(exact_task_points),
            "mathematical_exact_zero_tasks": exact["zero"],
            "reported": reported,
            "exact": exact,
            "counts_match": all(reported[key] == exact[key] for key in ("positive", "negative", "zero")),
            "p_matches_within_1e_15": math.isclose(
                float(reported["one_sided_p"]), float(exact["one_sided_p"]),
                rel_tol=0, abs_tol=1e-15,
            ),
        }

    gate = summary["gate"]
    cross = summary["metrics"]["task_loto"]["tfidf_pairwise_lr"]
    run = summary["metrics"]["run_grouped_5fold"]["tfidf_pairwise_lr"]
    threshold = gate["minimum_absolute_task_macro_delta"]
    exact_cross_pass = (
        cross["task_macro_delta"] >= threshold
        and cross["task_clustered_delta"]["ci95"][0] > 0
        and split_audits["task_loto"]["exact"]["one_sided_p"]
        < gate["maximum_one_sided_task_sign_p"]
    )
    run_pass = (
        run["task_macro_delta"] >= threshold
        and run["task_clustered_delta"]["ci95"][0] > 0
        and run["run_clustered_micro_delta"]["ci95"][0] > 0
    )
    exact_verdict = (
        "GO_CROSS_TASK" if exact_cross_pass
        else "GO_RUN_ONLY" if run_pass
        else "NO_NARROW_POSITIVE"
    )
    return {
        "protocol": "source-choice-oof-exact-sign-audit-v1",
        "status": "SOURCE_CHOICE_OOF_EXACT_SIGN_AUDIT_COMPLETE",
        "summary_sha256": digest(summary_path),
        "predictions_sha256": digest(predictions_path),
        "split_audits": split_audits,
        "reported_verdict": summary["verdict"],
        "exact_sign_verdict": exact_verdict,
        "verdict_unchanged": summary["verdict"] == exact_verdict,
        "model_refit": False,
        "frozen_or_extension_model_read": False,
        "frozen_or_extension_label_vault_read": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = audit(Path(args.summary).resolve(), Path(args.predictions).resolve())
        output = Path(args.output).resolve()
        need(not output.exists(), "output exists")
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_bytes(json.dumps(result, indent=2, sort_keys=True).encode() + b"\n")
        os.replace(temporary, output)
        print(
            f"{result['status']} reported={result['reported_verdict']} "
            f"exact={result['exact_sign_verdict']}"
        )
        return 0
    except (ExactSignError, OSError, ValueError) as exc:
        print(f"SOURCE_CHOICE_OOF_EXACT_SIGN_AUDIT_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
