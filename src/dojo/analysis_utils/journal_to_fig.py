"""Plot metric progress aggregated over recursively discovered journals.

Each ``journal.jsonl`` line is expected to contain a node object with
``metric``, ``metric_info.score`` and ``creation_time`` fields.  Missing
fields are represented as ``None`` while parsing and are ignored by numeric
aggregations.

Six curves are produced per folder:

``max_score`` / ``avg_max_score``
    The best official score seen so far, taken over all runs / per run then
    averaged.  This is the "did we ever find something good" view.
``max_metric`` / ``avg_max_metric``
    Same for the internal validation metric.  This is what the search itself
    optimises.
``max_selected_score`` / ``avg_selected_score``
    For every run, pick the node with the highest internal metric seen so far
    and report *its* official score (that is the node the solver would submit
    when it stops).  Then take the max / the mean over runs.  A widening gap
    between these curves and ``max_metric`` is the signal that the internal
    metric is being hacked.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

import matplotlib.pyplot as plt

CURVE_NAMES = (
    "max_score",
    "avg_max_score",
    "max_metric",
    "avg_max_metric",
    "max_selected_score",
    "avg_selected_score",
)

CURVE_TITLES = {
    "max_score": "Max Score",
    "avg_max_score": "Avg Max Score",
    "max_metric": "Max Metric",
    "avg_max_metric": "Avg Max Metric",
    "max_selected_score": "Max Score @ Max Metric",
    "avg_selected_score": "Avg Score @ Max Metric",
}


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
            is_lower_better = info.get("is_lower_better")
            sign = -1 if (is_lower_better is not None and float(is_lower_better) > 0.5) else 1
            records.append(
                {
                    "metric": sign * node["metric"] if node.get("metric") is not None else None,
                    "score": sign * info["score"] if info.get("score") is not None else None,
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
    """Compute the six curves for all journals under one folder."""
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
        return [], {name: [] for name in CURVE_NAMES}
    times = [index * interval for index in range(math.floor(max_elapsed / interval) + 1)]
    curves: dict[str, list[float | None]] = {name: [] for name in CURVE_NAMES}
    for cutoff in times:
        per_journal_scores: list[float] = []
        per_journal_metrics: list[float] = []
        per_journal_selected_scores: list[float] = []
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
            # The node the solver would submit: highest internal metric so far.
            # Ties keep the earlier node, matching a plain "first best" scan.
            chosen = None
            for elapsed, score, metric in selected:
                if metric is None:
                    continue
                if chosen is None or metric > chosen[1]:
                    chosen = (score, metric)
            if chosen is not None and chosen[0] is not None:
                per_journal_selected_scores.append(chosen[0])
        curves["max_score"].append(max(all_scores) if all_scores else None)
        curves["avg_max_score"].append(mean(per_journal_scores) if per_journal_scores else None)
        curves["max_metric"].append(max(all_metrics) if all_metrics else None)
        curves["avg_max_metric"].append(mean(per_journal_metrics) if per_journal_metrics else None)
        curves["max_selected_score"].append(
            max(per_journal_selected_scores) if per_journal_selected_scores else None
        )
        curves["avg_selected_score"].append(
            mean(per_journal_selected_scores) if per_journal_selected_scores else None
        )
    return times, curves


def _default_title(folders: list[Path]) -> str | None:
    """Derive a figure title from the deepest folder all inputs share."""
    if not folders:
        return None
    try:
        common = Path(os.path.commonpath([folder.resolve() for folder in folders]))
    except ValueError:
        return None
    parts = [part for part in common.parts if part not in (common.anchor, os.sep)]
    if not parts:
        return None
    return "/".join(parts[-3:])


def plot_folders(
    folders: Iterable[str | Path],
    interval: float,
    output: str | Path | None = None,
    title: str | None = None,
) -> Any:
    """Plot one line per folder for each of the six aggregate metrics."""
    import matplotlib.pyplot as plt

    folder_paths = [Path(folder) for folder in folders]
    folder_results = [(folder, aggregate_folder(folder, interval)) for folder in folder_paths]
    figure, axes = plt.subplots(2, 3, figsize=(18, 8), sharex=False)
    figure.suptitle(title if title is not None else _default_title(folder_paths), fontsize=14)
    axes_by_name = dict(zip(CURVE_NAMES, axes.flat))
    for folder, (times, curves) in folder_results:
        label = folder.name or str(folder)
        for name, axis in axes_by_name.items():
            values = [math.nan if value is None else value for value in curves[name]]
            axis.plot(times, values, marker="o", label=label)
            axis.set_title(CURVE_TITLES[name])
            axis.set_xlabel("Seconds since first node")
            axis.grid(True, alpha=0.3)
    for axis in axes.flat:
        if folder_results:
            axis.legend()
    figure.tight_layout()
    if output is not None:
        figure.savefig(output, dpi=150)
    return figure


def format_folder_text(folder: str | Path, times: list[float], curves: dict[str, list[float | None]]) -> str:
    """Render one folder's curves as a plain-text table."""
    path = Path(folder)
    lines = [f"# {path}  journals={len(find_journals(path))}  points={len(times)}"]
    header = ["hours", *CURVE_NAMES]
    lines.append("  ".join(f"{name:>20s}" for name in header))

    def cell(value: float | None) -> str:
        return "           -" if value is None else f"{value:20.4f}"

    for index, seconds in enumerate(times):
        cells = [f"{seconds / 3600.0:20.2f}"]
        cells.extend(cell(curves[name][index]) for name in CURVE_NAMES)
        lines.append("  ".join(cells))

    last = []
    for name in CURVE_NAMES:
        values = [value for value in curves[name] if value is not None]
        last.append(f"{name}={values[-1]:.4f}" if values else f"{name}=-")
    lines.append("last: " + "  ".join(last))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folders", nargs="+", help="Folders to search recursively")
    parser.add_argument("--interval", type=float, required=True, help="Time interval in seconds")
    parser.add_argument("--output", type=Path, help="Output image path (otherwise display interactively)")
    parser.add_argument("--text", action="store_true", help="Print the curves as plain text")
    parser.add_argument("--title", help="Figure title (defaults to the folders' common parent)")
    args = parser.parse_args()

    if args.text:
        for folder in args.folders:
            times, curves = aggregate_folder(folder, args.interval)
            print(format_folder_text(folder, times, curves))

    if args.output is not None or not args.text:
        figure = plot_folders(args.folders, args.interval, args.output, args.title)
        if args.output is None:
            plt.show()
        else:
            plt.close(figure)


if __name__ == "__main__":
    main()
