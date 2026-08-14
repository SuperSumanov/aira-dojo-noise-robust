"""Build an outcome-blind, equal-K continuation assignment manifest.

This module does not execute candidates and never accepts labels or scores.  It freezes a
blocked schedule in which every sibling under an anchor receives exactly K independent
continuation rollouts under one hash-locked execution contract.  The execution worker is a
separate gate; this manifest is the immutable randomization/provenance layer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


PROTOCOL = "balanced-continuation-v1"
STATUS = "READY_FOR_OUTCOME_BLIND_BALANCED_COLLECTION"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)

ANCHOR_KEYS = {
    "anchor_id",
    "task",
    "source_run_id",
    "parent_id",
    "sibling_id",
    "code_sha256",
    "anchor_contract_sha256",
}
CONTRACT_KEYS = {
    "schema_version",
    "model_id",
    "provider",
    "operator_config_sha256",
    "prompt_sha256",
    "source_commit",
    "dataset_contract_sha256",
    "evaluator_contract_sha256",
    "hardware_class",
    "execution_timeout_seconds",
    "continuation_horizon",
    "debug_policy",
    "workspace_policy",
    "temperature",
}


class ManifestError(RuntimeError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def checked_bytes(path: Path) -> bytes:
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise ManifestError(f"credential-shaped bytes refused before parsing: {path.name}")
    return raw


def nonempty_string(obj: dict[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{key} must be a non-empty string")
    return value


def parse_anchors(raw: bytes, siblings_per_anchor: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line_no, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ManifestError(f"invalid anchor JSON at line {line_no}") from exc
        if not isinstance(row, dict) or set(row) != ANCHOR_KEYS:
            raise ManifestError(f"anchor line {line_no} must have exactly {sorted(ANCHOR_KEYS)}")
        parsed = {key: nonempty_string(row, key) for key in ANCHOR_KEYS}
        for key in ("code_sha256", "anchor_contract_sha256"):
            if not HEX64.fullmatch(parsed[key]):
                raise ManifestError(f"anchor line {line_no} has invalid {key}")
        rows.append(parsed)
    if not rows:
        raise ManifestError("anchor input is empty")

    by_anchor: dict[str, list[dict[str, str]]] = defaultdict(list)
    sibling_ids: set[str] = set()
    code_hashes: set[str] = set()
    anchor_context: dict[str, tuple[str, str, str, str]] = {}
    for row in rows:
        sibling_id = row["sibling_id"]
        if sibling_id in sibling_ids:
            raise ManifestError(f"duplicate sibling_id: {sibling_id}")
        sibling_ids.add(sibling_id)
        if row["code_sha256"] in code_hashes:
            raise ManifestError("duplicate exact code across frozen siblings")
        code_hashes.add(row["code_sha256"])
        anchor_id = row["anchor_id"]
        context = (
            row["task"],
            row["source_run_id"],
            row["parent_id"],
            row["anchor_contract_sha256"],
        )
        previous = anchor_context.setdefault(anchor_id, context)
        if previous != context:
            raise ManifestError(f"anchor context changes within {anchor_id}")
        by_anchor[anchor_id].append(row)

    for anchor_id, siblings in by_anchor.items():
        if len(siblings) != siblings_per_anchor:
            raise ManifestError(
                f"anchor {anchor_id} has {len(siblings)} siblings, expected {siblings_per_anchor}"
            )
    return rows


def parse_contract(raw: bytes, horizon: int) -> dict[str, Any]:
    try:
        contract = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManifestError("invalid contract JSON") from exc
    if not isinstance(contract, dict) or set(contract) != CONTRACT_KEYS:
        raise ManifestError(f"contract must have exactly {sorted(CONTRACT_KEYS)}")
    for key in (
        "schema_version",
        "model_id",
        "provider",
        "hardware_class",
        "debug_policy",
        "workspace_policy",
    ):
        nonempty_string(contract, key)
    for key in (
        "operator_config_sha256",
        "prompt_sha256",
        "dataset_contract_sha256",
        "evaluator_contract_sha256",
    ):
        if not isinstance(contract.get(key), str) or not HEX64.fullmatch(contract[key]):
            raise ManifestError(f"invalid contract {key}")
    if not isinstance(contract.get("source_commit"), str) or not HEX40.fullmatch(contract["source_commit"]):
        raise ManifestError("invalid source_commit")
    if contract["schema_version"] != "balanced-continuation-contract-v1":
        raise ManifestError("unsupported contract schema_version")
    if contract["workspace_policy"] != "fresh_per_rollout":
        raise ManifestError("workspace_policy must be fresh_per_rollout")
    if contract["debug_policy"] != "fixed_one_operator_per_step":
        raise ManifestError("debug_policy must be fixed_one_operator_per_step")
    timeout = contract.get("execution_timeout_seconds")
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
        raise ManifestError("execution_timeout_seconds must be a positive integer")
    contract_horizon = contract.get("continuation_horizon")
    if isinstance(contract_horizon, bool) or not isinstance(contract_horizon, int) or contract_horizon != horizon:
        raise ManifestError("contract continuation_horizon does not match CLI")
    temperature = contract.get("temperature")
    if isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not (0 <= temperature <= 2):
        raise ManifestError("temperature must be finite and in [0, 2]")
    return contract


def hash_order(seed: int, *parts: str) -> str:
    message = "|".join((PROTOCOL, str(seed), *parts)).encode("utf-8")
    return sha256_bytes(message)


def rollout_seed(seed: int, anchor_id: str, sibling_id: str, replicate: int) -> int:
    digest = hashlib.sha256(
        f"{PROTOCOL}|rollout-seed|{seed}|{anchor_id}|{sibling_id}|{replicate}".encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:8], "big") % (2**31 - 1)


def build_assignments(
    anchors: Iterable[dict[str, str]],
    contract_sha256: str,
    siblings_per_anchor: int,
    replicates: int,
    horizon: int,
    seed: int,
) -> list[dict[str, Any]]:
    by_anchor: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in anchors:
        by_anchor[row["anchor_id"]].append(row)

    blocks = [(anchor_id, replicate) for anchor_id in by_anchor for replicate in range(replicates)]
    blocks.sort(key=lambda item: hash_order(seed, "block", item[0], str(item[1])))
    assignments: list[dict[str, Any]] = []
    seen_seeds: set[int] = set()
    seen_ids: set[str] = set()
    for anchor_id, replicate in blocks:
        siblings = sorted(
            by_anchor[anchor_id],
            key=lambda row: hash_order(seed, "within-block", anchor_id, str(replicate), row["sibling_id"]),
        )
        block_id = sha256_bytes(f"{PROTOCOL}|block|{anchor_id}|{replicate}".encode("utf-8"))
        for position, row in enumerate(siblings):
            rseed = rollout_seed(seed, anchor_id, row["sibling_id"], replicate)
            if rseed in seen_seeds:
                raise ManifestError("derived rollout seed collision")
            seen_seeds.add(rseed)
            rollout_id = sha256_bytes(
                (
                    f"{PROTOCOL}|{contract_sha256}|{anchor_id}|{row['sibling_id']}|"
                    f"{row['code_sha256']}|{replicate}|{rseed}"
                ).encode("utf-8")
            )
            if rollout_id in seen_ids:
                raise ManifestError("derived rollout id collision")
            seen_ids.add(rollout_id)
            assignments.append(
                {
                    "protocol": PROTOCOL,
                    "rollout_id": rollout_id,
                    "global_order": len(assignments),
                    "block_id": block_id,
                    "block_replicate": replicate,
                    "position_within_block": position,
                    "inclusion_probability": 1.0,
                    "order_probability": 1.0 / siblings_per_anchor,
                    "anchor_id": anchor_id,
                    "task": row["task"],
                    "source_run_id": row["source_run_id"],
                    "parent_id": row["parent_id"],
                    "sibling_id": row["sibling_id"],
                    "code_sha256": row["code_sha256"],
                    "anchor_contract_sha256": row["anchor_contract_sha256"],
                    "execution_contract_sha256": contract_sha256,
                    "rollout_seed": rseed,
                    "continuation_horizon": horizon,
                    "warm_start_executions": 1,
                    "planned_continuation_executions": horizon,
                }
            )
    return assignments


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def build(args: argparse.Namespace) -> int:
    if args.siblings_per_anchor < 2:
        raise ManifestError("siblings_per_anchor must be at least 2")
    if args.replicates < 2:
        raise ManifestError("replicates must be at least 2 for test-retest labels")
    if args.horizon < 1:
        raise ManifestError("horizon must be positive")
    if args.seed < 0:
        raise ManifestError("seed must be non-negative")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", args.created_utc):
        raise ManifestError("created_utc must be explicit UTC seconds")

    anchors_path = Path(args.anchors).resolve()
    contract_path = Path(args.contract).resolve()
    output = Path(args.output).resolve()
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if output.exists() or staging.exists():
        raise ManifestError("output and staging paths must not pre-exist")

    anchors_raw = checked_bytes(anchors_path)
    contract_raw = checked_bytes(contract_path)
    anchors = parse_anchors(anchors_raw, args.siblings_per_anchor)
    contract = parse_contract(contract_raw, args.horizon)
    anchors_sha = sha256_bytes(anchors_raw)
    contract_sha = sha256_bytes(contract_raw)
    assignments = build_assignments(
        anchors,
        contract_sha,
        args.siblings_per_anchor,
        args.replicates,
        args.horizon,
        args.seed,
    )
    task_count = len({row["task"] for row in anchors})
    anchor_count = len({row["anchor_id"] for row in anchors})
    jobs = len(assignments)
    summary = {
        "protocol": PROTOCOL,
        "status": STATUS,
        "created_utc": args.created_utc,
        "contains_outcomes": False,
        "anchors_input_sha256": anchors_sha,
        "execution_contract_sha256": contract_sha,
        "source_commit": contract["source_commit"],
        "seed": args.seed,
        "task_count": task_count,
        "anchor_count": anchor_count,
        "siblings_per_anchor": args.siblings_per_anchor,
        "replicates_per_sibling": args.replicates,
        "continuation_horizon": args.horizon,
        "rollout_jobs": jobs,
        "planned_warm_start_executions": jobs,
        "planned_continuation_executions": jobs * args.horizon,
        "planned_total_candidate_executions": jobs * (1 + args.horizon),
        "every_sibling_exactly_k": True,
        "every_block_contains_all_siblings": True,
        "fresh_workspace_required": True,
        "adaptive_allocation_allowed": False,
    }

    staging.mkdir(parents=True)
    try:
        (staging / "anchors.input.jsonl").write_bytes(anchors_raw)
        (staging / "execution_contract.input.json").write_bytes(contract_raw)
        assignment_text = "".join(canonical_json(row) + "\n" for row in assignments)
        write_text(staging / "assignment_manifest.jsonl", assignment_text)
        write_text(staging / "summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")
        write_text(staging / "command.txt", " ".join(sys.argv) + "\n")
        hashes = {
            path.name: sha256_bytes(path.read_bytes())
            for path in sorted(staging.iterdir())
            if path.is_file()
        }
        write_text(staging / "sha256_manifest.json", json.dumps(hashes, indent=2, sort_keys=True) + "\n")
        staging.replace(output)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    print(canonical_json(summary))
    return 0


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchors", required=True)
    ap.add_argument("--contract", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--siblings-per-anchor", type=int, required=True)
    ap.add_argument("--replicates", type=int, required=True)
    ap.add_argument("--horizon", type=int, required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--created-utc", required=True)
    return ap


def main() -> int:
    try:
        return build(parser().parse_args())
    except (ManifestError, OSError) as exc:
        print(f"MANIFEST_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
