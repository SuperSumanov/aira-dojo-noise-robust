#!/usr/bin/env python3
"""Audit train-vs-held run/node/raw-code isolation without opening frozen pairs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


class IntegrityError(RuntimeError):
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
    parser.add_argument("--cards", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--split", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--expect-cards-sha256")
    parser.add_argument("--expect-manifest-sha256")
    parser.add_argument("--expect-split-sha256")
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if args.out.exists():
        raise FileExistsError(args.out)
    for path, expected in (
        (args.cards, args.expect_cards_sha256),
        (args.manifest, args.expect_manifest_sha256),
        (args.split, args.expect_split_sha256),
    ):
        if expected and sha256(path) != expected.lower():
            raise IntegrityError(f"SHA256 mismatch: {path}")
    manifest = [
        json.loads(line)
        for line in args.manifest.read_text(encoding="utf-8").splitlines()
        if line
    ]
    split = json.loads(args.split.read_text(encoding="utf-8"))
    if int(split.get("seed", -1)) != 7:
        raise IntegrityError("split seed is not frozen at 7")
    all_runs = set(map(str, split.get("all") or []))
    hold_runs = set(map(str, split.get("hold") or []))
    prior_all = set(map(str, split.get("prior_all") or []))
    prior_hold = set(map(str, split.get("prior_hold") or []))
    if not hold_runs <= all_runs or not prior_all <= all_runs or not prior_hold <= hold_runs:
        raise IntegrityError("append-only run split survival failed")
    train_ids = {str(row["card_id"]) for row in manifest}
    train_runs = {str(row["run_id"]) for row in manifest}
    train_hashes = {str(row["code_sha256"]) for row in manifest}
    if train_runs & hold_runs:
        raise IntegrityError("training endpoint manifest includes held physical run")

    held_ids: set[str] = set()
    held_hashes: set[str] = set()
    cards_rows = 0
    cards_runs: set[str] = set()
    with args.cards.open("rb") as handle:
        for raw_line in handle:
            cards_rows += 1
            row = json.loads(raw_line)
            card_id = str(row["id"])
            run = str(row.get("run_id") or "")
            if not run:
                raise IntegrityError(f"card has no run_id: {card_id}")
            cards_runs.add(run)
            if run not in hold_runs:
                continue
            code = str(row.get("code") or "")
            if not code:
                raise IntegrityError(f"held card has empty code: {card_id}")
            held_ids.add(card_id)
            held_hashes.add(hashlib.sha256(code.encode("utf-8")).hexdigest())
    if cards_runs != all_runs:
        raise IntegrityError("cards physical-run set differs from frozen split all-runs set")
    node_overlap = train_ids & held_ids
    code_overlap = train_hashes & held_hashes
    if node_overlap or code_overlap:
        raise IntegrityError(
            f"held leakage node={len(node_overlap)} raw_code_hash={len(code_overlap)}"
        )
    output = {
        "status": "TRAIN_HELD_ISOLATION_PASS",
        "frozen_pair_file_opened": False,
        "inputs": {
            "cards_sha256": sha256(args.cards),
            "manifest_sha256": sha256(args.manifest),
            "split_sha256": sha256(args.split),
        },
        "cards": cards_rows,
        "all_runs": len(all_runs),
        "hold_runs": len(hold_runs),
        "prior_hold_runs": len(prior_hold),
        "prior_hold_survived": len(prior_hold),
        "train_endpoint_runs": len(train_runs),
        "train_endpoints": len(train_ids),
        "held_cards": len(held_ids),
        "run_overlap": 0,
        "node_overlap": 0,
        "raw_code_hash_overlap": 0,
    }
    atomic_json(args.out, output)
    print(
        "TRAIN_HELD_ISOLATION_PASS",
        f"train_endpoints={len(train_ids)}",
        f"train_runs={len(train_runs)}",
        f"hold_runs={len(hold_runs)}",
        "node_overlap=0 raw_code_hash_overlap=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
