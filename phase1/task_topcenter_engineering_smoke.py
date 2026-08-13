#!/usr/bin/env python3
"""Outcome-free timing smoke for the formal nested convex heads.

The smoke fits one worst-case full-training model per family and reports only
optimizer/runtime integrity.  It does not score endpoints or compute accuracy.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
from pathlib import Path
from typing import Any

from phase1 import frozen_embed_rank as baseline_module
from phase1 import task_topcenter_rank as rank_module


FORMAL_FIT_COUNTS = {
    "nested_global_allpair": 50,
    "nested_global_topcenter": 50,
    "nested_task_allpair": 140,
    "nested_task_topcenter": 140,
}


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--pairs", required=True, type=Path)
    parser.add_argument("--run-map", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--manifest-summary", required=True, type=Path)
    parser.add_argument("--feature-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--extraction-commit", required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--expect-pairs-sha256", required=True)
    parser.add_argument("--expect-run-map-sha256", required=True)
    parser.add_argument("--expect-manifest-sha256", required=True)
    parser.add_argument("--formal-runtime-budget-s", type=float, default=2400.0)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    rank_module.reject_forbidden_path(args.pairs, "training pairs")
    manifest, _, manifest_sha = baseline_module.load_manifest(
        args.manifest, args.manifest_summary
    )
    if manifest_sha != args.expect_manifest_sha256.lower():
        raise rank_module.IntegrityError("manifest hash mismatch")
    if rank_module.sha256(args.run_map) != args.expect_run_map_sha256.lower():
        raise rank_module.IntegrityError("run-map hash mismatch")
    rows, pair_audit, pair_sha = baseline_module.load_pairs(
        args.pairs, manifest, args.run_map
    )
    if pair_sha != args.expect_pairs_sha256.lower():
        raise rank_module.IntegrityError("training-pair hash mismatch")
    matrix, position, feature_audit = baseline_module.load_features(
        args.feature_root,
        manifest,
        manifest_sha,
        args.extraction_commit,
        args.model_sha256.lower(),
    )
    task_names = sorted({str(row["task"]) for row in rows})
    row_indices = list(range(len(rows)))
    records: dict[str, Any] = {}
    for family, definition in rank_module.FAMILIES.items():
        _, fit = rank_module.fit_ranker(
            rows,
            row_indices,
            matrix,
            position,
            task_names,
            str(definition["objective"]),
            bool(definition["task_residual"]),
            0.001,
            0.02 if bool(definition["task_residual"]) else None,
        )
        records[family] = fit
    estimate = sum(
        float(records[family]["elapsed_s"]) * count
        for family, count in FORMAL_FIT_COUNTS.items()
    )
    accepted = all(record["accepted"] for record in records.values())
    passed = accepted and estimate <= args.formal_runtime_budget_s
    payload = {
        "status": "ENGINEERING_SMOKE_PASS" if passed else "ENGINEERING_SMOKE_ABORT",
        "protocol": rank_module.PROTOCOL,
        "frozen_read": False,
        "accuracy_computed": False,
        "inputs": {
            "pairs_sha256": pair_sha,
            "run_map_sha256": rank_module.sha256(args.run_map),
            "manifest_sha256": manifest_sha,
            "extraction_commit": args.extraction_commit,
            "model_sha256": args.model_sha256.lower(),
        },
        "pair_audit": pair_audit,
        "feature_audit": feature_audit,
        "configuration": {
            "lambda_global": 0.001,
            "lambda_task": 0.02,
            "formal_fit_counts": FORMAL_FIT_COUNTS,
            "formal_runtime_budget_s": args.formal_runtime_budget_s,
        },
        "fits": records,
        "conservative_full_fit_extrapolation_s": estimate,
        "accepted": accepted,
        "software": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
    }
    atomic_json(args.output, payload)
    print(
        payload["status"],
        f"fits={len(records)}",
        f"extrapolation_s={estimate:.3f}",
        f"max_rss_kib={payload['software']['max_rss_kib']}",
    )
    return 0 if passed else 3


if __name__ == "__main__":
    raise SystemExit(main())
