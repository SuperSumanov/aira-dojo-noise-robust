#!/usr/bin/env python3
"""Independent verifier for the Target-522 linear contrast-rank audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any, Mapping


SHA_RE = re.compile(r"[0-9a-f]{64}")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(value, dict), f"{path} must be an object")
    return value


def integer(value: Any, name: str, minimum: int = 0) -> int:
    check(isinstance(value, int) and not isinstance(value, bool) and value >= minimum,
          f"invalid {name}")
    return value


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    check(denominator > 0, "zero denominator")
    divisor = math.gcd(numerator, denominator)
    return {
        "numerator": numerator // divisor,
        "denominator": denominator // divisor,
        "decimal_17g": format(numerator / denominator, ".17g"),
    }


def share(value: Any, name: str) -> dict[str, Any]:
    check(isinstance(value, Mapping), f"invalid {name}")
    check(set(value) == {"numerator", "denominator", "decimal_17g"}, f"{name} schema")
    numerator = integer(value["numerator"], f"{name} numerator", 1)
    denominator = integer(value["denominator"], f"{name} denominator", 1)
    check(numerator <= denominator, f"{name} exceeds one")
    expected = ratio(numerator, denominator)
    check(
        value["numerator"] == expected["numerator"]
        and value["denominator"] == expected["denominator"],
        f"{name} is not reduced",
    )
    check(value["decimal_17g"] == expected["decimal_17g"], f"{name} decimal")
    return expected


def share_leq(value: Mapping[str, Any], numerator: int, denominator: int) -> bool:
    return value["numerator"] * denominator <= value["denominator"] * numerator


def validate_gates(gates: Any) -> Mapping[str, Any]:
    check(isinstance(gates, Mapping), "confirmation gates")
    check(
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
        check(isinstance(gates[name], Mapping), f"{name} gate object")
        check(
            set(gates[name])
            == {"minimum_pairs", "minimum_physical_runs", "minimum_tasks"},
            f"{name} gate schema",
        )
    return gates


def expected_graph(profile: Mapping[str, Any], name: str, gates: Mapping[str, Any]) -> dict[str, Any]:
    check(
        set(profile)
        == {
            "pairs",
            "endpoints",
            "parents",
            "physical_runs",
            "tasks",
            "maximum_single_task_pair_share",
            "maximum_single_run_pair_share",
            "orientation_free_graph_sha256",
        },
        f"{name} profile schema",
    )
    pairs = integer(profile["pairs"], f"{name} pairs", 1)
    endpoints = integer(profile["endpoints"], f"{name} endpoints", 2)
    parents = integer(profile["parents"], f"{name} parents", 1)
    runs = integer(profile["physical_runs"], f"{name} runs", 1)
    tasks = integer(profile["tasks"], f"{name} tasks", 1)
    task_share = share(profile["maximum_single_task_pair_share"], f"{name} maximum task share")
    run_share = share(profile["maximum_single_run_pair_share"], f"{name} maximum run share")
    check(
        SHA_RE.fullmatch(str(profile["orientation_free_graph_sha256"])) is not None,
        f"{name} graph hash",
    )
    rank = endpoints - parents
    check(rank > 0 and pairs >= rank, f"{name} incidence arithmetic")
    redundant = pairs - rank
    local = gates[name]
    material_num = integer(gates["material_pair_rows_per_rank_numerator"], "material numerator", 1)
    material_den = integer(gates["material_pair_rows_per_rank_denominator"], "material denominator", 1)
    checks = {
        "minimum_pairs": pairs >= integer(local["minimum_pairs"], "minimum pairs", 1),
        "minimum_physical_runs": runs >= integer(local["minimum_physical_runs"], "minimum runs", 1),
        "minimum_tasks": tasks >= integer(local["minimum_tasks"], "minimum tasks", 1),
        "maximum_single_task_pair_share": share_leq(
            task_share,
            integer(gates["maximum_single_task_pair_share_numerator"], "task numerator"),
            integer(gates["maximum_single_task_pair_share_denominator"], "task denominator", 1),
        ),
        "material_pair_rows_per_incidence_rank": pairs * material_den >= rank * material_num,
    }
    return {
        "pairs": pairs,
        "endpoints": endpoints,
        "parents": parents,
        "physical_runs": runs,
        "tasks": tasks,
        "incidence_rank": rank,
        "redundant_pair_rows": redundant,
        "pair_rows_per_incidence_rank": ratio(pairs, rank),
        "redundant_pair_row_share": ratio(redundant, pairs),
        "maximum_single_task_pair_share": task_share,
        "maximum_single_run_pair_share": run_share,
        "orientation_free_graph_sha256": profile["orientation_free_graph_sha256"],
        "gates": checks,
        "all_gates_pass": all(checks.values()),
    }


def verify(
    protocol: Mapping[str, Any],
    protocol_sha: str,
    stage_a: Mapping[str, Any],
    stage_a_sha: str,
    claimed: Mapping[str, Any],
    claimed_sha: str,
) -> dict[str, Any]:
    for value, label in (
        (protocol_sha, "protocol SHA"),
        (stage_a_sha, "Stage-A SHA"),
        (claimed_sha, "claimed-result SHA"),
    ):
        check(SHA_RE.fullmatch(value) is not None, label)
    check(protocol.get("protocol") == "target522-linear-contrast-rank-audit-v1", "protocol")
    check(
        protocol.get("status")
        == "FROZEN_AFTER_DISCLOSED_HISTORICAL_EXPLORATION_BEFORE_TARGET522_CANDIDATE",
        "protocol status",
    )
    freeze = protocol.get("freeze_observation")
    check(isinstance(freeze, Mapping), "freeze observation")
    check(freeze.get("target522_candidate_present") is False, "candidate preceded freeze")
    check(freeze.get("target522_ready_present") is False, "READY preceded freeze")
    check(freeze.get("target522_complete_present") is False, "COMPLETE preceded freeze")
    check(freeze.get("candidate_profile_or_identity_opened") is False, "candidate profile opened")
    check(freeze.get("prospective_values_read") is False, "prospective values preceded freeze")
    check(stage_a.get("protocol") == "vertex-cost-contrast-target522-selection-public-v1", "Stage A")
    check(stage_a.get("status") == "COMPLETE", "Stage-A status")
    frozen = protocol["frozen_stage_a"]
    check(stage_a.get("analysis_source_commit") == frozen["source_commit"], "commit drift")
    check(stage_a.get("protocol_sha256") == frozen["scientific_protocol_sha256"], "protocol drift")
    bindings = stage_a["pair_file_bindings"]
    check(bindings.get("structural_pair_files_equal_exact_observed_sibling_cliques") is True,
          "clique certificate")
    check(stage_a["run_partition"].get("overlap") == 0, "partition overlap")
    scope = stage_a["scope"]
    check(scope.get("outcome_blind_code_and_topology_only") is True, "not outcome blind")
    check(scope.get("label_grade_gap_prediction_accuracy_utility_runtime_used") is False,
          "forbidden values")
    check(scope.get("prospective_values_read") is False, "prospective read")
    check(scope.get("first960_closure_opened") is False, "closure opened")
    check(scope.get("raw_identities_publicly_emitted") is False, "identity emitted")
    check(scope.get("gpu_paid_api_model_fit_base_update") == "0/0/0/0", "resource drift")

    gates = validate_gates(protocol["confirmation_gates"])
    graphs = {
        name: expected_graph(stage_a[f"{name}_graph"], name, gates)
        for name in ("acquisition", "evaluation")
    }
    support = stage_a["support_gates"]
    check(isinstance(support, dict) and support
          and all(isinstance(value, bool) for value in support.values()), "support schema")
    support_all = all(support.values())
    if not support_all:
        expected_class = "TARGET522_LINEAR_CONTRAST_RANK_AUDIT_LIMITED_SUPPORT"
    elif all(graph["all_gates_pass"] for graph in graphs.values()):
        expected_class = "TARGET522_LINEAR_CONTRAST_ROW_INFLATION_CONFIRMED"
    else:
        expected_class = "TARGET522_LINEAR_CONTRAST_ROW_INFLATION_NOT_CONFIRMED"

    check(
        set(claimed)
        == {
            "protocol",
            "status",
            "classification",
            "protocol_sha256",
            "stage_a_public_sha256",
            "stage_a_source_commit",
            "candidate_snapshot_sha256",
            "exact_disjoint_sibling_clique_basis",
            "run_partition_overlap",
            "stage_a_support_gates_all",
            "graphs",
            "interpretation_boundary",
            "scope",
        },
        "result schema",
    )
    check(claimed.get("protocol") == "target522-linear-contrast-rank-audit-result-v1", "result protocol")
    check(claimed.get("status") == "COMPLETE", "result status")
    check(claimed.get("classification") == expected_class, "classification")
    check(claimed.get("protocol_sha256") == protocol_sha, "result protocol SHA")
    check(claimed.get("stage_a_public_sha256") == stage_a_sha, "result Stage-A SHA")
    check(claimed.get("stage_a_source_commit") == frozen["source_commit"], "result commit")
    check(claimed.get("candidate_snapshot_sha256") == stage_a["candidate_snapshot_sha256"],
          "result candidate")
    check(claimed.get("exact_disjoint_sibling_clique_basis") is True, "result clique basis")
    check(claimed.get("run_partition_overlap") == 0, "result overlap")
    check(claimed.get("stage_a_support_gates_all") is support_all, "result support")
    check(claimed.get("graphs") == graphs, "graph reconstruction mismatch")
    boundary = claimed.get("interpretation_boundary")
    check(isinstance(boundary, dict)
          and set(boundary) == {"quantity", "not_claimed"}
          and boundary.get("quantity")
          == "rank of the endpoint-edge incidence design for disjoint sibling cliques",
          "interpretation boundary")
    check(
        boundary["not_claimed"]
        == [
            "statistically independent labels",
            "effective sample size",
            "Shannon information",
            "feature-matrix rank for every critic",
            "predictor efficacy",
        ],
        "interpretation exclusions",
    )
    result_scope = claimed.get("scope")
    check(isinstance(result_scope, dict), "result scope")
    check(
        set(result_scope)
        == {
            "public_stage_a_aggregate_only",
            "private_selection_opened",
            "candidate_profile_or_identity_opened",
            "label_grade_gap_prediction_accuracy_utility_runtime_used",
            "prospective_values_read",
            "first960_closure_opened",
            "gpu_paid_api_model_fit_base_update",
        },
        "result scope schema",
    )
    check(result_scope.get("public_stage_a_aggregate_only") is True, "aggregate scope")
    for key in (
        "private_selection_opened",
        "candidate_profile_or_identity_opened",
        "label_grade_gap_prediction_accuracy_utility_runtime_used",
        "prospective_values_read",
        "first960_closure_opened",
    ):
        check(result_scope.get(key) is False, f"scope {key}")
    check(result_scope.get("gpu_paid_api_model_fit_base_update") == "0/0/0/0", "result resource")

    return {
        "protocol": "target522-linear-contrast-rank-independent-verification-v1",
        "status": "INDEPENDENT_RECONSTRUCTION_EXACT",
        "classification": expected_class,
        "protocol_sha256": protocol_sha,
        "stage_a_public_sha256": stage_a_sha,
        "claimed_result_sha256": claimed_sha,
        "graphs_reconstructed": 2,
        "private_selection_opened": False,
        "candidate_profile_or_identity_opened": False,
        "prospective_values_read": False,
        "gpu_paid_api_model_fit_base_update": "0/0/0/0",
    }


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode() + b"\n"


def write(path: Path, value: Mapping[str, Any]) -> None:
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
    parser.add_argument("--claimed-result", type=Path, required=True)
    parser.add_argument("--claimed-result-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    for path, expected, label in (
        (args.protocol.resolve(), args.protocol_sha256, "protocol"),
        (args.stage_a_public.resolve(), args.stage_a_public_sha256, "Stage A"),
        (args.claimed_result.resolve(), args.claimed_result_sha256, "claimed result"),
    ):
        check(SHA_RE.fullmatch(expected) is not None and sha256(path) == expected,
              f"{label} file SHA")
    receipt = verify(
        read(args.protocol.resolve()),
        args.protocol_sha256,
        read(args.stage_a_public.resolve()),
        args.stage_a_public_sha256,
        read(args.claimed_result.resolve()),
        args.claimed_result_sha256,
    )
    write(args.output.resolve(), receipt)
    print(canonical_bytes({
        "status": receipt["status"],
        "classification": receipt["classification"],
        "output_sha256": sha256(args.output.resolve()),
        "prospective_values_read": False,
    }).decode(), end="")


if __name__ == "__main__":
    main()
