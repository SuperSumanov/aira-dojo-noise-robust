from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from phase1 import rpm_decision_time_context as context


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "rpm_decision_time_context_contract_v1.json"
VERIFIER = ROOT / "verify_rpm_decision_time_context.py"
READINESS = ROOT / "RPM_DECISION_TIME_CONTEXT_READINESS_20260902.md"
DRAFT = ROOT / "PAPER_DRAFT_DECISION_CORPUS_20260902.md"
POSTPUSH = ROOT / "rpm_decision_time_context_postpush_receipt_20260902.json"


def h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def candidates() -> list[context.CandidateRef]:
    return [context.CandidateRef(h("candidate-a"), 5), context.CandidateRef(h("candidate-b"), 6)]


def node(name: str, step: int, score: float, *, run: str = "run", task: str = "task") -> context.ExecutedNode:
    return context.ExecutedNode(
        node_id_sha256=h(name),
        run_id_sha256=h(run),
        task=task,
        step=step,
        operator="Improve",
        code=f"print({name!r})",
        self_reported_validation=score,
        higher_is_better=True,
    )


def source_payload() -> dict:
    return {
        "protocol": context.PROTOCOL,
        "run_id_sha256": h("run"),
        "task": "task",
        "candidates": [
            {"candidate_id_sha256": item.candidate_id_sha256, "step": item.step}
            for item in candidates()
        ],
        "nodes": [
            {
                "node_id_sha256": h("old"),
                "run_id_sha256": h("run"),
                "task": "task",
                "step": 1,
                "operator": "Draft",
                "code": "print('old')",
                "self_reported_validation": 0.1,
                "higher_is_better": True,
            },
            {
                "node_id_sha256": h("recent"),
                "run_id_sha256": h("run"),
                "task": "task",
                "step": 4,
                "operator": "Improve",
                "code": "print('recent')",
                "self_reported_validation": 0.2,
                "higher_is_better": True,
            },
        ],
    }


def test_context_uses_only_predecision_self_report_and_orders_by_recency() -> None:
    result = context.build_context(
        run_id_sha256=h("run"),
        task="task",
        candidates=candidates(),
        nodes=[node("old", 1, 0.1), node("recent", 4, 0.2)],
    )
    assert result.cutoff_step == 5
    assert result.node_count == 2
    lines = [json.loads(line) for line in result.context_text.splitlines()]
    assert [line["journal_step"] for line in lines] == [4, 1]
    assert [line["context_rank"] for line in lines] == [1, 2]
    assert all(line["score_type"] == "self_reported_validation" for line in lines)
    assert all("label" not in line and "graded" not in line for line in lines)
    assert all("candidate" not in line for line in lines)
    assert result.context_sha256 == hashlib.sha256(result.context_text.encode()).hexdigest()


def test_empty_context_is_explicit_and_not_silently_dropped() -> None:
    result = context.build_context(
        run_id_sha256=h("run"), task="task", candidates=candidates(), nodes=[]
    )
    assert result.node_count == 0
    assert result.context_text == context.EMPTY_CONTEXT


@pytest.mark.parametrize(
    ("bad_node", "message"),
    [
        (node("candidate-a", 1, 0.1), "candidate record"),
        (node("late", 5, 0.1), "post-decision"),
        (node("other-run", 1, 0.1, run="other"), "cross-run"),
        (node("other-task", 1, 0.1, task="other"), "cross-task"),
    ],
)
def test_context_fails_closed_on_temporal_or_identity_contamination(
    bad_node: context.ExecutedNode, message: str
) -> None:
    with pytest.raises(context.RPMContextError, match=message):
        context.build_context(
            run_id_sha256=h("run"), task="task", candidates=candidates(), nodes=[bad_node]
        )


def test_context_rejects_credential_shaped_code_without_storing_a_key_literal() -> None:
    fake = "sk-" + "x" * 20
    bad = context.ExecutedNode(
        node_id_sha256=h("secret-node"),
        run_id_sha256=h("run"),
        task="task",
        step=1,
        operator="Draft",
        code=f"credential = {fake!r}",
        self_reported_validation=0.1,
        higher_is_better=True,
    )
    with pytest.raises(context.RPMContextError, match="credential-shaped"):
        context.build_context(
            run_id_sha256=h("run"), task="task", candidates=candidates(), nodes=[bad]
        )


def test_source_schema_refuses_external_grade_field(tmp_path: Path) -> None:
    source = source_payload()
    source["nodes"][0]["graded"] = 0.9
    path = tmp_path / "source.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(context.RPMContextError, match="history source schema mismatch"):
        context.load_source(path)


