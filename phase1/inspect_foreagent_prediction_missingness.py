from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


def valid_index(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value in (0, 1)


def valid_confidence(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and 0.0 <= float(value) <= 1.0
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--master", type=Path, required=True)
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    sources = json.loads(args.manifest.read_text(encoding="utf-8"))["files"]
    counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    with args.master.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            scores = [float(value) for value in row["scores"]]
            if not all(math.isfinite(value) for value in scores) or scores[0] == scores[1]:
                continue
            source_index = row["source_index"]
            pred = valid_index(row.get("prediction_best_index"))
            conf = valid_confidence(row.get("confidence"))
            counts[source_index]["n"] += 1
            counts[source_index]["prediction"] += int(pred)
            counts[source_index]["confidence"] += int(conf)
            counts[source_index]["joint"] += int(pred and conf)
            counts[source_index]["prediction_only_invalid"] += int(not pred and conf)
            counts[source_index]["confidence_only_invalid"] += int(pred and not conf)
            counts[source_index]["both_invalid"] += int(not pred and not conf)

    for model in ("deepseek", "gpt"):
        indices = [index for index, source in enumerate(sources) if source["model_family"] == model]
        total = sum(counts[index]["n"] for index in indices)
        aggregate = {
            key: sum(counts[index][key] for index in indices)
            for key in (
                "prediction",
                "confidence",
                "joint",
                "prediction_only_invalid",
                "confidence_only_invalid",
                "both_invalid",
            )
        }
        print(
            "MISSINGNESS_MODEL",
            f"model={model}",
            f"records={total}",
            f"prediction_coverage={aggregate['prediction'] / total:.12f}",
            f"confidence_coverage={aggregate['confidence'] / total:.12f}",
            f"joint_coverage={aggregate['joint'] / total:.12f}",
            f"prediction_only_invalid={aggregate['prediction_only_invalid']}",
            f"confidence_only_invalid={aggregate['confidence_only_invalid']}",
            f"both_invalid={aggregate['both_invalid']}",
        )
        for field in ("prediction", "confidence", "joint"):
            values = [counts[index][field] / counts[index]["n"] for index in indices]
            print(
                "MISSINGNESS_SOURCE_GATE",
                f"model={model}",
                f"field={field}",
                f"min={min(values):.12f}",
                f"below_0p99={sum(value < 0.99 for value in values)}",
                f"sources={len(values)}",
            )

    if args.summary_only:
        return

    rows = []
    for index, source in enumerate(sources):
        n = counts[index]["n"]
        prediction_coverage = counts[index]["prediction"] / n
        confidence_coverage = counts[index]["confidence"] / n
        if prediction_coverage < 0.99 or confidence_coverage < 0.99:
            rows.append(
                (
                    min(prediction_coverage, confidence_coverage),
                    source["task"],
                    source["model_family"],
                    source["release_run"],
                    n,
                    prediction_coverage,
                    confidence_coverage,
                    counts[index]["prediction_only_invalid"],
                    counts[index]["confidence_only_invalid"],
                    counts[index]["both_invalid"],
                )
            )
    for row in sorted(rows):
        print(
            "MISSINGNESS_SOURCE",
            f"task={row[1]}",
            f"model={row[2]}",
            f"run={row[3]}",
            f"n={row[4]}",
            f"prediction={row[5]:.12f}",
            f"confidence={row[6]:.12f}",
            f"prediction_only_invalid={row[7]}",
            f"confidence_only_invalid={row[8]}",
            f"both_invalid={row[9]}",
        )


if __name__ == "__main__":
    main()
