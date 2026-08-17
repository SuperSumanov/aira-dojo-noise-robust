#!/usr/bin/env python3
"""Audit parent-matched train-only failure/success pair support without emitting code."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable

from phase1.source_opportunity_journal_status import (
    CREDENTIAL,
    canonical_journals,
    decode_journal,
    node_card_id,
    sha256_bytes,
    sha256_file,
)


PROTOCOL = "failure-risk-parent-matched-support-v1"


class SupportError(RuntimeError):
    pass


def rows(path: Path) -> Iterable[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise SupportError(f"non-object row at {path}:{line_number}")
                yield value
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SupportError(f"cannot parse {path}: {exc}") from exc


def locked(path_value: str, expected_sha: str) -> Path:
    path = Path(path_value).resolve()
    if not path.is_file() or sha256_file(path) != expected_sha:
        raise SupportError(f"locked input mismatch: {path}")
    return path


def task_name(card: dict[str, Any]) -> str:
    task = card.get("task")
    value = task.get("name") if isinstance(task, dict) else task
    if not isinstance(value, str) or not value:
        raise SupportError("card has no canonical task")
    return value


def card_parent(card: dict[str, Any]) -> str | None:
    lineage = card.get("lineage")
    value = lineage.get("parent_id") if isinstance(lineage, dict) else None
    return value if isinstance(value, str) and value else None


def parse_roots(values: list[str]) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise SupportError("root must be ALIAS=PATH")
        alias, raw_path = value.split("=", 1)
        path = Path(raw_path).resolve()
        if not alias or alias in roots or not path.is_dir():
            raise SupportError(f"invalid provenance root: {value}")
        roots[alias] = path
    return roots


def load_failures(status_path: Path, taxonomy_path: Path, expected_targets: int) -> dict[str, dict[str, Any]]:
    selected = {}
    for row in rows(status_path):
        if (
            row.get("role") == "train"
            and row.get("status") == "UNIQUE_NODE_RECOVERED"
            and row.get("category") == "EXECUTION_ERROR"
            and row.get("parent_match") is True
        ):
            child = row.get("child_id")
            parent = row.get("expected_parent_id")
            journal_sha = row.get("source_journal_sha256")
            if not all(isinstance(value, str) and value for value in (child, parent, journal_sha)):
                raise SupportError("invalid train failure row")
            selected[child] = {
                "child_id": child,
                "parent_id": parent,
                "source_journal_sha256": journal_sha,
            }
    if len(selected) != expected_targets:
        raise SupportError(f"failure target count mismatch: {len(selected)}")

    taxonomy = {row.get("child_id"): row for row in rows(taxonomy_path)}
    if set(taxonomy) != set(selected):
        raise SupportError("taxonomy/status child identity mismatch")
    for child, target in selected.items():
        category = taxonomy[child].get("category")
        if not isinstance(category, str) or not category:
            raise SupportError("taxonomy category missing")
        if taxonomy[child].get("source_journal_sha256") != target["source_journal_sha256"]:
            raise SupportError("taxonomy/status journal mismatch")
        target["failure_category"] = category
    return selected


def scan_failure_code_metadata(
    roots: dict[str, Path], failures: dict[str, dict[str, Any]]
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    targets_by_sha: dict[str, set[str]] = collections.defaultdict(set)
    for child, row in failures.items():
        targets_by_sha[row["source_journal_sha256"]].add(child)
    wanted_shas = set(targets_by_sha)
    found: dict[str, dict[str, Any]] = {}
    seen_shas: set[str] = set()
    credential_shas: set[str] = set()
    inventory = {}
    for alias, root in sorted(roots.items()):
        journals = canonical_journals(root)
        target_copies = parsed_copies = credential_copies = 0
        for journal in journals:
            blob = journal.read_bytes()
            journal_sha = sha256_bytes(blob)
            if journal_sha not in wanted_shas:
                continue
            target_copies += 1
            seen_shas.add(journal_sha)
            if CREDENTIAL.search(blob):
                credential_copies += 1
                credential_shas.add(journal_sha)
                continue
            task, nodes = decode_journal(blob, journal_sha)
            parsed_copies += 1
            wanted_children = targets_by_sha[journal_sha]
            for node in nodes:
                child = node_card_id(task, node)
                if child not in wanted_children:
                    continue
                code = node.get("code")
                code = code if isinstance(code, str) else ""
                code_bytes = code.encode("utf-8")
                metadata = {
                    "code_present": bool(code.strip()),
                    "code_bytes": len(code_bytes),
                    "code_sha256": sha256_bytes(code_bytes),
                }
                prior = found.get(child)
                if prior is not None and prior != metadata:
                    raise SupportError(f"conflicting code copies for {child}")
                found[child] = metadata
        inventory[alias] = {
            "canonical_journals": len(journals),
            "target_journal_copies": target_copies,
            "parsed_target_journal_copies": parsed_copies,
            "credential_target_journal_copies": credential_copies,
        }
    return found, {
        "roots": inventory,
        "unique_target_journal_shas_expected": len(wanted_shas),
        "unique_target_journal_shas_seen": len(seen_shas),
        "credential_target_journal_shas": len(credential_shas),
    }


def build_summary(
    cards: dict[str, dict[str, Any]],
    failures: dict[str, dict[str, Any]],
    code_metadata: dict[str, dict[str, Any]],
    inventory: dict[str, Any],
    frozen_runs: set[str],
) -> dict[str, Any]:
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
        metadata = code_metadata.get(child)
        if metadata and metadata["code_present"]:
            failures_by_parent[row["parent_id"]].append({**row, **metadata})
    for values in failures_by_parent.values():
        values.sort(key=lambda row: row["child_id"])

    unique_failure_parents = {row["parent_id"] for row in failures.values()}
    parents_with_failure_code = set(failures_by_parent)
    parents_with_retained = set(retained_by_parent)
    identical_only = 0
    frozen_overlap = 0
    inconsistent_run = 0
    pairs = []
    for parent_id in sorted(parents_with_failure_code & parents_with_retained):
        parent_card = cards.get(parent_id)
        if parent_card is None:
            continue
        parent_run = str(parent_card.get("run_id"))
        if parent_run in frozen_runs:
            frozen_overlap += 1
            continue
        failure = failures_by_parent[parent_id][0]
        retained = [
            card
            for card in retained_by_parent[parent_id]
            if str(card.get("run_id")) == parent_run
            and sha256_bytes(str(card.get("code") or "").encode("utf-8")) != failure["code_sha256"]
        ]
        if not retained:
            same_run = [card for card in retained_by_parent[parent_id] if str(card.get("run_id")) == parent_run]
            if same_run:
                identical_only += 1
            else:
                inconsistent_run += 1
            continue
        success = retained[0]
        pairs.append(
            {
                "parent_id": parent_id,
                "run_id": parent_run,
                "task": task_name(parent_card),
                "failure_category": failure["failure_category"],
                "failure_code_sha256": failure["code_sha256"],
                "success_code_sha256": sha256_bytes(str(success["code"]).encode("utf-8")),
            }
        )

    task_counts = collections.Counter(row["task"] for row in pairs)
    category_counts = collections.Counter(row["failure_category"] for row in pairs)
    runs = {row["run_id"] for row in pairs}
    dominant = max(task_counts.values(), default=0)
    eligible = len(pairs)
    denominator = len(unique_failure_parents)
    criteria = {
        "failure_child_code_refind_rate_ge_0_95": len(code_metadata) / len(failures) >= 0.95,
        "credential_target_journal_shas_eq_0": inventory["credential_target_journal_shas"] == 0,
        "eligible_parent_matched_pairs_ge_300": eligible >= 300,
        "eligible_pair_share_ge_0_50": eligible / denominator >= 0.50,
        "tasks_ge_8": len(task_counts) >= 8,
        "tasks_with_at_least_20_pairs_ge_6": sum(value >= 20 for value in task_counts.values()) >= 6,
        "dominant_task_share_le_0_35": dominant / eligible <= 0.35 if eligible else False,
        "frozen_run_overlap_eq_0": frozen_overlap == 0,
        "identical_code_only_parent_share_le_0_10": identical_only / denominator <= 0.10,
    }
    passed = all(criteria.values())
    return {
        "protocol": PROTOCOL,
        "status": "VERIFIED_FAILURE_RISK_PAIR_SUPPORT" if passed else "INSUFFICIENT_FAILURE_RISK_PAIR_SUPPORT",
        "scope": {
            "role": "train_only",
            "reads_code_after_full_journal_credential_scan": True,
            "emits_code": False,
            "reads_numeric_grade": False,
            "reads_pair_orientation": False,
            "reads_frozen_code_for_training": False,
            "gpu": 0,
            "api_calls": 0,
        },
        "failure_children": len(failures),
        "failure_children_with_code_metadata": len(code_metadata),
        "failure_children_with_nonempty_code": sum(row["code_present"] for row in code_metadata.values()),
        "unique_failure_parents": denominator,
        "parents_with_nonempty_failure_code": len(parents_with_failure_code),
        "parents_with_retained_nonempty_sibling": len(parents_with_retained & unique_failure_parents),
        "eligible_parent_matched_pairs": eligible,
        "eligible_pair_share": eligible / denominator,
        "physical_runs": len(runs),
        "tasks": len(task_counts),
        "tasks_with_at_least_20_pairs": sum(value >= 20 for value in task_counts.values()),
        "dominant_task_share": dominant / eligible if eligible else None,
        "per_task_pairs": dict(sorted(task_counts.items())),
        "failure_categories": dict(sorted(category_counts.items())),
        "identical_code_only_parents": identical_only,
        "inconsistent_run_parents": inconsistent_run,
        "frozen_run_overlap": frozen_overlap,
        "journal_inventory": inventory,
        "criteria": criteria,
        "failure_risk_controller_support_claim_allowed": passed,
        "method_effect_claim_allowed": False,
        "paid_experiment_authorized": False,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    cards_path = locked(args.cards, args.expect_cards_sha256)
    status_path = locked(args.status_per_child, args.expect_status_sha256)
    taxonomy_path = locked(args.taxonomy_per_child, args.expect_taxonomy_sha256)
    pair_paths = [locked(value, digest) for value, digest in zip(args.pair, args.expect_pair_sha256, strict=True)]
    cards = {str(row["id"]): row for row in rows(cards_path)}
    frozen_runs = set()
    for path in pair_paths:
        for row in rows(path):
            if row.get("intask_split") != "test":
                raise SupportError("frozen pair input contains a non-test row")
            for key in ("better", "worse"):
                card = cards.get(str(row.get(key)))
                if card is None:
                    raise SupportError("frozen endpoint missing from cards")
                frozen_runs.add(str(card.get("run_id")))
    failures = load_failures(status_path, taxonomy_path, args.expect_targets)
    code_metadata, inventory = scan_failure_code_metadata(parse_roots(args.root), failures)
    result = build_summary(cards, failures, code_metadata, inventory, frozen_runs)
    result["inputs"] = {
        "cards_sha256": args.expect_cards_sha256,
        "status_per_child_sha256": args.expect_status_sha256,
        "taxonomy_per_child_sha256": args.expect_taxonomy_sha256,
        "pair_sha256": list(args.expect_pair_sha256),
        "source_commit": args.source_commit,
    }
    return result


def write_atomic(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise SupportError("output already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--cards", required=True)
    value.add_argument("--expect-cards-sha256", required=True)
    value.add_argument("--status-per-child", required=True)
    value.add_argument("--expect-status-sha256", required=True)
    value.add_argument("--taxonomy-per-child", required=True)
    value.add_argument("--expect-taxonomy-sha256", required=True)
    value.add_argument("--pair", action="append", required=True)
    value.add_argument("--expect-pair-sha256", action="append", required=True)
    value.add_argument("--expect-targets", type=int, required=True)
    value.add_argument("--root", action="append", required=True)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        args = parser().parse_args()
        if len(args.pair) != len(args.expect_pair_sha256):
            raise SupportError("pair paths and digests have different lengths")
        result = run(args)
        write_atomic(Path(args.output).resolve(), result)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (SupportError, OSError) as exc:
        print(f"FAILURE_RISK_PAIR_SUPPORT_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
