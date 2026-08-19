#!/usr/bin/env python3
"""Independent verifier for the augmented pair mismatch provenance artifact."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


SHA = re.compile(r"[0-9a-f]{64}")
RID = re.compile(r"^(.*)_seed_[0-9]+_id_[0-9a-f]+__(\d{4}-\d{2}-\d{2})$")
RUN_KEYS = {"cards", "config_sha256", "curve_order_sha256", "dev_order_sha256", "original_hold", "role", "run_id", "task"}
PAIR_KEYS = {"original_split", "pair_key_sha256", "run_ids", "same_experiment_contract", "task"}


class VerificationError(RuntimeError):
    pass


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def read_rows(path: Path, keys: set[str]) -> list[dict[str, Any]]:
    output = []
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                raise VerificationError(f"blank line {number}")
            row = json.loads(line)
            if not isinstance(row, dict) or set(row) != keys:
                raise VerificationError("row schema mismatch")
            output.append(row)
    return output


def expected_analysis(runs: list[dict[str, Any]], pairs: list[dict[str, Any]], expected_full: int) -> dict[str, Any]:
    run_map = {}
    for row in runs:
        if row["run_id"] in run_map or row["role"] not in {"train", "dev", "test_hold", "excluded_low_support"}:
            raise VerificationError("run identity or role invalid")
        if not SHA.fullmatch(row["config_sha256"]):
            raise VerificationError("config digest invalid")
        run_map[row["run_id"]] = row
    full = []
    pair_keys = set()
    for row in pairs:
        if row["pair_key_sha256"] in pair_keys:
            raise VerificationError("duplicate pair")
        pair_keys.add(row["pair_key_sha256"])
        ids = row["run_ids"]
        if not isinstance(ids, list) or ids != sorted(set(ids)) or not 1 <= len(ids) <= 2:
            raise VerificationError("pair run IDs invalid")
        if any(item not in run_map or run_map[item]["task"] != row["task"] for item in ids):
            raise VerificationError("pair reference invalid")
        same = len({run_map[item]["config_sha256"] for item in ids}) == 1
        if row["same_experiment_contract"] is not same:
            raise VerificationError("contract flag invalid")
        if row["original_split"] == "train" and {run_map[item]["role"] for item in ids} == {"train"}:
            full.append(row)
    if len(full) != expected_full or expected_full != 9001:
        raise VerificationError("frozen full-train count mismatch")
    bad = [row for row in full if not row["same_experiment_contract"]]
    tasks = collections.Counter(row["task"] for row in bad)
    task_runs: dict[str, set[str]] = collections.defaultdict(set)
    transitions = collections.Counter()
    family_count = day_count = unparsed = 0
    for row in bad:
        ids = row["run_ids"]
        task_runs[row["task"]].update(ids)
        transitions[tuple(sorted({run_map[item]["config_sha256"] for item in ids}))] += 1
        parsed = [RID.fullmatch(item) for item in ids]
        if not all(parsed):
            unparsed += 1
        else:
            values = [(match.group(1), match.group(2)) for match in parsed if match]
            family_count += len(set(values)) == 1
            day_count += len({item[1] for item in values}) == 1
    count = len(bad)
    family_share = family_count / count if count else None
    attribution = (
        "NO_MISMATCH" if count == 0 else
        "BATCH_CONTENT_MIXING_LIKELY" if family_share is not None and family_share >= 0.95 else
        "AGGREGATION_OR_PROVENANCE_LOSS_LIKELY" if family_share is not None and family_share <= 0.05 else
        "MIXED_OR_AMBIGUOUS_PROVENANCE"
    )
    ordered = sorted(transitions.items(), key=lambda item: (-item[1], item[0]))
    top_task = max(tasks.values(), default=0)
    top_transition = ordered[0][1] if ordered else 0
    return {
        "attribution": attribution,
        "inventory": {
            "full_train_pairs": len(full), "mismatch_pairs": count,
            "mismatch_share": count / len(full) if full else None,
            "mismatch_tasks": len(tasks),
            "mismatch_unique_runs": len({item for row in bad for item in row["run_ids"]}),
            "mismatch_config_transitions": len(transitions),
            "same_family_date_mismatch_pairs": family_count,
            "same_family_date_mismatch_share": family_share,
            "same_day_mismatch_pairs": day_count,
            "same_day_mismatch_share": day_count / count if count else None,
            "unparsed_run_id_mismatch_pairs": unparsed,
            "top_task_mismatch_pairs": top_task,
            "top_task_mismatch_share": top_task / count if count else None,
            "top_transition_mismatch_pairs": top_transition,
            "top_transition_mismatch_share": top_transition / count if count else None,
        },
        "mismatch_pairs_per_task": dict(sorted(tasks.items())),
        "mismatch_unique_runs_per_task": {task: len(task_runs[task]) for task in sorted(task_runs)},
        "config_transitions": [{"config_sha256": list(configs), "pairs": value} for configs, value in ordered],
    }


def verify(args: argparse.Namespace) -> dict[str, Any]:
    artifact = Path(args.artifact).resolve()
    if {item.name for item in artifact.iterdir() if item.is_file()} != {"summary.json", "sha256_manifest.json"}:
        raise VerificationError("artifact filenames mismatch")
    summary = json.loads((artifact / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((artifact / "sha256_manifest.json").read_text(encoding="utf-8"))
    if manifest != {"summary.json": digest(artifact / "summary.json")}:
        raise VerificationError("artifact manifest mismatch")
    run_path = Path(args.run_manifest).resolve()
    pair_path = Path(args.pair_structure).resolve()
    support_path = Path(args.support_summary).resolve()
    inputs = summary.get("inputs", {})
    for path, key in ((run_path, "run_manifest_sha256"), (pair_path, "pair_structure_sha256"), (support_path, "support_summary_sha256")):
        if digest(path) != inputs.get(key):
            raise VerificationError("input digest mismatch")
    upstream = json.loads(support_path.read_text(encoding="utf-8"))
    expected = expected_analysis(
        read_rows(run_path, RUN_KEYS), read_rows(pair_path, PAIR_KEYS), upstream.get("inventory", {}).get("full_train_pairs")
    )
    for key, value in expected.items():
        if summary.get(key) != value:
            raise VerificationError(f"summary mismatch: {key}")
    if summary.get("upstream_status_unchanged") != upstream.get("status"):
        raise VerificationError("upstream status mismatch")
    scope = summary.get("scope", {})
    if any(scope.get(key) is not False for key in ("numeric_grade_used", "pair_orientation_used", "raw_code_used", "frozen_test_used", "model_trained")):
        raise VerificationError("scope boolean mismatch")
    if scope.get("gpu") != 0 or scope.get("api_calls") != 0:
        raise VerificationError("scope resource mismatch")
    return {
        "protocol": "independent-senior-augmented-pair-mismatch-verifier-v1",
        "status": "INDEPENDENT_PAIR_MISMATCH_ARTIFACT_VERIFIED",
        "attribution": expected["attribution"],
        "full_train_pairs": expected["inventory"]["full_train_pairs"],
        "mismatch_pairs": expected["inventory"]["mismatch_pairs"],
        "producer_imported": False,
        "summary_sha256": digest(artifact / "summary.json"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--run-manifest", required=True)
    parser.add_argument("--pair-structure", required=True)
    parser.add_argument("--support-summary", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = verify(args)
        output = Path(args.output).resolve()
        if output.exists():
            raise VerificationError("verification output exists")
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (VerificationError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"PAIR_MISMATCH_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
