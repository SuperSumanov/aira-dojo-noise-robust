#!/usr/bin/env python3
"""Structurally verify the code-free failure-risk pair registry."""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path
from typing import Any

from phase1.source_opportunity_journal_status import sha256_file


EXPECTED_KEYS = {
    "failure_category",
    "failure_child_id",
    "failure_code_sha256",
    "failure_source_journal_sha256",
    "parent_id",
    "physical_run_id",
    "role",
    "success_child_id",
    "success_code_sha256",
    "task",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class VerificationError(RuntimeError):
    pass


def read_registry(path: Path) -> list[dict[str, Any]]:
    result = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            value = json.loads(line)
            if not isinstance(value, dict) or set(value) != EXPECTED_KEYS:
                raise VerificationError(f"schema mismatch at line {line_number}")
            result.append(value)
    return result


def verify(registry_path: Path, summary_path: Path) -> dict[str, Any]:
    rows = read_registry(registry_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(summary, dict):
        raise VerificationError("summary is not an object")
    if summary.get("registry_sha256") != sha256_file(registry_path):
        raise VerificationError("registry hash mismatch")
    if summary.get("status") != "VERIFIED_CODE_FREE_FAILURE_RISK_PAIR_REGISTRY":
        raise VerificationError("producer status mismatch")
    if len(rows) != 494 or summary.get("pairs") != len(rows):
        raise VerificationError("pair count mismatch")

    parents = [str(row["parent_id"]) for row in rows]
    failures = [str(row["failure_child_id"]) for row in rows]
    successes = [str(row["success_child_id"]) for row in rows]
    if len(set(parents)) != len(rows) or len(set(failures)) != len(rows) or len(set(successes)) != len(rows):
        raise VerificationError("identity is not unique")

    for row in rows:
        if row["role"] != "train_only":
            raise VerificationError("non-train role")
        if not all(isinstance(row[key], str) and row[key] for key in EXPECTED_KEYS):
            raise VerificationError("empty or non-string registry field")
        for key in ("failure_code_sha256", "success_code_sha256", "failure_source_journal_sha256"):
            if not HEX64.fullmatch(row[key]):
                raise VerificationError(f"invalid digest in {key}")
        if row["failure_code_sha256"] == row["success_code_sha256"]:
            raise VerificationError("identical endpoint code digest")

    tasks = collections.Counter(str(row["task"]) for row in rows)
    categories = collections.Counter(str(row["failure_category"]) for row in rows)
    runs = {str(row["physical_run_id"]) for row in rows}
    if len(tasks) != 13 or len(runs) != 126:
        raise VerificationError("task/run count mismatch")
    if summary.get("per_task_pairs") != dict(sorted(tasks.items())):
        raise VerificationError("per-task aggregate mismatch")
    if summary.get("failure_categories") != dict(sorted(categories.items())):
        raise VerificationError("category aggregate mismatch")
    if summary.get("raw_code_emitted") is not False or summary.get("numeric_grade_read") is not False:
        raise VerificationError("scope declaration mismatch")
    return {
        "status": "STRUCTURALLY_VERIFIED_CODE_FREE_FAILURE_RISK_PAIR_REGISTRY",
        "pairs": len(rows),
        "tasks": len(tasks),
        "physical_runs": len(runs),
        "registry_sha256": sha256_file(registry_path),
        "summary_sha256": sha256_file(summary_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()
    try:
        result = verify(Path(args.registry).resolve(), Path(args.summary).resolve())
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (VerificationError, OSError, json.JSONDecodeError) as exc:
        print(f"FAILURE_RISK_PAIR_REGISTRY_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
