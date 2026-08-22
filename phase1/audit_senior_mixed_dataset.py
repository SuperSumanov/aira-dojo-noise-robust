#!/usr/bin/env python3
"""Outcome-blind structural audit for a senior mixed critic dataset.

The audit reads only pair metadata plus the launcher/training source. It does
not open Cards, code, grades, model outputs, or prospective outcome vaults.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable


VALID_SPLITS = {"train", "test"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_pairs(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON at {path}:{line_number}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"non-object pair at {path}:{line_number}")
            for field in ("better", "worse", "task", "intask_split"):
                if not isinstance(record.get(field), str) or not record[field]:
                    raise ValueError(
                        f"missing non-empty string {field!r} at {path}:{line_number}"
                    )
            if record["intask_split"] not in VALID_SPLITS:
                raise ValueError(
                    f"unsupported split {record['intask_split']!r} at "
                    f"{path}:{line_number}"
                )
            records.append(record)
    if not records:
        raise ValueError(f"empty pair file: {path}")
    return records


def pair_summary(path: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    split_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    split_source_counts: Counter[str] = Counter()
    task_counts: Counter[str] = Counter()
    test_task_counts: Counter[str] = Counter()
    endpoints: dict[str, set[str]] = defaultdict(set)
    oriented: Counter[tuple[str, str]] = Counter()
    unordered: Counter[tuple[str, str]] = Counter()
    self_pairs = 0

    for record in records:
        split = record["intask_split"]
        source = str(record.get("src", "<missing>"))
        better = record["better"]
        worse = record["worse"]
        split_counts[split] += 1
        source_counts[source] += 1
        split_source_counts[f"{split}:{source}"] += 1
        task_counts[record["task"]] += 1
        if split == "test":
            test_task_counts[record["task"]] += 1
        endpoints[split].update((better, worse))
        oriented[(better, worse)] += 1
        unordered[tuple(sorted((better, worse)))] += 1
        self_pairs += int(better == worse)

    dominant_test_task: dict[str, Any] | None = None
    if test_task_counts:
        name, count = sorted(test_task_counts.items(), key=lambda item: (-item[1], item[0]))[0]
        dominant_test_task = {
            "task": name,
            "count": count,
            "share": count / split_counts["test"],
        }

    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "rows": len(records),
        "split_counts": dict(sorted(split_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "split_source_counts": dict(sorted(split_source_counts.items())),
        "task_count": len(task_counts),
        "dominant_test_task": dominant_test_task,
        "endpoint_counts": {key: len(value) for key, value in sorted(endpoints.items())},
        "train_test_endpoint_overlap": len(endpoints["train"] & endpoints["test"]),
        "oriented_duplicate_excess": sum(count - 1 for count in oriented.values()),
        "unordered_duplicate_excess": sum(count - 1 for count in unordered.values()),
        "self_pairs": self_pairs,
    }


def split_pair_sequence(records: Iterable[dict[str, Any]], split: str) -> list[tuple[str, str]]:
    return [
        (record["better"], record["worse"])
        for record in records
        if record["intask_split"] == split
    ]


def launcher_audit(launcher: Path, data_dir: Path) -> dict[str, Any]:
    text = launcher.read_text(encoding="utf-8")
    train_refs = re.findall(r'--train_pairs\s+"\$DATA_DIR/([^"]+)"', text)
    test_refs = re.findall(r'--test_pairs\s+"\$DATA_DIR/([^"]+)"', text)
    all_refs = sorted(set(train_refs + test_refs))
    return {
        "path": str(launcher.resolve()),
        "sha256": sha256_file(launcher),
        "train_pair_references": train_refs,
        "test_pair_references": test_refs,
        "same_train_test_reference_per_run": len(train_refs) == len(test_refs)
        and all(left == right for left, right in zip(train_refs, test_refs)),
        "referenced_pair_files_exist": {
            reference: (data_dir / reference).is_file() for reference in all_refs
        },
        "eval_steps": [int(value) for value in re.findall(r"--eval_steps\s+(\d+)", text)],
        "models": re.findall(r"--model\s+([^\s]+)", text),
    }


def source_protocol_audit(train_script: Path, config: Path) -> dict[str, Any]:
    train_text = train_script.read_text(encoding="utf-8")
    config_text = config.read_text(encoding="utf-8")
    markers = {
        "testing_pool_assigned_to_validation": "validation_records = testing_pool" in train_text,
        "testing_pool_used_as_eval_dataset": (
            "eval_dataset=PairDataset(validation_records" in train_text
        ),
        "evaluation_strategy_steps": 'eval_strategy: str = field(default="steps")' in config_text,
        "save_strategy_best": 'save_strategy: str = field(default="best")' in config_text,
        "metric_for_best_is_pair_accuracy": (
            'metric_for_best_model: str = field(default="eval_pair_accuracy")' in config_text
        ),
        "greater_is_better_true": (
            "greater_is_better: bool = field(default=True)" in config_text
        ),
        "load_best_model_at_end_false": (
            "load_best_model_at_end: bool = field(default=False)" in config_text
        ),
    }
    return {
        "train_script": str(train_script.resolve()),
        "train_script_sha256": sha256_file(train_script),
        "config": str(config.resolve()),
        "config_sha256": sha256_file(config),
        "markers": markers,
        "test_touched_during_training": all(
            markers[key]
            for key in (
                "testing_pool_assigned_to_validation",
                "testing_pool_used_as_eval_dataset",
                "evaluation_strategy_steps",
            )
        ),
        "test_guided_best_checkpoint_metadata": all(
            markers[key]
            for key in (
                "save_strategy_best",
                "metric_for_best_is_pair_accuracy",
                "greater_is_better_true",
            )
        ),
    }


def references_under(root: Path, needle: str) -> list[str]:
    matches: list[str] = []
    for subdirectory in ("src", "docs"):
        candidate_root = root / subdirectory
        if not candidate_root.is_dir():
            continue
        for path in sorted(candidate_root.rglob("*")):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if needle in text:
                matches.append(str(path.relative_to(root)).replace("\\", "/"))
    return matches


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mixed", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--value", type=Path, required=True)
    parser.add_argument("--batch-value", type=Path, required=True)
    parser.add_argument("--launcher", type=Path, required=True)
    parser.add_argument("--train-script", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    datasets: dict[str, tuple[Path, list[dict[str, Any]]]] = {}
    for name, path in (
        ("mixed", args.mixed),
        ("decision", args.decision),
        ("value", args.value),
        ("batch_value", args.batch_value),
    ):
        datasets[name] = (path, read_pairs(path))

    mixed_test = split_pair_sequence(datasets["mixed"][1], "test")
    decision_test = split_pair_sequence(datasets["decision"][1], "test")
    generation_references = references_under(args.repo_root, args.mixed.name)
    report = {
        "schema_version": 1,
        "audit_scope": "pair_metadata_and_training_protocol_only",
        "datasets": {
            name: pair_summary(path, records)
            for name, (path, records) in datasets.items()
        },
        "mixed_test_vs_decision_test": {
            "mixed_test_pairs": len(mixed_test),
            "decision_test_pairs": len(decision_test),
            "sequence_equal": mixed_test == decision_test,
            "multiset_equal": Counter(mixed_test) == Counter(decision_test),
        },
        "launcher": launcher_audit(args.launcher, args.mixed.parent),
        "training_protocol": source_protocol_audit(args.train_script, args.config),
        "mixed_output_filename_references_under_src_or_docs": generation_references,
        "mixed_generation_command_recorded": bool(generation_references),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
