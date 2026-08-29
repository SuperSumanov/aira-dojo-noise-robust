#!/usr/bin/env python3
"""Analyze the frozen OpenRouter smoke without publishing private rows or reasoning."""

from __future__ import annotations

import argparse
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path
import random
from typing import Any

from phase1 import openrouter_full_context_judge as base
from phase1 import openrouter_full_context_live_v2 as live


ANALYSIS_SCHEMA = "openrouter-full-context-smoke-analysis-v2"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise base.JudgeError(message)


def percentile(sorted_values: list[float], probability: float) -> float:
    require(bool(sorted_values), "percentile requires values")
    index = max(0, min(len(sorted_values) - 1, int(probability * len(sorted_values))))
    return sorted_values[index]


def clustered_bootstrap(
    values: list[tuple[str, float]], seed: int, repetitions: int
) -> list[float] | None:
    by_cluster: dict[str, list[float]] = defaultdict(list)
    for cluster, value in values:
        by_cluster[cluster].append(value)
    clusters = sorted(by_cluster)
    if len(clusters) < 2:
        return None
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(repetitions):
        sampled = [rng.choice(clusters) for _ in clusters]
        flat = [value for cluster in sampled for value in by_cluster[cluster]]
        estimates.append(sum(flat) / len(flat))
    estimates.sort()
    return [percentile(estimates, 0.025), percentile(estimates, 0.975)]


