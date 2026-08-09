"""Reconstruct physical-run membership from the ordered raw card batches.

The old tree split treated a labeled node whose parent was filtered out as a new
root.  Batch files are written run-by-run, so run boundaries can be recovered by
task changes or non-increasing journal steps.  The two validations below prevent
silently producing an invalid map.

Usage:
  python -m src.mle_critic.src.preprocess.run_segment MANIFEST CARDS_DIR OUT_MAP
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path


def build_map(manifest: Path, cards_dir: Path):
    run_of, cards, seg_tasks = {}, {}, {}
    for fn in (x.strip() for x in manifest.read_text().splitlines()):
        if not fn:
            continue
        path = cards_dir / fn
        if not path.exists():
            raise FileNotFoundError(path)
        prev_task, prev_step, seg = None, None, -1
        for line in path.open():
            d = json.loads(line)
            cards[d["id"]] = d
            task = d["task"]["name"]
            step = (d.get("lineage") or {}).get("step") or 0
            if task != prev_task or (prev_step is not None and step <= prev_step):
                seg += 1
            rid = f"{fn}:{seg}"
            run_of[d["id"]] = rid
            seg_tasks.setdefault(rid, set()).add(task)
            prev_task, prev_step = task, step

    cross_parent = []
    for cid, d in cards.items():
        parent = (d.get("lineage") or {}).get("parent_id")
        if parent and parent in run_of and run_of[parent] != run_of[cid]:
            cross_parent.append((cid, parent))
    mixed = [rid for rid, tasks in seg_tasks.items() if len(tasks) > 1]
    if cross_parent or mixed:
        raise ValueError(
            f"invalid run segmentation: {len(cross_parent)} cross-run parents, "
            f"{len(mixed)} mixed-task segments"
        )
    return run_of, cards


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", type=Path)
    ap.add_argument("cards_dir", type=Path)
    ap.add_argument("out_map", type=Path)
    args = ap.parse_args()
    run_of, cards = build_map(args.manifest, args.cards_dir)
    args.out_map.parent.mkdir(parents=True, exist_ok=True)
    args.out_map.write_text(json.dumps(run_of, sort_keys=True))
    print(f"cards={len(cards)} runs reconstructed={len(set(run_of.values()))}")
    print(f"wrote {args.out_map}")


if __name__ == "__main__":
    main()
