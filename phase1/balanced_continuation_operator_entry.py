"""Exactly-one-call DeepSeek improve/debug operator for real E1 rollouts.

The OpenAI client is configured with transport retries disabled.  A malformed model
response is an observed ``invalid_format`` result; this entry point never asks again.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
import time
from typing import Any, Callable

import yaml
from jinja2 import StrictUndefined, Template

from phase1.balanced_continuation_e1_scoring import atomic_json, checked_json, file_sha256
from phase1.balanced_continuation_real_contract import (
    OPERATOR_RESPONSE_SCHEMA,
    canonical_json,
    sha256_bytes,
    validate_operator_request,
    validate_operator_response,
    validate_worker_contract,
)


MODEL_ID = "deepseek-v4-flash"
BASE_URL = "https://api.deepseek.com"
TEMPERATURE = 0.6
TOP_P = 0.95
MAX_OUTPUT_TOKENS = 8192
PACKAGES = (
    "numpy", "pandas", "scikit-learn", "statsmodels", "xgboost", "lightgbm",
    "torch", "torchvision", "torch-geometric", "bayesian-optimization", "timm",
)
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class OperatorError(RuntimeError):
    pass


def repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1]


def prompt_paths() -> dict[str, pathlib.Path]:
    root = repo_root() / "src" / "dojo" / "configs" / "solver" / "operators" / "mlebench" / "aira_operators"
    return {"improve": root / "improve.yaml", "debug": root / "debug.yaml"}


def prompt_bundle_sha256() -> str:
    value = {
        operator: {"path": path.relative_to(repo_root()).as_posix(), "sha256": file_sha256(path)}
        for operator, path in sorted(prompt_paths().items())
    }
    return sha256_bytes(canonical_json(value))


def operator_config_sha256() -> str:
    value = {
        "schema_version": "balanced-continuation-one-shot-operator-config-v1",
        "entry_sha256": file_sha256(pathlib.Path(__file__).resolve()),
        "model_id": MODEL_ID,
        "base_url": BASE_URL,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "sdk_max_retries": 0,
        "semantic_retries": 0,
        "packages": list(PACKAGES),
        "data_overview": "(No data preview available)",
        "memory": None,
    }
    return sha256_bytes(canonical_json(value))


def wrap_code(value: str, language: str = "python") -> str:
    return f"```{language}\n{value}\n```"


def load_template(operator: str) -> str:
    path = prompt_paths()[operator]
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    try:
        value = document[operator]["system_message_prompt_template"]["template"]
    except (KeyError, TypeError) as exc:
        raise OperatorError(f"operator prompt schema differs: {operator}") from exc
    if not isinstance(value, str) or not value:
        raise OperatorError(f"operator prompt is empty: {operator}")
    return value


def render_prompt(request: dict[str, Any]) -> str:
    operator = request["operator"]
    common = {
        "task_desc": request["task_description"],
        "execution_timeout": f"{request['execution_timeout_seconds']} seconds",
        "packages": ", ".join(f"`{name}`" for name in PACKAGES),
        "memory": None,
        "data_overview": "(No data preview available)",
    }
    if operator == "improve":
        values = {
            **common,
            "prev_code": wrap_code(request["previous_code"]),
            "prev_terminal_output": wrap_code(request["previous_terminal_output"], ""),
            "time_remaining": f"{request['execution_timeout_seconds']} seconds",
            "steps_remaining": request["remaining_steps"],
            "other_remarks": None,
            "improve_complexity": None,
        }
    elif operator == "debug":
        values = {
            **common,
            "prev_buggy_code": wrap_code(request["previous_code"]),
            "execution_output": wrap_code(request["previous_terminal_output"], ""),
            "time_remaining": f"{request['execution_timeout_seconds']} seconds",
            "steps_remaining": request["remaining_steps"],
            "other_remarks": None,
        }
    else:
        raise OperatorError("unsupported operator")
    return Template(load_template(operator), undefined=StrictUndefined).render(**values)


def extract_single_code(raw_response: str) -> str:
    # Match the established AIRA response contract without invoking its retry wrapper.
    blocks = re.findall(r"```(?:python)?\s*\n?(.*?)```", raw_response, flags=re.DOTALL | re.IGNORECASE)
    candidates = [block.strip() for block in blocks if block.strip()]
    return candidates[-1] + "\n" if candidates else ""


def response_from_raw(
    request: dict[str, Any], raw_response: str, provider_request_id: str | None
) -> dict[str, Any]:
    code = extract_single_code(raw_response)
    response = {
        "schema_version": OPERATOR_RESPONSE_SCHEMA,
        "rollout_id": request["rollout_id"],
        "transition_index": request["transition_index"],
        "operator": request["operator"],
        "request_sha256": sha256_bytes(canonical_json(request)),
        "raw_response_sha256": sha256_bytes(raw_response.encode("utf-8")),
        "extraction_status": "ok" if code else "invalid_format",
        "code": code,
        "code_sha256": sha256_bytes(code.encode("utf-8")),
        "provider_request_id": provider_request_id,
        "operator_calls": 1,
        "retry_count": 0,
    }
    return response


def call_once(prompt: str) -> tuple[str, str | None, dict[str, Any]]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise OperatorError("OpenAI SDK unavailable") from exc
    credential = os.environ.get("PRIMARY_KEY_DEEPSEEK_V4_FLASH") or os.environ.get("PRIMARY_KEY")
    if not credential:
        raise OperatorError("operator credential unavailable")
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
    message = completion.choices[0].message
    content = message.content or ""
    reasoning = getattr(message, "reasoning_content", None) or ""
    raw_response = content if content else reasoning
    usage = getattr(completion, "usage", None)
    usage_receipt = {
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
    return raw_response, getattr(completion, "id", None), usage_receipt


def run(
    args: argparse.Namespace,
    caller: Callable[[str], tuple[str, str | None, dict[str, Any]]] = call_once,
) -> dict[str, Any]:
    contract = validate_worker_contract(checked_json(pathlib.Path(args.contract).resolve()))
    if contract["operator_config_sha256"] != operator_config_sha256():
        raise OperatorError("operator config differs from worker contract")
    if contract["prompt_sha256"] != prompt_bundle_sha256():
        raise OperatorError("operator prompt bundle differs from worker contract")
    request = validate_operator_request(
        checked_json(pathlib.Path(args.request).resolve()), contract
    )
    prompt = render_prompt(request)
    if CREDENTIAL.search(prompt.encode("utf-8")):
        raise OperatorError("credential-shaped bytes in rendered prompt")
    raw_response, provider_id, usage = caller(prompt)
    if not isinstance(raw_response, str):
        raise OperatorError("provider response is not text")
    if CREDENTIAL.search(raw_response.encode("utf-8")):
        raise OperatorError("credential-shaped bytes in provider response")
    response = response_from_raw(request, raw_response, provider_id)
    validate_operator_response(response, request, contract)
    atomic_json(pathlib.Path(args.response).resolve(), response)
    usage = {
        **usage,
        "request_sha256": sha256_bytes(canonical_json(request)),
        "rendered_prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
        "raw_response_sha256": response["raw_response_sha256"],
        "extraction_status": response["extraction_status"],
    }
    atomic_json(pathlib.Path(args.usage_receipt).resolve(), usage)
    return response


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--contract", required=True)
    ap.add_argument("--request", required=True)
    ap.add_argument("--response", required=True)
    ap.add_argument("--usage-receipt", required=True)
    return ap


def main() -> int:
    try:
        response = run(parser().parse_args())
    except (OperatorError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ONE_SHOT_OPERATOR_ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        "ONE_SHOT_OPERATOR_DONE "
        f"status={response['extraction_status']} calls=1 retries=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