def load_inputs(args: argparse.Namespace) -> tuple[
    dict[str, Any],
    str,
    dict[str, Any],
    str,
    str,
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
    dict[str, str],
]:
    protocol, protocol_sha256 = base.load_protocol(
        args.protocol.resolve(), args.protocol_sha256
    )
    _, representation_sha256 = base.load_metric_omission_amendment(
        args.metric_omission_amendment.resolve(),
        args.metric_omission_amendment_sha256,
        protocol_sha256,
    )
    panel_path = args.panel.resolve()
    base.ensure_private_file(panel_path)
    panel_sha256 = base.sha256_file(panel_path)
    hardening, hardening_sha256 = live.load_hardening(
        args.hardening.resolve(),
        args.hardening_sha256,
        protocol_sha256,
        representation_sha256,
        panel_sha256,
    )
    panel = base.read_jsonl(panel_path)
    base.validate_private_panel(
        panel,
        protocol,
        protocol_sha256,
        "metric_omission_amendment_v2",
        representation_sha256,
        False,
    )
    panel_by_id = {row["pair_private_id"]: row for row in panel if row["smoke"] is True}
    require(len(panel_by_id) == 8, "smoke panel identity count")
    raw_path = args.raw.resolve()
    base.ensure_private_file(raw_path)
    raw = base.read_jsonl(raw_path)
    runner_sha256 = args.runner_sha256
    require(base.sha256_file(args.runner.resolve()) == runner_sha256, "runner SHA mismatch")
    analyzer_sha256 = base.sha256_file(Path(__file__).resolve())
    require(analyzer_sha256 == args.analyzer_sha256, "analyzer SHA mismatch")
    receipt_path = args.launch_receipt.resolve()
    receipt_sha256 = base.sha256_file(receipt_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    live.load_launch_receipt(
        receipt_path,
        protocol_sha256,
        representation_sha256,
        hardening_sha256,
        panel_sha256,
        runner_sha256,
        analyzer_sha256,
        "smoke",
        live.frozen_models(hardening),
        int(hardening["authorization"]["this_launch_maximum_calls"]),
        Decimal(str(hardening["authorization"]["this_launch_cumulative_usd_stop"])),
    )
    require(receipt.get("analyzer_sha256") == analyzer_sha256, "receipt analyzer binding")
    headers = live.nonsecret_headers(hardening)
    prepared_jobs: list[dict[str, Any]] = []
    for row, model, orientation in live.planned_jobs(
        panel, "smoke", live.frozen_models(hardening)
    ):
        payload = live.hardened_request_payload(row, orientation, model, protocol, hardening)
        prepared_jobs.append(
            {
                "key": (row["pair_private_id"], model, orientation),
                "payload": payload,
                "request_envelope_sha256": live.request_envelope_sha256(payload, headers),
                "maximum_charge": live.maximum_catalog_charge_bound(
                    payload, model, hardening
                ),
                "protocol": protocol,
            }
        )
    completed, _ = live.read_existing_state(
        raw_path,
        args.intent_log.resolve(),
        protocol_sha256,
        representation_sha256,
        hardening_sha256,
        panel_sha256,
        runner_sha256,
        receipt_sha256,
        args.expected_transport,
        prepared_jobs,
        hardening,
    )
    require(len(completed) == len(prepared_jobs), "intent/raw matrix incomplete")
    return (
        protocol,
        protocol_sha256,
        hardening,
        hardening_sha256,
        runner_sha256,
        panel,
        panel_by_id,
        raw,
        {
            "runner_sha256": runner_sha256,
            "analyzer_sha256": analyzer_sha256,
            "launch_receipt_sha256": receipt_sha256,
            "intent_log_sha256": base.sha256_file(args.intent_log.resolve()),
        },
    )


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    (
        protocol,
        protocol_sha256,
        hardening,
        hardening_sha256,
        runner_sha256,
        _panel,
        panel_by_id,
        raw,
        provenance,
    ) = load_inputs(args)
    representation_sha256 = args.metric_omission_amendment_sha256
    models = live.frozen_models(hardening)
    model_meta = {row["id"]: row for row in hardening["catalog_recheck"]["models"]}
    catalog = base.model_catalog(protocol)
    headers = live.nonsecret_headers(hardening)
    gates = hardening["smoke_gates"]
    expected_calls = int(gates["expected_calls"])
    require(len(raw) == expected_calls, "smoke raw call count")

    expected_keys = {
        (pair_id, model, orientation)
        for pair_id in panel_by_id
        for model in models
        for orientation in ("AB", "BA")
    }
    observed: dict[tuple[str, str, str], dict[str, Any]] = {}
    running_cost = Decimal(0)
    privacy_exact = True
    router_exact = True
    attempt_exact = True
    zero_errors = True
    for number, row in enumerate(raw, 1):
        require(row.get("schema") == live.RAW_SCHEMA, f"raw schema: {number}")
        require(row.get("protocol_sha256") == protocol_sha256, f"raw protocol: {number}")
        require(
            row.get("representation_contract_sha256") == representation_sha256,
            f"raw representation: {number}",
        )
        require(row.get("hardening_sha256") == hardening_sha256, f"raw hardening: {number}")
        require(
            row.get("private_panel_sha256") == hardening["parent"]["private_panel_sha256"],
            f"raw panel: {number}",
        )
        require(row.get("runner_sha256") == runner_sha256, f"raw runner: {number}")
        require(row.get("transport") == args.expected_transport, f"raw transport: {number}")
        key = (row.get("pair_private_id"), row.get("model"), row.get("orientation"))
        require(key in expected_keys, f"unexpected raw key: {number}")
        require(key not in observed, f"duplicate raw key: {number}")
        observed[key] = row
        panel_row = panel_by_id[str(row.get("pair_private_id"))]
        expected_payload = live.hardened_request_payload(
            panel_row,
            str(row.get("orientation")),
            str(row.get("model")),
            protocol,
            hardening,
        )
        require(
            row.get("request_envelope_sha256")
            == live.request_envelope_sha256(expected_payload, headers),
            f"request envelope drift: {number}",
        )
        request = row.get("request_contract")
        expected_provider = live.provider_contract(str(row.get("model")), hardening)
        privacy_exact = privacy_exact and isinstance(request, dict)
        if isinstance(request, dict):
            privacy_exact = privacy_exact and request.get("provider") == expected_provider
            privacy_exact = privacy_exact and request.get("router_metadata_header") == "enabled"
            privacy_exact = privacy_exact and request.get("max_tokens_omitted") is True
        response = row.get("response")
        require(isinstance(response, dict), f"raw response missing: {number}")
        independently_recomputed_audit = live.validate_router_response(
            response, str(row.get("model")), hardening
        )
        audit = row.get("router_audit")
        router_exact = router_exact and audit == independently_recomputed_audit
        attempt_exact = attempt_exact and independently_recomputed_audit["router_attempt"] == 1
        zero_errors = zero_errors and row.get("error") is None
        recomputed_pick, recomputed_parse_status = base.parse_final_pick(response)
        require(row.get("final_pick") == recomputed_pick, f"raw pick drift: {number}")
        require(
            row.get("parse_status") == recomputed_parse_status,
            f"raw parse status drift: {number}",
        )
        expected_correct = None
        if recomputed_pick is not None:
            expected_correct = recomputed_pick == (
                "A" if row.get("orientation") == "AB" else "B"
            )
        require(row.get("correct") == expected_correct, f"raw correctness drift: {number}")
        parse_status = recomputed_parse_status
        if parse_status == "parsed":
            require(row.get("final_pick") in {"A", "B"}, f"parsed pick: {number}")
            require(isinstance(row.get("correct"), bool), f"parsed correctness: {number}")
        else:
            require(row.get("final_pick") is None, f"unparsed pick leakage: {number}")
            require(row.get("correct") is None, f"unparsed correctness leakage: {number}")
        cost = base.response_cost_usd(response, str(row.get("model")), catalog)
        require(Decimal(str(row.get("cost_usd"))) == cost, f"raw cost drift: {number}")
        require(isinstance(request, dict), f"request contract missing: {number}")
        require(
            cost <= Decimal(str(request.get("maximum_catalog_charge_bound_usd"))),
            f"raw cost exceeded catalog bound: {number}",
        )
        running_cost += cost
        require(
            Decimal(str(row.get("cumulative_cost_usd"))) == running_cost,
            f"cumulative cost chain: {number}",
        )
    require(set(observed) == expected_keys, "smoke key set mismatch")

    per_model: list[dict[str, Any]] = []
    all_model_gates = True
    seed = int(hardening["analysis"]["bootstrap_seed"])
    repetitions = int(hardening["analysis"]["bootstrap_repetitions"])
    for model_index, model in enumerate(models):
        parsed_orientations = 0
        both_parsed_pairs = 0
        consistent_pairs = 0
        consistent_correct = 0
        consistent_wrong = 0
        inconsistent_pairs = 0
        missing_pairs = 0
        orientation_correct = 0
        orientation_parsed = 0
        task_values: list[tuple[str, float]] = []
        run_values: list[tuple[str, float]] = []
        selected_providers: set[str] = set()
        for pair_id, panel_row in panel_by_id.items():
            ab = observed[(pair_id, model, "AB")]
            ba = observed[(pair_id, model, "BA")]
            for item in (ab, ba):
                selected_providers.add(str(item["router_audit"]["selected_provider"]))
            parsed = [item.get("parse_status") == "parsed" for item in (ab, ba)]
            parsed_orientations += sum(parsed)
            for item, is_parsed in zip((ab, ba), parsed):
                if is_parsed:
                    orientation_parsed += 1
                    orientation_correct += int(item["correct"])
            if all(parsed):
                both_parsed_pairs += 1
                first_correct = bool(ab["correct"])
                second_correct = bool(ba["correct"])
                if first_correct == second_correct:
                    consistent_pairs += 1
                    consistent_correct += int(first_correct)
                    consistent_wrong += int(not first_correct)
                    task = panel_row["better"]["task"]["name"]
                    run = panel_row["better"]["run"]
                    value = float(first_correct)
                    task_values.append((task, value))
                    run_values.append((run, value))
                else:
                    inconsistent_pairs += 1
            else:
                missing_pairs += 1
        paid = bool(model_meta[model]["paid"])
        minimum_parsed = int(
            gates[
                "paid_model_minimum_parsed_orientations"
                if paid
                else "free_model_minimum_parsed_orientations"
            ]
        )
        minimum_both = int(
            gates[
                "paid_model_minimum_both_parsed_pairs"
                if paid
                else "free_model_minimum_both_parsed_pairs"
            ]
        )
        minimum_consistent = int(
            gates[
                "paid_model_minimum_order_consistent_pairs"
                if paid
                else "free_model_minimum_order_consistent_pairs"
            ]
        )
        model_gate = (
            parsed_orientations >= minimum_parsed
            and both_parsed_pairs >= minimum_both
            and consistent_pairs >= minimum_consistent
            and len(selected_providers) == 1
        )
        all_model_gates = all_model_gates and model_gate
        consistent_accuracy = (
            consistent_correct / consistent_pairs if consistent_pairs else None
        )
        orientation_accuracy = (
            orientation_correct / orientation_parsed if orientation_parsed else None
        )
        per_model.append(
            {
                "model": model,
                "paid": paid,
                "reliability": {
                    "parsed_orientations": parsed_orientations,
                    "both_parsed_pairs": both_parsed_pairs,
                    "order_consistent_pairs": consistent_pairs,
                    "order_inconsistent_pairs": inconsistent_pairs,
                    "pairs_with_missing_orientation": missing_pairs,
                    "minimum_parsed_orientations": minimum_parsed,
                    "minimum_both_parsed_pairs": minimum_both,
                    "minimum_order_consistent_pairs": minimum_consistent,
                    "selected_provider_count": len(selected_providers),
                    "single_selected_provider": len(selected_providers) == 1,
                    "gate_pass": model_gate,
                },
                "accuracy_descriptive_not_a_smoke_gate": {
                    "order_consistent_correct": consistent_correct,
                    "order_consistent_wrong": consistent_wrong,
                    "accuracy_among_order_consistent_pairs": consistent_accuracy,
                    "orientation_accuracy_among_parsed": orientation_accuracy,
                    "task_clustered_95_ci": clustered_bootstrap(
                        task_values, seed + model_index * 2, repetitions
                    ),
                    "run_clustered_95_ci": clustered_bootstrap(
                        run_values, seed + model_index * 2 + 1, repetitions
                    ),
                },
            }
        )

    cap = Decimal(str(hardening["authorization"]["this_launch_cumulative_usd_stop"]))
    global_gates = {
        "exact_call_matrix": len(raw) == expected_calls and set(observed) == expected_keys,
        "zero_transport_errors": zero_errors,
        "request_privacy_fields_exact": privacy_exact,
        "router_and_no_compression_evidence_exact": router_exact,
        "all_router_attempts_exactly_one": attempt_exact,
        "cumulative_cost_within_stop": running_cost <= cap,
        "single_selected_provider_per_model": all(
            row["reliability"]["single_selected_provider"] for row in per_model
        ),
        "all_model_reliability_gates": all_model_gates,
    }
    passed = all(global_gates.values())
    return {
        "schema": ANALYSIS_SCHEMA,
        "classification": (
            "HISTORICAL_FULL_CONTEXT_SMOKE_RELIABILITY_GATES_PASS"
            if passed
            else "HISTORICAL_FULL_CONTEXT_SMOKE_RELIABILITY_GATES_FAIL"
        ),
        "protocol_sha256": protocol_sha256,
        "representation_sha256": representation_sha256,
        "hardening_sha256": hardening_sha256,
        "execution_provenance": provenance,
        "private_panel_sha256": hardening["parent"]["private_panel_sha256"],
        "raw_sha256": base.sha256_file(args.raw.resolve()),
        "raw_rows": len(raw),
        "models": len(models),
        "pairs": len(panel_by_id),
        "global_reliability_and_safety_gates": global_gates,
        "per_model_reliability_then_accuracy": per_model,
        "cost": {
            "cumulative_usd": format(running_cost, "f"),
            "stop_usd": format(cap, "f"),
        },
        "accuracy_used_as_gate": False,
        "raw_reasoning_emitted": False,
        "pair_identities_emitted": False,
        "task_or_run_identities_emitted": False,
        "future_full_launch_authorized_by_this_analysis": False,
        "scientific_boundary": hardening["scientific_boundary"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--metric-omission-amendment", type=Path, required=True)
    parser.add_argument("--metric-omission-amendment-sha256", required=True)
    parser.add_argument("--hardening", type=Path, required=True)
    parser.add_argument("--hardening-sha256", required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--runner-sha256", required=True)
    parser.add_argument("--analyzer-sha256", required=True)
    parser.add_argument("--launch-receipt", type=Path, required=True)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--intent-log", type=Path, required=True)
    parser.add_argument("--expected-transport", choices=("mock", "live"), required=True)
    return parser.parse_args()


def main() -> None:
    print(base.canonical_json(analyze(parse_args())))


if __name__ == "__main__":
    main()
