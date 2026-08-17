#!/usr/bin/env python3
"""Task-held-out static controller for parent-matched execution-failure risk."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from phase1.audit_failure_risk_pair_support import (
    SupportError,
    card_parent,
    load_failures,
    locked,
    parse_roots,
    rows,
    task_name,
)
from phase1.source_opportunity_journal_status import (
    CREDENTIAL,
    canonical_journals,
    decode_journal,
    node_card_id,
    sha256_bytes,
    sha256_file,
)


PROTOCOL = "failure-risk-controller-loto-v1"
SEED = 20260817
BOOTSTRAPS = 10_000
MAX_CODE_CHARS = 20_000
SUPPORT_SHA = "77b81f8d4356d74f14647c8a12281af201fe34c75da04ed077febdac17b400f1"


class ControllerError(RuntimeError):
    pass


def truncate_code(code: str) -> str:
    if len(code) <= MAX_CODE_CHARS:
        return code
    return code[:5_000] + code[-15_000:]


def load_support(path: Path) -> dict[str, Any]:
    if not path.is_file() or sha256_file(path) != SUPPORT_SHA:
        raise ControllerError("locked support artifact mismatch")
    value = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "status": "VERIFIED_FAILURE_RISK_PAIR_SUPPORT",
        "eligible_parent_matched_pairs": 494,
        "tasks": 13,
        "physical_runs": 126,
        "frozen_run_overlap": 0,
        "failure_risk_controller_support_claim_allowed": True,
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise ControllerError(f"support contract mismatch for {key}")
    return value


def scan_failure_codes(roots: dict[str, Path], failures: dict[str, dict[str, Any]]) -> dict[str, str]:
    targets_by_sha: dict[str, set[str]] = collections.defaultdict(set)
    for child, row in failures.items():
        targets_by_sha[row["source_journal_sha256"]].add(child)
    codes: dict[str, str] = {}
    credential_shas: set[str] = set()
    seen_shas: set[str] = set()
    for root in roots.values():
        for journal in canonical_journals(root):
            blob = journal.read_bytes()
            journal_sha = sha256_bytes(blob)
            if journal_sha not in targets_by_sha:
                continue
            seen_shas.add(journal_sha)
            if CREDENTIAL.search(blob):
                credential_shas.add(journal_sha)
                continue
            task, nodes = decode_journal(blob, journal_sha)
            wanted = targets_by_sha[journal_sha]
            for node in nodes:
                child = node_card_id(task, node)
                if child not in wanted:
                    continue
                code = node.get("code")
                code = code if isinstance(code, str) else ""
                prior = codes.get(child)
                if prior is not None and prior != code:
                    raise ControllerError(f"conflicting code copies for {child}")
                codes[child] = code
    if credential_shas:
        raise ControllerError("credential-shaped target journals are forbidden")
    if len(seen_shas) != len(targets_by_sha) or len(codes) != len(failures):
        raise ControllerError("failure code refind contract changed")
    return codes


def build_pairs(args: argparse.Namespace) -> list[dict[str, str]]:
    cards_path = locked(args.cards, args.expect_cards_sha256)
    status_path = locked(args.status_per_child, args.expect_status_sha256)
    taxonomy_path = locked(args.taxonomy_per_child, args.expect_taxonomy_sha256)
    pair_paths = [locked(value, digest) for value, digest in zip(args.pair, args.expect_pair_sha256, strict=True)]
    cards = {str(row["id"]): row for row in rows(cards_path)}
    frozen_runs = set()
    for path in pair_paths:
        for row in rows(path):
            if row.get("intask_split") != "test":
                raise ControllerError("frozen pair input contains non-test row")
            for key in ("better", "worse"):
                card = cards.get(str(row.get(key)))
                if card is None:
                    raise ControllerError("frozen endpoint absent from cards")
                frozen_runs.add(str(card.get("run_id")))
    failures = load_failures(status_path, taxonomy_path, 691)
    codes = scan_failure_codes(parse_roots(args.root), failures)

    retained_by_parent: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for card in cards.values():
        parent = card_parent(card)
        code = card.get("code")
        if parent and isinstance(code, str) and code.strip():
            retained_by_parent[parent].append(card)
    for values in retained_by_parent.values():
        values.sort(key=lambda card: str(card["id"]))
    failures_by_parent: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for child, row in failures.items():
        code = codes[child]
        if code.strip():
            failures_by_parent[row["parent_id"]].append({**row, "code": code})
    for values in failures_by_parent.values():
        values.sort(key=lambda row: row["child_id"])

    pairs = []
    for parent_id in sorted(set(failures_by_parent) & set(retained_by_parent)):
        parent_card = cards.get(parent_id)
        if parent_card is None:
            continue
        run_id = str(parent_card.get("run_id"))
        if run_id in frozen_runs:
            continue
        failure = failures_by_parent[parent_id][0]
        failure_sha = sha256_bytes(failure["code"].encode("utf-8"))
        retained = [
            card
            for card in retained_by_parent[parent_id]
            if str(card.get("run_id")) == run_id
            and sha256_bytes(str(card.get("code") or "").encode("utf-8")) != failure_sha
        ]
        if not retained:
            continue
        success = retained[0]
        pairs.append(
            {
                "task": task_name(parent_card),
                "run_id": run_id,
                "failure_code": truncate_code(failure["code"]),
                "success_code": truncate_code(str(success["code"])),
            }
        )
    if len(pairs) != 494 or len({row["task"] for row in pairs}) != 13 or len({row["run_id"] for row in pairs}) != 126:
        raise ControllerError("reconstructed pair support differs from the locked audit")
    return pairs


def credit(success_score: float, failure_score: float) -> float:
    if success_score > failure_score:
        return 1.0
    if success_score < failure_score:
        return 0.0
    return 0.5


def fit_scores(train: list[dict[str, str]], test: list[dict[str, str]]) -> tuple[np.ndarray, np.ndarray]:
    train_docs = [row["success_code"] for row in train] + [row["failure_code"] for row in train]
    train_y = np.array([1] * len(train) + [0] * len(train), dtype=np.int8)
    test_docs = [row["success_code"] for row in test] + [row["failure_code"] for row in test]

    vectorizer = TfidfVectorizer(
        analyzer="char",
        ngram_range=(3, 5),
        min_df=2,
        max_features=50_000,
        sublinear_tf=True,
        lowercase=False,
        dtype=np.float32,
    )
    train_matrix = vectorizer.fit_transform(train_docs)
    test_matrix = vectorizer.transform(test_docs)
    model = LogisticRegression(
        C=1.0,
        class_weight="balanced",
        max_iter=1_000,
        random_state=SEED,
        solver="liblinear",
    )
    model.fit(train_matrix, train_y)
    tfidf_scores = model.predict_proba(test_matrix)[:, 1]

    train_lengths = np.log1p(np.array([len(value) for value in train_docs], dtype=np.float64)).reshape(-1, 1)
    test_lengths = np.log1p(np.array([len(value) for value in test_docs], dtype=np.float64)).reshape(-1, 1)
    length_model = LogisticRegression(C=1.0, class_weight="balanced", max_iter=1_000, random_state=SEED, solver="liblinear")
    length_model.fit(train_lengths, train_y)
    length_scores = length_model.predict_proba(test_lengths)[:, 1]
    return tfidf_scores, length_scores


def evaluate_pairs(pairs: list[dict[str, str]]) -> list[dict[str, Any]]:
    tasks = sorted({row["task"] for row in pairs})
    results = []
    for task in tasks:
        train = [row for row in pairs if row["task"] != task]
        test = [row for row in pairs if row["task"] == task]
        if not train or not test or {row["run_id"] for row in train} & {row["run_id"] for row in test}:
            raise ControllerError("LOTO split is empty or has run overlap")
        tfidf_scores, length_scores = fit_scores(train, test)
        count = len(test)
        for index, row in enumerate(test):
            results.append(
                {
                    "task": task,
                    "run_id": row["run_id"],
                    "tfidf_credit": credit(tfidf_scores[index], tfidf_scores[count + index]),
                    "length_credit": credit(length_scores[index], length_scores[count + index]),
                }
            )
    return results


def clustered_ci(results: list[dict[str, Any]], cluster_key: str, value_key: str) -> tuple[float, float]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row in results:
        grouped[str(row[cluster_key])].append(float(row[value_key]))
    keys = sorted(grouped)
    rng = np.random.default_rng(SEED)
    values = np.empty(BOOTSTRAPS, dtype=np.float64)
    for index in range(BOOTSTRAPS):
        sampled = rng.choice(keys, size=len(keys), replace=True)
        draw = [item for key in sampled for item in grouped[str(key)]]
        values[index] = np.mean(draw)
    return float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    tfidf = [row["tfidf_credit"] for row in results]
    length = [row["length_credit"] for row in results]
    differences = [left - right for left, right in zip(tfidf, length, strict=True)]
    enriched = [
        {**row, "difference": difference}
        for row, difference in zip(results, differences, strict=True)
    ]
    per_task = {}
    for task in sorted({row["task"] for row in results}):
        subset = [row for row in results if row["task"] == task]
        per_task[task] = {
            "pairs": len(subset),
            "tfidf_accuracy": float(np.mean([row["tfidf_credit"] for row in subset])),
            "length_accuracy": float(np.mean([row["length_credit"] for row in subset])),
        }
    tfidf_ci = clustered_ci(results, "task", "tfidf_credit")
    length_ci = clustered_ci(results, "task", "length_credit")
    difference_ci = clustered_ci(enriched, "task", "difference")
    run_tfidf_ci = clustered_ci(results, "run_id", "tfidf_credit")
    micro = float(np.mean(tfidf))
    length_micro = float(np.mean(length))
    large_tasks = [value for value in per_task.values() if value["pairs"] >= 20]
    criteria = {
        "pairs_eq_494": len(results) == 494,
        "tasks_eq_13": len(per_task) == 13,
        "tfidf_micro_accuracy_ge_0_60": micro >= 0.60,
        "task_clustered_tfidf_ci_lower_gt_0_50": tfidf_ci[0] > 0.50,
        "task_clustered_difference_ci_lower_gt_0": difference_ci[0] > 0.0,
        "at_least_6_of_8_large_tasks_above_0_50": sum(value["tfidf_accuracy"] > 0.50 for value in large_tasks) >= 6,
    }
    passed = all(criteria.values())
    return {
        "protocol": PROTOCOL,
        "status": "VERIFIED_TASK_HELDOUT_FAILURE_RISK_SIGNAL" if passed else "INSUFFICIENT_TASK_HELDOUT_FAILURE_RISK_SIGNAL",
        "scope": {
            "task_name_used_as_feature": False,
            "diagnostic_or_failure_category_used_as_feature": False,
            "numeric_grade_used": False,
            "frozen_code_used_for_training": False,
            "base_llm_updated": False,
            "gpu": 0,
            "api_calls": 0,
        },
        "pairs": len(results),
        "tasks": len(per_task),
        "physical_runs": len({row["run_id"] for row in results}),
        "tfidf_micro_accuracy": micro,
        "tfidf_task_macro_accuracy": float(np.mean([value["tfidf_accuracy"] for value in per_task.values()])),
        "tfidf_task_clustered_ci": list(tfidf_ci),
        "tfidf_run_clustered_ci": list(run_tfidf_ci),
        "length_micro_accuracy": length_micro,
        "length_task_clustered_ci": list(length_ci),
        "tfidf_minus_length": micro - length_micro,
        "tfidf_minus_length_task_clustered_ci": list(difference_ci),
        "per_task": per_task,
        "criteria": criteria,
        "failure_risk_signal_claim_allowed": passed,
        "search_utility_claim_allowed": False,
        "paid_experiment_authorized": False,
        "configuration": {
            "seed": SEED,
            "bootstraps": BOOTSTRAPS,
            "max_code_chars": MAX_CODE_CHARS,
            "tfidf": "char 3-5, min_df=2, max_features=50000, sublinear_tf, lowercase=false",
            "logistic_regression": "C=1.0, class_weight=balanced, liblinear, max_iter=1000",
        },
    }


def write_atomic(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise ControllerError("output already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--support-summary", required=True)
    value.add_argument("--cards", required=True)
    value.add_argument("--expect-cards-sha256", required=True)
    value.add_argument("--status-per-child", required=True)
    value.add_argument("--expect-status-sha256", required=True)
    value.add_argument("--taxonomy-per-child", required=True)
    value.add_argument("--expect-taxonomy-sha256", required=True)
    value.add_argument("--pair", action="append", required=True)
    value.add_argument("--expect-pair-sha256", action="append", required=True)
    value.add_argument("--root", action="append", required=True)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        args = parser().parse_args()
        if len(args.pair) != len(args.expect_pair_sha256):
            raise ControllerError("pair path/digest count mismatch")
        load_support(Path(args.support_summary).resolve())
        pairs = build_pairs(args)
        result = summarize(evaluate_pairs(pairs))
        result["source_commit"] = args.source_commit
        result["support_summary_sha256"] = SUPPORT_SHA
        write_atomic(Path(args.output).resolve(), result)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (ControllerError, SupportError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"FAILURE_RISK_CONTROLLER_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
