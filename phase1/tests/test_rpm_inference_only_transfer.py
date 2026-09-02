from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import rpm_inference_only_transfer as rpm


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "rpm_inference_only_transfer_contract_v1.json"
POSTPUSH_RECEIPT = ROOT / "rpm_inference_only_transfer_postpush_receipt_20260902.json"


def test_prompt_is_exact_v2_source_extraction() -> None:
    raw = rpm.PROMPT_PATH.read_bytes()
    assert len(raw) == rpm.PROMPT_BYTES == 1950
    assert hashlib.sha256(raw).hexdigest() == rpm.PROMPT_SHA256
    prompt = rpm.load_frozen_prompt()
    assert prompt.startswith("You are a principal investigator allocating compute budget")
    assert prompt.endswith("Provide your answer inside a \\boxed{A} or \\boxed{B}.\n")
    for placeholder, expected in rpm.PLACEHOLDER_COUNTS.items():
        assert prompt.count(placeholder) == expected


def test_prompt_sha_or_schema_drift_fails_closed(tmp_path: Path) -> None:
    changed = tmp_path / "prompt.txt"
    changed.write_bytes(rpm.PROMPT_PATH.read_bytes() + b"drift\n")
    with pytest.raises(rpm.RPMTransferError, match="byte-length drift"):
        rpm.load_frozen_prompt(changed)

    with pytest.raises(rpm.RPMTransferError, match="template placeholder drift"):
        rpm.render_prompt(
            task_desc="task",
            context_text="context",
            candidate_a=rpm.CandidateText("plan-a", "code-a"),
            candidate_b=rpm.CandidateText("plan-b", "code-b"),
            template=rpm.load_frozen_prompt().replace("{plan_A}", "missing"),
        )


def test_two_orientations_swap_only_candidate_plan_and_code() -> None:
    first = rpm.CandidateText("FIRST PLAN", "print({'first': 1})")
    second = rpm.CandidateText("SECOND PLAN", "print({'second': 2})")
    rendered = rpm.render_orientations(
        task_desc="SYNTHETIC TASK",
        context_text="SYNTHETIC PRIOR CONTEXT",
        first=first,
        second=second,
    )
    assert set(rendered) == {"AB", "BA"}
    assert rendered["AB"].index("FIRST PLAN") < rendered["AB"].index("SECOND PLAN")
    assert rendered["BA"].index("SECOND PLAN") < rendered["BA"].index("FIRST PLAN")
    for prompt in rendered.values():
        assert prompt.count("SYNTHETIC TASK") == 1
        assert prompt.count("SYNTHETIC PRIOR CONTEXT") == 2
        assert "print({'first': 1})" in prompt
        assert "print({'second': 2})" in prompt


def test_render_requires_all_decision_time_fields() -> None:
    with pytest.raises(rpm.RPMTransferError, match="candidate_a.plan must be nonempty"):
        rpm.render_prompt(
            task_desc="task",
            context_text="context",
            candidate_a=rpm.CandidateText("", "code-a"),
            candidate_b=rpm.CandidateText("plan-b", "code-b"),
        )


@pytest.mark.parametrize(
    ("content", "choice", "status"),
    [
        ("Reasoning.\n\\boxed{A}", "A", "parsed"),
        ("Reasoning.\n\\boxed { b }!", "B", "parsed"),
        ("", None, "missing_final_content"),
        ("A", None, "not_exactly_one_boxed_choice"),
        ("\\boxed{A} then \\boxed{B}", None, "not_exactly_one_boxed_choice"),
        ("\\boxed{A} trailing explanation", None, "boxed_choice_not_terminal"),
    ],
)
def test_strict_boxed_parser(content: str, choice: str | None, status: str) -> None:
    observed = rpm.parse_boxed_choice(content)
    assert observed.choice == choice
    assert observed.status == status


def test_orientation_reconciliation_is_position_aware() -> None:
    first = rpm.reconcile_orientations("\\boxed{A}", "\\boxed{B}")
    assert first == rpm.ReconciledChoice(0, "orientation_consistent")
    second = rpm.reconcile_orientations("\\boxed{B}", "\\boxed{A}")
    assert second == rpm.ReconciledChoice(1, "orientation_consistent")
    disagreement = rpm.reconcile_orientations("\\boxed{A}", "\\boxed{A}")
    assert disagreement == rpm.ReconciledChoice(None, "position_disagreement")
    missing = rpm.reconcile_orientations("not parsed", "\\boxed{B}")
    assert missing.winner_index is None
    assert missing.status.startswith("incomplete:")


def test_contract_is_transfer_only_and_does_not_authorize_calls() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["status"] == "SOURCE_AND_LOCAL_RENDERER_FROZEN_NO_LIVE_CALLS_AUTHORIZED"
    assert contract["source"]["version"] == "v2"
    assert contract["source"]["source_sha256"] == (
        "9910b62a9b8c9bb7da864fbb8534b124e697cf397a04103b43a273329e050ca0"
    )
    assert contract["frozen_prompt"]["sha256"] == rpm.PROMPT_SHA256
    assert contract["decision_corpus_transfer"]["may_be_called_exact_reproduction"] is False
    assert contract["decision_corpus_transfer"]["context_policy_status"] == "NOT_YET_FROZEN"
    assert contract["implementation"]["network_transport_implemented"] is False
    assert contract["security"]["live_calls_authorized"] is False
    assert contract["security"]["paid_api_calls"] == 0
    assert contract["interpretation_boundary"]["counts_as_distinct_claim_evidence"] is False


def test_renderer_has_no_network_or_credential_path() -> None:
    tree = ast.parse(Path(rpm.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported.isdisjoint({"urllib", "requests", "httpx", "socket", "os"})
    source = Path(rpm.__file__).read_text(encoding="utf-8").lower()
    assert "api_key" not in source
    assert "authorization" not in source


def test_postpush_receipt_binds_exact_commit_and_keeps_table_sealed() -> None:
    receipt = json.loads(POSTPUSH_RECEIPT.read_text(encoding="utf-8"))
    assert receipt["status"] == "PASS_SOURCE_BOUND_LOCAL_TRANSFER_READINESS"
    assert receipt["exact_public_commit"] == "0c04c7ed0e2d67437313236520c5c2028530c071"
    assert receipt["source_binding"]["frozen_prompt_sha256"] == rpm.PROMPT_SHA256
    assert receipt["focused_tests"]["passed"] == 28
    assert receipt["full_tests"]["passed"] == 2119
    assert receipt["full_tests"]["failed"] == 0
    assert receipt["changed_files"]["credential_filename_hits"] == 0
    assert receipt["changed_files"]["credential_shape_hits"] == 0
    assert receipt["implementation_boundary"]["live_calls_authorized"] is False
    assert receipt["implementation_boundary"]["table_4b_row_state"] == "SEALED"
    assert receipt["security"]["prospective_outcome_read"] is False
    assert receipt["security"]["prospective_prediction_value_read"] is False
    assert receipt["security"]["gpu"] == 0
    assert receipt["security"]["paid_api"] == 0
    assert receipt["interpretation"]["counts_as_distinct_claim_evidence"] is False
