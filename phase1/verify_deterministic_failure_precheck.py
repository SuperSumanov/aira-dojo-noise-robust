#!/usr/bin/env python3
"""Independent verifier for anonymized deterministic-precheck artifacts."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np


SEED = 20260819
BOOTSTRAPS = 10_000
SHA256 = re.compile(r"[0-9a-f]{64}")
WRITERS = {"copy", "copyfile", "move", "open", "rename", "replace", "savetxt", "to_csv", "write_bytes", "write_csv", "write_text"}


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


def validate_endpoint(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != {"code_sha256", "decision", "parseable", "writer_kinds"}:
        raise VerificationError("endpoint fields mismatch")
    if not isinstance(value["code_sha256"], str) or not SHA256.fullmatch(value["code_sha256"]):
        raise VerificationError("endpoint code digest invalid")
    if not isinstance(value["parseable"], bool):
        raise VerificationError("parseable flag invalid")
    writers = value["writer_kinds"]
    if not isinstance(writers, list) or writers != sorted(set(writers)) or not set(writers) <= WRITERS:
        raise VerificationError("writer kinds invalid")
    expected = "REJECT_SYNTAX" if not value["parseable"] else ("KEEP" if writers else "REJECT_NO_ARTIFACT_WRITER")
    if value["decision"] != expected or (not value["parseable"] and writers):
        raise VerificationError("endpoint decision mismatch")


def rejected(value: dict[str, Any]) -> bool:
    return value["decision"] != "KEEP"


def bootstrap(rows: list[dict[str, Any]], cluster_key: str) -> dict[str, list[float]]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        grouped[row[cluster_key]].append(row)
    keys = sorted(grouped)
    rng = np.random.default_rng(SEED)
    catch = np.empty(BOOTSTRAPS, dtype=np.float64)
    false_reject = np.empty(BOOTSTRAPS, dtype=np.float64)
    net = np.empty(BOOTSTRAPS, dtype=np.float64)
    for index in range(BOOTSTRAPS):
        sampled = rng.choice(keys, size=len(keys), replace=True)
        draw = [row for key in sampled for row in grouped[str(key)]]
        failures = np.array([rejected(row["failure"]) for row in draw], dtype=np.float64)
        successes = np.array([rejected(row["success"]) for row in draw], dtype=np.float64)
        catch[index] = np.mean(failures)
        false_reject[index] = np.mean(successes)
        net[index] = np.mean(failures - successes)
    return {
        "failure_catch": [float(np.quantile(catch, 0.025)), float(np.quantile(catch, 0.975))],
        "success_false_reject": [float(np.quantile(false_reject, 0.025)), float(np.quantile(false_reject, 0.975))],
        "paired_net": [float(np.quantile(net, 0.025)), float(np.quantile(net, 0.975))],
    }


def derive(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = len(rows)
    failure_count = sum(rejected(row["failure"]) for row in rows)
    success_count = sum(rejected(row["success"]) for row in rows)
    per_task: dict[str, dict[str, Any]] = {}
    for task in sorted({row["task"] for row in rows}):
        subset = [row for row in rows if row["task"] == task]
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
    task_ci = bootstrap(rows, "task")
    run_ci = bootstrap(rows, "run_id")
    catch_rate = failure_count / pairs
    false_rate = success_count / pairs
    large_tasks = [value for value in per_task.values() if value["pairs"] >= 20]
    criteria = {
        "locked_support_eq_494_pairs_13_tasks_126_runs": pairs == 494
        and len(per_task) == 13
        and len({row["run_id"] for row in rows}) == 126,
        "failure_catch_rate_ge_0_05": catch_rate >= 0.05,
        "success_false_reject_rate_le_0_01": false_rate <= 0.01,
        "task_clustered_paired_net_ci_lower_gt_0": task_ci["paired_net"][0] > 0.0,
        "caught_failure_tasks_ge_6": sum(value["failure_caught"] >= 1 for value in per_task.values()) >= 6,
        "all_8_large_tasks_false_reject_rate_le_0_05": len(large_tasks) == 8
        and all(value["success_false_reject_rate"] <= 0.05 for value in large_tasks),
    }
    return {
        "pairs": pairs,
        "tasks": len(per_task),
        "physical_runs": len({row["run_id"] for row in rows}),
        "failure_caught": failure_count,
        "failure_catch_rate": catch_rate,
        "success_false_rejected": success_count,
        "success_false_reject_rate": false_rate,
        "paired_net": catch_rate - false_rate,
        "balanced_pair_rejection_precision": failure_count / (failure_count + success_count)
        if failure_count + success_count
        else None,
        "caught_failure_tasks": sum(value["failure_caught"] >= 1 for value in per_task.values()),
        "failure_rejection_reasons": dict(
            sorted(collections.Counter(row["failure"]["decision"] for row in rows if rejected(row["failure"])).items())
        ),
        "success_rejection_reasons": dict(
            sorted(collections.Counter(row["success"]["decision"] for row in rows if rejected(row["success"])).items())
        ),
        "task_clustered_ci": task_ci,
        "run_clustered_ci": run_ci,
        "per_task": per_task,
        "criteria": criteria,
    }


def verify(args: argparse.Namespace) -> dict[str, Any]:
    artifact = Path(args.artifact).resolve()
    expected_files = {"summary.json", "pair_features.jsonl", "sha256_manifest.json"}
    if {path.name for path in artifact.iterdir() if path.is_file()} != expected_files:
        raise VerificationError("artifact filenames mismatch")
    manifest = load_json(artifact / "sha256_manifest.json")
    for name in ("summary.json", "pair_features.jsonl"):
        if manifest.get(name) != sha256_file(artifact / name):
            raise VerificationError(f"artifact digest mismatch for {name}")
    summary = load_json(artifact / "summary.json")
    rows: list[dict[str, Any]] = []
    with (artifact / "pair_features.jsonl").open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            row = json.loads(line)
            if set(row) != {"failure", "failure_category", "parent_key_sha256", "run_id", "success", "task"}:
                raise VerificationError(f"pair fields mismatch at {line_number}")
            if not isinstance(row["parent_key_sha256"], str) or not SHA256.fullmatch(row["parent_key_sha256"]):
                raise VerificationError("parent digest invalid")
            if not all(isinstance(row[key], str) and row[key] for key in ("failure_category", "run_id", "task")):
                raise VerificationError("pair identity invalid")
            validate_endpoint(row["failure"])
            validate_endpoint(row["success"])
            rows.append(row)
    parents = [row["parent_key_sha256"] for row in rows]
    if len(parents) != len(set(parents)):
        raise VerificationError("parent digest duplicated")
    expected = derive(rows)
    for key, value in expected.items():
        if summary.get(key) != value:
            raise VerificationError(f"summary mismatch for {key}")
    feasible = all(expected["criteria"].values())
    expected_status = "RETROSPECTIVE_DETERMINISTIC_PRECHECK_FEASIBLE" if feasible else "INSUFFICIENT_DETERMINISTIC_PRECHECK_FEASIBILITY"
    if summary.get("status") != expected_status:
        raise VerificationError("status mismatch")
    scope = summary.get("scope", {})
    if scope.get("retrospective_only") is not True or scope.get("prospective_confirmation_required") is not True:
        raise VerificationError("retrospective scope missing")
    forbidden_true = ("search_utility_claim_allowed", "cross_agent_generalization_claim_allowed", "numeric_grade_read", "raw_code_emitted", "frozen_code_used", "base_llm_updated")
    if any(scope.get(key) is not False for key in forbidden_true) or scope.get("gpu") != 0 or scope.get("api_calls") != 0:
        raise VerificationError("forbidden scope enabled")
    if summary.get("configuration") != {
        "seed": SEED,
        "bootstraps": BOOTSTRAPS,
        "unconditional_writers": ["savetxt", "to_csv", "write_csv"],
        "submission_writers": ["copy", "copyfile", "move", "open", "rename", "replace", "write_bytes", "write_text"],
        "required_literal_suffix": "submission.csv",
    }:
        raise VerificationError("configuration mismatch")
    if summary.get("inputs", {}).get("pair_registry_sha256") != "ee7c878c9b3390c08d309229ac6380bf86e6934b92aab269e42ce7c2ffd57747":
        raise VerificationError("pair registry binding mismatch")
    return {
        "protocol": "independent-deterministic-failure-precheck-verifier-v1",
        "status": "INDEPENDENT_DETERMINISTIC_PRECHECK_ARTIFACT_VERIFIED",
        "producer_status": expected_status,
        "pairs": len(rows),
        "failure_caught": expected["failure_caught"],
        "success_false_rejected": expected["success_false_rejected"],
        "producer_imported": False,
        "summary_sha256": sha256_file(artifact / "summary.json"),
    }


def main() -> int:
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--artifact", required=True)
        parser.add_argument("--output", required=True)
        args = parser.parse_args()
        result = verify(args)
        output = Path(args.output).resolve()
        if output.exists():
            raise VerificationError("verification output exists")
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (VerificationError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"DETERMINISTIC_FAILURE_PRECHECK_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
