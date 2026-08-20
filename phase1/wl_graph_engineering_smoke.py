#!/usr/bin/env python3
"""Train-only engineering smoke for the frozen WL graph feature path."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path

from phase1.fixed_decision_scorer import load_manifest, load_train_cards, sha256
from phase1.wl_code_graph_features import (
    HASHED_DIMENSIONS,
    MAXIMUM_NODES,
    WL_ITERATIONS,
    aggregate_diagnostics,
    hashed_l2_matrix,
    wl_feature_dict,
)

try:
    import resource
except ImportError:  # pragma: no cover - the formal smoke is Linux-only
    resource = None


PROTOCOL = "wl-graph-engineering-smoke-v1"
FULL_ENDPOINTS = 5499
OVERHEAD_ALLOWANCE_SECONDS = 600.0
MAX_PROJECTED_WALL_SECONDS = 7200.0
MAX_RSS_GIB = 32.0


class SmokeError(RuntimeError):
    pass


def matrix_digest(matrix) -> str:
    value = hashlib.sha256()
    value.update(str(matrix.shape).encode())
    value.update(matrix.indptr.tobytes())
    value.update(matrix.indices.tobytes())
    value.update(matrix.data.tobytes())
    return value.hexdigest()


def bind_source(repo: Path, source_commit: str, protocol: Path) -> None:
    actual = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(
        ["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all"], text=True
    ).strip()
    if actual != source_commit or dirty:
        raise SmokeError("source commit/clean worktree binding failed")
    value = json.loads(protocol.read_text(encoding="utf-8"))
    if value.get("protocol") != "wl-graph-multiview-extension-v1":
        raise SmokeError("protocol binding failed")


def run(args: argparse.Namespace) -> dict:
    if resource is None:
        raise SmokeError("resource module unavailable; formal smoke requires Linux")
    repo = Path(__file__).resolve().parent.parent
    protocol_path = Path(args.protocol).resolve()
    bind_source(repo, args.source_commit, protocol_path)
    manifest, _summary = load_manifest(
        Path(args.manifest),
        Path(args.manifest_summary),
        args.expect_manifest_sha256,
        args.expect_manifest_summary_sha256,
    )
    cards, card_audit = load_train_cards(
        Path(args.cards), manifest, args.expect_cards_sha256
    )
    identifiers = sorted(cards)[: args.sample_endpoints]
    if len(identifiers) != args.sample_endpoints or not identifiers:
        raise SmokeError("sample size unavailable")
    started = time.perf_counter()
    rows = []
    diagnostics = []
    for identifier in identifiers:
        features, receipt = wl_feature_dict(cards[identifier]["code"])
        rows.append(features)
        diagnostics.append(receipt)
    matrix = hashed_l2_matrix(rows)
    elapsed = time.perf_counter() - started
    repeat_rows = [wl_feature_dict(cards[identifier]["code"])[0] for identifier in identifiers[:8]]
    repeat_matrix = hashed_l2_matrix(repeat_rows)
    deterministic_prefix = matrix_digest(matrix[:8].tocsr()) == matrix_digest(repeat_matrix)
    if not deterministic_prefix or matrix.shape != (len(identifiers), HASHED_DIMENSIONS):
        raise SmokeError("feature determinism/shape failure")
    norms = (matrix.multiply(matrix).sum(axis=1).A1 ** 0.5).tolist()
    if not all(math.isfinite(value) and abs(value - 1.0) <= 1e-12 for value in norms):
        raise SmokeError("graph normalization failure")
    projected_feature_seconds = elapsed * FULL_ENDPOINTS / len(identifiers)
    projected_total_seconds = projected_feature_seconds + OVERHEAD_ALLOWANCE_SECONDS
    maximum_rss_raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    maximum_rss_gib = maximum_rss_raw / (1024.0 * 1024.0)
    gates = {
        "all_sample_endpoints_featured": matrix.shape[0] == len(identifiers),
        "deterministic_prefix": deterministic_prefix,
        "finite_unit_norm_rows": True,
        "projected_total_wall_le_7200s": projected_total_seconds <= MAX_PROJECTED_WALL_SECONDS,
        "peak_rss_le_32gib": maximum_rss_gib <= MAX_RSS_GIB,
        "train_card_scope_exact": card_audit["selected_endpoints"] == FULL_ENDPOINTS,
    }
    return {
        "status": "WL_GRAPH_ENGINEERING_GATE_PASS" if all(gates.values()) else "WL_GRAPH_ENGINEERING_GATE_FAIL",
        "protocol": PROTOCOL,
        "source_commit": args.source_commit,
        "protocol_sha256": sha256(protocol_path),
        "configuration": {
            "sample_endpoints": len(identifiers),
            "full_endpoints": FULL_ENDPOINTS,
            "wl_iterations": WL_ITERATIONS,
            "maximum_nodes": MAXIMUM_NODES,
            "hashed_dimensions": HASHED_DIMENSIONS,
            "overhead_allowance_seconds": OVERHEAD_ALLOWANCE_SECONDS,
        },
        "timing": {
            "sample_elapsed_seconds": elapsed,
            "projected_full_feature_seconds": projected_feature_seconds,
            "projected_total_build_seconds": projected_total_seconds,
        },
        "memory": {"maximum_rss_gib": maximum_rss_gib},
        "matrix": {
            "shape": list(matrix.shape),
            "nnz": int(matrix.nnz),
            "digest_sha256": matrix_digest(matrix),
            "deterministic_prefix": deterministic_prefix,
        },
        "graph_diagnostics": aggregate_diagnostics(diagnostics),
        "gates": gates,
        "inputs": {
            "cards_sha256": args.expect_cards_sha256,
            "manifest_sha256": args.expect_manifest_sha256,
            "manifest_summary_sha256": args.expect_manifest_summary_sha256,
        },
        "reproducibility": {
            "python": platform.python_version(),
            "randomness_used": False,
        },
        "scope": {
            "v11_frozen_or_extension_read": False,
            "outcome_metric_computed": False,
            "raw_code_identity_or_task_emitted": False,
            "gpu": 0,
            "api_calls": 0,
            "base_llm_updates": 0,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--cards", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--manifest-summary", required=True)
    parser.add_argument("--expect-cards-sha256", required=True)
    parser.add_argument("--expect-manifest-sha256", required=True)
    parser.add_argument("--expect-manifest-summary-sha256", required=True)
    parser.add_argument("--sample-endpoints", type=int, default=256)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite output: {output}")
    try:
        receipt = run(args)
    except (SmokeError, OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"WL_GRAPH_SMOKE_ERROR: {error}", file=sys.stderr)
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(
        receipt["status"],
        f"sample={receipt['configuration']['sample_endpoints']}",
        f"projected_total_s={receipt['timing']['projected_total_build_seconds']}",
        f"rss_gib={receipt['memory']['maximum_rss_gib']}",
    )
    return 0 if receipt["status"].endswith("PASS") else 3


if __name__ == "__main__":
    raise SystemExit(main())
