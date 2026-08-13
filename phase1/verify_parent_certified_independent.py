"""Independent reconstruction of the frozen parent-certified comparison.

This verifier intentionally imports nothing from parent_certified_override.py.
It was committed before the outcome analysis was executed.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any


HASHES = {
    "manifest": "77f696828010e2d6ae10a9b9de2d9ec05d44975b1285ea763d9850a7f30ca4ef",
    "results": "b1266d04912596b1e37e13f79ce2387a962f5510cfa264aa1a97b7a1c443180d",
    "run_map": "3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30",
    "orientation": "e11111a3538c54eb91048b54380466b4dc0f041c2f511a78a85573cbc92b121a",
    "cards": "daeb29fc07ad670b5ca7a10cd2d84f1fa9a27dfa9d22510533417f1a8ad9407f",
}
TOL = 1e-12


def cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="phase1/fidelity_manifest.jsonl")
    parser.add_argument("--results", default="phase1/fidelity_results.jsonl")
    parser.add_argument("--run-map", default="phase1/card_run_map.json")
    parser.add_argument("--orientation", default="phase1/task_orientation.json")
    parser.add_argument("--cards", default="phase1/cards_current_v9.jsonl")
    parser.add_argument("--summary", default="phase1/parent_certified_v9/summary.json")
    parser.add_argument(
        "--out", default="phase1/parent_certified_v9/independent_verify.json"
    )
    parser.add_argument("--draws", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=9173)
    return parser.parse_args()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def oriented(value: float, lower: bool) -> float:
    return -float(value) if lower else float(value)


def selected(
    children: list[str], signal: dict[str, float], lower: bool
) -> list[str]:
    if not signal:
        return children
    peak = max(oriented(value, lower) for value in signal.values())
    return sorted(
        card_id
        for card_id, value in signal.items()
        if math.isclose(oriented(value, lower), peak, rel_tol=0.0, abs_tol=TOL)
    )


def top1(choice: list[str], truth: dict[str, float], lower: bool) -> float:
    values = {card_id: oriented(value, lower) for card_id, value in truth.items()}
    peak = max(values.values())
    winners = {
        card_id
        for card_id, value in values.items()
        if math.isclose(value, peak, rel_tol=0.0, abs_tol=TOL)
    }
    return len(set(choice) & winners) / len(choice)


def quantile(samples: list[float], probability: float) -> float:
    values = sorted(samples)
    position = min(len(values) - 1, max(0, int(probability * len(values))))
    return values[position]


def cluster_ci(
    rows: list[dict[str, Any]], cluster: str, draws: int, seed: int
) -> list[float]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row in rows:
        grouped[str(row[cluster])].append(float(row["delta"]))
    keys = sorted(grouped)
    rng = random.Random(seed)
    estimates = []
    for _ in range(draws):
        sampled = [rng.choice(keys) for _ in keys]
        estimates.append(
            statistics.mean(value for key in sampled for value in grouped[key])
        )
    return [quantile(estimates, 0.025), quantile(estimates, 0.975)]


def run_sign(rows: list[dict[str, Any]]) -> dict[str, int | float]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row in rows:
        grouped[str(row["run_id"])].append(float(row["delta"]))
    effects = [statistics.mean(values) for values in grouped.values()]
    positive = sum(value > 1e-15 for value in effects)
    negative = sum(value < -1e-15 for value in effects)
    tied = len(effects) - positive - negative
    active = positive + negative
    tail_index = min(positive, negative)
    tail = (
        sum(math.comb(active, index) for index in range(tail_index + 1)) / 2**active
        if active
        else 0.5
    )
    return {
        "positive": positive,
        "negative": negative,
        "tied": tied,
        "informative": active,
        "p_two_sided": min(1.0, 2.0 * tail),
    }


def main() -> None:
    args = cli()
    if args.draws <= 0:
        raise ValueError("draws must be positive")
    paths = {
        "manifest": Path(args.manifest),
        "results": Path(args.results),
        "run_map": Path(args.run_map),
        "orientation": Path(args.orientation),
        "cards": Path(args.cards),
    }
    actual = {name: digest(path) for name, path in paths.items()}
    if actual != HASHES:
        raise RuntimeError(f"raw input hash mismatch: {actual}")

    manifest = read_jsonl(paths["manifest"])
    results = read_jsonl(paths["results"])
    corpus_rows = read_jsonl(paths["cards"])
    run_map = json.loads(paths["run_map"].read_text(encoding="utf-8"))
    orientation = json.loads(paths["orientation"].read_text(encoding="utf-8"))
    summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))

    corpus = {str(row["id"]): row for row in corpus_rows}
    if len(corpus) != len(corpus_rows) or len(corpus) != 14323:
        raise RuntimeError("corpus uniqueness/count check failed")
    at_120 = {
        str(row["card_id"]): row for row in results if int(row["cap"]) == 120
    }
    if len(at_120) != 230:
        raise RuntimeError("120-second result count mismatch")

    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in manifest:
        grouped[str(row["parent"])].append(row)
    if len(grouped) != 100:
        raise RuntimeError("sibling-set count mismatch")

    paired = []
    support_sets = []
    random_top1 = []
    stdout_top1 = []
    naive_top1 = []
    parent_top1 = []
    for parent, members in sorted(grouped.items()):
        children = sorted(str(row["card_id"]) for row in members)
        task_set = {str(row["competition"]) for row in members}
        stratum_set = {str(row["stratum"]) for row in members}
        run_set = {run_map[card_id] for card_id in children}
        if len(task_set) != 1 or len(stratum_set) != 1 or len(run_set) != 1:
            raise RuntimeError(f"set metadata mismatch: {parent}")
        task = next(iter(task_set))
        lower = bool(orientation[task])
        truth = {str(row["card_id"]): float(row["graded"]) for row in members}
        stdout = {
            card_id: float(at_120[card_id]["stdout_val"])
            for card_id in children
            if is_number(at_120[card_id].get("stdout_val"))
        }
        artifact = {
            card_id: float(at_120[card_id]["sub_score"])
            for card_id in children
            if is_number(at_120[card_id].get("sub_score"))
        }
        parent_value = None
        if parent in corpus and is_number((corpus[parent].get("label") or {}).get("graded")):
            parent_value = float(corpus[parent]["label"]["graded"])
        certified = {}
        if parent_value is not None:
            parent_oriented = oriented(parent_value, lower)
            certified = {
                card_id: value
                for card_id, value in artifact.items()
                if oriented(value, lower) > parent_oriented + TOL
            }
        if certified:
            support_sets.append(
                {"run_id": next(iter(run_set)), "task": task, "parent": parent}
            )

        random_choice = children
        stdout_choice = selected(children, stdout, lower)
        naive_choice = selected(children, artifact if artifact else stdout, lower)
        parent_choice = selected(children, certified if certified else stdout, lower)
        random_score = top1(random_choice, truth, lower)
        stdout_score = top1(stdout_choice, truth, lower)
        naive_score = top1(naive_choice, truth, lower)
        parent_score = top1(parent_choice, truth, lower)
        random_top1.append(random_score)
        stdout_top1.append(stdout_score)
        naive_top1.append(naive_score)
        parent_top1.append(parent_score)
        paired.append(
            {
                "parent": parent,
                "run_id": next(iter(run_set)),
                "task": task,
                "stratum": next(iter(stratum_set)),
                "delta": parent_score - stdout_score,
            }
        )

    anchors = {
        "random": statistics.mean(random_top1),
        "stdout_only": statistics.mean(stdout_top1),
        "artifact_score_then_stdout": statistics.mean(naive_top1),
    }
    point = statistics.mean(row["delta"] for row in paired)
    sign = run_sign(paired)
    run_ci = cluster_ci(paired, "run_id", args.draws, args.seed)
    task_ci = cluster_ci(paired, "task", args.draws, args.seed)
    support = {
        "sets": len(support_sets),
        "runs": len({row["run_id"] for row in support_sets}),
        "tasks": len({row["task"] for row in support_sets}),
    }

    reported = next(
        item
        for item in summary["comparisons"]
        if item["label"] == "MAIN_PARENT_VS_STDOUT"
    )
    checks = {
        "point": math.isclose(point, float(reported["delta_top1"]), abs_tol=1e-15),
        "support": support == summary["support"],
        "sign": sign == reported["run_sign"],
        "anchors": all(
            math.isclose(value, float(summary["anchors"][name]), abs_tol=1e-15)
            for name, value in anchors.items()
        ),
        "counts": summary["counts"]["sets"] == 100
        and summary["counts"]["cards"] == 230
        and summary["counts"]["runs"] == 52
        and summary["counts"]["tasks"] == 19,
    }
    if not all(checks.values()):
        raise RuntimeError(f"independent verification failed: {checks}")

    output = {
        "status": "independent implementation; no import from main analysis",
        "inputs": actual,
        "seed": args.seed,
        "draws": args.draws,
        "checks": checks,
        "anchors": anchors,
        "support": support,
        "main": {
            "delta_top1": point,
            "run_ci95": run_ci,
            "task_ci95": task_ci,
            "run_sign": sign,
        },
    }
    out_path = Path(args.out)
    if out_path.exists():
        raise FileExistsError(f"refusing to overwrite {out_path}")
    out_path.write_text(
        json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print("INDEPENDENT_PARENT_VERIFY_PASS", checks)
    print("main", point, run_ci, task_ci, sign)
    print("support", support)


if __name__ == "__main__":
    main()
