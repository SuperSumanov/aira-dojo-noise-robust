"""Production-matched two-call DeepSeek conformance gate for repaired E1 prompts."""

from __future__ import annotations

import argparse
import os
import pathlib
import time
from typing import Any, Callable

from phase1.balanced_continuation_e1_scoring import (
    CREDENTIAL,
    atomic_json,
    file_sha256,
    sha256_bytes,
)
from phase1.balanced_continuation_operator_conformance_probe import (
    EXPECTED_TASKS,
    select_requests,
    utc_now,
)
from phase1.balanced_continuation_operator_entry import (
    BASE_URL,
    MAX_OUTPUT_TOKENS,
    MODEL_ID,
    TEMPERATURE,
    TOP_P,
    assess_single_complete_code,
    render_prompt,
)


SCHEMA = "balanced-continuation-deepseek-production-conformance-v1"
KEY_ENV = "PRIMARY_KEY_DEEPSEEK_V4_FLASH"


class ProductionProbeError(RuntimeError):
    pass


def assert_production_profile() -> None:
    expected = {
        "model_id": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com",
        "temperature": 0.6,
        "top_p": 0.95,
        "max_output_tokens": 8192,
    }
    actual = {
        "model_id": MODEL_ID,
        "base_url": BASE_URL,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }
    if actual != expected:
        raise ProductionProbeError("production operator profile differs from preregistration")


def call_deepseek(prompt: str) -> dict[str, Any]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ProductionProbeError("OpenAI SDK unavailable") from exc
    credential = os.environ.get(KEY_ENV)
    if not credential:
        raise ProductionProbeError("DeepSeek credential unavailable in remote environment")
    client = OpenAI(api_key=credential, base_url=BASE_URL, max_retries=0, timeout=180.0)
    started = time.monotonic()
    completion = client.chat.completions.create(
        model=MODEL_ID,
        messages=[{"role": "system", "content": prompt}],
        temperature=TEMPERATURE,
        top_p=TOP_P,
        max_tokens=MAX_OUTPUT_TOKENS,
    )
    latency = time.monotonic() - started
    choice = completion.choices[0]
    message = choice.message
    content = message.content or ""
    reasoning = getattr(message, "reasoning_content", None) or ""
    raw_response = content if content else reasoning
    usage = getattr(completion, "usage", None)
    return {
        "content": raw_response,
        "response_channel": "content" if content else "reasoning_content",
        "provider_request_id": getattr(completion, "id", None),
        "finish_reason": getattr(choice, "finish_reason", None),
        "latency_seconds": latency,
        "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
        "completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
        "total_tokens": getattr(usage, "total_tokens", None) if usage else None,
    }


def run(
    args: argparse.Namespace,
    caller: Callable[[str], dict[str, Any]] = call_deepseek,
) -> dict[str, Any]:
    assert_production_profile()
    run_root = pathlib.Path(args.run_root).resolve()
    output_root = pathlib.Path(args.output_root).resolve()
    if not run_root.is_dir() or output_root.exists() or output_root.is_symlink():
        raise ProductionProbeError("run root missing or output root already exists")
    output_root.mkdir(parents=True)
    if os.name == "posix":
        os.chmod(output_root, 0o700)
    selected = select_requests(run_root)
    records: list[dict[str, Any]] = []
    for index, item in enumerate(selected):
        prompt = render_prompt(item["prompt_request"])
        if CREDENTIAL.search(prompt.encode("utf-8")):
            raise ProductionProbeError("credential-shaped bytes in rendered prompt")
        intent = {
            "schema_version": SCHEMA,
            "call_index": index,
            "task": item["task"],
            "rollout_id": item["rollout_id"],
            "model_id": MODEL_ID,
            "base_url_sha256": sha256_bytes(BASE_URL.encode("utf-8")),
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "message_role": "system",
            "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
            "sdk_retries": 0,
            "semantic_retries": 0,
            "candidate_execution_planned": False,
            "created_utc": utc_now(),
        }
        atomic_json(output_root / f"call_{index:02d}.intent.json", intent, mode=0o600)
        response = caller(prompt)
        content = response.get("content")
        if not isinstance(content, str):
            raise ProductionProbeError("provider response content is not text")
        if CREDENTIAL.search(content.encode("utf-8")):
            raise ProductionProbeError("credential-shaped bytes in provider response")
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
        usage_complete = all(
            isinstance(response.get(key), int) and not isinstance(response.get(key), bool)
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        )
        at_token_cap = completion_tokens == MAX_OUTPUT_TOKENS
        gate_pass = (
            conformance == "ok"
            and response.get("finish_reason") == "stop"
            and usage_complete
            and not at_token_cap
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
            "response_channel": response.get("response_channel"),
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
            "gate_pass": gate_pass,
        })
    passed = len(records) == len(EXPECTED_TASKS) and all(row["gate_pass"] for row in records)
    summary = {
        "schema_version": SCHEMA,
        "status": (
            "PASS_PRODUCTION_MODEL_OPERATOR_GATE"
            if passed else "FAIL_PRODUCTION_MODEL_OPERATOR_GATE"
        ),
        "source_run_root": str(run_root),
        "probe_source_sha256": file_sha256(pathlib.Path(__file__).resolve()),
        "prompt_source_sha256": file_sha256(
            pathlib.Path(render_prompt.__code__.co_filename).resolve()
        ),
        "production_profile_exact_match": True,
        "model_id": MODEL_ID,
        "base_url_sha256": sha256_bytes(BASE_URL.encode("utf-8")),
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "message_role": "system",
        "client_timeout_seconds": 180,
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
        "production_operator_engineering_gate_passed": passed,
        "new_gpu_budget_still_required": True,
        "e2_e3_unlocked": False,
    }
    atomic_json(output_root / "summary.json", summary, mode=0o600)
    return summary


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--run-root", required=True)
    result.add_argument("--output-root", required=True)
    return result


def main() -> int:
    try:
        summary = run(parser().parse_args())
    except (ProductionProbeError, OSError, ValueError) as exc:
        print(f"DEEPSEEK_PRODUCTION_CONFORMANCE_ERROR: {exc}")
        return 2
    print(
        "DEEPSEEK_PRODUCTION_CONFORMANCE_DONE "
        f"status={summary['status']} calls={summary['api_calls']} "
        "gpu_jobs=0 method_claim_allowed=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
