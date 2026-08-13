"""Independent raw-input recomputation for artifact_cascade_audit.py outputs."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import random
import statistics
from pathlib import Path


LOCKS = {
    "manifest": "77f696828010e2d6ae10a9b9de2d9ec05d44975b1285ea763d9850a7f30ca4ef",
    "results": "b1266d04912596b1e37e13f79ce2387a962f5510cfa264aa1a97b7a1c443180d",
    "run_map": "3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30",
    "orientation": "e11111a3538c54eb91048b54380466b4dc0f041c2f511a78a85573cbc92b121a",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="phase1/fidelity_manifest.jsonl")
    parser.add_argument("--results", default="phase1/fidelity_results.jsonl")
    parser.add_argument("--run-map", default="phase1/card_run_map.json")
    parser.add_argument("--orientation", default="phase1/task_orientation.json")
    parser.add_argument("--summary", default="phase1/artifact_cascade_v9/summary.json")
    parser.add_argument("--out", default="phase1/artifact_cascade_v9/independent_verify.json")
    parser.add_argument("--draws", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=9173)
    return parser.parse_args()


def digest(path: str | Path) -> str:
    value = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def read_jsonl(path: str | Path) -> list[dict]:
    with Path(path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def oriented(value: float, task: str, lower: dict[str, bool]) -> float:
    return -float(value) if lower[task] else float(value)


def winners(scores: dict[str, float], task: str, lower: dict[str, bool]) -> set[str]:
    best = max(oriented(value, task, lower) for value in scores.values())
    return {
        card_id
        for card_id, value in scores.items()
        if math.isclose(oriented(value, task, lower), best, abs_tol=1e-12)
    }


def expected_hit(selected: set[str], truth: dict[str, float], task: str, lower: dict) -> float:
    best = winners(truth, task, lower)
    return len(selected & best) / len(selected)


def interval(rows: list[dict], cluster: str, draws: int, seed: int) -> list[float]:
    grouped = collections.defaultdict(list)
    for row in rows:
        grouped[str(row[cluster])].append(float(row["delta"]))
    keys = sorted(grouped)
    rng = random.Random(seed)
    estimates = []
    for _ in range(draws):
        chosen = [rng.choice(keys) for _ in keys]
        values = [value for key in chosen for value in grouped[key]]
        estimates.append(statistics.mean(values))
    estimates.sort()
    return [estimates[int(0.025 * draws)], estimates[int(0.975 * draws)]]


def sign_test(rows: list[dict]) -> dict[str, int | float]:
    grouped = collections.defaultdict(list)
    for row in rows:
        grouped[str(row["run_id"])].append(float(row["delta"]))
    effects = [statistics.mean(values) for values in grouped.values()]
    positive = sum(value > 1e-15 for value in effects)
    negative = sum(value < -1e-15 for value in effects)
    tied = len(effects) - positive - negative
    informative = positive + negative
    smaller = min(positive, negative)
    tail = (
        sum(math.comb(informative, k) for k in range(smaller + 1)) / 2**informative
        if informative
        else 0.5
    )
    return {
        "positive": positive,
        "negative": negative,
        "tied": tied,
        "p_two_sided": min(1.0, 2 * tail),
    }


def compare(rows: list[dict], field_a: str, field_b: str, draws: int, seed: int) -> dict:
    paired = [
        {
            "run_id": row["run_id"],
            "task": row["task"],
            "delta": float(row[field_a]) - float(row[field_b]),
        }
        for row in rows
    ]
    return {
        "delta": statistics.mean(row["delta"] for row in paired),
        "run_ci95": interval(paired, "run_id", draws, seed),
        "task_ci95": interval(paired, "task", draws, seed),
        "run_sign": sign_test(paired),
    }


def main() -> None:
    args = parse_args()
    paths = {
        "manifest": Path(args.manifest),
        "results": Path(args.results),
        "run_map": Path(args.run_map),
        "orientation": Path(args.orientation),
    }
    observed = {name: digest(path) for name, path in paths.items()}
    if observed != LOCKS:
        raise RuntimeError(f"input locks differ: {observed}")
    manifest = read_jsonl(paths["manifest"])
    results = {
        str(row["card_id"]): row
        for row in read_jsonl(paths["results"])
        if int(row["cap"]) == 120
    }
    run_of = json.loads(paths["run_map"].read_text(encoding="utf-8"))
    lower = json.loads(paths["orientation"].read_text(encoding="utf-8"))
    by_parent = collections.defaultdict(list)
    for row in manifest:
        by_parent[str(row["parent"])].append(row)
    if len(by_parent) != 100 or len(results) != 230:
        raise RuntimeError("population count mismatch")

    rows = []
    for parent, members in sorted(by_parent.items()):
        ids = {str(member["card_id"]) for member in members}
        tasks = {str(member["competition"]) for member in members}
        runs = {run_of.get(card_id) for card_id in ids}
        if len(tasks) != 1 or len(runs) != 1 or None in runs:
            raise RuntimeError(f"mixed sibling set: {parent}")
        task, run_id = next(iter(tasks)), next(iter(runs))
        truth = {str(member["card_id"]): float(member["graded"]) for member in members}
        artifact = {
            card_id: float(results[card_id]["sub_score"])
            for card_id in ids
            if is_number(results[card_id].get("sub_score"))
        }
        stdout = {
            card_id: float(results[card_id]["stdout_val"])
            for card_id in ids
            if is_number(results[card_id].get("stdout_val"))
        }
        stdout_selected = winners(stdout, task, lower) if stdout else ids
        presence_selected = set(artifact) if artifact else stdout_selected
        score_selected = winners(artifact, task, lower) if artifact else stdout_selected
        rows.append(
            {
                "parent": parent,
                "run_id": run_id,
                "task": task,
                "stdout": expected_hit(stdout_selected, truth, task, lower),
                "presence": expected_hit(presence_selected, truth, task, lower),
                "score": expected_hit(score_selected, truth, task, lower),
            }
        )

    recomputed = {
        "counts": {
            "sets": len(rows),
            "runs": len({row["run_id"] for row in rows}),
            "tasks": len({row["task"] for row in rows}),
        },
        "main_score_minus_stdout": compare(rows, "score", "stdout", args.draws, args.seed),
        "score_value_minus_presence": compare(
            rows, "score", "presence", args.draws, args.seed
        ),
        "presence_minus_stdout": compare(
            rows, "presence", "stdout", args.draws, args.seed
        ),
        "bootstrap": {"draws": args.draws, "seed": args.seed},
        "inputs": observed,
    }
    published = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    indexed = {item["label"]: item for item in published["comparisons"]}
    checks = {
        "main_point": math.isclose(
            recomputed["main_score_minus_stdout"]["delta"], indexed["MAIN"]["delta_top1"]
        ),
        "score_value_point": math.isclose(
            recomputed["score_value_minus_presence"]["delta"],
            indexed["SECONDARY_SCORE_VALUE"]["delta_top1"],
        ),
        "presence_point": math.isclose(
            recomputed["presence_minus_stdout"]["delta"],
            indexed["SECONDARY_ARTIFACT_PRESENCE"]["delta_top1"],
        ),
        "main_sign": (
            recomputed["main_score_minus_stdout"]["run_sign"]
            == {
                key: indexed["MAIN"]["run_sign"][key]
                for key in ("positive", "negative", "tied", "p_two_sided")
            }
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(f"independent verification failed: {checks}")
    recomputed["checks"] = checks
    output = Path(args.out)
    if output.exists():
        raise FileExistsError(output)
    output.write_text(
        json.dumps(recomputed, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print("INDEPENDENT_VERIFY_PASS", checks)
    for name in (
        "main_score_minus_stdout",
        "score_value_minus_presence",
        "presence_minus_stdout",
    ):
        result = recomputed[name]
        print(name, result["delta"], result["run_ci95"], result["task_ci95"])


if __name__ == "__main__":
    main()
