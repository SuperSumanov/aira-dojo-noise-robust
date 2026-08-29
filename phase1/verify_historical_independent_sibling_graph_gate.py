#!/usr/bin/env python3
"""Independent verifier for the historical sibling-graph qualification gate.

The verifier deliberately does not import the gate producer.  It rebuilds the
senior-0819 verified direct-sibling population with the previously independent
Card/decision decoder, parses the v11 graph separately, applies the frozen
identity/run exclusion rule, and compares every aggregate field exactly.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

try:
    from phase1 import verify_senior_0819_verified_sibling_quarantine as senior
except ImportError:  # direct execution from phase1/
    import verify_senior_0819_verified_sibling_quarantine as senior


PROTOCOL = "historical-independent-sibling-graph-gate-v1"
STATUS = (
    "FROZEN_AFTER_B0_ACQUISITION_RESULT_AND_BUDGET_VARIANT_OVERLAP_"
    "BEFORE_SENIOR0819_CROSSWALK"
)
RECEIPT = "historical-independent-sibling-graph-gate-receipt-v1"


class IndependentGraphGateError(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise IndependentGraphGateError(message)


def digest(path: Path) -> str:
    check(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            value.update(block)
    return value.hexdigest()


def object_json(path: Path) -> dict[str, Any]:
    check(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(value, dict), f"JSON object required: {path}")
    return value


def normalized_payload(path: Path) -> bytes:
    check(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    return (
        path.read_bytes()
        .decode("utf-8")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .encode("utf-8")
    )


def frozen_fraction(text: str) -> Fraction:
    check(bool(re.fullmatch(r"[0-9]+/[1-9][0-9]*", text)), "invalid fraction")
    numerator, denominator = text.split("/")
    return Fraction(int(numerator), int(denominator))


def ratio_payload(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal_17g": format(float(value), ".17g"),
    }


def load_protocol(path: Path, expected_sha256: str) -> dict[str, Any]:
    check(digest(path) == expected_sha256, "protocol SHA mismatch")
    value = object_json(path)
    check(value.get("protocol") == PROTOCOL, "protocol name")
    check(value.get("status") == STATUS, "protocol status")
    known = value["discovery_context_known_before_freeze"]
    check(known["v11_train_b0_low_budget_signal_seen"] is True, "discovery disclosure")
    check(
        known["budget_variants_rejected_as_independent_confirmation"] is True,
        "budget collision disclosure",
    )
    check(
        known["senior_0819_crosswalk_or_residual_counts_seen"] is False,
        "crosswalk seen before freeze",
    )
    candidate = value["fixed_candidate"]
    check(candidate["test_rows_forbidden"] is True, "test prohibition")
    check(candidate["pair_orientation_used"] is False, "orientation drift")
    check(
        value["analysis"]["no_threshold_or_residual_rule_rescue_after_readout"] is True,
        "rescue drift",
    )
    return value


def verify_parent_certificates(args: argparse.Namespace, protocol: dict[str, Any]) -> None:
    immutable = protocol["immutable_inputs"]

    lineage_path = Path(args.v11_lineage).resolve()
    lineage_binding = immutable["v11_lineage_certificate"]
    check(digest(lineage_path) == lineage_binding["sha256"], "v11 lineage SHA")
    lineage = object_json(lineage_path)
    check(
        lineage["classification"] == lineage_binding["required_classification"],
        "v11 lineage classification",
    )
    profile = lineage["scientific"]["set_profiles"]["train:b0"]
    check(profile["all_rows"]["pairs"] == 4263, "v11 lineage rows")
    check(profile["relation_counts"]["cross_run_declared_context"] == 0, "v11 cross-run")
    check(
        profile["relation_counts"]["same_run_declared_context_non_sibling"] == 0,
        "v11 non-sibling",
    )

    result_binding = immutable["senior_0819_quarantine_result"]
    result_path = Path(args.senior_quarantine_result).resolve()
    verification_path = Path(args.senior_quarantine_verification).resolve()
    manifest_path = Path(args.senior_quarantine_manifest).resolve()
    check(digest(result_path) == result_binding["sha256"], "senior result SHA")
    check(
        digest(verification_path) == result_binding["verification_sha256"],
        "senior verification SHA",
    )
    check(digest(manifest_path) == result_binding["manifest_sha256"], "senior manifest SHA")
    result = object_json(result_path)
    verification = object_json(verification_path)
    check(
        result["classification"] == result_binding["required_classification"],
        "senior result classification",
    )
    check(result["core_counts"] == {"total": 1270, "train": 952, "test": 318}, "core counts")
    check(verification["classification"] == result["classification"], "verifier class")
    check(verification["all_aggregate_fields_equal"] is True, "verifier equality")
    check(
        verification["producer_result_sha256"] == result_binding["sha256"],
        "verifier binding",
    )


def verify_security_receipt(path: Path, protocol: dict[str, Any]) -> dict[str, Any]:
    binding = protocol["immutable_inputs"]["senior_safe_cards"]
    check(
        digest(path) == binding["credential_scan_receipt_sha256"],
        "security receipt SHA",
    )
    value = object_json(path)
    check(value["status"] == "CREDENTIAL_SCAN_AND_REDACTION_PASS", "security status")
    check(value["input_sha256"] == value["safe_sha256"] == binding["sha256"], "safe binding")
    check(value["remaining_credential_hits"] == 0, "remaining credential")
    check(value["private_key_markers"] == 0, "private key marker")
    check(value["json_parsed_before_scan"] is False, "parsed before scan")
    return value


def load_v11_graph(path: Path, protocol: dict[str, Any]) -> dict[str, set[Any]]:
    binding = protocol["immutable_inputs"]["v11_train_b0"]
    payload = normalized_payload(path)
    check(hashlib.sha256(payload).hexdigest() == binding["sha256"], "v11 normalized SHA")
    pairs: set[tuple[str, str]] = set()
    endpoints: set[str] = set()
    parents: set[str] = set()
    runs: set[str] = set()
    tasks: set[str] = set()
    for number, line in enumerate(payload.decode("utf-8").splitlines(), 1):
        check(bool(line), f"blank v11 row: {number}")
        row = json.loads(line)
        check(isinstance(row, dict), f"v11 object: {number}")
        check(row.get("intask_split") == "train", f"v11 split: {number}")
        check(row.get("budget") == 0, f"v11 budget: {number}")
        values = [row.get(key) for key in ("better", "worse", "parent", "run_id", "task")]
        check(
            all(isinstance(value, str) and value for value in values),
            f"v11 field: {number}",
        )
        better, worse, parent, run, task = values
        pair = tuple(sorted((better, worse)))
        check(pair[0] != pair[1] and pair not in pairs, f"v11 duplicate: {number}")
        pairs.add(pair)
        endpoints.update(pair)
        parents.add(parent)
        runs.add(run)
        tasks.add(task)
    check(len(pairs) == binding["rows"], "v11 row count")
    return {
        "pairs": pairs,
        "endpoints": endpoints,
        "parents": parents,
        "runs": runs,
        "tasks": tasks,
    }


def strict_residual(
    rows: list[senior.independent.RelationEdge],
    v11_identities: set[str],
    v11_runs: set[str],
) -> tuple[list[senior.independent.RelationEdge], collections.Counter[str]]:
    kept: list[senior.independent.RelationEdge] = []
    reasons: collections.Counter[str] = collections.Counter()
    for row in rows:
        endpoint_overlap = row.high in v11_identities or row.low in v11_identities
        parent_overlap = row.declared in v11_identities
        run_overlap = row.high_run in v11_runs
        mask = "".join(
            key
            for key, present in (
                ("E", endpoint_overlap),
                ("P", parent_overlap),
                ("R", run_overlap),
            )
            if present
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


def row_sets(
    rows: Iterable[senior.independent.RelationEdge],
) -> dict[str, set[str] | set[tuple[str, str]]]:
    materialized = list(rows)
    return {
        "pairs": {row.pair() for row in materialized},
        "endpoints": {item for row in materialized for item in row.pair()},
        "parents": {row.declared for row in materialized},
        "runs": {row.high_run for row in materialized},
        "tasks": {row.task for row in materialized},
    }


def duplicate_profile(rows: list[senior.independent.RelationEdge]) -> dict[str, int]:
    unordered = collections.Counter(row.pair() for row in rows)
    ordered: dict[tuple[str, str], set[tuple[str, str]]] = collections.defaultdict(set)
    for row in rows:
        ordered[row.pair()].add(row.direction())
    return {
        "duplicate_unordered_pair_rows": sum(count - 1 for count in unordered.values()),
        "conflicting_orientation_unordered_pairs": sum(len(values) > 1 for values in ordered.values()),
    }


def identity_fingerprint(rows: Iterable[senior.independent.RelationEdge]) -> str:
    records = []
    for row in rows:
        first, second = row.pair()
        records.append("\0".join((first, second, row.declared, row.task, row.high_run)))
    return hashlib.sha256(("\n".join(sorted(records)) + "\n").encode()).hexdigest()


def classify(integrity: dict[str, bool], support: dict[str, bool]) -> str:
    if not all(integrity.values()):
        return "HISTORICAL_SENIOR0819_INDEPENDENT_SIBLING_GRAPH_INTEGRITY_FAIL"
    if not all(support.values()):
        return "HISTORICAL_SENIOR0819_INDEPENDENT_SIBLING_GRAPH_LIMITED_SUPPORT"
    return "HISTORICAL_SENIOR0819_INDEPENDENT_SIBLING_GRAPH_FEASIBLE"


def recompute(args: argparse.Namespace) -> dict[str, Any]:
    protocol = load_protocol(Path(args.protocol).resolve(), args.protocol_sha256)
    verify_parent_certificates(args, protocol)
    security = verify_security_receipt(
        Path(args.senior_security_receipt).resolve(), protocol
    )
    immutable = protocol["immutable_inputs"]
    paths = {
        "cards": Path(args.senior_cards).resolve(),
        "run_split": Path(args.senior_run_split).resolve(),
        "decision": Path(args.senior_decision).resolve(),
    }
    check(digest(paths["cards"]) == immutable["senior_safe_cards"]["sha256"], "cards SHA")
    check(digest(paths["run_split"]) == immutable["senior_run_split"]["sha256"], "run split SHA")
    check(digest(paths["decision"]) == immutable["senior_decision"]["sha256"], "decision SHA")

    senior_protocol_path = Path(args.senior_quarantine_protocol).resolve()
    senior_binding = immutable["senior_0819_quarantine_protocol"]
    check(digest(senior_protocol_path) == senior_binding["sha256"], "senior protocol SHA")
    senior_protocol = senior.frozen_protocol(senior_protocol_path, senior_binding["sha256"])
    all_runs, held = senior.independent.prior.manifest(paths["run_split"], senior_protocol)
    nodes, inventory = senior.independent.prior.card_index(paths["cards"], all_runs)
    edges, diagnostics = senior.independent.parse_decisions(
        paths["decision"],
        nodes,
        held,
        senior_protocol["immutable_inputs"]["decision"],
    )
    core = [edge for edge in edges if senior.selected_core(edge, held)]
    train_core = [edge for edge in core if edge.split == "train"]
    check(len(core) == 1270 and len(train_core) == 952, "senior core reconstruction")

    v11 = load_v11_graph(Path(args.v11_pairs).resolve(), protocol)
    v11_identities = set(v11["endpoints"]) | set(v11["parents"])
    residual, drop_reasons = strict_residual(train_core, v11_identities, set(v11["runs"]))
    candidate_sets = row_sets(train_core)
    residual_sets = row_sets(residual)
    duplicate = duplicate_profile(residual)
    candidate_profile, _ = senior.independent.group_profile(train_core)
    residual_profile, residual_exacts = senior.independent.group_profile(residual)
    candidate_profile["parents"] = len(candidate_sets["parents"])
    residual_profile["parents"] = len(residual_sets["parents"])

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
        "minimum_residual_pair_retention": (
            retention >= frozen_fraction(frozen["minimum_residual_pair_retention"])
        ),
        "minimum_residual_endpoints": (
            residual_profile["endpoints"] >= frozen["minimum_residual_endpoints"]
        ),
        "minimum_residual_parents": (
            residual_profile["parents"] >= frozen["minimum_residual_parents"]
        ),
        "minimum_residual_physical_runs": (
            residual_profile["physical_runs"] >= frozen["minimum_residual_physical_runs"]
        ),
        "minimum_residual_tasks": residual_profile["tasks"] >= frozen["minimum_residual_tasks"],
        "maximum_single_residual_task_pair_share": (
            residual_exacts["maximum_single_task_pair_share"]
            <= frozen_fraction(frozen["maximum_single_residual_task_pair_share"])
        ),
        "maximum_single_residual_run_pair_share": (
            residual_exacts["maximum_single_run_pair_share"]
            <= frozen_fraction(frozen["maximum_single_residual_run_pair_share"])
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
            "senior_train_core": identity_fingerprint(train_core),
            "strict_residual": identity_fingerprint(residual),
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
            "cards": inventory["cards"],
        },
    }


def arguments() -> argparse.Namespace:
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
    parser.add_argument("--producer-result", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = arguments()
    expected = object_json(Path(args.producer_result).resolve())
    observed = recompute(args)
    check(observed == expected, "producer and independent aggregate differ")
    receipt = {
        "protocol": "historical-independent-sibling-graph-gate-independent-verification-v1",
        "status": "INDEPENDENT_HISTORICAL_SIBLING_GRAPH_GATE_VERIFIED",
        "protocol_sha256": args.protocol_sha256,
        "producer_result_sha256": digest(Path(args.producer_result).resolve()),
        "producer_imported": False,
        "all_aggregate_fields_equal": True,
        "classification": expected["classification"],
        "scope": expected["scope"],
    }
    Path(args.output).write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(receipt["classification"])


if __name__ == "__main__":
    main()
