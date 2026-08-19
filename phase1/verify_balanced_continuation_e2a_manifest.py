"""Independently reconstruct and verify the E2-A variable-K assignment artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


RANDOMIZATION_PROTOCOL = "balanced-continuation-e2a-variable-k-v1"
ASSIGNMENT_PROTOCOL = "balanced-continuation-v1"
STATUS = "READY_FOR_OUTCOME_BLIND_E2A_COLLECTION"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
ANCHOR_KEYS = {
    "anchor_id", "task", "source_run_id", "parent_id", "sibling_id",
    "code_sha256", "anchor_contract_sha256",
}
CONTRACT_KEYS = {
    "schema_version", "model_id", "provider", "operator_config_sha256",
    "prompt_sha256", "source_commit", "dataset_contract_sha256",
    "evaluator_contract_sha256", "hardware_class", "execution_timeout_seconds",
    "continuation_horizon", "debug_policy", "workspace_policy", "temperature",
}
EXPECTED_FILES = {
    "anchors.input.jsonl", "calibration_anchor_ids.input.json",
    "execution_contract.input.json", "assignment_manifest.jsonl", "summary.json",
    "command.txt", "sha256_manifest.json",
}


class VerifyError(RuntimeError):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def safe_read(path: Path) -> bytes:
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise VerifyError(f"credential-shaped bytes in {path.name}")
    return raw


def require_string(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise VerifyError(f"invalid {key}")
    return result


def parse_anchors(raw: bytes) -> tuple[list[dict[str, str]], dict[str, list[dict[str, str]]]]:
    rows: list[dict[str, str]] = []
    for line_number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise VerifyError(f"invalid anchor JSON line {line_number}") from exc
        if not isinstance(value, dict) or set(value) != ANCHOR_KEYS:
            raise VerifyError("anchor schema mismatch")
        row = {key: require_string(value, key) for key in ANCHOR_KEYS}
        if not HEX64.fullmatch(row["code_sha256"]) or not HEX64.fullmatch(
            row["anchor_contract_sha256"]
        ):
            raise VerifyError("anchor hash mismatch")
        rows.append(row)
    if len(rows) != 48:
        raise VerifyError("E2-A requires 48 sibling rows")

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    contexts: dict[str, tuple[str, str, str, str]] = {}
    sibling_ids: set[str] = set()
    code_hashes: set[str] = set()
    source_runs: set[str] = set()
    for row in rows:
        if row["sibling_id"] in sibling_ids or row["code_sha256"] in code_hashes:
            raise VerifyError("duplicate sibling identity or exact code")
        sibling_ids.add(row["sibling_id"])
        code_hashes.add(row["code_sha256"])
        context = (
            row["task"], row["source_run_id"], row["parent_id"],
            row["anchor_contract_sha256"],
        )
        anchor_id = row["anchor_id"]
        if anchor_id in contexts and contexts[anchor_id] != context:
            raise VerifyError("anchor context mismatch")
        contexts[anchor_id] = context
        groups[anchor_id].append(row)
        source_runs.add(row["source_run_id"])
    if len(groups) != 24 or any(len(group) != 2 for group in groups.values()):
        raise VerifyError("E2-A requires 24 exact-two anchors")
    if len(source_runs) != 24:
        raise VerifyError("E2-A requires 24 distinct physical runs")
    task_counts = Counter(group[0]["task"] for group in groups.values())
    if len(task_counts) != 6 or set(task_counts.values()) != {4}:
        raise VerifyError("E2-A requires four anchors for each of six tasks")
    return rows, groups


def parse_calibration(raw: bytes, groups: dict[str, list[dict[str, str]]]) -> list[str]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise VerifyError("invalid calibration JSON") from exc
    if (
        not isinstance(value, list) or len(value) != 6 or len(set(value)) != 6
        or not all(isinstance(item, str) and HEX64.fullmatch(item) for item in value)
    ):
        raise VerifyError("calibration list must contain six unique SHA-256 IDs")
    if not set(value) <= set(groups):
        raise VerifyError("calibration anchor absent from anchors")
    tasks = [groups[anchor_id][0]["task"] for anchor_id in value]
    if len(set(tasks)) != 6:
        raise VerifyError("calibration list must contain one anchor per task")
    return value


def parse_contract(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise VerifyError("invalid execution contract JSON") from exc
    if not isinstance(value, dict) or set(value) != CONTRACT_KEYS:
        raise VerifyError("execution contract schema mismatch")
    for key in (
        "schema_version", "model_id", "provider", "hardware_class", "debug_policy",
        "workspace_policy",
    ):
        require_string(value, key)
    for key in (
        "operator_config_sha256", "prompt_sha256", "dataset_contract_sha256",
        "evaluator_contract_sha256",
    ):
        if not isinstance(value.get(key), str) or not HEX64.fullmatch(value[key]):
            raise VerifyError("execution contract hash mismatch")
    if not isinstance(value.get("source_commit"), str) or not HEX40.fullmatch(value["source_commit"]):
        raise VerifyError("execution contract source commit mismatch")
    if (
        value["schema_version"] != "balanced-continuation-contract-v1"
        or value["workspace_policy"] != "fresh_per_rollout"
        or value["debug_policy"] != "fixed_one_operator_per_step"
        or value.get("continuation_horizon") != 1
    ):
        raise VerifyError("frozen execution contract differs")
    timeout = value.get("execution_timeout_seconds")
    temperature = value.get("temperature")
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
        raise VerifyError("execution timeout invalid")
    if (
        isinstance(temperature, bool) or not isinstance(temperature, (int, float))
        or not 0 <= temperature <= 2
    ):
        raise VerifyError("temperature invalid")
    return value


def order_hash(seed: int, *parts: str) -> str:
    return digest("|".join((RANDOMIZATION_PROTOCOL, str(seed), *parts)).encode("utf-8"))


def derive_seed(seed: int, anchor_id: str, sibling_id: str, replicate: int) -> int:
    raw = (
        f"{RANDOMIZATION_PROTOCOL}|rollout-seed|{seed}|{anchor_id}|"
        f"{sibling_id}|{replicate}"
    ).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big") % (2**31 - 1)


def reconstruct(
    groups: dict[str, list[dict[str, str]]], calibration: set[str],
    contract_sha: str, seed: int,
) -> list[dict[str, Any]]:
    blocks = [(anchor_id, 0) for anchor_id in groups]
    blocks.extend((anchor_id, 1) for anchor_id in calibration)
    blocks.sort(key=lambda item: order_hash(seed, "block", item[0], str(item[1])))
    result: list[dict[str, Any]] = []
    seen_seeds: set[int] = set()
    seen_rollouts: set[str] = set()
    for anchor_id, replicate in blocks:
        siblings = sorted(
            groups[anchor_id],
            key=lambda row: order_hash(
                seed, "within-block", anchor_id, str(replicate), row["sibling_id"]
            ),
        )
        block_id = digest(
            f"{RANDOMIZATION_PROTOCOL}|block|{anchor_id}|{replicate}".encode("utf-8")
        )
        for position, row in enumerate(siblings):
            rollout_seed = derive_seed(seed, anchor_id, row["sibling_id"], replicate)
            rollout_id = digest((
                f"{RANDOMIZATION_PROTOCOL}|{contract_sha}|{anchor_id}|{row['sibling_id']}|"
                f"{row['code_sha256']}|{replicate}|{rollout_seed}"
            ).encode("utf-8"))
            if rollout_seed in seen_seeds or rollout_id in seen_rollouts:
                raise VerifyError("derived seed or rollout collision")
            seen_seeds.add(rollout_seed)
            seen_rollouts.add(rollout_id)
            result.append({
                "protocol": ASSIGNMENT_PROTOCOL,
                "rollout_id": rollout_id,
                "global_order": len(result),
                "block_id": block_id,
                "block_replicate": replicate,
                "position_within_block": position,
                "inclusion_probability": 1.0,
                "order_probability": 0.5,
                "anchor_id": anchor_id,
                "task": row["task"],
                "source_run_id": row["source_run_id"],
                "parent_id": row["parent_id"],
                "sibling_id": row["sibling_id"],
                "code_sha256": row["code_sha256"],
                "anchor_contract_sha256": row["anchor_contract_sha256"],
                "execution_contract_sha256": contract_sha,
                "rollout_seed": rollout_seed,
                "continuation_horizon": 1,
                "warm_start_executions": 1,
                "planned_continuation_executions": 1,
            })
    return result


def verify(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.result).resolve()
    receipt = Path(args.receipt).resolve()
    temporary = receipt.with_name(receipt.name + f".tmp-{os.getpid()}")
    if receipt.exists() or receipt.is_symlink() or temporary.exists() or temporary.is_symlink():
        raise VerifyError("receipt path must not pre-exist")
    if not root.is_dir() or root.is_symlink():
        raise VerifyError("result root missing or symlinked")
    files = {path.name for path in root.iterdir() if path.is_file()}
    if files != EXPECTED_FILES:
        raise VerifyError(f"artifact file set mismatch: {sorted(files)}")

    hash_manifest_raw = safe_read(root / "sha256_manifest.json")
    stored_hashes = json.loads(hash_manifest_raw)
    hash_names = EXPECTED_FILES - {"sha256_manifest.json"}
    if not isinstance(stored_hashes, dict) or set(stored_hashes) != hash_names:
        raise VerifyError("hash manifest key mismatch")
    for name in hash_names:
        if stored_hashes[name] != digest(safe_read(root / name)):
            raise VerifyError(f"artifact hash mismatch: {name}")

    anchor_raw = safe_read(root / "anchors.input.jsonl")
    calibration_raw = safe_read(root / "calibration_anchor_ids.input.json")
    contract_raw = safe_read(root / "execution_contract.input.json")
    _, groups = parse_anchors(anchor_raw)
    calibration = parse_calibration(calibration_raw, groups)
    contract = parse_contract(contract_raw)
    contract_sha = digest(contract_raw)

    summary = json.loads(safe_read(root / "summary.json"))
    integer_fields = {
        "seed", "task_count", "anchor_count", "physical_run_count",
        "siblings_per_anchor", "broad_replicates", "calibration_anchor_count",
        "calibration_replicates", "continuation_horizon", "rollout_jobs",
        "planned_warm_start_executions", "planned_continuation_executions",
        "planned_total_candidate_executions", "planned_operator_api_calls",
    }
    if not isinstance(summary, dict) or any(
        isinstance(summary.get(key), bool) or not isinstance(summary.get(key), int)
        for key in integer_fields
    ):
        raise VerifyError("summary integer schema mismatch")
    if (
        summary.get("protocol") != RANDOMIZATION_PROTOCOL
        or summary.get("assignment_protocol") != ASSIGNMENT_PROTOCOL
        or summary.get("status") != STATUS
        or summary.get("contains_outcomes") is not False
        or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", str(summary.get("created_utc"))
        )
    ):
        raise VerifyError("summary status or timestamp mismatch")
    seed = summary["seed"]
    if seed < 0:
        raise VerifyError("negative assignment seed")

    expected = reconstruct(groups, set(calibration), contract_sha, seed)
    expected_raw = "".join(canonical(row) + "\n" for row in expected).encode("utf-8")
    if safe_read(root / "assignment_manifest.jsonl") != expected_raw:
        raise VerifyError("assignment manifest differs from independent reconstruction")

    sibling_counts = Counter(row["sibling_id"] for row in expected)
    block_counts = Counter(row["block_id"] for row in expected)
    calibration_siblings = {
        row["sibling_id"] for anchor_id in calibration for row in groups[anchor_id]
    }
    expected_summary = {
        "anchors_input_sha256": digest(anchor_raw),
        "calibration_anchor_ids_sha256": digest(calibration_raw),
        "execution_contract_sha256": contract_sha,
        "source_commit": contract["source_commit"],
        "task_count": 6,
        "anchor_count": 24,
        "physical_run_count": 24,
        "siblings_per_anchor": 2,
        "broad_replicates": 1,
        "calibration_anchor_count": 6,
        "calibration_replicates": 2,
        "continuation_horizon": 1,
        "rollout_jobs": 60,
        "planned_warm_start_executions": 60,
        "planned_continuation_executions": 60,
        "planned_total_candidate_executions": 120,
        "planned_operator_api_calls": 60,
    }
    for key, value in expected_summary.items():
        if summary.get(key) != value:
            raise VerifyError(f"summary mismatch: {key}")
    for key in (
        "every_sibling_at_least_once", "calibration_siblings_exactly_twice",
        "every_block_contains_all_siblings", "fresh_workspace_required",
    ):
        if summary.get(key) is not True:
            raise VerifyError(f"summary gate false: {key}")
    if summary.get("adaptive_allocation_allowed") is not False:
        raise VerifyError("adaptive allocation must be false")
    if (
        len(expected) != 60 or len(block_counts) != 30 or set(block_counts.values()) != {2}
        or len(sibling_counts) != 48
        or Counter(sibling_counts.values()) != Counter({1: 36, 2: 12})
        or any(sibling_counts[item] != 2 for item in calibration_siblings)
    ):
        raise VerifyError("variable-K exposure reconstruction differs")

    result = {
        "status": "VERIFIED_E2A_OUTCOME_BLIND_VARIABLE_K_ASSIGNMENT",
        "result_sha256_manifest": digest(hash_manifest_raw),
        "rollout_jobs": 60,
        "planned_total_candidate_executions": 120,
        "planned_operator_api_calls": 60,
        "anchor_count": 24,
        "physical_run_count": 24,
        "task_count": 6,
        "block_count": 30,
        "siblings_once": 36,
        "siblings_twice": 12,
        "contains_outcomes": False,
        "producer_imported": False,
        "independent_reconstruction_exact": True,
    }
    receipt.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, receipt)
    print(canonical(result))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True)
    parser.add_argument("--receipt", required=True)
    try:
        verify(parser.parse_args())
    except (VerifyError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"VERIFY_E2A_MANIFEST_ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
