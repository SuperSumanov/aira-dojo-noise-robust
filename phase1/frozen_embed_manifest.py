#!/usr/bin/env python3
"""Build a label-blind endpoint manifest for frozen-embedding extraction."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import zlib
from pathlib import Path
from typing import Any


SEED = 887


class IntegrityError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def task_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("desc") or "")
    return str(value or "")


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def load_pairs(path: Path, expected_split: str) -> tuple[list[dict[str, Any]], str]:
    raw = path.read_bytes()
    rows: list[dict[str, Any]] = []
    required = {
        "better",
        "worse",
        "parent",
        "task",
        "run_id",
        "budget",
        "intask_split",
    }
    for line_number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        missing = required - set(row)
        if missing:
            raise IntegrityError(f"{path}:{line_number} missing {sorted(missing)}")
        if str(row["intask_split"]) != expected_split:
            raise IntegrityError(
                f"{path}:{line_number} split={row['intask_split']!r}, expected {expected_split!r}"
            )
        if int(row["budget"]) != 0:
            raise IntegrityError(f"{path}:{line_number} budget is not zero")
        if row["better"] == row["worse"]:
            raise IntegrityError(f"{path}:{line_number} identical endpoints")
        rows.append(row)
    if not rows:
        raise IntegrityError(f"empty pair file: {path}")
    oriented = collections.Counter((str(row["better"]), str(row["worse"])) for row in rows)
    duplicates = sum(count - 1 for count in oriented.values())
    unordered: dict[tuple[str, str], set[tuple[str, str]]] = collections.defaultdict(set)
    for pair in oriented:
        unordered[tuple(sorted(pair))].add(pair)
    reversed_conflicts = sum(len(directions) > 1 for directions in unordered.values())
    if duplicates or reversed_conflicts:
        raise IntegrityError(
            f"duplicates={duplicates}, reversed_conflicts={reversed_conflicts}"
        )
    return rows, hashlib.sha256(raw).hexdigest()


def build_manifest(
    cards_path: Path,
    pairs_path: Path,
    run_map_path: Path,
    expected_split: str,
    num_shards: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if num_shards <= 0:
        raise ValueError("num_shards must be positive")
    pairs, pairs_sha = load_pairs(pairs_path, expected_split)
    run_map = json.loads(run_map_path.read_text(encoding="utf-8"))
    endpoints = {
        str(row[key]) for row in pairs for key in ("better", "worse")
    }
    endpoint_expectation: dict[str, tuple[str, str]] = {}
    for row in pairs:
        expected = (str(row["task"]), str(row["run_id"]))
        for key in ("better", "worse"):
            card_id = str(row[key])
            previous = endpoint_expectation.setdefault(card_id, expected)
            if previous != expected:
                raise IntegrityError(f"endpoint context conflict: {card_id}")

    found: dict[str, dict[str, Any]] = {}
    cards_digest = hashlib.sha256()
    corpus_rows = 0
    with cards_path.open("rb") as handle:
        for raw_line in handle:
            cards_digest.update(raw_line)
            corpus_rows += 1
            row = json.loads(raw_line)
            card_id = str(row["id"])
            if card_id not in endpoints:
                continue
            if card_id in found:
                raise IntegrityError(f"duplicate card id: {card_id}")
            code = str(row.get("code") or "")
            task = task_name(row.get("task"))
            run = str(row.get("run_id") or run_map.get(card_id) or "")
            expected_task, expected_run = endpoint_expectation[card_id]
            if not code:
                raise IntegrityError(f"empty code: {card_id}")
            if task != expected_task:
                raise IntegrityError(f"task mismatch for {card_id}: {task} != {expected_task}")
            if run_map.get(card_id) != expected_run or run != expected_run:
                raise IntegrityError(f"run mismatch for {card_id}")
            found[card_id] = {
                "card_id": card_id,
                "task": task,
                "run_id": run,
                "code_chars": len(code),
                "code_sha256": hashlib.sha256(code.encode("utf-8")).hexdigest(),
                "shard": zlib.crc32(f"{SEED}:{card_id}".encode("utf-8")) % num_shards,
            }
    missing = sorted(endpoints - found.keys())
    if missing:
        raise IntegrityError(f"missing endpoint cards, examples={missing[:8]}")
    manifest = [found[card_id] for card_id in sorted(found)]
    shard_counts = collections.Counter(int(row["shard"]) for row in manifest)
    task_counts = collections.Counter(str(row["task"]) for row in manifest)
    run_counts = collections.Counter(str(row["run_id"]) for row in manifest)
    summary = {
        "status": "MANIFEST_COMPLETE",
        "protocol": "frozen_embed_v11_discovery_v1",
        "expected_split": expected_split,
        "seed": SEED,
        "num_shards": num_shards,
        "pairs": len(pairs),
        "endpoints": len(manifest),
        "runs": len(run_counts),
        "tasks": len(task_counts),
        "dominant_task": task_counts.most_common(1)[0][0],
        "dominant_task_share": task_counts.most_common(1)[0][1] / len(manifest),
        "per_shard": {str(key): shard_counts[key] for key in range(num_shards)},
        "per_task": dict(sorted(task_counts.items())),
        "inputs": {
            "cards": str(cards_path),
            "cards_sha256": cards_digest.hexdigest(),
            "cards_rows": corpus_rows,
            "pairs": str(pairs_path),
            "pairs_sha256": pairs_sha,
            "run_map": str(run_map_path),
            "run_map_sha256": sha256(run_map_path),
        },
    }
    return manifest, summary


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", required=True, type=Path)
    parser.add_argument("--pairs", required=True, type=Path)
    parser.add_argument("--run-map", required=True, type=Path)
    parser.add_argument("--expected-split", required=True, choices=("train", "test"))
    parser.add_argument("--num-shards", type=int, default=4)
    parser.add_argument("--out-manifest", required=True, type=Path)
    parser.add_argument("--out-summary", required=True, type=Path)
    parser.add_argument("--expect-cards-sha256")
    parser.add_argument("--expect-pairs-sha256")
    parser.add_argument("--expect-run-map-sha256")
    return parser.parse_args()


def main() -> int:
    args = arguments()
    expectations = (
        (args.cards, args.expect_cards_sha256),
        (args.pairs, args.expect_pairs_sha256),
        (args.run_map, args.expect_run_map_sha256),
    )
    for path, expected in expectations:
        if expected and sha256(path) != expected.lower():
            raise IntegrityError(f"SHA256 mismatch: {path}")
    if args.out_manifest.exists() or args.out_summary.exists():
        raise FileExistsError("refusing to overwrite manifest outputs")
    manifest, summary = build_manifest(
        args.cards,
        args.pairs,
        args.run_map,
        args.expected_split,
        args.num_shards,
    )
    manifest_text = "".join(
        json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in manifest
    )
    atomic_text(args.out_manifest, manifest_text)
    summary["outputs"] = {
        "manifest": str(args.out_manifest),
        "manifest_sha256": hashlib.sha256(manifest_text.encode("utf-8")).hexdigest(),
    }
    atomic_text(
        args.out_summary,
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )
    print(
        "FROZEN_EMBED_MANIFEST_COMPLETE",
        f"pairs={summary['pairs']}",
        f"endpoints={summary['endpoints']}",
        f"runs={summary['runs']}",
        f"tasks={summary['tasks']}",
        f"sha256={summary['outputs']['manifest_sha256']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
