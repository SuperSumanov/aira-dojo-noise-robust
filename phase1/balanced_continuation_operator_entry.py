"""Exactly-one-call DeepSeek improve/debug operator for real E1 rollouts.

The OpenAI client is configured with transport retries disabled.  A malformed model
response is an observed ``invalid_format`` result; this entry point never asks again.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import pathlib
import re
import sys
import time
from typing import Any, Callable

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
STRICT_PROMPT_SCHEMA = "balanced-continuation-complete-script-prompt-v2"
RAW_RESPONSE_SCHEMA = "balanced-continuation-operator-raw-response-v1"
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


def prompt_bundle_sha256() -> str:
    return sha256_bytes(canonical_json({
        "schema_version": STRICT_PROMPT_SCHEMA,
        "entry_sha256": file_sha256(pathlib.Path(__file__).resolve()),
    }))


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


def render_prompt(request: dict[str, Any]) -> str:
    operator = request["operator"]
    if operator == "improve":
        action = (
            "Make exactly one conservative, likely-beneficial improvement while preserving "
            "the prior evaluation protocol and output schema."
        )
    elif operator == "debug":
        action = "Repair the observed failure without changing the script's core method."
    else:
        raise OperatorError("unsupported operator")
    return f"""You are the frozen one-step code operator in an MLE search experiment.

{action}

TASK DESCRIPTION
{request['task_description']}

PREVIOUS COMPLETE SCRIPT
```python
{request['previous_code'].rstrip()}
```

PREVIOUS TERMINAL OUTPUT
```
{request['previous_terminal_output'].rstrip()}
```

HARD EXECUTION CONTRACT
- Return exactly one fenced `python` code block and no prose before or after it.
- The block must be a complete replacement script, never a patch, excerpt, example, or pseudocode.
- Do not use ellipses, TODOs, omitted sections, or undefined placeholder variables.
- Read prepared data only from the read-only `./data` directory; network is unavailable.
- Finish within {request['execution_timeout_seconds']} seconds on one RTX 3090 and 6 CPUs.
- Use only these installed packages when needed: {', '.join(PACKAGES)}.
- Preserve the task's exact submission columns and save all test predictions to `./submission.csv`.
- Print exactly one `FINAL_VALIDATION_SCORE: <number>` marker as the final stdout line.
- Before answering, silently verify syntax, imports, variable definitions, and end-to-end completeness.
"""


def assess_single_complete_code(raw_response: str, previous_code: str) -> tuple[str, str]:
    stripped = raw_response.strip()
    exact = re.fullmatch(r"```python\s*\n(.*?)\n```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if exact is None:
        return "", "not_exactly_one_python_block"
    if "```" in exact.group(1):
        return "", "not_exactly_one_python_block"
    code = exact.group(1).strip() + "\n"
    minimum_chars = max(512, min(4096, len(previous_code) // 4))
    if len(code) < minimum_chars or len(code.splitlines()) < 20:
        return "", "replacement_too_short"
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return "", "python_syntax_error"
    if any(isinstance(node, ast.Constant) and node.value is Ellipsis for node in ast.walk(tree)):
        return "", "ellipsis_placeholder"
    required_markers = ("read_csv", "submission.csv", "to_csv", "FINAL_VALIDATION_SCORE")
    if any(marker not in code for marker in required_markers):
        return "", "required_end_to_end_marker_missing"
    if not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree)):
        return "", "imports_missing"
    return code, "ok"


def extract_single_code(raw_response: str, previous_code: str = "") -> str:
    code, _ = assess_single_complete_code(raw_response, previous_code)
    return code


def response_from_raw(
    request: dict[str, Any], raw_response: str, provider_request_id: str | None
) -> dict[str, Any]:
    code, _ = assess_single_complete_code(raw_response, request["previous_code"])
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
    atomic_json(pathlib.Path(args.raw_response).resolve(), {
        "schema_version": RAW_RESPONSE_SCHEMA,
        "request_sha256": response["request_sha256"],
        "raw_response_sha256": response["raw_response_sha256"],
        "raw_response": raw_response,
    }, mode=0o600)
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
    ap.add_argument("--raw-response", required=True)
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
