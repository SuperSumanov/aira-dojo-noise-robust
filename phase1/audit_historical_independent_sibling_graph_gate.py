#!/usr/bin/env python3
"""Aggregate-only independence gate for a second historical sibling graph.

The audit reconstructs the already certified senior-0819 train sibling core,
removes every row sharing an endpoint/parent identity or physical run with v11
train:b0, and reports only aggregate support and irreversible fingerprints.
It never computes an acquisition curve or consumes orientation, outcomes, code,
predictions, runtime, or prospective values.
"""

from __future__ import annotations

import argparse
import collections
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

try:
    from phase1 import audit_senior_0819_verified_sibling_quarantine as quarantine
    from phase1 import audit_senior_0819_decision_relation_taxonomy as relation
except ImportError:  # direct execution from phase1/
    import audit_senior_0819_verified_sibling_quarantine as quarantine
    import audit_senior_0819_decision_relation_taxonomy as relation


PROTOCOL = "historical-independent-sibling-graph-gate-v1"
STATUS = (
    "FROZEN_AFTER_B0_ACQUISITION_RESULT_AND_BUDGET_VARIANT_OVERLAP_"
    "BEFORE_SENIOR0819_CROSSWALK"
)
RECEIPT = "historical-independent-sibling-graph-gate-receipt-v1"
COMMIT_RE = re.compile(r"[0-9a-f]{64}")


class IndependenceGateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise IndependenceGateError(message)


