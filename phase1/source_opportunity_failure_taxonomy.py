#!/usr/bin/env python3
"""Classify train-only execution failures without emitting diagnostic text."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from phase1.source_opportunity_journal_status import (
    CREDENTIAL,
    HEX40,
    StatusError as SourceStatusError,
    canonical_journals,
    decode_journal,
    node_card_id,
    scan_file,
    sha256_bytes,
    sha256_file,
)


PROTOCOL = "source-opportunity-failure-taxonomy-v1"
STATUS_PASS = "VERIFIED_STRUCTURED_FAILURE_MEMORY_SUPPORT"
STATUS_FAIL = "INSUFFICIENT_STRUCTURED_FAILURE_MEMORY_SUPPORT"
SHA256 = re.compile(r"[0-9a-f]{64}")


class TaxonomyError(RuntimeError):
    pass


RULES: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = (
    (
        "ARTIFACT_OUTPUT_CONTRACT",
        (
            re.compile(
                r"(?:submission(?:\.csv)?|sample_submission).{0,120}"
                r"(?:not found|missing|no such file|invalid|column|schema|shape)",
                re.I | re.S,
            ),
            re.compile(
                r"(?:not found|missing|no such file|invalid|column|schema|shape).{0,120}"
                r"(?:submission(?:\.csv)?|sample_submission)",
                re.I | re.S,
            ),
        ),
    ),
    (
        "RESOURCE_OOM",
        tuple(
            re.compile(pattern, re.I)
            for pattern in (
                r"cuda\s+out\s+of\s+memory",
                r"outofmemoryerror",
                r"out\s+of\s+memory",
                r"cannot\s+allocate\s+memory",
            )
        ),
    ),
    (
        "RESOURCE_TIMEOUT",
        tuple(
            re.compile(pattern, re.I)
            for pattern in (r"timed?\s+out", r"timeout", r"time\s+limit\s+exceeded")
        ),
    ),
    (
        "DEPENDENCY_IMPORT",
        tuple(
            re.compile(pattern, re.I)
            for pattern in (r"modulenotfounderror", r"importerror", r"no\s+module\s+named")
        ),
    ),
    (
        "PYTHON_SYNTAX",
        tuple(
            re.compile(pattern, re.I)
            for pattern in (r"syntaxerror", r"indentationerror", r"taberror")
        ),
    ),
    (
        "FILESYSTEM_INPUT_PATH",
        tuple(
            re.compile(pattern, re.I)
            for pattern in (
                r"filenotfounderror",
                r"notadirectoryerror",
                r"permissionerror",
                r"no\s+such\s+file\s+or\s+directory",
            )
        ),
    ),
    (
        "LIBRARY_API_ATTRIBUTE",
        tuple(
            re.compile(pattern, re.I)
            for pattern in (r"attributeerror", r"unexpected\s+keyword\s+argument", r"has\s+no\s+attribute")
        ),
    ),
    (
        "DATA_SCHEMA_SHAPE_TYPE",
        tuple(
            re.compile(pattern, re.I)
            for pattern in (
                r"keyerror",
                r"valueerror",
                r"typeerror",
                r"indexerror",
                r"shape\s+mismatch",
                r"inconsistent\s+number\s+of\s+samples",
                r"column.{0,60}not\s+found",
                r"dtype",
            )
        ),
    ),
)

STRUCTURED_CATEGORIES = frozenset(category for category, _ in RULES) | {
    "PROCESS_SIGNAL"
}
CONTRACT_RELATED_CATEGORIES = frozenset(
    {"ARTIFACT_OUTPUT_CONTRACT", "DATA_SCHEMA_SHAPE_TYPE"}
)
SIGNAL_EXIT_CODES = frozenset({-15, -9, 137, 143})


def parse_roots(values: list[str]) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise TaxonomyError("root must be ALIAS=PATH")
        alias, raw_path = value.split("=", 1)
        if not re.fullmatch(r"[a-z0-9_]+", alias) or alias in roots:
            raise TaxonomyError("root alias is invalid or duplicated")
        path = Path(raw_path).resolve()
        if not path.is_dir():
            raise TaxonomyError(f"root is not a directory: {alias}")
        roots[alias] = path
    if not roots:
        raise TaxonomyError("no journal roots")
    return roots


def load_targets(path: Path, expected_sha256: str, expected_targets: int) -> dict[str, dict[str, str]]:
    if not SHA256.fullmatch(expected_sha256):
        raise TaxonomyError("expected status SHA must be lowercase SHA-256")
    if sha256_file(path) != expected_sha256:
        raise TaxonomyError("status per-child SHA mismatch")
    scan_file(path)
    targets: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise TaxonomyError(f"invalid status row {line_number}")
            if not (
                row.get("role") == "train"
                and row.get("status") == "UNIQUE_NODE_RECOVERED"
                and row.get("category") == "EXECUTION_ERROR"
            ):
                continue
            child = row.get("child_id")
            journal_sha = row.get("source_journal_sha256")
            if (
                not isinstance(child, str)
                or not child
                or child in targets
                or not isinstance(journal_sha, str)
                or not SHA256.fullmatch(journal_sha)
                or row.get("parent_match") is not True
            ):
                raise TaxonomyError(f"invalid train execution target row {line_number}")
            targets[child] = {"source_journal_sha256": journal_sha}
    if len(targets) != expected_targets:
        raise TaxonomyError(
            f"expected {expected_targets} train execution targets, found {len(targets)}"
        )
    return targets


def classify(exit_code: Any, diagnostic: str) -> tuple[str, str]:
    for category, patterns in RULES:
        for pattern_index, pattern in enumerate(patterns):
            if pattern.search(diagnostic):
                return category, f"{category}:{pattern_index}"
    if isinstance(exit_code, int) and not isinstance(exit_code, bool) and exit_code in SIGNAL_EXIT_CODES:
        return "PROCESS_SIGNAL", "PROCESS_SIGNAL:exit_code"
    if not diagnostic.strip():
        return "NO_DIAGNOSTIC_TEXT", "NO_DIAGNOSTIC_TEXT:empty"
    if re.search(r"traceback|exception|error\s*:", diagnostic, re.I):
        return "OTHER_TRACEBACK", "OTHER_TRACEBACK:generic"
    return "NON_TRACEBACK_TEXT", "NON_TRACEBACK_TEXT:nonempty"


def scan_targets(
    roots: dict[str, Path], targets: dict[str, dict[str, str]]
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    wanted_shas = {target["source_journal_sha256"] for target in targets.values()}
    targets_by_sha: dict[str, set[str]] = collections.defaultdict(set)
    for child, target in targets.items():
        targets_by_sha[target["source_journal_sha256"]].add(child)

    records: dict[str, dict[str, Any]] = {}
    seen_target_shas: set[str] = set()
    credential_target_shas: set[str] = set()
    inventory: dict[str, Any] = {}
    for alias, root in sorted(roots.items()):
        journals = canonical_journals(root)
        target_journals = credential_skips = parsed_target_journals = 0
        for journal in journals:
            blob = journal.read_bytes()
            journal_sha = sha256_bytes(blob)
            if journal_sha not in wanted_shas:
                continue
            target_journals += 1
            seen_target_shas.add(journal_sha)
            if CREDENTIAL.search(blob):
                credential_skips += 1
                credential_target_shas.add(journal_sha)
                continue
            task, nodes = decode_journal(blob, journal_sha)
            parsed_target_journals += 1
            wanted_children = targets_by_sha[journal_sha]
            for node in nodes:
                child = node_card_id(task, node)
                if child not in wanted_children:
                    continue
                diagnostic = node.get("term_out")
                diagnostic = diagnostic if isinstance(diagnostic, str) else ""
                category, rule_id = classify(node.get("exit_code"), diagnostic)
                record = {
                    "child_id": child,
                    "source_journal_sha256": journal_sha,
                    "category": category,
                    "rule_id": rule_id,
                    "diagnostic_text_present": bool(diagnostic.strip()),
                    "diagnostic_text_bytes": len(diagnostic.encode("utf-8")),
                    "diagnostic_text_sha256": sha256_bytes(diagnostic.encode("utf-8")),
                }
                previous = records.get(child)
                if previous is not None and previous != record:
                    raise TaxonomyError(f"conflicting source copies for child {child}")
                records[child] = record
        inventory[alias] = {
            "canonical_journals": len(journals),
            "target_journal_copies": target_journals,
            "parsed_target_journal_copies": parsed_target_journals,
            "credential_target_journal_copies_skipped": credential_skips,
        }

    for child, target in sorted(targets.items()):
        if child in records:
            continue
        journal_sha = target["source_journal_sha256"]
        category = (
            "CREDENTIAL_JOURNAL_SKIPPED"
            if journal_sha in credential_target_shas
            else "TARGET_NODE_NOT_REFINDABLE"
        )
        records[child] = {
            "child_id": child,
            "source_journal_sha256": journal_sha,
            "category": category,
            "rule_id": f"{category}:none",
            "diagnostic_text_present": False,
            "diagnostic_text_bytes": None,
            "diagnostic_text_sha256": None,
        }
    return records, {
        "roots": inventory,
        "unique_target_journal_shas_expected": len(wanted_shas),
        "unique_target_journal_shas_seen": len(seen_target_shas),
        "credential_target_journal_shas_skipped": len(credential_target_shas),
    }


def summarize(records: list[dict[str, Any]], inventory: dict[str, Any]) -> dict[str, Any]:
    total = len(records)
    categories = collections.Counter(row["category"] for row in records)
    classified = sum(row["category"] not in {"TARGET_NODE_NOT_REFINDABLE", "CREDENTIAL_JOURNAL_SKIPPED"} for row in records)
    structured = sum(row["category"] in STRUCTURED_CATEGORIES for row in records)
    contract_related = sum(row["category"] in CONTRACT_RELATED_CATEGORIES for row in records)
    diagnostic = sum(row["diagnostic_text_present"] for row in records)
    task_counts = collections.Counter(row["child_id"].split("__", 1)[0] for row in records)
    structured_task_counts = collections.Counter(
        row["child_id"].split("__", 1)[0]
        for row in records
        if row["category"] in STRUCTURED_CATEGORIES
    )
    dominant_structured_task = max(structured_task_counts.values(), default=0)
    gates = {
        "target_refind_rate_ge_0_95": classified / total >= 0.95,
        "diagnostic_text_share_ge_0_50": diagnostic / total >= 0.50,
        "structured_category_share_ge_0_50": structured / total >= 0.50,
        "structured_tasks_ge_10": len(structured_task_counts) >= 10,
        "dominant_structured_task_share_le_0_50": (
            dominant_structured_task / structured <= 0.50 if structured else False
        ),
        "credential_target_journal_shas_eq_0": inventory[
            "credential_target_journal_shas_skipped"
        ]
        == 0,
    }
    passed = all(gates.values())
    return {
        "protocol": PROTOCOL,
        "status": STATUS_PASS if passed else STATUS_FAIL,
        "scope": {
            "role": "train_only",
            "reads_term_out_after_credential_scan": True,
            "emits_raw_diagnostic_text": False,
            "reads_code": False,
            "reads_numeric_grade": False,
            "reads_pair_orientation": False,
            "reads_frozen_or_extension_target_nodes": False,
            "reads_env_or_tar_other_members": False,
            "gpu": 0,
            "api_calls": 0,
        },
        "targets": total,
        "target_nodes_refound": classified,
        "target_refind_rate": classified / total,
        "diagnostic_text_present": diagnostic,
        "diagnostic_text_share": diagnostic / total,
        "structured_category_nodes": structured,
        "structured_category_share": structured / total,
        "contract_related_nodes": contract_related,
        "contract_related_share": contract_related / total,
        "tasks": len(task_counts),
        "structured_tasks": len(structured_task_counts),
        "dominant_structured_task_share": (
            dominant_structured_task / structured if structured else None
        ),
        "categories": dict(sorted(categories.items())),
        "per_task_targets": dict(sorted(task_counts.items())),
        "per_task_structured": dict(sorted(structured_task_counts.items())),
        "journal_inventory": inventory,
        "criteria": gates,
        "failure_memory_support_claim_allowed": passed,
        "contract_method_effect_claim_allowed": False,
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def canonical_command(args: argparse.Namespace) -> str:
    parts = [
        "python",
        "-m",
        "phase1.source_opportunity_failure_taxonomy",
        "--status-per-child",
        str(args.status_per_child),
        "--expect-status-sha256",
        args.expect_status_sha256,
        "--expect-targets",
        str(args.expect_targets),
    ]
    for root in args.root:
        parts.extend(("--root", root))
    parts.extend(("--source-commit", args.source_commit, "--output", "<OUTPUT>"))
    return " ".join(parts) + "\n"


def run(args: argparse.Namespace) -> int:
    if not isinstance(args.source_commit, str) or not HEX40.fullmatch(args.source_commit):
        raise TaxonomyError("source commit must be a full lowercase SHA-1")
    status_path = Path(args.status_per_child).resolve()
    if not status_path.is_file():
        raise TaxonomyError("status per-child input missing")
    targets = load_targets(status_path, args.expect_status_sha256, args.expect_targets)
    roots = parse_roots(args.root)
    output = Path(args.output).resolve()
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if output.exists() or staging.exists():
        raise TaxonomyError("output already exists")
    record_map, inventory = scan_targets(roots, targets)
    records = [record_map[child] for child in sorted(record_map)]
    summary = summarize(records, inventory)
    summary["source_commit"] = args.source_commit
    summary["status_per_child_sha256"] = sha256_file(status_path)
    summary["taxonomy_priority"] = [category for category, _ in RULES] + [
        "PROCESS_SIGNAL",
        "NO_DIAGNOSTIC_TEXT",
        "OTHER_TRACEBACK",
        "NON_TRACEBACK_TEXT",
    ]
    staging.mkdir(parents=True)
    write_json(staging / "summary.json", summary)
    with (staging / "per_child.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in records:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    (staging / "command.txt").write_text(
        canonical_command(args), encoding="utf-8", newline="\n"
    )
    manifest = {
        name: sha256_file(staging / name)
        for name in ("summary.json", "per_child.jsonl", "command.txt")
    }
    write_json(staging / "sha256_manifest.json", manifest)
    for path in staging.iterdir():
        scan_file(path)
    staging.replace(output)
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--status-per-child", required=True)
    value.add_argument("--expect-status-sha256", required=True)
    value.add_argument("--expect-targets", type=int, required=True)
    value.add_argument("--root", action="append", required=True)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        return run(parser().parse_args())
    except (TaxonomyError, SourceStatusError, json.JSONDecodeError) as exc:
        print(f"FAILURE_TAXONOMY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
