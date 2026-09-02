from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "phase1/neurips_ed_9page_content_budget_v1.json"
NOTE = ROOT / "phase1/NEURIPS_ED_9PAGE_CONTENT_BUDGET_20260902.md"


def load_contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_baseline_is_exact_and_not_misrepresented_as_submission_candidate() -> None:
    data = load_contract()
    baseline = data["baseline"]
    assert data["status"] == (
        "PROVISIONAL_2026_TEMPLATE_BASELINE_NOT_SUBMISSION_CANDIDATE"
    )
    assert baseline["public_commit"] == "2844624e8e5a7be0033bc22d2fc7947a81e6de1b"
    assert baseline["input_words"] == 6476
    assert baseline["total_pdf_pages"] == 17
    assert baseline["last_page_containing_main_content"] == 16
    assert baseline["references_begin_on_page"] == 16
    assert baseline["within_nine_content_pages"] is False
    assert baseline["submission_candidate"] is False


def test_template_and_renderer_are_digest_bound_and_provisional() -> None:
    data = load_contract()
    target = data["target_call"]
    renderer = data["renderer"]
    assert target["call_published"] is False
    assert target["provisional_template_year"] == 2026
    assert target["must_revalidate_for_2027"] is True
    assert len(target["official_template_zip_sha256"]) == 64
    assert len(target["official_style_sha256"]) == 64
    assert renderer["version"] == "0.16.9"
    assert renderer["submission_style_option"] == "eandd"
    assert len(renderer["windows_asset_sha256"]) == 64


def test_page_and_word_budgets_sum_exactly() -> None:
    budget = load_contract()["main_text_budget"]
    assert sum(item["target_pages"] for item in budget["sections"]) == 9.0
    assert sum(item["target_words"] for item in budget["sections"]) == 3980
    assert budget["maximum_content_pages"] == 9.0
    assert budget["target_prose_words"] == 3980


def test_main_appendix_and_removal_routes_are_explicit() -> None:
    data = load_contract()
    assert len(data["main_text_keep"]) == 11
    assert len(data["move_to_appendix"]) == 7
    assert len(data["remove_from_submission"]) == 5
    assert any("Figure 1" in item for item in data["main_text_keep"])
    assert any("Figure 2" in item for item in data["main_text_keep"])
    assert any("full audit-readout" in item for item in data["move_to_appendix"])
    assert any("empty sealed Table 4B" in item for item in data["remove_from_submission"])


def test_human_note_records_visual_qa_and_nonnegotiable_gate() -> None:
    text = NOTE.read_text(encoding="utf-8")
    assert "all 17 rendered pages" in text
    assert "overlapping" in text
    assert "3,980" in text
    assert "no unresolved result placeholder" in text
    assert "word count alone is insufficient" in text
    assert "must be revalidated" in text
    assert "against the 2027 call" in text


def test_measurement_did_not_open_sealed_results_or_authorize_compute() -> None:
    security = load_contract()["security"]
    assert security["prospective_values_or_identities_read"] is False
    assert security["counts_as_distinct_claim_evidence"] is False
    assert security["gpu_jobs"] == 0
    assert security["paid_api_calls"] == 0
    assert security["model_fits"] == 0
    assert security["base_llm_updates"] == 0
