from __future__ import annotations

import ast
import json
from pathlib import Path

from phase1 import audit_historical_release_future_identifier_erased_overlap as producer
from phase1 import historical_release_future_identifier_erased_schema as schema
from phase1 import verify_historical_release_future_identifier_erased_overlap as verifier


def test_schema_freezes_full_release_future_population_and_thresholds() -> None:
    producer.require_dependency_contract()
    verifier.require_dependency_contract()
    assert schema.HISTORICAL_ENDPOINTS == 16012
    assert schema.HISTORICAL_RUNS == 667
    assert schema.HISTORICAL_TASKS == 25
    assert schema.OBSERVED_FUTURE_RUNS == 435
    assert schema.OBSERVED_FUTURE_ENDPOINTS == 11906
    assert schema.OBSERVED_FUTURE_TASKS == 34
    assert (schema.PRIMARY_NUMERATOR, schema.PRIMARY_DENOMINATOR) == (17, 20)
    assert (schema.STRICT_NUMERATOR, schema.STRICT_DENOMINATOR) == (19, 20)


def test_protocol_discloses_known_subset_and_keeps_claim_boundary() -> None:
    path = Path(__file__).parents[1] / "historical_release_future_identifier_erased_887_protocol_v1.json"
    protocol = json.loads(path.read_text(encoding="utf-8"))
    producer.validate_protocol(protocol)
    verifier.validate_protocol(protocol)
    prior = protocol["prior_result_disclosure"]
    assert prior["historical_train_subset_result_known"] is True
    assert prior["historical_train_subset_endpoints"] == 5519
    assert prior["historical_train_subset_primary_links"] == 0
    assert prior["full_release_result_read_before_freeze"] is False
    boundary = protocol["claim_boundary"]
    assert boundary["full_byte_reproducible_v11_release_covered"] is True
    assert boundary["semantic_clone_absence_proven"] is False
    assert boundary["pretraining_contamination_absence_proven"] is False
    assert boundary["predictor_effect_accuracy_or_search_utility_computed"] is False


def test_ordered_classification_is_shared_and_cannot_be_strict_rescued() -> None:
    passed = {"a": True, "b": True}
    failed = {"a": True, "b": False}
    assert producer.classify(passed, 0) == "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS"
    assert verifier.classify(passed, 0) == "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS"
    assert producer.classify(passed, 3) == (
        "LOW_IDENTIFIER_ERASED_RELEASE_OVERLAP_WITH_EXCEPTIONS"
    )
    assert verifier.classify(passed, 3) == (
        "LOW_IDENTIFIER_ERASED_RELEASE_OVERLAP_WITH_EXCEPTIONS"
    )
    assert producer.classify(failed, 0) == "RELEASE_SPLIT_INTEGRITY_GATE_FAIL"
    assert verifier.classify(failed, 0) == "RELEASE_SPLIT_INTEGRITY_GATE_FAIL"


def test_full_release_loaders_independently_match_on_synthetic_contract(
    tmp_path: Path, monkeypatch
) -> None:
    cards = [
        {
            "id": "c1",
            "run_id": "r1",
            "task": {"name": "t1"},
            "code": "x = 1",
            "label": {"forbidden": 0.1},
            "obs": {"forbidden": "unused"},
        },
        {
            "id": "c2",
            "run_id": "r1",
            "task": {"name": "t1"},
            "code": "y = 2",
            "label": {"forbidden": 0.2},
            "obs": {"forbidden": "unused"},
        },
        {
            "id": "c3",
            "run_id": "r2",
            "task": {"name": "t2"},
            "code": "z = 3",
            "label": {"forbidden": 0.3},
            "obs": {"forbidden": "unused"},
        },
    ]
    cards_path = tmp_path / "cards.jsonl"
    cards_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in cards),
        encoding="utf-8",
        newline="\n",
    )
    receipt_path = tmp_path / "receipt.json"
    receipt = {
        "status": "VERIFIED_BYTE_EXACT_CORPUS_REBUILD",
        "output": {
            "rows": 3,
            "bytes": cards_path.stat().st_size,
            "sha256": producer.sha256_file(cards_path),
        },
        "segmentation": {
            "runs": 2,
            "cross_segment_parents": 0,
            "mixed_task_segments": 0,
        },
    }
    receipt_path.write_text(
        json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    replacements = {
        "HISTORICAL_CARDS_PATH": "cards.jsonl",
        "HISTORICAL_CARDS_SHA256": producer.sha256_file(cards_path),
        "HISTORICAL_CARDS_BYTES": cards_path.stat().st_size,
        "HISTORICAL_RELEASE_RECEIPT_PATH": "receipt.json",
        "HISTORICAL_RELEASE_RECEIPT_SHA256": producer.sha256_file(receipt_path),
        "HISTORICAL_ENDPOINTS": 3,
        "HISTORICAL_RUNS": 2,
        "HISTORICAL_TASKS": 2,
    }
    for name, value in replacements.items():
        monkeypatch.setattr(schema, name, value)
    produced, produced_scope = producer.load_historical_release(tmp_path)
    verified, verified_scope = verifier.load_historical_release(tmp_path)
    assert produced_scope == verified_scope
    assert [(r.card_id, r.run_id, r.task, r.code) for r in produced] == [
        (r.card_id, r.run_id, r.task, r.code) for r in verified
    ]
    assert produced_scope["historical_label_or_observation_fields_used"] is False


def test_independent_verifier_does_not_import_new_producer() -> None:
    path = Path(verifier.__file__).resolve()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert (
        "phase1.audit_historical_release_future_identifier_erased_overlap"
        not in imported
    )


def test_security_contract_has_no_result_or_model_unlock() -> None:
    path = Path(__file__).parents[1] / "historical_release_future_identifier_erased_887_protocol_v1.json"
    protocol = json.loads(path.read_text(encoding="utf-8"))
    resources = protocol["resources"]
    assert resources["gpu_jobs"] == 0
    assert resources["api_calls"] == 0
    assert resources["model_fits"] == 0
    assert resources["base_llm_updates"] == 0
    assert "prediction" in " ".join(protocol["forbidden_inputs"])
    assert "prospective label" in " ".join(protocol["forbidden_inputs"])


def test_resource_revision_changes_only_timeout_and_records_blind_failure() -> None:
    root = Path(__file__).parents[1]
    original = json.loads(
        (root / "historical_release_future_identifier_erased_887_protocol_v1.json").read_text(
            encoding="utf-8"
        )
    )
    revised = json.loads(
        (
            root
            / "historical_release_future_identifier_erased_887_protocol_v1_resource_r2.json"
        ).read_text(encoding="utf-8")
    )
    producer.validate_protocol(revised)
    verifier.validate_protocol(revised)
    disclosure = revised["resource_revision_disclosure"]
    assert revised["resource_revision"] == 2
    assert disclosure["scientific_protocol_changed"] is False
    assert disclosure["failed_rc"] == 124
    assert disclosure["failed_result_file_created"] is False
    assert disclosure["failed_stderr_bytes"] == 0
    assert disclosure["failed_result_values_read"] is False
    assert original["resources"]["per_formal_command_timeout_seconds"] == 1800
    assert revised["resources"]["per_formal_command_timeout_seconds"] == 5400

    comparable = dict(revised)
    comparable.pop("resource_revision")
    comparable.pop("resource_revision_disclosure")
    comparable["frozen_at_utc"] = original["frozen_at_utc"]
    comparable["resources"] = dict(comparable["resources"])
    comparable["resources"]["per_formal_command_timeout_seconds"] = 1800
    assert comparable == original
