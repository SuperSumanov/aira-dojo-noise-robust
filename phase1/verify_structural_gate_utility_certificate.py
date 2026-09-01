from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(path)
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)

    root = args.repo_root.resolve()
    protocol = read_object(args.protocol)
    candidate = read_object(args.candidate)
    inputs: dict[str, dict[str, Any]] = {}
    for spec in protocol["inputs"]:
        path = (root / spec["path"]).resolve()
        assert path.is_relative_to(root) and path.is_file() and not path.is_symlink()
        assert digest(path) == spec["sha256"]
        assert spec["name"] not in inputs
        inputs[spec["name"]] = read_object(path)

    retention = inputs["archive_granularity_retention_result"]
    retention_v = inputs["archive_granularity_retention_verification"]
    census = inputs["archive_rejection_support_census_result"]
    census_v = inputs["archive_rejection_support_census_verification"]
    incremental = inputs["incremental_archive_support_result"]
    incremental_v = inputs["incremental_archive_support_verification"]
    no_checkpoint = inputs["no_checkpoint_archive_summary"]
    no_checkpoint_v = inputs["no_checkpoint_archive_verification"]
    expected = protocol["expected_linkage"]

    assert retention_v["result_sha256"] == protocol["inputs"][0]["sha256"]
    assert census_v["result_sha256"] == protocol["inputs"][2]["sha256"]
    assert incremental_v["result_sha256"] == protocol["inputs"][4]["sha256"]
    assert no_checkpoint["independent_verification_sha256"] == protocol["inputs"][7]["sha256"]
    assert retention_v["all_aggregate_fields_equal"] is True
    assert census_v["all_result_fields_equal"] is True
    assert incremental_v["all_result_fields_equal"] is True
    assert census["input_bindings"]["latest_single_event_result_sha256"] == protocol["inputs"][4]["sha256"]
    assert census["input_bindings"]["latest_single_event_verification_sha256"] == protocol["inputs"][5]["sha256"]
    assert incremental["input_bindings"]["target_rejection_registry_sha256"] == expected["target_rejection_registry_sha256"]
    assert no_checkpoint["registry_sha256"] == expected["target_rejection_registry_sha256"]
    assert no_checkpoint_v["archive_audit"] == no_checkpoint["archive_audit"]

    counts = census["competition_support_class_counts"]
    retained = counts["PRIOR_ANCHOR_ELIGIBLE_SUPPORT"]
    absent = counts["NO_ACCEPTED_ARCHIVE_SUPPORT"]
    distinct = counts["distinct_rejected_competitions"]
    assert (retained, absent, distinct) == (6, 1, 7)
    assert census["event_support_class_counts"]["NO_ACCEPTED_ARCHIVE_SUPPORT"] == 1
    assert census["reason_by_event_support_class"]["ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS"]["NO_ACCEPTED_ARCHIVE_SUPPORT"] == 1
    detail = retention["retained_by_archive_granular_validation"]
    assert detail["affected_competitions"] == retained
    assert detail["affected_competitions_with_eligible_support"] == retained
    assert detail["anonymous_affected_task_distribution"]["eligible_runs"]["minimum"] == 4
    assert detail["anonymous_affected_task_distribution"]["eligible_endpoints"]["minimum"] == 50
    assert incremental["anonymized_target_support"]["current_total"]["eligible_runs"] == 0
    audit = no_checkpoint["archive_audit"]
    assert audit["checkpoint_runs"] == 0
    assert audit["discovered_run_roots"] == audit["live_only_runs_excluded"] == 2

    partition = candidate["derived_partition"]
    expected_partition = {
        "accounted_affected_competitions": 7,
        "accounting_complete": True,
        "invalid_only_trigger_competitions": 1,
        "observed_last_usable_support_elimination_competitions": 0,
        "retained_usable_support_competitions": 6,
    }
    assert partition == expected_partition
    assert candidate["retained_support"] == {
        "accepted_archives": 20,
        "eligible_endpoints": 2558,
        "eligible_runs": 92,
        "minimum_eligible_endpoints_per_retained_competition": 50,
        "minimum_eligible_runs_per_retained_competition": 4,
        "physical_runs": 94,
    }
    assert candidate["decision"]["logical_gate_passed"] is True
    assert candidate["decision"]["counts_as_distinct_claim_evidence"] is False
    assert candidate["decision"]["derived_from_published_evidence_count"] == 4
    assert candidate["access_attestation"]["published_aggregate_json_only"] is True
    assert candidate["access_attestation"]["prospective_values_read"] is False
    assert candidate["access_attestation"]["raw_senior_archives_opened"] is False
    assert candidate["access_attestation"]["identity_values_emitted"] is False
    assert candidate["access_attestation"]["gpu_paid_api_model_fit_base_update"] == "0/0/0/0"

    verification = {
        "protocol": "independent-structural-gate-utility-certificate-v1",
        "status": "INDEPENDENT_STRUCTURAL_GATE_UTILITY_CERTIFICATE_PASS",
        "candidate_sha256": digest(args.candidate),
        "producer_imported": False,
        "all_derived_fields_equal": True,
        "distinct_rejected_competitions": distinct,
        "retained_usable_support_competitions": retained,
        "invalid_only_trigger_competitions": absent,
        "observed_last_usable_support_elimination_competitions": 0,
        "counts_as_distinct_claim_evidence": False,
        "prospective_values_read": False,
        "raw_senior_archives_opened": False,
        "identity_values_emitted": False,
        "gpu_paid_api_model_fit_base_update": "0/0/0/0",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(verification, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


if __name__ == "__main__":
    main()
