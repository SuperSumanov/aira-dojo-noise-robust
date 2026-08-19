#!/usr/bin/env python3
"""Independent artifact verifier; does not import the operator-support producer."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


class VerificationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def verify(args: argparse.Namespace) -> dict[str, Any]:
    artifact = Path(args.artifact).resolve()
    expected_names = {"summary.json", "parent_support.jsonl", "sha256_manifest.json"}
    if {path.name for path in artifact.iterdir() if path.is_file()} != expected_names:
        raise VerificationError("artifact filenames mismatch")
    manifest = load_json(artifact / "sha256_manifest.json")
    for name in ("summary.json", "parent_support.jsonl"):
        if manifest.get(name) != sha256_file(artifact / name):
            raise VerificationError(f"manifest mismatch for {name}")
    summary = load_json(artifact / "summary.json")
    rows: list[dict[str, Any]] = []
    with (artifact / "parent_support.jsonl").open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            row = json.loads(line)
            if set(row) != {"parent_key_sha256", "task", "run_id", "children", "ops", "mixed", "exact_two"}:
                raise VerificationError(f"row fields mismatch at {line_number}")
            if not re.fullmatch(r"[0-9a-f]{64}", row["parent_key_sha256"]):
                raise VerificationError("parent key digest invalid")
            if not isinstance(row["task"], str) or not row["task"]:
                raise VerificationError("task identity invalid")
            if not isinstance(row["run_id"], str) or not row["run_id"]:
                raise VerificationError("run identity invalid")
            if not isinstance(row["children"], int) or isinstance(row["children"], bool) or row["children"] < 1:
                raise VerificationError("child count invalid")
            if not isinstance(row["ops"], list) or not all(isinstance(op, str) and op for op in row["ops"]):
                raise VerificationError("operator list invalid")
            if not isinstance(row["mixed"], bool) or not isinstance(row["exact_two"], bool):
                raise VerificationError("parent flags invalid")
            if row["ops"] != sorted(set(row["ops"])) or row["mixed"] != (len(row["ops"]) >= 2):
                raise VerificationError("operator set mismatch")
            if row["exact_two"] != (row["children"] == 2):
                raise VerificationError("exact-two flag mismatch")
            rows.append(row)
    keys = [row["parent_key_sha256"] for row in rows]
    if len(keys) != len(set(keys)):
        raise VerificationError("duplicate parent key")
    mixed = [row for row in rows if row["mixed"]]
    mixed_tasks = collections.Counter(row["task"] for row in mixed)
    exact_two = [row for row in mixed if row["exact_two"]]
    inventory = summary.get("inventory", {})
    expected = {
        "nonroot_parents": len(rows),
        "mixed_operator_parents": len(mixed),
        "mixed_operator_tasks": len(mixed_tasks),
        "exact_two_mixed_operator_parents": len(exact_two),
        "dominant_mixed_operator_task_share": max(mixed_tasks.values(), default=0) / len(mixed) if mixed else None,
    }
    for key, value in expected.items():
        if inventory.get(key) != value:
            raise VerificationError(f"inventory mismatch for {key}")
    if summary.get("mixed_parent_per_task") != dict(sorted(mixed_tasks.items())):
        raise VerificationError("per-task mixed support mismatch")
    scope = summary.get("scope", {})
    if any(scope.get(key) is not False for key in ("outcomes_read", "label_vault_opened", "numeric_grade_read", "raw_code_emitted", "production_activation_authorized", "causal_claim_allowed")):
        raise VerificationError("scope permits forbidden access or claims")
    criteria = summary.get("criteria", {})
    independently_checked_criteria = {
        "mixed_operator_parents_ge_100": len(mixed) >= 100,
        "mixed_operator_tasks_ge_10": len(mixed_tasks) >= 10,
        "exact_two_mixed_operator_parents_ge_60": len(exact_two) >= 60,
        "dominant_mixed_operator_task_share_le_0_25": expected["dominant_mixed_operator_task_share"] is not None
        and expected["dominant_mixed_operator_task_share"] <= 0.25,
    }
    for key, value in independently_checked_criteria.items():
        if criteria.get(key) is not value:
            raise VerificationError(f"criterion mismatch for {key}")
    if summary.get("status") not in {
        "OPERATOR_RANDOMIZATION_SUPPORT_FEASIBLE",
        "INSUFFICIENT_OPERATOR_RANDOMIZATION_SUPPORT",
    }:
        raise VerificationError("producer status invalid")
    if (summary["status"] == "OPERATOR_RANDOMIZATION_SUPPORT_FEASIBLE") != all(criteria.values()):
        raise VerificationError("producer status/criteria mismatch")
    return {
        "protocol": "independent-prospective-operator-support-verifier-v1",
        "status": "INDEPENDENT_OPERATOR_SUPPORT_ARTIFACT_VERIFIED",
        "producer_status": summary.get("status"),
        "parents": len(rows),
        "mixed_operator_parents": len(mixed),
        "mixed_operator_tasks": len(mixed_tasks),
        "exact_two_mixed_operator_parents": len(exact_two),
        "producer_imported": False,
        "summary_sha256": sha256_file(artifact / "summary.json"),
    }


def main() -> int:
    try:
        args = argparse.ArgumentParser()
        args.add_argument("--artifact", required=True)
        args.add_argument("--output", required=True)
        parsed = args.parse_args()
        result = verify(parsed)
        output = Path(parsed.output).resolve()
        if output.exists():
            raise VerificationError("verification output exists")
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (VerificationError, OSError, json.JSONDecodeError) as exc:
        print(f"PROSPECTIVE_OPERATOR_SUPPORT_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
