"""Exactly-one-call Qwen complete-script operator for a fresh E1-Q contract."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
from typing import Any, Callable

from phase1 import balanced_continuation_operator_entry as shared
from phase1.balanced_continuation_e1_scoring import atomic_json, checked_json, file_sha256
from phase1.balanced_continuation_real_contract import (
    canonical_json,
    sha256_bytes,
    validate_operator_request,
    validate_operator_response,
    validate_worker_contract,
)


MODEL_ID = "qwen3-coder-flash"
PROVIDER = "qwen"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
KEY_ENV = "PRIMARY_KEY_QWEN3_CODER_FLASH"
TEMPERATURE = 0.0
MAX_OUTPUT_TOKENS = 8192
ENABLE_THINKING = False
CLIENT_TIMEOUT_SECONDS = 240.0
RAW_RESPONSE_SCHEMA = shared.RAW_RESPONSE_SCHEMA
CREDENTIAL = shared.CREDENTIAL


class QwenOperatorError(RuntimeError):
    pass


def prompt_bundle_sha256() -> str:
    return sha256_bytes(canonical_json({
        "schema_version": "balanced-continuation-qwen-complete-script-prompt-v1",
        "qwen_entry_sha256": file_sha256(pathlib.Path(__file__).resolve()),
        "shared_prompt_entry_sha256": file_sha256(pathlib.Path(shared.__file__).resolve()),
        "shared_prompt_schema": shared.STRICT_PROMPT_SCHEMA,
        "message_role": "user",
    }))


def operator_config_sha256() -> str:
    return sha256_bytes(canonical_json({
        "schema_version": "balanced-continuation-one-shot-qwen-config-v1",
        "entry_sha256": file_sha256(pathlib.Path(__file__).resolve()),
        "shared_entry_sha256": file_sha256(pathlib.Path(shared.__file__).resolve()),
        "model_id": MODEL_ID,
        "provider": PROVIDER,
        "base_url": BASE_URL,
        "temperature": TEMPERATURE,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "enable_thinking": ENABLE_THINKING,
        "message_role": "user",
        "client_timeout_seconds": CLIENT_TIMEOUT_SECONDS,
        "sdk_max_retries": 0,
        "semantic_retries": 0,
        "packages": list(shared.PACKAGES),
        "data_overview": "(No data preview available)",
        "memory": None,
    }))


def call_once(prompt: str) -> tuple[str, str | None, dict[str, Any]]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise QwenOperatorError("OpenAI SDK unavailable") from exc
    credential = os.environ.get(KEY_ENV)
    if not credential:
        raise QwenOperatorError("Qwen operator credential unavailable")
    client = OpenAI(
        api_key=credential,
        base_url=BASE_URL,
        max_retries=0,
        timeout=CLIENT_TIMEOUT_SECONDS,
    )
    started = time.monotonic()
    completion = client.chat.completions.create(
        model=MODEL_ID,
        messages=[{"role": "user", "content": prompt}],
        temperature=TEMPERATURE,
        max_tokens=MAX_OUTPUT_TOKENS,
        extra_body={"enable_thinking": ENABLE_THINKING},
    )
    latency = time.monotonic() - started
    choice = completion.choices[0]
    content = choice.message.content or ""
    usage = getattr(completion, "usage", None)
    receipt = {
        "schema_version": "balanced-continuation-operator-usage-v1",
        "model_id": MODEL_ID,
        "provider_request_id": getattr(completion, "id", None),
        "api_calls": 1,
        "retry_count": 0,
        "latency_seconds": latency,
        "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
        "completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
        "total_tokens": getattr(usage, "total_tokens", None) if usage else None,
    }
    return content, getattr(completion, "id", None), receipt


def run(
    args: argparse.Namespace,
    caller: Callable[[str], tuple[str, str | None, dict[str, Any]]] = call_once,
) -> dict[str, Any]:
    contract = validate_worker_contract(checked_json(pathlib.Path(args.contract).resolve()))
    if contract["operator_config_sha256"] != operator_config_sha256():
        raise QwenOperatorError("Qwen operator config differs from worker contract")
    if contract["prompt_sha256"] != prompt_bundle_sha256():
        raise QwenOperatorError("Qwen prompt bundle differs from worker contract")
    request = validate_operator_request(
        checked_json(pathlib.Path(args.request).resolve()), contract
    )
    prompt = shared.render_prompt(request)
    if CREDENTIAL.search(prompt.encode("utf-8")):
        raise QwenOperatorError("credential-shaped bytes in rendered prompt")
    raw_response, provider_id, usage = caller(prompt)
    if not isinstance(raw_response, str):
        raise QwenOperatorError("provider response is not text")
    if CREDENTIAL.search(raw_response.encode("utf-8")):
        raise QwenOperatorError("credential-shaped bytes in provider response")
    response = shared.response_from_raw(request, raw_response, provider_id)
    validate_operator_response(response, request, contract)
    atomic_json(pathlib.Path(args.raw_response).resolve(), {
        "schema_version": RAW_RESPONSE_SCHEMA,
        "request_sha256": response["request_sha256"],
        "raw_response_sha256": response["raw_response_sha256"],
        "raw_response": raw_response,
    }, mode=0o600)
    atomic_json(pathlib.Path(args.response).resolve(), response)
    bound_usage = {
        **usage,
        "request_sha256": sha256_bytes(canonical_json(request)),
        "rendered_prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
        "raw_response_sha256": response["raw_response_sha256"],
        "extraction_status": response["extraction_status"],
    }
    atomic_json(pathlib.Path(args.usage_receipt).resolve(), bound_usage)
    return response


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--contract", required=True)
    ap.add_argument("--request", required=True)
    ap.add_argument("--response", required=True)
    ap.add_argument("--raw-response", required=True)
    ap.add_argument("--usage-receipt", required=True)
    return ap


def main() -> int:
    try:
        response = run(parser().parse_args())
    except (
        QwenOperatorError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"ONE_SHOT_QWEN_OPERATOR_ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        "ONE_SHOT_QWEN_OPERATOR_DONE "
        f"status={response['extraction_status']} calls=1 retries=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
