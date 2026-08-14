"""Independent verifier for the zero-GPU real-adapter process-boundary smoke.

This verifier does not import the mock producer.  It may open sealed synthetic D_val receipts
only after the mock worker has terminated; the worker-visible receipts are reconstructed and
checked to contain D_search plus an opaque sealed-receipt commitment only.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import stat
from typing import Any

from phase1.balanced_continuation_real_contract import (
    RealContractError,
    bind_visible_step,
    build_operator_request,
    canonical_json,
    sha256_bytes,
    validate_execution_receipt,
    validate_operator_response,
    validate_search_receipt,
    validate_sealed_label_receipt,
    validate_visible_step,
    validate_worker_contract,
)


MOCK_SCHEMA = "balanced-continuation-real-adapter-mock-v1"
COMMITMENT_SCHEMA = "balanced-continuation-sealed-commitment-v1"
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class MockVerificationError(RuntimeError):
    pass


def checked_bytes(path: pathlib.Path) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise MockVerificationError(f"required regular file is absent or symlinked: {path}")
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise MockVerificationError(f"credential-shaped bytes refused before parse: {path}")
    return raw


def checked_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(checked_bytes(path))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MockVerificationError(f"invalid JSON: {path}") from exc


def exact_keys(value: Any, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = set(value) if isinstance(value, dict) else set()
        raise MockVerificationError(
            f"{where} keys differ: missing={sorted(keys - actual)} unknown={sorted(actual - keys)}"
        )
    return value


def verify(args: argparse.Namespace) -> dict[str, Any]:
    root = pathlib.Path(args.input)
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise MockVerificationError("input must be an absolute real directory")
    root = root.resolve()
    expected_top = {
        "public",
        "private_fixture",
        "workspace",
        "receipts",
        "sealed",
        "commitments",
        "operator",
        "logs",
        "split_manifest.json",
        "contract.json",
        "process_records.json",
        "summary.json",
    }
    actual_top = {path.name for path in root.iterdir()}
    if actual_top != expected_top or any(path.is_symlink() for path in root.iterdir()):
        raise MockVerificationError("mock artifact top-level membership differs")
    all_files = sorted(path for path in root.rglob("*") if path.is_file())
    if any(path.is_symlink() for path in all_files):
        raise MockVerificationError("mock artifact contains a symlinked file")
    for path in all_files:
        checked_bytes(path)

    contract = validate_worker_contract(checked_json(root / "contract.json"))
    split_manifest = exact_keys(
        checked_json(root / "split_manifest.json"),
        {"schema_version", "role", "dtest_materialized"},
        "mock split manifest",
    )
    if split_manifest != {
        "schema_version": "mock-80-10-10-split-manifest-v1",
        "role": "process-boundary-fixture-only",
        "dtest_materialized": False,
    }:
        raise MockVerificationError("mock split fixture differs")
    if sha256_bytes(canonical_json(split_manifest) + b"\n") != contract[
        "split_manifest_sha256_opaque"
    ]:
        raise MockVerificationError("mock split commitment differs")

    summary_keys = {
        "schema_version",
        "source_commit",
        "rollout_id",
        "workspace_token",
        "candidate_processes",
        "dsearch_processes",
        "dval_sealer_processes",
        "operator_processes",
        "operator_calls",
        "retry_count",
        "analyze_calls",
        "sealed_files_opened_by_worker",
        "gpu_jobs",
        "api_calls",
        "scientific_outcome_claimed",
        "process_record_count",
    }
    summary = exact_keys(checked_json(root / "summary.json"), summary_keys, "mock summary")
    expected_counts = {
        "candidate_processes": 2,
        "dsearch_processes": 2,
        "dval_sealer_processes": 2,
        "operator_processes": 1,
        "operator_calls": 1,
        "retry_count": 0,
        "analyze_calls": 0,
        "sealed_files_opened_by_worker": 0,
        "gpu_jobs": 0,
        "api_calls": 0,
        "scientific_outcome_claimed": False,
        "process_record_count": 7,
    }
    if summary["schema_version"] != MOCK_SCHEMA or any(
        summary[key] != value for key, value in expected_counts.items()
    ):
        raise MockVerificationError("mock summary counters or status differ")
    if summary["source_commit"] != contract["source_commit"]:
        raise MockVerificationError("summary source commit differs")

    records = checked_json(root / "process_records.json")
    if not isinstance(records, list) or len(records) != 7:
        raise MockVerificationError("process ledger must contain exactly seven sidecars")
    expected_labels = [
        "candidate_000",
        "dsearch_000",
        "dval_sealer_000",
        "operator_001",
        "candidate_001",
        "dsearch_001",
        "dval_sealer_001",
    ]
    private_text = str((root / "private_fixture").resolve())
    for ordinal, (record, expected_label) in enumerate(zip(records, expected_labels, strict=True)):
        record = exact_keys(
            record,
            {"ordinal", "label", "command", "return_code", "wall_time_seconds"},
            f"process record {ordinal}",
        )
        if (
            record["ordinal"] != ordinal
            or record["label"] != expected_label
            or record["return_code"] != 0
            or not isinstance(record["wall_time_seconds"], (int, float))
            or isinstance(record["wall_time_seconds"], bool)
            or record["wall_time_seconds"] <= 0
        ):
            raise MockVerificationError(f"process record {ordinal} differs")
        if not isinstance(record["command"], list) or not all(
            isinstance(part, str) for part in record["command"]
        ):
            raise MockVerificationError("process command is not a string vector")
        if expected_label.startswith("candidate_") and private_text in "\n".join(record["command"]):
            raise MockVerificationError("candidate command received the private fixture path")

    rollout_id = summary["rollout_id"]
    workspace_token = summary["workspace_token"]
    workspace_root = root / "workspace"
    workspace_entries = list(workspace_root.iterdir())
    if len(workspace_entries) != 1 or not workspace_entries[0].is_dir() or workspace_entries[0].is_symlink():
        raise MockVerificationError("expected exactly one fresh rollout workspace")
    workspace = workspace_entries[0]
    expected_workspace = {
        "code_000.py",
        "submission_000.csv",
        "code_001.py",
        "submission_001.csv",
    }
    if {path.name for path in workspace.iterdir()} != expected_workspace:
        raise MockVerificationError("rollout workspace membership differs")

    request = checked_json(root / "operator" / "request_001.json")
    response = checked_json(root / "operator" / "response_001.json")
    visible_rows: list[dict[str, Any]] = []
    sealed_mode_status = "0600" if os.name == "posix" else "WINDOWS_MODE_UNVERIFIABLE"
    for ordinal in range(2):
        execution = validate_execution_receipt(
            checked_json(root / "receipts" / f"execution_{ordinal:03d}.json"), contract
        )
        search = validate_search_receipt(
            checked_json(root / "receipts" / f"dsearch_{ordinal:03d}.json"), contract
        )
        sealed_path = root / "sealed" / f"dval_{ordinal:03d}.json"
        sealed = validate_sealed_label_receipt(checked_json(sealed_path), contract)
        if os.name == "posix" and stat.S_IMODE(sealed_path.stat().st_mode) != 0o600:
            raise MockVerificationError("sealed D_val receipt actual mode is not 0600")
        commitment = exact_keys(
            checked_json(root / "commitments" / f"sealed_{ordinal:03d}.json"),
            {
                "schema_version",
                "rollout_id",
                "workspace_token",
                "task",
                "execution_ordinal",
                "sealed_label_receipt_sha256",
            },
            f"sealed commitment {ordinal}",
        )
        if commitment["schema_version"] != COMMITMENT_SCHEMA:
            raise MockVerificationError("sealed commitment schema differs")
        identity = {
            "rollout_id": rollout_id,
            "workspace_token": workspace_token,
            "task": "mock-task",
            "execution_ordinal": ordinal,
        }
        if any(commitment[key] != value for key, value in identity.items()):
            raise MockVerificationError("sealed commitment identity differs")
        if commitment["sealed_label_receipt_sha256"] != sha256_bytes(checked_bytes(sealed_path)):
            raise MockVerificationError("sealed commitment hash differs")
        for key in ("rollout_id", "workspace_token", "task", "execution_ordinal", "artifact_sha256"):
            if execution[key] != search[key] or execution[key] != sealed[key]:
                raise MockVerificationError(f"cross-process identity differs: {key}")
        code = checked_bytes(workspace / f"code_{ordinal:03d}.py").decode("utf-8")
        expected_visible = bind_visible_step(
            execution,
            search,
            contract,
            stage="warm_start" if ordinal == 0 else "continuation",
            operator="none" if ordinal == 0 else response["operator"],
            code=code,
            sealed_label_receipt_sha256=commitment["sealed_label_receipt_sha256"],
        )
        visible = validate_visible_step(
            checked_json(root / "receipts" / f"visible_{ordinal:03d}.json"), contract
        )
        if visible != expected_visible or any("dval" in key.lower() for key in visible):
            raise MockVerificationError("worker-visible step differs or exposes D_val")
        visible_rows.append(visible)

    expected_request = build_operator_request(
        visible_rows[0],
        contract,
        task_description="Synthetic public-only mock task.",
        transition_index=1,
        operator_seed=1729,
    )
    if request != expected_request or any("dval" in key.lower() for key in request):
        raise MockVerificationError("one-shot operator request differs or exposes D_val")
    response = validate_operator_response(response, request, contract)
    if checked_bytes(workspace / "code_001.py").decode("utf-8") != response["code"]:
        raise MockVerificationError("operator response code was not executed exactly")

    receipt_files = {path.name for path in (root / "receipts").iterdir()}
    if receipt_files != {
        "execution_000.json",
        "execution_001.json",
        "dsearch_000.json",
        "dsearch_001.json",
        "visible_000.json",
        "visible_001.json",
    }:
        raise MockVerificationError("public receipt membership differs")
    result = {
        "status": "VERIFIED_ZERO_GPU_REAL_ADAPTER_MOCK",
        "source_commit": contract["source_commit"],
        "rollouts": 1,
        "candidate_processes": 2,
        "dsearch_processes": 2,
        "dval_sealer_processes": 2,
        "operator_processes": 1,
        "operator_calls": 1,
        "retries": 0,
        "visible_dval_fields": 0,
        "actual_sealed_mode": sealed_mode_status,
        "dtest_rows_read": 0,
        "gpu_jobs": 0,
        "api_calls": 0,
        "scientific_outcome_claimed": False,
        "files_scanned": len(all_files),
    }
    if args.output:
        output = pathlib.Path(args.output)
        if not output.is_absolute() or output.exists() or output.is_symlink():
            raise MockVerificationError("verification output must be a new absolute path")
        output.write_bytes(canonical_json(result) + b"\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        result = verify(args)
    except (MockVerificationError, RealContractError) as exc:
        raise SystemExit(f"REAL_ADAPTER_MOCK_VERIFY_FAILED: {exc}") from exc
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
