"""Build the frozen 48 broad + 12 calibration E2-A assignment manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import sys
from collections import Counter, defaultdict
from typing import Any

from phase1.balanced_continuation_manifest import (
    CREDENTIAL, ManifestError, canonical_json, checked_bytes, parse_anchors, parse_contract,
    sha256_bytes,
)


ASSIGNMENT_PROTOCOL = "balanced-continuation-v1"
RANDOMIZATION_PROTOCOL = "balanced-continuation-e2a-variable-k-v1"
STATUS = "READY_FOR_OUTCOME_BLIND_E2A_COLLECTION"


def hash_order(seed: int, *parts: str) -> str:
    return sha256_bytes("|".join((RANDOMIZATION_PROTOCOL, str(seed), *parts)).encode("utf-8"))


def rollout_seed(seed: int, anchor_id: str, sibling_id: str, replicate: int) -> int:
    raw = f"{RANDOMIZATION_PROTOCOL}|rollout-seed|{seed}|{anchor_id}|{sibling_id}|{replicate}"
    return int.from_bytes(hashlib.sha256(raw.encode("utf-8")).digest()[:8], "big") % (2**31 - 1)


def load_calibration(path: pathlib.Path, anchors: list[dict[str, str]]) -> list[str]:
    raw = checked_bytes(path)
    value = json.loads(raw)
    if (
        not isinstance(value, list) or len(value) != 6 or len(set(value)) != 6
        or not all(isinstance(item, str) and re.fullmatch(r"[0-9a-f]{64}", item) for item in value)
    ):
        raise ManifestError("calibration anchor list must contain six unique SHA-256 ids")
    by_anchor: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in anchors:
        by_anchor[row["anchor_id"]].append(row)
    if not set(value) <= set(by_anchor):
        raise ManifestError("calibration anchor is absent from frozen anchors")
    tasks = [by_anchor[anchor_id][0]["task"] for anchor_id in value]
    if Counter(tasks) != Counter({task: 1 for task in set(tasks)}) or len(set(tasks)) != 6:
        raise ManifestError("calibration anchors must cover six tasks exactly once")
    return value


def build_assignments(
    anchors: list[dict[str, str]], calibration: set[str], contract_sha: str,
    siblings_per_anchor: int, horizon: int, seed: int,
) -> list[dict[str, Any]]:
    by_anchor: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in anchors:
        by_anchor[row["anchor_id"]].append(row)
    blocks = [(anchor_id, 0) for anchor_id in by_anchor]
    blocks.extend((anchor_id, 1) for anchor_id in calibration)
    blocks.sort(key=lambda item: hash_order(seed, "block", item[0], str(item[1])))
    assignments = []
    seen_seeds: set[int] = set(); seen_ids: set[str] = set()
    for anchor_id, replicate in blocks:
        siblings = sorted(
            by_anchor[anchor_id],
            key=lambda row: hash_order(
                seed, "within-block", anchor_id, str(replicate), row["sibling_id"]
            ),
        )
        block_id = sha256_bytes(
            f"{RANDOMIZATION_PROTOCOL}|block|{anchor_id}|{replicate}".encode("utf-8")
        )
        for position, row in enumerate(siblings):
            derived_seed = rollout_seed(seed, anchor_id, row["sibling_id"], replicate)
            if derived_seed in seen_seeds:
                raise ManifestError("derived rollout seed collision")
            seen_seeds.add(derived_seed)
            rollout_id = sha256_bytes((
                f"{RANDOMIZATION_PROTOCOL}|{contract_sha}|{anchor_id}|{row['sibling_id']}|"
                f"{row['code_sha256']}|{replicate}|{derived_seed}"
            ).encode("utf-8"))
            if rollout_id in seen_ids:
                raise ManifestError("derived rollout id collision")
            seen_ids.add(rollout_id)
            assignments.append({
                "protocol": ASSIGNMENT_PROTOCOL, "rollout_id": rollout_id,
                "global_order": len(assignments), "block_id": block_id,
                "block_replicate": replicate, "position_within_block": position,
                "inclusion_probability": 1.0, "order_probability": 1.0 / siblings_per_anchor,
                "anchor_id": anchor_id, "task": row["task"],
                "source_run_id": row["source_run_id"], "parent_id": row["parent_id"],
                "sibling_id": row["sibling_id"], "code_sha256": row["code_sha256"],
                "anchor_contract_sha256": row["anchor_contract_sha256"],
                "execution_contract_sha256": contract_sha, "rollout_seed": derived_seed,
                "continuation_horizon": horizon, "warm_start_executions": 1,
                "planned_continuation_executions": horizon,
            })
    return assignments


def write_text(path: pathlib.Path, value: str) -> None:
    path.write_text(value, encoding="utf-8", newline="\n")


def build(args: argparse.Namespace) -> dict[str, Any]:
    if args.siblings_per_anchor != 2 or args.horizon != 1 or args.seed < 0:
        raise ManifestError("E2-A requires two siblings, H=1, and a non-negative seed")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", args.created_utc):
        raise ManifestError("created_utc must be explicit UTC seconds")
    anchor_path = pathlib.Path(args.anchors).resolve()
    contract_path = pathlib.Path(args.contract).resolve()
    calibration_path = pathlib.Path(args.calibration_anchors).resolve()
    anchor_raw = checked_bytes(anchor_path); contract_raw = checked_bytes(contract_path)
    if CREDENTIAL.search(calibration_path.read_bytes()):
        raise ManifestError("credential-shaped bytes in calibration input")
    anchors = parse_anchors(anchor_raw, args.siblings_per_anchor)
    contract = parse_contract(contract_raw, args.horizon)
    if len(anchors) != 48 or len({row["anchor_id"] for row in anchors}) != 24:
        raise ManifestError("E2-A requires 24 exact-two anchors")
    if len({row["source_run_id"] for row in anchors}) != 24:
        raise ManifestError("E2-A anchors must occupy 24 distinct physical runs")
    if len({row["task"] for row in anchors}) != 6:
        raise ManifestError("E2-A anchors must cover six tasks")
    calibration = load_calibration(calibration_path, anchors)
    contract_sha = sha256_bytes(contract_raw)
    assignments = build_assignments(
        anchors, set(calibration), contract_sha, args.siblings_per_anchor, args.horizon, args.seed
    )
    if len(assignments) != 60:
        raise ManifestError("E2-A assignment count differs")
    per_sibling = Counter(row["sibling_id"] for row in assignments)
    calibration_siblings = {
        row["sibling_id"] for row in anchors if row["anchor_id"] in set(calibration)
    }
    if (
        len(per_sibling) != 48
        or any(count != (2 if sibling in calibration_siblings else 1) for sibling, count in per_sibling.items())
    ):
        raise ManifestError("E2-A variable-K exposure differs")
    output = pathlib.Path(args.output).resolve()
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if output.exists() or output.is_symlink() or staging.exists() or staging.is_symlink():
        raise ManifestError("output/staging must not pre-exist")
    summary = {
        "protocol": RANDOMIZATION_PROTOCOL, "assignment_protocol": ASSIGNMENT_PROTOCOL,
        "status": STATUS, "created_utc": args.created_utc, "contains_outcomes": False,
        "anchors_input_sha256": sha256_bytes(anchor_raw),
        "calibration_anchor_ids_sha256": sha256_bytes(calibration_path.read_bytes()),
        "execution_contract_sha256": contract_sha, "source_commit": contract["source_commit"],
        "seed": args.seed, "task_count": 6, "anchor_count": 24,
        "physical_run_count": 24, "siblings_per_anchor": 2, "broad_replicates": 1,
        "calibration_anchor_count": 6, "calibration_replicates": 2,
        "continuation_horizon": 1, "rollout_jobs": 60,
        "planned_warm_start_executions": 60, "planned_continuation_executions": 60,
        "planned_total_candidate_executions": 120, "planned_operator_api_calls": 60,
        "every_sibling_at_least_once": True, "calibration_siblings_exactly_twice": True,
        "every_block_contains_all_siblings": True, "fresh_workspace_required": True,
        "adaptive_allocation_allowed": False,
    }
    staging.mkdir(parents=True)
    try:
        (staging / "anchors.input.jsonl").write_bytes(anchor_raw)
        (staging / "calibration_anchor_ids.input.json").write_bytes(calibration_path.read_bytes())
        (staging / "execution_contract.input.json").write_bytes(contract_raw)
        write_text(
            staging / "assignment_manifest.jsonl",
            "".join(canonical_json(row) + "\n" for row in assignments),
        )
        write_text(staging / "summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")
        write_text(staging / "command.txt", " ".join(sys.argv) + "\n")
        hashes = {
            path.name: sha256_bytes(path.read_bytes())
            for path in sorted(staging.iterdir()) if path.is_file()
        }
        write_text(staging / "sha256_manifest.json", json.dumps(hashes, indent=2, sort_keys=True) + "\n")
        os.replace(staging, output)
    except BaseException:
        if staging.exists(): shutil.rmtree(staging)
        raise
    print(canonical_json(summary))
    return summary


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--anchors", required=True); ap.add_argument("--calibration-anchors", required=True)
    ap.add_argument("--contract", required=True); ap.add_argument("--output", required=True)
    ap.add_argument("--siblings-per-anchor", type=int, required=True)
    ap.add_argument("--horizon", type=int, required=True); ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--created-utc", required=True)
    return ap


def main() -> int:
    try:
        build(parser().parse_args())
    except (ManifestError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"E2A_MANIFEST_ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
