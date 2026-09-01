#!/usr/bin/env python3
"""Render the outcome-blind run-to-pair weighting figure from a hash-locked receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


EXPECTED_INPUT_SHA256 = (
    "bbdb802711bd2f300725be156c5fd228a79fa0792f8d7317674a6a0bbb419f30"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def point_by_prefix(rows: list[dict], prefix: int) -> dict:
    matches = [row for row in rows if int(row["prefix_runs"]) == prefix]
    if len(matches) != 1:
        raise ValueError(f"expected one prefix={prefix} row, found {len(matches)}")
    return matches[0]


def render(input_path: Path, output_dir: Path) -> dict:
    actual_sha = sha256(input_path)
    if actual_sha != EXPECTED_INPUT_SHA256:
        raise ValueError(f"input SHA drift: {actual_sha}")

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if payload["status"] != "OUTCOME_BLIND_STRUCTURAL_WEIGHT_TRAJECTORY_READY":
        raise ValueError("unexpected trajectory status")
    security = payload["security"]
    for key in ("api_calls", "gpu_calls", "base_llm_updates"):
        if security.get(key) != 0:
            raise ValueError(f"security contract drift: {key}")
    for key in (
        "eligible_blind_manifest_opened",
        "label_vault_opened",
        "outcome_grade_winner_orientation_opened",
        "raw_archive_or_journal_bytes_opened",
        "score_or_prediction_values_opened",
    ):
        if security.get(key) is not False:
            raise ValueError(f"security contract drift: {key}")

    all_rows = payload["full_prefix_trajectory"]
    if len(all_rows) != 339:
        raise ValueError(f"unexpected trajectory rows: {len(all_rows)}")
    rows = [row for row in all_rows if int(row["prefix_runs"]) >= 120]
    prefixes = [int(row["prefix_runs"]) for row in rows]

    run_hhi = [float(row["concentration"]["runs"]["hhi"]) for row in rows]
    pair_hhi = [
        float(row["concentration"]["structural_pairs"]["hhi"]) for row in rows
    ]
    run_max = [
        float(row["concentration"]["runs"]["maximum_share"]) for row in rows
    ]
    pair_max = [
        float(row["concentration"]["structural_pairs"]["maximum_share"])
        for row in rows
    ]

    baseline = point_by_prefix(all_rows, 240)
    current = point_by_prefix(all_rows, 339)
    baseline_run_hhi = float(baseline["concentration"]["runs"]["hhi"])
    baseline_pair_hhi = float(
        baseline["concentration"]["structural_pairs"]["hhi"]
    )
    current_run_hhi = float(current["concentration"]["runs"]["hhi"])
    current_pair_hhi = float(
        current["concentration"]["structural_pairs"]["hhi"]
    )
    baseline_run_max = float(
        baseline["concentration"]["runs"]["maximum_share"]
    )
    baseline_pair_max = float(
        baseline["concentration"]["structural_pairs"]["maximum_share"]
    )
    current_run_max = float(current["concentration"]["runs"]["maximum_share"])
    current_pair_max = float(
        current["concentration"]["structural_pairs"]["maximum_share"]
    )
    post240 = [row for row in all_rows if int(row["prefix_runs"]) >= 240]
    pair_hhi_jumps = [
        (
            int(post240[index]["prefix_runs"]),
            float(post240[index]["concentration"]["structural_pairs"]["hhi"])
            - float(post240[index - 1]["concentration"]["structural_pairs"]["hhi"]),
        )
        for index in range(1, len(post240))
    ]
    leverage_prefix, leverage_hhi_jump = max(pair_hhi_jumps, key=lambda item: item[1])
    if leverage_prefix != 260:
        raise ValueError(f"high-leverage drop prefix drift: {leverage_prefix}")

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "figure.dpi": 160,
            "savefig.dpi": 240,
            "svg.hashsalt": "decision-corpus-figure2-v1",
        }
    )
    colors = {"runs": "#2F6B9A", "pairs": "#D05A4E"}
    fig, axes = plt.subplots(1, 2, figsize=(7.15, 2.85), sharex=True)

    axes[0].plot(prefixes, run_hhi, color=colors["runs"], lw=1.8, label="Run weights")
    axes[0].plot(
        prefixes,
        pair_hhi,
        color=colors["pairs"],
        lw=1.8,
        label="Sibling-pair weights",
    )
    axes[0].set_title("(a) Task concentration (HHI)", loc="left")
    axes[0].set_ylabel("Herfindahl--Hirschman index")

    axes[1].plot(prefixes, run_max, color=colors["runs"], lw=1.8, label="Run weights")
    axes[1].plot(
        prefixes,
        pair_max,
        color=colors["pairs"],
        lw=1.8,
        label="Sibling-pair weights",
    )
    axes[1].set_title("(b) Largest task share", loc="left")
    axes[1].set_ylabel("Maximum task share")

    for axis in axes:
        axis.axvline(240, color="#666666", ls="--", lw=0.9, alpha=0.8)
        axis.text(
            242,
            axis.get_ylim()[1] - 0.02 * (axis.get_ylim()[1] - axis.get_ylim()[0]),
            "first-240",
            color="#555555",
            fontsize=7.5,
            va="top",
        )
        axis.set_xlabel("Chronological eligible runs")
        axis.grid(axis="y", color="#DDDDDD", lw=0.6)
        axis.spines[["top", "right"]].set_visible(False)
        axis.set_xlim(120, 339)

    axes[0].scatter(
        [240, 339],
        [baseline_run_hhi, current_run_hhi],
        color=colors["runs"],
        s=16,
        zorder=3,
    )
    axes[0].scatter(
        [240, 339],
        [baseline_pair_hhi, current_pair_hhi],
        color=colors["pairs"],
        s=16,
        zorder=3,
    )
    axes[1].scatter(
        [240, 339],
        [baseline_run_max, current_run_max],
        color=colors["runs"],
        s=16,
        zorder=3,
    )
    leverage_row = point_by_prefix(all_rows, leverage_prefix)
    leverage_pair_max = float(
        leverage_row["concentration"]["structural_pairs"]["maximum_share"]
    )
    axes[1].annotate(
        "one high-leverage drop",
        xy=(leverage_prefix, leverage_pair_max),
        xytext=(290, 0.265),
        fontsize=7.5,
        color="#555555",
        ha="center",
        arrowprops={"arrowstyle": "->", "color": "#777777", "lw": 0.8},
    )
    axes[1].scatter(
        [240, 339],
        [baseline_pair_max, current_pair_max],
        color=colors["pairs"],
        s=16,
        zorder=3,
    )
    axes[0].legend(frameon=False, loc="upper left")
    axes[1].legend(frameon=False, loc="upper left")

    fig.suptitle(
        "Run-balanced accrual can become pair-imbalanced evaluation",
        fontsize=11,
        y=1.02,
    )
    fig.tight_layout()

    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / "figure2_run_to_pair_weighting.png"
    svg_path = output_dir / "figure2_run_to_pair_weighting.svg"
    fig.savefig(
        png_path,
        bbox_inches="tight",
        metadata={"Software": "Decision Corpus figure renderer v1"},
    )
    fig.savefig(
        svg_path,
        bbox_inches="tight",
        metadata={
            "Creator": "Decision Corpus figure renderer v1",
            "Date": "2026-09-02",
        },
    )
    plt.close(fig)
    # Matplotlib writes path-data lines with insignificant trailing spaces. Normalize
    # them so repository whitespace checks pass and cross-platform hashes stay stable.
    normalized_svg = "\n".join(
        line.rstrip() for line in svg_path.read_text(encoding="utf-8").splitlines()
    ) + "\n"
    with svg_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(normalized_svg)

    receipt = {
        "protocol": "decision-corpus-paper-figure2-v1",
        "status": "PASS",
        "input_path": input_path.as_posix(),
        "input_sha256": actual_sha,
        "trajectory_rows": len(all_rows),
        "displayed_prefix_min": min(prefixes),
        "displayed_prefix_max": max(prefixes),
        "baseline_first240": {
            "run_hhi": baseline_run_hhi,
            "pair_hhi": baseline_pair_hhi,
            "run_max_share": baseline_run_max,
            "pair_max_share": baseline_pair_max,
        },
        "current_339": {
            "run_hhi": current_run_hhi,
            "pair_hhi": current_pair_hhi,
            "run_max_share": current_run_max,
            "pair_max_share": current_pair_max,
            "run_to_pair_total_variation": float(
                current["weighting_shift_tv"]["runs_to_structural_pairs"]
            ),
        },
        "largest_post240_pair_hhi_jump": {
            "prefix_runs": leverage_prefix,
            "delta": leverage_hhi_jump,
        },
        "claim_boundary": (
            "Outcome-blind structural weighting diagnostic; not predictor bias, "
            "accuracy, effect, utility, or a causal producer-behavior estimate."
        ),
        "security": payload["security"],
        "outputs": {
            png_path.name: sha256(png_path),
            svg_path.name: sha256(svg_path),
        },
    }
    receipt_path = output_dir / "figure2_receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "phase1/results/structural_weight_trajectory_7cda_20260826/trajectory.json"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("phase1/figures/decision_corpus_20260902"),
    )
    args = parser.parse_args()
    receipt = render(args.input, args.output_dir)
    print(
        "PAPER_FIGURE2=PASS "
        f"rows={receipt['trajectory_rows']} "
        f"prefix={receipt['displayed_prefix_min']}--{receipt['displayed_prefix_max']} "
        "outcomes_read=false"
    )


if __name__ == "__main__":
    main()
