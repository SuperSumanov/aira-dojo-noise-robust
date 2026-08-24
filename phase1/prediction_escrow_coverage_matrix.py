#!/usr/bin/env python3
"""Build an aggregate, outcome-blind overlap receipt for two prediction escrows.

This program is deliberately not an evaluator.  It checks prediction-field
completeness but never aggregates prediction values and has no input through
which labels, grades, pair orientation, or outcomes can be supplied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any


PROTOCOL = "prediction-escrow-coverage-matrix-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
WL_ARMS = (
    "step_only_lr",
    "wl_graph_lr",
    "wl_graph_static_lr",
    "wl_graph_static_tfidf_lr",
)
TRANSITION_ARMS = ("child_code", "transition_only", "child_plus_transition")
WL_FIELDS = {
    "left",
    "pair_key_sha256",
    "parent",
    "right",
    "run_id",
    "task",
    "temporal_stratum",
    *(f"{arm}_margin_left_minus_right" for arm in WL_ARMS),
    *(f"{arm}_selected" for arm in WL_ARMS),
}
TRANSITION_FIELDS = {
    "pair_id",
    "task",
    "run_id",
    "parent",
    "left",
    "right",
    "generation_started_at_utc",
    "temporal_stratum",
    "parent_source_present",
    "left_code_sha256",
    "right_code_sha256",
    "parent_code_sha256",
    "training_endpoint_id_overlap",
    "training_run_id_overlap",
    "training_code_sha_overlap",
    "source_novel",
    "finite_all_arms",
    "nontie_all_arms",
    "strict_effect_eligible",
    *TRANSITION_ARMS,
}


class CoverageError(RuntimeError):
    """Raised when the outcome-blind coverage contract fails closed."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def checked_bytes(path_value: str | Path, expected_sha256: str) -> tuple[Path, bytes]:
    if not isinstance(expected_sha256, str) or SHA256_RE.fullmatch(expected_sha256) is None:
        raise CoverageError("invalid expected SHA-256")
    unresolved = Path(path_value)
    if unresolved.is_symlink() or not unresolved.is_file():
        raise CoverageError(f"input is absent, symlinked, or non-regular: {unresolved.name}")
    path = unresolved.resolve()
    raw = path.read_bytes()
    if sha256_bytes(raw) != expected_sha256:
        raise CoverageError(f"input SHA-256 mismatch: {path.name}")
    return path, raw


