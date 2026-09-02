import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXTRACT = ROOT / "phase1/results/historical_table4a_extract_20260902/table4a.json"
PAPER = ROOT / "phase1/PAPER_DRAFT_DECISION_CORPUS_20260902.md"
FORMAL_RECEIPT = ROOT / "phase1/historical_ust_predictor_sensitivity_formal_receipt_20260830.json"
HUMAN_REPORT = ROOT / "phase1/实验记录/2026-08-30/HistoricalUSTSensitivity_v2正式结果.md"
COST_A = ROOT / "phase1/results/deployment_cost_attestation_v2_20260820_c800345/run_A/summary.json"
COST_B = ROOT / "phase1/results/deployment_cost_attestation_v2_20260820_c800345/run_B/summary.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_extract_binds_formal_and_cost_sources():
    extract = load(EXTRACT)
    receipt = load(FORMAL_RECEIPT)
    assert extract["counts_as_distinct_claim_evidence"] is False
    assert sha256(FORMAL_RECEIPT) == extract["source"]["formal_receipt_sha256"]
    assert sha256(HUMAN_REPORT) == extract["source"]["human_report_sha256"]
    assert receipt["formal"]["result_sha256"] == extract["source"]["formal_result_sha256"]
    assert receipt["formal"]["independent_verification_sha256"] == extract["source"]["formal_verification_sha256"]
    assert sha256(COST_A) == extract["cost_panel"]["run_a_summary_sha256"]
    assert sha256(COST_B) == extract["cost_panel"]["run_b_summary_sha256"]
    assert extract["population"]["pairs"] == receipt["pair_graph"]["pair_rows"]
    assert extract["population"]["tasks"] == receipt["pair_graph"]["tasks"]
    assert extract["population"]["decision_parents"] == receipt["pair_graph"]["decision_parents"]
    assert extract["population"]["incidence_rank"] == receipt["pair_graph"]["incidence_rank"]
    assert extract["population"]["cycle_rows"] == receipt["pair_graph"]["cycle_rows"]


def test_cost_extract_is_exact_for_both_runs():
    extract = load(EXTRACT)
    runs = [load(COST_A), load(COST_B)]
    for row in extract["cost_panel"]["rows"]:
        model = row["model"]
        for observed, expected in zip(
            row["initialization_p50_s"],
            (run["models"][model]["initialization_s"]["p50"] for run in runs),
        ):
            assert math.isclose(float(observed), expected, rel_tol=0.0, abs_tol=1e-12)
        for observed, expected in zip(
            row["query_p50_ms"],
            (run["models"][model]["single_pair_query_ms"]["p50"] for run in runs),
        ):
            assert math.isclose(float(observed), expected, rel_tol=0.0, abs_tol=1e-12)
        for observed, expected in zip(
            row["execution_p50_over_query_p50"],
            (run["models"][model]["execution_parallel_p50_over_query_p50"] for run in runs),
        ):
            assert math.isclose(float(observed), expected, rel_tol=0.0, abs_tol=1e-12)


def test_paper_accuracy_rows_match_extract_rounding():
    extract = load(EXTRACT)
    paper = PAPER.read_text(encoding="utf-8")
    for row in extract["accuracy_panel"]:
        line = (
            f'| {row["paper_name"]} | {float(row["raw_pair_micro"]):.4f} | '
            f'{float(row["raw_task_parent_macro"]):.4f} | '
            f'{float(row["ust_task_parent_macro"]):.4f} '
            f'[{float(row["ust_task_parent_ci95"][0]):.4f}, '
            f'{float(row["ust_task_parent_ci95"][1]):.4f}] | '
            f'{row["pairs"]} / {row["ties"]} |'
        )
        assert line in paper


def test_paper_cost_rows_match_extract_rounding():
    extract = load(EXTRACT)
    paper = PAPER.read_text(encoding="utf-8")
    for row in extract["cost_panel"]["rows"]:
        init = sorted(float(value) for value in row["initialization_p50_s"])
        query = sorted(float(value) for value in row["query_p50_ms"])
        ratio = sorted(float(value) for value in row["execution_p50_over_query_p50"])
        line = (
            f'| {row["paper_name"]} | {init[0]:.2f}--{init[1]:.2f} | '
            f'{query[0]:.2f}--{query[1]:.2f} | '
            f'{ratio[0]:,.0f}--{ratio[1]:,.0f}× |'
        )
        assert line in paper


def test_scope_fail_closed():
    scope = load(EXTRACT)["scope"]
    assert scope == {
        "historical_development_only": True,
        "direct_same_physical_run_confirmation": False,
        "full_predictor_family": False,
        "prospective_confirmation": False,
        "task_unseen_generalization": False,
        "search_utility": False,
        "prospective_value_or_identity_read": False,
        "gpu_api_model_fit_base_update": [0, 0, 0, 0],
    }
