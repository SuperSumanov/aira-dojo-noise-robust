"""Independently verify the two-result Qwen execution-only smoke archive."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
import os
import pathlib
import re
import sys
import tempfile
from itertools import zip_longest
from typing import Any


SCHEMA = "balanced-continuation-qwen-execution-smoke-v1"
PROBE_SCHEMA = "balanced-continuation-operator-conformance-probe-v1"
PROBE_SHA256 = "a30aa463a75ead9fa48fcd53a37921749425ac4a8ee696b18c2d0be33413ed1d"
MODEL_ID = "qwen3-coder-flash"
TASKS = ("spaceship-titanic", "tabular-playground-series-may-2022")
HEX64 = re.compile(r"[0-9a-f]{64}")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class VerifyError(RuntimeError):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_digest(path: pathlib.Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read_json(path: pathlib.Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise VerifyError(f"credential-shaped bytes in {path.name}")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise VerifyError(f"expected object in {path.name}")
    return value


def atomic_json(path: pathlib.Path, value: Any) -> None:
    if path.exists() or path.is_symlink():
        raise VerifyError("verification receipt must be new")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = pathlib.Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(
                value,
                handle,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def extract_code(raw_response: str, previous_code: str) -> str:
    exact = re.fullmatch(
        r"```python\s*\n(.*?)\n```",
        raw_response.strip(),
        flags=re.DOTALL | re.IGNORECASE,
    )
    if exact is None or "```" in (exact.group(1) if exact else ""):
        raise VerifyError("raw response is not exactly one Python block")
    code = exact.group(1).strip() + "\n"
    minimum_chars = max(512, min(4096, len(previous_code) // 4))
    if len(code) < minimum_chars or len(code.splitlines()) < 20:
        raise VerifyError("independently extracted code is too short")
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise VerifyError("independently extracted code has invalid syntax") from exc
    if any(isinstance(node, ast.Constant) and node.value is Ellipsis for node in ast.walk(tree)):
        raise VerifyError("independently extracted code contains Ellipsis")
    if any(
        marker not in code
        for marker in ("read_csv", "submission.csv", "to_csv", "FINAL_VALIDATION_SCORE")
    ):
        raise VerifyError("independently extracted code lacks end-to-end markers")
    return code


def validate_shape(sample: pathlib.Path, candidate: pathlib.Path) -> dict[str, Any]:
    with sample.open("r", encoding="utf-8-sig", newline="") as expected_handle:
        with candidate.open("r", encoding="utf-8-sig", newline="") as actual_handle:
            expected_reader = csv.reader(expected_handle)
            actual_reader = csv.reader(actual_handle)
            header = next(expected_reader, None)
            if not header or next(actual_reader, None) != header or len(header) < 2:
                raise VerifyError("submission header differs")
            rows = 0
            for expected, actual in zip_longest(expected_reader, actual_reader):
                if expected is None or actual is None:
                    raise VerifyError("submission row count differs")
                if len(actual) != len(header) or not expected or actual[0] != expected[0]:
                    raise VerifyError("submission ID sequence differs")
                for value in actual[1:]:
                    if not math.isfinite(float(value)):
                        raise VerifyError("submission prediction is non-finite")
                rows += 1
    return {"valid": True, "reason": "ok", "rows": rows, "columns": header}


def verify(args: argparse.Namespace) -> dict[str, Any]:
    source_root = pathlib.Path(args.source_root).resolve()
    source_run = pathlib.Path(args.source_run_root).resolve()
    probe = pathlib.Path(args.probe_root).resolve()
    output = pathlib.Path(args.output_root).resolve()
    workspace = pathlib.Path(args.workspace_root).resolve()
    job_rc_root = pathlib.Path(args.job_rc_root).resolve()
    receipt = pathlib.Path(args.receipt).resolve()
    for path, label in (
        (source_root, "source"),
        (source_run, "source run"),
        (probe, "probe"),
        (output, "output"),
        (workspace, "workspace"),
        (job_rc_root, "job rc"),
    ):
        if not path.is_dir() or path.is_symlink():
            raise VerifyError(f"{label} directory differs")
    if {path.name for path in output.iterdir()} != {"index_0", "index_1"}:
        raise VerifyError("smoke output index set differs")
    if {path.name for path in workspace.iterdir()} != {"index_0", "index_1"}:
        raise VerifyError("smoke workspace index set differs")
    probe_summary_path = probe / "summary.json"
    if file_digest(probe_summary_path) != PROBE_SHA256:
        raise VerifyError("probe summary SHA differs")
    probe_summary = read_json(probe_summary_path)
    records = probe_summary.get("records")
    if (
        probe_summary.get("schema_version") != PROBE_SCHEMA
        or probe_summary.get("status") != "PASS_OPERATOR_ONLY_GATE"
        or probe_summary.get("model_id") != MODEL_ID
        or not isinstance(records, list)
        or len(records) != 2
    ):
        raise VerifyError("probe summary differs")

    summaries: list[dict[str, Any]] = []
    for index, task in enumerate(TASKS):
        job_rc = read_json(job_rc_root / f"{index}.json")
        if (
            job_rc.get("index") != index
            or job_rc.get("producer_rc") != 0
            or job_rc.get("safety_rc") != 0
            or not isinstance(job_rc.get("slurm_job_id"), str)
            or not job_rc["slurm_job_id"]
        ):
            raise VerifyError(f"job rc differs at index {index}")
        root = output / f"index_{index}"
        step = root / "step"
        summary = read_json(root / "summary.json")
        record = records[index]
        raw = read_json(probe / f"call_{index:02d}.raw.json")
        rollout_id = record.get("rollout_id")
        if (
            summary.get("schema_version") != SCHEMA
            or summary.get("index") != index
            or summary.get("task") != task
            or summary.get("model_id") != MODEL_ID
            or summary.get("source_rollout_id") != rollout_id
            or summary.get("probe_summary_sha256") != PROBE_SHA256
            or summary.get("raw_response_sha256") != record.get("raw_response_sha256")
            or summary.get("prompt_sha256") != record.get("prompt_sha256")
            or summary.get("candidate_executions") != 1
            or summary.get("api_calls") != 0
            or summary.get("operator_retries") != 0
            or summary.get("candidate_retries") != 0
            or summary.get("dsearch_rows_read") != 0
            or summary.get("dval_rows_read") != 0
            or summary.get("dtest_rows_read") != 0
            or summary.get("first960_or_prospective_read") is not False
            or summary.get("external_score_or_gain_reported") is not False
            or summary.get("public_data_read_only") is not True
            or summary.get("private_paths_mounted") is not False
            or summary.get("source_warm_status") != "ok"
        ):
            raise VerifyError(f"summary contract differs at index {index}")
        source = source_run / "worker_outputs" / str(rollout_id)
        archived = read_json(source / "steps" / "step_001" / "operator_request.json")
        previous = archived.get("previous_code")
        response_text = raw.get("raw_response")
        if (
            not isinstance(previous, str)
            or not isinstance(response_text, str)
            or digest(response_text.encode("utf-8")) != record.get("raw_response_sha256")
        ):
            raise VerifyError("raw/source response binding differs")
        code = extract_code(response_text, previous)
        if (
            digest(code.encode("utf-8")) != summary.get("code_sha256")
            or file_digest(step / "code.py") != summary.get("code_sha256")
        ):
            raise VerifyError("executed code differs")
        execution = read_json(step / "execution.json")
        process = read_json(step / "candidate_process.json")
        command = process.get("command")
        if (
            execution.get("rollout_id") != summary.get("smoke_rollout_id")
            or execution.get("task") != task
            or execution.get("execution_ordinal") != 1
            or execution.get("code_sha256") != summary.get("code_sha256")
            or execution.get("execution_status") != summary.get("execution_status")
            or execution.get("process_started") is not True
            or execution.get("candidate_execution_attempted") is not True
            or execution.get("retry_count") != 0
            or execution.get("public_data_read_only") is not True
            or execution.get("private_paths_mounted") is not False
            or not isinstance(command, list)
            or "--containall" not in command
            or "--cleanenv" not in command
            or "--network" not in command
            or "none" not in command
        ):
            raise VerifyError("candidate execution receipt differs")
        passed = summary.get("gate_pass") is True
        if passed:
            artifact = step / "submission.csv"
            sample = pathlib.Path(
                read_json(source / "real_contract.json")["public_data_root"]
            ) / task / "sample_submission.csv"
            shape = validate_shape(sample, artifact)
            if (
                summary.get("status") != "PASS_EXECUTION_ONLY"
                or summary.get("execution_status") != "ok"
                or summary.get("artifact_sha256") != file_digest(artifact)
                or summary.get("submission_shape") != shape
            ):
                raise VerifyError("passing candidate artifact differs")
        elif summary.get("status") != "FAIL_EXECUTION_ONLY":
            raise VerifyError("failed candidate status differs")
        forbidden = [
            path for path in root.rglob("*")
            if path.is_file() and re.search(r"(?i)(dsearch|dval|dtest|score|gain|utility)", path.name)
        ]
        if forbidden:
            raise VerifyError("score-bearing artifact found in execution-only output")
        summaries.append(summary)

    passed = all(summary["gate_pass"] for summary in summaries)
    result = {
        "schema_version": "balanced-continuation-qwen-execution-smoke-verification-v1",
        "status": (
            "VERIFIED_QWEN_EXECUTION_SMOKE_PASS"
            if passed
            else "VERIFIED_QWEN_EXECUTION_SMOKE_FAIL"
        ),
        "producer_imported": False,
        "results": 2,
        "tasks": list(TASKS),
        "candidate_executions": 2,
        "api_calls": 0,
        "dsearch_rows_read": 0,
        "dval_rows_read": 0,
        "dtest_rows_read": 0,
        "external_score_or_gain_reported": False,
        "all_gate_pass": passed,
        "summary_sha256": [
            file_digest(output / f"index_{index}" / "summary.json")
            for index in range(2)
        ],
    }
    atomic_json(receipt, result)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return result


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-root", required=True)
    ap.add_argument("--source-run-root", required=True)
    ap.add_argument("--probe-root", required=True)
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--job-rc-root", required=True)
    ap.add_argument("--receipt", required=True)
    return ap


def main() -> int:
    try:
        verify(parser().parse_args())
    except (VerifyError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"QWEN_EXECUTION_SMOKE_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
