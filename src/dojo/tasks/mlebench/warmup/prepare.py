"""Build an immutable warmup version from an existing prepared/public directory."""

import argparse
import hashlib
import json
import math
import tempfile
from pathlib import Path

from dojo.tasks.mlebench.warmup.converters import CONVERTERS
from dojo.tasks.mlebench.warmup.datasets import check_ids, read_table


def inventory(directory: Path) -> dict:
    """Hash file contents and reject links to files outside the published dataset."""
    result = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Prepared source contains a symlink: {path}")
        if path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                    digest.update(block)
            result[str(path.relative_to(directory))] = {
                "bytes": path.stat().st_size,
                "sha256": digest.hexdigest(),
            }
    return result


def submission_ids(competition_id, sample):
    column = "example_id" if competition_id == "tensorflow2-question-answering" else "id"
    return check_ids(sample[column])


def prepare_warmup(data_dir: Path, output: Path, competition_id: str, seed=0, count=None):
    convert = CONVERTERS[competition_id]
    source = (data_dir / competition_id / "prepared/public").resolve()
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"Use a new version directory: {output}")
    if output.is_relative_to(source.parent) or source.is_relative_to(output):
        raise ValueError("Warmup output must be separate from the source prepared directory")
    sample = read_table(source / "sample_submission.csv")
    original_ids = submission_ids(competition_id, sample)
    if competition_id == "tensorflow2-question-answering":
        original_samples = {identifier.rsplit("_", 1)[0] for identifier in original_ids}
        if set(original_ids) != {
            f"{identifier}_{kind}" for identifier in original_samples for kind in ["short", "long"]
        }:
            raise ValueError("TensorFlow QA sample must have short/long pairs")
        test_count = len(original_samples)
    else:
        test_count = len(original_ids)
    target = min(500, math.ceil(0.2 * test_count)) if count is None else count
    if not 0 < target <= 500:
        raise ValueError("Warmup count must be between 1 and 500")
    source_inventory = inventory(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".warmup-", dir=output.parent) as temporary:
        stage = Path(temporary) / "version"
        stage.mkdir()
        private = stage / "private"
        private.mkdir(mode=0o700)
        metadata = convert(source, stage / "public", private, target, seed)
        warmup_samples = check_ids(metadata["warmup_ids"])
        warmup_rows = (
            [f"{identifier}_{kind}" for identifier in warmup_samples for kind in ["short", "long"]]
            if competition_id == "tensorflow2-question-answering"
            else warmup_samples
        )
        combined = submission_ids(competition_id, read_table(stage / "public/sample_submission.csv"))
        if set(original_ids) & set(warmup_rows) or set(combined) != set(original_ids + warmup_rows):
            raise ValueError("Combined sample submission IDs do not match the split")
        if metadata["train_count"] <= len(warmup_samples):
            raise ValueError("Warmup must leave training samples")
        remaining_ids = metadata.pop("remaining_train_ids", None)
        if remaining_ids is not None and set(remaining_ids) & set(original_ids + warmup_rows):
            raise ValueError("Training IDs overlap test IDs")
        description = stage / "public/description.md"
        with description.open("a") as stream:
            stream.write(
                "\n\n## Harness warmup feedback\n"
                f"Training samples: {metadata['train_count'] - len(warmup_samples)}. "
                f"Test samples: {test_count + len(warmup_samples)}.\n"
                "Predict all test inputs in one submission.csv. A small held-out subset is "
                "graded separately after submission and its aggregate score is returned "
                "for diagnosing the prediction pipeline. Continue to print your own CV metric.\n"
            )
        public_inventory = inventory(stage / "public")
        manifest = {
            "format_version": 1,
            "competition_id": competition_id,
            "seed": seed,
            "source_public": str(source),
            "source_inventory": source_inventory,
            "public_inventory": public_inventory,
            "original_test_count": test_count,
            "target_count": target,
            "actual_count": len(warmup_samples),
            "original_submission_ids": original_ids,
            "warmup_submission_ids": warmup_rows,
            "answers_file": (
                "warmup_answers.jsonl" if competition_id == "tensorflow2-question-answering" else "warmup_answers.csv"
            ),
            **metadata,
        }
        manifest["private_inventory"] = inventory(private)
        identity = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
        manifest["version"] = identity
        (private / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
        if output.exists():
            raise FileExistsError(output)
        stage.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--competition-id", choices=CONVERTERS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--count", type=int)
    args = parser.parse_args()
    manifest = prepare_warmup(args.data_dir, args.output, args.competition_id, args.seed, args.count)
    print(
        json.dumps(
            {
                key: manifest[key]
                for key in ["competition_id", "version", "target_count", "actual_count", "train_count"]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
