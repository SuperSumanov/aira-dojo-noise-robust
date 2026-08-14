"""Two-call, zero-GPU conformance gate for a repaired E1 operator.

The probe selects one successful warm-start artifact per task by rollout-id only, renders
the strict complete-script prompt, and checks response shape without executing generated
code.  Raw responses remain mode 0600 outside Git; only the compact summary is publishable.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import pathlib
import time
from typing import Any, Callable

from phase1.balanced_continuation_e1_scoring import (
    CREDENTIAL,
    atomic_json,
    canonical_json,
    checked_json,
    file_sha256,
    sha256_bytes,
)
from phase1.balanced_continuation_operator_entry import (
    assess_single_complete_code,
    render_prompt,
)


SCHEMA = "balanced-continuation-operator-conformance-probe-v1"
MODEL_ID = "qwen3-coder-flash"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
KEY_ENV = "PRIMARY_KEY_QWEN3_CODER_FLASH"
MAX_OUTPUT_TOKENS = 8192
TEMPERATURE = 0.0
EXPECTED_TASKS = ("spaceship-titanic", "tabular-playground-series-may-2022")


class ProbeError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def select_requests(run_root: pathlib.Path) -> list[dict[str, Any]]:
    final_status = checked_json(run_root / "final_status.json")
    if (
        final_status.get("status") != "VERIFIED_COMPLETE_REAL_E1_COLLECTION"
        or final_status.get("collection_rc") != 0
    ):
        raise ProbeError("source E1 run is not a verified complete collection")
    eligible: dict[str, list[tuple[str, pathlib.Path]]] = {task: [] for task in EXPECTED_TASKS}
    for result_path in sorted((run_root / "worker_outputs").glob("*/result.json")):
        result = checked_json(result_path)
        task = result.get("task")
        rollout_id = result.get("rollout_id")
        if task not in eligible or not isinstance(rollout_id, str):
            continue
        step0 = result_path.parent / "steps" / "step_000"
        execution = checked_json(step0 / "execution.json")
        if execution.get("execution_status") == "ok" and (step0 / "submission.csv").is_file():
            eligible[task].append((rollout_id, result_path.parent))
    selected: list[dict[str, Any]] = []
    for task in EXPECTED_TASKS:
        if not eligible[task]:
            raise ProbeError(f"no successful warm-start artifact for {task}")
        rollout_id, root = sorted(eligible[task], key=lambda value: value[0])[0]
        archived = checked_json(root / "steps" / "step_001" / "operator_request.json")
        # The frozen v1 evaluator mislabeled every warm start as buggy.  The probe only
        # changes the action word to the repaired-path action; render_prompt reads no score.
        prompt_request = {**archived, "operator": "improve", "previous_is_buggy": False}
        selected.append({
            "task": task,
            "rollout_id": rollout_id,
            "selection_rule": "lexicographically_first_successful_warm_artifact",
            "archived_request_sha256": sha256_bytes(canonical_json(archived)),
            "previous_code_sha256": archived.get("previous_code_sha256"),
            "prompt_request": prompt_request,
        })
    return selected


def call_qwen(prompt: str) -> dict[str, Any]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ProbeError("OpenAI SDK unavailable") from exc
    credential = os.environ.get(KEY_ENV)
    if not credential:
        raise ProbeError("Qwen credential unavailable in remote environment")
    client = OpenAI(api_key=credential, base_url=BASE_URL, max_retries=0, timeout=240.0)
    started = time.monotonic()
    completion = client.chat.completions.create(
        model=MODEL_ID,
        messages=[{"role": "user", "content": prompt}],
        temperature=TEMPERATURE,
        max_tokens=MAX_OUTPUT_TOKENS,
        extra_body={"enable_thinking": False},
    )
    latency = time.monotonic() - started
    choice = completion.choices[0]
    message = choice.message
    content = message.content or ""
    usage = getattr(completion, "usage", None)
    return {
        "content": content,
        "provider_request_id": getattr(completion, "id", None),
        "finish_reason": getattr(choice, "finish_reason", None),
        "latency_seconds": latency,
        "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
        "completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
        "total_tokens": getattr(usage, "total_tokens", None) if usage else None,
    }


def run(
    args: argparse.Namespace,
    caller: Callable[[str], dict[str, Any]] = call_qwen,
) -> dict[str, Any]:
    run_root = pathlib.Path(args.run_root).resolve()
    output_root = pathlib.Path(args.output_root).resolve()
    if not run_root.is_dir() or output_root.exists() or output_root.is_symlink():
        raise ProbeError("run root missing or output root already exists")
    output_root.mkdir(parents=True)
    if os.name == "posix":
        os.chmod(output_root, 0o700)
    selected = select_requests(run_root)
    records: list[dict[str, Any]] = []
    for index, item in enumerate(selected):
        prompt = render_prompt(item["prompt_request"])
        if CREDENTIAL.search(prompt.encode("utf-8")):
            raise ProbeError("credential-shaped bytes in rendered prompt")
        intent = {
            "schema_version": SCHEMA,
            "call_index": index,
            "task": item["task"],
            "rollout_id": item["rollout_id"],
            "model_id": MODEL_ID,
            "base_url_sha256": sha256_bytes(BASE_URL.encode("utf-8")),
            "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "temperature": TEMPERATURE,
            "enable_thinking": False,
            "sdk_retries": 0,
            "semantic_retries": 0,
            "candidate_execution_planned": False,
            "created_utc": utc_now(),
        }
        atomic_json(output_root / f"call_{index:02d}.intent.json", intent, mode=0o600)
        response = caller(prompt)
        content = response.get("content")
        if not isinstance(content, str):
            raise ProbeError("provider response content is not text")
        if CREDENTIAL.search(content.encode("utf-8")):
            raise ProbeError("credential-shaped bytes in provider response")
        code, conformance = assess_single_complete_code(
            content, item["prompt_request"]["previous_code"]
        )
        raw_document = {
            "schema_version": SCHEMA,
            "call_index": index,
            "task": item["task"],
            "rollout_id": item["rollout_id"],
            "prompt_sha256": intent["prompt_sha256"],
            "raw_response_sha256": sha256_bytes(content.encode("utf-8")),
            "raw_response": content,
        }
        atomic_json(output_root / f"call_{index:02d}.raw.json", raw_document, mode=0o600)
        completion_tokens = response.get("completion_tokens")
        at_token_cap = completion_tokens == MAX_OUTPUT_TOKENS
        usage_complete = all(
            isinstance(response.get(key), int) and not isinstance(response.get(key), bool)
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        )
        records.append({
            "call_index": index,
            "task": item["task"],
            "rollout_id": item["rollout_id"],
            "selection_rule": item["selection_rule"],
            "archived_request_sha256": item["archived_request_sha256"],
            "previous_code_sha256": item["previous_code_sha256"],
            "prompt_sha256": intent["prompt_sha256"],
            "raw_response_sha256": raw_document["raw_response_sha256"],
            "provider_request_id": response.get("provider_request_id"),
            "finish_reason": response.get("finish_reason"),
            "latency_seconds": response.get("latency_seconds"),
            "prompt_tokens": response.get("prompt_tokens"),
            "completion_tokens": completion_tokens,
            "total_tokens": response.get("total_tokens"),
            "at_output_token_cap": at_token_cap,
            "usage_complete": usage_complete,
            "raw_response_chars": len(content),
            "extracted_code_chars": len(code),
            "extracted_code_lines": len(code.splitlines()) if code else 0,
            "conformance_status": conformance,
            "gate_pass": (
                conformance == "ok"
                and response.get("finish_reason") == "stop"
                and usage_complete
                and not at_token_cap
            ),
        })
    passed = len(records) == len(EXPECTED_TASKS) and all(record["gate_pass"] for record in records)
    summary = {
        "schema_version": SCHEMA,
        "status": "PASS_OPERATOR_ONLY_GATE" if passed else "FAIL_OPERATOR_ONLY_GATE",
        "source_run_root": str(run_root),
        "probe_source_sha256": file_sha256(pathlib.Path(__file__).resolve()),
        "model_id": MODEL_ID,
        "base_url_sha256": sha256_bytes(BASE_URL.encode("utf-8")),
        "temperature": TEMPERATURE,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "enable_thinking": False,
        "api_calls": len(records),
        "sdk_retries": 0,
        "semantic_retries": 0,
        "gpu_jobs_started": 0,
        "candidate_executions": 0,
        "raw_responses_mode_0600": os.name != "posix" or all(
            (output_root / f"call_{index:02d}.raw.json").stat().st_mode & 0o777 == 0o600
            for index in range(len(records))
        ),
        "records": records,
        "method_claim_allowed": False,
        "repair_e1_engineering_gate_passed": passed,
        "new_gpu_budget_still_required": True,
        "e2_e3_unlocked": False,
    }
    atomic_json(output_root / "summary.json", summary, mode=0o600)
    return summary


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-root", required=True)
    ap.add_argument("--output-root", required=True)
    return ap


def main() -> int:
    try:
        summary = run(parser().parse_args())
    except (ProbeError, OSError, ValueError) as exc:
        print(f"OPERATOR_CONFORMANCE_PROBE_ERROR: {exc}")
        return 2
    print(
        "OPERATOR_CONFORMANCE_PROBE_DONE "
        f"status={summary['status']} calls={summary['api_calls']} "
        "gpu_jobs=0 method_claim_allowed=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
