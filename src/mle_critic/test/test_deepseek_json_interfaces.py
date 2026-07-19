#!/usr/bin/env python3
"""Live diagnostic for DeepSeek JSON/structured-output transports.

This is intentionally a manually invoked integration test: importing the file or
running the normal pytest suite does not make network calls.

It sends the same analyze-style request through six paths:

1. OpenAI SDK with ``response_format={"type": "json_object"}``.
2. OpenAI SDK with modern, forced ``tools`` function calling.
3. LiteLLM with JSON mode.
4. LiteLLM with modern, forced ``tools`` function calling.
5. LiteLLM with the exact legacy ``functions`` payload shape currently built by
   ``dojo.core.solvers.llm_helpers.backends.lite_llm.FunctionSpec``.
6. The actual Dojo ``LiteLLMClient.query`` wrapper.

The request contains several distracting numbers and an expected validation metric.
A response counts as successful only if it is valid JSON, matches the requested
schema, reports ``is_bug=false``, and returns the correct metric.

Examples::

    conda activate aira-dojo

    # Automatically loads PRIMARY_KEY from the repository-root .env.
    python src/mle_critic/test/test_deepseek_json_interfaces.py --trials 3

    # Run only the most informative comparison.
    python src/mle_critic/test/test_deepseek_json_interfaces.py \
        --modes openai_json,litellm_json,openai_tools,litellm_tools,litellm_dojo_payload,dojo_wrapper \
        --trials 10 --output tmp/deepseek-json-report.json

    # Alternative endpoint/model/key variables are also supported.
    DEEPSEEK_API_KEY=... DEEPSEEK_MODEL=deepseek-chat \
    DEEPSEEK_BASE_URL=https://api.deepseek.com \
    python src/mle_critic/test/test_deepseek_json_interfaces.py --trials 5

Use ``--strict`` when a non-zero exit code is desired if any selected mode has a
transport or schema failure. Without it, the script remains a diagnostic and exits
zero after printing the comparison report.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import os
import shlex
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[3]
ROOT_ENV_FILE = REPO_ROOT / ".env"


def _load_root_env() -> None:
    """Load root .env without overriding variables already injected by the shell."""
    try:
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=ROOT_ENV_FILE, override=False)
        return
    except ModuleNotFoundError:
        pass

    # Lightweight fallback for minimal environments where python-dotenv is absent.
    if not ROOT_ENV_FILE.is_file():
        return
    for raw_line in ROOT_ENV_FILE.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        try:
            tokens = shlex.split(raw_value, comments=True, posix=True)
            value = " ".join(tokens)
        except ValueError:
            value = raw_value.strip().strip("'\"")
        os.environ[key] = value


# Match the rest of AIRA-Dojo: load credentials from the repository-root .env.
_load_root_env()


FUNCTION_NAME = "submit_review"
FUNCTION_DESCRIPTION = "Submit a review evaluating the output of a training script."
EXPECTED_METRIC = 0.8123

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "is_bug": {"type": "boolean"},
        "summary": {"type": "string"},
        "metric": {"type": "number"},
    },
    "required": ["is_bug", "summary", "metric"],
}

SYSTEM_PROMPT = f"""You are reviewing the output of a machine-learning training script.
Return a JSON object matching this exact contract:
- is_bug: boolean
- summary: string
- metric: number

Do not confuse runtime, fold numbers, row counts, or random seeds with the validation
metric. The run is successful, so is_bug must be false. The validation metric is the
number following 'Cross-validation accuracy'. Return metric={EXPECTED_METRIC}.

