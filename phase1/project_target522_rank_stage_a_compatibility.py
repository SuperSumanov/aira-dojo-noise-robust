#!/usr/bin/env python3
"""Validate Stage-A v2 provenance and project its public JSON to the frozen rank schema.

The projection removes exactly two execution-container fields and rewrites exactly
one provenance field to the byte-frozen scientific implementation commit.  It does
not inspect private selection, identities, labels, outcomes, predictions, or utility.
The actual immutable Stage-A public file and the projected file are bound together
in a separate receipt.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping


COMPATIBILITY_PROTOCOL = "target522-linear-contrast-rank-stage-a-compatibility-v1"
RANK_PROTOCOL = "target522-linear-contrast-rank-audit-v1"
STAGE_PROTOCOL = "vertex-cost-contrast-target522-selection-public-v1"
SHA_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")

COMMON_STAGE_KEYS = {
    "protocol",
    "status",
    "protocol_sha256",
    "analysis_source_commit",
    "candidate_snapshot_sha256",
    "append_only",
    "pair_file_bindings",
    "run_partition",
    "acquisition_graph",
    "evaluation_graph",
    "support_gates",
    "scope",
}
LIMITED_STAGE_KEYS = {
    "classification",
    "checkpoints",
    "arm_metrics",
    "yield_solver",
    "private_selection_sha256",
}
READY_STAGE_KEYS = {
    "classification",
    "checkpoints",
    "uniform_baseline",
    "vccd",
    "yield_baseline",
    "yield_floors",
    "yield_solver",
    "yield_witness_gates",
    "arm_metrics",
    "private_selection_sha256",
}
EXECUTION_ONLY_KEYS = {
    "selection_container",
    "selection_container_compatibility_sha256",
}
FORBIDDEN_IDENTITY_KEYS = {
    "endpoint_ids",
    "run_ids",
    "parent_ids",
    "task_ids",
    "acquisition_run_ids",
    "evaluation_run_ids",
    "arms",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode() + b"\n"


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


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


def identity_key_hits(value: Any) -> list[str]:
    hits: list[str] = []

    def visit(node: Any, prefix: str) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                path = f"{prefix}.{key}" if prefix else str(key)
                if key in FORBIDDEN_IDENTITY_KEYS:
                    hits.append(path)
                visit(child, path)
        elif isinstance(node, list):
            for index, child in enumerate(node):
                visit(child, f"{prefix}[{index}]")

    visit(value, "")
    return hits


def validate_and_project(
    compatibility: Mapping[str, Any],
    compatibility_sha256: str,
    rank_protocol: Mapping[str, Any],
    rank_protocol_sha256: str,
    stage_a: Mapping[str, Any],
    stage_a_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    for value, label in (
        (compatibility_sha256, "compatibility SHA"),
        (rank_protocol_sha256, "rank protocol SHA"),
        (stage_a_sha256, "Stage-A public SHA"),
    ):
        require(SHA_RE.fullmatch(value) is not None, label)
    require(compatibility.get("protocol") == COMPATIBILITY_PROTOCOL, "compatibility protocol")
    require(compatibility.get("version") == 1, "compatibility version")
    require(
        compatibility.get("status")
        == "FROZEN_BEFORE_STAGE_A_V2_COMPLETE_WITHOUT_PUBLIC_PROFILE_READ",
        "compatibility status",
    )
    freeze = compatibility.get("freeze_observation")
    require(isinstance(freeze, Mapping), "freeze observation")
    require(all(value is False for value in freeze.values()), "post-result compatibility freeze")

    rank_binding = compatibility.get("rank_scientific_protocol")
    require(isinstance(rank_binding, Mapping), "rank binding")
    require(rank_binding.get("sha256") == rank_protocol_sha256, "rank SHA drift")
    require(rank_protocol.get("protocol") == RANK_PROTOCOL, "rank protocol")
    require(
        rank_protocol.get("status")
        == "FROZEN_AFTER_DISCLOSED_HISTORICAL_EXPLORATION_BEFORE_TARGET522_CANDIDATE",
        "rank status",
    )

    bridge = compatibility.get("stage_a_execution_bridge")
    require(isinstance(bridge, Mapping), "Stage-A execution bridge")
    for key in ("frozen_scientific_source_commit", "compatible_execution_source_commit"):
        require(COMMIT_RE.fullmatch(str(bridge.get(key))) is not None, f"invalid {key}")
    for key in (
        "scientific_protocol_sha256",
        "execution_protocol_v2_sha256",
        "selection_container_compatibility_sha256",
        "outer_selection_sha256sums_sha256",
    ):
        require(SHA_RE.fullmatch(str(bridge.get(key))) is not None, f"invalid {key}")
    frozen_stage = rank_protocol.get("frozen_stage_a")
    require(isinstance(frozen_stage, Mapping), "rank frozen Stage-A binding")
    require(
        frozen_stage.get("source_commit") == bridge["frozen_scientific_source_commit"],
        "frozen Stage-A commit drift",
    )
    require(
        frozen_stage.get("scientific_protocol_sha256") == bridge["scientific_protocol_sha256"],
        "frozen Stage-A protocol drift",
    )

    require(stage_a.get("protocol") == STAGE_PROTOCOL, "Stage-A protocol")
    require(stage_a.get("status") == "COMPLETE", "Stage-A incomplete")
    require(
        stage_a.get("analysis_source_commit") == bridge["compatible_execution_source_commit"],
        "Stage-A execution source drift",
    )
    require(
        stage_a.get("protocol_sha256") == bridge["scientific_protocol_sha256"],
        "Stage-A scientific protocol drift",
    )
    require(
        stage_a.get("selection_container_compatibility_sha256")
        == bridge["selection_container_compatibility_sha256"],
        "Stage-A container compatibility drift",
    )
    container = stage_a.get("selection_container")
    require(isinstance(container, Mapping), "Stage-A selection container")
    require(
        container.get("outer_sha256sums_sha256")
        == bridge["outer_selection_sha256sums_sha256"],
        "Stage-A outer selection manifest drift",
    )
    require(
        SHA_RE.fullmatch(str(container.get("core_projection_sha256sums_sha256"))) is not None,
        "Stage-A core projection SHA",
    )
    require(
        container.get("manifest_bound_auxiliary_receipt_count")
        == bridge["manifest_bound_auxiliary_receipt_count"],
        "Stage-A auxiliary receipt count drift",
    )
    support = stage_a.get("support_gates")
    require(
        isinstance(support, Mapping)
        and bool(support)
        and all(isinstance(value, bool) for value in support.values()),
        "Stage-A support-gate schema",
    )
    expected_keys = COMMON_STAGE_KEYS | EXECUTION_ONLY_KEYS
    expected_keys |= READY_STAGE_KEYS if all(support.values()) else LIMITED_STAGE_KEYS
    require(set(stage_a) == expected_keys, "Stage-A public top-level schema drift")
    require(not identity_key_hits(stage_a), "Stage-A public identity collection present")

    projection_spec = compatibility.get("projection")
    require(isinstance(projection_spec, Mapping), "projection specification")
    require(
        projection_spec.get("remove_exact_top_level_keys")
        == ["selection_container", "selection_container_compatibility_sha256"],
        "projection removal drift",
    )
    require(
        projection_spec.get("replace_exact_top_level_key") == "analysis_source_commit"
        and projection_spec.get("replacement_value") == bridge["frozen_scientific_source_commit"]
        and projection_spec.get("require_no_other_top_level_change") is True
        and projection_spec.get("actual_stage_a_public_remains_immutable") is True,
        "projection replacement drift",
    )
    scope = compatibility.get("scope")
    require(isinstance(scope, Mapping), "compatibility scope")
    require(scope.get("changes_rank_threshold_partition_or_decision_rule") is False, "rank drift")
    require(scope.get("opens_stage_a_private_selection") is False, "private selection scope")
    require(scope.get("opens_candidate_identity") is False, "identity scope")
    require(
        scope.get("reads_label_outcome_prediction_accuracy_gap_runtime_or_utility") is False,
        "forbidden-value scope",
    )
    require(scope.get("reads_prospective_values") is False, "prospective-value scope")
    require(scope.get("gpu_paid_api_model_fit_base_update") == "0/0/0/0", "resource scope")

    projected = copy.deepcopy(dict(stage_a))
    for key in projection_spec["remove_exact_top_level_keys"]:
        require(key in projected, f"missing projected removal {key}")
        del projected[key]
    projected[projection_spec["replace_exact_top_level_key"]] = projection_spec["replacement_value"]
    require(set(stage_a) - set(projected) == EXECUTION_ONLY_KEYS, "unexpected projection removal")
    changed = {
        key
        for key in set(projected) & set(stage_a)
        if projected[key] != stage_a[key]
    }
    require(changed == {"analysis_source_commit"}, "unexpected projection change")
    require(not identity_key_hits(projected), "projected identity collection present")
    projected_sha = hashlib.sha256(canonical_bytes(projected)).hexdigest()
    receipt = {
        "protocol": "target522-linear-contrast-rank-stage-a-projection-receipt-v1",
        "status": "EXACT_EXECUTION_COMPATIBILITY_PROJECTION",
        "compatibility_sha256": compatibility_sha256,
        "rank_scientific_protocol_sha256": rank_protocol_sha256,
        "actual_stage_a_public_sha256": stage_a_sha256,
        "projected_stage_a_public_sha256": projected_sha,
        "actual_execution_source_commit": bridge["compatible_execution_source_commit"],
        "frozen_scientific_source_commit": bridge["frozen_scientific_source_commit"],
        "removed_top_level_keys": sorted(EXECUTION_ONLY_KEYS),
        "changed_top_level_keys": ["analysis_source_commit"],
        "other_top_level_changes": 0,
        "private_selection_opened": False,
        "candidate_identity_opened": False,
        "prospective_values_read": False,
        "gpu_paid_api_model_fit_base_update": "0/0/0/0",
    }
    return projected, receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compatibility", type=Path, required=True)
    parser.add_argument("--compatibility-sha256", required=True)
    parser.add_argument("--rank-protocol", type=Path, required=True)
    parser.add_argument("--rank-protocol-sha256", required=True)
    parser.add_argument("--stage-a-public", type=Path, required=True)
    parser.add_argument("--stage-a-public-sha256", required=True)
    parser.add_argument("--projected-output", type=Path, required=True)
    parser.add_argument("--receipt-output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    for path, expected, label in (
        (args.compatibility.resolve(), args.compatibility_sha256, "compatibility"),
        (args.rank_protocol.resolve(), args.rank_protocol_sha256, "rank protocol"),
        (args.stage_a_public.resolve(), args.stage_a_public_sha256, "Stage-A public"),
    ):
        require(SHA_RE.fullmatch(expected) is not None and file_sha(path) == expected, f"{label} file SHA")
    projected, receipt = validate_and_project(
        read_object(args.compatibility.resolve()),
        args.compatibility_sha256,
        read_object(args.rank_protocol.resolve()),
        args.rank_protocol_sha256,
        read_object(args.stage_a_public.resolve()),
        args.stage_a_public_sha256,
    )
    write_exclusive(args.projected_output.resolve(), projected)
    write_exclusive(args.receipt_output.resolve(), receipt)
    print(
        canonical_bytes(
            {
                "status": receipt["status"],
                "projected_stage_a_public_sha256": receipt["projected_stage_a_public_sha256"],
                "prospective_values_read": False,
            }
        ).decode(),
        end="",
    )


if __name__ == "__main__":
    main()
