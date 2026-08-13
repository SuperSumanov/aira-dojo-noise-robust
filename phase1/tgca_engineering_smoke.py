#!/usr/bin/env python3
"""One-fold TGCA engineering smoke that deliberately computes no accuracy metric."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from pathlib import Path

from phase1 import tgca_discovery as experiment

try:
    import resource
except ImportError:  # pragma: no cover - Windows development host
    resource = None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--pairs", required=True, type=Path)
    parser.add_argument("--cards", required=True, type=Path)
    parser.add_argument("--fold-oof", required=True, type=Path)
    parser.add_argument("--orientation", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expect-pairs-sha256", required=True)
    parser.add_argument("--expect-cards-sha256", required=True)
    parser.add_argument("--expect-fold-oof-sha256", required=True)
    parser.add_argument("--expect-orientation-sha256", required=True)
    parser.add_argument("--formal-chain-budget-s", required=True, type=float)
    args = parser.parse_args()
    if args.output.exists() or args.output_dir.exists():
        raise FileExistsError("smoke output already exists")
    started = time.monotonic()
    rows, metadata, row_audit = experiment.load_rows_and_folds(
        args.pairs,
        args.fold_oof,
        args.expect_pairs_sha256,
        args.expect_fold_oof_sha256,
    )
    cards, card_audit = experiment.load_cards(args.cards, metadata, args.expect_cards_sha256)
    orientation = experiment.load_orientation(
        args.orientation,
        args.expect_orientation_sha256,
        {row["task"] for row in rows},
    )
    experiment.validate_orientations(rows, cards, orientation)
    _, fold_summary, edges, graph_rows = experiment.run_fold(
        0,
        rows,
        cards,
        orientation,
        args.output_dir,
        "engineering-smoke-fold-zero-v1",
    )
    elapsed = time.monotonic() - started
    # Five producer folds plus five independent-verifier refits, with a 1.5x safety factor.
    conservative = elapsed * 10.0 * 1.5
    payload = {
        "status": "TGCA_ENGINEERING_SMOKE_PASS",
        "protocol": experiment.PROTOCOL,
        "fold": 0,
        "pairs": row_audit["pairs"],
        "runs": row_audit["runs"],
        "tasks": row_audit["tasks"],
        "parents": row_audit["parents"],
        "endpoints": row_audit["endpoints"],
        "selected_edge_manifest_rows": len(edges),
        "graph_stat_rows": len(graph_rows),
        "fold_isolation": fold_summary["isolation"],
        "fold_augmentation_rows": fold_summary["selection_audit"]["augmentation_rows"],
        "all_models_accepted": all(
            fold_summary["diagnostics"][arm]["accepted"] for arm in experiment.ARMS
        ),
        "accuracy_computed": False,
        "metrics_computed": [],
        "elapsed_s": elapsed,
        "conservative_formal_chain_extrapolation_s": conservative,
        "formal_chain_budget_s": args.formal_chain_budget_s,
        "within_formal_chain_budget": conservative < args.formal_chain_budget_s,
        "max_rss_kib": (
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource is not None else None
        ),
        "card_audit": card_audit,
    }
    if not payload["all_models_accepted"] or not payload["within_formal_chain_budget"]:
        raise RuntimeError(f"engineering smoke gate failed: {payload}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, args.output)
    shutil.rmtree(args.output_dir)
    print(
        payload["status"],
        f"fold_elapsed_s={elapsed:.3f}",
        f"chain_extrapolation_s={conservative:.3f}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
