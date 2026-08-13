#!/usr/bin/env python3
"""Deterministically select one prior usable and one prior silent card for path-coverage smoke."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

EXPECTED_MANIFEST = "77f696828010e2d6ae10a9b9de2d9ec05d44975b1285ea763d9850a7f30ca4ef"
EXPECTED_RESULTS = "b1266d04912596b1e37e13f79ce2387a962f5510cfa264aa1a97b7a1c443180d"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def usable(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--results", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--audit", type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists() or args.audit.exists():
        raise RuntimeError("refusing to overwrite smoke manifest/audit")
    if sha256(args.manifest) != EXPECTED_MANIFEST or sha256(args.results) != EXPECTED_RESULTS:
        raise RuntimeError("locked input SHA mismatch")

    manifest = rows(args.manifest)
    result_rows = rows(args.results)
    cap120 = {}
    for row in result_rows:
        if row.get("cap") == 120:
            cid = str(row.get("card_id", ""))
            if not cid or cid in cap120:
                raise RuntimeError("duplicate/missing cap=120 card")
            cap120[cid] = row
    if len(manifest) != 230 or len(cap120) != 230:
        raise RuntimeError("locked input count mismatch")

    selected = []
    seen_state = set()
    for row in manifest:
        cid = str(row["card_id"])
        if cid not in cap120:
            raise RuntimeError(f"missing cap=120 result {cid}")
        state = "usable" if usable(cap120[cid].get("sub_score")) else "silent"
        if state not in seen_state:
            selected.append(row)
            seen_state.add(state)
        if seen_state == {"usable", "silent"}:
            break
    if len(selected) != 2:
        raise RuntimeError("failed to cover usable and silent paths")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8", newline="") as f:
        for row in selected:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    audit = {
        "selection_only_for_infrastructure_path_coverage": True,
        "input_manifest_sha256": EXPECTED_MANIFEST,
        "input_results_sha256": EXPECTED_RESULTS,
        "output_manifest_sha256": sha256(args.out),
        "cards": [
            {
                "card_id": row["card_id"],
                "competition": row["competition"],
                "prior_fresh_cap120_state": (
                    "usable" if usable(cap120[row["card_id"]].get("sub_score")) else "silent"
                ),
            }
            for row in selected
        ],
    }
    args.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
