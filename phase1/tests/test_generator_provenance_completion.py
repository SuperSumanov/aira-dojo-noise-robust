import json
from pathlib import Path

import pytest

from phase1.compose_generator_provenance_completion import compose
from phase1.verify_generator_provenance_completion import verify


SHA = "0" * 64


def synthetic() -> tuple[dict, dict, dict, dict, dict, dict]:
    hashes = {
        "protocol": SHA,
        "inventory": SHA,
        "inventory_verification": SHA,
        "archived_summary": SHA,
        "archived_verification": SHA,
    }
    protocol = {
        "protocol": "decision-corpus-generator-provenance-completion-v1",
        "version": 1,
        "status": "FROZEN_BEFORE_R6_FORMAL_PUBLIC_AGGREGATE_READ",
        "known_baseline": {
            "release_rows": 3,
            "provider_family_rows": 2,
            "configured_model_id_rows": 2,
            "exact_version_or_model_rows": 1,
            "version_boundary_ambiguous_rows": 1,
            "unmapped_rows": 1,
            "unmapped_batches": 1,
            "inventory_sha256": SHA,
            "inventory_verification_sha256": SHA,
        },
        "completion_rule": {
            "post_result_rule_change_allowed": False,
            "provider_family_rows_change_allowed": False,
            "service_provider_or_contract_entity_inference_from_model_id_allowed": False,
        },
    }
    release = {
        "version": "v-test",
        "release_commit": "a" * 40,
        "batch_lock_sha256": "b" * 64,
        "batches": 3,
        "rows": 3,
    }
    coverage = {
        "mapped_batches": 2,
        "mapped_rows": 2,
        "exact_version_or_model_batches": 1,
        "exact_version_or_model_rows": 1,
        "version_boundary_ambiguous_batches": 1,
        "version_boundary_ambiguous_rows": 1,
        "unmapped_batches": 1,
        "unmapped_rows": 1,
    }
    inventory = {
        "protocol": "release-provider-provenance-inventory-v1",
        "status": "PARTIAL_NOT_RELEASE_CLEARED",
        "release": release,
        "coverage": coverage,
        "batches": [
            {"file": "exact.jsonl", "rows": 1, "annotation_status": "annotated-model"},
            {"file": "ambiguous.jsonl", "rows": 1, "annotation_status": "version-boundary-ambiguous"},
            {"file": "unmapped.jsonl", "rows": 1, "annotation_status": "unmapped"},
        ],
        "unmapped_batch_files": ["unmapped.jsonl"],
    }
    inventory_verification = {
        "protocol": "release-provider-provenance-independent-verification-v1",
        "status": "PASS",
        "inventory_sha256": SHA,
        "coverage": coverage,
        "release": release,
    }
    archived_coverage = {
        "batches": 1,
        "target_rows": 1,
        "exact_rows": 1,
        "ambiguous_rows": 0,
        "missing_rows": 0,
    }
    archived = {
        "protocol": "archived-card-generator-provenance-v1",
        "status": "COMPLETE_EXACT",
        "coverage": archived_coverage,
        "model_counts": {"model-from-config": 1},
        "batches": [
            {
                "batch": "unmapped.jsonl",
                "target_rows": 1,
                "exact_rows": 1,
                "ambiguous_rows": 0,
                "missing_rows": 0,
                "model_counts": {"model-from-config": 1},
            }
        ],
    }
    archived_verification = {
        "protocol": "archived-card-generator-provenance-independent-verifier-v1",
        "status": "PASS",
        "summary_sha256": SHA,
        "coverage": archived_coverage,
        "model_counts": {"model-from-config": 1},
    }
    return protocol, inventory, inventory_verification, archived, archived_verification, hashes


def test_completion_keeps_model_provider_and_version_axes_separate() -> None:
    protocol, inventory, inventory_verification, archived, archived_verification, hashes = synthetic()
    result = compose(protocol, inventory, inventory_verification, archived, archived_verification, hashes)
    assert result["coverage"]["configured_model_id_rows"] == 3
    assert result["coverage"]["exact_version_or_model_rows"] == 2
    assert result["coverage"]["version_boundary_ambiguous_rows"] == 1
    assert result["coverage"]["provider_family_rows"] == 2
    assert result["coverage"]["provider_family_unresolved_rows"] == 1
    assert result["interpretation_boundary"]["configured_model_id_identifies_provider_or_contract_entity"] is False
    receipt = verify(
        protocol, inventory, inventory_verification, archived, archived_verification,
        hashes, result, SHA,
    )
    assert receipt["status"] == "PASS_EXACT_RECONSTRUCTION"


def test_claimed_provider_inflation_is_rejected() -> None:
    protocol, inventory, inventory_verification, archived, archived_verification, hashes = synthetic()
    result = compose(protocol, inventory, inventory_verification, archived, archived_verification, hashes)
    result["coverage"]["provider_family_rows"] = 3
    with pytest.raises(ValueError, match="claimed coverage"):
        verify(
            protocol, inventory, inventory_verification, archived, archived_verification,
            hashes, result, SHA,
        )


def test_incomplete_archived_mapping_fails_closed() -> None:
    protocol, inventory, inventory_verification, archived, archived_verification, hashes = synthetic()
    archived["batches"][0]["exact_rows"] = 0
    with pytest.raises(Exception, match="exact rows"):
        compose(protocol, inventory, inventory_verification, archived, archived_verification, hashes)


def test_real_protocol_freezes_provider_and_version_nonimplications() -> None:
    value = json.loads(
        (Path(__file__).resolve().parents[1] / "generator_provenance_completion_protocol_v1.json")
        .read_text(encoding="utf-8")
    )
    assert value["status"] == "FROZEN_BEFORE_R6_FORMAL_PUBLIC_AGGREGATE_READ"
    assert value["known_baseline"]["unmapped_rows"] == 6111
    assert value["completion_rule"]["provider_family_rows_change_allowed"] is False
    assert value["completion_rule"]["version_boundary_ambiguous_rows_change_allowed"] is False
    assert value["completion_rule"]["service_provider_or_contract_entity_inference_from_model_id_allowed"] is False
