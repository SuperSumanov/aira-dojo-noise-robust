import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from phase1 import source_choice_benchmark_materializer as materializer
from phase1 import source_choice_sealed_evaluator as evaluator
from phase1 import verify_source_choice_benchmark_materialization as verifier


def journal_blob(task: str, child: str, parent: str, code: str = "print('safe')") -> bytes:
    parent_raw = parent.split("__", 1)[1]
    child_raw = child.split("__", 1)[1]
    rows = [
        {
            "id": parent_raw,
            "step": 1,
            "parents": [],
            "code": "print('parent')",
            "metric_info": {"competition_id": task},
        },
        {
            "id": child_raw,
            "step": 2,
            "parents": [1],
            "code": code,
            "operators_used": ["Improve"],
            "depth": 2,
            "metric_info": {"competition_id": task},
        },
    ]
    return b"".join(materializer.canonical_json(row) + b"\n" for row in rows)


def install_journal(root: Path, blob: bytes) -> Path:
    path = root / "run-a" / "checkpoint" / "journal.jsonl"
    path.parent.mkdir(parents=True)
    path.write_bytes(blob)
    return path


def test_checked_in_protocol_is_strictly_valid():
    root = Path(__file__).resolve().parents[2]
    protocol = materializer.load_protocol(
        root / "phase1" / "source_choice_benchmark_materialization_protocol_v2.json"
    )
    assert protocol["expected"]["materializable_groups"] == 3000
    assert protocol["scope"] == materializer.EXPECTED_SCOPE
    assert protocol["parent_card_required"] is False


def test_collects_only_needed_credential_safe_journal(tmp_path: Path):
    blob = journal_blob("task-a", "task-a__child", "task-a__parent")
    install_journal(tmp_path, blob)
    digest = materializer.sha256_bytes(blob)
    found, summary = materializer.collect_needed_journals({"root": tmp_path}, {digest})
    assert found == {digest: blob}
    assert summary["needed_journal_shas_found"] == 1


def test_needed_credential_shaped_journal_is_fail_closed(tmp_path: Path):
    credential_shape = "sk-" + "a" * 16
    blob = journal_blob(
        "task-a", "task-a__child", "task-a__parent", f"value='{credential_shape}'"
    )
    install_journal(tmp_path, blob)
    digest = materializer.sha256_bytes(blob)
    with pytest.raises(materializer.MaterializationError, match="needed journal contains"):
        materializer.collect_needed_journals({"root": tmp_path}, {digest})


def test_decodes_code_and_parent_without_numeric_metric_access():
    blob = journal_blob("task-a", "task-a__child", "task-a__parent")
    digest = materializer.sha256_bytes(blob)
    output = materializer.decode_needed_nodes(
        {digest: blob},
        {
            digest: {
                "task-a__child": {
                    "task": "task-a",
                    "parent": "task-a__parent",
                    "role": "train",
                }
            }
        },
    )
    assert output["task-a__child"]["code"] == "print('safe')"
    assert output["task-a__child"]["provenance"] == "journal_recovered"
    assert output["task-a__child"]["source_journal_sha256"] == digest


def test_journal_parent_mismatch_is_rejected():
    blob = journal_blob("task-a", "task-a__child", "task-a__parent")
    digest = materializer.sha256_bytes(blob)
    with pytest.raises(materializer.MaterializationError, match="parent mismatch"):
        materializer.decode_needed_nodes(
            {digest: blob},
            {
                digest: {
                    "task-a__child": {
                        "task": "task-a",
                        "parent": "task-a__wrong",
                        "role": "train",
                    }
                }
            },
        )


def test_jsonl_writer_is_canonical_and_deterministic(tmp_path: Path):
    rows = [{"z": 1, "a": "x"}, {"a": "y", "z": 2}]
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    count_a, digest_a = materializer.write_jsonl(first, rows)
    count_b, digest_b = materializer.write_jsonl(second, rows)
    assert count_a == count_b == 2
    assert digest_a == digest_b
    assert first.read_bytes() == second.read_bytes()
    assert json.loads(first.read_text(encoding="utf-8").splitlines()[0]) == rows[0]


def test_independent_verifier_reconstructs_needed_journal(tmp_path: Path):
    blob = journal_blob("task-a", "task-a__child", "task-a__parent")
    install_journal(tmp_path, blob)
    digest = verifier.digest_bytes(blob)
    output, inventory = verifier.recover_journal_candidates(
        {"root": tmp_path},
        {
            digest: {
                "task-a__child": {
                    "task": "task-a",
                    "parent": "task-a__parent",
                    "role": "frozen",
                }
            }
        },
    )
    assert output["task-a__child"]["code_sha256"] == materializer.sha256_bytes(
        b"print('safe')"
    )
    assert inventory["needed_journal_shas"] == 1


def evaluator_fixture(tmp_path: Path, leak_winner: bool = False):
    candidate_a = materializer.hash_identity("candidate-a")
    candidate_b = materializer.hash_identity("candidate-b")
    group_id = materializer.hash_identity("group-a")
    group = {
        "schema_version": materializer.SCHEMA,
        "group_id": group_id,
        "role": "frozen",
        "task": "task-a",
        "run_id_sha256": materializer.hash_identity("run-a"),
        "parent_id_sha256": materializer.hash_identity("parent-a"),
        "source_size": 2,
        "candidates": [
            {"candidate_id_sha256": value} for value in sorted((candidate_a, candidate_b))
        ],
    }
    if leak_winner:
        group["winner_candidate_sha256"] = candidate_a
    label = {
        "schema_version": materializer.VAULT_SCHEMA,
        "group_id": group_id,
        "task": "task-a",
        "run_id_sha256": materializer.hash_identity("run-a"),
        "winner_candidate_sha256": candidate_a,
    }
    prediction = {
        "schema_version": evaluator.PREDICTION_SCHEMA,
        "group_id": group_id,
        "selected_candidate_sha256": candidate_a,
    }
    inputs = tmp_path / "inputs.jsonl"
    vault = tmp_path / "vault.jsonl"
    predictions = tmp_path / "predictions.jsonl"
    materializer.write_jsonl(inputs, [group])
    materializer.write_jsonl(vault, [label])
    materializer.write_jsonl(predictions, [prediction])
    return SimpleNamespace(
        inputs=str(inputs),
        vault=str(vault),
        predictions=str(predictions),
        expected_input_sha256=materializer.sha256_file(inputs),
        expected_vault_sha256=materializer.sha256_file(vault),
    )


def test_sealed_evaluator_reports_only_aggregate(tmp_path: Path):
    result = evaluator.evaluate(evaluator_fixture(tmp_path))
    assert result["accuracy"] == 1.0
    assert result["per_group_truth_emitted"] is False
    assert result["winner_candidate_ids_emitted"] is False
    assert "winner_candidate_sha256" not in json.dumps(result)


def test_sealed_evaluator_rejects_public_label_leak(tmp_path: Path):
    with pytest.raises(evaluator.EvaluationError, match="contains winner label"):
        evaluator.evaluate(evaluator_fixture(tmp_path, leak_winner=True))
