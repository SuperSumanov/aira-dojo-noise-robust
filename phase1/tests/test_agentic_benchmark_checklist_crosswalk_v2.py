from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path

import pytest

from phase1 import agentic_benchmark_checklist_crosswalk_v2_schema as schema
from phase1 import build_agentic_benchmark_checklist_crosswalk_v2 as builder
from phase1 import verify_agentic_benchmark_checklist_crosswalk_v2 as verifier


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = REPO_ROOT / schema.SOURCE_PATH


def item(payload: dict, item_id: str) -> dict:
    return next(value for value in payload["items"] if value["id"] == item_id)


def write(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def test_builder_and_non_importing_verifier_reconstruct_same_v2() -> None:
    built = builder.migrate(REPO_ROOT, SOURCE)
    assert built == verifier.expected_crosswalk(REPO_ROOT)
    assert "build_agentic_benchmark_checklist_crosswalk_v2" not in inspect.getsource(
        verifier
    )


def test_v1_is_only_a_human_template_and_access_attestation_is_not_inherited() -> None:
    payload = builder.migrate(REPO_ROOT, SOURCE)
    template = payload["source_v1_template"]
    assert template["used_for_human_item_text_and_conservative_statuses_only"] is True
    assert template["source_evidence_artifacts_opened"] is False
    assert template["source_access_attestation_inherited"] is False
    assert payload["access_attestation"] == schema.ACCESS_ATTESTATION


def test_removed_ids_and_withdrawn_paths_are_absent() -> None:
    payload = builder.migrate(REPO_ROOT, SOURCE)
    catalog = payload["evidence_catalog"]
    assert not set(schema.REMOVED_EVIDENCE_IDS).intersection(catalog)
    assert set(schema.ADDED_EVIDENCE).issubset(catalog)
    for evidence in catalog.values():
        assert not any(
            fragment in evidence["path"]
            for fragment in schema.FORBIDDEN_EVIDENCE_PATH_FRAGMENTS
        )
    for value in payload["items"]:
        assert not set(value["local_evidence_ids"]).intersection(
            schema.REMOVED_EVIDENCE_IDS
        )


def test_migration_does_not_upgrade_any_human_status() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    payload = builder.migrate(REPO_ROOT, SOURCE)
    assert {value["id"]: value["status"] for value in payload["items"]} == {
        value["id"]: value["status"] for value in source["items"]
    }
    assert payload["status_counts"] == {
        "PASS_LOCAL": 9,
        "PARTIAL": 9,
        "INHERITED_UPSTREAM": 5,
        "NOT_APPLICABLE": 1,
    }


def test_clean_replacements_are_all_referenced() -> None:
    payload = builder.migrate(REPO_ROOT, SOURCE)
    referenced = {
        evidence_id
        for value in payload["items"]
        for evidence_id in value["local_evidence_ids"]
    }
    assert referenced == set(payload["evidence_catalog"])
    assert set(schema.ADDED_EVIDENCE).issubset(referenced)
    assert "provenance_taint_registry" in item(payload, "T.10")["local_evidence_ids"]
    assert "opportunity_yield_audit" in item(payload, "R.9")["local_evidence_ids"]


def test_r13_remains_not_applicable_with_random_predictor_analogue() -> None:
    payload = builder.migrate(REPO_ROOT, SOURCE)
    value = item(payload, "R.13")
    assert value["status"] == "NOT_APPLICABLE"
    assert "analogue" in value["rationale"].lower()
    assert "literal pass" in value["rationale"].lower()


def test_independent_verifier_checks_complete_clean_crosswalk(tmp_path: Path) -> None:
    candidate = tmp_path / "crosswalk.json"
    write(candidate, builder.migrate(REPO_ROOT, SOURCE))
    receipt = verifier.verify_crosswalk(REPO_ROOT, candidate)
    assert receipt["status"] == (
        "INDEPENDENTLY_VERIFIED_CLEAN_PROVENANCE_ABC_CROSSWALK"
    )
    assert receipt["items_verified"] == 24
    assert receipt["evidence_files_verified"] == 29
    assert receipt["status_counts"] == {
        "PASS_LOCAL": 9,
        "PARTIAL": 9,
        "INHERITED_UPSTREAM": 5,
        "NOT_APPLICABLE": 1,
    }
    assert receipt["human_statuses_upgraded_during_migration"] is False
    assert receipt["source_v1_evidence_artifacts_opened"] is False
    assert receipt["withdrawn_artifacts_used_as_v2_evidence"] is False
    assert receipt["prediction_values_read_or_aggregated"] is False
    assert receipt["prospective_outcomes_read"] is False


def test_checked_in_crosswalk_matches_builder_when_present() -> None:
    checked = (
        REPO_ROOT
        / "phase1/results/agentic_benchmark_checklist_crosswalk_v2_20260826/crosswalk.json"
    )
    if not checked.exists():
        pytest.skip("formal v2 crosswalk has not been generated yet")
    assert json.loads(checked.read_text(encoding="utf-8")) == builder.migrate(
        REPO_ROOT, SOURCE
    )


def test_builder_rejects_unfrozen_source_path() -> None:
    with pytest.raises(builder.BuildError, match="frozen ABC crosswalk v1"):
        builder.migrate(
            REPO_ROOT,
            REPO_ROOT
            / "phase1/results/agentic_benchmark_checklist_crosswalk_v1_20260825/independent_verification.json",
        )


def test_verifier_rejects_status_promotion(tmp_path: Path) -> None:
    payload = copy.deepcopy(builder.migrate(REPO_ROOT, SOURCE))
    item(payload, "T.1")["status"] = "PASS_LOCAL"
    payload["status_counts"]["PARTIAL"] -= 1
    payload["status_counts"]["PASS_LOCAL"] += 1
    candidate = tmp_path / "promoted.json"
    write(candidate, payload)
    with pytest.raises(verifier.VerificationError, match="differs"):
        verifier.verify_crosswalk(REPO_ROOT, candidate)


def test_verifier_rejects_removed_evidence_reintroduction(tmp_path: Path) -> None:
    payload = copy.deepcopy(builder.migrate(REPO_ROOT, SOURCE))
    item(payload, "R.2")["local_evidence_ids"].append("evidence_index_v6")
    candidate = tmp_path / "reintroduced.json"
    write(candidate, payload)
    with pytest.raises(verifier.VerificationError, match="differs"):
        verifier.verify_crosswalk(REPO_ROOT, candidate)


def test_verifier_rejects_clean_evidence_hash_drift(tmp_path: Path) -> None:
    payload = copy.deepcopy(builder.migrate(REPO_ROOT, SOURCE))
    payload["evidence_catalog"]["evidence_index_v7"][
        "sha256_normalized_lf"
    ] = "0" * 64
    candidate = tmp_path / "hash-drift.json"
    write(candidate, payload)
    with pytest.raises(verifier.VerificationError, match="differs"):
        verifier.verify_crosswalk(REPO_ROOT, candidate)
