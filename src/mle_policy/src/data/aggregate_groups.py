"""Stage 2: merge the per-batch dataset directories into one.

Grouping already happened inside each batch, so this is a plain concatenation:
the merged dataset keeps every batch's groups intact and adds nothing across
batches.  It writes ``samples.jsonl``, ``groups.jsonl`` and a manifest that
summarises which batches went in.

No train/val split is decided here -- that is ``assign_splits``.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from . import groupdata


def find_batch_dirs(paths: Iterable[Path]) -> list[Path]:
    """Resolve each input to batch dataset directories.

    An input that is itself a dataset directory is used directly; anything else
    is treated as a parent whose immediate subdirectories are batches.
    """
    batches: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path).resolve()
        if (path / groupdata.MANIFEST_FILE).is_file():
            batches.append(path)
            continue
        if not path.is_dir():
            raise ValueError(f"Batch input does not exist: {path}")
        batches.extend(sorted(child for child in path.iterdir() if (child / groupdata.MANIFEST_FILE).is_file()))
    if not batches:
        raise ValueError("No batch dataset directories found")
    return batches


def aggregate(batch_dirs: list[Path], output_dir: Path, verbose: bool = True) -> dict[str, Any]:
    """Concatenate the batches and write a merged dataset directory."""
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    samples = 0
    groups = 0
    seen_group_ids: set[str] = set()
    operators: Counter[str] = Counter()
    per_batch: list[dict[str, Any]] = []
    group_size_histogram: dict[str, int] = defaultdict(int)
    tasks: set[str] = set()
    providers: set[str] = set()
    clients: set[str] = set()
    env_signatures: set[str] = set()
    resolved_episodes = 0
    episodes: set[str] = set()
    normalize_packages: set[bool] = set()

    with (
        (output_dir / groupdata.SAMPLES_FILE).open("w", encoding="utf-8") as samples_file,
        (output_dir / groupdata.GROUPS_FILE).open("w", encoding="utf-8") as groups_file,
    ):
        for batch_dir in batch_dirs:
            manifest = groupdata.read_manifest(batch_dir)
            normalize_packages.add(bool(manifest.get("normalize_packages", True)))
            batch_samples = 0
            for sample in groupdata.iter_samples(batch_dir):
                groupdata.write_jsonl(samples_file, sample)
                batch_samples += 1
                samples += 1
                operators[sample["operator"]] += 1
                tasks.add(sample["task"])
                providers.update(sample["providers"])
                clients.update(sample["clients"])
                env_signatures.add(sample["env_signature"])
                if sample["episode_id"] not in episodes:
                    episodes.add(sample["episode_id"])
                    resolved_episodes += sample["episode_terminal_step"] is not None
            batch_groups = 0
            for group in groupdata.read_groups(batch_dir):
                if group["group_id"] in seen_group_ids:
                    raise ValueError(
                        f"Group {group['group_id']} appears in more than one batch "
                        f"({batch_dir}); batches must be disjoint"
                    )
                seen_group_ids.add(group["group_id"])
                groupdata.write_jsonl(groups_file, group)
                batch_groups += 1
                groups += 1
                group_size_histogram[str(group["size"])] += 1
            per_batch.append(
                {
                    "batch": manifest.get("batch", batch_dir.name),
                    "batch_dir": str(batch_dir),
                    "journals": manifest.get("journals"),
                    "samples": batch_samples,
                    "groups": batch_groups,
                }
            )

    size_histogram = dict(sorted(group_size_histogram.items(), key=lambda item: int(item[0])))
    if len(normalize_packages) != 1:
        raise ValueError(f"Batches disagree about normalize_packages: {sorted(normalize_packages)}")
    manifest = {
        "kind": "aggregate",
        "normalize_packages": normalize_packages.pop(),
        "batches": per_batch,
        "journals": sum(batch["journals"] or 0 for batch in per_batch),
        "samples": samples,
        "groups": groups,
        "tasks": sorted(tasks),
        "providers": sorted(providers),
        "clients": sorted(clients),
        "env_signatures": sorted(env_signatures),
        "environments": len(env_signatures),
        "episodes": len(episodes),
        "episodes_resolved": resolved_episodes,
        "operators": {name: count for name, count in operators.most_common()},
        "group_size_histogram": size_histogram,
    }
    groupdata.write_manifest(output_dir, manifest)
    if verbose:
        summary = {key: value for key, value in manifest.items() if key not in ("batches", "group_size_histogram")}
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--input",
        required=True,
        nargs="+",
        help="Batch dataset directories, or parents whose immediate subdirectories are batches.",
    )
    parser.add_argument("--output-dir", required=True, help="Where to write the merged dataset directory.")
    args = parser.parse_args()

    aggregate(find_batch_dirs([Path(path) for path in args.input]), Path(args.output_dir))


if __name__ == "__main__":
    main()
