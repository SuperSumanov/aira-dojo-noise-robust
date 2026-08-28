#!/usr/bin/env python3
"""Run the frozen full-context historical pairwise evaluator diagnostic.

The executable is deliberately inert by default.  ``dry-run`` and ``mock`` never
read a credential or open the network.  ``live`` additionally requires a separate
launch receipt bound to the protocol SHA and reads one credential from the process
environment only.  It never loads a dotenv file or records request headers.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
from typing import Any, Iterable
import urllib.error
import urllib.request


PROTOCOL_NAME = "openrouter-full-context-judge-v1"
PROTOCOL_STATUS = "FROZEN_BEFORE_PANEL_MATERIALIZATION_OR_API_CALLS"
PANEL_SCHEMA = "openrouter-full-context-private-panel-row-v1"
LAUNCH_RECEIPT = "openrouter-full-context-launch-receipt-v1"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
KEY_ENVIRONMENT_VARIABLE = "OPENROUTER_API_KEY"

SYSTEM_PROMPT = """You are an expert machine-learning competition evaluator.
You will receive two complete candidate programs for the same task under exactly
the same agent, hardware, and time constraints. Predict which program is more
likely to produce the stronger external competition submission if executed once.
Judge methodology, validation, leakage risk, feature/model choices, robustness,
and feasibility under the stated constraints. Do not execute code. End your final
answer with exactly one standalone character: A or B."""


class JudgeError(RuntimeError):
    """Raised when a frozen contract, security rule, or cost gate fails."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise JudgeError(message)


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise JudgeError("non-canonical JSON value") from error


def sha256_file(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_protocol(path: Path, expected_sha256: str) -> tuple[dict[str, Any], str]:
    observed = sha256_file(path)
    require(observed == expected_sha256, "protocol SHA mismatch")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "protocol object required")
    require(value.get("protocol") == PROTOCOL_NAME, "protocol name mismatch")
    require(value.get("status") == PROTOCOL_STATUS, "protocol status mismatch")
    require(value["prompt_contract"]["truncate_input"] is False, "input truncation drift")
    require(value["prompt_contract"]["max_tokens_field"] == "OMITTED", "output cap drift")
    return value, observed


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSONL: {path}")
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank JSONL row: {number}")
            value = json.loads(line)
            require(isinstance(value, dict), f"JSONL object required: {number}")
            rows.append(value)
    return rows


def validate_private_panel(
    rows: list[dict[str, Any]], protocol: dict[str, Any], protocol_sha256: str
) -> None:
    expected_pairs = sum(int(value["pairs"]) for value in protocol["eligibility"]["panels"].values())
    require(len(rows) == expected_pairs, "private panel row count")
    private_ids: set[str] = set()
    endpoints: set[str] = set()
    runs: set[str] = set()
    task_counts: dict[str, int] = {}
    smoke = 0
    per_stratum: dict[tuple[str, str], int] = {}
    valid_panels = set(protocol["eligibility"]["panels"])
    valid_bins = {item["name"] for item in protocol["selection"]["gap_bins"]}
    for row in rows:
        require(row.get("schema") == PANEL_SCHEMA, "private panel schema")
        require(row.get("protocol_sha256") == protocol_sha256, "private panel protocol binding")
        private_id = row.get("pair_private_id")
        require(isinstance(private_id, str) and len(private_id) == 64, "private pair identity")
        require(private_id not in private_ids, "duplicate private pair identity")
        private_ids.add(private_id)
        panel, gap = row.get("panel"), row.get("gap_bin")
        require(panel in valid_panels and gap in valid_bins, "private panel stratum")
        per_stratum[(panel, gap)] = per_stratum.get((panel, gap), 0) + 1
        first, second = row.get("better"), row.get("worse")
        require(isinstance(first, dict) and isinstance(second, dict), "private endpoints")
        for endpoint in (first, second):
            identity = endpoint.get("id")
            require(isinstance(identity, str) and identity and identity not in endpoints, "endpoint reuse")
            endpoints.add(identity)
            require(isinstance(endpoint.get("code"), str) and endpoint["code"].strip(), "full code")
        require(first["run"] == second["run"], "private cross-run pair")
        require(first["run"] not in runs, "physical-run reuse")
        runs.add(first["run"])
        require(first["task"] == second["task"], "task metadata mismatch")
        for field in ("name", "desc", "metric"):
            require(
                isinstance(first["task"].get(field), str) and first["task"][field],
                f"missing task prompt field: {field}",
            )
        require(
            isinstance(first["task"].get("higher_is_better"), bool),
            "missing metric direction",
        )
        for field in ("client", "hardware", "time_limit", "execution_timeout"):
            require(first[field] == second[field], f"resource stratum mismatch: {field}")
        task_name = first["task"]["name"]
        task_counts[task_name] = task_counts.get(task_name, 0) + 1
        smoke += int(row.get("smoke") is True)
    quota = int(protocol["selection"]["pairs_per_panel_bin"])
    require(
        all(per_stratum.get((panel, gap), 0) == quota for panel in valid_panels for gap in valid_bins),
        "private panel quotas",
    )
    require(max(task_counts.values()) <= protocol["selection"]["global_max_pairs_per_task"], "task cap")
    require(smoke == len(valid_panels) * len(valid_bins), "smoke subset count")


