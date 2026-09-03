import json
from pathlib import Path

from phase1.verify_historical_global_local_token_plan_readiness import verify


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "phase1" / "results" / "global_local_token_plan_20260904"
PROTOCOL_SHA = "1964e8e48e998660584c045a7e8fe2a03d61a946ba266d29d74555f934482902"
SUMMARY_SHA = "c40f9b696530c2303c5129fa5571a2ffc484986472d1962871170d30a509043b"


def test_aggregate_receipt_replays_without_source_data():
    receipt = verify(RESULT / "summary.json", PROTOCOL_SHA)
    assert receipt == json.loads((RESULT / "independent_receipt.json").read_text())
    assert receipt["summary_sha256"] == SUMMARY_SHA


def test_exact_real_order_budget_shortfalls_are_pinned():
    value = json.loads((RESULT / "summary.json").read_text())
    plans = {
        (row["seed"], row["arm"]): row
        for row in value["plans"] if row["world_size"] == 2
    }
    assert {
        seed: plans[seed, "Lbudget"]["token_budget_shortfall"]
        for seed in (6, 7, 8)
    } == {6: 2720, 7: 1937, 8: 2066}
    assert {
        seed: plans[seed, "Gbudget"]["token_budget_shortfall"]
        for seed in (6, 7, 8)
    } == {6: 5367, 7: 711, 8: 593}
    assert {
        seed: plans[seed, "Lbudget"]["planned_pair_visits"]
        for seed in (6, 7, 8)
    } == {6: 15276, 7: 15275, 8: 15273}
    assert {
        seed: plans[seed, "Gbudget"]["planned_pair_visits"]
        for seed in (6, 7, 8)
    } == {6: 13519, 7: 13557, 8: 13517}


def test_transport_failure_is_not_misreported_as_workload_failure_or_success():
    context = json.loads((RESULT / "execution_context.json").read_text())
    attempt = next(row for row in context["attempts"] if row["id"] == "r1-real-input-plan")
    assert attempt["workload_remote_rc_captured_before_end_timestamp"] == 0
    assert attempt["outer_ssh_process_rc"] == 1
    assert "CRLF" in attempt["outer_failure_after_workload"]
    assert context["scope"]["model_fits"] == context["scope"]["new_gpu_jobs"] == 0


def test_receipt_has_aggregate_schema_not_private_pair_payloads():
    value = json.loads((RESULT / "summary.json").read_text())
    text = (RESULT / "summary.json").read_text()
    assert value["output_contains_card_ids_code_tasks_labels_predictions_or_effects"] is False
    keys = set()
    def collect(item):
        if isinstance(item, dict):
            keys.update(item)
            for child in item.values():
                collect(child)
        elif isinstance(item, list):
            for child in item:
                collect(child)
    collect(value)
    assert not ({"pair_keys", "card_id", "code", "task", "label", "prediction", "accuracy", "utility"} & keys)
    assert "synthetic:" not in text
