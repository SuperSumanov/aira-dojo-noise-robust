#!/usr/bin/env python3
"""Outcome-blind provenance audit for augmented experiment-contract mismatches."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


PROTOCOL = "senior-augmented-pair-mismatch-provenance-v1"
SHA256 = re.compile(r"[0-9a-f]{64}")
RUN_ID = re.compile(r"^(.*)_seed_[0-9]+_id_[0-9a-f]+__(\d{4}-\d{2}-\d{2})$")
RUN_FIELDS = {"cards", "config_sha256", "curve_order_sha256", "dev_order_sha256", "original_hold", "role", "run_id", "task"}
PAIR_FIELDS = {"original_split", "pair_key_sha256", "run_ids", "same_experiment_contract", "task"}


class AuditError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def locked(path_value: str, expected: str) -> Path:
    path = Path(path_value).resolve()
    if not path.is_file() or sha256_file(path) != expected:
        raise AuditError(f"locked input mismatch: {path.name}")
    return path


def load_jsonl(path: Path, expected_fields: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise AuditError(f"blank line at {path.name}:{line_number}")
            row = json.loads(line)
            if not isinstance(row, dict) or set(row) != expected_fields:
                raise AuditError(f"schema mismatch at {path.name}:{line_number}")
            rows.append(row)
    return rows


def family_date(run_id: str) -> tuple[str, str] | None:
    match = RUN_ID.fullmatch(run_id)
    return (match.group(1), match.group(2)) if match else None


def derive(run_rows: list[dict[str, Any]], pairs: list[dict[str, Any]], upstream: dict[str, Any]) -> dict[str, Any]:
    run_map: dict[str, dict[str, Any]] = {}
    for row in run_rows:
        run_id = row["run_id"]
        if not isinstance(run_id, str) or not run_id or run_id in run_map:
            raise AuditError("run identity invalid")
        if row["role"] not in {"train", "dev", "test_hold", "excluded_low_support"}:
            raise AuditError("run role invalid")
        if not isinstance(row["task"], str) or not SHA256.fullmatch(row["config_sha256"]):
            raise AuditError("run task or config digest invalid")
        run_map[run_id] = row

    seen: set[str] = set()
    full: list[dict[str, Any]] = []
    for pair in pairs:
        key = pair["pair_key_sha256"]
        run_ids = pair["run_ids"]
        if not isinstance(key, str) or not SHA256.fullmatch(key) or key in seen:
            raise AuditError("pair digest invalid or duplicated")
        seen.add(key)
        if pair["original_split"] not in {"train", "test"}:
            raise AuditError("pair split invalid")
        if not isinstance(run_ids, list) or not 1 <= len(run_ids) <= 2 or run_ids != sorted(set(run_ids)):
            raise AuditError("pair run list invalid")
        if any(run_id not in run_map for run_id in run_ids):
            raise AuditError("pair references unknown run")
        if any(run_map[run_id]["task"] != pair["task"] for run_id in run_ids):
            raise AuditError("pair task mismatch")
        expected_same = len({run_map[run_id]["config_sha256"] for run_id in run_ids}) == 1
        if pair["same_experiment_contract"] is not expected_same:
            raise AuditError("pair contract flag mismatch")
        if pair["original_split"] == "train" and {run_map[run_id]["role"] for run_id in run_ids} == {"train"}:
            full.append(pair)

    expected_full = upstream.get("inventory", {}).get("full_train_pairs")
    if expected_full != 9001 or len(full) != expected_full:
        raise AuditError("full-train pair count does not reproduce frozen support result")
    mismatches = [pair for pair in full if not pair["same_experiment_contract"]]
    task_counts = collections.Counter(pair["task"] for pair in mismatches)
    task_runs: dict[str, set[str]] = collections.defaultdict(set)
    transitions: collections.Counter[tuple[str, ...]] = collections.Counter()
    same_family_date = 0
    same_day = 0
    unparsed = 0
    for pair in mismatches:
        run_ids = pair["run_ids"]
        task_runs[pair["task"]].update(run_ids)
        transitions[tuple(sorted({run_map[run_id]["config_sha256"] for run_id in run_ids}))] += 1
        parsed = [family_date(run_id) for run_id in run_ids]
        if any(value is None for value in parsed):
            unparsed += 1
        else:
            parsed_ok = [value for value in parsed if value is not None]
            same_family_date += len(set(parsed_ok)) == 1
            same_day += len({value[1] for value in parsed_ok}) == 1

    mismatch_count = len(mismatches)
    family_share = same_family_date / mismatch_count if mismatch_count else None
    if mismatch_count == 0:
        attribution = "NO_MISMATCH"
    elif family_share is not None and family_share >= 0.95:
        attribution = "BATCH_CONTENT_MIXING_LIKELY"
    elif family_share is not None and family_share <= 0.05:
        attribution = "AGGREGATION_OR_PROVENANCE_LOSS_LIKELY"
    else:
        attribution = "MIXED_OR_AMBIGUOUS_PROVENANCE"

    ordered_transitions = sorted(transitions.items(), key=lambda item: (-item[1], item[0]))
    top_task_count = max(task_counts.values(), default=0)
    top_transition_count = ordered_transitions[0][1] if ordered_transitions else 0
    return {
        "attribution": attribution,
        "inventory": {
            "full_train_pairs": len(full),
            "mismatch_pairs": mismatch_count,
            "mismatch_share": mismatch_count / len(full) if full else None,
            "mismatch_tasks": len(task_counts),
            "mismatch_unique_runs": len({run_id for pair in mismatches for run_id in pair["run_ids"]}),
            "mismatch_config_transitions": len(transitions),
            "same_family_date_mismatch_pairs": same_family_date,
            "same_family_date_mismatch_share": family_share,
            "same_day_mismatch_pairs": same_day,
            "same_day_mismatch_share": same_day / mismatch_count if mismatch_count else None,
            "unparsed_run_id_mismatch_pairs": unparsed,
            "top_task_mismatch_pairs": top_task_count,
            "top_task_mismatch_share": top_task_count / mismatch_count if mismatch_count else None,
            "top_transition_mismatch_pairs": top_transition_count,
            "top_transition_mismatch_share": top_transition_count / mismatch_count if mismatch_count else None,
        },
        "mismatch_pairs_per_task": dict(sorted(task_counts.items())),
        "mismatch_unique_runs_per_task": {task: len(task_runs[task]) for task in sorted(task_runs)},
        "config_transitions": [
            {"config_sha256": list(configs), "pairs": count}
            for configs, count in ordered_transitions
        ],
    }


def run(args: argparse.Namespace) -> int:
    run_path = locked(args.run_manifest, args.expect_run_manifest_sha256)
    pair_path = locked(args.pair_structure, args.expect_pair_structure_sha256)
    upstream_path = locked(args.support_summary, args.expect_support_summary_sha256)
    output = Path(args.output).resolve()
    if output.exists():
        raise AuditError("output exists")
    run_rows = load_jsonl(run_path, RUN_FIELDS)
    pairs = load_jsonl(pair_path, PAIR_FIELDS)
    upstream = json.loads(upstream_path.read_text(encoding="utf-8"))
    derived = derive(run_rows, pairs, upstream)
    summary = {
        "protocol": PROTOCOL,
        "source_commit": args.source_commit,
        "inputs": {
            "run_manifest_sha256": args.expect_run_manifest_sha256,
            "pair_structure_sha256": args.expect_pair_structure_sha256,
            "support_summary_sha256": args.expect_support_summary_sha256,
        },
        **derived,
        "upstream_status_unchanged": upstream.get("status"),
        "scope": {
            "numeric_grade_used": False,
            "pair_orientation_used": False,
            "raw_code_used": False,
            "frozen_test_used": False,
            "model_trained": False,
            "gpu": 0,
            "api_calls": 0,
        },
    }
    output.mkdir(parents=True)
    summary_path = output / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    manifest = {"summary.json": sha256_file(summary_path)}
    (output / "sha256_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-manifest", required=True)
    parser.add_argument("--expect-run-manifest-sha256", required=True)
    parser.add_argument("--pair-structure", required=True)
    parser.add_argument("--expect-pair-structure-sha256", required=True)
    parser.add_argument("--support-summary", required=True)
    parser.add_argument("--expect-support-summary-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        return run(args)
    except (AuditError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"SENIOR_AUGMENTED_PAIR_MISMATCH_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