def render_user_prompt(row: dict[str, Any], orientation: str) -> str:
    require(orientation in {"AB", "BA"}, "orientation")
    first = row["better"] if orientation == "AB" else row["worse"]
    second = row["worse"] if orientation == "AB" else row["better"]
    task = first["task"]
    direction = "higher is better" if task["higher_is_better"] else "lower is better"
    return (
        f"TASK\n{task['desc']}\n\n"
        f"METRIC\n{task['metric']} ({direction})\n\n"
        "SHARED EXECUTION CONTRACT\n"
        f"Agent/client: {first['client']}\n"
        f"Hardware: {first['hardware']}\n"
        f"Overall time limit: {first['time_limit']} seconds\n"
        f"Per-execution timeout: {first['execution_timeout']} seconds\n\n"
        f"CANDIDATE A — COMPLETE UNMODIFIED CODE\n```python\n{first['code']}\n```\n\n"
        f"CANDIDATE B — COMPLETE UNMODIFIED CODE\n```python\n{second['code']}\n```\n\n"
        "Which candidate is more likely to produce the stronger external submission? "
        "End with exactly one standalone A or B."
    )


def request_payload(
    row: dict[str, Any], orientation: str, model: str, protocol: dict[str, Any]
) -> dict[str, Any]:
    contract = protocol["prompt_contract"]
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": render_user_prompt(row, orientation)},
        ],
        "temperature": contract["temperature"],
        "seed": contract["seed"],
        "reasoning": contract["reasoning"],
        "provider": contract["provider"],
    }
    require("max_tokens" not in payload and "max_completion_tokens" not in payload, "output truncation")
    serialized = canonical_json(payload)
    for endpoint in (row["better"], row["worse"]):
        require(endpoint["id"] not in serialized, "endpoint identity leaked into request")
        require(endpoint["run"] not in serialized, "run identity leaked into request")
    for forbidden in ("gap_raw", "normalized_gap", "pair_private_id", "declared_parent_id"):
        require(forbidden not in serialized, f"forbidden field leaked: {forbidden}")
    return payload


def parse_final_pick(response: dict[str, Any]) -> tuple[str | None, str]:
    try:
        content = response["choices"][0]["message"].get("content")
    except (KeyError, IndexError, TypeError, AttributeError):
        return None, "missing_final_content"
    if not isinstance(content, str) or not content.strip():
        return None, "missing_final_content"
    matches = re.findall(r"(?<![A-Za-z])([AB])(?![A-Za-z])", content.upper())
    if len(matches) != 1:
        return None, "final_content_not_exactly_one_standalone_choice"
    return matches[0], "parsed"


def model_catalog(protocol: dict[str, Any]) -> dict[str, dict[str, Any]]:
    values = protocol["model_catalog_snapshot"]["models"]
    result = {item["id"]: item for item in values}
    require(len(result) == len(values), "duplicate model catalog ID")
    return result


def response_cost_usd(
    response: dict[str, Any], model: str, catalog: dict[str, dict[str, Any]]
) -> Decimal:
    usage = response.get("usage")
    require(isinstance(usage, dict), "successful response missing usage")
    reported = usage.get("cost")
    if reported is not None:
        try:
            cost = Decimal(str(reported))
        except InvalidOperation as error:
            raise JudgeError("invalid reported response cost") from error
        require(cost >= 0, "negative response cost")
        return cost
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    require(
        isinstance(prompt, int) and prompt >= 0 and isinstance(completion, int) and completion >= 0,
        "successful response missing token usage",
    )
    entry = catalog[model]
    return (
        Decimal(prompt) * Decimal(entry["input_usd_per_million"])
        + Decimal(completion) * Decimal(entry["output_usd_per_million"])
    ) / Decimal(1_000_000)


