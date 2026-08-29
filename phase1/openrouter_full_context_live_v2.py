#!/usr/bin/env python3
"""Hardened live transport for the frozen full-context evaluator smoke.

This module preserves the v1 scientific prompt and panel contract while adding
transport evidence that was missing from the original inert harness.  A live run
requires an exact-SHA launch receipt and reads one credential from the process
environment only.  It never loads dotenv files or emits row outcomes to stdout.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Iterable
import urllib.error
import urllib.request

from phase1 import openrouter_full_context_judge as base


HARDENING_NAME = "openrouter-full-context-live-hardening-v2"
HARDENING_STATUS = "FROZEN_AFTER_PANEL_FEASIBILITY_BEFORE_ANY_LIVE_CALL"
LAUNCH_RECEIPT_NAME = "openrouter-full-context-live-launch-receipt-v2"
RAW_SCHEMA = "openrouter-full-context-raw-call-v2"
INTENT_SCHEMA = "openrouter-full-context-call-intent-v2"
ROUTER_METADATA_HEADER = "X-OpenRouter-Metadata"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise base.JudgeError(message)


def load_hardening(
    path: Path,
    expected_sha256: str,
    protocol_sha256: str,
    representation_sha256: str,
    panel_sha256: str,
) -> tuple[dict[str, Any], str]:
    observed = base.sha256_file(path)
    require(observed == expected_sha256, "hardening SHA mismatch")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "hardening object required")
    require(value.get("protocol") == HARDENING_NAME, "hardening name mismatch")
    require(value.get("status") == HARDENING_STATUS, "hardening status mismatch")
    parent = value.get("parent")
    require(isinstance(parent, dict), "hardening parent object required")
    require(parent.get("judge_protocol_sha256") == protocol_sha256, "hardening protocol binding")
    require(
        parent.get("representation_sha256") == representation_sha256,
        "hardening representation binding",
    )
    require(parent.get("private_panel_sha256") == panel_sha256, "hardening panel binding")
    request = value.get("request_hardening")
    require(isinstance(request, dict), "request hardening object required")
    require(request.get("input_truncation") is False, "input truncation drift")
    require(
        request.get("max_tokens_or_max_completion_tokens_field") == "OMITTED",
        "completion cap drift",
    )
    expected_provider = {
        "zdr": True,
        "data_collection": "deny",
        "require_parameters": True,
        "allow_fallbacks": False,
        "sort": "price",
    }
    require(request.get("provider") == expected_provider, "provider hardening drift")
    require(
        request.get("provider_max_price_from_catalog_recheck") is True,
        "provider max-price hardening drift",
    )
    headers = request.get("nonsecret_headers")
    require(isinstance(headers, dict), "nonsecret headers required")
    require(headers.get(ROUTER_METADATA_HEADER) == "enabled", "router metadata disabled")
    return value, observed


def frozen_models(hardening: dict[str, Any]) -> list[str]:
    rows = hardening["catalog_recheck"]["models"]
    result = [row["id"] for row in rows]
    require(result and len(result) == len(set(result)), "hardening model catalog invalid")
    return result


def canonical_models(hardening: dict[str, Any]) -> dict[str, str]:
    return {
        row["id"]: row["canonical_slug"]
        for row in hardening["catalog_recheck"]["models"]
    }


def provider_contract(model: str, hardening: dict[str, Any]) -> dict[str, Any]:
    rows = {row["id"]: row for row in hardening["catalog_recheck"]["models"]}
    require(model in rows, "model missing from hardening catalog")
    row = rows[model]
    return {
        "zdr": True,
        "data_collection": "deny",
        "require_parameters": True,
        "allow_fallbacks": False,
        "sort": "price",
        "max_price": {
            "prompt": float(row["prompt_usd_per_million_at_recheck"]),
            "completion": float(row["completion_usd_per_million_at_recheck"]),
        },
    }


def hardened_request_payload(
    row: dict[str, Any],
    orientation: str,
    model: str,
    protocol: dict[str, Any],
    hardening: dict[str, Any],
) -> dict[str, Any]:
    payload = base.request_payload(row, orientation, model, protocol)
    provider = provider_contract(model, hardening)
    payload["provider"] = provider
    require(provider == provider_contract(model, hardening), "request provider contract drift")
    require(
        "max_tokens" not in payload and "max_completion_tokens" not in payload,
        "completion cap added",
    )
    return payload


def maximum_catalog_charge_bound(
    payload: dict[str, Any], model: str, hardening: dict[str, Any]
) -> Decimal:
    rows = {row["id"]: row for row in hardening["catalog_recheck"]["models"]}
    require(model in rows, "model missing from cost catalog")
    row = rows[model]
    input_upper_bound = len(base.canonical_json(payload).encode("utf-8"))
    completion_upper_bound = max(
        int(row["context_length"]), int(row["max_completion_tokens"])
    )
    return (
        Decimal(input_upper_bound) * Decimal(row["prompt_usd_per_million_at_recheck"])
        + Decimal(completion_upper_bound)
        * Decimal(row["completion_usd_per_million_at_recheck"])
    ) / Decimal(1_000_000)


def nonsecret_headers(hardening: dict[str, Any]) -> dict[str, str]:
    value = hardening["request_hardening"]["nonsecret_headers"]
    require(isinstance(value, dict) and value, "nonsecret header contract")
    result = {str(key): str(item) for key, item in value.items()}
    require("Authorization" not in result, "authorization must not enter public headers")
    return result


def request_envelope_sha256(payload: dict[str, Any], headers: dict[str, str]) -> str:
    envelope = {"body": payload, "nonsecret_headers": headers}
    return hashlib.sha256(base.canonical_json(envelope).encode("utf-8")).hexdigest()


def validate_router_response(
    response: dict[str, Any], requested_model: str, hardening: dict[str, Any]
) -> dict[str, Any]:
    allowed = {requested_model, canonical_models(hardening)[requested_model]}
    require(response.get("model") in allowed, "response model drift")
    metadata = response.get("openrouter_metadata")
    require(isinstance(metadata, dict), "missing router metadata")
    require(metadata.get("requested") == requested_model, "router requested model drift")
    attempt = metadata.get("attempt")
    require(type(attempt) is int and attempt == 1, "router attempt must be exactly one")
    endpoints = metadata.get("endpoints")
    require(isinstance(endpoints, dict), "router endpoint metadata missing")
    available = endpoints.get("available")
    require(isinstance(available, list), "router available endpoints missing")
    selected = [item for item in available if isinstance(item, dict) and item.get("selected") is True]
    require(len(selected) == 1, "router selected endpoint is not unique")
    require(selected[0].get("model") in allowed, "selected endpoint model drift")
    provider = selected[0].get("provider")
    require(isinstance(provider, str) and provider.strip(), "selected provider missing")
    pipeline = metadata.get("pipeline", [])
    require(isinstance(pipeline, list), "router pipeline metadata invalid")
    compressed = [
        item
        for item in pipeline
        if isinstance(item, dict)
        and (
            item.get("type") == "context_compression"
            or item.get("name") == "context-compression"
        )
    ]
    require(not compressed, "router context compression detected")
    usage = response.get("usage")
    require(isinstance(usage, dict), "successful response missing usage")
    require(
        type(usage.get("prompt_tokens")) is int and usage["prompt_tokens"] >= 0,
        "successful response missing prompt usage",
    )
    require(
        type(usage.get("completion_tokens")) is int
        and usage["completion_tokens"] >= 0,
        "successful response missing completion usage",
    )
    try:
        reported_cost = Decimal(str(usage["cost"]))
    except (KeyError, InvalidOperation, ValueError) as error:
        raise base.JudgeError("successful response missing valid reported cost") from error
    require(reported_cost.is_finite() and reported_cost >= 0, "invalid reported response cost")
    return {
        "router_metadata_present": True,
        "requested_model_exact": True,
        "response_model_allowed": True,
        "selected_endpoint_unique": True,
        "selected_provider": provider,
        "router_attempt": 1,
        "context_compression_detected": False,
    }


def mock_response(payload: dict[str, Any], hardening: dict[str, Any]) -> dict[str, Any]:
    digest = hashlib.sha256(base.canonical_json(payload).encode("utf-8")).digest()
    pick = "A" if digest[0] % 2 == 0 else "B"
    model = payload["model"]
    return {
        "id": "mock-" + hashlib.sha256(base.canonical_json(payload).encode()).hexdigest()[:16],
        "model": model,
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
        "usage": {
            "prompt_tokens": max(1, len(base.canonical_json(payload).encode("utf-8")) // 4),
            "completion_tokens": 12,
            "cost": 0,
        },
        "openrouter_metadata": {
            "requested": model,
            "strategy": "direct",
            "attempt": 1,
            "is_byok": False,
            "endpoints": {
                "total": 1,
                "available": [{"provider": "mock", "model": model, "selected": True}],
            },
            "attempts": [{"provider": "mock", "model": model, "status": 200}],
            "pipeline": [],
        },
    }


def live_response(
    payload: dict[str, Any],
    credential: str,
    timeout: float,
    headers: dict[str, str],
) -> dict[str, Any]:
    request_headers = dict(headers)
    request_headers["Authorization"] = "Bearer " + credential
    request = urllib.request.Request(
        base.API_URL,
        data=base.canonical_json(payload).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response_handle:
            value = json.load(response_handle)
    except urllib.error.HTTPError as error:
        raise base.JudgeError(f"provider HTTP error {error.code}; retry forbidden") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise base.JudgeError("ambiguous transport failure; retry forbidden") from error
    require(isinstance(value, dict), "provider response object required")
    return value


def load_launch_receipt(
    path: Path | None,
    protocol_sha256: str,
    representation_sha256: str,
    hardening_sha256: str,
    panel_sha256: str,
    runner_sha256: str,
    analyzer_sha256: str,
    phase: str,
    models: list[str],
    maximum_calls: int,
    cap: Decimal,
) -> dict[str, Any]:
    require(path is not None, "live transport requires a v2 launch receipt")
    require(path.is_file() and not path.is_symlink(), "unsafe launch receipt")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "launch receipt object required")
    require(value.get("protocol") == LAUNCH_RECEIPT_NAME, "launch receipt name")
    require(value.get("authorized") is True, "live calls not authorized")
    require(value.get("judge_protocol_sha256") == protocol_sha256, "launch protocol binding")
    require(
        value.get("representation_sha256") == representation_sha256,
        "launch representation binding",
    )
    require(value.get("hardening_sha256") == hardening_sha256, "launch hardening binding")
    require(value.get("private_panel_sha256") == panel_sha256, "launch panel binding")
    require(value.get("runner_sha256") == runner_sha256, "launch runner binding")
    require(value.get("analyzer_sha256") == analyzer_sha256, "launch analyzer binding")
    require(value.get("phase") == phase, "launch phase drift")
    require(value.get("models") == models, "launch model matrix drift")
    require(value.get("maximum_calls") == maximum_calls, "launch call budget drift")
    require(Decimal(str(value.get("cumulative_usd_stop"))) == cap, "launch cost cap drift")
    require(
        value.get("credential_source") == "remote_dotenv_environment_only",
        "launch credential source drift",
    )
    return value


def read_existing_state(
    raw_path: Path,
    intent_path: Path,
    protocol_sha256: str,
    representation_sha256: str,
    hardening_sha256: str,
    panel_sha256: str,
    runner_sha256: str,
    launch_receipt_sha256: str,
    transport: str,
    prepared_jobs: list[dict[str, Any]],
    hardening: dict[str, Any],
) -> tuple[frozenset[tuple[str, str, str]], Decimal]:
    """Validate a resumable prefix without ever retrying an ambiguous call."""

    if not raw_path.exists() and not intent_path.exists():
        return frozenset(), Decimal(0)
    require(raw_path.exists() and intent_path.exists(), "raw/intent journal presence mismatch")
    base.ensure_private_file(raw_path)
    base.ensure_private_file(intent_path)
    raw_rows = base.read_jsonl(raw_path)
    intent_rows = base.read_jsonl(intent_path)
    require(len(raw_rows) == len(intent_rows), "pending intent makes resume ambiguous")
    require(len(raw_rows) <= len(prepared_jobs), "existing rows exceed planned matrix")

    completed: set[tuple[str, str, str]] = set()
    cumulative = Decimal(0)
    catalog = base.model_catalog(prepared_jobs[0]["protocol"]) if prepared_jobs else {}
    for number, (intent, value, prepared) in enumerate(
        zip(intent_rows, raw_rows, prepared_jobs), 1
    ):
        expected_key = prepared["key"]
        require(intent.get("schema") == INTENT_SCHEMA, f"intent schema: {number}")
        for field, expected in (
            ("protocol_sha256", protocol_sha256),
            ("representation_contract_sha256", representation_sha256),
            ("hardening_sha256", hardening_sha256),
            ("private_panel_sha256", panel_sha256),
            ("runner_sha256", runner_sha256),
            ("launch_receipt_sha256", launch_receipt_sha256),
            ("transport", transport),
            ("request_envelope_sha256", prepared["request_envelope_sha256"]),
            ("maximum_catalog_charge_bound_usd", format(prepared["maximum_charge"], "f")),
        ):
            require(intent.get(field) == expected, f"intent {field}: {number}")
        intent_key = (
            intent.get("pair_private_id"),
            intent.get("model"),
            intent.get("orientation"),
        )
        require(intent_key == expected_key, f"intent is not exact planned prefix: {number}")

        require(value.get("schema") == RAW_SCHEMA, f"raw schema: {number}")
        for field, expected in (
            ("protocol_sha256", protocol_sha256),
            ("representation_contract_sha256", representation_sha256),
            ("hardening_sha256", hardening_sha256),
            ("private_panel_sha256", panel_sha256),
            ("runner_sha256", runner_sha256),
            ("launch_receipt_sha256", launch_receipt_sha256),
            ("transport", transport),
            ("request_envelope_sha256", prepared["request_envelope_sha256"]),
        ):
            require(value.get(field) == expected, f"raw {field}: {number}")
        key = (value.get("pair_private_id"), value.get("model"), value.get("orientation"))
        require(key == expected_key, f"raw is not exact planned prefix: {number}")
        require(key not in completed, f"duplicate raw call key: {number}")
        require(value.get("error") is None, f"failed record forbids resume: {number}")
        request_contract = value.get("request_contract")
        require(isinstance(request_contract, dict), f"request contract missing: {number}")
        require(
            request_contract.get("provider") == prepared["payload"]["provider"],
            f"request provider drift: {number}",
        )
        require(
            request_contract.get("router_metadata_header")
            == nonsecret_headers(hardening)[ROUTER_METADATA_HEADER],
            f"router metadata header drift: {number}",
        )
        require(request_contract.get("max_tokens_omitted") is True, f"completion cap drift: {number}")
        require(
            request_contract.get("maximum_catalog_charge_bound_usd")
            == format(prepared["maximum_charge"], "f"),
            f"maximum charge binding drift: {number}",
        )

        response = value.get("response")
        require(isinstance(response, dict), f"completed response missing: {number}")
        expected_audit = validate_router_response(response, str(value.get("model")), hardening)
        require(value.get("router_audit") == expected_audit, f"router audit drift: {number}")
        cost = base.response_cost_usd(response, str(value.get("model")), catalog)
        require(Decimal(str(value.get("cost_usd"))) == cost, f"recorded cost drift: {number}")
        require(cost <= prepared["maximum_charge"], f"cost exceeded catalog bound: {number}")
        pick, parse_status = base.parse_final_pick(response)
        require(value.get("final_pick") == pick, f"recorded pick drift: {number}")
        require(value.get("parse_status") == parse_status, f"parse status drift: {number}")
        expected_correct = None
        if pick is not None:
            expected_correct = pick == ("A" if expected_key[2] == "AB" else "B")
        require(value.get("correct") == expected_correct, f"correctness drift: {number}")

        completed.add(key)
        cumulative += cost
        require(
            Decimal(str(value.get("cumulative_cost_usd"))) == cumulative,
            f"cumulative cost chain: {number}",
        )
    return frozenset(completed), cumulative


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
    parser.add_argument("--metric-omission-amendment", type=Path, required=True)
    parser.add_argument("--metric-omission-amendment-sha256", required=True)
    parser.add_argument("--hardening", type=Path, required=True)
    parser.add_argument("--hardening-sha256", required=True)
    parser.add_argument("--analyzer", type=Path, required=True)
    parser.add_argument("--analyzer-sha256", required=True)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--raw-out", type=Path)
    parser.add_argument("--intent-log", type=Path)
    parser.add_argument("--phase", choices=("smoke", "full"), required=True)
    parser.add_argument("--transport", choices=("dry-run", "mock", "live"), default="dry-run")
    parser.add_argument("--models", nargs="*")
    parser.add_argument("--launch-receipt", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = args.protocol.resolve()
    protocol, protocol_sha256 = base.load_protocol(protocol_path, args.protocol_sha256)
    amendment_path = args.metric_omission_amendment.resolve()
    _, representation_sha256 = base.load_metric_omission_amendment(
        amendment_path,
        args.metric_omission_amendment_sha256,
        protocol_sha256,
    )
    panel_path = args.panel.resolve()
    base.ensure_private_file(panel_path)
    panel_sha256 = base.sha256_file(panel_path)
    hardening, hardening_sha256 = load_hardening(
        args.hardening.resolve(),
        args.hardening_sha256,
        protocol_sha256,
        representation_sha256,
        panel_sha256,
    )
    rows = base.read_jsonl(panel_path)
    base.validate_private_panel(
        rows,
        protocol,
        protocol_sha256,
        "metric_omission_amendment_v2",
        representation_sha256,
        False,
    )
    catalog = base.model_catalog(protocol)
    exact_models = frozen_models(hardening)
    require(set(exact_models) == set(catalog), "hardening and parent model catalogs differ")
    models = args.models or exact_models
    require(models == exact_models, "live v2 requires the exact frozen model order")
    phase_value = protocol["phases"][args.phase]
    cap = Decimal(
        str(
            phase_value.get(
                "cumulative_usd_stop",
                phase_value.get("cumulative_usd_stop_including_smoke"),
            )
        )
    )
    jobs = planned_jobs(rows, args.phase, models)
    maximum_calls = int(phase_value["maximum_calls"])
    require(len(jobs) == maximum_calls, "planned calls do not equal frozen phase matrix")
    authorization = hardening["authorization"]
    require(args.phase == authorization["this_launch_phase"], "hardening phase drift")
    require(
        maximum_calls == int(authorization["this_launch_maximum_calls"]),
        "hardening call budget drift",
    )
    require(
        cap == Decimal(str(authorization["this_launch_cumulative_usd_stop"])),
        "hardening cost cap drift",
    )
    require(
        args.timeout_seconds == float(hardening["request_hardening"]["timeout_seconds"]),
        "transport timeout drift",
    )
    headers = nonsecret_headers(hardening)
    analyzer_sha256 = base.sha256_file(args.analyzer.resolve())
    require(analyzer_sha256 == args.analyzer_sha256, "analyzer SHA mismatch")

    prepared_jobs: list[dict[str, Any]] = []
    for row, model, orientation in jobs:
        payload = hardened_request_payload(row, orientation, model, protocol, hardening)
        prepared_jobs.append(
            {
                "row": row,
                "model": model,
                "orientation": orientation,
                "key": (row["pair_private_id"], model, orientation),
                "payload": payload,
                "request_envelope_sha256": request_envelope_sha256(payload, headers),
                "maximum_charge": maximum_catalog_charge_bound(payload, model, hardening),
                "protocol": protocol,
            }
        )

    if args.transport == "dry-run":
        requests = [prepared["payload"] for prepared in prepared_jobs]
        sizes = [len(base.canonical_json(value).encode("utf-8")) for value in requests]
        return {
            "status": "DRY_RUN_COMPLETE_NO_NETWORK",
            "phase": args.phase,
            "pairs": len({row["pair_private_id"] for row, _, _ in jobs}),
            "models": len(models),
            "requests": len(requests),
            "request_bytes_min": min(sizes),
            "request_bytes_max": max(sizes),
            "request_bytes_total": sum(sizes),
            "privacy_fields_exact": all(
                value["provider"] == provider_contract(value["model"], hardening)
                for value in requests
            ),
            "router_metadata_header": headers[ROUTER_METADATA_HEADER],
            "completion_cap_omitted": all(
                "max_tokens" not in value and "max_completion_tokens" not in value
                for value in requests
            ),
            "credential_read": False,
            "network_calls": 0,
        }

    require(args.raw_out is not None, "mock/live transport requires --raw-out")
    require(args.intent_log is not None, "mock/live transport requires --intent-log")
    raw_path = args.raw_out.resolve()
    intent_path = args.intent_log.resolve()
    require(raw_path != intent_path, "raw and intent paths must differ")
    runner_sha256 = base.sha256_file(Path(__file__).resolve())
    load_launch_receipt(
        args.launch_receipt,
        protocol_sha256,
        representation_sha256,
        hardening_sha256,
        panel_sha256,
        runner_sha256,
        analyzer_sha256,
        args.phase,
        models,
        maximum_calls,
        cap,
    )
    launch_receipt_sha256 = base.sha256_file(args.launch_receipt.resolve())
    completed, cumulative = read_existing_state(
        raw_path,
        intent_path,
        protocol_sha256,
        representation_sha256,
        hardening_sha256,
        panel_sha256,
        runner_sha256,
        launch_receipt_sha256,
        args.transport,
        prepared_jobs,
        hardening,
    )
    require(cumulative <= cap, "existing cumulative cost exceeds phase cap")
    credential = ""
    if args.transport == "live":
        credential = os.environ.get(base.KEY_ENVIRONMENT_VARIABLE, "")
        require(bool(credential), f"missing {base.KEY_ENVIRONMENT_VARIABLE}")
        require("\n" not in credential and "\r" not in credential, "malformed credential")

    attempted = succeeded = parsed = skipped = 0
    with base.open_secure_append(intent_path) as intent_handle, base.open_secure_append(
        raw_path
    ) as handle:
        for prepared in prepared_jobs:
            row = prepared["row"]
            model = prepared["model"]
            orientation = prepared["orientation"]
            key = prepared["key"]
            if key in completed:
                skipped += 1
                continue
            require(
                cumulative < cap or catalog[model]["input_usd_per_million"] == "0",
                "cost stop reached",
            )
            payload = prepared["payload"]
            maximum_charge = prepared["maximum_charge"]
            require(
                cumulative + maximum_charge <= cap,
                "pre-call maximum charge would exceed frozen cost stop",
            )
            envelope_sha256 = prepared["request_envelope_sha256"]
            intent_record = {
                "schema": INTENT_SCHEMA,
                "protocol_sha256": protocol_sha256,
                "representation_contract_sha256": representation_sha256,
                "hardening_sha256": hardening_sha256,
                "private_panel_sha256": panel_sha256,
                "runner_sha256": runner_sha256,
                "launch_receipt_sha256": launch_receipt_sha256,
                "pair_private_id": row["pair_private_id"],
                "model": model,
                "orientation": orientation,
                "transport": args.transport,
                "request_envelope_sha256": envelope_sha256,
                "maximum_catalog_charge_bound_usd": format(maximum_charge, "f"),
            }
            intent_handle.write(base.canonical_json(intent_record) + "\n")
            intent_handle.flush()
            os.fsync(intent_handle.fileno())
            started = time.monotonic()
            response: dict[str, Any] | None = None
            router_audit: dict[str, Any] | None = None
            error: str | None = None
            cost = Decimal(0)
            try:
                response = (
                    mock_response(payload, hardening)
                    if args.transport == "mock"
                    else live_response(payload, credential, args.timeout_seconds, headers)
                )
                router_audit = validate_router_response(response, model, hardening)
                cost = base.response_cost_usd(response, model, catalog)
                require(cost <= maximum_charge, "reported cost exceeded catalog upper bound")
                pick, parse_status = base.parse_final_pick(response)
                succeeded += 1
                parsed += int(pick is not None)
            except base.JudgeError as exception:
                if response is not None and cost == 0:
                    try:
                        cost = base.response_cost_usd(response, model, catalog)
                    except base.JudgeError:
                        cost = Decimal(0)
                pick, parse_status = None, "request_error"
                error = str(exception)
            elapsed = time.monotonic() - started
            cumulative += cost
            correct = None
            if pick is not None:
                correct = pick == ("A" if orientation == "AB" else "B")
            record = {
                "schema": RAW_SCHEMA,
                "protocol_sha256": protocol_sha256,
                "representation_contract_sha256": representation_sha256,
                "hardening_sha256": hardening_sha256,
                "private_panel_sha256": panel_sha256,
                "runner_sha256": runner_sha256,
                "launch_receipt_sha256": launch_receipt_sha256,
                "pair_private_id": row["pair_private_id"],
                "panel": row["panel"],
                "gap_bin": row["gap_bin"],
                "smoke": row["smoke"],
                "model": model,
                "orientation": orientation,
                "request_envelope_sha256": envelope_sha256,
                "request_contract": {
                    "temperature": payload["temperature"],
                    "seed": payload["seed"],
                    "reasoning": payload["reasoning"],
                    "provider": payload["provider"],
                    "maximum_catalog_charge_bound_usd": format(maximum_charge, "f"),
                    "router_metadata_header": headers[ROUTER_METADATA_HEADER],
                    "max_tokens_omitted": (
                        "max_tokens" not in payload and "max_completion_tokens" not in payload
                    ),
                    "full_code_utf8_bytes": [
                        len(row["better"]["code"].encode("utf-8")),
                        len(row["worse"]["code"].encode("utf-8")),
                    ],
                },
                "transport": args.transport,
                "elapsed_seconds": elapsed,
                "response": response,
                "router_audit": router_audit,
                "error": error,
                "parse_status": parse_status,
                "final_pick": pick,
                "correct": correct,
                "cost_usd": format(cost, "f"),
                "cumulative_cost_usd": format(cumulative, "f"),
            }
            handle.write(base.canonical_json(record) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            attempted += 1
            if error is not None:
                raise base.JudgeError("call failed and was recorded; automatic retry is forbidden")
            if cumulative > cap:
                raise base.JudgeError("cumulative cost exceeded frozen stop after recorded response")
    return {
        "status": "MOCK_COMPLETE_NO_NETWORK" if args.transport == "mock" else "LIVE_PHASE_COMPLETE",
        "phase": args.phase,
        "planned_calls": len(jobs),
        "attempted_calls": attempted,
        "skipped_existing_calls": skipped,
        "successful_calls": succeeded,
        "parse_successes": parsed,
        "cumulative_cost_usd": format(cumulative, "f"),
        "raw_output_sha256": base.sha256_file(raw_path),
        "intent_log_sha256": base.sha256_file(intent_path),
        "row_outcomes_emitted_to_stdout": False,
    }


def main() -> None:
    print(base.canonical_json(run(parse_args())))


if __name__ == "__main__":
    main()
