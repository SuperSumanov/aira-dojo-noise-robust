#!/usr/bin/env python3
"""Retrospective deterministic execution precheck on locked train-only pairs."""
from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np

from phase1.audit_failure_risk_pair_support import load_failures, locked, parse_roots, rows
from phase1.build_failure_risk_pair_registry import build_registry, jsonl_bytes, load_support
from phase1.source_opportunity_journal_status import (
    CREDENTIAL,
    canonical_journals,
    decode_journal,
    node_card_id,
    sha256_bytes,
    sha256_file,
)


PROTOCOL = "deterministic-failure-precheck-v1"
SEED = 20260819
BOOTSTRAPS = 10_000
SHA1 = re.compile(r"[0-9a-f]{40}")
UNCONDITIONAL_WRITERS = {"savetxt", "to_csv", "write_csv"}
SUBMISSION_WRITERS = {"copy", "copyfile", "move", "open", "rename", "replace", "write_bytes", "write_text"}


class PrecheckError(RuntimeError):
    pass


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
                    raise PrecheckError(f"conflicting code copies for {child}")
                codes[child] = code
    if credential_shas:
        raise PrecheckError("credential-shaped target journals are forbidden")
    if len(seen_shas) != len(targets_by_sha) or len(codes) != len(failures):
        raise PrecheckError("failure code refind contract changed")
    return codes


def call_name(function: ast.expr) -> str:
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return ""


def static_strings(node: ast.AST) -> list[str]:
    return [
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    ]


def is_submission_path(value: str) -> bool:
    return value.replace("\\", "/").lower().rstrip().endswith("submission.csv")


