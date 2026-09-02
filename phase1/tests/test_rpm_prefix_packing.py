from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from phase1 import rpm_inference_only_transfer as transfer
from phase1 import rpm_prefix_packing as packing
from phase1 import verify_rpm_prefix_packing as verifier


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "rpm_prefix_packing_contract_v1.json"
READINESS = ROOT / "RPM_PREFIX_PACKING_READINESS_20260902.md"
PREFLIGHT = ROOT / "RPM_QWEN_PREFIX_SMOKE_PREFLIGHT_20260902.md"
DRAFT = ROOT / "PAPER_DRAFT_DECISION_CORPUS_20260902.md"


class FakeTokenizer:
    """A deterministic tokenizer fixture; it is not a linguistic approximation."""

    def apply_chat_template(
        self,
        messages: list[dict[str, str]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
        enable_thinking: bool,
    ) -> str | list[int]:
        assert add_generation_prompt is True
        assert enable_thinking is True
        assert messages == [{"role": "user", "content": messages[0]["content"]}]
        rendered = f"<user>{messages[0]['content']}</user><assistant><think>"
        return list(rendered.encode("utf-8")) if tokenize else rendered


def context_line(rank: int, *, code: str | None = None) -> str:
    return packing.canonical_json(
        {
            "code": code or f"print('node-{rank}')",
            "context_rank": rank,
            "journal_step": 10 - rank,
            "operator": "Improve",
            "optimization_direction": "higher_is_better",
            "score_type": "self_reported_validation",
            "self_reported_validation": rank / 10,
        }
    )


def source_payload(node_count: int = 2) -> dict:
    lines = [context_line(rank) for rank in range(1, node_count + 1)]
    context_text = "\n".join(lines) if lines else packing.NO_PRIOR_CONTEXT
    return {
        "protocol": packing.INPUT_PROTOCOL,
        "task_desc": "Synthetic tabular regression task",
        "context": {
            "schema_version": packing.CONTEXT_SCHEMA,
            "protocol": packing.CONTEXT_PROTOCOL,
            "cutoff_step": 10,
            "node_count": node_count,
            "ordering": "journal_step_desc_then_node_sha256_asc",
            "score_source": "self_reported_validation",
            "identity_fields_emitted": False,
            "context_text": context_text,
            "context_sha256": hashlib.sha256(context_text.encode()).hexdigest(),
            "token_packing_applied": False,
            "live_call_authorized": False,
        },
        "candidate_first": {
            "plan": packing.MISSING_PLAN,
            "code": "print('candidate-first')",
        },
        "candidate_second": {
            "plan": packing.MISSING_PLAN,
            "code": "print('candidate-second')",
        },
    }


def snapshot_binding() -> dict:
    return {
        "artifacts": {"synthetic": {"bytes": 0, "sha256": "0" * 64}},
        "chat_template_bytes": packing.CHAT_TEMPLATE_BYTES,
        "chat_template_sha256": packing.CHAT_TEMPLATE_SHA256,
        "tokenizer_class_in_config": "Qwen2Tokenizer",
        "model_max_length": packing.CONTEXT_WINDOW_TOKENS,
        "bos_token": None,
        "eos_token": "<|im_end|>",
        "pad_token": "<|endoftext|>",
    }


def test_prefix_packing_keeps_whole_nodes_and_stops_at_first_overflow() -> None:
    source = packing.validate_source(source_payload(2))
    tokenizer = FakeTokenizer()
    first_only = packing.measure_orientations(
        tokenizer=tokenizer,
        task_desc=source["task_desc"],
        context_text=source["context_lines"][0],
        first=source["first"],
        second=source["second"],
    )
    two_nodes = packing.measure_orientations(
        tokenizer=tokenizer,
        task_desc=source["task_desc"],
        context_text="\n".join(source["context_lines"]),
        first=source["first"],
        second=source["second"],
    )
    limit = max(item.prompt_token_count for item in first_only.values())
    assert any(item.prompt_token_count > limit for item in two_nodes.values())
    selected = packing.select_prefix(
        tokenizer=tokenizer,
        task_desc=source["task_desc"],
        context_lines=source["context_lines"],
        source_context_empty=False,
        first=source["first"],
        second=source["second"],
        prompt_token_limit=limit,
    )
    assert selected.eligible_node_count == 2
    assert selected.included_node_count == 1
    assert selected.packed_context_text == source["context_lines"][0]
    assert selected.overflow_at_node_rank == 2
    assert selected.stop_reason == "FIRST_OVERFLOW_STOPS_PREFIX"
    assert all(item.prompt_token_count <= limit for item in selected.orientations.values())


def test_empty_source_context_and_budget_empty_context_are_distinct() -> None:
    validated = packing.validate_source(source_payload(0))
    selected = packing.select_prefix(
        tokenizer=FakeTokenizer(),
        task_desc=validated["task_desc"],
        context_lines=[],
        source_context_empty=True,
        first=validated["first"],
        second=validated["second"],
        prompt_token_limit=100_000,
    )
    assert selected.packed_context_text == packing.NO_PRIOR_CONTEXT
    assert selected.packed_context_text != packing.NO_FIT_CONTEXT
    assert selected.stop_reason == "NO_ELIGIBLE_CONTEXT_NODES"


def test_full_transfer_packing_records_fixed_public_binding_without_calls() -> None:
    result = packing.build_packing(
        source_payload(2),
        tokenizer=FakeTokenizer(),
        snapshot_binding=snapshot_binding(),
        runtime_versions=packing.EXPECTED_RUNTIME,
    )
    assert result["model"]["public_repository_revision"] == packing.MODEL_REVISION
    assert result["model"]["model_weights_downloaded_or_loaded"] is False
    assert result["packing"]["included_node_count"] == 2
    assert result["packing"]["both_orientations_must_fit"] is True
    assert set(result["orientations"]) == {"AB", "BA"}
    assert result["paper_alignment"]["paper_aligned_parent_bfs_context_selection"] is False
    assert result["paper_alignment"]["may_be_called_exact_reproduction"] is False
    assert result["security"]["model_call_implemented"] is False
    assert result["security"]["live_call_authorized"] is False


def test_nonimporting_verifier_reconstructs_the_same_synthetic_receipt() -> None:
    raw = source_payload(3)
    source_sha = hashlib.sha256(
        json.dumps(raw, sort_keys=True).encode("utf-8")
    ).hexdigest()
    produced = packing.build_packing(
        raw,
        tokenizer=FakeTokenizer(),
        snapshot_binding=snapshot_binding(),
        runtime_versions=packing.EXPECTED_RUNTIME,
    )
    produced["source_sha256"] = source_sha
    independently_rebuilt = verifier.reconstruct(
        raw,
        tokenizer=FakeTokenizer(),
        snapshot=snapshot_binding(),
        versions=verifier.VERSIONS,
        source_sha256=source_sha,
    )
    assert independently_rebuilt == produced


def test_input_schema_rejects_outcome_fields_noncanonical_nodes_and_credentials() -> None:
    outcome = source_payload()
    outcome["candidate_first"]["graded"] = 0.9
    with pytest.raises(packing.RPMTokenPackingError, match="candidate schema mismatch"):
        packing.validate_source(outcome)

    noncanonical = source_payload(1)
    payload = json.loads(noncanonical["context"]["context_text"])
    noncanonical_text = json.dumps(payload, ensure_ascii=False)
    noncanonical["context"]["context_text"] = noncanonical_text
    noncanonical["context"]["context_sha256"] = hashlib.sha256(
        noncanonical_text.encode()
    ).hexdigest()
    with pytest.raises(packing.RPMTokenPackingError, match="not canonical JSON"):
        packing.validate_source(noncanonical)

    credential = source_payload()
    credential["candidate_second"]["code"] = "value = 'sk-' + 'x' * 20"
    credential["candidate_second"]["code"] = "sk-" + "x" * 20
    with pytest.raises(packing.RPMTokenPackingError, match="credential-shaped"):
        packing.validate_source(credential)


def test_generic_artifact_gate_checks_hashes_and_refuses_weight_files(tmp_path: Path) -> None:
    artifact = tmp_path / "tiny.json"
    artifact.write_bytes(b"{}\n")
    expected = {"tiny.json": (3, hashlib.sha256(b"{}\n").hexdigest())}
    assert packing.validate_artifact_manifest(tmp_path, expected)["tiny.json"]["bytes"] == 3
    (tmp_path / "weights.safetensors").write_bytes(b"not weights")
    with pytest.raises(packing.RPMTokenPackingError, match="model weight file refused"):
        packing.validate_artifact_manifest(tmp_path, expected)


def test_independent_verifier_does_not_import_either_producer() -> None:
    path = Path(verifier.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not any("rpm_prefix_packing" in name for name in imported)
    assert not any("rpm_inference_only_transfer" in name for name in imported)


def test_tools_are_local_only_and_have_no_model_call_or_credential_loader() -> None:
    paths = [Path(packing.__file__), Path(verifier.__file__)]
    for path in paths:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        assert imports.isdisjoint({"requests", "httpx", "urllib", "socket", "openai"})
        lowered = source.lower()
        assert "api_key" not in lowered
        assert "authorization" not in lowered
        assert "local_files_only=true" in lowered.replace(" ", "")
        assert "trust_remote_code=false" in lowered.replace(" ", "")


def test_contract_freezes_transfer_packing_and_keeps_bfs_and_results_blocked() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["status"] == (
        "PUBLIC_TOKENIZER_AND_DETERMINISTIC_TRANSFER_PACKING_FROZEN_"
        "PAPER_ALIGNED_BFS_BLOCKED"
    )
    assert contract["public_model_transfer_binding"]["repository_revision"] == packing.MODEL_REVISION
    assert contract["tokenizer_snapshot"]["tokenizer.json"]["sha256"] == (
        packing.REQUIRED_ARTIFACTS["tokenizer.json"][1]
    )
    assert contract["packing"]["prompt_token_limit"] == packing.PROMPT_TOKEN_LIMIT
    assert contract["packing"]["partial_node_truncation_allowed"] is False
    assert contract["paper_alignment_blocker"]["current_transfer_context_is_paper_aligned"] is False
    assert contract["security"]["live_calls_authorized"] is False
    assert contract["security"]["table_4b_state"] == "SEALED"
    assert contract["interpretation_boundary"]["counts_as_distinct_claim_evidence"] is False


def test_readiness_and_preflight_disclose_bfs_deviation_and_no_effect_claim() -> None:
    readiness = READINESS.read_text(encoding="utf-8")
    preflight = PREFLIGHT.read_text(encoding="utf-8")
    assert "breadth-first" in readiness
    assert "non-buggy" in readiness
    assert "只能" not in readiness or "transfer" in readiness
    assert "Table 4B=`SEALED`" in readiness
    assert "counts_as_distinct_claim_evidence=false" in readiness
    for number in range(1, 14):
        assert f"{number}. **" in preflight
    assert "模型权重" in preflight
    assert "paid API=0" in preflight


def test_manuscript_does_not_yet_claim_completed_tokenizer_baseline() -> None:
    draft = DRAFT.read_text(encoding="utf-8")
    assert "RPM-style inference-only prompt-transfer" in draft
    assert "must not be reported\nas a completed baseline run" in draft
