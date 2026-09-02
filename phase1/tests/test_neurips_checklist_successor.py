from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "phase1/neurips_paper_checklist_provisional_v1.json"
BASE_PAPER = ROOT / "phase1/PAPER_DRAFT_DECISION_CORPUS_9PAGE_20260902.md"
BASE_APPENDIX = ROOT / "phase1/PAPER_REPRODUCIBILITY_APPENDIX_DRAFT_20260902.md"
PAPER = ROOT / "phase1/PAPER_DRAFT_DECISION_CORPUS_CHECKLIST_20260903.md"
APPENDIX = ROOT / "phase1/PAPER_REPRODUCIBILITY_APPENDIX_DRAFT_20260903.md"
TEMPLATE = ROOT / "phase1/render/neurips_2026_checklist_template.tex"
CHECKLIST = ROOT / "phase1/render/decision_corpus_neurips_2026_checklist_provisional.tex"
REPORT = ROOT / "phase1/NEURIPS_PAPER_CHECKLIST_PROVISIONAL_20260903.md"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def test_bindings_preserve_the_immutable_base_documents_and_official_template() -> None:
    bindings = load()["bindings"]
    assert sha256(BASE_PAPER) == bindings["base_paper_sha256"]
    assert sha256(BASE_APPENDIX) == bindings["base_appendix_sha256"]
    assert bindings["official_checklist_source_sha256"] == (
        "780ba13c480f652dcc42e69ed61a752ce0ea270f15d332d4a45b059dabad84f6"
    )
    assert sha256(TEMPLATE) == bindings["official_checklist_template_sha256"]
    assert bindings["official_checklist_template_normalization"] == (
        "UTF-8/LF with trailing horizontal whitespace removed"
    )
    generated = bindings["generated_outputs"]
    assert generated["paper"]["path"] == "phase1/PAPER_DRAFT_DECISION_CORPUS_CHECKLIST_20260903.md"
    assert generated["paper"]["sha256"] == sha256(PAPER)
    assert generated["appendix"]["path"] == "phase1/PAPER_REPRODUCIBILITY_APPENDIX_DRAFT_20260903.md"
    assert generated["appendix"]["sha256"] == sha256(APPENDIX)
    assert generated["checklist_tex"]["path"] == (
        "phase1/render/decision_corpus_neurips_2026_checklist_provisional.tex"
    )
    assert generated["checklist_tex"]["sha256"] == sha256(CHECKLIST)


def test_all_sixteen_official_items_have_honest_provisional_answers() -> None:
    data = load()
    items = data["items"]
    assert [item["number"] for item in items] == list(range(1, 17))
    assert len({item["title"] for item in items}) == 16
    counts = {answer: sum(item["answer"] == answer for item in items) for answer in ("Yes", "No", "N/A")}
    assert counts == {"Yes": 7, "No": 5, "N/A": 4}
    assert data["summary"]["yes"] == 7
    assert data["summary"]["no"] == 5
    assert data["summary"]["not_applicable_or_not_available"] == 4
    assert data["summary"]["hard_submission_blockers"] == [4, 5, 8, 12, 13]
    assert data["summary"]["author_attestation_required"] == [9]


def test_generated_tex_keeps_questions_and_guidelines_but_removes_template_todos() -> None:
    data = load()
    text = CHECKLIST.read_text(encoding="utf-8")
    assert text.startswith("\\clearpage\n\\section*{NeurIPS Paper Checklist}")
    assert "NeurIPS Paper Checklist" in text
    assert "%%% BEGIN INSTRUCTIONS %%%" not in text
    assert "%%% END INSTRUCTIONS %%%" not in text
    assert r"\answerTODO" not in text
    assert r"\justificationTODO" not in text
    answer_lines = re.findall(r"(?m)^\s*\\item\[\] Answer: (\\answer(?:Yes|No|NA)\{\})\s*$", text)
    assert len(answer_lines) == 16
    for item in data["items"]:
        assert rf"\item {{\bf {item['title']}}}" in text
        assert rf"\item[] Question: {item['question_tex']}" in text
        assert item["latex_answer"] in answer_lines
        assert "Guidelines:" in text


def test_successor_adds_impact_llm_and_settings_without_internal_paths_or_unsealed_values() -> None:
    paper = PAPER.read_text(encoding="utf-8")
    appendix = APPENDIX.read_text(encoding="utf-8")
    assert "## Broader impacts, safeguards, and LLM use" in paper
    assert "No agent base model is fine-tuned" in paper
    assert "no crowdsourcing or human-subject experiment" in paper
    assert paper.count(r"$\rightarrow$") == 4
    assert "\r" not in PAPER.read_bytes().decode("utf-8")
    assert "$\nightarrow$" not in paper
    assert "phase1/" not in paper
    assert len(paper.split()) <= 3980
    assert "## A.12 Reported experiment settings and compute-ledger status" in appendix
    assert "4,689 train, 551 development, and 931 test pairs" in appendix
    assert "20,000 percentile bootstrap replicates" in appendix
    assert "18 fits total" in appendix
    assert "compute-resources answer remains No" in appendix
    assert "## A.13 Evidence routing for this appendix" in appendix


def test_blockers_and_security_boundary_are_machine_readable() -> None:
    data = load()
    statuses = {item["number"]: item["status"] for item in data["items"]}
    assert statuses[4] == "BLOCKED"
    assert statuses[5] == "BLOCKED_DESK_REJECT_RISK"
    assert statuses[9] == "AUTHOR_ATTESTATION_REQUIRED"
    assert statuses[13] == "BLOCKED_DESK_REJECT_RISK"
    security = data["security"]
    assert all(value is False or value == 0 for value in security.values())
    interpretation = data["interpretation"]
    assert interpretation["counts_as_distinct_scientific_evidence"] is False
    assert interpretation["checklist_presence_gate_closed"] is True
    assert interpretation["submission_readiness_closed"] is False
    assert interpretation["all_yes_claim_forbidden"] is True


def test_report_states_provisional_status_and_does_not_hide_no_answers() -> None:
    text = REPORT.read_text(encoding="utf-8")
    assert "7 Yes / 5 No / 4 N/A" in text
    assert "submission readiness is not" in text
    assert "should not be cosmetically converted to Yes" in text
    assert "Code of Ethics answer remains N/A" in text
    assert "GPU, paid API, model fit, base-model update: **0 / 0 / 0 / 0**" in text
