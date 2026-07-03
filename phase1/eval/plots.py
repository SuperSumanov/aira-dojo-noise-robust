"""Sample-efficiency plots: a metric vs label-budget N, one line per predictor with a bootstrap CI
band. Always writes the plot data as CSV (so the numbers exist even in a headless/matplotlib-less
env); renders a PNG only when matplotlib is importable.
"""
from __future__ import annotations

import csv
from typing import List

from .metrics import METRIC_HIGHER_BETTER
from .runner import Row, aggregate


def _write_plotdata(agg, metric: str, path: str) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "predictor", "budget", "median", "lo", "hi"])
        for p, d in agg.items():
            for i, b in enumerate(d["x"]):
                w.writerow([metric, p, b, d["median"][i], d["lo"][i], d["hi"][i]])


def plot_metric(rows: List[Row], metric: str, png_path: str, csv_path: str = None) -> str:
    """Returns a short status string. Writes csv_path (plot data) always; png_path if mpl present."""
    agg = aggregate(rows, metric)
    csv_path = csv_path or (png_path.rsplit(".", 1)[0] + ".csv")
    _write_plotdata(agg, metric, csv_path)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:  # matplotlib not installed -> data-only
        return f"[plot] {metric}: data -> {csv_path} (png skipped: {e})"

    order = ["25", "50", "100", "200", "all"]
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    for p, d in agg.items():
        xi = [order.index(b) for b in d["x"]]
        ax.plot(xi, d["median"], marker="o", label=p)
        ax.fill_between(xi, d["lo"], d["hi"], alpha=0.15)
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(order)
    ax.set_xlabel("label budget N")
    better = "higher better" if METRIC_HIGHER_BETTER.get(metric, True) else "lower better"
    ax.set_ylabel(f"{metric}  ({better})")
    ax.set_title(f"Sample efficiency: {metric} vs label budget")
    ax.legend(fontsize=8, ncol=2)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(png_path, dpi=120)
    plt.close(fig)
    return f"[plot] {metric}: {png_path} (+ {csv_path})"


def plot_all(rows: List[Row], out_dir: str, metrics=("spearman", "regret@1", "ece")) -> List[str]:
    import os
    os.makedirs(out_dir, exist_ok=True)
    msgs = []
    for m in metrics:
        safe = m.replace("@", "at")
        msgs.append(plot_metric(rows, m, os.path.join(out_dir, f"sample_eff_{safe}.png")))
    return msgs
