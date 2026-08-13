#!/usr/bin/env python3
"""Validate the label-blind 16-endpoint GPU smoke and extrapolate wall time."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np


class SmokeError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-dir", required=True, type=Path)
    parser.add_argument("--manifest-summary", required=True, type=Path)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--worker-source", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--max-extrapolated-s", type=float, default=12_600.0)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if args.out.exists():
        raise FileExistsError(args.out)
    metadata_path = args.smoke_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    summary = json.loads(args.manifest_summary.read_text(encoding="utf-8"))
    checks = {
        "status_complete": metadata.get("status") == "COMPLETE",
        "protocol_exact": metadata.get("protocol") == "frozen_embed_v11_discovery_v1",
        "commit_exact": metadata.get("git_commit") == args.commit,
        "worker_source_exact": metadata.get("source_sha256") == sha256(args.worker_source),
        "manifest_exact": metadata.get("inputs", {}).get("manifest_sha256")
        == args.manifest_sha256.lower(),
        "model_exact": metadata.get("inputs", {}).get("model_weights_sha256")
        == args.model_sha256.lower(),
        "config_exact": metadata.get("config")
        == {
            "shard": 0,
            "num_shards": 4,
            "max_len": 8192,
            "head_fraction": 0.25,
            "batch_size": 2,
            "chunk_size": 32,
            "limit_cards": 16,
        },
        "feature_exact": metadata.get("feature", {}).get("definition")
        == "concat(masked_mean_last_hidden)"
        and metadata.get("feature", {}).get("dtype") == "float16"
        and metadata.get("feature", {}).get("dimension") == 1792
        and metadata.get("feature", {}).get("task_prefix") is True,
        "cards_exact": metadata.get("completed_cards") == 16,
    }
    records = metadata.get("chunks") or []
    actual = sorted(path.name for path in args.smoke_dir.glob("chunk_*.npz"))
    checks["chunk_inventory_exact"] = [str(record["file"]) for record in records] == actual
    rows = 0
    dimensions: set[int] = set()
    token_values: list[int] = []
    finite = True
    for record in records:
        path = args.smoke_dir / str(record["file"])
        if sha256(path) != str(record["sha256"]):
            raise SmokeError(f"chunk hash mismatch: {path}")
        with np.load(path, allow_pickle=False) as data:
            ids = data["card_ids"]
            features = np.asarray(data["features"])
            tokens = np.asarray(data["token_counts"])
        rows += len(ids)
        dimensions.add(int(features.shape[1]) if features.ndim == 2 else -1)
        finite &= bool(np.isfinite(features).all())
        token_values.extend(map(int, tokens.tolist()))
    checks["chunk_rows_exact"] = rows == 16
    checks["chunk_dimension_exact"] = dimensions == {1792}
    checks["chunk_finite"] = finite
    checks["tokens_valid"] = (
        len(token_values) == 16
        and min(token_values) > 0
        and max(token_values) <= 8192
    )
    per_shard = {int(key): int(value) for key, value in summary["per_shard"].items()}
    elapsed_s = float(metadata.get("elapsed_s", math.nan))
    extrapolated_s = elapsed_s / 16.0 * max(per_shard.values())
    checks["elapsed_finite_positive"] = math.isfinite(elapsed_s) and elapsed_s > 0.0
    checks["extrapolated_within_cap"] = (
        math.isfinite(extrapolated_s) and extrapolated_s <= args.max_extrapolated_s
    )
    checks["all"] = all(checks.values())
    output = {
        "status": "SMOKE_PASS" if checks["all"] else "SMOKE_FAIL",
        "checks": checks,
        "metadata_sha256": sha256(metadata_path),
        "manifest_summary_sha256": sha256(args.manifest_summary),
        "rows": rows,
        "feature_dimension": sorted(dimensions),
        "token_minimum": min(token_values) if token_values else None,
        "token_median": float(np.median(token_values)) if token_values else None,
        "token_maximum": max(token_values) if token_values else None,
        "elapsed_s": elapsed_s,
        "maximum_full_shard_cards": max(per_shard.values()),
        "conservative_extrapolated_max_shard_s": extrapolated_s,
        "hard_extrapolation_cap_s": args.max_extrapolated_s,
    }
    atomic_json(args.out, output)
    print(
        output["status"],
        f"rows={rows}",
        f"elapsed_s={elapsed_s:.3f}",
        f"extrapolated_s={extrapolated_s:.3f}",
        flush=True,
    )
    if not checks["all"]:
        raise SmokeError(json.dumps(checks, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
