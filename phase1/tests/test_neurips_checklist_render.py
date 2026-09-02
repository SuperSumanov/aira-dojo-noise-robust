from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "phase1/decision_corpus_neurips_checklist_render_v1.json"
PAPER = ROOT / "phase1/PAPER_DRAFT_DECISION_CORPUS_CHECKLIST_20260903.md"
APPENDIX = ROOT / "phase1/PAPER_REPRODUCIBILITY_APPENDIX_DRAFT_20260903.md"
BIBLIOGRAPHY = ROOT / "phase1/DECISION_CORPUS_REFERENCES_20260902.bib"
HEADER = ROOT / "phase1/render/decision_corpus_neurips_2026_header.tex"
TEMPLATE = ROOT / "phase1/render/neurips_2026_checklist_template.tex"
CHECKLIST = ROOT / "phase1/render/decision_corpus_neurips_2026_checklist_provisional.tex"
REPORT = ROOT / "phase1/NEURIPS_CHECKLIST_RENDER_20260903.md"
RECEIPT = ROOT / "phase1/neurips_checklist_postpush_receipt_20260903.json"
CURRENT = ROOT / "phase1/CURRENT_DIRECTION.md"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_contract_binds_every_tracked_render_input() -> None:
    data = load()
    source = data["source"]
    checklist = data["checklist"]
    renderer = data["renderer"]
    assert sha256(PAPER) == source["paper_sha256"]
    assert sha256(APPENDIX) == source["appendix_sha256"]
    assert sha256(BIBLIOGRAPHY) == source["bibliography_sha256"]
    assert checklist["official_source_sha256"] == (
        "780ba13c480f652dcc42e69ed61a752ce0ea270f15d332d4a45b059dabad84f6"
    )
    assert sha256(TEMPLATE) == checklist["official_template_sha256"]
    assert checklist["official_template_normalization"] == (
        "UTF-8/LF with trailing horizontal whitespace removed"
    )
    assert sha256(CHECKLIST) == checklist["generated_sha256"]
    assert sha256(HEADER) == renderer["header_sha256"]


def test_successor_is_inside_content_gate_and_checklist_is_separate() -> None:
    data = load()
    render = data["render"]
    assert len(PAPER.read_text(encoding="utf-8").split()) == 3081
    assert render["total_pdf_pages"] == 16
    assert render["last_page_containing_main_content"] == 7
    assert render["references_begin_on_page"] == 8
    assert render["checklist_begins_on_page"] == 9
    assert render["checklist_pages"] == 8
    assert render["maximum_content_pages"] == 9
    assert render["within_content_page_gate"] is True
    assert render["submission_candidate"] is False
    assert render["internal_review_candidate"] is True


def test_all_pages_were_visually_inspected_and_two_builds_match() -> None:
    render = load()["render"]
    assert render["visual_qa_pages_rendered"] == 16
    assert render["visual_qa_pages_inspected"] == 16
    assert render["overlap_or_clipping_observed"] is False
    assert render["black_boxes_or_missing_figures_observed"] is False
    assert render["overfull_box_warnings"] == 0
    assert render["independent_build_directories"] == 2
    assert render["independent_pdf_sha256"] == render["pdf_sha256"]
    assert render["independent_pdf_bytes"] == render["pdf_bytes"]
    assert render["independent_build_byte_identical"] is True


def test_visual_defect_repair_is_narrow_and_regression_guarded() -> None:
    repair = load()["visual_defect_repair"]
    paper_bytes = PAPER.read_bytes()
    paper = paper_bytes.decode("utf-8")
    assert repair["immutable_base_lone_cr_right_arrow_tokens"] == 4
    assert repair["successor_lone_cr_bytes"] == 0
    assert paper_bytes.count(b"\r") == 0
    assert paper.count(r"$\rightarrow$") == 4
    assert "$\nightarrow$" not in paper
    assert repair["rendered_unicode_right_arrows_present"] is True
    assert repair["rendered_ightarrow_literal_present"] is False
    assert repair["scientific_values_changed"] is False
    assert repair["base_source_modified"] is False


