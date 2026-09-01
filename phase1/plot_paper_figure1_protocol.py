#!/usr/bin/env python3
"""Render the Decision Corpus unit hierarchy and sealed evaluation protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_box(
    axis,
    x: float,
    y: float,
    width: float,
    height: float,
    text: str,
    *,
    face: str,
    edge: str,
    fontsize: float = 8.2,
    linewidth: float = 1.2,
    style: str = "round,pad=0.025,rounding_size=0.02",
) -> None:
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle=style,
        facecolor=face,
        edgecolor=edge,
        linewidth=linewidth,
    )
    axis.add_patch(patch)
    axis.text(
        x + width / 2,
        y + height / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        color="#202124",
        linespacing=1.15,
    )


def arrow(
    axis,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    color: str = "#59636E",
    style: str = "-|>",
    linestyle: str = "-",
    linewidth: float = 1.2,
    connectionstyle: str = "arc3",
) -> None:
    axis.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle=style,
            mutation_scale=10,
            color=color,
            linewidth=linewidth,
            linestyle=linestyle,
            connectionstyle=connectionstyle,
        )
    )


def render(output_dir: Path) -> dict:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.5,
            "figure.dpi": 160,
            "savefig.dpi": 240,
            "svg.hashsalt": "decision-corpus-figure1-v1",
        }
    )
    palette = {
        "data": "#E8F1F8",
        "data_edge": "#3976A8",
        "historical": "#EAF4EA",
        "historical_edge": "#4C8B57",
        "sealed": "#FFF2D8",
        "sealed_edge": "#B67A16",
        "report": "#E9F6F2",
        "report_edge": "#2E8673",
        "audit": "#F1F2F4",
        "audit_edge": "#6B7280",
    }

    fig, axis = plt.subplots(figsize=(9.0, 5.35))
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.axis("off")
    fig.suptitle(
        "Decision Corpus: from search archives to a sealed predictor benchmark",
        fontsize=13,
        y=0.985,
    )

    axis.text(0.035, 0.905, "A  Provenance-bound decision units", weight="bold", fontsize=10)
    unit_x = [0.035, 0.225, 0.415, 0.605, 0.795]
    unit_text = [
        "Immutable\narchive",
        "Physical\nsearch run",
        "Endpoint / card\n(candidate program)",
        "Recorded parent\nwithin the same run",
        "Retained sibling\ndecision fragment",
    ]
    widths = [0.145, 0.145, 0.15, 0.15, 0.17]
    for x, width, label in zip(unit_x, widths, unit_text):
        add_box(
            axis,
            x,
            0.78,
            width,
            0.09,
            label,
            face=palette["data"],
            edge=palette["data_edge"],
        )
    for index in range(len(unit_x) - 1):
        arrow(
            axis,
            (unit_x[index] + widths[index], 0.825),
            (unit_x[index + 1] - 0.008, 0.825),
        )
    axis.text(
        0.795,
        0.735,
        "fragment ≠ complete choice set",
        fontsize=7.3,
        color="#5F6368",
        ha="left",
    )

    axis.text(0.035, 0.675, "B  Two evidence tracks", weight="bold", fontsize=10)
    add_box(
        axis,
        0.04,
        0.48,
        0.28,
        0.145,
        "Historical v11 development\n\nrun/parent/endpoint/pair isolation\nlabels available; claims remain historical",
        face=palette["historical"],
        edge=palette["historical_edge"],
        fontsize=8,
    )
    add_box(
        axis,
        0.36,
        0.48,
        0.28,
        0.145,
        "Chronological prospective cohort\n\nappend-only eligible-run registry\noutcomes hidden until closure",
        face=palette["sealed"],
        edge=palette["sealed_edge"],
        fontsize=8,
    )
    add_box(
        axis,
        0.68,
        0.48,
        0.28,
        0.145,
        "Clean scaling (conditional)\n\nfuture exact config stratum\nGPU matrix requires separate approval",
        face="#F7EDF8",
        edge="#8B5A91",
        fontsize=8,
    )
    arrow(axis, (0.32, 0.552), (0.352, 0.552), color="#8A8F98", style="->")
    axis.text(
        0.337,
        0.64,
        "confirm",
        fontsize=6.8,
        color="#6B7280",
        ha="center",
    )
    arrow(
        axis,
        (0.64, 0.552),
        (0.672, 0.552),
        color="#8A8F98",
        style="->",
        linestyle="--",
    )
    axis.text(
        0.656,
        0.64,
        "only if provenance gate passes",
        fontsize=6.4,
        color="#6B7280",
        ha="center",
    )

    axis.text(0.035, 0.405, "C  Outcome-blind one-time join", weight="bold", fontsize=10)
    add_box(
        axis,
        0.04,
        0.245,
        0.18,
        0.10,
        "Frozen predictors\n(train-run dev only)",
        face=palette["data"],
        edge=palette["data_edge"],
    )
    add_box(
        axis,
        0.285,
        0.245,
        0.17,
        0.10,
        "Prediction escrow\n(values sealed)",
        face=palette["sealed"],
        edge=palette["sealed_edge"],
    )
    add_box(
        axis,
        0.04,
        0.105,
        0.18,
        0.10,
        "Pristine evaluator\n(external to agent)",
        face=palette["data"],
        edge=palette["data_edge"],
    )
    add_box(
        axis,
        0.285,
        0.105,
        0.17,
        0.10,
        "Label / outcome vault\n(values sealed)",
        face=palette["sealed"],
        edge=palette["sealed_edge"],
    )
    add_box(
        axis,
        0.525,
        0.17,
        0.17,
        0.105,
        "One-time closure anchor\nidentity + accrual receipt",
        face=palette["sealed"],
        edge=palette["sealed_edge"],
    )
    add_box(
        axis,
        0.765,
        0.17,
        0.19,
        0.105,
        "Exact-common-support report\nquality + coverage + cost\nclustered uncertainty",
        face=palette["report"],
        edge=palette["report_edge"],
        fontsize=7.8,
    )
    arrow(axis, (0.22, 0.295), (0.277, 0.295))
    arrow(axis, (0.22, 0.155), (0.277, 0.155))
    arrow(axis, (0.455, 0.295), (0.517, 0.235), connectionstyle="arc3,rad=0.05")
    arrow(axis, (0.455, 0.155), (0.517, 0.205), connectionstyle="arc3,rad=-0.05")
    arrow(axis, (0.695, 0.222), (0.757, 0.222), color=palette["report_edge"])
    axis.text(
        0.61,
        0.365,
        "no accuracy / utility before closure",
        fontsize=7.6,
        color="#A33A2B",
        ha="center",
        weight="bold",
    )

    add_box(
        axis,
        0.015,
        0.015,
        0.97,
        0.055,
        "Audit rail: exact commit  •  input/output hashes  •  producer A/B  •  independent verifier  •  "
        "file/network trace  •  read-only artifacts  •  withdrawal ledger",
        face=palette["audit"],
        edge=palette["audit_edge"],
        fontsize=6.7,
        style="round,pad=0.018,rounding_size=0.018",
    )

    fig.tight_layout(rect=(0, 0, 1, 0.965))
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / "figure1_corpus_and_sealed_protocol.png"
    svg_path = output_dir / "figure1_corpus_and_sealed_protocol.svg"
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
    normalized_svg = "\n".join(
        line.rstrip() for line in svg_path.read_text(encoding="utf-8").splitlines()
    ) + "\n"
    with svg_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(normalized_svg)

    renderer_path = Path(__file__).resolve()
    receipt = {
        "protocol": "decision-corpus-paper-figure1-v1",
        "status": "PASS",
        "renderer_sha256": sha256(renderer_path),
        "scientific_values_read": False,
        "prospective_identity_profile_read": False,
        "outcome_label_prediction_accuracy_utility_read": False,
        "gpu_api_model_fit_base_update": "0/0/0/0",
        "claim_boundary": (
            "Protocol schematic only; it does not report predictor performance, "
            "search utility, cohort identities, or a completed scaling experiment."
        ),
        "outputs": {
            png_path.name: sha256(png_path),
            svg_path.name: sha256(svg_path),
        },
    }
    receipt_path = output_dir / "figure1_receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("phase1/figures/decision_corpus_20260902"),
    )
    args = parser.parse_args()
    receipt = render(args.output_dir)
    print(
        "PAPER_FIGURE1=PASS "
        f"outputs={len(receipt['outputs'])} "
        "scientific_values_read=false outcomes_read=false"
    )


if __name__ == "__main__":
    main()