def test_builder_and_nonimporting_verifier_agree_byte_for_byte(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    built_a = tmp_path / "built_a.json"
    built_b = tmp_path / "built_b.json"
    verification = tmp_path / "verification.json"
    source.write_text(json.dumps(source_payload(), sort_keys=True), encoding="utf-8")
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    build_command = [
        sys.executable,
        str(Path(context.__file__)),
        "--source",
        str(source),
        "--expected-source-sha256",
        source_sha,
    ]
    subprocess.run(build_command + ["--output", str(built_a)], check=True, capture_output=True)
    subprocess.run(build_command + ["--output", str(built_b)], check=True, capture_output=True)
    assert built_a.read_bytes() == built_b.read_bytes()
    immutable = built_a.read_bytes()
    repeated = subprocess.run(
        build_command + ["--output", str(built_a)], check=False, capture_output=True
    )
    assert repeated.returncode != 0
    assert built_a.read_bytes() == immutable
    built_sha = hashlib.sha256(built_a.read_bytes()).hexdigest()
    subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            "--source",
            str(source),
            "--expected-source-sha256",
            source_sha,
            "--candidate",
            str(built_a),
            "--expected-candidate-sha256",
            built_sha,
            "--output",
            str(verification),
        ],
        check=True,
        capture_output=True,
    )
    checked = json.loads(verification.read_text(encoding="utf-8"))
    assert checked["status"] == "RPM_CONTEXT_INDEPENDENT_VERIFICATION_PASS"
    assert checked["external_grade_used"] is False
    assert checked["candidate_outcome_used"] is False


def test_verifier_is_structurally_independent() -> None:
    tree = ast.parse(VERIFIER.read_text(encoding="utf-8"))
    imports = set()
    for item in ast.walk(tree):
        if isinstance(item, ast.Import):
            imports.update(alias.name for alias in item.names)
        elif isinstance(item, ast.ImportFrom) and item.module:
            imports.add(item.module)
    assert not any("rpm_decision_time_context" in name for name in imports)


def test_context_tools_have_no_network_or_credential_loader() -> None:
    for path in (Path(context.__file__), VERIFIER):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = set()
        for item in ast.walk(tree):
            if isinstance(item, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in item.names)
            elif isinstance(item, ast.ImportFrom) and item.module:
                imports.add(item.module.split(".")[0])
        assert imports.isdisjoint({"requests", "httpx", "urllib", "socket"})
        source = path.read_text(encoding="utf-8").lower()
        assert "api_key" not in source
        assert "authorization" not in source


def test_contract_freezes_score_semantics_but_not_token_packing() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["status"] == "STRUCTURAL_CONTEXT_POLICY_FROZEN_TOKEN_PACKING_NOT_YET_FROZEN"
    assert contract["source_semantics"]["required_score_field"] == "obs.val_at_low"
    assert contract["source_semantics"]["external_grade_or_label_allowed"] is False
    assert contract["selection"]["same_context_for_every_pair_and_orientation_within_parent"] is True
    assert contract["packing_boundary"]["status"] == "NOT_YET_FROZEN"
    assert contract["historical_train_only_feasibility"]["train_groups"] == 2109
    assert contract["historical_train_only_feasibility"]["groups_with_scorable_prior_context"] == 2071
    assert contract["security"]["live_calls_authorized"] is False
    assert contract["historical_train_only_feasibility"]["counts_as_distinct_claim_evidence"] is False


def test_readiness_and_manuscript_keep_result_and_packing_sealed() -> None:
    readiness = READINESS.read_text(encoding="utf-8")
    draft = DRAFT.read_text(encoding="utf-8")
    assert "2,087 行全部为" in readiness
    assert "2,071/2,109" in readiness
    assert "token packing 仍未冻结" in readiness
    assert "counts_as_distinct_claim_evidence=false" in readiness
    assert "then-visible self-reported" in draft
    assert "post-hoc external grade" in draft
    assert "tokenizer-based context packing" in draft
    assert "must not be reported\nas a completed baseline run" in draft


def test_postpush_receipt_binds_exact_commit_and_remaining_gates() -> None:
    receipt = json.loads(POSTPUSH.read_text(encoding="utf-8"))
    assert receipt["exact_public_commit"] == "bda3de4bddc1d03c13bedd624c86a6492695e33d"
    assert receipt["split_first_failed_input_gate"]["endpoint_payload_used"] is False
    assert receipt["historical_train_only_feasibility"]["train_groups"] == 2109
    assert receipt["historical_train_only_feasibility"]["groups_with_scorable_prior_context"] == 2071
    assert receipt["focused_tests"]["passed"] == 43
    assert receipt["full_tests"]["passed"] == 2134
    assert receipt["full_tests"]["failed"] == 0
    assert receipt["changed_files"]["credential_filename_hits"] == 0
    assert receipt["changed_files"]["credential_shape_hits"] == 0
    assert receipt["remaining_gates"]["exact_tokenizer_prefix_packing_frozen"] is False
    assert receipt["remaining_gates"]["live_calls_authorized"] is False
    assert receipt["remaining_gates"]["table_4b_row_state"] == "SEALED"
    assert receipt["security"]["prospective_outcome_read"] is False
    assert receipt["security"]["paid_api"] == 0
    assert receipt["interpretation"]["counts_as_distinct_claim_evidence"] is False
