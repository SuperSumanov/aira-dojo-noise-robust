from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "phase1/NEURIPS_ED_2027_SUBMISSION_READINESS_GATE_20260902.md"
SPRINT = ROOT / "phase1/TWENTY_DAY_POSITIVE_RESULT_SPRINT_20260902.md"
HANDOFF = ROOT / "phase1/SENIOR_HANDOFF_20_DAY_SPRINT_20260902.md"


OFFICIAL_URLS = (
    "https://neurips.cc/Conferences/2026/CallForEvaluationsDatasets",
    "https://neurips.cc/Conferences/2026/EvaluationsDatasetsHosting",
    "https://neurips.cc/Conferences/2026/EvaluationsDatasetsFAQ",
    "https://neurips.cc/Conferences/2026/MainTrackHandbook",
    "https://neurips.cc/public/guides/PaperChecklist",
)


def test_gate_is_explicitly_provisional_and_official_source_bound() -> None:
    text = GATE.read_text(encoding="utf-8")
    assert "The 2027 call has not been published" in text
    assert "latest official NeurIPS\n> 2026" in text
    assert "must be\n> revalidated against the 2027 call" in text
    assert "not a claim that 2027 requirements are already known" in text
    for url in OFFICIAL_URLS:
        assert text.count(url) == 1


def test_gate_records_fit_without_claiming_submission_readiness() -> None:
    text = GATE.read_text(encoding="utf-8")
    assert "| Track fit |" in text
    assert "| **PASS** |" in text
    assert "| Dataset access |" in text
    assert "**BLOCKED / DESK-REJECT RISK**" in text
    assert "| Main-paper format |" in text
    assert "| Review anonymity |" in text
    assert "| Croissant core |" in text
    assert text.count("**BLOCKED**") >= 5
    assert "SUBMISSION_READY" not in text


def test_release_language_cannot_evade_accessibility_gate() -> None:
    text = GATE.read_text(encoding="utf-8")
    assert "cannot be used to evade accessibility" in text
    assert "legally cleared derived artifact" in text
    assert "A private holdout is not a substitute" in text
    assert "must still be sufficient to reproduce every headline result" in text


def test_twenty_day_path_has_artifact_and_paper_deadlines() -> None:
    text = GATE.read_text(encoding="utf-8")
    for stage in (
        "D0--D3: freeze the submission artifact boundary",
        "D2--D7: make a real anonymous reviewer artifact",
        "D3--D9: produce the nine-page paper",
        "D7--D14: close or remove prospective result slots",
        "D10--D17: reproducibility and responsible-release dry run",
        "D17--D20: adversarial internal review",
    ):
        assert stage in text
    assert "rendered, nine-page, internally reviewable E&D\npaper" in text
    assert "Additional CPU audits do\nnot substitute" in text


def test_readiness_gate_is_routed_to_sprint_and_senior_handoff() -> None:
    for path in (SPRINT, HANDOFF):
        text = path.read_text(encoding="utf-8")
        assert "NEURIPS_ED_2027_SUBMISSION_READINESS_GATE_20260902.md" in text
        assert "2027" in text
        assert "Croissant" in text
        assert "9" in text or "nine" in text
    sprint = SPRINT.read_text(encoding="utf-8")
    assert "artifact/release" in sprint
    handoff = HANDOFF.read_text(encoding="utf-8")
    assert "DESK-REJECT" in handoff
    assert "Kaggle" in handoff
