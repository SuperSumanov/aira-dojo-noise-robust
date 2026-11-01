"""Inherit existing original group splits without assigning new splits."""

import argparse
from collections import Counter
import json
from pathlib import Path

from .. import groupdata

def align_splits(original: Path, hindsight: Path) -> dict:
    """Inherit splits by group_id and update the target splits, manifest, and alignment report."""
    original, hindsight = original.resolve(), hindsight.resolve()
    if original == hindsight:
        raise ValueError("Original and hindsight datasets must differ")
    splits = groupdata.read_splits(original)
    if splits is None:
        raise ValueError("Original dataset has no splits")
    originals = {group["group_id"]: group for group in groupdata.read_groups(original)}
    groups = groupdata.read_groups(hindsight)
    records = []
    for group in groups:
        group_id = group["group_id"]
        source = originals[group_id]
        if group["batch"] != source["batch"] or group["task"] != source["task"]:
            raise ValueError(f"Source group mismatch: {group_id}")
        split = splits[group_id]
        records.append({"group_id": group_id, "task": group["task"], "split": split})
    destination = hindsight / groupdata.SPLITS_FILE
    with destination.open("w", encoding="utf-8") as handle:
        for record in records:
            groupdata.write_jsonl(handle, record)
    report = {
        "source_dataset": str(original),
        "dataset": str(hindsight),
        "groups": len(records),
        "group_counts": dict(Counter(record["split"] for record in records)),
    }
    manifest = groupdata.read_manifest(hindsight)
    manifest["split"] = {"split_by": "original_group", **report}
    groupdata.write_manifest(hindsight, manifest)
    with (hindsight / "split_alignment.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return report


def main():
    """Parse dataset paths, align group splits, and print the report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", required=True, type=Path)
    parser.add_argument("--hindsight", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(align_splits(args.original, args.hindsight), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