def load_object(path: Path, raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CoverageError(f"invalid JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise CoverageError(f"JSON root is not an object: {path.name}")
    return value


def load_rows(path: Path, raw: bytes, exact_fields: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(raw.splitlines(), 1):
        if not raw_line.strip():
            raise CoverageError(f"blank JSONL line at {path.name}:{line_number}")
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise CoverageError(f"invalid JSONL at {path.name}:{line_number}") from exc
        if not isinstance(row, dict) or set(row) != exact_fields:
            raise CoverageError(f"schema mismatch at {path.name}:{line_number}")
        rows.append(row)
    if not rows:
        raise CoverageError(f"empty JSONL input: {path.name}")
    return rows


def required_text(row: dict[str, Any], field: str) -> str:
    value = row[field]
    if not isinstance(value, str) or not value:
        raise CoverageError(f"invalid {field}")
    return value


def finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CoverageError(f"non-numeric prediction: {field}")
    result = float(value)
    if not math.isfinite(result):
        raise CoverageError(f"non-finite prediction: {field}")
    return result


def normalized_stratum(value: Any) -> str:
    if not isinstance(value, str):
        raise CoverageError("temporal_stratum is not a string")
    normalized = value.removeprefix("outcome_unread_")
    if normalized not in {"support_only", "strict_effect_eligible"}:
        raise CoverageError(f"unknown temporal stratum: {value}")
    return normalized


def identity_parts(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    task = required_text(row, "task")
    run_id = required_text(row, "run_id")
    parent = required_text(row, "parent")
    left = required_text(row, "left")
    right = required_text(row, "right")
    if left == right:
        raise CoverageError("pair has identical endpoints")
    child_a, child_b = sorted((left, right))
    return task, run_id, parent, child_a, child_b


def identity_sha256(row: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json(identity_parts(row)).encode("utf-8"))


def mapping_sha256(items: list[Any]) -> str:
    payload = "".join(canonical_json(item) + "\n" for item in items).encode("utf-8")
    return sha256_bytes(payload)


def summary_scope(summary: dict[str, Any], expected_snapshot: str, pairs_sha: str, kind: str) -> None:
    inputs = summary.get("inputs")
    scope = summary.get("scope")
    outputs = summary.get("outputs")
    if not isinstance(inputs, dict) or inputs.get("snapshot_sha256") != expected_snapshot:
        raise CoverageError(f"{kind} summary does not bind the expected snapshot")
    if not isinstance(scope, dict):
        raise CoverageError(f"{kind} summary has no scope receipt")
    expected_scope = {
        "prospective_outcomes_read": False,
        "effect_metrics_computed": [],
        "gpu": 0,
        "api_calls": 0,
        "base_llm_updates": 0,
    }
    for field, expected in expected_scope.items():
        if scope.get(field) != expected:
            raise CoverageError(f"{kind} summary violates blind scope: {field}")
    if not isinstance(outputs, dict):
        raise CoverageError(f"{kind} summary has no output receipt")
    output_field = "pair_predictions_sha256" if kind == "wl" else "pairs_sha256"
    if outputs.get(output_field) != pairs_sha:
        raise CoverageError(f"{kind} summary does not bind its pair file")


def parse_wl(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    parsed: dict[str, dict[str, Any]] = {}
    for row in rows:
        native = row["pair_key_sha256"]
        if not isinstance(native, str) or SHA256_RE.fullmatch(native) is None:
            raise CoverageError("invalid WL native pair key")
        key = identity_sha256(row)
        if key in parsed:
            raise CoverageError("duplicate canonical pair identity in WL escrow")
        margins: list[float] = []
        for arm in WL_ARMS:
            margin = finite_number(row[f"{arm}_margin_left_minus_right"], arm)
            selected = row[f"{arm}_selected"]
            if selected not in {row["left"], row["right"]}:
                raise CoverageError(f"WL selected endpoint is outside pair: {arm}")
            margins.append(margin)
        parsed[key] = {
            "parts": identity_parts(row),
            "orientation": (row["left"], row["right"]),
            "native_id": native,
            "stratum": normalized_stratum(row["temporal_stratum"]),
            "nontie_all_arms": all(value != 0.0 for value in margins),
        }
    return parsed


def parse_transition(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    parsed: dict[str, dict[str, Any]] = {}
    for row in rows:
        native = row["pair_id"]
        if not isinstance(native, str) or SHA256_RE.fullmatch(native) is None:
            raise CoverageError("invalid transition native pair key")
        for field in ("left_code_sha256", "right_code_sha256", "parent_code_sha256"):
            if not isinstance(row[field], str) or SHA256_RE.fullmatch(row[field]) is None:
                raise CoverageError(f"invalid transition code hash: {field}")
        for field in (
            "parent_source_present",
            "training_endpoint_id_overlap",
            "training_run_id_overlap",
            "training_code_sha_overlap",
            "source_novel",
            "finite_all_arms",
            "nontie_all_arms",
            "strict_effect_eligible",
        ):
            if not isinstance(row[field], bool):
                raise CoverageError(f"non-boolean transition field: {field}")
        values = [finite_number(row[arm], arm) for arm in TRANSITION_ARMS]
        if row["finite_all_arms"] is not True:
            raise CoverageError("transition finite_all_arms receipt mismatch")
        derived_nontie = all(value != 0.0 for value in values)
        if row["nontie_all_arms"] != derived_nontie:
            raise CoverageError("transition nontie_all_arms receipt mismatch")
        stratum = normalized_stratum(row["temporal_stratum"])
        if row["strict_effect_eligible"] != (stratum == "strict_effect_eligible"):
            raise CoverageError("transition strict-effect receipt mismatch")
        key = identity_sha256(row)
        if key in parsed:
            raise CoverageError("duplicate canonical pair identity in transition escrow")
        parsed[key] = {
            "parts": identity_parts(row),
            "orientation": (row["left"], row["right"]),
            "native_id": native,
            "stratum": stratum,
            "nontie_all_arms": derived_nontie,
            "parent_source_present": row["parent_source_present"],
            "source_novel": row["source_novel"],
        }
    return parsed


def source_inventory(parsed: dict[str, dict[str, Any]]) -> dict[str, Any]:
    task_counts = Counter(item["parts"][0] for item in parsed.values())
    run_counts = Counter(item["parts"][1] for item in parsed.values())
    stratum_counts = Counter(item["stratum"] for item in parsed.values())
    dominant_task, dominant_count = max(task_counts.items(), key=lambda item: (item[1], item[0]))
    return {
        "pairs": len(parsed),
        "runs": len(run_counts),
        "tasks": len(task_counts),
        "strata": dict(sorted(stratum_counts.items())),
        "pairs_per_task": dict(sorted(task_counts.items())),
        "dominant_task": dominant_task,
        "dominant_task_pairs": dominant_count,
        "dominant_task_share": dominant_count / len(parsed),
        "nontie_all_arms_pairs": sum(item["nontie_all_arms"] for item in parsed.values()),
        "canonical_identity_mapping_sha256": mapping_sha256(sorted(parsed)),
        "native_identity_mapping_sha256": mapping_sha256(
            [[key, parsed[key]["native_id"]] for key in sorted(parsed)]
        ),
    }


def build_matrix(
    wl_pairs_path: str | Path,
    wl_pairs_sha256: str,
    wl_summary_path: str | Path,
    wl_summary_sha256: str,
    transition_pairs_path: str | Path,
    transition_pairs_sha256: str,
    transition_summary_path: str | Path,
    transition_summary_sha256: str,
    expected_snapshot_sha256: str,
) -> dict[str, Any]:
    if SHA256_RE.fullmatch(expected_snapshot_sha256 or "") is None:
        raise CoverageError("invalid expected snapshot SHA-256")
    wl_path, wl_raw = checked_bytes(wl_pairs_path, wl_pairs_sha256)
    wls_path, wls_raw = checked_bytes(wl_summary_path, wl_summary_sha256)
    tr_path, tr_raw = checked_bytes(transition_pairs_path, transition_pairs_sha256)
    trs_path, trs_raw = checked_bytes(transition_summary_path, transition_summary_sha256)
    wl_summary = load_object(wls_path, wls_raw)
    transition_summary = load_object(trs_path, trs_raw)
    summary_scope(wl_summary, expected_snapshot_sha256, wl_pairs_sha256, "wl")
    summary_scope(transition_summary, expected_snapshot_sha256, transition_pairs_sha256, "transition")
    wl = parse_wl(load_rows(wl_path, wl_raw, WL_FIELDS))
    transition = parse_transition(load_rows(tr_path, tr_raw, TRANSITION_FIELDS))

    wl_keys = set(wl)
    transition_keys = set(transition)
    intersection = wl_keys & transition_keys
    union = wl_keys | transition_keys
    same_orientation = 0
    reversed_orientation = 0
    per_stratum: dict[str, int] = {}
    for key in intersection:
        if wl[key]["stratum"] != transition[key]["stratum"]:
            raise CoverageError("overlapping pair has inconsistent temporal stratum")
        stratum = wl[key]["stratum"]
        per_stratum[stratum] = per_stratum.get(stratum, 0) + 1
        if wl[key]["orientation"] == transition[key]["orientation"]:
            same_orientation += 1
        elif wl[key]["orientation"] == tuple(reversed(transition[key]["orientation"])):
            reversed_orientation += 1
        else:
            raise CoverageError("canonical overlap has inconsistent endpoints")

    return {
        "protocol": PROTOCOL,
        "formal_status": "OUTCOME_BLIND_PREDICTION_COVERAGE_VERIFIED",
        "snapshot_sha256": expected_snapshot_sha256,
        "inputs": {
            "wl_pairs_sha256": wl_pairs_sha256,
            "wl_summary_sha256": wl_summary_sha256,
            "transition_pairs_sha256": transition_pairs_sha256,
            "transition_summary_sha256": transition_summary_sha256,
        },
        "arms": {
            "wl": list(WL_ARMS),
            "transition": list(TRANSITION_ARMS),
            "total": len(WL_ARMS) + len(TRANSITION_ARMS),
        },
        "inventory": {
            "wl": source_inventory(wl),
            "transition": source_inventory(transition),
        },
        "overlap": {
            "intersection_pairs": len(intersection),
            "union_pairs": len(union),
            "intersection_over_union": len(intersection) / len(union),
            "wl_covered_by_transition": len(intersection) / len(wl),
            "transition_covered_by_wl": len(intersection) / len(transition),
            "wl_only_pairs": len(wl_keys - transition_keys),
            "transition_only_pairs": len(transition_keys - wl_keys),
            "same_left_right_orientation": same_orientation,
            "reversed_left_right_orientation": reversed_orientation,
            "pairs_per_stratum": dict(sorted(per_stratum.items())),
            "intersection_mapping_sha256": mapping_sha256(sorted(intersection)),
        },
        "transition_support_receipts": {
            "parent_source_present_pairs": sum(
                item["parent_source_present"] for item in transition.values()
            ),
            "source_novel_pairs": sum(item["source_novel"] for item in transition.values()),
        },
        "cost_boundary": {
            "input_artifact_bytes": {
                "wl_pairs": len(wl_raw),
                "wl_summary": len(wls_raw),
                "transition_pairs": len(tr_raw),
                "transition_summary": len(trs_raw),
            },
            "shared_runtime_receipt_available": False,
            "runtime_or_query_cost_comparison": "NOT_COMPUTED",
        },
        "criteria": {
            "input_hashes_verified": True,
            "same_snapshot_verified": True,
            "blind_scope_verified": True,
            "duplicate_canonical_pairs_eq_0": True,
            "seven_arm_prediction_fields_complete": True,
            "overlap_strata_consistent": True,
        },
        "access_attestation": {
            "labels_grades_outcomes_or_winner_orientation_read": False,
            "prediction_values_aggregated": False,
            "accuracy_effect_or_search_utility_computed": False,
            "gpu_or_api_calls": 0,
            "base_llm_updates": 0,
        },
    }


def write_once(path_value: str | Path, value: dict[str, Any]) -> None:
    unresolved = Path(path_value)
    if unresolved.is_symlink() or unresolved.exists():
        raise CoverageError("output path already exists or is symlinked")
    path = unresolved.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    if temporary.exists():
        raise CoverageError("temporary output path already exists")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wl-pairs", required=True)
    parser.add_argument("--expect-wl-pairs-sha256", required=True)
    parser.add_argument("--wl-summary", required=True)
    parser.add_argument("--expect-wl-summary-sha256", required=True)
    parser.add_argument("--transition-pairs", required=True)
    parser.add_argument("--expect-transition-pairs-sha256", required=True)
    parser.add_argument("--transition-summary", required=True)
    parser.add_argument("--expect-transition-summary-sha256", required=True)
    parser.add_argument("--expect-snapshot-sha256", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        matrix = build_matrix(
            args.wl_pairs,
            args.expect_wl_pairs_sha256,
            args.wl_summary,
            args.expect_wl_summary_sha256,
            args.transition_pairs,
            args.expect_transition_pairs_sha256,
            args.transition_summary,
            args.expect_transition_summary_sha256,
            args.expect_snapshot_sha256,
        )
        write_once(args.output, matrix)
    except (CoverageError, OSError) as exc:
        print(f"PREDICTION_COVERAGE_FAIL type={type(exc).__name__}", file=os.sys.stderr)
        return 2
    print(
        "PREDICTION_COVERAGE_PASS "
        f"wl={matrix['inventory']['wl']['pairs']} "
        f"transition={matrix['inventory']['transition']['pairs']} "
        f"intersection={matrix['overlap']['intersection_pairs']} "
        f"arms={matrix['arms']['total']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
