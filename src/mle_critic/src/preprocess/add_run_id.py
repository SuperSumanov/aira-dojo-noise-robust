"""Inject a reproducible physical ``run_id`` into every card."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("dst", type=Path)
    ap.add_argument("run_map", type=Path)
    args = ap.parse_args()
    run_map = json.loads(args.run_map.read_text())
    missing = 0
    n = 0
    args.dst.parent.mkdir(parents=True, exist_ok=True)
    with args.src.open() as inp, args.dst.open("w") as out:
        for line in inp:
            card = json.loads(line)
            run_id = run_map.get(card["id"])
            if run_id is None:
                missing += 1
            card["run_id"] = run_id
            card.setdefault("provenance", {})["run_id_source"] = "reconstructed:file-contiguity"
            out.write(json.dumps(card, separators=(",", ":")) + "\n")
            n += 1
    print(f"[add_run_id] {n} cards -> {args.dst}; unmapped {missing}")
    if missing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