Execution output:
Loaded 8693 rows and 14 columns.
Random seed: 42
Fold 1 accuracy: 0.8011
Fold 2 accuracy: 0.8190
Cross-validation accuracy: {EXPECTED_METRIC}
Execution time: 17.4 seconds
submission.csv saved with 870 rows.
"""

MESSAGES = [{"role": "system", "content": SYSTEM_PROMPT}]


@dataclass
class TrialResult:
    mode: str
    trial: int
    ok: bool
    latency_s: float
    transport: str
    parsed: dict[str, Any] | None = None
    raw: str | None = None
    error: str | None = None


def _version(package: str) -> str | None:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


def _resolve_api_key(model: str) -> str:
    model_key = "PRIMARY_KEY_" + model.replace("-", "_").upper()
    # This diagnostic intentionally uses the repository's standard PRIMARY_KEY
    # first. Model-specific variables remain supported as fallbacks.
    for name in ("PRIMARY_KEY", "DEEPSEEK_API_KEY", model_key):
        value = os.getenv(name, "").strip()
        if value:
            return value
    raise RuntimeError(
        f"No API key found. Set PRIMARY_KEY in {ROOT_ENV_FILE}, or provide "
        f"DEEPSEEK_API_KEY/{model_key} in the environment."
    )


def _redact(text: str, api_key: str) -> str:
    if api_key:
        text = text.replace(api_key, "<REDACTED_API_KEY>")
    return text


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return repr(value)


def _parse_json_text(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()

    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(candidate[start : end + 1])

    if not isinstance(value, dict):
        raise TypeError(f"Expected a JSON object, got {type(value).__name__}")
    return value


def _validate(value: dict[str, Any]) -> None:
    required = {"is_bug", "summary", "metric"}
    if set(value) != required:
        raise ValueError(f"Expected exactly keys {sorted(required)}, got {sorted(value)}")
    if not isinstance(value["is_bug"], bool):
        raise TypeError("is_bug must be a boolean")
    if value["is_bug"]:
        raise ValueError("is_bug should be false for the supplied successful run")
    if not isinstance(value["summary"], str) or not value["summary"].strip():
        raise TypeError("summary must be a non-empty string")
    if isinstance(value["metric"], bool) or not isinstance(value["metric"], (int, float)):
        raise TypeError("metric must be numeric")
    if not math.isclose(float(value["metric"]), EXPECTED_METRIC, rel_tol=0.0, abs_tol=1e-6):
        raise ValueError(f"Expected metric {EXPECTED_METRIC}, got {value['metric']}")


def _modern_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": FUNCTION_NAME,
            "description": FUNCTION_DESCRIPTION,
            "parameters": SCHEMA,
        },
    }


def _dojo_legacy_function_payload() -> dict[str, Any]:
    """Reproduce FunctionSpec.as_openai_tool_dict from the current LiteLLM backend."""
    return {
        "type": "function",
        "name": FUNCTION_NAME,
        "description": FUNCTION_DESCRIPTION,
        "parameters": SCHEMA,
    }


def _arguments_from_message(message: Any) -> str:
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        return tool_calls[0].function.arguments

    function_call = getattr(message, "function_call", None)
    if function_call:
        return function_call.arguments

    content = getattr(message, "content", None)
    if content:
        return content
    raise ValueError("Response contained neither tool arguments nor text content")


def call_openai_json(api_key: str, base_url: str, model: str, timeout: float) -> tuple[Any, str]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)
    response = client.chat.completions.create(
        model=model,
        messages=MESSAGES,
        temperature=0,
        max_tokens=256,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content, "content/json_object"


def call_openai_tools(api_key: str, base_url: str, model: str, timeout: float) -> tuple[Any, str]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)
    response = client.chat.completions.create(
        model=model,
        messages=MESSAGES,
        temperature=0,
        max_tokens=256,
        tools=[_modern_tool()],
        tool_choice={"type": "function", "function": {"name": FUNCTION_NAME}},
    )
    message = response.choices[0].message
    return _arguments_from_message(message), "modern_tools/forced"


def _litellm_completion(
    *, api_key: str, base_url: str, model: str, timeout: float, **kwargs: Any
) -> Any:
    import litellm

    return litellm.completion(
        model=f"openai/{model}",
        api_key=api_key,
        base_url=base_url,
        messages=MESSAGES,
        temperature=0,
        max_tokens=256,
        timeout=timeout,
        max_retries=0,
        **kwargs,
    )


def call_litellm_json(api_key: str, base_url: str, model: str, timeout: float) -> tuple[Any, str]:
    response = _litellm_completion(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout=timeout,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content, "content/json_object"


def call_litellm_tools(api_key: str, base_url: str, model: str, timeout: float) -> tuple[Any, str]:
    response = _litellm_completion(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout=timeout,
        tools=[_modern_tool()],
        tool_choice={"type": "function", "function": {"name": FUNCTION_NAME}},
    )
    return _arguments_from_message(response.choices[0].message), "modern_tools/forced"


def call_litellm_dojo_payload(
    api_key: str, base_url: str, model: str, timeout: float
) -> tuple[Any, str]:
    response = _litellm_completion(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout=timeout,
        functions=[_dojo_legacy_function_payload()],
        function_call="auto",
    )
    return _arguments_from_message(response.choices[0].message), "dojo_legacy_functions/auto"


def call_dojo_wrapper(api_key: str, base_url: str, model: str, timeout: float) -> tuple[Any, str]:
    # The wrapper hard-codes its own 1500-second request timeout. The timeout argument
    # remains in this signature so all mode callables share one interface.
    del timeout
    model_key = "PRIMARY_KEY_" + model.replace("-", "_").upper()
    old_model_key = os.environ.get(model_key)
    os.environ[model_key] = api_key
    try:
        from dojo.core.solvers.llm_helpers.backends.lite_llm import LiteLLMClient

        cfg = SimpleNamespace(
            model_id=model,
            base_url=base_url,
            use_azure_client=False,
            provider="openai",
        )
        client = LiteLLMClient(cfg)
        output, _usage = client.query(
            MESSAGES,
            json_schema=json.dumps(SCHEMA),
            function_name=FUNCTION_NAME,
            function_description=FUNCTION_DESCRIPTION,
            temperature=0,
            max_tokens=256,
        )
        return output, f"dojo_wrapper/{type(output).__name__}"
    finally:
        if old_model_key is None:
            os.environ.pop(model_key, None)
        else:
            os.environ[model_key] = old_model_key


MODES: dict[str, Callable[[str, str, str, float], tuple[Any, str]]] = {
    "openai_json": call_openai_json,
    "openai_tools": call_openai_tools,
    "litellm_json": call_litellm_json,
    "litellm_tools": call_litellm_tools,
    "litellm_dojo_payload": call_litellm_dojo_payload,
    "dojo_wrapper": call_dojo_wrapper,
}


def run_trial(
    mode: str,
    trial: int,
    api_key: str,
    base_url: str,
    model: str,
    timeout: float,
) -> TrialResult:
    started = time.monotonic()
    transport = "not_started"
    raw: str | None = None
    try:
        output, transport = MODES[mode](api_key, base_url, model, timeout)
        if isinstance(output, dict):
            parsed = output
            raw = _as_text(output)
        else:
            raw = _as_text(output)
            parsed = _parse_json_text(raw)
        _validate(parsed)
        return TrialResult(
            mode=mode,
            trial=trial,
            ok=True,
            latency_s=time.monotonic() - started,
            transport=transport,
            parsed=parsed,
            raw=raw,
        )
    except Exception as exc:  # The exception type is part of the diagnostic.
        return TrialResult(
            mode=mode,
            trial=trial,
            ok=False,
            latency_s=time.monotonic() - started,
            transport=transport,
            raw=_redact(raw or "", api_key) or None,
            error=_redact(f"{type(exc).__name__}: {exc}", api_key),
        )


def _print_summary(results: list[TrialResult]) -> None:
    print("\n=== DeepSeek JSON transport comparison ===")
    print(f"{'mode':28} {'ok/total':10} {'rate':8} {'mean_s':8} first_error")
    print("-" * 100)
    for mode in MODES:
        selected = [result for result in results if result.mode == mode]
        if not selected:
            continue
        successes = sum(result.ok for result in selected)
        mean_latency = sum(result.latency_s for result in selected) / len(selected)
        first_error = next((result.error for result in selected if result.error), "")
        if len(first_error) > 42:
            first_error = first_error[:39] + "..."
        print(
            f"{mode:28} {successes:>2}/{len(selected):<7} "
            f"{successes / len(selected):>6.1%} {mean_latency:>8.2f} {first_error}"
        )

    print("\nInterpretation:")
    print("- openai_json succeeds but litellm_json fails: suspect LiteLLM translation/versioning.")
    print("- modern tools succeed but litellm_dojo_payload/dojo_wrapper fail: suspect Dojo's")
    print("  legacy functions payload shape or auto function choice.")
    print("- JSON modes succeed while all tool modes fail: prefer response_format JSON mode")
    print("  for analyze, or have candidates write a schema-validated metrics.json file.")
    print("- all paths fail similarly: inspect the model name, endpoint capabilities, and prompt.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        help="DeepSeek model ID (default: DEEPSEEK_MODEL or deepseek-v4-pro).",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        help="OpenAI-compatible base URL.",
    )
    parser.add_argument("--trials", type=int, default=3, help="Calls per selected mode.")
    parser.add_argument("--timeout", type=float, default=120.0, help="Per-call timeout in seconds.")
    parser.add_argument(
        "--modes",
        default=",".join(MODES),
        help=f"Comma-separated modes. Available: {','.join(MODES)}",
    )
    parser.add_argument("--output", type=Path, help="Optional path for the full JSON report.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any selected trial fails.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.trials < 1:
        raise ValueError("--trials must be at least 1")

    selected_modes = [mode.strip() for mode in args.modes.split(",") if mode.strip()]
    unknown = sorted(set(selected_modes) - set(MODES))
    if unknown:
        raise ValueError(f"Unknown modes: {unknown}. Available: {sorted(MODES)}")

    api_key = _resolve_api_key(args.model)
    print(f"model={args.model}")
    print(f"base_url={args.base_url}")
    print(f"env_file={ROOT_ENV_FILE} (exists={ROOT_ENV_FILE.is_file()})")
    print(f"trials={args.trials}")
    print(f"modes={','.join(selected_modes)}")
    print(f"openai={_version('openai')} litellm={_version('litellm')}")

    results: list[TrialResult] = []
    for mode in selected_modes:
        for trial in range(1, args.trials + 1):
            print(f"[{mode}] trial {trial}/{args.trials} ...", flush=True)
            result = run_trial(
                mode=mode,
                trial=trial,
                api_key=api_key,
                base_url=args.base_url,
                model=args.model,
                timeout=args.timeout,
            )
            results.append(result)
            status = "OK" if result.ok else "FAIL"
            print(f"[{mode}] trial {trial}: {status} ({result.latency_s:.2f}s)", flush=True)
            if result.error:
                print(f"  {result.error}", flush=True)

    _print_summary(results)

    report = {
        "model": args.model,
        "base_url": args.base_url,
        "expected_metric": EXPECTED_METRIC,
        "versions": {"python": sys.version, "openai": _version("openai"), "litellm": _version("litellm")},
        "results": [asdict(result) for result in results],
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(f"\nFull report written to {args.output}")

    return 1 if args.strict and any(not result.ok for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