def test_checklist_answer_counts_and_open_gates_are_not_hidden() -> None:
    data = load()
    checklist = data["checklist"]
    gates = data["remaining_submission_gates"]
    assert (checklist["items"], checklist["yes"], checklist["no"]) == (16, 7, 5)
    assert checklist["not_applicable_or_not_available"] == 4
    assert checklist["hard_submission_blockers"] == [4, 5, 8, 12, 13]
    assert checklist["author_attestation_required"] == [9]
    assert checklist["starts_on_fresh_page"] is True
    assert len(gates) == 8
    assert gates["anonymous_open_data_and_code"] == "BLOCKED_DESK_REJECT_RISK"
    assert gates["author_ethics_attestation"] == "AUTHOR_ACTION_REQUIRED"


def test_report_and_security_preserve_nonclaim_boundary() -> None:
    data = load()
    text = REPORT.read_text(encoding="utf-8")
    assert "7 Yes / 5 No / 4 N/A" in text
    assert "byte-identical 500,133-byte PDFs" in text
    assert "main content ends on page 7" in text
    assert "All 16 final pages" in text
    assert "not a submission candidate" in text
    assert "0 / 0 / 0 / 0" in text
    assert data["interpretation"]["counts_as_distinct_claim_evidence"] is False
    assert data["interpretation"]["scientific_result_changed"] is False
    assert data["interpretation"]["submission_readiness_closed"] is False
    assert all(value is False or value == 0 for value in data["security"].values())


def test_postpush_receipt_binds_failure_chain_full_suite_and_cleanup() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    verification = receipt["successful_verification"]
    attempts = receipt["attempt_chain"]
    cleanup = receipt["cleanup"]
    assert receipt["exact_public_commit"] == (
        "9a6477a3a726609e63747d31798642a679fb6899"
    )
    assert receipt["frozen_assets"]["render_contract_sha256"] == sha256(CONTRACT)
    assert attempts[0]["status"] == "FAILED_BEFORE_PREFLIGHT"
    assert attempts[0]["worktree_created"] is False
    assert attempts[0]["test_results_produced"] is False
    assert attempts[1]["status"] == "PASS"
    assert verification["preflight_items_passed"] == 11
    assert verification["changed_files"] == 11
    assert verification["builder_outputs_byte_identical"] is True
    assert verification["focused_tests"]["passed"] == 20
    assert verification["full_phase1_tests"]["passed"] == 2222
    assert verification["full_phase1_tests"]["skipped"] == 1
    assert verification["full_phase1_tests"]["failed"] == 0
    assert verification["full_phase1_tests"]["warnings"] == 48
    assert verification["focused_stderr_bytes"] == 0
    assert verification["full_stderr_bytes"] == 0
    assert verification["log_manifest_sha256"] == (
        "ab7a113df0d4949f940b5b50629c970aee036e46ab5665b59cd6ba0f52d55f82"
    )
    assert cleanup["local_log_files_hash_verified"] == 19
    assert cleanup["local_log_files_missing_or_mismatched"] == 0
    assert cleanup["remote_exact_worktree_removed"] is True
    assert cleanup["remote_exact_log_root_removed_after_verified_local_copy"] is True
    assert cleanup["remote_helpers_removed"] is True
    assert all(value is False or value == 0 for value in receipt["security"].values())


def test_current_direction_records_checklist_gate_without_claiming_submission_ready() -> None:
    text = CURRENT.read_text(encoding="utf-8")
    assert text.startswith("# 当前研究方向唯一入口（2026-09-03）")
    assert "## 0L0s." in text
    assert "7 Yes / 5 No / 4 N/A" in text
    assert "focused/full=`20 / 2,222 passed`" in text
    assert "仍不是 submission candidate" in text
    assert "counts_as_distinct_claim_evidence=false" in text
