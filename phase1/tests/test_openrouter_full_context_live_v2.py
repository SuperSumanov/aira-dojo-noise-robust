from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import analyze_openrouter_full_context_smoke_v2 as analyzer
from phase1 import openrouter_full_context_judge as base
from phase1 import openrouter_full_context_live_v2 as live


PHASE1 = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = PHASE1 / "openrouter_full_context_judge_v1.json"
AMENDMENT_PATH = PHASE1 / "openrouter_full_context_metric_omission_amendment_v2.json"
HARDENING_PATH = PHASE1 / "openrouter_full_context_live_hardening_v2.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def endpoint(identity: str) -> dict[str, object]:
    return {
        "id": identity,
        "run": "synthetic-run",
        "task": {
            "name": "synthetic-task",
            "desc": "Synthetic complete competition description",
            "higher_is_better": True,
        },
        "client": "synthetic-client",
        "hardware": "synthetic-hardware",
        "time_limit": 3600,
        "execution_timeout": 300,
        "code": "print('synthetic complete program')",
    }


def test_hardening_contract_binds_parent_and_panel() -> None:
    panel_sha = json.loads(HARDENING_PATH.read_text(encoding="utf-8"))["parent"][
        "private_panel_sha256"
    ]
    value, observed = live.load_hardening(
        HARDENING_PATH,
        sha256(HARDENING_PATH),
        sha256(PROTOCOL_PATH),
        sha256(AMENDMENT_PATH),
        panel_sha,
    )
    assert observed == sha256(HARDENING_PATH)
    assert value["request_hardening"]["provider"]["require_parameters"] is True


def test_hardened_request_keeps_full_context_and_privacy_fields() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    row = {"better": endpoint("better-id"), "worse": endpoint("worse-id")}
    model = protocol["model_catalog_snapshot"]["models"][0]["id"]
    hardening = json.loads(HARDENING_PATH.read_text(encoding="utf-8"))
    payload = live.hardened_request_payload(row, "AB", model, protocol, hardening)
    assert payload["provider"] == live.provider_contract(model, hardening)
    assert "max_tokens" not in payload
    assert "max_completion_tokens" not in payload
    assert row["better"]["code"] in base.canonical_json(payload)
    assert row["worse"]["code"] in base.canonical_json(payload)


