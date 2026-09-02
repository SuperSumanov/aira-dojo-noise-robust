from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "phase1/PAPER_DRAFT_DECISION_CORPUS_9PAGE_20260902.md"
BIBLIOGRAPHY = ROOT / "phase1/DECISION_CORPUS_REFERENCES_20260902.bib"
HEADER = ROOT / "phase1/render/decision_corpus_neurips_2026_header.tex"
CONTRACT = ROOT / "phase1/decision_corpus_9page_draft_render_v1.json"
RECEIPT = ROOT / "phase1/decision_corpus_9page_draft_postpush_receipt_20260902.json"
NOTE = ROOT / "phase1/NEURIPS_ED_9PAGE_DRAFT_RENDER_20260902.md"
CURRENT = ROOT / "phase1/CURRENT_DIRECTION.md"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_source_is_compact_anonymous_and_has_a_real_reference_heading() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    assert len(text.split()) == 2903
    assert 'author:\n  - "Anonymous Author(s)"' in text
    assert 'reference-section-title: "References"' in text
    assert text.count("# Introduction") == 1
    assert text.count("# Conclusion") == 1
    assert "# Limitations, governance, and release" in text
    assert len(text.split()) <= 3980


def test_source_embeds_both_frozen_figures_once_and_no_internal_paths() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    assert text.count("figure1_corpus_and_sealed_protocol.png") == 1
    assert text.count("figure2_run_to_pair_weighting.png") == 1
    assert "phase1/" not in text
    assert "CURRENT_DIRECTION" not in text
    assert "[SEALED TABLE" not in text
    assert "[CONDITIONAL TABLE" not in text
    assert "DRAFT GOVERNANCE NOTE" not in text


def test_contract_binds_source_bibliography_figures_and_renderer() -> None:
    data = load_contract()
    source = data["source"]
    renderer = data["renderer"]
    assert sha256(SOURCE) == source["sha256"]
    assert sha256(BIBLIOGRAPHY) == source["bibliography_sha256"]
    assert sha256(HEADER) == renderer["header_sha256"]
    for item in source["embedded_figures"]:
        assert sha256(ROOT / item["path"]) == item["sha256"]
    assert renderer["pandoc_source_format"] == (
        "markdown+tex_math_single_backslash"
    )
    assert renderer["submission_style_option"] == "eandd"
    assert renderer["tectonic_version"] == "0.16.9"


def test_measured_render_is_inside_page_gate_but_not_submission_ready() -> None:
    data = load_contract()
    render = data["render"]
    gates = data["remaining_submission_gates"]
    assert render["total_pdf_pages"] == 8
    assert render["last_page_containing_main_content"] == 7
    assert render["references_begin_on_page"] == 7
    assert render["maximum_content_pages"] == 9
    assert render["within_content_page_gate"] is True
    assert render["reference_heading_present"] is True
    assert render["visual_qa_pages_rendered"] == 8
    assert render["visual_qa_pages_inspected"] == 8
    assert render["deterministic_render_pngs_matching_inspected_pass"] == 8
    assert render["deterministic_render_png_mismatches"] == 0
    assert render["overlap_or_clipping_observed"] is False
    assert render["independent_build_directories"] == 2
    assert render["independent_pdf_sha256"] == render["pdf_sha256"]
    assert render["independent_pdf_bytes"] == render["pdf_bytes"]
    assert render["independent_build_byte_identical"] is True
    assert render["submission_candidate"] is False
    assert render["internal_review_candidate"] is True
    assert set(gates.values()) == {
        "BLOCKED_NOT_PUBLISHED",
        "BLOCKED_NOT_INCLUDED",
        "BLOCKED",
        "PARTIAL_PENDING_PREREGISTERED_CLOSURE",
    }


def test_measured_reduction_is_arithmetic_not_an_unverified_claim() -> None:
    change = load_contract()["measured_change_from_v0_7_baseline"]
    assert change["baseline_words"] - change["draft_words"] == 3573
    assert change["baseline_total_pdf_pages"] - change["draft_total_pdf_pages"] == 9
    assert change["baseline_last_content_page"] - change["draft_last_content_page"] == 9
    assert change["word_reduction_fraction"] == 0.551729


def test_note_and_direction_preserve_nonclaim_and_remaining_gates() -> None:
    note = NOTE.read_text(encoding="utf-8")
    current = CURRENT.read_text(encoding="utf-8")
    assert "All eight final pages" in note
    assert "Two independent build directories" in note
    assert "byte-identical 467,024-byte PDFs" in note
    assert "This is not yet a submission candidate" in note
    assert "not permission to pad the paper" in note
    assert "## 0L0p." in current
    assert "8 个 PDF pages" in current
    assert "正文最后页从 16 降到 7" in current
    assert "不是 submission candidate" in current


def test_render_work_did_not_open_sealed_results_or_authorize_compute() -> None:
    data = load_contract()
    interpretation = data["interpretation"]
    security = data["security"]
    assert interpretation["counts_as_distinct_claim_evidence"] is False
    assert interpretation["scientific_result_changed"] is False
    assert interpretation["page_budget_gate_closed"] is True
    assert interpretation["submission_readiness_closed"] is False
    assert sum(int(value) for value in security.values()) == 0


def test_postpush_receipt_binds_exact_commit_full_suite_and_cleanup() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    verification = receipt["successful_verification"]
    render = receipt["deterministic_render"]
    assert receipt["exact_public_commit"] == (
        "b711a600fb45c18a65140f192f8c0e94b97a538a"
    )
    assert verification["preflight_items_passed"] == 11
    assert verification["focused_tests"]["passed"] == 20
    assert verification["full_phase1_tests"]["passed"] == 2193
    assert verification["full_phase1_tests"]["failed"] == 0
    assert verification["focused_stderr_bytes"] == 0
    assert verification["full_stderr_bytes"] == 0
    assert render["byte_identical"] is True
    assert render["pdf_sha256"] == load_contract()["render"]["pdf_sha256"]
    assert receipt["cleanup"]["local_log_files_hash_verified"] == 13
    assert receipt["cleanup"]["local_log_files_missing_or_mismatched"] == 0
    assert receipt["cleanup"]["remote_exact_log_root_removed_after_verified_local_copy"] is True
    assert sum(int(value) for value in receipt["security"].values()) == 0
