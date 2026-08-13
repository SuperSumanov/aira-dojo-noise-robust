#!/usr/bin/env python3
"""Second, outcome-blind verifier for the frozen SPT pilot.

This intentionally does not import the primary verifier or worker.  It reads the
raw manifest, status files, and result JSON files and recomputes the preregistered
K0--K5 gates through a separate implementation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


ARMS = {"original_a", "original_b", "tap"}
IDENTITY_FIELDS = (
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
)


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def is_finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def score_of(event: object) -> float | None:
    if not isinstance(event, dict):
        return None
    grade = event.get("grade")
    value = grade.get("sub_score") if isinstance(grade, dict) else None
    return float(value) if is_finite_number(value) else None


def valid_endpoint(result: dict) -> tuple[float, str, float] | None:
    events = result.get("submission_events")
    if result.get("final_rc") != 0 or not isinstance(events, list) or not events:
        return None
    final = events[-1]
    score = score_of(final)
    sha = final.get("sub_sha256") if isinstance(final, dict) else None
    elapsed = final.get("first_seen_elapsed_s") if isinstance(final, dict) else None
    if (
        score is None
        or not isinstance(sha, str)
        or len(sha) != 64
        or not is_finite_number(elapsed)
        or final.get("sub_source_changed_during_copy") is not False
        or final.get("source_signature") != result.get("submission_final_signature")
    ):
        return None
    return score, sha, float(elapsed)


def valid_probe(result: dict) -> tuple[float, str, float] | None:
    event = result.get("probe")
    markers = result.get("probe_markers")
    if result.get("arm") != "tap" or not isinstance(event, dict):
        return None
    score = score_of(event)
    sha = event.get("sub_sha256")
    elapsed = event.get("first_seen_elapsed_s")
    if (
        score is None
        or not isinstance(sha, str)
        or len(sha) != 64
        or not is_finite_number(elapsed)
        or result.get("probe_mutated_after_capture") is not False
        or event.get("sub_source_changed_during_copy") is not False
        or event.get("source_signature") != result.get("probe_final_signature")
        or not isinstance(markers, list)
        or len(markers) != 1
        or not isinstance(markers[0], dict)
        or markers[0].get("sha256") != sha
    ):
        return None
    return score, sha, float(elapsed)


def load_json_lines(path: Path) -> list[dict]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"non-object manifest row {line_number}")
        rows.append(row)
    return rows


def load_single_jsons(paths: list[Path], label: str) -> list[dict]:
    rows = []
    for path in paths:
        row = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(row, dict):
            raise ValueError(f"non-object {label}: {path}")
        rows.append(row)
    return rows


def calculate(args: argparse.Namespace) -> dict:
    failures: list[str] = []
    actual_manifest_sha = digest(args.manifest)
    if actual_manifest_sha != args.manifest_sha256:
        failures.append("manifest_sha256")
    manifest = load_json_lines(args.manifest)
    if len(manifest) != 18:
        failures.append(f"manifest_count={len(manifest)}")
    indices = [row.get("index") for row in manifest]
    if indices != list(range(18)):
        failures.append("manifest_index_grid")
    if any(row.get("arm") not in ARMS for row in manifest):
        failures.append("manifest_arm_grid")

    status_paths = sorted(args.status_dir.glob("index_*.json"))
    statuses = load_single_jsons(status_paths, "status")
    status_by_index: dict[int, dict] = {}
    for status in statuses:
        index = status.get("index")
        if not isinstance(index, int) or index in status_by_index:
            failures.append("status_duplicate_or_bad_index")
            continue
        status_by_index[index] = status
        command_sha = status.get("command_sha256")
        if status.get("return_code") != 0:
            failures.append(f"status_rc_index={index}")
        if not isinstance(command_sha, str) or len(command_sha) != 64:
            failures.append(f"status_command_sha_index={index}")
    if set(status_by_index) != set(range(18)):
        failures.append(f"status_grid={sorted(status_by_index)}")

    result_paths = sorted(args.results.glob("index_*/result.json"))
    results = load_single_jsons(result_paths, "result")
    result_by_index: dict[int, dict] = {}
    for result in results:
        index = result.get("index")
        if not isinstance(index, int) or index in result_by_index:
            failures.append("result_duplicate_or_bad_index")
            continue
        result_by_index[index] = result
    if set(result_by_index) != set(range(18)):
        failures.append(f"result_grid={sorted(result_by_index)}")

    if failures:
        return {
            "schema_version": 1,
            "verifier": "independent_raw_v1",
            "verdict": "INVALID",
            "k0_complete_provenance": False,
            "failures": failures,
        }

    triplets: dict[str, dict[str, dict]] = defaultdict(dict)
    for expected in manifest:
        result = result_by_index[expected["index"]]
        for field in IDENTITY_FIELDS:
            if result.get(field) != expected.get(field):
                failures.append(f"drift_index={expected['index']}_field={field}")
        if result.get("manifest_sha256") != args.manifest_sha256:
            failures.append(f"worker_manifest_sha_index={expected['index']}")
        if expected["arm"] != "tap" and result.get("probe") is not None:
            failures.append(f"reserved_probe_index={expected['index']}")
        arm_map = triplets[expected["card_id"]]
        if expected["arm"] in arm_map:
            failures.append(f"duplicate_arm_card={expected['card_id']}")
        arm_map[expected["arm"]] = result

    if len(triplets) != 6:
        failures.append(f"card_count={len(triplets)}")
    for card_id, arm_map in triplets.items():
        if set(arm_map) != ARMS:
            failures.append(f"arm_triplet_card={card_id}")

    if failures:
        return {
            "schema_version": 1,
            "verifier": "independent_raw_v1",
            "verdict": "INVALID",
            "k0_complete_provenance": False,
            "failures": failures,
        }

    cards = []
    for card_id in sorted(triplets):
        arm_map = triplets[card_id]
        end_a = valid_endpoint(arm_map["original_a"])
        end_b = valid_endpoint(arm_map["original_b"])
        end_t = valid_endpoint(arm_map["tap"])
        tapped = valid_probe(arm_map["tap"])
        baseline_valid = end_a is not None and end_b is not None
        equivalent = False
        mode = None
        baseline_elapsed = None
        relative_gain = None
        if baseline_valid:
            assert end_a is not None and end_b is not None
            baseline_elapsed = statistics.median([end_a[2], end_b[2]])
            if end_t is not None:
                if end_a[1] == end_b[1]:
                    equivalent = end_t[1] == end_a[1]
                    mode = "exact_hash"
                else:
                    original_span = abs(end_a[0] - end_b[0])
                    nearest = min(abs(end_t[0] - end_a[0]), abs(end_t[0] - end_b[0]))
                    equivalent = nearest <= max(original_span, 1e-8)
                    mode = "within_original_replicate_span"
            if tapped is not None:
                relative_gain = (baseline_elapsed - tapped[2]) / max(baseline_elapsed, 1e-8)
        cards.append(
            {
                "card_id": card_id,
                "baseline_valid": baseline_valid,
                "tap_endpoint_valid": end_t is not None,
                "tap_probe_valid": tapped is not None,
                "tap_probe_by_120": tapped is not None and tapped[2] <= 120.0,
                "semantics_equal": equivalent,
                "equivalence_mode": mode,
                "relative_feedback_gain": relative_gain,
            }
        )

    baseline_n = sum(row["baseline_valid"] for row in cards)
    probe120_n = sum(row["tap_probe_by_120"] for row in cards)
    semantic_n = sum(row["baseline_valid"] and row["semantics_equal"] for row in cards)
    semantic_rate = semantic_n / baseline_n if baseline_n else None
    gains = [
        row["relative_feedback_gain"]
        for row in cards
        if row["baseline_valid"]
        and row["semantics_equal"]
        and row["tap_probe_by_120"]
        and row["relative_feedback_gain"] is not None
    ]
    median_gain = statistics.median(gains) if gains else None
    gates = {
        "K0_complete_provenance": True,
        "K1_baseline_evaluable_at_least_4_of_6": baseline_n >= 4,
        "K2_finite_probe_by_120_at_least_4_of_6": probe120_n >= 4,
        "K3_semantics_rate_at_least_0p95": semantic_rate is not None and semantic_rate >= 0.95,
        "K4_latency_pairs_at_least_4": len(gains) >= 4,
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
    return {
        "schema_version": 1,
        "verifier": "independent_raw_v1",
        "verdict": verdict,
        "manifest_sha256": actual_manifest_sha,
        "execution_count": len(results),
        "card_count": len(cards),
        "baseline_valid_cards": baseline_n,
        "probe_by_120_cards": probe120_n,
        "semantic_numerator": semantic_n,
        "semantic_denominator": baseline_n,
        "semantic_rate": semantic_rate,
        "latency_pair_count": len(gains),
        "median_relative_feedback_gain": median_gain,
        "gates": gates,
        "cards": cards,
        "failures": [],
    }


def self_test() -> None:
    sha = "a" * 64
    event = {
        "grade": {"sub_score": 0.75},
        "sub_sha256": sha,
        "first_seen_elapsed_s": 15.0,
        "sub_source_changed_during_copy": False,
        "source_signature": [1, 2, 3, 4],
    }
    base = {
        "arm": "tap",
        "final_rc": 0,
        "submission_events": [event],
        "submission_final_signature": [1, 2, 3, 4],
        "probe": event,
        "probe_final_signature": [1, 2, 3, 4],
        "probe_mutated_after_capture": False,
        "probe_markers": [{"sha256": sha}],
    }
    assert valid_endpoint(base) == (0.75, sha, 15.0)
    assert valid_probe(base) == (0.75, sha, 15.0)
    bad = dict(base, probe_mutated_after_capture=True)
    assert valid_probe(bad) is None
    print("SPT_RAW_VERIFIER_SELF_TEST_PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--results", type=Path)
    parser.add_argument("--status-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if None in (args.manifest, args.manifest_sha256, args.results, args.status_dir, args.output):
        parser.error("manifest, hash, results, status-dir, and output are required")
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    report = calculate(args)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="",
    )
    print(
        "SPT_RAW_VERDICT "
        f"verdict={report['verdict']} "
        f"baseline={report.get('baseline_valid_cards')}/6 "
        f"probe120={report.get('probe_by_120_cards')}/6 "
        f"semantic={report.get('semantic_numerator')}/{report.get('semantic_denominator')} "
        f"latency_n={report.get('latency_pair_count')} "
        f"median_gain={report.get('median_relative_feedback_gain')}",
        flush=True,
    )


if __name__ == "__main__":
    main()
