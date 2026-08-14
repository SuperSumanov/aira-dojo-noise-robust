"""Independent verifier for the equal-K continuation assignment artifact.

This file intentionally does not import ``balanced_continuation_manifest``.  It re-parses
inputs, re-derives every block/order/seed/rollout ID, and checks all artifact hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


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
EXPECTED_FILES = {
    "anchors.input.jsonl",
    "execution_contract.input.json",
    "assignment_manifest.jsonl",
    "summary.json",
    "command.txt",
    "sha256_manifest.json",
}


class VerifyError(RuntimeError):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def safe_read(path: Path) -> bytes:
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise VerifyError(f"credential-shaped bytes in {path.name}")
    return raw


def require_string(obj: dict[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise VerifyError(f"invalid {key}")
    return value


def anchors_from(raw: bytes, siblings_per_anchor: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line_no, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise VerifyError(f"invalid anchor JSON line {line_no}") from exc
        if not isinstance(row, dict) or set(row) != ANCHOR_KEYS:
            raise VerifyError("anchor schema mismatch")
        parsed = {key: require_string(row, key) for key in ANCHOR_KEYS}
        if not HEX64.fullmatch(parsed["code_sha256"]) or not HEX64.fullmatch(
            parsed["anchor_contract_sha256"]
        ):
            raise VerifyError("anchor hash mismatch")
        rows.append(parsed)
    if not rows:
        raise VerifyError("empty anchors")

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    contexts: dict[str, tuple[str, str, str, str]] = {}
    sibling_ids: set[str] = set()
    code_hashes: set[str] = set()
    for row in rows:
        if row["sibling_id"] in sibling_ids or row["code_sha256"] in code_hashes:
            raise VerifyError("duplicate sibling identity or exact code")
        sibling_ids.add(row["sibling_id"])
        code_hashes.add(row["code_sha256"])
        anchor_id = row["anchor_id"]
        context = (
            row["task"],
            row["source_run_id"],
            row["parent_id"],
            row["anchor_contract_sha256"],
        )
        if anchor_id in contexts and contexts[anchor_id] != context:
            raise VerifyError("anchor context mismatch")
        contexts[anchor_id] = context
        groups[anchor_id].append(row)
    if any(len(group) != siblings_per_anchor for group in groups.values()):
        raise VerifyError("unequal sibling support")
    return rows


def contract_from(raw: bytes, horizon: int) -> dict[str, Any]:
    try:
        contract = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise VerifyError("invalid contract JSON") from exc
    if not isinstance(contract, dict) or set(contract) != CONTRACT_KEYS:
        raise VerifyError("contract schema mismatch")
    for key in (
        "schema_version",
        "model_id",
        "provider",
        "hardware_class",
        "debug_policy",
        "workspace_policy",
    ):
        require_string(contract, key)
    for key in (
        "operator_config_sha256",
        "prompt_sha256",
        "dataset_contract_sha256",
        "evaluator_contract_sha256",
    ):
        if not isinstance(contract.get(key), str) or not HEX64.fullmatch(contract[key]):
            raise VerifyError("contract hash mismatch")
    if not isinstance(contract.get("source_commit"), str) or not HEX40.fullmatch(contract["source_commit"]):
        raise VerifyError("source commit mismatch")
    if contract["schema_version"] != "balanced-continuation-contract-v1":
        raise VerifyError("contract version mismatch")
    if contract["workspace_policy"] != "fresh_per_rollout":
        raise VerifyError("workspace policy mismatch")
    if contract["debug_policy"] != "fixed_one_operator_per_step":
        raise VerifyError("debug policy mismatch")
    timeout = contract.get("execution_timeout_seconds")
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
        raise VerifyError("timeout mismatch")
    if contract.get("continuation_horizon") != horizon:
        raise VerifyError("horizon mismatch")
    temperature = contract.get("temperature")
    if isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not 0 <= temperature <= 2:
        raise VerifyError("temperature mismatch")
    return contract


def order_hash(seed: int, *parts: str) -> str:
    return digest("|".join((PROTOCOL, str(seed), *parts)).encode("utf-8"))


def derive_seed(seed: int, anchor_id: str, sibling_id: str, replicate: int) -> int:
    raw = f"{PROTOCOL}|rollout-seed|{seed}|{anchor_id}|{sibling_id}|{replicate}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big") % (2**31 - 1)


def expected_assignments(
    anchors: list[dict[str, str]],
    contract_sha: str,
    siblings_per_anchor: int,
    replicates: int,
    horizon: int,
    seed: int,
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in anchors:
        groups[row["anchor_id"]].append(row)
    blocks = [(anchor, rep) for anchor in groups for rep in range(replicates)]
    blocks.sort(key=lambda item: order_hash(seed, "block", item[0], str(item[1])))
    result: list[dict[str, Any]] = []
    seeds: set[int] = set()
    rollout_ids: set[str] = set()
    for anchor_id, replicate in blocks:
        siblings = sorted(
            groups[anchor_id],
            key=lambda row: order_hash(seed, "within-block", anchor_id, str(replicate), row["sibling_id"]),
        )
        block_id = digest(f"{PROTOCOL}|block|{anchor_id}|{replicate}".encode("utf-8"))
        for position, row in enumerate(siblings):
            rseed = derive_seed(seed, anchor_id, row["sibling_id"], replicate)
            rollout_id = digest(
                (
                    f"{PROTOCOL}|{contract_sha}|{anchor_id}|{row['sibling_id']}|"
                    f"{row['code_sha256']}|{replicate}|{rseed}"
                ).encode("utf-8")
            )
            if rseed in seeds or rollout_id in rollout_ids:
                raise VerifyError("derived collision")
            seeds.add(rseed)
            rollout_ids.add(rollout_id)
            result.append(
                {
                    "protocol": PROTOCOL,
                    "rollout_id": rollout_id,
                    "global_order": len(result),
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
                    "execution_contract_sha256": contract_sha,
                    "rollout_seed": rseed,
                    "continuation_horizon": horizon,
                    "warm_start_executions": 1,
                    "planned_continuation_executions": horizon,
                }
            )
    return result


def verify(args: argparse.Namespace) -> int:
    root = Path(args.result).resolve()
    receipt = Path(args.receipt).resolve()
    if receipt.exists() or receipt.with_name(receipt.name + f".tmp-{os.getpid()}").exists():
        raise VerifyError("receipt path must not pre-exist")
    files = {path.name for path in root.iterdir() if path.is_file()}
    if files != EXPECTED_FILES:
        raise VerifyError(f"artifact file set mismatch: {sorted(files)}")

    stored_hashes = json.loads(safe_read(root / "sha256_manifest.json"))
    expected_hash_names = EXPECTED_FILES - {"sha256_manifest.json"}
    if not isinstance(stored_hashes, dict) or set(stored_hashes) != expected_hash_names:
        raise VerifyError("hash manifest key mismatch")
    for name in expected_hash_names:
        if stored_hashes[name] != digest(safe_read(root / name)):
            raise VerifyError(f"artifact hash mismatch: {name}")

    summary = json.loads(safe_read(root / "summary.json"))
    required_ints = {
        "seed",
        "task_count",
        "anchor_count",
        "siblings_per_anchor",
        "replicates_per_sibling",
        "continuation_horizon",
        "rollout_jobs",
        "planned_warm_start_executions",
        "planned_continuation_executions",
        "planned_total_candidate_executions",
    }
    if not isinstance(summary, dict) or any(
        isinstance(summary.get(key), bool) or not isinstance(summary.get(key), int) for key in required_ints
    ):
        raise VerifyError("summary integer schema mismatch")
    if summary.get("protocol") != PROTOCOL or summary.get("status") != STATUS:
        raise VerifyError("summary status mismatch")
    if summary.get("contains_outcomes") is not False:
        raise VerifyError("outcome-blind flag mismatch")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", str(summary.get("created_utc"))):
        raise VerifyError("created UTC mismatch")
    siblings_per_anchor = summary["siblings_per_anchor"]
    replicates = summary["replicates_per_sibling"]
    horizon = summary["continuation_horizon"]
    seed = summary["seed"]
    if siblings_per_anchor < 2 or replicates < 2 or horizon < 1 or seed < 0:
        raise VerifyError("invalid frozen design")

    anchors_raw = safe_read(root / "anchors.input.jsonl")
    contract_raw = safe_read(root / "execution_contract.input.json")
    anchors = anchors_from(anchors_raw, siblings_per_anchor)
    contract = contract_from(contract_raw, horizon)
    contract_sha = digest(contract_raw)
    expected = expected_assignments(anchors, contract_sha, siblings_per_anchor, replicates, horizon, seed)
    expected_bytes = "".join(canonical(row) + "\n" for row in expected).encode("utf-8")
    if safe_read(root / "assignment_manifest.jsonl") != expected_bytes:
        raise VerifyError("assignment manifest does not match independent reconstruction")

    anchor_count = len({row["anchor_id"] for row in anchors})
    task_count = len({row["task"] for row in anchors})
    jobs = len(expected)
    recomputed = {
        "anchors_input_sha256": digest(anchors_raw),
        "execution_contract_sha256": contract_sha,
        "source_commit": contract["source_commit"],
        "task_count": task_count,
        "anchor_count": anchor_count,
        "rollout_jobs": jobs,
        "planned_warm_start_executions": jobs,
        "planned_continuation_executions": jobs * horizon,
        "planned_total_candidate_executions": jobs * (1 + horizon),
    }
    for key, value in recomputed.items():
        if summary.get(key) != value:
            raise VerifyError(f"summary mismatch: {key}")
    for key in (
        "every_sibling_exactly_k",
        "every_block_contains_all_siblings",
        "fresh_workspace_required",
    ):
        if summary.get(key) is not True:
            raise VerifyError(f"summary gate false: {key}")
    if summary.get("adaptive_allocation_allowed") is not False:
        raise VerifyError("adaptive allocation must be false")

    verification = {
        "status": "VERIFIED_OUTCOME_BLIND_BALANCED_ASSIGNMENT",
        "result_sha256_manifest": digest(safe_read(root / "sha256_manifest.json")),
        "rollout_jobs": jobs,
        "anchor_count": anchor_count,
        "task_count": task_count,
        "siblings_per_anchor": siblings_per_anchor,
        "replicates_per_sibling": replicates,
        "continuation_horizon": horizon,
        "contains_outcomes": False,
        "independent_reconstruction_exact": True,
    }
    receipt.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt.with_name(receipt.name + f".tmp-{os.getpid()}")
    temporary.write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(receipt)
    print(canonical(verification))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", required=True)
    ap.add_argument("--receipt", required=True)
    try:
        return verify(ap.parse_args())
    except (VerifyError, OSError, json.JSONDecodeError) as exc:
        print(f"VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
