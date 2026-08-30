#!/usr/bin/env python3
"""Audit pair-row inflation over the endpoint-incidence rank in Target-522 Stage A.

The input is the public, aggregate-only Stage-A result.  This module never opens
the private endpoint selection, candidate files, labels, grades, gaps, code, or
predictions.  Its rank is the incidence-matrix rank implied by a disjoint union
of exact sibling cliques; it is not an effective-sample-size or Shannon-information
estimate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any, Mapping


PROTOCOL_NAME = "target522-linear-contrast-rank-audit-v1"
PUBLIC_STAGE_A_PROTOCOL = "vertex-cost-contrast-target522-selection-public-v1"
SHA_RE = re.compile(r"[0-9a-f]{64}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode() + b"\n"


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path} is not a JSON object")
    return value


def integer(value: Any, name: str, minimum: int = 0) -> int:
    require(
        isinstance(value, int) and not isinstance(value, bool) and value >= minimum,
        f"invalid {name}",
    )
    return value


def exact_ratio(numerator: int, denominator: int) -> dict[str, Any]:
    require(denominator > 0, "zero ratio denominator")
    common = math.gcd(numerator, denominator)
    return {
        "numerator": numerator // common,
        "denominator": denominator // common,
        "decimal_17g": format(numerator / denominator, ".17g"),
    }


def validated_share(value: Any, name: str) -> dict[str, Any]:
    require(isinstance(value, Mapping), f"invalid {name}")
    require(
        set(value) == {"numerator", "denominator", "decimal_17g"},
        f"{name} schema",
    )
    numerator = integer(value["numerator"], f"{name} numerator", 1)
    denominator = integer(value["denominator"], f"{name} denominator", 1)
    require(numerator <= denominator, f"{name} exceeds one")
    expected = exact_ratio(numerator, denominator)
    require(
        value["numerator"] == expected["numerator"]
        and value["denominator"] == expected["denominator"],
        f"{name} is not reduced",
    )
    require(value["decimal_17g"] == expected["decimal_17g"], f"{name} decimal")
    return expected


def fraction_leq(value: Mapping[str, Any], numerator: int, denominator: int) -> bool:
    return value["numerator"] * denominator <= value["denominator"] * numerator


def validate_gate_schema(gates: Mapping[str, Any]) -> None:
    require(
        set(gates)
        == {
            "material_pair_rows_per_rank_numerator",
            "material_pair_rows_per_rank_denominator",
            "maximum_single_task_pair_share_numerator",
            "maximum_single_task_pair_share_denominator",
            "acquisition",
            "evaluation",
        },
        "confirmation-gate schema",
    )
    for name in ("acquisition", "evaluation"):
        require(isinstance(gates[name], Mapping), f"{name} gate object")
        require(
            set(gates[name])
            == {"minimum_pairs", "minimum_physical_runs", "minimum_tasks"},
            f"{name} gate schema",
        )


def graph_audit(
    profile: Mapping[str, Any], graph_name: str, gates: Mapping[str, Any]
) -> dict[str, Any]:
    expected = {
        "pairs",
        "endpoints",
        "parents",
        "physical_runs",
        "tasks",
        "maximum_single_task_pair_share",
        "maximum_single_run_pair_share",
        "orientation_free_graph_sha256",
    }
    require(set(profile) == expected, f"{graph_name} profile schema")
    pairs = integer(profile["pairs"], f"{graph_name} pairs", 1)
    endpoints = integer(profile["endpoints"], f"{graph_name} endpoints", 2)
    parents = integer(profile["parents"], f"{graph_name} parents", 1)
    runs = integer(profile["physical_runs"], f"{graph_name} runs", 1)
    tasks = integer(profile["tasks"], f"{graph_name} tasks", 1)
    task_share = validated_share(
        profile["maximum_single_task_pair_share"],
        f"{graph_name} maximum task share",
    )
    run_share = validated_share(
        profile["maximum_single_run_pair_share"],
        f"{graph_name} maximum run share",
    )
    require(parents < endpoints, f"{graph_name} nonpositive incidence rank")
    require(SHA_RE.fullmatch(str(profile["orientation_free_graph_sha256"])) is not None,
            f"{graph_name} graph hash")
    incidence_rank = endpoints - parents
    require(pairs >= incidence_rank, f"{graph_name} pair/rank inconsistency")
    redundant_rows = pairs - incidence_rank

    graph_gate = gates[graph_name]
    material_num = integer(gates["material_pair_rows_per_rank_numerator"], "material numerator", 1)
    material_den = integer(gates["material_pair_rows_per_rank_denominator"], "material denominator", 1)
    checks = {
        "minimum_pairs": pairs >= integer(graph_gate["minimum_pairs"], "minimum pairs", 1),
        "minimum_physical_runs": runs
        >= integer(graph_gate["minimum_physical_runs"], "minimum runs", 1),
        "minimum_tasks": tasks
        >= integer(graph_gate["minimum_tasks"], "minimum tasks", 1),
        "maximum_single_task_pair_share": fraction_leq(
            task_share,
            integer(gates["maximum_single_task_pair_share_numerator"], "task-share numerator"),
            integer(gates["maximum_single_task_pair_share_denominator"], "task-share denominator", 1),
        ),
        "material_pair_rows_per_incidence_rank": pairs * material_den
        >= incidence_rank * material_num,
    }
    return {
        "pairs": pairs,
        "endpoints": endpoints,
        "parents": parents,
        "physical_runs": runs,
        "tasks": tasks,
        "incidence_rank": incidence_rank,
        "redundant_pair_rows": redundant_rows,
        "pair_rows_per_incidence_rank": exact_ratio(pairs, incidence_rank),
        "redundant_pair_row_share": exact_ratio(redundant_rows, pairs),
        "maximum_single_task_pair_share": task_share,
        "maximum_single_run_pair_share": run_share,
        "orientation_free_graph_sha256": profile["orientation_free_graph_sha256"],
        "gates": checks,
        "all_gates_pass": all(checks.values()),
    }


def build(
    protocol: Mapping[str, Any],
    protocol_sha256: str,
    stage_a: Mapping[str, Any],
    stage_a_sha256: str,
) -> dict[str, Any]:
    require(protocol.get("protocol") == PROTOCOL_NAME, "protocol name")
    require(
        protocol.get("status")
        == "FROZEN_AFTER_DISCLOSED_HISTORICAL_EXPLORATION_BEFORE_TARGET522_CANDIDATE",
        "protocol status",
    )
    freeze = protocol.get("freeze_observation")
    require(isinstance(freeze, Mapping), "freeze observation")
    require(freeze.get("target522_candidate_present") is False, "candidate preceded freeze")
    require(freeze.get("target522_ready_present") is False, "READY preceded freeze")
    require(freeze.get("target522_complete_present") is False, "COMPLETE preceded freeze")
    require(freeze.get("candidate_profile_or_identity_opened") is False, "candidate profile opened")
    require(freeze.get("prospective_values_read") is False, "prospective values preceded freeze")
    require(SHA_RE.fullmatch(protocol_sha256) is not None, "protocol SHA syntax")
    require(SHA_RE.fullmatch(stage_a_sha256) is not None, "Stage-A SHA syntax")
    frozen = protocol["frozen_stage_a"]
    require(stage_a.get("protocol") == PUBLIC_STAGE_A_PROTOCOL, "Stage-A protocol")
    require(stage_a.get("status") == "COMPLETE", "Stage-A incomplete")
    require(stage_a.get("protocol_sha256") == frozen["scientific_protocol_sha256"],
            "scientific protocol drift")
    require(stage_a.get("analysis_source_commit") == frozen["source_commit"],
            "Stage-A source commit drift")
    require(SHA_RE.fullmatch(str(stage_a.get("candidate_snapshot_sha256"))) is not None,
            "candidate snapshot SHA")
    pair_bindings = stage_a.get("pair_file_bindings")
    require(isinstance(pair_bindings, dict), "missing pair bindings")
    require(pair_bindings.get("structural_pair_files_equal_exact_observed_sibling_cliques") is True,
            "exact sibling-clique certificate absent")
    partition = stage_a.get("run_partition")
    require(isinstance(partition, dict) and partition.get("overlap") == 0,
            "run partition overlap")
    scope = stage_a.get("scope")
    require(isinstance(scope, dict), "missing Stage-A scope")
    require(scope.get("outcome_blind_code_and_topology_only") is True, "Stage-A not outcome blind")
    require(scope.get("label_grade_gap_prediction_accuracy_utility_runtime_used") is False,
            "forbidden Stage-A values used")
    require(scope.get("prospective_values_read") is False, "prospective values read")
    require(scope.get("first960_closure_opened") is False, "first960 closure opened")
    require(scope.get("raw_identities_publicly_emitted") is False, "public identities emitted")
    require(scope.get("gpu_paid_api_model_fit_base_update") == "0/0/0/0", "resource drift")
    support = stage_a.get("support_gates")
    require(isinstance(support, dict) and support, "missing Stage-A support gates")
    require(all(isinstance(value, bool) for value in support.values()), "support-gate schema")

    gates = protocol["confirmation_gates"]
    require(isinstance(gates, Mapping), "confirmation gates")
    validate_gate_schema(gates)
    acquisition = graph_audit(stage_a["acquisition_graph"], "acquisition", gates)
    evaluation = graph_audit(stage_a["evaluation_graph"], "evaluation", gates)
    support_all = all(support.values())
    if not support_all:
        classification = "TARGET522_LINEAR_CONTRAST_RANK_AUDIT_LIMITED_SUPPORT"
    elif acquisition["all_gates_pass"] and evaluation["all_gates_pass"]:
        classification = "TARGET522_LINEAR_CONTRAST_ROW_INFLATION_CONFIRMED"
    else:
        classification = "TARGET522_LINEAR_CONTRAST_ROW_INFLATION_NOT_CONFIRMED"

    return {
        "protocol": "target522-linear-contrast-rank-audit-result-v1",
        "status": "COMPLETE",
        "classification": classification,
        "protocol_sha256": protocol_sha256,
        "stage_a_public_sha256": stage_a_sha256,
        "stage_a_source_commit": frozen["source_commit"],
        "candidate_snapshot_sha256": stage_a["candidate_snapshot_sha256"],
        "exact_disjoint_sibling_clique_basis": True,
        "run_partition_overlap": 0,
        "stage_a_support_gates_all": support_all,
        "graphs": {"acquisition": acquisition, "evaluation": evaluation},
        "interpretation_boundary": {
            "quantity": "rank of the endpoint-edge incidence design for disjoint sibling cliques",
            "not_claimed": [
                "statistically independent labels",
                "effective sample size",
                "Shannon information",
                "feature-matrix rank for every critic",
                "predictor efficacy",
            ],
        },
        "scope": {
            "public_stage_a_aggregate_only": True,
            "private_selection_opened": False,
            "candidate_profile_or_identity_opened": False,
            "label_grade_gap_prediction_accuracy_utility_runtime_used": False,
            "prospective_values_read": False,
            "first960_closure_opened": False,
            "gpu_paid_api_model_fit_base_update": "0/0/0/0",
        },
    }


def write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--stage-a-public", type=Path, required=True)
    parser.add_argument("--stage-a-public-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    protocol_path = args.protocol.resolve()
    stage_a_path = args.stage_a_public.resolve()
    require(file_sha(protocol_path) == args.protocol_sha256, "protocol file SHA")
    require(file_sha(stage_a_path) == args.stage_a_public_sha256, "Stage-A file SHA")
    protocol = load_json(protocol_path)
    stage_a = load_json(stage_a_path)
    result = build(protocol, args.protocol_sha256, stage_a, args.stage_a_public_sha256)
    write_exclusive(args.output.resolve(), result)
    print(canonical_bytes({
        "status": result["status"],
        "classification": result["classification"],
        "output_sha256": file_sha(args.output.resolve()),
        "prospective_values_read": False,
    }).decode(), end="")


if __name__ == "__main__":
    main()
