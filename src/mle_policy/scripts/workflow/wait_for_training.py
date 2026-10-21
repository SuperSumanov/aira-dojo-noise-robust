#!/usr/bin/env python3
"""Wait for N/N in the given log, its checkpoint, and released training GPUs."""

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path


def completed_step(log: Path) -> int | None:
    with log.open("rb") as stream:
        stream.seek(max(0, log.stat().st_size - 1024 * 1024))
        tail = stream.read().decode(errors="replace")
    progress = re.findall(r"Training Progress:[^\r\n]*?(\d+)/(\d+)", tail)
    if progress:
        current, total = map(int, progress[-1])
        if current == total and total > 0:
            return total
    return None


def checkpoint_signature(actor: Path):
    shards = sorted(actor.glob("model_world_size_*_rank_*.pt"))
    if not shards or not (actor / "huggingface/config.json").is_file():
        return None
    ranks = [tuple(map(int, re.fullmatch(r"model_world_size_(\d+)_rank_(\d+)\.pt", p.name).groups())) for p in shards]
    world = ranks[0][0]
    if set(ranks) != {(world, rank) for rank in range(world)}:
        return None
    stats = [p.stat() for p in shards]
    if any(s.st_size == 0 for s in stats):
        return None
    return [(s.st_size, s.st_mtime_ns) for s in stats]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("run_root", type=Path)
    args = parser.parse_args()
    deadline = time.monotonic() + 24 * 3600
    previous = None
    while time.monotonic() < deadline:
        step = completed_step(args.log)
        signature = checkpoint_signature(args.run_root / f"global_step_{step}" / "actor") if step else None
        if signature is not None and (step, signature) == previous:
            processes = subprocess.check_output([
                "nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"
            ], text=True).strip()
            if not processes:
                print(step, flush=True)
                return
        previous = (step, signature)
        time.sleep(60)
    sys.exit("Training did not finish with a stable checkpoint and free GPUs within 24 hours")


if __name__ == "__main__":
    main()
