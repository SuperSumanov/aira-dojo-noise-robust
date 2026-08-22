#!/usr/bin/env python3
"""Validate a credential-safe run-to-experiment-config provenance overlay.

This validator composes with, rather than replaces, the source-provenance
contract.  It never reads archive payloads, Cards, code, stdout, grades, model
predictions, or pair orientation.  Its only scientific purpose is to bind each
already identified physical run to the exact public execution stratum used by
the future pair producer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


PROTOCOL = "senior-experiment-config-manifest-v1"
SOURCE_PROTOCOL = "senior-source-provenance-manifest-v1"
RUN_RE = re.compile(r"^(.+_seed_[0-9]+_id_[0-9a-f]+)__(\d{4}-\d{2}-\d{2})$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
PUBLIC_VALUE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+() @-]{0,199}$")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
EXPECTED_RUN_FIELDS = {
    "cards",
    "config_sha256",
    "curve_order_sha256",
    "dev_order_sha256",
    "original_hold",
    "role",
    "run_id",
    "task",
}
SOURCE_FIELDS = {
    "archive_path",
    "archive_sha256",
    "batch_id",
    "producer_commit",
    "run_id",
    "source_date",
    "task",
}
CONFIG_FIELDS = {
    "client",
    "execution_timeout",
    "experiment_stratum_sha256",
    "generator_release",
    "hardware",
    "run_id",
    "task",
    "time_limit",
}


class ContractError(RuntimeError):
    """Raised when the config-provenance composition must fail closed."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def rows_sha256(rows: Iterable[dict[str, Any]]) -> str:
    payload = "".join(canonical_json(row) + "\n" for row in rows).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def checked_bytes(path_value: str | Path, expected_sha256: str) -> tuple[Path, bytes]:
    if not isinstance(expected_sha256, str) or not SHA256_RE.fullmatch(expected_sha256):
        raise ContractError("expected input SHA-256 is invalid")
    input_path = Path(path_value)
    if input_path.is_symlink() or not input_path.is_file():
        raise ContractError(
            f"input is absent, symlinked, or non-regular: {input_path.name}"
        )
    path = input_path.resolve()
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise ContractError(f"credential-shaped bytes refused: {path.name}")
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ContractError(f"input SHA-256 mismatch: {path.name}")
    return path, raw


