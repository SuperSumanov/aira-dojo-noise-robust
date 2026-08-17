#!/usr/bin/env python3
"""Build a code-free registry for the locked parent-matched failure-risk pairs."""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
from pathlib import Path
from typing import Any

from phase1.audit_failure_risk_pair_support import (
    SupportError,
    card_parent,
    load_failures,
    locked,
    parse_roots,
    rows,
    scan_failure_code_metadata,
    task_name,
)
from phase1.source_opportunity_journal_status import sha256_bytes, sha256_file


PROTOCOL = "failure-risk-pair-registry-v1"
SUPPORT_SHA256 = "77b81f8d4356d74f14647c8a12281af201fe34c75da04ed077febdac17b400f1"


class RegistryError(RuntimeError):
    pass


def load_support(path: Path) -> dict[str, Any]:
    if not path.is_file() or sha256_file(path) != SUPPORT_SHA256:
        raise RegistryError("locked support summary mismatch")
    value = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "status": "VERIFIED_FAILURE_RISK_PAIR_SUPPORT",
        "eligible_parent_matched_pairs": 494,
        "tasks": 13,
        "physical_runs": 126,
        "frozen_run_overlap": 0,
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise RegistryError(f"support contract mismatch for {key}")
    return value


def build_registry(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cards_path = locked(args.cards, args.expect_cards_sha256)
    status_path = locked(args.status_per_child, args.expect_status_sha256)
    taxonomy_path = locked(args.taxonomy_per_child, args.expect_taxonomy_sha256)
    pair_paths = [locked(path, digest) for path, digest in zip(args.pair, args.expect_pair_sha256, strict=True)]
    cards = {str(row["id"]): row for row in rows(cards_path)}

    frozen_runs: set[str] = set()
    for path in pair_paths:
        for pair in rows(path):
            if pair.get("intask_split") != "test":
                raise RegistryError("frozen pair input contains a non-test row")
            for key in ("better", "worse"):
                card = cards.get(str(pair.get(key)))
                if card is None:
                    raise RegistryError("frozen endpoint missing from cards")
                frozen_runs.add(str(card.get("run_id")))

    failures = load_failures(status_path, taxonomy_path, 691)
    metadata, inventory = scan_failure_code_metadata(parse_roots(args.root), failures)
    if inventory["credential_target_journal_shas"] != 0:
        raise RegistryError("credential-shaped target journal")

    retained_by_parent: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for card in cards.values():
        parent = card_parent(card)
        code = card.get("code")
        if parent and isinstance(code, str) and code.strip():
            retained_by_parent[parent].append(card)
    for values in retained_by_parent.values():
        values.sort(key=lambda card: str(card["id"]))

    failures_by_parent: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for child_id, failure in failures.items():
        code_meta = metadata.get(child_id)
        if code_meta and code_meta["code_present"]:
            failures_by_parent[failure["parent_id"]].append({**failure, **code_meta})
    for values in failures_by_parent.values():
        values.sort(key=lambda row: row["child_id"])

    registry = []
    for parent_id in sorted(set(failures_by_parent) & set(retained_by_parent)):
        parent = cards.get(parent_id)
        if parent is None:
            continue
        run_id = str(parent.get("run_id"))
        if run_id in frozen_runs:
            continue
        failure = failures_by_parent[parent_id][0]
        successes = [
            card
            for card in retained_by_parent[parent_id]
            if str(card.get("run_id")) == run_id
            and sha256_bytes(str(card.get("code") or "").encode("utf-8")) != failure["code_sha256"]
        ]
        if not successes:
            continue
        success = successes[0]
        registry.append(
            {
                "failure_category": failure["failure_category"],
                "failure_child_id": failure["child_id"],
                "failure_code_sha256": failure["code_sha256"],
                "failure_source_journal_sha256": failure["source_journal_sha256"],
                "parent_id": parent_id,
                "physical_run_id": run_id,
                "role": "train_only",
                "success_child_id": str(success["id"]),
                "success_code_sha256": sha256_bytes(str(success["code"]).encode("utf-8")),
                "task": task_name(parent),
            }
        )

    tasks = collections.Counter(row["task"] for row in registry)
    categories = collections.Counter(row["failure_category"] for row in registry)
    runs = {row["physical_run_id"] for row in registry}
    if len(registry) != 494 or len(tasks) != 13 or len(runs) != 126:
        raise RegistryError("registry differs from locked support counts")
    if len({row["parent_id"] for row in registry}) != len(registry):
        raise RegistryError("parent is not unique")
    if any(row["failure_code_sha256"] == row["success_code_sha256"] for row in registry):
        raise RegistryError("identical failure/success code hash")

    summary = {
        "protocol": PROTOCOL,
        "status": "VERIFIED_CODE_FREE_FAILURE_RISK_PAIR_REGISTRY",
        "pairs": len(registry),
        "tasks": len(tasks),
        "physical_runs": len(runs),
        "per_task_pairs": dict(sorted(tasks.items())),
        "failure_categories": dict(sorted(categories.items())),
        "support_summary_sha256": SUPPORT_SHA256,
        "credential_target_journal_shas": inventory["credential_target_journal_shas"],
        "raw_code_emitted": False,
        "numeric_grade_read": False,
        "frozen_code_used": False,
        "source_commit": args.source_commit,
        "inputs": {
            "cards_sha256": args.expect_cards_sha256,
            "status_per_child_sha256": args.expect_status_sha256,
            "taxonomy_per_child_sha256": args.expect_taxonomy_sha256,
            "pair_sha256": list(args.expect_pair_sha256),
        },
    }
    return registry, summary


def jsonl_bytes(registry: list[dict[str, Any]]) -> bytes:
    return b"".join(
        (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        for row in registry
    )


def write_new(path: Path, blob: bytes) -> None:
    if path.exists():
        raise RegistryError(f"output exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_bytes(blob)
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
    value.add_argument("--registry-output", required=True)
    value.add_argument("--summary-output", required=True)
    return value


def main() -> int:
    try:
        args = parser().parse_args()
        if len(args.pair) != len(args.expect_pair_sha256):
            raise RegistryError("pair path/digest count mismatch")
        load_support(Path(args.support_summary).resolve())
        registry, summary = build_registry(args)
        registry_blob = jsonl_bytes(registry)
        summary["registry_sha256"] = sha256_bytes(registry_blob)
        summary_blob = (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode("utf-8")
        write_new(Path(args.registry_output).resolve(), registry_blob)
        write_new(Path(args.summary_output).resolve(), summary_blob)
        print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
        return 0
    except (RegistryError, SupportError, OSError, json.JSONDecodeError) as exc:
        print(f"FAILURE_RISK_PAIR_REGISTRY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
