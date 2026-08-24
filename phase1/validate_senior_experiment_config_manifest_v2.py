#!/usr/bin/env python3
"""Validate a prompt-sensitive future senior config provenance overlay."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import phase1.senior_experiment_config_v2 as schema
import phase1.validate_senior_experiment_config_manifest as v1


PROTOCOL = schema.PROTOCOL


def independent_experiment_stratum_sha256(row: dict[str, Any]) -> str:
    payload = (
        row["task"],
        row["client"],
        row["generator_release"],
        row["hardware"],
        row["time_limit"],
        row["execution_timeout"],
        row["solver_projection_schema"],
        row["resolved_solver_config_sha256"],
    )
    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise v1.ContractError("v2 experiment stratum is not canonical JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def validate_config_rows(
    rows: list[dict[str, Any]], expected: dict[str, dict[str, str]]
) -> dict[str, dict[str, Any]]:
    v1.require_sorted_unique(rows, "v2 config provenance")
    configs: dict[str, dict[str, Any]] = {}
    for row in rows:
        run_id = row["run_id"]
        expected_row = expected.get(run_id)
        if expected_row is None:
            raise v1.ContractError("v2 config provenance contains an unexpected run_id")
        if row["task"] != expected_row["task"]:
            raise v1.ContractError("v2 config provenance task does not match expected run")
        for field in (
            "task",
            "client",
            "generator_release",
            "hardware",
            "solver_projection_schema",
        ):
            v1.public_value(row[field], field)
        if row["solver_projection_schema"] != schema.SOLVER_PROJECTION_SCHEMA:
            raise v1.ContractError("unknown solver projection schema")
        v1.positive_number(row["time_limit"], "time_limit")
        v1.positive_number(row["execution_timeout"], "execution_timeout")
        solver_hash = row["resolved_solver_config_sha256"]
        if not isinstance(solver_hash, str) or v1.SHA256_RE.fullmatch(solver_hash) is None:
            raise v1.ContractError("resolved_solver_config_sha256 is invalid")
        observed_hash = row["experiment_stratum_sha256"]
        if not isinstance(observed_hash, str) or v1.SHA256_RE.fullmatch(observed_hash) is None:
            raise v1.ContractError("experiment_stratum_sha256 is invalid")
        expected_hash = independent_experiment_stratum_sha256(row)
        if observed_hash != expected_hash:
            raise v1.ContractError("v2 experiment-stratum receipt mismatch")
        configs[run_id] = row
    if set(configs) != set(expected):
        raise v1.ContractError("v2 config provenance does not exactly cover expected runs")
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
    expected_path, _ = v1.checked_bytes(expected_runs_path, expected_runs_sha256)
    source_path, _ = v1.checked_bytes(source_manifest_path, source_manifest_sha256)
    receipt_path, receipt_raw = v1.checked_bytes(source_receipt_path, source_receipt_sha256)
    config_path, _ = v1.checked_bytes(config_manifest_path, config_manifest_sha256)

    expected_rows = v1.load_jsonl(expected_path, v1.EXPECTED_RUN_FIELDS)
    source_rows = v1.load_jsonl(source_path, v1.SOURCE_FIELDS)
    config_rows = v1.load_jsonl(config_path, schema.CONFIG_FIELDS)
    expected = v1.validate_expected_runs(expected_rows)
    source = v1.validate_source_rows(source_rows, expected)
    source_mapping = v1.rows_sha256(v1.source_canonical_rows(source))
    v1.validate_source_receipt(
        v1.load_json(receipt_path, receipt_raw),
        expected_runs_sha256=expected_runs_sha256,
        source_manifest_sha256=source_manifest_sha256,
        source_mapping_sha256=source_mapping,
    )
    configs = validate_config_rows(config_rows, expected)

    canonical_configs = [
        {field: configs[run_id][field] for field in sorted(schema.CONFIG_FIELDS)}
        for run_id in sorted(configs)
    ]
    joined_rows = []
    for run_id in sorted(configs):
        producer_stratum = hashlib.sha256(
            json.dumps(
                (
                    source[run_id]["producer_commit"],
                    configs[run_id]["experiment_stratum_sha256"],
                ),
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        joined_rows.append(
            {
                **configs[run_id],
                "batch_id": source[run_id]["batch_id"],
                "producer_commit": source[run_id]["producer_commit"],
                "producer_stratum_sha256": producer_stratum,
                "source_date": source[run_id]["source_date"],
            }
        )
    task_counts = Counter(row["task"] for row in canonical_configs)
    client_counts = Counter(row["client"] for row in canonical_configs)
    release_counts = Counter(row["generator_release"] for row in canonical_configs)
    hardware_counts = Counter(row["hardware"] for row in canonical_configs)
    solver_counts = Counter(row["resolved_solver_config_sha256"] for row in canonical_configs)
    unknown_fields = {
        field: sum(str(row[field]).casefold() == "unknown" for row in canonical_configs)
        for field in ("client", "generator_release", "hardware")
    }
    criteria = {
        "exact_v2_schema": True,
        "expected_run_coverage_complete": set(configs) == set(expected),
        "source_provenance_receipt_linked": True,
        "task_mismatches_eq_0": all(
            row["task"] == expected[row["run_id"]]["task"] for row in canonical_configs
        ),
        "resolved_solver_hashes_present": True,
        "prompt_sensitive_stratum_hashes_verified": True,
        "outcome_fields_present_eq_0": True,
    }
    if not all(criteria.values()):
        raise v1.ContractError("internal v2 criteria inconsistency")
    return {
        "protocol": PROTOCOL,
        "formal_status": "PROMPT_SENSITIVE_CONFIG_PROVENANCE_VERIFIED",
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
            "resolved_solver_configs": len(solver_counts),
            "producer_strata": len(
                {row["producer_stratum_sha256"] for row in joined_rows}
            ),
            "experiment_strata": len(
                {row["experiment_stratum_sha256"] for row in canonical_configs}
            ),
            "unknown_client_rows": unknown_fields["client"],
            "unknown_generator_release_rows": unknown_fields["generator_release"],
            "unknown_hardware_rows": unknown_fields["hardware"],
            "runs_per_task": dict(sorted(task_counts.items())),
            "runs_per_client": dict(sorted(client_counts.items())),
            "runs_per_generator_release": dict(sorted(release_counts.items())),
            "runs_per_hardware": dict(sorted(hardware_counts.items())),
        },
        "criteria": criteria,
        "interaction_metadata_complete": not any(unknown_fields.values()),
        "source_mapping_sha256": source_mapping,
        "config_mapping_sha256": v1.rows_sha256(canonical_configs),
        "joined_mapping_sha256": v1.rows_sha256(joined_rows),
        "access_attestation": {
            "archive_headers_read_by_this_validator": False,
            "tar_member_payloads_opened": False,
            "dojo_configs_opened_by_this_validator": False,
            "cards_pairs_predictions_or_outcomes_opened": False,
            "model_fit_gpu_or_api_used": False,
        },
    }


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
        v1.write_receipt(args.output, receipt)
    except (v1.ContractError, OSError) as exc:
        print(f"CONFIG_PROVENANCE_V2_FAIL type={type(exc).__name__}", file=os.sys.stderr)
        return 2
    print(
        "CONFIG_PROVENANCE_V2_PASS "
        f"runs={receipt['inventory']['config_rows']} "
        f"solver_configs={receipt['inventory']['resolved_solver_configs']} "
        f"joined_mapping_sha256={receipt['joined_mapping_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