def load_jsonl(path: Path, exact_fields: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise ContractError(f"blank JSONL line at {path.name}:{line_number}")
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ContractError(f"invalid JSON at {path.name}:{line_number}") from exc
            if not isinstance(row, dict) or set(row) != exact_fields:
                raise ContractError(f"schema mismatch at {path.name}:{line_number}")
            rows.append(row)
    if not rows:
        raise ContractError(f"empty JSONL input: {path.name}")
    return rows


def load_json(path: Path, raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON input: {path.name}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON receipt must be an object: {path.name}")
    return value


def validate_expected_runs(rows: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    expected: dict[str, dict[str, str]] = {}
    for row in rows:
        run_id = row["run_id"]
        task = row["task"]
        if (
            not isinstance(run_id, str)
            or RUN_RE.fullmatch(run_id) is None
            or run_id in expected
        ):
            raise ContractError("expected run identity is invalid or duplicated")
        if not isinstance(task, str) or not task:
            raise ContractError("expected run task is invalid")
        expected[run_id] = {"run_id": run_id, "task": task}
    return expected


def require_sorted_unique(rows: list[dict[str, Any]], label: str) -> None:
    run_ids = [row.get("run_id") for row in rows]
    if not all(isinstance(run_id, str) for run_id in run_ids):
        raise ContractError(f"{label} run_id is invalid")
    if run_ids != sorted(run_ids):
        raise ContractError(f"{label} rows must be sorted by run_id")
    if len(set(run_ids)) != len(run_ids):
        raise ContractError(f"{label} run_id is duplicated")


def validate_source_rows(
    rows: list[dict[str, Any]], expected: dict[str, dict[str, str]]
) -> dict[str, dict[str, Any]]:
    require_sorted_unique(rows, "source provenance")
    source: dict[str, dict[str, Any]] = {}
    for row in rows:
        run_id = row["run_id"]
        expected_row = expected.get(run_id)
        if expected_row is None:
            raise ContractError("source provenance contains an unexpected run_id")
        if row["task"] != expected_row["task"]:
            raise ContractError("source provenance task does not match expected run")
        if not isinstance(row["producer_commit"], str) or not GIT_COMMIT_RE.fullmatch(
            row["producer_commit"]
        ):
            raise ContractError("source producer_commit is invalid")
        source[run_id] = row
    if set(source) != set(expected):
        raise ContractError("source provenance does not exactly cover expected runs")
    return source


def source_canonical_rows(source: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {field: source[run_id][field] for field in sorted(SOURCE_FIELDS)}
        for run_id in sorted(source)
    ]


def validate_source_receipt(
    receipt: dict[str, Any],
    *,
    expected_runs_sha256: str,
    source_manifest_sha256: str,
    source_mapping_sha256: str,
) -> None:
    if receipt.get("protocol") != SOURCE_PROTOCOL or receipt.get("formal_status") != "PROVENANCE_VERIFIED":
        raise ContractError("source receipt is not a verified v1 provenance receipt")
    inputs = receipt.get("inputs")
    if not isinstance(inputs, dict) or inputs.get("expected_runs_sha256") != expected_runs_sha256:
        raise ContractError("source receipt expected-runs binding mismatch")
    if inputs.get("provenance_manifest_sha256") != source_manifest_sha256:
        raise ContractError("source receipt provenance binding mismatch")
    if receipt.get("mapping_sha256") != source_mapping_sha256:
        raise ContractError("source receipt mapping binding mismatch")
    access = receipt.get("access_attestation")
    if (
        not isinstance(access, dict)
        or access.get("tar_member_payloads_opened") is not False
        or access.get("outcomes_or_grades_read") is not False
        or access.get("model_fit_or_gpu_used") is not False
    ):
        raise ContractError("source receipt access attestation is incompatible")


def public_value(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or value != value.strip()
        or PUBLIC_VALUE_RE.fullmatch(value) is None
    ):
        raise ContractError(f"{label} is not a credential-safe public identifier")
    return value


def positive_number(value: Any, label: str) -> int | float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or value <= 0
    ):
        raise ContractError(f"{label} must be a positive finite JSON number")
    return value


def experiment_stratum_sha256(row: dict[str, Any]) -> str:
    payload = json.dumps(
        (
            row["task"],
            row["client"],
            row["hardware"],
            row["time_limit"],
            row["execution_timeout"],
        ),
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_config_rows(
    rows: list[dict[str, Any]], expected: dict[str, dict[str, str]]
) -> dict[str, dict[str, Any]]:
    require_sorted_unique(rows, "config provenance")
    configs: dict[str, dict[str, Any]] = {}
    for row in rows:
        run_id = row["run_id"]
        expected_row = expected.get(run_id)
        if expected_row is None:
            raise ContractError("config provenance contains an unexpected run_id")
        if row["task"] != expected_row["task"]:
            raise ContractError("config provenance task does not match expected run")
        public_value(row["client"], "client")
        public_value(row["generator_release"], "generator_release")
        public_value(row["hardware"], "hardware")
        positive_number(row["time_limit"], "time_limit")
        positive_number(row["execution_timeout"], "execution_timeout")
        observed_hash = row["experiment_stratum_sha256"]
        if not isinstance(observed_hash, str) or not SHA256_RE.fullmatch(observed_hash):
            raise ContractError("experiment_stratum_sha256 is invalid")
        if observed_hash != experiment_stratum_sha256(row):
            raise ContractError("experiment-stratum receipt mismatch")
        configs[run_id] = row
    if set(configs) != set(expected):
        raise ContractError("config provenance does not exactly cover expected runs")
    return configs


def validate(
    expected_runs_path: str | Path,
    expected_runs_sha256: str,
    source_manifest_path: str | Path,
    source_manifest_sha256: str,
    source_receipt_path: str | Path,
    source_receipt_sha256: str,
    config_manifest_path: str | Path,
    config_manifest_sha256: str,
) -> dict[str, Any]:
    expected_path, _ = checked_bytes(expected_runs_path, expected_runs_sha256)
    source_path, _ = checked_bytes(source_manifest_path, source_manifest_sha256)
    receipt_path, receipt_raw = checked_bytes(source_receipt_path, source_receipt_sha256)
    config_path, _ = checked_bytes(config_manifest_path, config_manifest_sha256)

    expected_rows = load_jsonl(expected_path, EXPECTED_RUN_FIELDS)
    source_rows = load_jsonl(source_path, SOURCE_FIELDS)
    config_rows = load_jsonl(config_path, CONFIG_FIELDS)
    expected = validate_expected_runs(expected_rows)
    source = validate_source_rows(source_rows, expected)
    source_mapping = rows_sha256(source_canonical_rows(source))
    validate_source_receipt(
        load_json(receipt_path, receipt_raw),
        expected_runs_sha256=expected_runs_sha256,
        source_manifest_sha256=source_manifest_sha256,
        source_mapping_sha256=source_mapping,
    )
    configs = validate_config_rows(config_rows, expected)

    canonical_configs = [
        {field: configs[run_id][field] for field in sorted(CONFIG_FIELDS)}
        for run_id in sorted(configs)
    ]
    joined_rows = [
        {
            **canonical_configs[index],
            "batch_id": source[run_id]["batch_id"],
            "producer_commit": source[run_id]["producer_commit"],
            "source_date": source[run_id]["source_date"],
        }
        for index, run_id in enumerate(sorted(configs))
    ]
    task_counts = Counter(row["task"] for row in canonical_configs)
    client_counts = Counter(row["client"] for row in canonical_configs)
    release_counts = Counter(row["generator_release"] for row in canonical_configs)
    hardware_counts = Counter(row["hardware"] for row in canonical_configs)
    unknown_release_rows = sum(
        count for value, count in release_counts.items() if value.casefold() == "unknown"
    )
    unknown_client_rows = sum(
        count for value, count in client_counts.items() if value.casefold() == "unknown"
    )
    unknown_hardware_rows = sum(
        count for value, count in hardware_counts.items() if value.casefold() == "unknown"
    )
    criteria = {
        "exact_schema": True,
        "expected_run_coverage_complete": set(configs) == set(expected),
        "source_provenance_receipt_linked": True,
        "task_mismatches_eq_0": all(
            row["task"] == expected[row["run_id"]]["task"] for row in canonical_configs
        ),
        "credential_safe_public_values": True,
        "exact_stratum_hashes_verified": True,
        "outcome_fields_present_eq_0": True,
    }
    if not all(criteria.values()):
        raise ContractError("internal criteria inconsistency")
    return {
        "protocol": PROTOCOL,
        "formal_status": "CONFIG_PROVENANCE_VERIFIED",
        "inputs": {
            "expected_runs_sha256": expected_runs_sha256,
            "source_manifest_sha256": source_manifest_sha256,
            "source_receipt_sha256": source_receipt_sha256,
            "config_manifest_sha256": config_manifest_sha256,
        },
        "inventory": {
            "expected_runs": len(expected),
            "config_rows": len(canonical_configs),
            "tasks": len(task_counts),
            "clients": len(client_counts),
            "generator_releases": len(release_counts),
            "hardware_classes": len(hardware_counts),
            "experiment_strata": len(
                {row["experiment_stratum_sha256"] for row in canonical_configs}
            ),
            "unknown_client_rows": unknown_client_rows,
            "unknown_generator_release_rows": unknown_release_rows,
            "unknown_hardware_rows": unknown_hardware_rows,
            "runs_per_task": dict(sorted(task_counts.items())),
            "runs_per_client": dict(sorted(client_counts.items())),
            "runs_per_generator_release": dict(sorted(release_counts.items())),
            "runs_per_hardware": dict(sorted(hardware_counts.items())),
        },
        "criteria": criteria,
        "interaction_metadata_complete": (
            unknown_release_rows == 0
            and unknown_client_rows == 0
            and unknown_hardware_rows == 0
        ),
        "source_mapping_sha256": source_mapping,
        "config_mapping_sha256": rows_sha256(canonical_configs),
        "joined_mapping_sha256": rows_sha256(joined_rows),
        "access_attestation": {
            "archive_headers_read_by_this_validator": False,
            "tar_member_payloads_opened": False,
            "cards_or_pair_payloads_opened": False,
            "code_stdout_grades_predictions_opened": False,
            "model_fit_or_gpu_used": False,
        },
    }


def write_receipt(path_value: str | Path, receipt: dict[str, Any]) -> None:
    output_path = Path(path_value)
    if output_path.is_symlink():
        raise ContractError("output receipt path must not be a symlink")
    path = output_path.resolve()
    if path.exists():
        raise ContractError("output receipt already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    if temporary.exists():
        raise ContractError("temporary receipt path already exists")
    try:
        temporary.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-runs", required=True)
    parser.add_argument("--expect-runs-sha256", required=True)
    parser.add_argument("--source-provenance", required=True)
    parser.add_argument("--expect-source-provenance-sha256", required=True)
    parser.add_argument("--source-receipt", required=True)
    parser.add_argument("--expect-source-receipt-sha256", required=True)
    parser.add_argument("--config-provenance", required=True)
    parser.add_argument("--expect-config-provenance-sha256", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        receipt = validate(
            args.expected_runs,
            args.expect_runs_sha256,
            args.source_provenance,
            args.expect_source_provenance_sha256,
            args.source_receipt,
            args.expect_source_receipt_sha256,
            args.config_provenance,
            args.expect_config_provenance_sha256,
        )
        write_receipt(args.output, receipt)
    except (ContractError, OSError) as exc:
        print(f"CONFIG_PROVENANCE_CONTRACT_FAIL type={type(exc).__name__}", file=os.sys.stderr)
        return 2
    print(
        "CONFIG_PROVENANCE_CONTRACT_PASS "
        f"runs={receipt['inventory']['config_rows']} "
        f"strata={receipt['inventory']['experiment_strata']} "
        f"joined_mapping_sha256={receipt['joined_mapping_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