def sha256(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_payload(path: Path) -> bytes:
    require(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    return (
        path.read_bytes()
        .decode("utf-8")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .encode("utf-8")
    )


def load_json(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def fraction(text: str) -> Fraction:
    require(bool(re.fullmatch(r"[0-9]+/[1-9][0-9]*", text)), "invalid fraction")
    numerator, denominator = map(int, text.split("/"))
    return Fraction(numerator, denominator)


def ratio_payload(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def fingerprint(rows: Iterable[relation.DecisionRow]) -> str:
    records = []
    for row in rows:
        first, second = row.unordered
        records.append("\0".join((first, second, row.parent, row.task, row.first_run)))
    return hashlib.sha256(("\n".join(sorted(records)) + "\n").encode()).hexdigest()


def load_protocol(path: Path, expected_sha: str) -> dict[str, Any]:
    require(sha256(path) == expected_sha, "protocol SHA mismatch")
    value = load_json(path)
    require(value.get("protocol") == PROTOCOL, "protocol name")
    require(value.get("status") == STATUS, "protocol status")
    known = value["discovery_context_known_before_freeze"]
    require(known["v11_train_b0_low_budget_signal_seen"] is True, "discovery disclosure")
    require(known["budget_variants_rejected_as_independent_confirmation"] is True, "budget collision disclosure")
    require(known["senior_0819_crosswalk_or_residual_counts_seen"] is False, "crosswalk seen before freeze")
    require(value["fixed_candidate"]["test_rows_forbidden"] is True, "test prohibition")
    require(value["fixed_candidate"]["pair_orientation_used"] is False, "orientation drift")
    require(value["analysis"]["no_threshold_or_residual_rule_rescue_after_readout"] is True, "rescue drift")
    return value


def verify_published_dependencies(args: argparse.Namespace, protocol: dict[str, Any]) -> None:
    immutable = protocol["immutable_inputs"]
    lineage_path = Path(args.v11_lineage).resolve()
    lineage = load_json(lineage_path)
    lineage_binding = immutable["v11_lineage_certificate"]
    require(sha256(lineage_path) == lineage_binding["sha256"], "v11 lineage SHA")
    require(lineage["classification"] == lineage_binding["required_classification"], "v11 lineage classification")
    profile = lineage["scientific"]["set_profiles"]["train:b0"]
    require(profile["all_rows"]["pairs"] == 4263, "v11 lineage rows")
    require(profile["relation_counts"]["cross_run_declared_context"] == 0, "v11 cross-run")
    require(profile["relation_counts"]["same_run_declared_context_non_sibling"] == 0, "v11 non-sibling")

    result_path = Path(args.senior_quarantine_result).resolve()
    verification_path = Path(args.senior_quarantine_verification).resolve()
    manifest_path = Path(args.senior_quarantine_manifest).resolve()
    result_binding = immutable["senior_0819_quarantine_result"]
    require(sha256(result_path) == result_binding["sha256"], "senior result SHA")
    require(sha256(verification_path) == result_binding["verification_sha256"], "senior verification SHA")
    require(sha256(manifest_path) == result_binding["manifest_sha256"], "senior manifest SHA")
    result = load_json(result_path)
    verification = load_json(verification_path)
    require(result["classification"] == result_binding["required_classification"], "senior result classification")
    require(result["core_counts"] == {"total": 1270, "train": 952, "test": 318}, "senior core counts")
    require(verification["classification"] == result["classification"], "senior verifier classification")
    require(verification["all_aggregate_fields_equal"] is True, "senior verifier fields")
    require(verification["producer_result_sha256"] == result_binding["sha256"], "senior verifier binding")


def verify_security_receipt(path: Path, protocol: dict[str, Any]) -> dict[str, Any]:
    binding = protocol["immutable_inputs"]["senior_safe_cards"]
    require(sha256(path) == binding["credential_scan_receipt_sha256"], "security receipt SHA")
    value = load_json(path)
    require(value["status"] == "CREDENTIAL_SCAN_AND_REDACTION_PASS", "security receipt status")
    require(value["input_sha256"] == value["safe_sha256"] == binding["sha256"], "safe cards binding")
    require(value["remaining_credential_hits"] == 0, "remaining credential")
    require(value["private_key_markers"] == 0, "private key marker")
    require(value["json_parsed_before_scan"] is False, "parsed before credential scan")
    return value


def load_v11_graph(path: Path, protocol: dict[str, Any]) -> dict[str, set[Any]]:
    binding = protocol["immutable_inputs"]["v11_train_b0"]
    payload = normalized_payload(path)
    require(hashlib.sha256(payload).hexdigest() == binding["sha256"], "v11 normalized SHA")
    pairs: set[tuple[str, str]] = set()
    endpoints: set[str] = set()
    parents: set[str] = set()
    runs: set[str] = set()
    tasks: set[str] = set()
    for number, line in enumerate(payload.decode("utf-8").splitlines(), 1):
        require(bool(line), f"blank v11 row: {number}")
        row = json.loads(line)
        require(row.get("intask_split") == "train", f"v11 split: {number}")
        require(row.get("budget") == 0, f"v11 budget: {number}")
        values = [row.get(key) for key in ("better", "worse", "parent", "run_id", "task")]
        require(all(isinstance(value, str) and value for value in values), f"v11 field: {number}")
        better, worse, parent, run, task = values
        pair = tuple(sorted((better, worse)))
        require(pair[0] != pair[1] and pair not in pairs, f"v11 duplicate: {number}")
        pairs.add(pair)
        endpoints.update(pair)
        parents.add(parent)
        runs.add(run)
        tasks.add(task)
    require(len(pairs) == binding["rows"], "v11 row count")
    return {"pairs": pairs, "endpoints": endpoints, "parents": parents, "runs": runs, "tasks": tasks}


def strict_residual(
    rows: list[relation.DecisionRow],
    v11_identities: set[str],
    v11_runs: set[str],
) -> tuple[list[relation.DecisionRow], collections.Counter[str]]:
    kept: list[relation.DecisionRow] = []
    reasons: collections.Counter[str] = collections.Counter()
    for row in rows:
        endpoint_overlap = row.first in v11_identities or row.second in v11_identities
        parent_overlap = row.parent in v11_identities
        run_overlap = row.first_run in v11_runs
        mask = "".join(
            key for key, present in (("E", endpoint_overlap), ("P", parent_overlap), ("R", run_overlap)) if present
        )
        if mask:
            reasons[f"drop_mask_{mask}"] += 1
            reasons["rows_dropped"] += 1
            reasons["endpoint_overlap_rows"] += endpoint_overlap
            reasons["parent_overlap_rows"] += parent_overlap
            reasons["run_overlap_rows"] += run_overlap
        else:
            kept.append(row)
    reasons["rows_retained"] = len(kept)
    return kept, reasons


def row_sets(rows: Iterable[relation.DecisionRow]) -> dict[str, set[str] | set[tuple[str, str]]]:
    rows = list(rows)
    return {
        "pairs": {row.unordered for row in rows},
        "endpoints": {item for row in rows for item in row.unordered},
        "parents": {row.parent for row in rows},
        "runs": {row.first_run for row in rows},
        "tasks": {row.task for row in rows},
    }


def duplicate_profile(rows: list[relation.DecisionRow]) -> dict[str, int]:
    unordered = collections.Counter(row.unordered for row in rows)
    ordered: dict[tuple[str, str], set[tuple[str, str]]] = collections.defaultdict(set)
    for row in rows:
        ordered[row.unordered].add(row.ordered)
    return {
        "duplicate_unordered_pair_rows": sum(count - 1 for count in unordered.values()),
        "conflicting_orientation_unordered_pairs": sum(len(values) > 1 for values in ordered.values()),
    }


def classify(integrity: dict[str, bool], support: dict[str, bool]) -> str:
    if not all(integrity.values()):
        return "HISTORICAL_SENIOR0819_INDEPENDENT_SIBLING_GRAPH_INTEGRITY_FAIL"
    if not all(support.values()):
        return "HISTORICAL_SENIOR0819_INDEPENDENT_SIBLING_GRAPH_LIMITED_SUPPORT"
    return "HISTORICAL_SENIOR0819_INDEPENDENT_SIBLING_GRAPH_FEASIBLE"


def audit(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol).resolve()
    protocol = load_protocol(protocol_path, args.protocol_sha256)
    verify_published_dependencies(args, protocol)
    security = verify_security_receipt(Path(args.senior_security_receipt).resolve(), protocol)

    paths = {
        "cards": Path(args.senior_cards).resolve(),
        "run_split": Path(args.senior_run_split).resolve(),
        "decision": Path(args.senior_decision).resolve(),
    }
    immutable = protocol["immutable_inputs"]
    require(sha256(paths["cards"]) == immutable["senior_safe_cards"]["sha256"], "cards SHA")
    require(sha256(paths["run_split"]) == immutable["senior_run_split"]["sha256"], "run split SHA")
    require(sha256(paths["decision"]) == immutable["senior_decision"]["sha256"], "decision SHA")

    senior_protocol_path = Path(args.senior_quarantine_protocol).resolve()
    senior_protocol_binding = immutable["senior_0819_quarantine_protocol"]
    require(sha256(senior_protocol_path) == senior_protocol_binding["sha256"], "senior protocol SHA")
    senior_protocol = quarantine.load_protocol(senior_protocol_path, senior_protocol_binding["sha256"])
    all_runs, held_runs = relation.base.load_run_split(paths["run_split"], senior_protocol)
    cards, card_inventory = relation.base.load_cards(paths["cards"], all_runs)
    senior_rows, diagnostics = relation.read_rows(
        paths["decision"], cards, held_runs, senior_protocol["immutable_inputs"]["decision"]
    )
    all_core = [row for row in senior_rows if quarantine.is_core(row, held_runs)]
    train_core = [row for row in all_core if row.split == "train"]
    require(len(all_core) == 1270 and len(train_core) == 952, "senior core reconstruction")

    v11 = load_v11_graph(Path(args.v11_pairs).resolve(), protocol)
    v11_identities = set(v11["endpoints"]) | set(v11["parents"])
    residual, drop_reasons = strict_residual(train_core, v11_identities, set(v11["runs"]))
    candidate_sets = row_sets(train_core)
    residual_sets = row_sets(residual)
    duplicate = duplicate_profile(residual)
    residual_profile, residual_exacts = relation.profile(residual)
    residual_profile["parents"] = len(residual_sets["parents"])
    candidate_profile, _ = relation.profile(train_core)
    candidate_profile["parents"] = len(candidate_sets["parents"])

    crosswalk = {
        "exact_unordered_pairs": len(candidate_sets["pairs"] & v11["pairs"]),
        "endpoints": len(candidate_sets["endpoints"] & v11_identities),
        "parents": len(candidate_sets["parents"] & v11_identities),
        "physical_runs": len(candidate_sets["runs"] & v11["runs"]),
        "tasks_descriptive_only": len(candidate_sets["tasks"] & v11["tasks"]),
    }
    residual_overlap = {
        "exact_unordered_pairs": len(residual_sets["pairs"] & v11["pairs"]),
        "endpoints": len(residual_sets["endpoints"] & v11_identities),
        "parents": len(residual_sets["parents"] & v11_identities),
        "physical_runs": len(residual_sets["runs"] & v11["runs"]),
    }
    retention = Fraction(len(residual), len(train_core))
    frozen = protocol["support_gates"]
    support = {
        "minimum_residual_pair_rows": len(residual) >= frozen["minimum_residual_pair_rows"],
        "minimum_residual_pair_retention": retention >= fraction(frozen["minimum_residual_pair_retention"]),
        "minimum_residual_endpoints": residual_profile["endpoints"] >= frozen["minimum_residual_endpoints"],
        "minimum_residual_parents": residual_profile["parents"] >= frozen["minimum_residual_parents"],
        "minimum_residual_physical_runs": residual_profile["physical_runs"] >= frozen["minimum_residual_physical_runs"],
        "minimum_residual_tasks": residual_profile["tasks"] >= frozen["minimum_residual_tasks"],
        "maximum_single_residual_task_pair_share": (
            residual_exacts["maximum_single_task_pair_share"]
            <= fraction(frozen["maximum_single_residual_task_pair_share"])
        ),
        "maximum_single_residual_run_pair_share": (
            residual_exacts["maximum_single_run_pair_share"]
            <= fraction(frozen["maximum_single_residual_run_pair_share"])
        ),
    }
    integrity = {
        "all_inputs_and_parent_certificates_exact": True,
        "credential_scan_passes_before_safe_cards_parse": (
            security["remaining_credential_hits"] == security["private_key_markers"] == 0
        ),
        "v11_b0_rows_are_unique_train_budget0_lineage_direct": len(v11["pairs"]) == 4263,
        "senior_candidate_exactly_reproduces_952_train_core_rows": (
            len(train_core) == 952 and diagnostics["rows"] == 7644
        ),
        "residual_rule_is_exhaustive_and_deterministic": (
            len(residual) + drop_reasons["rows_dropped"] == len(train_core)
        ),
        "residual_has_no_v11_pair_endpoint_parent_or_run_overlap": all(
            value == 0 for value in residual_overlap.values()
        ),
        "residual_unordered_pair_duplicates_and_orientation_conflicts_zero": all(
            value == 0 for value in duplicate.values()
        ),
        "aggregate_only_and_no_identities_emitted": True,
    }

    return {
        "protocol": RECEIPT,
        "status": "HISTORICAL_INDEPENDENT_SIBLING_GRAPH_GATE_COMPLETE",
        "protocol_sha256": args.protocol_sha256,
        "inputs": {
            "v11_train_b0_normalized_sha256": immutable["v11_train_b0"]["sha256"],
            "senior_safe_cards_sha256": immutable["senior_safe_cards"]["sha256"],
            "senior_run_split_sha256": immutable["senior_run_split"]["sha256"],
            "senior_decision_sha256": immutable["senior_decision"]["sha256"],
        },
        "v11_graph_counts": {
            "pairs": len(v11["pairs"]),
            "endpoints": len(v11["endpoints"]),
            "parents": len(v11["parents"]),
            "physical_runs": len(v11["runs"]),
            "tasks": len(v11["tasks"]),
        },
        "senior_train_core_profile": candidate_profile,
        "candidate_to_v11_overlap": crosswalk,
        "strict_residual_drop_reasons": dict(sorted(drop_reasons.items())),
        "strict_residual_profile": residual_profile,
        "strict_residual_pair_retention": ratio_payload(retention),
        "strict_residual_overlap_recheck": residual_overlap,
        "strict_residual_duplicate_profile": duplicate,
        "identity_fingerprints": {
            "senior_train_core": fingerprint(train_core),
            "strict_residual": fingerprint(residual),
        },
        "integrity_gates": integrity,
        "support_gates": support,
        "classification": classify(integrity, support),
        "scope": {
            "population_qualification_only": True,
            "acquisition_curves_computed": False,
            "pair_orientation_gap_grade_code_prediction_runtime_used": False,
            "senior_test_rows_used": False,
            "prospective_first960_target300_values_read": False,
            "raw_senior_archives_opened": False,
            "identities_emitted": False,
            "gpu_api_model_fit_base_update": "0/0/0/0",
            "cards": card_inventory["cards"],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--v11-pairs", required=True)
    parser.add_argument("--v11-lineage", required=True)
    parser.add_argument("--senior-quarantine-protocol", required=True)
    parser.add_argument("--senior-quarantine-result", required=True)
    parser.add_argument("--senior-quarantine-verification", required=True)
    parser.add_argument("--senior-quarantine-manifest", required=True)
    parser.add_argument("--senior-security-receipt", required=True)
    parser.add_argument("--senior-cards", required=True)
    parser.add_argument("--senior-run-split", required=True)
    parser.add_argument("--senior-decision", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = audit(args)
    Path(args.output).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(result["classification"])


if __name__ == "__main__":
    main()
