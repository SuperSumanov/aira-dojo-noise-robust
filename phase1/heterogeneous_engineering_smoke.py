#!/usr/bin/env python3
"""Outcome-free real-input engineering smoke for heterogeneous OOF models."""

from __future__ import annotations

import argparse
import json
import os
import resource
import time
from pathlib import Path

import numpy as np

from phase1 import frozen_embed_rank as baseline_module
from phase1 import heterogeneous_oof as producer
from phase1 import task_topcenter_rank as metric_module


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", required=True, type=Path)
    parser.add_argument("--run-map", required=True, type=Path)
    parser.add_argument("--cards", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--manifest-summary", required=True, type=Path)
    parser.add_argument("--baseline-oof", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expect-pairs-sha256", required=True)
    parser.add_argument("--expect-run-map-sha256", required=True)
    parser.add_argument("--expect-cards-sha256", required=True)
    parser.add_argument("--expect-manifest-sha256", required=True)
    parser.add_argument("--expect-baseline-sha256", required=True)
    parser.add_argument("--formal-chain-budget-s", type=float, default=3_600.0)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    for path, label in (
        (args.pairs, "training pairs"),
        (args.run_map, "run map"),
        (args.cards, "source cards"),
        (args.manifest, "train manifest"),
        (args.manifest_summary, "train manifest summary"),
        (args.baseline_oof, "baseline OOF"),
    ):
        producer.reject_forbidden_path(path, label)
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite smoke output: {args.output}")
    started = time.perf_counter()
    manifest, _ = producer.load_manifest(
        args.manifest, args.manifest_summary, args.expect_manifest_sha256
    )
    cards, card_audit = producer.load_train_cards(
        args.cards, manifest, args.expect_cards_sha256
    )
    rows, pair_audit, pair_sha = baseline_module.load_pairs(
        args.pairs, manifest, args.run_map
    )
    if pair_sha != args.expect_pairs_sha256.lower():
        raise producer.IntegrityError("pair SHA mismatch")
    if producer.sha256(args.run_map) != args.expect_run_map_sha256.lower():
        raise producer.IntegrityError("run-map SHA mismatch")
    folds, _, baseline_audit = metric_module.load_locked_baseline(
        args.baseline_oof, rows, args.expect_baseline_sha256
    )
    ids = sorted(cards)
    position = {card_id: index for index, card_id in enumerate(ids)}
    names, op_indices = producer.feature_names(cards[ids[0]])
    matrix = np.asarray(
        [
            [producer.static_feature_dict(cards[card_id])[name] for name in names]
            for card_id in ids
        ],
        dtype=np.float64,
    )
    fold_started = time.perf_counter()
    scores, fold = producer.run_fold(
        0,
        rows,
        folds,
        cards,
        matrix,
        position,
        op_indices,
        None,
        "engineering-smoke-v1",
    )
    fold_elapsed = time.perf_counter() - fold_started
    if any(not fold["diagnostics"][arm]["accepted"] for arm in producer.BASE_ARMS):
        raise producer.IntegrityError("engineering fold fit was not accepted")
    valid_ids = {
        str(rows[index][key])
        for index, assigned in enumerate(folds)
        if assigned == 0
        for key in ("better", "worse")
    }
    if any(set(scores[arm]) != valid_ids for arm in producer.BASE_ARMS):
        raise producer.IntegrityError("engineering fold score coverage mismatch")
    # Producer and independent full-refit verifier each execute five folds.
    conservative_chain = fold_elapsed * 10.0 * 1.5
    status = (
        "ENGINEERING_SMOKE_PASS"
        if conservative_chain <= args.formal_chain_budget_s
        else "ENGINEERING_SMOKE_RUNTIME_FAIL"
    )
    payload = {
        "status": status,
        "protocol": producer.PROTOCOL,
        "accuracy_computed": False,
        "metrics_computed": [],
        "fold": 0,
        "fold_elapsed_s": fold_elapsed,
        "conservative_chain_extrapolation_s": conservative_chain,
        "formal_chain_budget_s": args.formal_chain_budget_s,
        "total_smoke_elapsed_s": time.perf_counter() - started,
        "max_rss_kib": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        "pairs": pair_audit["pairs"],
        "runs": pair_audit["runs"],
        "tasks": pair_audit["tasks"],
        "parents": pair_audit["parents"],
        "endpoints": len(ids),
        "card_audit": card_audit,
        "baseline_sha256": baseline_audit["sha256"],
        "fold_audit": {
            key: value for key, value in fold.items() if key != "diagnostics"
        },
        "fit_diagnostics": fold["diagnostics"],
    }
    producer.atomic_json(args.output, payload)
    print(
        status,
        f"fold_s={fold_elapsed:.3f}",
        f"chain_estimate_s={conservative_chain:.3f}",
        f"max_rss_kib={payload['max_rss_kib']}",
        flush=True,
    )
    return 0 if status == "ENGINEERING_SMOKE_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
