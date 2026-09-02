from __future__ import annotations

import json
from pathlib import Path


PHASE1 = Path(__file__).resolve().parents[1]
ROOT = PHASE1.parent


def load_json(name: str) -> dict:
    return json.loads((PHASE1 / name).read_text(encoding="utf-8"))


def manifest() -> dict:
    return load_json("release_gate_action_manifest_v11_draft.json")


def test_top_level_remains_fail_closed_and_non_scientific() -> None:
    value = manifest()
    assert value["status"] == "INTERNAL_DRAFT_NOT_RELEASE_CLEARED"
    assert value["legal_advice"] is False
    assert value["release_clearance"] is False
    assert value["counts_as_distinct_claim_evidence"] is False
    assert value["source_release"] == {
        "version": "v11",
        "cards": 16012,
        "tasks": 25,
        "competition_data_redistributed_bytes": 0,
    }


def test_content_counts_are_bound_to_existing_receipts() -> None:
    value = manifest()["content_gate"]
    scan = load_json("release_content_scan_postflight_receipt_20260902.json")
    tier = load_json("release_content_tier_postflight_receipt_20260902.json")
    assert value["tasks_scanned"] == scan["tasks_scanned"] == 23
    assert value["tasks_total"] == scan["tasks_total"] == 25
    assert value["tasks_unscanned"] == scan["tasks_unscanned"] == 2
    assert value["candidate_patterns"] == scan["candidate_patterns"] == 3766518
    assert value["matched_patterns"] == scan["matched_patterns"] == 173
    assert value["affected_cards"] == scan["affected_card_sum_across_tasks"] == 419
    assert value["content_review_eligible_cards"] == tier["content_review_eligible_cards"] == 15174
    assert value["structure_only_cards"] == tier["structure_only_cards"] == 838
    assert value["structure_only_due_matched_pattern"] == tier["structure_only_due_matched_pattern"] == 419
    assert value["structure_only_due_unscanned_task"] == tier["structure_only_due_unscanned_task"] == 419
    assert scan["release_clearance"] is tier["release_clearance"] is False
    assert value["exact_final_release_candidate_scan_complete"] is False
    assert value["public_release_cleared"] is False


def test_competition_rule_counts_are_bound_to_draft_inventory() -> None:
    value = manifest()["competition_rules_gate"]
    rules = load_json("licenses_v11_draft.json")
    aggregate = rules["aggregate"]
    assert value["status"] == rules["status"]
    for key in (
        "rules_pages_visible",
        "detailed_standard",
        "compact_legacy",
        "detailed_legacy_custom",
        "explicit_private_sharing_prohibition",
        "public_forum_sharing_statement",
        "explicit_osi_no_commercial_limit",
        "exact_standard_data_nonredistribution",
    ):
        assert value[key] == aggregate[key]
    assert (value["detailed_standard"], value["compact_legacy"], value["detailed_legacy_custom"]) == (16, 7, 2)
    assert value["missing_clause_means_permission"] is False
    assert value["public_release_cleared"] is False


def test_provider_counts_are_bound_to_terms_and_completion_receipts() -> None:
    value = manifest()["provider_gate"]
    terms = load_json("provider_terms_v11_draft.json")
    completion = load_json("generator_provenance_completion_postflight_receipt_20260902.json")
    inventory = terms["inventory"]
    coverage = completion["coverage"]
    assert value["status"] == terms["status"]
    assert (value["release_batches"], value["release_rows"]) == (29, 16012)
    assert value["configured_model_batches"] == inventory["configured_model_batches"] == 29
    assert value["configured_model_rows"] == coverage["configured_model_id_rows"] == 16012
    assert value["exact_version_or_model_rows"] == coverage["exact_version_or_model_rows"] == 15905
    assert value["version_boundary_ambiguous_rows"] == coverage["version_boundary_ambiguous_rows"] == 107
    assert value["provider_family_batches"] == inventory["mapped_batches"] == 24
    assert value["provider_family_rows"] == coverage["provider_family_rows"] == 9901
    assert value["provider_unresolved_batches"] == inventory["unmapped_batches"] == 5
    assert value["provider_unresolved_rows"] == coverage["provider_family_unresolved_rows"] == 6111
    qwen = next(provider for provider in terms["providers"] if provider["provider"] == "Alibaba Cloud Model Studio / Bailian")
    assert (value["qwen_collection_time_terms_blocked_batches"], value["qwen_collection_time_terms_blocked_rows"]) == (qwen["batches"], qwen["rows"]) == (2, 44)
    assert value["configured_model_id_identifies_provider_or_contract_entity"] is False
    assert value["public_release_cleared"] is False


def test_croissant_fields_remain_blocked_and_uninvented() -> None:
    value = manifest()["publication_metadata_gate"]
    config = load_json("croissant_release_config_v11.template.json")
    expected = ["license", "url", "creator", "datePublished", "contentBaseUrl"]
    assert value["status"] == "ENGINEERING_READY_PUBLICATION_FIELDS_BLOCKED"
    assert value["blocked_fields"] == expected
    assert config == {
        "license": None,
        "url": None,
        "creator": [],
        "datePublished": None,
        "contentBaseUrl": None,
    }
    assert value["final_jsonld_generated"] is False
    assert value["public_release_cleared"] is False


def test_no_candidate_payload_class_is_mislabeled_as_cleared() -> None:
    classes = {item["id"]: item for item in manifest()["candidate_payload_classes"]}
    assert classes["historical_structure_only"]["cards"] == 838
    assert classes["historical_content_review_eligible"]["cards"] == 15174
    assert classes["historical_content_review_eligible"]["means_clean_or_licensed"] is False
    assert classes["prospective_first960"]["status"] == "SEALED"
    assert classes["prospective_first960"]["labels_outcomes_predictions_identities_utility_read_allowed"] is False
    for item in classes.values():
        clearance_key = "public_release_cleared" if "public_release_cleared" in item else "dataset_payload_release_cleared"
        assert item[clearance_key] is False


def test_roles_sequence_and_evidence_paths_are_complete() -> None:
    value = manifest()
    roles = {item["owner_role"] for item in value["responsibility_matrix"]}
    assert roles == {
        "historical_data_curator_or_senior",
        "authorized_content_security_reviewer",
        "institutional_legal_reviewer",
        "project_governance_owner",
        "release_engineer",
    }
    assert len(value["ordered_release_sequence"]) == 8
    assert value["ordered_release_sequence"][-1] == "run_final_release_postflight"
    for relative in value["evidence_paths"]:
        assert (ROOT / relative).is_file(), relative


def test_human_packet_preserves_the_same_boundaries() -> None:
    packet = (PHASE1 / "RELEASE_GATE_ACTION_PACKET_V11_20260902.md").read_text(encoding="utf-8")
    for required in (
        "INTERNAL_REVIEW_PACKET_NOT_LEGAL_ADVICE_NOT_RELEASE_CLEARANCE",
        "15,174",
        "838",
        "173 matched patterns",
        "five batches / 6,111 rows",
        "Competition data remains zero-byte redistributed",
        "This packet reduces coordination risk; it is not a scientific positive result",
    ):
        assert required in packet
