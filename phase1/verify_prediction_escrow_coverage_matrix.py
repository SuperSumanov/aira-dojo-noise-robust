#!/usr/bin/env python3
"""Independently re-derive a prediction-escrow coverage matrix receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import Counter
from pathlib import Path
from typing import Any


PROTOCOL = "prediction-escrow-coverage-matrix-v1"
WL_ARMS = (
    "step_only_lr",
    "wl_graph_lr",
    "wl_graph_static_lr",
    "wl_graph_static_tfidf_lr",
)
TRANSITION_ARMS = ("child_code", "transition_only", "child_plus_transition")


class VerificationError(RuntimeError):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def read_bound(path_value: str | Path, expected: str) -> tuple[Path, bytes]:
    unresolved = Path(path_value)
    if unresolved.is_symlink() or not unresolved.is_file():
        raise VerificationError("input missing, non-regular, or symlinked")
    path = unresolved.resolve()
    raw = path.read_bytes()
    if digest(raw) != expected:
        raise VerificationError(f"hash mismatch: {path.name}")
    return path, raw


def json_object(raw: bytes) -> dict[str, Any]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise VerificationError("expected JSON object")
    return value


def jsonl_objects(raw: bytes) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.strip():
            raise VerificationError("blank JSONL line")
        value = json.loads(line)
        if not isinstance(value, dict):
            raise VerificationError("JSONL row is not an object")
        result.append(value)
    if not result:
        raise VerificationError("empty JSONL")
    return result


def finite(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def verify_prediction_shape(row: dict[str, Any], source: str) -> None:
    if source == "wl":
        for arm in WL_ARMS:
            margin = row.get(f"{arm}_margin_left_minus_right")
            selected = row.get(f"{arm}_selected")
            if not finite(margin):
                raise VerificationError("WL prediction is absent or non-finite")
            expected = (
                row.get("left")
                if float(margin) > 0
                else row.get("right")
                if float(margin) < 0
                else "tie"
            )
            if selected != expected:
                raise VerificationError("WL selection/margin mismatch")
        return
    values = [row.get(arm) for arm in TRANSITION_ARMS]
    if row.get("parent_source_present") is True:
        if not all(finite(value) for value in values):
            raise VerificationError("covered transition prediction is absent or non-finite")
        finite_receipt = True
        nontie = all(float(value) != 0.0 for value in values)
    elif row.get("parent_source_present") is False:
        if any(value is not None for value in values) or row.get("parent_code_sha256") is not None:
            raise VerificationError("missing-parent transition is not null")
        finite_receipt = False
        nontie = False
    else:
        raise VerificationError("invalid parent-source receipt")
    if row.get("finite_all_arms") != finite_receipt:
        raise VerificationError("transition finite receipt mismatch")
    if row.get("nontie_all_arms") != nontie:
        raise VerificationError("transition nontie receipt mismatch")


def key_and_metadata(
    row: dict[str, Any], source: str
) -> tuple[str, tuple[str, str], str, str, str, bool]:
    values = [row.get(field) for field in ("task", "run_id", "parent", "left", "right")]
    if not all(isinstance(value, str) and value for value in values):
        raise VerificationError("invalid pair identity")
    task, run_id, parent, left, right = values
    if left == right:
        raise VerificationError("self pair")
    low, high = sorted((left, right))
    identity = (task, run_id, parent, low, high)
    key = digest(canonical(identity).encode("utf-8"))
    stratum = row.get("temporal_stratum")
    if not isinstance(stratum, str):
        raise VerificationError("invalid stratum")
    aliases = (
        {
            "outcome_unread_support_only": "support_only",
            "strict_post_activation_primary": "post_wl_activation",
        }
        if source == "wl"
        else {
            "support_only": "support_only",
            "strict_future": "post_transition_activation",
        }
    )
    stratum = aliases.get(stratum)
    if stratum is None:
        raise VerificationError("unknown stratum")
    eligible = bool(row.get("strict_effect_eligible", False)) if source == "transition" else False
    if source == "transition" and eligible and stratum != "post_transition_activation":
        raise VerificationError("eligible transition precedes activation")
    return key, (left, right), stratum, task, run_id, eligible


def parse_source(
    rows: list[dict[str, Any]], source: str
) -> dict[str, tuple[tuple[str, str], str, str, str, bool]]:
    parsed: dict[str, tuple[tuple[str, str], str, str, str, bool]] = {}
    for row in rows:
        verify_prediction_shape(row, source)
        key, orientation, stratum, task, run_id, eligible = key_and_metadata(row, source)
        if key in parsed:
            raise VerificationError("duplicate canonical identity")
        parsed[key] = (orientation, stratum, task, run_id, eligible)
    return parsed


def map_digest(values: list[Any]) -> str:
    return digest("".join(canonical(value) + "\n" for value in values).encode("utf-8"))


def verify(matrix: dict[str, Any], wl_raw: bytes, transition_raw: bytes) -> dict[str, Any]:
    if matrix.get("protocol") != PROTOCOL:
        raise VerificationError("protocol mismatch")
    if matrix.get("formal_status") != "OUTCOME_BLIND_PREDICTION_COVERAGE_VERIFIED":
        raise VerificationError("formal status mismatch")
    wl = parse_source(jsonl_objects(wl_raw), "wl")
    transition = parse_source(jsonl_objects(transition_raw), "transition")
    wl_keys, transition_keys = set(wl), set(transition)
    intersection = wl_keys & transition_keys
    union = wl_keys | transition_keys

    def expected_inventory(
        source: dict[str, tuple[tuple[str, str], str, str, str, bool]]
    ) -> dict[str, Any]:
        task_counts = Counter(value[2] for value in source.values())
        run_counts = Counter(value[3] for value in source.values())
        strata = Counter(value[1] for value in source.values())
        dominant_task, dominant_count = max(
            task_counts.items(), key=lambda item: (item[1], item[0])
        )
        return {
            "pairs": len(source),
            "runs": len(run_counts),
            "tasks": len(task_counts),
            "strata": dict(sorted(strata.items())),
            "pairs_per_task": dict(sorted(task_counts.items())),
            "dominant_task": dominant_task,
            "dominant_task_pairs": dominant_count,
            "dominant_task_share": dominant_count / len(source),
            "canonical_identity_mapping_sha256": map_digest(sorted(source)),
        }

    for name, source in (("wl", wl), ("transition", transition)):
        observed = matrix["inventory"][name]
        expected = expected_inventory(source)
        for field, value in expected.items():
            if observed.get(field) != value:
                raise VerificationError(f"inventory mismatch: {name}.{field}")

    same = 0
    reversed_count = 0
    joint_strata = Counter()
    eligible_in_intersection = 0
    for key in intersection:
        joint_strata[f"{wl[key][1]}|{transition[key][1]}"] += 1
        eligible_in_intersection += transition[key][4]
        if wl[key][0] == transition[key][0]:
            same += 1
        elif wl[key][0] == tuple(reversed(transition[key][0])):
            reversed_count += 1
        else:
            raise VerificationError("overlap orientation mismatch")
    expected_overlap = {
        "intersection_pairs": len(intersection),
        "union_pairs": len(union),
        "intersection_over_union": len(intersection) / len(union),
        "wl_covered_by_transition": len(intersection) / len(wl),
        "transition_covered_by_wl": len(intersection) / len(transition),
        "wl_only_pairs": len(wl_keys - transition_keys),
        "transition_only_pairs": len(transition_keys - wl_keys),
        "same_left_right_orientation": same,
        "reversed_left_right_orientation": reversed_count,
        "joint_temporal_strata": dict(sorted(joint_strata.items())),
        "transition_effect_eligible_pairs": eligible_in_intersection,
        "intersection_mapping_sha256": map_digest(sorted(intersection)),
    }
    for field, value in expected_overlap.items():
        if matrix["overlap"].get(field) != value:
            raise VerificationError(f"overlap mismatch: {field}")

    attestation = matrix.get("access_attestation")
    if attestation != {
        "labels_grades_outcomes_or_winner_orientation_read": False,
        "prediction_values_aggregated": False,
        "accuracy_effect_or_search_utility_computed": False,
        "gpu_or_api_calls": 0,
        "base_llm_updates": 0,
    }:
        raise VerificationError("access attestation mismatch")
    return {
        "protocol": "independent-" + PROTOCOL,
        "formal_status": "INDEPENDENT_COVERAGE_VERIFICATION_PASS",
        "canonical_matrix_sha256": digest((canonical(matrix) + "\n").encode("utf-8")),
        "recomputed": {
            "wl_pairs": len(wl),
            "transition_pairs": len(transition),
            "intersection_pairs": len(intersection),
            "union_pairs": len(union),
            "tasks_in_intersection": len({wl[key][2] for key in intersection}),
            "runs_in_intersection": len({wl[key][3] for key in intersection}),
            "intersection_mapping_sha256": map_digest(sorted(intersection)),
        },
        "access_attestation": {
            "prediction_values_aggregated": False,
            "labels_grades_outcomes_or_winner_orientation_read": False,
            "accuracy_effect_or_search_utility_computed": False,
        },
    }


def write_once(path_value: str | Path, value: dict[str, Any]) -> None:
    unresolved = Path(path_value)
    if unresolved.is_symlink() or unresolved.exists():
        raise VerificationError("output path exists or is symlinked")
    path = unresolved.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--expect-matrix-sha256", required=True)
    parser.add_argument("--wl-pairs", required=True)
    parser.add_argument("--expect-wl-pairs-sha256", required=True)
    parser.add_argument("--transition-pairs", required=True)
    parser.add_argument("--expect-transition-pairs-sha256", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        _, matrix_raw = read_bound(args.matrix, args.expect_matrix_sha256)
        _, wl_raw = read_bound(args.wl_pairs, args.expect_wl_pairs_sha256)
        _, transition_raw = read_bound(
            args.transition_pairs, args.expect_transition_pairs_sha256
        )
        result = verify(json_object(matrix_raw), wl_raw, transition_raw)
        write_once(args.output, result)
    except (VerificationError, OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"INDEPENDENT_COVERAGE_FAIL type={type(exc).__name__}", file=os.sys.stderr)
        return 2
    print(
        "INDEPENDENT_COVERAGE_PASS "
        f"intersection={result['recomputed']['intersection_pairs']} "
        f"union={result['recomputed']['union_pairs']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
