"""Independent verifier for the frozen v9 anytime-oracle audit.

This deliberately does not import the analysis implementation.  It recomputes
the card-level accounting from locked raw inputs and compares every reported
aggregate used in the scientific interpretation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


LOCKS = {
    "manifest": "77f696828010e2d6ae10a9b9de2d9ec05d44975b1285ea763d9850a7f30ca4ef",
    "results": "b1266d04912596b1e37e13f79ce2387a962f5510cfa264aa1a97b7a1c443180d",
    "runtime": "dff8eb88a1db8d63bab17851c1dce2c1bd389a4744a811d65a5ce1fe5a1f55e7",
    "run_map": "3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30",
    "orientation": "e11111a3538c54eb91048b54380466b4dc0f041c2f511a78a85573cbc92b121a",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="phase1/fidelity_manifest.jsonl")
    parser.add_argument("--results", default="phase1/fidelity_results.jsonl")
    parser.add_argument("--runtime", default="phase1/fidelity_runtime_v9.jsonl")
    parser.add_argument("--run-map", default="phase1/card_run_map.json")
    parser.add_argument("--orientation", default="phase1/task_orientation.json")
    parser.add_argument("--reported", default="phase1/anytime_oracle_headroom_v9.json")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(row) for row in path.read_text(encoding="utf-8").splitlines() if row.strip()]


def is_score(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def optimum(items: set[str], values: dict[str, float], lower_is_better: bool) -> set[str]:
    signed = {item: (-values[item] if lower_is_better else values[item]) for item in items}
    maximum = max(signed.values())
    return {item for item, value in signed.items() if abs(value - maximum) <= 1e-12}


def nearest_rank(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]


def assert_close(label: str, actual: float, expected: object, tolerance: float = 1e-12) -> None:
    if not isinstance(expected, (int, float)) or isinstance(expected, bool):
        raise AssertionError(f"{label}: reported value is not numeric: {expected!r}")
    if not math.isclose(actual, float(expected), rel_tol=0.0, abs_tol=tolerance):
        raise AssertionError(f"{label}: recomputed={actual!r} reported={expected!r}")


def main() -> None:
    args = parse_args()
    paths = {
        "manifest": Path(args.manifest),
        "results": Path(args.results),
        "runtime": Path(args.runtime),
        "run_map": Path(args.run_map),
        "orientation": Path(args.orientation),
    }
    observed_hashes = {name: sha256(path) for name, path in paths.items()}
    if observed_hashes != LOCKS:
        raise AssertionError(f"input lock mismatch: {observed_hashes}")

    manifest_rows = jsonl(paths["manifest"])
    cards = {str(row["card_id"]): row for row in manifest_rows}
    if len(cards) != 230 or len(cards) != len(manifest_rows):
        raise AssertionError("manifest cardinality or card uniqueness changed")

    result_rows = jsonl(paths["results"])
    result_grid = {(str(row["card_id"]), int(row["cap"])): row for row in result_rows}
    expected_grid = {(card, cap) for card in cards for cap in (30, 120)}
    if len(result_grid) != len(result_rows) or set(result_grid) != expected_grid:
        raise AssertionError("fidelity result grid changed")

    runtime_rows = jsonl(paths["runtime"])
    runtime = {str(row["card_id"]): float(row["runtime_s"]) for row in runtime_rows}
    if len(runtime) != len(runtime_rows) or set(runtime) != set(cards):
        raise AssertionError("runtime grid changed")
    if any(not math.isfinite(value) or value < 0 for value in runtime.values()):
        raise AssertionError("invalid historical runtime")

    run_map = json.loads(paths["run_map"].read_text(encoding="utf-8"))
    orientation = json.loads(paths["orientation"].read_text(encoding="utf-8"))
    if not set(cards).issubset(run_map):
        missing_run_ids = sorted(set(cards) - set(run_map))
        raise AssertionError(f"run-map misses frozen cards: {missing_run_ids[:3]}")

    siblings: dict[str, set[str]] = defaultdict(set)
    for card, row in cards.items():
        siblings[str(row["parent"])].add(card)
    if len(siblings) != 100 or sum(map(len, siblings.values())) != 230:
        raise AssertionError("sibling partition changed")

    observed_runtime: list[float] = []
    missing_runtime: list[float] = []
    all_runs: set[str] = set()
    all_tasks: set[str] = set()
    winner_any_missing = 0
    winner_all_missing = 0
    current_pruned_cards = 0
    oracle_pruned_cards = 0
    current_pruned_runtime = 0.0
    oracle_pruned_runtime = 0.0
    current_tail = 0.0
    oracle_tail = 0.0
    total_runtime = sum(runtime.values())
    total_probe = 0.0

    for parent, members in siblings.items():
        tasks = {str(cards[card]["competition"]) for card in members}
        runs = {str(run_map[card]) for card in members}
        if len(members) < 2 or len(tasks) != 1 or len(runs) != 1:
            raise AssertionError(f"invalid sibling set {parent}")
        task = next(iter(tasks))
        all_tasks.add(task)
        all_runs.update(runs)
        lower_is_better = bool(orientation[task])

        final_values = {card: float(cards[card]["graded"]) for card in members}
        final_winners = optimum(members, final_values, lower_is_better)
        scored = {
            card
            for card in members
            if is_score(result_grid[(card, 120)].get("sub_score"))
        }
        silent = members - scored
        early_values = {
            card: float(result_grid[(card, 120)]["sub_score"])
            for card in scored
        }
        observed_runtime.extend(runtime[card] for card in scored)
        missing_runtime.extend(runtime[card] for card in silent)
        winner_any_missing += int(bool(final_winners & silent))
        winner_all_missing += int(final_winners <= silent)

        # Frozen censor-aware policy: abstain on every silent candidate and retain
        # all ties for the best observed pristine score.
        current_kept = set(silent)
        if scored:
            current_kept |= optimum(scored, early_values, lower_is_better)
        else:
            current_kept |= members
        current_pruned = members - current_kept
        oracle_pruned = members - final_winners

        for card in members:
            probe = float(result_grid[(card, 120)]["wall_s"])
            if not math.isfinite(probe) or probe < 0:
                raise AssertionError(f"invalid probe wall time for {card}")
            total_probe += probe
        current_pruned_cards += len(current_pruned)
        oracle_pruned_cards += len(oracle_pruned)
        current_pruned_runtime += sum(runtime[card] for card in current_pruned)
        oracle_pruned_runtime += sum(runtime[card] for card in oracle_pruned)
        current_tail += sum(
            max(runtime[card] - float(result_grid[(card, 120)]["wall_s"]), 0.0)
            for card in current_pruned
        )
        oracle_tail += sum(
            max(runtime[card] - float(result_grid[(card, 120)]["wall_s"]), 0.0)
            for card in oracle_pruned
        )

    reported = json.loads(Path(args.reported).read_text(encoding="utf-8"))
    if reported.get("inputs") != LOCKS:
        raise AssertionError("reported input locks changed")
    counts = reported["counts"]
    expected_counts = {
        "sets": len(siblings),
        "cards": len(cards),
        "runs": len(all_runs),
        "tasks": len(all_tasks),
    }
    if counts != expected_counts:
        raise AssertionError(f"count mismatch: {counts} != {expected_counts}")

    missing = reported["selective_missingness"]
    exact_missing = {
        "observed_cards": len(observed_runtime),
        "missing_cards": len(missing_runtime),
        "sets_any_final_winner_missing": winner_any_missing,
        "sets_all_final_winners_missing": winner_all_missing,
    }
    for key, value in exact_missing.items():
        if missing.get(key) != value:
            raise AssertionError(f"{key}: recomputed={value} reported={missing.get(key)}")
    assert_close("observed runtime median", statistics.median(observed_runtime), missing["observed_runtime_median_s"])
    assert_close("missing runtime median", statistics.median(missing_runtime), missing["missing_runtime_median_s"])
    expected_observed_quartiles = [nearest_rank(observed_runtime, 0.25), nearest_rank(observed_runtime, 0.75)]
    expected_missing_quartiles = [nearest_rank(missing_runtime, 0.25), nearest_rank(missing_runtime, 0.75)]
    if missing["observed_runtime_q25_q75_s"] != expected_observed_quartiles:
        raise AssertionError("observed runtime quartiles mismatch")
    if missing["missing_runtime_q25_q75_s"] != expected_missing_quartiles:
        raise AssertionError("missing runtime quartiles mismatch")

    current = reported["current_censor_aware"]
    oracle = reported["perfect_score_at_120_hindsight_oracle"]
    current_metrics = {
        "pruned_cards": current_pruned_cards,
        "pruned_card_fraction": current_pruned_cards / len(cards),
        "pruned_full_runtime_fraction": current_pruned_runtime / total_runtime,
        "optimistic_avoidable_tail_fraction": current_tail / total_runtime,
    }
    oracle_metrics = {
        "pruned_cards": oracle_pruned_cards,
        "pruned_card_fraction": oracle_pruned_cards / len(cards),
        "pruned_full_runtime_fraction": oracle_pruned_runtime / total_runtime,
        "optimistic_avoidable_tail_fraction": oracle_tail / total_runtime,
        "optimistic_resume_cost_ratio": 1.0 - oracle_tail / total_runtime,
        "pessimistic_restart_cost_ratio": (total_probe + total_runtime - oracle_pruned_runtime) / total_runtime,
    }
    for key, value in current_metrics.items():
        if key == "pruned_cards":
            if current.get(key) != value:
                raise AssertionError(f"current {key} mismatch")
        else:
            assert_close(f"current {key}", value, current.get(key))
    for key, value in oracle_metrics.items():
        if key == "pruned_cards":
            if oracle.get(key) != value:
                raise AssertionError(f"oracle {key} mismatch")
        else:
            assert_close(f"oracle {key}", value, oracle.get(key))

    guard = reported.get("interpretation_guard", {})
    if guard.get("uses_final_grade_for_oracle") is not True or guard.get("actual_speedup_claim_allowed") is not False:
        raise AssertionError("interpretation guard missing or weakened")
    print(
        "ANYTIME_ORACLE_INDEPENDENT_VERIFY_PASS",
        f"sets={len(siblings)}",
        f"observed={len(observed_runtime)}",
        f"missing={len(missing_runtime)}",
        f"winner_all_missing_sets={winner_all_missing}",
        f"current_tail={current_tail / total_runtime:.6f}",
        f"oracle_tail={oracle_tail / total_runtime:.6f}",
    )


if __name__ == "__main__":
    main()
