"""Independent critical-path verifier for the external PBE pair audit."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path, PurePosixPath

import pyarrow.parquet as pq


LOCKS = {
    "official_parquet": "79363b7ef0b6154061f18e81f6c6fdf380e71ae3f1d7b9a262cc79acb08f0b5f",
    "our_b0": "33df48f8c9b54f60e6e3f100b9269e5e3950c506c8ff98601a61848e197ede50",
}


def cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--official-parquet", default="/tmp/pbe_predict_before_execute.parquet")
    parser.add_argument("--our-b0", default="phase1/decision_clean_b0.jsonl")
    parser.add_argument("--reported-json", default="phase1/pbe_external_pair_audit.json")
    parser.add_argument("--reported-csv", default="phase1/pbe_external_pair_audit_per_task.csv")
    return parser.parse_args()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def official_task(path: str) -> str:
    marker = "/solutions_subset_50/"
    if marker not in path:
        raise AssertionError(path)
    tail = path.split(marker, 1)[1]
    task = tail.split("/", 1)[0]
    if not task:
        raise AssertionError(path)
    return task


def trajectory_key(path: str) -> str:
    stem = PurePosixPath(path).stem
    before, separator, _ = stem.rpartition("_run_")
    if not separator or not before:
        raise AssertionError(path)
    return before


def close(label: str, first: float, second: object) -> None:
    if not isinstance(second, (int, float)) or isinstance(second, bool):
        raise AssertionError(f"{label} reported nonnumeric: {second!r}")
    if not math.isclose(first, float(second), rel_tol=0.0, abs_tol=1e-12):
        raise AssertionError(f"{label}: {first!r} != {second!r}")


def main() -> None:
    args = cli()
    official_path = Path(args.official_parquet)
    own_path = Path(args.our_b0)
    locks = {"official_parquet": digest(official_path), "our_b0": digest(own_path)}
    if locks != LOCKS:
        raise AssertionError(f"input locks changed: {locks}")

    table = pq.read_table(official_path, columns=["paths", "scores"])
    external_gap: dict[str, list[float]] = collections.defaultdict(list)
    external_paths: dict[str, set[str]] = collections.defaultdict(set)
    appearances: collections.Counter[str] = collections.Counter()
    unordered_pairs: set[tuple[str, str]] = set()
    same_trajectory = 0
    for index, row in enumerate(table.to_pylist()):
        paths = tuple(str(value) for value in row["paths"])
        scores = tuple(float(value) for value in row["scores"])
        if len(paths) != 2 or len(scores) != 2:
            raise AssertionError(index)
        tasks = {official_task(path) for path in paths}
        if len(tasks) != 1:
            raise AssertionError(f"cross-task row {index}")
        task = next(iter(tasks))
        external_gap[task].append(abs(scores[0] - scores[1]))
        external_paths[task].update(paths)
        appearances.update(paths)
        pair = tuple(sorted(paths))
        if pair in unordered_pairs:
            raise AssertionError(f"duplicate official pair {index}")
        unordered_pairs.add(pair)
        same_trajectory += int(trajectory_key(paths[0]) == trajectory_key(paths[1]))

    own_gap: dict[str, list[float]] = collections.defaultdict(list)
    own_nonfinite = []
    own_pairs: set[tuple[str, str]] = set()
    own_rows = [json.loads(line) for line in own_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for index, row in enumerate(own_rows):
        gap = float(row["gap_raw"])
        if not math.isfinite(gap):
            own_nonfinite.append(index)
            continue
        if gap < 0:
            raise AssertionError(f"negative own gap {index}")
        own_gap[str(row["task"])].append(gap)
        pair = tuple(sorted((str(row["better"]), str(row["worse"]))))
        if pair in own_pairs:
            raise AssertionError(f"duplicate own pair {index}")
        own_pairs.add(pair)

    common = sorted(set(external_gap) & set(own_gap))
    ext_all = [gap for values in external_gap.values() for gap in values]
    own_all = [gap for values in own_gap.values() for gap in values]
    ext_common = [gap for task in common for gap in external_gap[task]]
    own_common = [gap for task in common for gap in own_gap[task]]
    ext_hard = sum(gap < 1e-2 for gap in ext_all)
    own_hard = sum(gap < 1e-2 for gap in own_all)
    ext_common_hard = sum(gap < 1e-2 for gap in ext_common)
    own_common_hard = sum(gap < 1e-2 for gap in own_common)
    directional_tasks = sum(
        (sum(gap < 1e-2 for gap in own_gap[task]) / len(own_gap[task]))
        > (sum(gap < 1e-2 for gap in external_gap[task]) / len(external_gap[task]))
        for task in common
    )

    reported = json.loads(Path(args.reported_json).read_text(encoding="utf-8"))
    if reported["input_locks"] != LOCKS:
        raise AssertionError("reported locks changed")
    external_report = reported["official"]
    own_report = reported["our_b0"]
    common_report = reported["common_tasks"]
    exact_checks = {
        "official rows": (table.num_rows, external_report["rows"]),
        "official tasks": (len(external_gap), external_report["tasks"]),
        "official solutions": (len(appearances), external_report["unique_solution_paths"]),
        "official pairs": (len(unordered_pairs), external_report["unique_unordered_pairs"]),
        "official same trajectory": (same_trajectory, external_report["same_trajectory_pairs"]),
        "official hard": (ext_hard, external_report["gap"]["hard_lt_1e2_pairs"]),
        "own rows total": (len(own_rows), own_report["rows_total"]),
        "own finite": (len(own_all), own_report["rows_finite_gap"]),
        "own nonfinite": (len(own_nonfinite), own_report["rows_excluded_nonfinite_gap"]),
        "own pairs": (len(own_pairs), own_report["unique_unordered_pairs"]),
        "own hard": (own_hard, own_report["gap"]["hard_lt_1e2_pairs"]),
        "common tasks": (len(common), len(common_report["names"])),
        "external common hard": (ext_common_hard, common_report["official"]["hard_lt_1e2_pairs"]),
        "own common hard": (own_common_hard, common_report["our_b0"]["hard_lt_1e2_pairs"]),
    }
    for label, (actual, expected) in exact_checks.items():
        if actual != expected:
            raise AssertionError(f"{label}: {actual} != {expected}")
    if common_report["names"] != common:
        raise AssertionError("common-task names changed")
    if own_nonfinite != [1013]:
        raise AssertionError(f"unexpected nonfinite rows: {own_nonfinite}")

    close("official same trajectory share", same_trajectory / table.num_rows, external_report["same_trajectory_share_of_parseable"])
    close("official hard share", ext_hard / len(ext_all), external_report["gap"]["hard_lt_1e2_pair_share"])
    close("own hard share", own_hard / len(own_all), own_report["gap"]["hard_lt_1e2_pair_share"])
    close("external common hard share", ext_common_hard / len(ext_common), common_report["official"]["hard_lt_1e2_pair_share"])
    close("own common hard share", own_common_hard / len(own_common), common_report["our_b0"]["hard_lt_1e2_pair_share"])
    close("appearance median", statistics.median(appearances.values()), external_report["solution_appearance_median"])
    close("appearance mean", statistics.mean(appearances.values()), external_report["solution_appearance_mean"])

    csv_rows = list(csv.DictReader(Path(args.reported_csv).open(encoding="utf-8")))
    if {row["task"] for row in csv_rows} != set(external_gap) | set(own_gap):
        raise AssertionError("per-task CSV coverage changed")
    csv_by_task = {row["task"]: row for row in csv_rows}
    for task in common:
        ext_share = sum(gap < 1e-2 for gap in external_gap[task]) / len(external_gap[task])
        own_share = sum(gap < 1e-2 for gap in own_gap[task]) / len(own_gap[task])
        close(f"CSV external hard {task}", ext_share, float(csv_by_task[task]["official_hard_lt_1e2_share"]))
        close(f"CSV own hard {task}", own_share, float(csv_by_task[task]["our_hard_lt_1e2_share"]))
        close(f"CSV external median {task}", statistics.median(external_gap[task]), float(csv_by_task[task]["official_median_gap"]))
        close(f"CSV own median {task}", statistics.median(own_gap[task]), float(csv_by_task[task]["our_median_gap"]))

    guard = reported["interpretation_guard"]
    if guard.get("contains_official_predictions") is not False or guard.get("causal_explanation_allowed") is not False:
        raise AssertionError("interpretation guard weakened")
    print(
        "PBE_EXTERNAL_PAIR_INDEPENDENT_VERIFY_PASS",
        f"official_rows={table.num_rows}",
        f"solutions={len(appearances)}",
        f"official_hard={ext_hard / len(ext_all):.6f}",
        f"our_hard={own_hard / len(own_all):.6f}",
        f"official_common_hard={ext_common_hard / len(ext_common):.6f}",
        f"our_common_hard={own_common_hard / len(own_common):.6f}",
        f"directional_common_tasks={directional_tasks}/{len(common)}",
    )


if __name__ == "__main__":
    main()