def mock_response(request: dict[str, Any]) -> dict[str, Any]:
    digest = hashlib.sha256(canonical_json(request).encode()).digest()
    pick = "A" if digest[0] % 2 == 0 else "B"
    prompt_tokens = max(1, len(canonical_json(request).encode("utf-8")) // 4)
    return {
        "id": "mock-" + hashlib.sha256(canonical_json(request).encode()).hexdigest()[:16],
        "provider": "mock",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "reasoning": "Synthetic reasoning retained for transport testing only.",
                    "content": pick,
                }
            }
        ],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": 12, "cost": 0},
    }


def live_response(request_payload_value: dict[str, Any], credential: str, timeout: float) -> dict[str, Any]:
    body = canonical_json(request_payload_value).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": "Bearer " + credential,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.load(response)
    except urllib.error.HTTPError as error:
        try:
            message = error.read(4096).decode("utf-8", errors="replace")
        except OSError:
            message = ""
        raise JudgeError(f"provider HTTP error {error.code}: {message[:500]}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise JudgeError(
            "ambiguous transport failure; frozen protocol forbids automatic retry: "
            + str(error)[:300]
        ) from error
    require(isinstance(value, dict), "provider response object required")
    return value


def load_launch_receipt(
    path: Path | None, protocol_sha256: str, phase: str, cap: Decimal
) -> dict[str, Any]:
    require(path is not None, "live transport requires a separate launch receipt")
    require(path.is_file() and not path.is_symlink(), "unsafe launch receipt")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "launch receipt object")
    require(value.get("protocol") == LAUNCH_RECEIPT, "launch receipt protocol")
    require(value.get("protocol_sha256") == protocol_sha256, "launch receipt SHA binding")
    require(value.get("phase") == phase, "launch receipt phase")
    require(value.get("authorized") is True, "live calls not authorized")
    require(Decimal(str(value.get("cumulative_usd_stop"))) == cap, "launch receipt cost cap")
    return value


def ensure_private_file(path: Path) -> None:
    if os.name == "posix":
        mode = stat.S_IMODE(path.stat().st_mode)
        require(mode & 0o077 == 0, f"private file permissions too broad: {oct(mode)}")


def open_secure_append(path: Path) -> Any:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.exists():
        require(path.is_file() and not path.is_symlink(), "unsafe raw output")
        ensure_private_file(path)
        return path.open("a", encoding="utf-8", newline="\n")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    return os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")


@dataclass(frozen=True)
class ExistingState:
    completed: frozenset[tuple[str, str, str]]
    cumulative_cost: Decimal


def existing_state(path: Path, protocol_sha256: str) -> ExistingState:
    if not path.exists():
        return ExistingState(frozenset(), Decimal(0))
    ensure_private_file(path)
    completed: set[tuple[str, str, str]] = set()
    cumulative = Decimal(0)
    for number, value in enumerate(read_jsonl(path), 1):
        require(value.get("schema") == "openrouter-full-context-raw-call-v1", f"raw schema: {number}")
        require(value.get("protocol_sha256") == protocol_sha256, f"raw protocol binding: {number}")
        key = (value["pair_private_id"], value["model"], value["orientation"])
        require(key not in completed, f"duplicate raw call key: {number}")
        completed.add(key)
        cumulative += Decimal(str(value.get("cost_usd", "0")))
    return ExistingState(frozenset(completed), cumulative)