def writer_kinds(tree: ast.AST) -> list[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = call_name(node.func).lower()
        if name in UNCONDITIONAL_WRITERS:
            found.add(name)
            continue
        strings = static_strings(node)
        if name not in SUBMISSION_WRITERS or not any(is_submission_path(value) for value in strings):
            continue
        if name == "open":
            mode_values: list[str] = []
            mode_index = 0 if isinstance(node.func, ast.Attribute) else 1
            if len(node.args) > mode_index and isinstance(node.args[mode_index], ast.Constant) and isinstance(node.args[mode_index].value, str):
                mode_values.append(node.args[mode_index].value)
            for keyword in node.keywords:
                if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                    mode_values.append(keyword.value.value)
            if not any(set(mode.lower()) & {"w", "a", "x"} for mode in mode_values):
                continue
        found.add(name)
    return sorted(found)


def analyze_code(code: str) -> dict[str, Any]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {"parseable": False, "writer_kinds": [], "decision": "REJECT_SYNTAX"}
    writers = writer_kinds(tree)
    decision = "KEEP" if writers else "REJECT_NO_ARTIFACT_WRITER"
    return {"parseable": True, "writer_kinds": writers, "decision": decision}


def build_feature_rows(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    load_support(Path(args.support_summary).resolve())
    registry, registry_summary = build_registry(args)
    if registry_summary.get("registry_sha256") is not None:
        raise PrecheckError("unexpected in-memory registry digest")
    registry_path = locked(args.pair_registry, args.expect_pair_registry_sha256)
    if registry_path.read_bytes() != jsonl_bytes(registry):
        raise PrecheckError("published pair registry differs from reconstruction")
    registry_summary["pair_registry_sha256"] = args.expect_pair_registry_sha256

    cards_path = locked(args.cards, args.expect_cards_sha256)
    status_path = locked(args.status_per_child, args.expect_status_sha256)
    taxonomy_path = locked(args.taxonomy_per_child, args.expect_taxonomy_sha256)
    cards = {str(row["id"]): row for row in rows(cards_path)}
    failures = load_failures(status_path, taxonomy_path, 691)
    failure_codes = scan_failure_codes(parse_roots(args.root), failures)

    feature_rows: list[dict[str, Any]] = []
    for pair in registry:
        success_id = pair["success_child_id"]
        failure_id = pair["failure_child_id"]
        success_card = cards.get(success_id)
        failure_code = failure_codes.get(failure_id)
        if success_card is None or not isinstance(failure_code, str):
            raise PrecheckError("registry endpoint code missing")
        success_code = success_card.get("code")
        if not isinstance(success_code, str) or not success_code.strip() or not failure_code.strip():
            raise PrecheckError("registry endpoint code empty")
        if sha256_bytes(success_code.encode("utf-8")) != pair["success_code_sha256"]:
            raise PrecheckError("success code SHA mismatch")
        if sha256_bytes(failure_code.encode("utf-8")) != pair["failure_code_sha256"]:
            raise PrecheckError("failure code SHA mismatch")
        parent_key = hashlib.sha256(pair["parent_id"].encode("utf-8")).hexdigest()
        feature_rows.append(
            {
                "failure": {"code_sha256": pair["failure_code_sha256"], **analyze_code(failure_code)},
                "failure_category": pair["failure_category"],
                "parent_key_sha256": parent_key,
                "run_id": pair["physical_run_id"],
                "success": {"code_sha256": pair["success_code_sha256"], **analyze_code(success_code)},
                "task": pair["task"],
            }
        )
    if len(feature_rows) != 494:
        raise PrecheckError("feature row count mismatch")
    return feature_rows, registry_summary


def rejected(endpoint: dict[str, Any]) -> bool:
    return endpoint["decision"] != "KEEP"


def bootstrap(rows_value: list[dict[str, Any]], cluster_key: str) -> dict[str, list[float]]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows_value:
        grouped[str(row[cluster_key])].append(row)
    keys = sorted(grouped)
    rng = np.random.default_rng(SEED)
    catch = np.empty(BOOTSTRAPS, dtype=np.float64)
    false_reject = np.empty(BOOTSTRAPS, dtype=np.float64)
    net = np.empty(BOOTSTRAPS, dtype=np.float64)
    for index in range(BOOTSTRAPS):
        sampled = rng.choice(keys, size=len(keys), replace=True)
        draw = [row for key in sampled for row in grouped[str(key)]]
        failure_values = np.array([rejected(row["failure"]) for row in draw], dtype=np.float64)
        success_values = np.array([rejected(row["success"]) for row in draw], dtype=np.float64)
        catch[index] = np.mean(failure_values)
        false_reject[index] = np.mean(success_values)
        net[index] = np.mean(failure_values - success_values)
    return {
        "failure_catch": [float(np.quantile(catch, 0.025)), float(np.quantile(catch, 0.975))],
        "success_false_reject": [float(np.quantile(false_reject, 0.025)), float(np.quantile(false_reject, 0.975))],
        "paired_net": [float(np.quantile(net, 0.025)), float(np.quantile(net, 0.975))],
    }


def summarize(feature_rows: list[dict[str, Any]], source_commit: str, registry_summary: dict[str, Any]) -> dict[str, Any]:
    failure_rejections = [rejected(row["failure"]) for row in feature_rows]
    success_rejections = [rejected(row["success"]) for row in feature_rows]
    failure_count = sum(failure_rejections)
    success_count = sum(success_rejections)
    pairs = len(feature_rows)
    per_task: dict[str, dict[str, Any]] = {}
    for task in sorted({row["task"] for row in feature_rows}):
        subset = [row for row in feature_rows if row["task"] == task]
        caught = sum(rejected(row["failure"]) for row in subset)
        false = sum(rejected(row["success"]) for row in subset)
        per_task[task] = {
            "pairs": len(subset),
            "failure_caught": caught,
            "failure_catch_rate": caught / len(subset),
            "success_false_rejected": false,
            "success_false_reject_rate": false / len(subset),
            "paired_net": (caught - false) / len(subset),
        }
    large_tasks = [value for value in per_task.values() if value["pairs"] >= 20]
    task_ci = bootstrap(feature_rows, "task")
    run_ci = bootstrap(feature_rows, "run_id")
    catch_rate = failure_count / pairs
    false_rate = success_count / pairs
    net = catch_rate - false_rate
    criteria = {
        "locked_support_eq_494_pairs_13_tasks_126_runs": pairs == 494
        and len(per_task) == 13
        and len({row["run_id"] for row in feature_rows}) == 126,
        "failure_catch_rate_ge_0_05": catch_rate >= 0.05,
        "success_false_reject_rate_le_0_01": false_rate <= 0.01,
        "task_clustered_paired_net_ci_lower_gt_0": task_ci["paired_net"][0] > 0.0,
        "caught_failure_tasks_ge_6": sum(value["failure_caught"] >= 1 for value in per_task.values()) >= 6,
        "all_8_large_tasks_false_reject_rate_le_0_05": len(large_tasks) == 8
        and all(value["success_false_reject_rate"] <= 0.05 for value in large_tasks),
    }
    passed = all(criteria.values())
    failure_reasons = collections.Counter(row["failure"]["decision"] for row in feature_rows if rejected(row["failure"]))
    success_reasons = collections.Counter(row["success"]["decision"] for row in feature_rows if rejected(row["success"]))
    return {
        "protocol": PROTOCOL,
        "status": "RETROSPECTIVE_DETERMINISTIC_PRECHECK_FEASIBLE" if passed else "INSUFFICIENT_DETERMINISTIC_PRECHECK_FEASIBILITY",
        "source_commit": source_commit,
        "scope": {
            "retrospective_only": True,
            "prospective_confirmation_required": True,
            "search_utility_claim_allowed": False,
            "cross_agent_generalization_claim_allowed": False,
            "numeric_grade_read": False,
            "raw_code_emitted": False,
            "frozen_code_used": False,
            "base_llm_updated": False,
            "gpu": 0,
            "api_calls": 0,
        },
        "pairs": pairs,
        "tasks": len(per_task),
        "physical_runs": len({row["run_id"] for row in feature_rows}),
        "failure_caught": failure_count,
        "failure_catch_rate": catch_rate,
        "success_false_rejected": success_count,
        "success_false_reject_rate": false_rate,
        "paired_net": net,
        "balanced_pair_rejection_precision": failure_count / (failure_count + success_count)
        if failure_count + success_count
        else None,
        "caught_failure_tasks": sum(value["failure_caught"] >= 1 for value in per_task.values()),
        "failure_rejection_reasons": dict(sorted(failure_reasons.items())),
        "success_rejection_reasons": dict(sorted(success_reasons.items())),
        "task_clustered_ci": task_ci,
        "run_clustered_ci": run_ci,
        "per_task": per_task,
        "criteria": criteria,
        "inputs": {
            "support_summary_sha256": registry_summary["support_summary_sha256"],
            "pair_registry_sha256": registry_summary["pair_registry_sha256"],
            "cards_sha256": registry_summary["inputs"]["cards_sha256"],
            "status_per_child_sha256": registry_summary["inputs"]["status_per_child_sha256"],
            "taxonomy_per_child_sha256": registry_summary["inputs"]["taxonomy_per_child_sha256"],
            "pair_sha256": registry_summary["inputs"]["pair_sha256"],
        },
        "configuration": {
            "seed": SEED,
            "bootstraps": BOOTSTRAPS,
            "unconditional_writers": sorted(UNCONDITIONAL_WRITERS),
            "submission_writers": sorted(SUBMISSION_WRITERS),
            "required_literal_suffix": "submission.csv",
        },
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(args: argparse.Namespace) -> int:
    if not SHA1.fullmatch(args.source_commit):
        raise PrecheckError("source commit must be a full lowercase SHA-1")
    feature_rows, registry_summary = build_feature_rows(args)
    summary = summarize(feature_rows, args.source_commit, registry_summary)
    output = Path(args.output).resolve()
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if output.exists() or staging.exists():
        raise PrecheckError("output path exists")
    staging.mkdir(parents=True)
    write_json(staging / "summary.json", summary)
    with (staging / "pair_features.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in feature_rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    write_json(
        staging / "sha256_manifest.json",
        {name: sha256_file(staging / name) for name in ("summary.json", "pair_features.jsonl")},
    )
    staging.replace(output)
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--support-summary", required=True)
    value.add_argument("--pair-registry", required=True)
    value.add_argument("--expect-pair-registry-sha256", required=True)
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
            raise PrecheckError("pair path/digest count mismatch")
        return run(args)
    except (PrecheckError, OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"DETERMINISTIC_FAILURE_PRECHECK_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
