"""Plot metric progress aggregated over recursively discovered journals.

Each ``journal.jsonl`` line is expected to contain a node object with
``metric``, ``metric_info.score`` and ``creation_time`` fields.  Missing
fields are represented as ``None`` while parsing and are ignored by numeric
aggregations.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

import matplotlib.pyplot as plt

def _parse_time(value: Any) -> datetime | float | None:
    """Convert a serialized creation time to a comparable value."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return None
    return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def read_journal(path: str | Path) -> list[dict[str, Any]]:
    """Read one journal, retaining the three fields needed for plotting."""
    records: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            try:
                node = json.loads(line)
            except json.JSONDecodeError:
                continue
            info = node.get("metric_info") or {}
            records.append(
                {
                    "metric": node.get("metric"),
                    "score": info.get("score"),
                    "creation_time": node.get("creation_time"),
                }
            )
    return records


def find_journals(folder: str | Path) -> list[Path]:
    """Return all lowercase ``journal.jsonl`` files below *folder*."""
    root = Path(folder)
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")
    return sorted(root.rglob("journal.jsonl"))


def _elapsed_seconds(value: datetime | float, start: datetime | float) -> float | None:
    try:
        elapsed = (value - start).total_seconds() if isinstance(value, datetime) else value - start
        return float(elapsed)
    except (TypeError, ValueError):
        return None


def aggregate_folder(folder: str | Path, interval: float) -> tuple[list[float], dict[str, list[float | None]]]:
    """Compute the four curves for all journals under one folder."""
    if interval <= 0:
        raise ValueError("interval must be positive")
    journals: list[list[tuple[float, float | None, float | None]]] = []
    max_elapsed = 0.0
    for journal_path in find_journals(folder):
        raw = read_journal(journal_path)
        times = [_parse_time(record["creation_time"]) for record in raw]
        # The reference is explicitly the first node, even if later nodes
        # happen to have valid timestamps.  Such a journal cannot be placed
        # on the requested relative time axis and is therefore skipped.
        if not times or times[0] is None:
            continue
        start = times[0]
        entries: list[tuple[float, float | None, float | None]] = []
        for record, timestamp in zip(raw, times):
            if timestamp is None:
                continue
            elapsed = _elapsed_seconds(timestamp, start)
            if elapsed is None or elapsed < 0:
                continue
            entries.append((elapsed, _number(record["score"]), _number(record["metric"])))
            max_elapsed = max(max_elapsed, elapsed)
        if entries:
            journals.append(entries)

    if not journals:
        return [], {"max_score": [], "avg_max_score": [], "max_metric": [], "avg_max_metric": []}
    times = [index * interval for index in range(math.floor(max_elapsed / interval) + 1)]
    curves: dict[str, list[float | None]] = {
        name: [] for name in ("max_score", "avg_max_score", "max_metric", "avg_max_metric")
    }
    for cutoff in times:
        per_journal_scores: list[float] = []
        per_journal_metrics: list[float] = []
        all_scores: list[float] = []
        all_metrics: list[float] = []
        for entries in journals:
            selected = [entry for entry in entries if entry[0] <= cutoff]
            scores = [entry[1] for entry in selected if entry[1] is not None]
            metrics = [entry[2] for entry in selected if entry[2] is not None]
            if scores:
                per_journal_scores.append(max(scores))
                all_scores.extend(scores)
            if metrics:
                per_journal_metrics.append(max(metrics))
                all_metrics.extend(metrics)
        curves["max_score"].append(max(all_scores) if all_scores else None)
        curves["avg_max_score"].append(mean(per_journal_scores) if per_journal_scores else None)
        curves["max_metric"].append(max(all_metrics) if all_metrics else None)
        curves["avg_max_metric"].append(mean(per_journal_metrics) if per_journal_metrics else None)
    return times, curves


def plot_folders(folders: Iterable[str | Path], interval: float, output: str | Path | None = None) -> Any:
    """Plot one line per folder for each of the four aggregate metrics."""
    import matplotlib.pyplot as plt

    folder_results = [(Path(folder), aggregate_folder(folder, interval)) for folder in folders]
    figure, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=False)
    axes_by_name = dict(zip(("max_score", "avg_max_score", "max_metric", "avg_max_metric"), axes.flat))
    for folder, (times, curves) in folder_results:
        label = folder.name or str(folder)
        for name, axis in axes_by_name.items():
            values = [math.nan if value is None else value for value in curves[name]]
            axis.plot(times, values, marker="o", label=label)
            axis.set_title(name.replace("_", " ").title())
            axis.set_xlabel("Seconds since first node")
            axis.grid(True, alpha=0.3)
    for axis in axes.flat:
        if folder_results:
            axis.legend()
    figure.tight_layout()
    if output is not None:
        figure.savefig(output, dpi=150)
    return figure


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folders", nargs="+", help="Folders to search recursively")
    parser.add_argument("--interval", type=float, required=True, help="Time interval in seconds")
    parser.add_argument("--output", type=Path, help="Output image path (otherwise display interactively)")
    args = parser.parse_args()
    figure = plot_folders(args.folders, args.interval, args.output)
    if args.output is None:
        plt.show()
    else:
        plt.close(figure)


if __name__ == "__main__":
    main()