def valid_router_response(model: str) -> dict[str, object]:
    return {
        "model": model,
        "choices": [{"message": {"content": "A"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 1, "cost": 0},
        "openrouter_metadata": {
            "requested": model,
            "attempt": 1,
            "endpoints": {
                "available": [
                    {"provider": "synthetic-provider", "model": model, "selected": True}
                ]
            },
            "pipeline": [],
        },
    }


def test_router_audit_accepts_exact_route_and_rejects_compression_or_drift() -> None:
    hardening = json.loads(HARDENING_PATH.read_text(encoding="utf-8"))
    model = live.frozen_models(hardening)[0]
    observed = live.validate_router_response(valid_router_response(model), model, hardening)
    assert observed["context_compression_detected"] is False

    compressed = valid_router_response(model)
    compressed["openrouter_metadata"]["pipeline"] = [
        {"type": "context_compression", "name": "context-compression"}
    ]
    with pytest.raises(base.JudgeError, match="context compression"):
        live.validate_router_response(compressed, model, hardening)

    drift = valid_router_response(model)
    drift["model"] = "unexpected/model"
    with pytest.raises(base.JudgeError, match="model drift"):
        live.validate_router_response(drift, model, hardening)

    fallback = valid_router_response(model)
    fallback["openrouter_metadata"]["attempt"] = 2
    with pytest.raises(base.JudgeError, match="attempt must be exactly one"):
        live.validate_router_response(fallback, model, hardening)

    missing_cost = valid_router_response(model)
    del missing_cost["usage"]["cost"]
    with pytest.raises(base.JudgeError, match="reported cost"):
        live.validate_router_response(missing_cost, model, hardening)

    nonfinite_cost = valid_router_response(model)
    nonfinite_cost["usage"]["cost"] = "NaN"
    with pytest.raises(base.JudgeError, match="reported response cost"):
        live.validate_router_response(nonfinite_cost, model, hardening)


def test_launch_receipt_is_bound_to_exact_runner_matrix_and_cost(tmp_path: Path) -> None:
    hardening = json.loads(HARDENING_PATH.read_text(encoding="utf-8"))
    models = live.frozen_models(hardening)
    receipt = {
        "protocol": live.LAUNCH_RECEIPT_NAME,
        "authorized": True,
        "judge_protocol_sha256": "p" * 64,
        "representation_sha256": "r" * 64,
        "hardening_sha256": "h" * 64,
        "private_panel_sha256": "a" * 64,
        "runner_sha256": "x" * 64,
        "analyzer_sha256": "z" * 64,
        "phase": "smoke",
        "models": models,
        "maximum_calls": 64,
        "cumulative_usd_stop": "2.00",
        "credential_source": "remote_dotenv_environment_only",
    }
    path = tmp_path / "launch.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    live.load_launch_receipt(
        path,
        "p" * 64,
        "r" * 64,
        "h" * 64,
        "a" * 64,
        "x" * 64,
        "z" * 64,
        "smoke",
        models,
        64,
        Decimal("2.00"),
    )
    receipt["models"] = list(reversed(models))
    path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(base.JudgeError, match="model matrix"):
        live.load_launch_receipt(
            path,
            "p" * 64,
            "r" * 64,
            "h" * 64,
            "a" * 64,
            "x" * 64,
            "z" * 64,
            "smoke",
            models,
            64,
            Decimal("2.00"),
        )


def synthetic_analysis_inputs(
    *, inconsistent_model: str | None = None,
) -> tuple[
    dict[str, object],
    str,
    dict[str, object],
    str,
    str,
    list[dict[str, object]],
    dict[str, dict[str, object]],
    list[dict[str, object]],
    dict[str, str],
]:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    hardening = json.loads(HARDENING_PATH.read_text(encoding="utf-8"))
    protocol_sha = sha256(PROTOCOL_PATH)
    hardening_sha = sha256(HARDENING_PATH)
    runner_sha = sha256(PHASE1 / "openrouter_full_context_live_v2.py")
    panel: list[dict[str, object]] = []
    panel_by_id: dict[str, dict[str, object]] = {}
    for index in range(8):
        pair_id = f"{index:064x}"
        first = endpoint(f"better-{index}")
        second = endpoint(f"worse-{index}")
        first["run"] = second["run"] = f"run-{index}"
        first["task"] = second["task"] = {
            "name": f"task-{index % 4}",
            "desc": "Synthetic task",
            "higher_is_better": True,
        }
        row = {"pair_private_id": pair_id, "better": first, "worse": second, "smoke": True}
        panel.append(row)
        panel_by_id[pair_id] = row
    raw: list[dict[str, object]] = []
    cumulative = 0
    for pair_id in panel_by_id:
        for model in live.frozen_models(hardening):
            for orientation in ("AB", "BA"):
                correct = not (model == inconsistent_model and orientation == "BA")
                pick = "A" if orientation == "AB" else ("B" if correct else "A")
                payload = live.hardened_request_payload(
                    panel_by_id[pair_id], orientation, model, protocol, hardening
                )
                response = valid_router_response(model)
                response["choices"][0]["message"]["content"] = pick
                router_audit = live.validate_router_response(response, model, hardening)
                raw.append(
                    {
                        "schema": live.RAW_SCHEMA,
                        "protocol_sha256": protocol_sha,
                        "representation_contract_sha256": sha256(AMENDMENT_PATH),
                        "hardening_sha256": hardening_sha,
                        "private_panel_sha256": hardening["parent"]["private_panel_sha256"],
                        "runner_sha256": runner_sha,
                        "launch_receipt_sha256": "l" * 64,
                        "pair_private_id": pair_id,
                        "model": model,
                        "orientation": orientation,
                        "transport": "live",
                        "request_envelope_sha256": live.request_envelope_sha256(
                            payload, live.nonsecret_headers(hardening)
                        ),
                        "request_contract": {
                            "provider": live.provider_contract(model, hardening),
                            "router_metadata_header": "enabled",
                            "max_tokens_omitted": True,
                            "maximum_catalog_charge_bound_usd": format(
                                live.maximum_catalog_charge_bound(payload, model, hardening),
                                "f",
                            ),
                        },
                        "response": response,
                        "router_audit": router_audit,
                        "error": None,
                        "parse_status": "parsed",
                        "final_pick": pick,
                        "correct": correct,
                        "cost_usd": "0",
                        "cumulative_cost_usd": str(cumulative),
                    }
                )
    return (
        protocol,
        protocol_sha,
        hardening,
        hardening_sha,
        runner_sha,
        panel,
        panel_by_id,
        raw,
        {
            "runner_sha256": runner_sha,
            "analyzer_sha256": sha256(PHASE1 / "analyze_openrouter_full_context_smoke_v2.py"),
            "launch_receipt_sha256": "l" * 64,
            "intent_log_sha256": "i" * 64,
        },
    )


def test_resume_requires_exact_fsynced_intent_and_completed_prefix(tmp_path: Path) -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    hardening = json.loads(HARDENING_PATH.read_text(encoding="utf-8"))
    model = live.frozen_models(hardening)[0]
    row = {
        "pair_private_id": "0" * 64,
        "better": endpoint("better-id"),
        "worse": endpoint("worse-id"),
    }
    payload = live.hardened_request_payload(row, "AB", model, protocol, hardening)
    headers = live.nonsecret_headers(hardening)
    maximum_charge = live.maximum_catalog_charge_bound(payload, model, hardening)
    envelope = live.request_envelope_sha256(payload, headers)
    prepared = {
        "key": (row["pair_private_id"], model, "AB"),
        "payload": payload,
        "request_envelope_sha256": envelope,
        "maximum_charge": maximum_charge,
        "protocol": protocol,
    }
    protocol_sha = sha256(PROTOCOL_PATH)
    representation_sha = sha256(AMENDMENT_PATH)
    hardening_sha = sha256(HARDENING_PATH)
    panel_sha = "p" * 64
    runner_sha = "r" * 64
    receipt_sha = "l" * 64
    response = valid_router_response(model)
    audit = live.validate_router_response(response, model, hardening)
    intent = {
        "schema": live.INTENT_SCHEMA,
        "protocol_sha256": protocol_sha,
        "representation_contract_sha256": representation_sha,
        "hardening_sha256": hardening_sha,
        "private_panel_sha256": panel_sha,
        "runner_sha256": runner_sha,
        "launch_receipt_sha256": receipt_sha,
        "pair_private_id": row["pair_private_id"],
        "model": model,
        "orientation": "AB",
        "transport": "live",
        "request_envelope_sha256": envelope,
        "maximum_catalog_charge_bound_usd": format(maximum_charge, "f"),
    }
    raw = {
        "schema": live.RAW_SCHEMA,
        "protocol_sha256": protocol_sha,
        "representation_contract_sha256": representation_sha,
        "hardening_sha256": hardening_sha,
        "private_panel_sha256": panel_sha,
        "runner_sha256": runner_sha,
        "launch_receipt_sha256": receipt_sha,
        "pair_private_id": row["pair_private_id"],
        "model": model,
        "orientation": "AB",
        "transport": "live",
        "request_envelope_sha256": envelope,
        "request_contract": {
            "provider": payload["provider"],
            "router_metadata_header": "enabled",
            "max_tokens_omitted": True,
            "maximum_catalog_charge_bound_usd": format(maximum_charge, "f"),
        },
        "response": response,
        "router_audit": audit,
        "error": None,
        "parse_status": "parsed",
        "final_pick": "A",
        "correct": True,
        "cost_usd": "0",
        "cumulative_cost_usd": "0",
    }
    intent_path = tmp_path / "intent.jsonl"
    raw_path = tmp_path / "raw.jsonl"
    intent_path.write_text(base.canonical_json(intent) + "\n", encoding="utf-8")
    raw_path.write_text(base.canonical_json(raw) + "\n", encoding="utf-8")
    completed, cumulative = live.read_existing_state(
        raw_path,
        intent_path,
        protocol_sha,
        representation_sha,
        hardening_sha,
        panel_sha,
        runner_sha,
        receipt_sha,
        "live",
        [prepared],
        hardening,
    )
    assert completed == {prepared["key"]}
    assert cumulative == 0

    intent_path.write_text(
        base.canonical_json(intent) + "\n" + base.canonical_json(intent) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(base.JudgeError, match="pending intent"):
        live.read_existing_state(
            raw_path,
            intent_path,
            protocol_sha,
            representation_sha,
            hardening_sha,
            panel_sha,
            runner_sha,
            receipt_sha,
            "live",
            [prepared],
            hardening,
        )


def test_smoke_analyzer_gates_reliability_before_descriptive_accuracy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_path = tmp_path / "raw.jsonl"
    raw_path.write_text("synthetic", encoding="utf-8")
    args = argparse.Namespace(
        protocol=PROTOCOL_PATH,
        protocol_sha256=sha256(PROTOCOL_PATH),
        metric_omission_amendment=AMENDMENT_PATH,
        metric_omission_amendment_sha256=sha256(AMENDMENT_PATH),
        hardening=HARDENING_PATH,
        hardening_sha256=sha256(HARDENING_PATH),
        panel=tmp_path / "panel.jsonl",
        raw=raw_path,
        expected_transport="live",
    )
    passing = synthetic_analysis_inputs()
    monkeypatch.setattr(analyzer, "load_inputs", lambda _args: passing)
    result = analyzer.analyze(args)
    assert result["classification"].endswith("GATES_PASS")
    assert result["accuracy_used_as_gate"] is False

    model = live.frozen_models(passing[2])[0]
    failing = synthetic_analysis_inputs(inconsistent_model=model)
    monkeypatch.setattr(analyzer, "load_inputs", lambda _args: failing)
    result = analyzer.analyze(args)
    assert result["classification"].endswith("GATES_FAIL")
    failed_row = next(row for row in result["per_model_reliability_then_accuracy"] if row["model"] == model)
    assert failed_row["reliability"]["gate_pass"] is False
