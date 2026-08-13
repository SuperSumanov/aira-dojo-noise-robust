#!/usr/bin/env python3
"""Independent, outcome-frozen verifier for the SPT feasibility pilot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


ARMS = ("original_a", "original_b", "tap")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def atomic_json(path: Path, payload: object) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")


def atomic_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise RuntimeError(f"refusing empty CSV: {path}")
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def grade_score(record: dict | None) -> float | None:
    if not isinstance(record, dict):
        return None
    grade = record.get("grade")
    value = grade.get("sub_score") if isinstance(grade, dict) else None
    return float(value) if finite(value) else None


def endpoint(result: dict) -> dict | None:
    events = result.get("submission_events")
    if result.get("final_rc") != 0 or not isinstance(events, list) or not events:
        return None
    row = events[-1]
    score = grade_score(row)
    signature = row.get("source_signature")
    if (
        score is None
        or not isinstance(row.get("sub_sha256"), str)
        or row.get("sub_source_changed_during_copy") is not False
        or signature != result.get("submission_final_signature")
    ):
        return None
    return {
        "score": score,
        "sha256": row["sub_sha256"],
        "elapsed_s": float(row["first_seen_elapsed_s"]),
        "event_count": len(events),
    }


def probe(result: dict) -> dict | None:
    row = result.get("probe")
    score = grade_score(row)
    if not isinstance(row, dict) or score is None:
        return None
    markers = result.get("probe_markers")
    if (
        result.get("arm") != "tap"
        or result.get("probe_mutated_after_capture") is not False
        or row.get("source_signature") != result.get("probe_final_signature")
        or row.get("sub_source_changed_during_copy") is not False
        or not isinstance(markers, list)
        or len(markers) != 1
        or markers[0].get("sha256") != row.get("sub_sha256")
    ):
        return None
    return {
        "score": score,
        "sha256": row["sub_sha256"],
        "elapsed_s": float(row["first_seen_elapsed_s"]),
    }


def decide(
    baseline_valid_count: int,
    probe_120_count: int,
    semantic_rate: float | None,
    gain_values: list[float],
) -> tuple[dict[str, bool], str, float | None]:
    median_gain = statistics.median(gain_values) if gain_values else None
    gates = {
        "K0_complete_provenance": True,
        "K1_baseline_evaluable_at_least_4_of_6": baseline_valid_count >= 4,
        "K2_finite_probe_by_120_at_least_4_of_6": probe_120_count >= 4,
        "K3_semantics_rate_at_least_0p95": semantic_rate is not None and semantic_rate >= 0.95,
        "K4_latency_pairs_at_least_4": len(gain_values) >= 4,
        "K5_median_relative_feedback_gain_at_least_0p25": median_gain is not None and median_gain >= 0.25,
    }
    if not gates["K1_baseline_evaluable_at_least_4_of_6"]:
        verdict = "INCONCLUSIVE"
    elif not gates["K2_finite_probe_by_120_at_least_4_of_6"]:
        verdict = "NO_TAP_COVERAGE"
    elif not gates["K3_semantics_rate_at_least_0p95"]:
        verdict = "SEMANTICS_KILL"
    elif not gates["K4_latency_pairs_at_least_4"]:
        verdict = "INCONCLUSIVE"
    elif not gates["K5_median_relative_feedback_gain_at_least_0p25"]:
        verdict = "NO_FEEDBACK_ADVANCE"
    else:
        verdict = "PILOT_PASS"
    return gates, verdict, median_gain


def self_test() -> None:
    event = {
        "sub_sha256": "a" * 64,
        "source_signature": [1, 2, 3, 4],
        "sub_source_changed_during_copy": False,
        "first_seen_elapsed_s": 20.0,
        "grade": {"sub_score": 0.7},
    }
    result = {
        "arm": "tap",
        "final_rc": 0,
        "submission_events": [event],
        "submission_final_signature": [1, 2, 3, 4],
        "probe": event,
        "probe_final_signature": [1, 2, 3, 4],
        "probe_mutated_after_capture": False,
        "probe_markers": [{"sha256": "a" * 64}],
    }
    assert endpoint(result) is not None
    assert probe(result) is not None
    assert decide(6, 6, 1.0, [0.5] * 6)[1] == "PILOT_PASS"
    assert decide(6, 3, 1.0, [0.5] * 6)[1] == "NO_TAP_COVERAGE"
    assert decide(6, 6, 0.8, [0.5] * 6)[1] == "SEMANTICS_KILL"
    assert decide(6, 6, 1.0, [0.1] * 6)[1] == "NO_FEEDBACK_ADVANCE"
    assert decide(3, 6, 1.0, [0.5] * 3)[1] == "INCONCLUSIVE"
    print("SPT_PILOT_VERIFIER_SELF_TEST_PASS", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--results", type=Path)
    parser.add_argument("--status-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if None in (args.manifest, args.manifest_sha256, args.results, args.status_dir, args.out):
        parser.error("--manifest --manifest-sha256 --results --status-dir --out are required")
    if args.out.exists():
        raise RuntimeError(f"refusing existing analysis directory: {args.out}")
    if sha256_file(args.manifest) != args.manifest_sha256:
        raise RuntimeError("manifest hash mismatch")
    manifest = [json.loads(line) for line in args.manifest.read_text(encoding="utf-8").splitlines() if line]
    if len(manifest) != 18 or [row["index"] for row in manifest] != list(range(18)):
        raise RuntimeError("manifest grid mismatch")
    status_paths = sorted(args.status_dir.glob("index_*.json"))
    if len(status_paths) != 18:
        raise RuntimeError(f"expected 18 status files, got {len(status_paths)}")
    status_indices: set[int] = set()
    for path in status_paths:
        status = json.loads(path.read_text(encoding="utf-8"))
        index = int(status.get("index", -1))
        if (
            index in status_indices
            or status.get("return_code") != 0
            or not isinstance(status.get("command_sha256"), str)
            or len(status["command_sha256"]) != 64
        ):
            raise RuntimeError(f"invalid infrastructure status: {path}")
        status_indices.add(index)
    if status_indices != set(range(18)):
        raise RuntimeError("status index grid mismatch")
    paths = sorted(args.results.glob("index_*/result.json"))
    if len(paths) != 18:
        raise RuntimeError(f"expected 18 result files, got {len(paths)}")
    results_by_index: dict[int, dict] = {}
    for path in paths:
        result = json.loads(path.read_text(encoding="utf-8"))
        index = int(result.get("index", -1))
        if index in results_by_index:
            raise RuntimeError(f"duplicate result index: {index}")
        results_by_index[index] = result
    if set(results_by_index) != set(range(18)):
        raise RuntimeError("result index grid mismatch")

    execution_rows: list[dict] = []
    by_card: dict[str, dict[str, tuple[dict, dict]]] = defaultdict(dict)
    for expected in manifest:
        result = results_by_index[expected["index"]]
        for key in (
            "index",
            "group_index",
            "group_id",
            "sibling_index",
            "card_id",
            "competition",
            "metric",
            "higher_is_better",
            "run_id",
            "parent_id",
            "arm",
            "seed",
            "code_sha256",
            "base_code_sha256",
            "tap_runtime_sha256",
            "tap_site_count",
            "source_export_sha256",
            "split_sha256",
        ):
            if result.get(key) != expected.get(key):
                raise RuntimeError(f"manifest/result drift index={expected['index']} key={key}")
        if result.get("manifest_sha256") != args.manifest_sha256:
            raise RuntimeError(f"worker manifest hash drift: {expected['index']}")
        found_endpoint = endpoint(result)
        found_probe = probe(result)
        if expected["arm"] != "tap" and result.get("probe") is not None:
            raise RuntimeError(f"original unexpectedly created reserved probe: {expected['index']}")
        execution_rows.append(
            {
                "index": expected["index"],
                "group_index": expected["group_index"],
                "group_id": expected["group_id"],
                "sibling_index": expected["sibling_index"],
                "card_id": expected["card_id"],
                "competition": expected["competition"],
                "metric": expected["metric"],
                "higher_is_better": expected["higher_is_better"],
                "arm": expected["arm"],
                "seed": expected["seed"],
                "tap_site_count": expected["tap_site_count"],
                "final_rc": result.get("final_rc"),
                "wall_s": result.get("wall_s"),
                "submission_events": len(result.get("submission_events") or []),
                "endpoint_valid": found_endpoint is not None,
                "endpoint_score": None if found_endpoint is None else found_endpoint["score"],
                "endpoint_sha256": None if found_endpoint is None else found_endpoint["sha256"],
                "endpoint_elapsed_s": None if found_endpoint is None else found_endpoint["elapsed_s"],
                "probe_valid": found_probe is not None,
                "probe_score": None if found_probe is None else found_probe["score"],
                "probe_sha256": None if found_probe is None else found_probe["sha256"],
                "probe_elapsed_s": None if found_probe is None else found_probe["elapsed_s"],
                "manifest_sha256": args.manifest_sha256,
                "container_sha256": result.get("container_sha256"),
                "base_code_sha256": expected["base_code_sha256"],
                "executed_code_sha256": expected["code_sha256"],
                "tap_runtime_sha256": expected["tap_runtime_sha256"],
            }
        )
        by_card[expected["card_id"]][expected["arm"]] = (result, expected)

    if len(by_card) != 6 or any(set(rows) != set(ARMS) for rows in by_card.values()):
        raise RuntimeError("incomplete card triplets")
    per_card: list[dict] = []
    group_cards: dict[str, list[dict]] = defaultdict(list)
    for card_id, arm_rows in sorted(by_card.items()):
        result_a, expected_a = arm_rows["original_a"]
        result_b, _ = arm_rows["original_b"]
        result_t, _ = arm_rows["tap"]
        end_a, end_b, end_t = endpoint(result_a), endpoint(result_b), endpoint(result_t)
        tap_probe = probe(result_t)
        baseline_valid = end_a is not None and end_b is not None
        tap_endpoint_valid = end_t is not None
        base_span = None
        semantics_equal = False
        equivalence_mode = None
        baseline_endpoint_s = None
        relative_gain = None
        absolute_gain_s = None
        if baseline_valid:
            base_span = abs(end_a["score"] - end_b["score"])
            baseline_endpoint_s = statistics.median((end_a["elapsed_s"], end_b["elapsed_s"]))
            if tap_endpoint_valid:
                if end_a["sha256"] == end_b["sha256"]:
                    semantics_equal = end_t["sha256"] == end_a["sha256"]
                    equivalence_mode = "exact_hash"
                else:
                    tap_distance = min(
                        abs(end_t["score"] - end_a["score"]),
                        abs(end_t["score"] - end_b["score"]),
                    )
                    semantics_equal = tap_distance <= max(base_span, 1e-8)
                    equivalence_mode = "within_original_replicate_span"
            if tap_probe is not None:
                absolute_gain_s = baseline_endpoint_s - tap_probe["elapsed_s"]
                relative_gain = absolute_gain_s / max(baseline_endpoint_s, 1e-8)
        row = {
            "group_index": expected_a["group_index"],
            "group_id": expected_a["group_id"],
            "sibling_index": expected_a["sibling_index"],
            "card_id": card_id,
            "competition": expected_a["competition"],
            "metric": expected_a["metric"],
            "higher_is_better": expected_a["higher_is_better"],
            "tap_site_count": expected_a["tap_site_count"],
            "baseline_valid": baseline_valid,
            "original_a_score": None if end_a is None else end_a["score"],
            "original_b_score": None if end_b is None else end_b["score"],
            "original_score_span": base_span,
            "tap_endpoint_valid": tap_endpoint_valid,
            "tap_endpoint_score": None if end_t is None else end_t["score"],
            "semantics_equal": semantics_equal,
            "equivalence_mode": equivalence_mode,
            "tap_probe_valid": tap_probe is not None,
            "tap_probe_by_120": tap_probe is not None and tap_probe["elapsed_s"] <= 120.0,
            "tap_probe_score": None if tap_probe is None else tap_probe["score"],
            "tap_probe_elapsed_s": None if tap_probe is None else tap_probe["elapsed_s"],
            "baseline_endpoint_elapsed_s": baseline_endpoint_s,
            "absolute_feedback_gain_s": absolute_gain_s,
            "relative_feedback_gain": relative_gain,
        }
        per_card.append(row)
        group_cards[expected_a["group_id"]].append(row)

    per_group: list[dict] = []
    for group_id, cards in sorted(group_cards.items()):
        if len(cards) != 2:
            raise RuntimeError(f"group does not contain two siblings: {group_id}")
        reference_ready = all(card["baseline_valid"] for card in cards)
        probe_ready = all(card["tap_probe_valid"] and card["semantics_equal"] for card in cards)
        rank_correct = None
        reference_gap = None
        probe_gap = None
        if reference_ready and probe_ready:
            orientations = {1.0 if card["higher_is_better"] else -1.0 for card in cards}
            if len(orientations) != 1:
                raise RuntimeError(f"orientation drift within group: {group_id}")
            orientation = orientations.pop()
            reference_values = [
                orientation * statistics.median((card["original_a_score"], card["original_b_score"]))
                for card in cards
            ]
            probe_values = [orientation * card["tap_probe_score"] for card in cards]
            reference_gap = abs(reference_values[0] - reference_values[1])
            probe_gap = abs(probe_values[0] - probe_values[1])
            if reference_gap > 1e-12:
                rank_correct = (reference_values[0] > reference_values[1]) == (
                    probe_values[0] > probe_values[1]
                )
        per_group.append(
            {
                "group_id": group_id,
                "group_index": cards[0]["group_index"],
                "competition": cards[0]["competition"],
                "reference_ready": reference_ready,
                "probe_ready": probe_ready,
                "reference_oriented_gap": reference_gap,
                "probe_oriented_gap": probe_gap,
                "tap_sibling_rank_correct": rank_correct,
            }
        )

    baseline_valid_count = sum(row["baseline_valid"] for row in per_card)
    probe_120_count = sum(row["tap_probe_by_120"] for row in per_card)
    semantic_denominator = baseline_valid_count
    semantic_numerator = sum(
        row["baseline_valid"] and row["semantics_equal"] for row in per_card
    )
    semantic_rate = (
        semantic_numerator / semantic_denominator if semantic_denominator else None
    )
    gain_values = [
        row["relative_feedback_gain"]
        for row in per_card
        if row["baseline_valid"]
        and row["semantics_equal"]
        and row["tap_probe_by_120"]
        and row["relative_feedback_gain"] is not None
    ]
    rank_values = [row["tap_sibling_rank_correct"] for row in per_group if row["tap_sibling_rank_correct"] is not None]
    gates, verdict, median_gain = decide(
        baseline_valid_count, probe_120_count, semantic_rate, gain_values
    )
    summary = {
        "schema_version": 1,
        "verdict": verdict,
        "claim_scope": "feasibility/mechanism pilot only; no population effect or p-value",
        "manifest_sha256": args.manifest_sha256,
        "execution_count": len(execution_rows),
        "card_count": len(per_card),
        "group_count": len(per_group),
        "baseline_valid_cards": baseline_valid_count,
        "probe_by_120_cards": probe_120_count,
        "semantic_numerator": semantic_numerator,
        "semantic_denominator": semantic_denominator,
        "semantic_rate": semantic_rate,
        "latency_pair_count": len(gain_values),
        "median_relative_feedback_gain": median_gain,
        "sibling_rank_correct": sum(value is True for value in rank_values),
        "sibling_rank_evaluable": len(rank_values),
        "gates": gates,
    }
    args.out.mkdir(parents=True)
    atomic_csv(args.out / "per_execution.csv", execution_rows)
    atomic_csv(args.out / "per_card.csv", per_card)
    atomic_csv(args.out / "per_group.csv", per_group)
    atomic_json(args.out / "summary.json", summary)
    (args.out / "verdict.txt").write_text(verdict + "\n", encoding="utf-8", newline="")
    print(
        "SPT_PILOT_VERDICT "
        f"verdict={verdict} baseline={baseline_valid_count}/6 probe120={probe_120_count}/6 "
        f"semantic={semantic_numerator}/{semantic_denominator} latency_n={len(gain_values)} "
        f"median_gain={median_gain} rank={sum(value is True for value in rank_values)}/{len(rank_values)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
