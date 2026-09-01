from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object: {path}")
    return value


def bind_inputs(repo_root: Path, protocol: dict[str, Any]) -> dict[str, dict[str, Any]]:
    bound: dict[str, dict[str, Any]] = {}
    root = repo_root.resolve()
    for spec in protocol["inputs"]:
        path = (root / spec["path"]).resolve()
        if not path.is_relative_to(root) or path.is_symlink() or not path.is_file():
            raise AssertionError(f"invalid input path: {spec['path']}")
        actual_sha = sha256(path)
        if actual_sha != spec["sha256"]:
            raise AssertionError(f"input hash drift: {spec['name']}")
        bound[spec["name"]] = load_json(path)
    if len(bound) != len(protocol["inputs"]):
        raise AssertionError("duplicate input name")
    return bound


def derive(protocol: dict[str, Any], data: dict[str, dict[str, Any]]) -> dict[str, Any]:
    retention = data["archive_granularity_retention_result"]
    retention_v = data["archive_granularity_retention_verification"]
    census = data["archive_rejection_support_census_result"]
    census_v = data["archive_rejection_support_census_verification"]
    incremental = data["incremental_archive_support_result"]
    incremental_v = data["incremental_archive_support_verification"]
    no_checkpoint = data["no_checkpoint_archive_summary"]
    no_checkpoint_v = data["no_checkpoint_archive_verification"]
    expected = protocol["expected_linkage"]

    assert retention["status"] == "ARCHIVE_GRANULARITY_RETENTION_STRONG"
    assert retention_v["status"] == "INDEPENDENT_ARCHIVE_GRANULARITY_RETENTION_PASS"
    assert retention_v["result_sha256"] == protocol["inputs"][0]["sha256"]
    assert retention_v["all_aggregate_fields_equal"] is True
    assert census["status"] == "ARCHIVE_REJECTION_SUPPORT_CENSUS_COMPLETE_PARTIALLY_PREDISCLOSED"
    assert census_v["status"] == "INDEPENDENT_ARCHIVE_REJECTION_SUPPORT_CENSUS_PASS"
    assert census_v["result_sha256"] == protocol["inputs"][2]["sha256"]
    assert census_v["all_result_fields_equal"] is True
    assert incremental["status"] == "INCREMENTAL_ARCHIVE_SUPPORT_ABSENT"
    assert incremental_v["status"] == "INDEPENDENT_INCREMENTAL_ARCHIVE_SUPPORT_PASS"
    assert incremental_v["result_sha256"] == protocol["inputs"][4]["sha256"]
    assert incremental_v["all_result_fields_equal"] is True
    assert no_checkpoint["status"] == "STRUCTURAL_NO_CHECKPOINT_REJECTION_FORMAL_PASS"
    assert no_checkpoint_v["status"] == "STRUCTURAL_NO_CHECKPOINT_REJECTION_INDEPENDENTLY_VERIFIED"
    assert no_checkpoint["independent_verification_sha256"] == protocol["inputs"][7]["sha256"]

    assert retention["input_bindings"]["latest_snapshot_sha256"] == expected["prior_snapshot_sha256"]
    assert census["input_bindings"]["prior_snapshot_sha256"] == expected["prior_snapshot_sha256"]
    assert census["input_bindings"]["current_snapshot_sha256"] == expected["current_snapshot_sha256"]
    assert incremental["input_bindings"]["current_snapshot_sha256"] == expected["current_snapshot_sha256"]
    assert census["input_bindings"]["latest_single_event_result_sha256"] == protocol["inputs"][4]["sha256"]
    assert census["input_bindings"]["latest_single_event_verification_sha256"] == protocol["inputs"][5]["sha256"]
    assert incremental["input_bindings"]["target_rejection_registry_sha256"] == expected["target_rejection_registry_sha256"]
    assert no_checkpoint["registry_sha256"] == expected["target_rejection_registry_sha256"]
    assert no_checkpoint_v["diagnostic_receipt_sha256"] == no_checkpoint["diagnostic_receipt_sha256"]

    competition_counts = census["competition_support_class_counts"]
    event_counts = census["event_support_class_counts"]
    reason_counts = census["reason_by_event_support_class"]["ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS"]
    distinct = competition_counts["distinct_rejected_competitions"]
    retained = competition_counts["PRIOR_ANCHOR_ELIGIBLE_SUPPORT"]
    no_support = competition_counts["NO_ACCEPTED_ARCHIVE_SUPPORT"]
    no_support_events = event_counts["NO_ACCEPTED_ARCHIVE_SUPPORT"]
    no_support_no_checkpoint_events = reason_counts["NO_ACCEPTED_ARCHIVE_SUPPORT"]
    assert distinct == expected["distinct_rejected_competitions"]
    assert retained == expected["prior_supported_competitions"]
    assert no_support == expected["no_accepted_support_competitions"]
    assert no_support_events == expected["no_support_events"]
    assert no_support_no_checkpoint_events == expected["no_support_no_checkpoint_events"]
    assert competition_counts["CURRENT_WINDOW_ELIGIBLE_SUPPORT"] == 0
    assert competition_counts["ACCEPTED_ARCHIVE_ONLY_NO_ELIGIBLE_SUPPORT"] == 0
    assert retained + no_support == distinct

    retained_detail = retention["retained_by_archive_granular_validation"]
    assert retained_detail["affected_competitions"] == retained
    assert retained_detail["affected_competitions_with_eligible_support"] == retained
    assert retention_v["recomputed_aggregate"]["retained_eligible_runs"] == retained_detail["eligible_runs"]
    assert retention_v["recomputed_aggregate"]["retained_eligible_endpoints"] == retained_detail["eligible_endpoints"]
    min_runs = retained_detail["anonymous_affected_task_distribution"]["eligible_runs"]["minimum"]
    min_endpoints = retained_detail["anonymous_affected_task_distribution"]["eligible_endpoints"]["minimum"]
    assert min_runs > 0 and min_endpoints > 0

    zero_support = incremental["anonymized_target_support"]["current_total"]
    assert zero_support == {
        "accepted_archives": 0,
        "eligible_endpoints": 0,
        "eligible_runs": 0,
        "physical_runs": 0,
    }
    assert incremental["decision"]["support_absent"] is True
    audit = no_checkpoint["archive_audit"]
    assert audit == no_checkpoint_v["archive_audit"]
    assert audit["discovered_run_roots"] > 0
    assert audit["checkpoint_runs"] == 0
    assert audit["live_only_runs_excluded"] == audit["discovered_run_roots"]

    elimination = no_support if audit["checkpoint_runs"] > 0 else 0
    invalid_only = no_support if audit["checkpoint_runs"] == 0 else 0
    accounted = retained + invalid_only
    assert accounted == distinct and elimination == 0

    return {
        "protocol": "structural-gate-utility-certificate-v1",
        "status": "OBSERVED_STRUCTURAL_GATE_SUPPORT_PRESERVING_DERIVED_CERTIFICATE",
        "analysis_class": protocol["analysis_class"],
        "input_bindings": {spec["name"]: {"path": spec["path"], "sha256": spec["sha256"]} for spec in protocol["inputs"]},
        "population": {
            "observed_archives": census["population"]["observed_archives"],
            "accepted_archives": census["population"]["accepted_archives"],
            "structural_rejected_archives": census["population"]["structural_rejected_archives"],
            "distinct_rejected_competitions": distinct,
            "eligible_runs": census["population"]["eligible_runs"],
            "eligible_endpoints": census["population"]["eligible_endpoints"],
        },
        "derived_partition": {
            "retained_usable_support_competitions": retained,
            "invalid_only_trigger_competitions": invalid_only,
            "accounted_affected_competitions": accounted,
            "observed_last_usable_support_elimination_competitions": elimination,
            "accounting_complete": accounted == distinct,
        },
        "retained_support": {
            "accepted_archives": retained_detail["accepted_archives"],
            "physical_runs": retained_detail["physical_runs"],
            "eligible_runs": retained_detail["eligible_runs"],
            "eligible_endpoints": retained_detail["eligible_endpoints"],
            "minimum_eligible_runs_per_retained_competition": min_runs,
            "minimum_eligible_endpoints_per_retained_competition": min_endpoints,
        },
        "unique_no_support_trigger": {
            "no_accepted_support_events": no_support_events,
            "no_support_no_checkpoint_events": no_support_no_checkpoint_events,
            "discovered_run_roots": audit["discovered_run_roots"],
            "checkpoint_runs": audit["checkpoint_runs"],
            "live_only_runs_excluded": audit["live_only_runs_excluded"],
            "target_registry_sha256": expected["target_rejection_registry_sha256"],
        },
        "decision": {
            "logical_gate_passed": True,
            "counts_as_distinct_claim_evidence": False,
            "derived_from_published_evidence_count": len(protocol["decision_rule"]["derives_from"]),
            "paper_safe_claim": "Within the settled 283-archive audit state, all seven structurally rejected competitions are accounted for: six retain accepted eligible support, while the only no-accepted-support competition is uniquely linked to an archive with zero checkpoint runs. No observed competition therefore shows evidence that structural validation removed its last usable checkpoint-derived support.",
        },
        "claim_boundary": protocol["claim_boundary"],
        "access_attestation": {
            "published_aggregate_json_only": True,
            "prospective_values_read": False,
            "raw_senior_archives_opened": False,
            "identity_values_emitted": False,
            "predictor_accuracy_scaling_search_utility_or_causal_effect_computed": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    protocol = load_json(args.protocol)
    assert protocol["protocol"] == "structural-gate-utility-certificate-v1"
    data = bind_inputs(args.repo_root, protocol)
    result = derive(protocol, data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


if __name__ == "__main__":
    main()
