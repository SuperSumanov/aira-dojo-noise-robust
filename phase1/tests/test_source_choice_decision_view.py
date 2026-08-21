import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from phase1 import source_choice_decision_view as producer
from phase1 import source_choice_decision_view_sealed_evaluator as evaluator
from phase1 import verify_source_choice_decision_view as verifier


def write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, values):
    path.write_bytes(b"".join(producer.canonical(value) + b"\n" for value in values))


def identity(value: str) -> str:
    return producer.sha256_bytes(value.encode())


def candidate(name: str, provenance: str = "card"):
    code = f"print({name!r})"
    return {
        "candidate_id_sha256": identity(name),
        "code": code,
        "code_sha256": identity(code),
        "operator": "Improve",
        "step": 2,
        "depth": 1,
        "provenance": provenance,
        "source_journal_sha256": identity("journal") if provenance == "journal_recovered" else None,
    }


def raw_group(role: str, number: int):
    candidates = sorted(
        [candidate(f"{role}-{number}-a"), candidate(f"{role}-{number}-b", "journal_recovered")],
        key=lambda value: value["candidate_id_sha256"],
    )
    value = {
        "schema_version": producer.RAW_SCHEMA,
        "group_id": identity(f"group-{role}-{number}"),
        "role": role,
        "task": "task-a",
        "run_id_sha256": identity(f"run-{role}"),
        "parent_id_sha256": identity(f"parent-{role}-{number}"),
        "source_size": 2,
        "candidates": candidates,
    }
    if role == "train":
        value["winner_candidate_sha256"] = candidates[0]["candidate_id_sha256"]
    return value


def fixture(tmp_path: Path):
    source_paths = {}
    groups = {}
    for role in producer.ROLES:
        groups[role] = [raw_group(role, 1)]
        source_paths[role] = tmp_path / f"source_{role}.jsonl"
        write_jsonl(source_paths[role], groups[role])
    source_summary = {
        "status": "SOURCE_CHOICE_BENCHMARK_MATERIALIZED_AND_SEALED",
        "source_commit": "a" * 40,
        "groups": 3,
        "candidate_slots": 6,
        "groups_by_role": {role: 1 for role in producer.ROLES},
        "candidate_slots_by_role": {role: 2 for role in producer.ROLES},
        "frozen_public_winner_fields": 0,
        "extension_public_winner_fields": 0,
        "frozen_labels_used_for_model_or_scoring": False,
        "sealed_vault_outputs_opaque": {
            "frozen_labels.jsonl": identity("frozen-vault"),
            "extension_labels.jsonl": identity("extension-vault"),
        },
    }
    summary_path = tmp_path / "source_summary.json"
    manifest_path = tmp_path / "source_manifest.json"
    write_json(summary_path, source_summary)
    write_json(manifest_path, {"fixture": True})
    source_verification = {
        "status": "INDEPENDENT_SOURCE_CHOICE_BENCHMARK_MATERIALIZATION_VERIFIED",
        "producer_imported": False,
        "source_commit": "a" * 40,
        "public_summary_sha256": producer.sha256_file(summary_path),
        "public_manifest_sha256": producer.sha256_file(manifest_path),
    }
    verification_path = tmp_path / "source_verification.json"
    write_json(verification_path, source_verification)
    protocol = {
        "protocol": "source-choice-decision-view-v1",
        "source": {
            "materialization_commit": "a" * 40,
            "summary_sha256": producer.sha256_file(summary_path),
            "manifest_sha256": producer.sha256_file(manifest_path),
            "independent_verification_sha256": producer.sha256_file(verification_path),
            "train_groups_sha256": producer.sha256_file(source_paths["train"]),
            "frozen_inputs_sha256": producer.sha256_file(source_paths["frozen"]),
            "extension_inputs_sha256": producer.sha256_file(source_paths["extension"]),
        },
        "expected": {
            "groups": 3,
            "candidate_slots": 6,
            "tasks": 1,
            "groups_by_role": {role: 1 for role in producer.ROLES},
            "candidate_slots_by_role": {role: 2 for role in producer.ROLES},
            "train_winner_fields": 1,
            "frozen_winner_fields": 0,
            "extension_winner_fields": 0,
            "blocked_candidate_fields_removed": {
                "provenance": 6,
                "source_journal_sha256": 6,
            },
        },
        "model_group_fields": sorted(producer.MODEL_BASE_FIELDS),
        "train_only_group_fields": ["winner_candidate_sha256"],
        "model_candidate_fields": sorted(producer.MODEL_CANDIDATE_FIELDS),
        "cluster_manifest_fields": sorted(producer.CLUSTER_FIELDS),
        "blocked_model_fields": sorted(producer.BLOCKED_MODEL_FIELDS),
        "scope": producer.EXPECTED_SCOPE,
    }
    protocol_path = tmp_path / "protocol.json"
    write_json(protocol_path, protocol)
    output = tmp_path / "view"
    arguments = SimpleNamespace(
        protocol=str(protocol_path),
        source_summary=str(summary_path),
        source_manifest=str(manifest_path),
        source_verification=str(verification_path),
        source=[f"{role}={source_paths[role]}" for role in producer.ROLES],
        output=str(output),
    )
    return arguments, groups, output