def planned_jobs(
    rows: list[dict[str, Any]], phase: str, models: Iterable[str]
) -> list[tuple[dict[str, Any], str, str]]:
    selected = [row for row in rows if phase == "full" or row["smoke"] is True]
    return [
        (row, model, orientation)
        for row in selected
        for model in models
        for orientation in ("AB", "BA")
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--raw-out", type=Path)
    parser.add_argument("--phase", choices=("smoke", "full"), required=True)
    parser.add_argument("--transport", choices=("dry-run", "mock", "live"), default="dry-run")
    parser.add_argument("--models", nargs="*")
    parser.add_argument("--launch-receipt", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, Any]:
    protocol, protocol_sha256 = load_protocol(args.protocol.resolve(), args.protocol_sha256)
    panel_path = args.panel.resolve()
    ensure_private_file(panel_path)
    rows = read_jsonl(panel_path)
    validate_private_panel(rows, protocol, protocol_sha256)
    catalog = model_catalog(protocol)
    models = args.models or list(catalog)
    require(models and len(models) == len(set(models)), "models must be unique")
    require(all(model in catalog for model in models), "model outside frozen exact catalog")
    phase_value = protocol["phases"][args.phase]
    cap = Decimal(str(phase_value.get("cumulative_usd_stop", phase_value.get("cumulative_usd_stop_including_smoke"))))
    jobs = planned_jobs(rows, args.phase, models)
    maximum_calls = int(phase_value["maximum_calls"])
    require(len(jobs) <= maximum_calls, "planned calls exceed frozen phase maximum")

    if args.transport == "dry-run":
        requests = [request_payload(row, orientation, model, protocol) for row, model, orientation in jobs]
        return {
            "status": "DRY_RUN_COMPLETE_NO_NETWORK",
            "phase": args.phase,
            "pairs": len({row["pair_private_id"] for row, _, _ in jobs}),
            "models": len(models),
            "requests": len(requests),
            "request_bytes_min": min(len(canonical_json(value).encode("utf-8")) for value in requests),
            "request_bytes_max": max(len(canonical_json(value).encode("utf-8")) for value in requests),
            "credential_read": false_value(),
            "network_calls": 0,
        }

    require(args.raw_out is not None, "mock/live transport requires --raw-out")
    raw_path = args.raw_out.resolve()
    state = existing_state(raw_path, protocol_sha256)
    cumulative = state.cumulative_cost
    require(cumulative <= cap, "existing cumulative cost exceeds phase cap")
    credential = ""
    if args.transport == "live":
        load_launch_receipt(args.launch_receipt, protocol_sha256, args.phase, cap)
        credential = os.environ.get(KEY_ENVIRONMENT_VARIABLE, "")
        require(bool(credential), f"missing {KEY_ENVIRONMENT_VARIABLE}")
        require("\n" not in credential and "\r" not in credential, "malformed credential")

    attempted = succeeded = parsed = skipped = 0
    with open_secure_append(raw_path) as handle:
        for row, model, orientation in jobs:
            key = (row["pair_private_id"], model, orientation)
            if key in state.completed:
                skipped += 1
                continue
            require(cumulative < cap or catalog[model]["input_usd_per_million"] == "0", "cost stop reached")
            payload = request_payload(row, orientation, model, protocol)
            request_sha = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
            started = time.monotonic()
            response: dict[str, Any] | None = None
            error: str | None = None
            try:
                response = (
                    mock_response(payload)
                    if args.transport == "mock"
                    else live_response(payload, credential, args.timeout_seconds)
                )
                cost = response_cost_usd(response, model, catalog)
                pick, parse_status = parse_final_pick(response)
                succeeded += 1
                parsed += int(pick is not None)
            except JudgeError as exception:
                cost = Decimal(0)
                pick, parse_status = None, "request_error"
                error = str(exception)
            elapsed = time.monotonic() - started
            cumulative += cost
            correct = None
            if pick is not None:
                correct = pick == ("A" if orientation == "AB" else "B")
            record = {
                "schema": "openrouter-full-context-raw-call-v1",
                "protocol_sha256": protocol_sha256,
                "pair_private_id": row["pair_private_id"],
                "panel": row["panel"],
                "gap_bin": row["gap_bin"],
                "smoke": row["smoke"],
                "model": model,
                "orientation": orientation,
                "request_sha256": request_sha,
                "request_contract": {
                    "temperature": payload["temperature"],
                    "seed": payload["seed"],
                    "reasoning": payload["reasoning"],
                    "provider": payload["provider"],
                    "max_tokens_omitted": "max_tokens" not in payload,
                    "full_code_utf8_bytes": [
                        len(row["better"]["code"].encode("utf-8")),
                        len(row["worse"]["code"].encode("utf-8")),
                    ],
                },
                "transport": args.transport,
                "elapsed_seconds": elapsed,
                "response": response,
                "error": error,
                "parse_status": parse_status,
                "final_pick": pick,
                "correct": correct,
                "cost_usd": format(cost, "f"),
                "cumulative_cost_usd": format(cumulative, "f"),
            }
            handle.write(canonical_json(record) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            attempted += 1
            if error is not None:
                raise JudgeError("call failed and was recorded; automatic retry is forbidden")
            if cumulative > cap:
                raise JudgeError("cumulative cost exceeded frozen stop after recorded response")
    return {
        "status": "MOCK_COMPLETE_NO_NETWORK" if args.transport == "mock" else "LIVE_PHASE_COMPLETE",
        "phase": args.phase,
        "planned_calls": len(jobs),
        "attempted_calls": attempted,
        "skipped_existing_calls": skipped,
        "successful_calls": succeeded,
        "parse_successes": parsed,
        "cumulative_cost_usd": format(cumulative, "f"),
        "raw_output_sha256": sha256_file(raw_path),
        "row_outcomes_emitted_to_stdout": false_value(),
    }


def false_value() -> bool:
    """Return False without using JSON-ish lowercase names in Python code."""

    return False


def main() -> None:
    print(canonical_json(run(parse_args())))


if __name__ == "__main__":
    main()
