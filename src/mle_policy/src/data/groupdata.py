"""The on-disk layout of the episode-grouped dataset (the pipeline's middle layer).

A *dataset directory* is produced by ``build_batch_groups`` (one batch) and by
``aggregate_groups`` (many batches merged) and contains:

``samples.jsonl``
    One line per LLM call: prompt, completion, node outcome, episode outcome.
    Calls from one episode share a group id.
``groups.jsonl``
    One line per group: which episodes have the same root input under the same
    environment. Each member references all of its call-level samples.  The group's *canonical* prompt is deliberately not repeated
    here -- prompts are ~83% of the bytes and can be recovered from any member
    sample.
``manifest.json``
    Build config, environment signature, counts and histograms.
``splits.jsonl``
    Optional, written by ``assign_splits``: ``group_id``, ``task``, ``split``.

Everything downstream (the ``to_sft`` / ``to_dpo`` / ``to_grpo`` programs) reads
the dataset through the helpers here.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Iterator

SAMPLES_FILE = "samples.jsonl"
GROUPS_FILE = "groups.jsonl"
MANIFEST_FILE = "manifest.json"
SPLITS_FILE = "splits.jsonl"


def write_jsonl(handle, record: dict[str, Any]) -> None:
    handle.write(json.dumps(record, ensure_ascii=False))
    handle.write("\n")


def write_manifest(dataset_dir: Path, manifest: dict[str, Any]) -> None:
    with (dataset_dir / MANIFEST_FILE).open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def read_manifest(dataset_dir: Path) -> dict[str, Any]:
    path = dataset_dir / MANIFEST_FILE
    if not path.is_file():
        raise ValueError(f"{dataset_dir} is not a dataset directory (no {MANIFEST_FILE})")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def iter_samples(dataset_dir: Path) -> Iterator[dict[str, Any]]:
    """Stream ``samples.jsonl``."""
    with (dataset_dir / SAMPLES_FILE).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def read_groups(dataset_dir: Path) -> list[dict[str, Any]]:
    """Load the compact group index into memory."""
    groups: list[dict[str, Any]] = []
    with (dataset_dir / GROUPS_FILE).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                groups.append(json.loads(line))
    return groups


def read_splits(dataset_dir: Path) -> dict[str, str] | None:
    """Return ``group_id -> split`` or ``None`` when no split was assigned."""
    path = dataset_dir / SPLITS_FILE
    if not path.is_file():
        return None
    splits: dict[str, str] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                splits[record["group_id"]] = record["split"]
    return splits


def group_size_histogram(groups: Iterable[dict[str, Any]]) -> dict[str, int]:
    histogram: dict[str, int] = defaultdict(int)
    for group in groups:
        histogram[str(group["size"])] += 1
    return dict(sorted(histogram.items(), key=lambda item: int(item[0])))
