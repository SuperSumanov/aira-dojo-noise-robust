from __future__ import annotations

import ast
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from phase1 import build_structural_gate_utility_certificate as builder


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = ROOT / "phase1/structural_gate_utility_certificate_v1.json"
BUILDER = ROOT / "phase1/build_structural_gate_utility_certificate.py"
VERIFIER = ROOT / "phase1/verify_structural_gate_utility_certificate.py"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def protocol_and_data() -> tuple[dict, dict[str, dict]]:
    protocol = load(PROTOCOL_PATH)
    data = {
        spec["name"]: load(ROOT / spec["path"])
        for spec in protocol["inputs"]
    }
    return protocol, data


def run_pair(tmp_path: Path) -> tuple[Path, Path]:
    result = tmp_path / "result.json"
    verification = tmp_path / "verification.json"
    subprocess.run(
        [
            sys.executable,
            str(BUILDER),
            "--repo-root",
            str(ROOT),
            "--protocol",
            str(PROTOCOL_PATH),
            "--output",
            str(result),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            "--repo-root",
            str(ROOT),
            "--protocol",
            str(PROTOCOL_PATH),
            "--candidate",
            str(result),
            "--output",
            str(verification),
        ],
        check=True,
    )
    return result, verification


def test_protocol_and_all_eight_public_inputs_are_hash_bound() -> None:
    protocol = load(PROTOCOL_PATH)
    assert hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest() == (
        "bb4091ff0585c288d0fb99614125e82148338d6871872ae023a1c41913c60308"
    )
    assert len(protocol["inputs"]) == 8
    assert len({spec["name"] for spec in protocol["inputs"]}) == 8
    for spec in protocol["inputs"]:
        assert hashlib.sha256((ROOT / spec["path"]).read_bytes()).hexdigest() == spec["sha256"]
    assert protocol["decision_rule"]["no_tunable_threshold"] is True
    assert protocol["decision_rule"]["counts_as_distinct_claim_evidence"] is False


def test_certificate_reports_complete_seven_competition_partition(tmp_path: Path) -> None:
    result, verification = run_pair(tmp_path)
    value = load(result)
    assert value["status"] == "OBSERVED_STRUCTURAL_GATE_SUPPORT_PRESERVING_DERIVED_CERTIFICATE"
    assert value["derived_partition"] == {
        "accounted_affected_competitions": 7,
        "accounting_complete": True,
        "invalid_only_trigger_competitions": 1,
        "observed_last_usable_support_elimination_competitions": 0,
        "retained_usable_support_competitions": 6,
    }
    checked = load(verification)
    assert checked["status"] == "INDEPENDENT_STRUCTURAL_GATE_UTILITY_CERTIFICATE_PASS"
    assert checked["candidate_sha256"] == hashlib.sha256(result.read_bytes()).hexdigest()
    assert checked["all_derived_fields_equal"] is True
    assert checked["producer_imported"] is False


def test_certificate_preserves_support_depth_and_zero_checkpoint_trigger(tmp_path: Path) -> None:
    result, _ = run_pair(tmp_path)
    value = load(result)
    assert value["retained_support"] == {
        "accepted_archives": 20,
        "eligible_endpoints": 2558,
        "eligible_runs": 92,
        "minimum_eligible_endpoints_per_retained_competition": 50,
        "minimum_eligible_runs_per_retained_competition": 4,
        "physical_runs": 94,
    }
    trigger = value["unique_no_support_trigger"]
    assert trigger["no_accepted_support_events"] == 1
    assert trigger["no_support_no_checkpoint_events"] == 1
    assert trigger["discovered_run_roots"] == 2
    assert trigger["checkpoint_runs"] == 0
    assert trigger["live_only_runs_excluded"] == 2


def test_logical_derivation_fails_if_unique_trigger_has_checkpoint_run() -> None:
    protocol, data = protocol_and_data()
    changed = copy.deepcopy(data)
    changed["no_checkpoint_archive_summary"]["archive_audit"]["checkpoint_runs"] = 1
    changed["no_checkpoint_archive_verification"]["archive_audit"]["checkpoint_runs"] = 1
    with pytest.raises(AssertionError):
        builder.derive(protocol, changed)


def test_logical_derivation_fails_if_cross_artifact_linkage_drifts() -> None:
    protocol, data = protocol_and_data()
    changed = copy.deepcopy(data)
    changed["archive_rejection_support_census_result"]["input_bindings"][
        "latest_single_event_result_sha256"
    ] = "0" * 64
    with pytest.raises(AssertionError):
        builder.derive(protocol, changed)


def test_builder_and_verifier_are_deterministic_and_no_overwrite(tmp_path: Path) -> None:
    first_result, first_verification = run_pair(tmp_path / "first")
    second_result, second_verification = run_pair(tmp_path / "second")
    assert first_result.read_bytes() == second_result.read_bytes()
    assert first_verification.read_bytes() == second_verification.read_bytes()
    completed = subprocess.run(
        [
            sys.executable,
            str(BUILDER),
            "--repo-root",
            str(ROOT),
            "--protocol",
            str(PROTOCOL_PATH),
            "--output",
            str(first_result),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "FileExistsError" in completed.stderr


def test_independent_verifier_does_not_import_producer() -> None:
    tree = ast.parse(VERIFIER.read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert not any("build_structural_gate_utility_certificate" in name for name in imported)


def test_output_is_explicitly_derived_and_identity_erased(tmp_path: Path) -> None:
    result, verification = run_pair(tmp_path)
    value = load(result)
    assert value["decision"]["counts_as_distinct_claim_evidence"] is False
    assert value["decision"]["derived_from_published_evidence_count"] == 4
    assert value["access_attestation"]["published_aggregate_json_only"] is True
    assert value["access_attestation"]["identity_values_emitted"] is False
    assert value["access_attestation"]["prospective_values_read"] is False
    assert value["access_attestation"]["raw_senior_archives_opened"] is False
    assert value["access_attestation"]["gpu_paid_api_model_fit_base_update"] == "0/0/0/0"
    assert load(verification)["counts_as_distinct_claim_evidence"] is False