def test_checked_in_protocol_has_exact_decision_time_surface():
    root = Path(__file__).resolve().parents[2]
    protocol = producer.load_protocol(root / "phase1" / "source_choice_decision_view_protocol_v1.json")
    assert protocol["expected"]["groups"] == 3000
    assert set(protocol["blocked_model_fields"]) == producer.BLOCKED_MODEL_FIELDS
    assert protocol["scope"] == producer.EXPECTED_SCOPE


def test_projection_strips_provenance_and_separates_cluster_metadata(tmp_path: Path):
    arguments, _, output = fixture(tmp_path)
    result = producer.build(arguments)
    assert result["status"] == "SOURCE_CHOICE_DECISION_VIEW_READY"
    train = json.loads((output / "train_model.jsonl").read_text(encoding="utf-8"))
    assert set(train) == producer.MODEL_BASE_FIELDS | {"winner_candidate_sha256"}
    assert all(set(value) == producer.MODEL_CANDIDATE_FIELDS for value in train["candidates"])
    assert "provenance" not in json.dumps(train)
    cluster = json.loads((output / "cluster_manifest.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert set(cluster) == producer.CLUSTER_FIELDS
    assert result["blocked_candidate_fields_removed"] == {
        "provenance": 6,
        "source_journal_sha256": 6,
    }


def test_independent_verifier_reconstructs_projection(tmp_path: Path):
    arguments, _, output = fixture(tmp_path)
    producer.build(arguments)
    verify_arguments = SimpleNamespace(
        protocol=arguments.protocol,
        source_summary=arguments.source_summary,
        source_manifest=arguments.source_manifest,
        source_verification=arguments.source_verification,
        source=arguments.source,
        view=str(output),
    )
    result = verifier.verify(verify_arguments)
    assert result["status"] == "INDEPENDENT_SOURCE_CHOICE_DECISION_VIEW_VERIFIED"
    assert result["producer_imported"] is False
    assert result["blocked_fields_present_in_model_objects"] == 0


def test_projection_rejects_raw_extra_field(tmp_path: Path):
    arguments, groups, _ = fixture(tmp_path)
    groups["frozen"][0]["post_outcome"] = True
    frozen_path = Path(arguments.source[1].split("=", 1)[1])
    write_jsonl(frozen_path, groups["frozen"])
    protocol = json.loads(Path(arguments.protocol).read_text(encoding="utf-8"))
    protocol["source"]["frozen_inputs_sha256"] = producer.sha256_file(frozen_path)
    write_json(Path(arguments.protocol), protocol)
    with pytest.raises(producer.DecisionViewError, match="raw group fields"):
        producer.build(arguments)


def test_projection_rejects_code_hash_drift(tmp_path: Path):
    arguments, groups, _ = fixture(tmp_path)
    groups["extension"][0]["candidates"][0]["code"] = "print('changed')"
    extension_path = Path(arguments.source[2].split("=", 1)[1])
    write_jsonl(extension_path, groups["extension"])
    protocol = json.loads(Path(arguments.protocol).read_text(encoding="utf-8"))
    protocol["source"]["extension_inputs_sha256"] = producer.sha256_file(extension_path)
    write_json(Path(arguments.protocol), protocol)
    with pytest.raises(producer.DecisionViewError, match="candidate closure"):
        producer.build(arguments)


def evaluator_arguments(tmp_path: Path):
    build_arguments, groups, output = fixture(tmp_path)
    producer.build(build_arguments)
    frozen = groups["frozen"][0]
    winner = frozen["candidates"][0]["candidate_id_sha256"]
    vault = tmp_path / "vault.jsonl"
    prediction = tmp_path / "prediction.jsonl"
    write_jsonl(
        vault,
        [
            {
                "schema_version": evaluator.LABEL_SCHEMA,
                "group_id": frozen["group_id"],
                "task": frozen["task"],
                "run_id_sha256": frozen["run_id_sha256"],
                "winner_candidate_sha256": winner,
            }
        ],
    )
    write_jsonl(
        prediction,
        [
            {
                "schema_version": evaluator.PREDICTION_SCHEMA,
                "group_id": frozen["group_id"],
                "selected_candidate_sha256": winner,
            }
        ],
    )
    inputs = output / "frozen_model.jsonl"
    cluster = output / "cluster_manifest.jsonl"
    arguments = SimpleNamespace(
        inputs=str(inputs),
        cluster_manifest=str(cluster),
        predictions=str(prediction),
        vault=str(vault),
        expected_input_sha256=producer.sha256_file(inputs),
        expected_cluster_manifest_sha256=producer.sha256_file(cluster),
        expected_vault_sha256=producer.sha256_file(vault),
    )
    return arguments, output


def test_sealed_evaluator_accepts_sanitized_view_and_emits_only_aggregates(tmp_path: Path):
    arguments, _ = evaluator_arguments(tmp_path)
    result = evaluator.evaluate(arguments)
    assert result["accuracy"] == 1.0
    assert result["per_group_truth_emitted"] is False
    assert result["winner_candidate_ids_emitted"] is False
    assert "winner_candidate_sha256" not in json.dumps(result)


def test_sealed_evaluator_rejects_provenance_extra_field(tmp_path: Path):
    arguments, output = evaluator_arguments(tmp_path)
    group = json.loads((output / "frozen_model.jsonl").read_text(encoding="utf-8"))
    group["candidates"][0]["provenance"] = "card"
    contaminated = tmp_path / "contaminated.jsonl"
    write_jsonl(contaminated, [group])
    arguments.inputs = str(contaminated)
    arguments.expected_input_sha256 = producer.sha256_file(contaminated)
    with pytest.raises(evaluator.EvaluationError, match="exact fields"):
        evaluator.evaluate(arguments)


def test_sealed_evaluator_rejects_public_winner_field(tmp_path: Path):
    arguments, output = evaluator_arguments(tmp_path)
    group = json.loads((output / "frozen_model.jsonl").read_text(encoding="utf-8"))
    group["winner_candidate_sha256"] = group["candidates"][0]["candidate_id_sha256"]
    contaminated = tmp_path / "winner_leak.jsonl"
    write_jsonl(contaminated, [group])
    arguments.inputs = str(contaminated)
    arguments.expected_input_sha256 = producer.sha256_file(contaminated)
    with pytest.raises(evaluator.EvaluationError, match="exact fields"):
        evaluator.evaluate(arguments)


def test_sealed_evaluator_rejects_cluster_run_mismatch(tmp_path: Path):
    arguments, output = evaluator_arguments(tmp_path)
    rows = [json.loads(line) for line in (output / "cluster_manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    for row in rows:
        if row["role"] == "frozen":
            row["run_id_sha256"] = identity("wrong-run")
    bad_cluster = tmp_path / "bad_cluster.jsonl"
    write_jsonl(bad_cluster, rows)
    arguments.cluster_manifest = str(bad_cluster)
    arguments.expected_cluster_manifest_sha256 = producer.sha256_file(bad_cluster)
    with pytest.raises(evaluator.EvaluationError, match="vault/group closure"):
        evaluator.evaluate(arguments)
