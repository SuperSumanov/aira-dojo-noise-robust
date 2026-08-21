#!/usr/bin/env python3
"""Outcome-blind recovery and support audit for senior augmented batch identity.

Only tar headers are inspected.  No archive member is extracted or opened.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import hashlib
import json
import math
import os
import re
import stat
import sys
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


PROTOCOL = "senior-augmented-true-batch-identity-support-v1"
SPLIT_DOMAIN = "senior-experiment-closed-dev-v1|20260821"
SENIOR_COMMIT = "92a9651f2e13a9e43623235b82c07c19721bc2ee"
RUN_MANIFEST_SHA256 = "bd707dd992a131d03dc20bdc981626826325f461e086a945b2f85fc41c2c171b"
PAIR_STRUCTURE_SHA256 = "52ffcdc0b7cc4486b61de0c664c7c057c26171a520372ca2071d55f2fb7a127b"
SUPPORT_SUMMARY_SHA256 = "7745dd157e41dc96a00ac76979afa6369f06395b0aa8ad67756de4d84e7297e8"
RUN_RE = re.compile(r"^(.*)_seed_[0-9]+_id_[0-9a-f]+__(\d{4}-\d{2}-\d{2})$")
SHA_RE = re.compile(r"[0-9a-f]{64}")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
RUN_FIELDS = {
    "cards",
    "config_sha256",
    "curve_order_sha256",
    "dev_order_sha256",
    "original_hold",
    "role",
    "run_id",
    "task",
}
PAIR_FIELDS = {"original_split", "pair_key_sha256", "run_ids", "same_experiment_contract", "task"}
SOURCE_DAYS = (
    "0726",
    "0727",
    "0728",
    "0729",
    "0730",
    "0731",
    "0801",
    "0802",
    "0803",
    "0804",
    "0805-这里开始进一步压低任务限时和子节点数",
    "0806",
    "0807",
    "0808",
    "0809",
    "0810-明天的任务将降低单次run时长来提高run产量",
    "0811",
    "0812",
    "0813",
    "0814",
    "0815",
)


class AuditError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_hash(parts: Iterable[str]) -> str:
    return sha256_bytes("\0".join(parts).encode("utf-8"))


def locked(path_value: str, expected: str) -> Path:
    path = Path(path_value).resolve()
    if not path.is_file() or path.is_symlink() or sha256_file(path) != expected:
        raise AuditError(f"locked input mismatch: {path.name}")
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise AuditError(f"credential-shaped bytes refused: {path.name}")
    return path


def load_jsonl(path: Path, fields: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise AuditError(f"blank line at {path.name}:{line_number}")
            value = json.loads(line)
            if not isinstance(value, dict) or set(value) != fields:
                raise AuditError(f"schema mismatch at {path.name}:{line_number}")
            rows.append(value)
    return rows


def safe_parts(name: str) -> tuple[str, ...]:
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise AuditError("unsafe tar member spelling")
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts:
        raise AuditError("unsafe tar member path")
    parts = tuple(part for part in pure.parts if part not in {"", "."})
    if not parts:
        raise AuditError("empty tar member path")
    return parts


def scan_archive(path: Path, source_root: Path) -> dict[str, Any]:
    relative = path.relative_to(source_root).as_posix()
    before = path.stat()
    if path.is_symlink() or not stat.S_ISREG(before.st_mode):
        raise AuditError("source archive is not a regular file")
    member_count = 0
    declared_bytes = 0
    env_headers = 0
    checkpoint_headers = 0
    run_batches: dict[str, str] = {}
    with tarfile.open(path, mode="r|*") as archive:
        for member in archive:
            member_count += 1
            declared_bytes += max(0, int(member.size))
            if member_count > 1_000_000 or declared_bytes > 256 * 1024**3:
                raise AuditError("archive resource cap exceeded")
            parts = safe_parts(member.name)
            if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                raise AuditError("unsupported tar member type")
            if parts[-1] == "env_variables.json":
                env_headers += 1
            if len(parts) >= 3 and parts[-2:] == ("checkpoint", "journal.jsonl"):
                if not member.isfile():
                    raise AuditError("checkpoint journal header is not a regular file")
                checkpoint_headers += 1
                batch_name = parts[0]
                run_name = parts[-3]
                previous = run_batches.setdefault(run_name, batch_name)
                if previous != batch_name:
                    raise AuditError("one run directory appears under multiple batches in one archive")
            # Deliberately never call TarFile.extractfile() or extract().
    digest = sha256_file(path)
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise AuditError("source archive changed during scan")
    if checkpoint_headers == 0:
        raise AuditError("archive has no checkpoint journal headers")
    return {
        "relative_path": relative,
        "size": before.st_size,
        "mtime_ns": before.st_mtime_ns,
        "sha256": digest,
        "members": member_count,
        "declared_member_bytes": declared_bytes,
        "env_member_headers_seen": env_headers,
        "checkpoint_journal_headers": checkpoint_headers,
        "run_batches": run_batches,
        "status": "ok",
    }


def inventory_archives(source_root: Path) -> tuple[list[Path], str]:
    paths: list[Path] = []
    metadata: list[dict[str, Any]] = []
    for day in SOURCE_DAYS:
        directory = source_root / day
        if not directory.is_dir() or directory.is_symlink():
            raise AuditError(f"required source day is absent or symlinked: {day}")
        day_paths = sorted((path for path in directory.iterdir() if path.is_file()), key=lambda path: path.name)
        if not day_paths:
            raise AuditError(f"required source day is empty: {day}")
        for path in day_paths:
            current = path.stat()
            if path.is_symlink() or not stat.S_ISREG(current.st_mode):
                raise AuditError("source inventory contains a non-regular file")
            paths.append(path)
            metadata.append(
                {
                    "relative_path": path.relative_to(source_root).as_posix(),
                    "size": current.st_size,
                    "mtime_ns": current.st_mtime_ns,
                }
            )
    encoded = b"".join(
        (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        for row in metadata
    )
    return paths, sha256_bytes(encoded)


def scan_archives(paths: list[Path], source_root: Path, workers: int) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(scan_archive, path, source_root): path for path in paths}
        for future in concurrent.futures.as_completed(futures):
            path = futures[future]
            try:
                output.append(future.result())
            except (AuditError, OSError, tarfile.TarError, EOFError) as exc:
                output.append(
                    {
                        "relative_path": path.relative_to(source_root).as_posix(),
                        "status": "error",
                        "error_type": type(exc).__name__,
                        "error_sha256": sha256_bytes(str(exc).encode("utf-8")),
                    }
                )
    return sorted(output, key=lambda row: row["relative_path"])


def validate_runs(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        if set(row) != RUN_FIELDS:
            raise AuditError("run manifest schema mismatch")
        run_id = row["run_id"]
        if not isinstance(run_id, str) or run_id in output:
            raise AuditError("run identity missing or duplicated")
        match = RUN_RE.fullmatch(run_id)
        if match is None:
            raise AuditError("run identity does not match frozen regex")
        if not isinstance(row["task"], str) or not row["task"]:
            raise AuditError("run task invalid")
        if not isinstance(row["original_hold"], bool):
            raise AuditError("run hold flag invalid")
        output[run_id] = {**row, "source_run_name": match.group(1), "launch_date": match.group(2)}
    return output


def archive_run_sources(archive_rows: list[dict[str, Any]]) -> dict[str, set[tuple[str, str]]]:
    output: dict[str, set[tuple[str, str]]] = collections.defaultdict(set)
    for archive in archive_rows:
        if archive["status"] != "ok":
            continue
        day = archive["relative_path"].split("/", 1)[0]
        for run_name, batch_name in archive["run_batches"].items():
            output[run_name].add((day, batch_name))
    return output


def attach_batches(
    runs: dict[str, dict[str, Any]], sources: dict[str, set[tuple[str, str]]]
) -> tuple[list[dict[str, Any]], dict[str, str], int, int]:
    rows: list[dict[str, Any]] = []
    run_batch: dict[str, str] = {}
    missing = ambiguous = 0
    for run_id in sorted(runs):
        source_keys = sorted(sources.get(runs[run_id]["source_run_name"], set()))
        if len(source_keys) == 1:
            day, batch_name = source_keys[0]
            batch_sha = canonical_hash(("senior-true-batch-v1", day, batch_name))
            status_value = "unique"
            run_batch[run_id] = batch_sha
        elif not source_keys:
            day = batch_sha = None
            status_value = "missing"
            missing += 1
        else:
            day = batch_sha = None
            status_value = "ambiguous"
            ambiguous += 1
        rows.append(
            {
                "run_id": run_id,
                "task": runs[run_id]["task"],
                "original_hold": runs[run_id]["original_hold"],
                "source_match_status": status_value,
                "source_candidate_batches": len(source_keys),
                "source_day": day,
                "batch_sha256": batch_sha,
            }
        )
    return rows, run_batch, missing, ambiguous


def validate_pairs(
    pairs: list[dict[str, Any]],
    runs: dict[str, dict[str, Any]],
    run_batch: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    counts = collections.Counter()
    for pair in pairs:
        if set(pair) != PAIR_FIELDS:
            raise AuditError("pair structure schema mismatch")
        key = pair["pair_key_sha256"]
        run_ids = pair["run_ids"]
        split = pair["original_split"]
        if not isinstance(key, str) or not SHA_RE.fullmatch(key) or key in seen:
            raise AuditError("pair identity invalid or duplicated")
        seen.add(key)
        if split not in {"train", "test"}:
            raise AuditError("pair split invalid")
        if not isinstance(run_ids, list) or not 1 <= len(run_ids) <= 2 or run_ids != sorted(set(run_ids)):
            raise AuditError("pair run list invalid")
        if any(run_id not in runs for run_id in run_ids):
            raise AuditError("pair references unknown run")
        task_match = all(runs[run_id]["task"] == pair["task"] for run_id in run_ids)
        if not task_match:
            counts["task_mismatch"] += 1
        mapped = [run_batch.get(run_id) for run_id in run_ids]
        identity_complete = all(value is not None for value in mapped)
        same_batch = identity_complete and len(set(mapped)) == 1
        if not identity_complete:
            counts["identity_incomplete"] += 1
        elif not same_batch:
            counts["cross_batch"] += 1
        counts[f"original_{split}"] += 1
        output.append(
            {
                "pair_key_sha256": key,
                "original_split": split,
                "task": pair["task"],
                "batch_sha256": mapped[0] if same_batch else None,
                "identity_complete": identity_complete,
                "same_true_batch": same_batch,
                "task_match": task_match,
            }
        )
    return output, dict(counts)


def assign_experiment_roles(
    pair_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    train_pairs = [
        row
        for row in pair_rows
        if row["original_split"] == "train"
        and row["identity_complete"]
        and row["same_true_batch"]
        and row["task_match"]
    ]
    test_pairs = [
        row
        for row in pair_rows
        if row["original_split"] == "test"
        and row["identity_complete"]
        and row["same_true_batch"]
        and row["task_match"]
    ]
    pair_counts: collections.Counter[tuple[str, str]] = collections.Counter(
        (row["task"], row["batch_sha256"]) for row in train_pairs
    )
    test_counts: collections.Counter[tuple[str, str]] = collections.Counter(
        (row["task"], row["batch_sha256"]) for row in test_pairs
    )
    by_task: dict[str, list[str]] = collections.defaultdict(list)
    for task, batch in pair_counts:
        by_task[task].append(batch)

    roles: dict[tuple[str, str], str] = {}
    for task, batches in by_task.items():
        unique = sorted(set(batches))
        if len(unique) < 5:
            for batch in unique:
                roles[(task, batch)] = "excluded_low_support"
            continue
        ordered = sorted(unique, key=lambda batch: canonical_hash((SPLIT_DOMAIN, task, batch)))
        dev_count = max(1, math.floor(0.2 * len(ordered)))
        for index, batch in enumerate(ordered):
            roles[(task, batch)] = "dev" if index < dev_count else "train"

    experiment_rows: list[dict[str, Any]] = []
    for task, batch in sorted(pair_counts):
        experiment_rows.append(
            {
                "task": task,
                "batch_sha256": batch,
                "role": roles[(task, batch)],
                "train_structure_pairs": pair_counts[(task, batch)],
                "test_structure_pairs_same_experiment": test_counts[(task, batch)],
                "split_order_sha256": canonical_hash((SPLIT_DOMAIN, task, batch)),
            }
        )

    selected_train = [row for row in train_pairs if roles[(row["task"], row["batch_sha256"])] == "train"]
    selected_dev = [row for row in train_pairs if roles[(row["task"], row["batch_sha256"])] == "dev"]
    dev_tasks = collections.Counter(row["task"] for row in selected_dev)
    train_tasks = collections.Counter(row["task"] for row in selected_train)
    train_experiments = {key for key, role in roles.items() if role == "train"}
    dev_experiments = {key for key, role in roles.items() if role == "dev"}
    test_experiments = set(test_counts)
    metrics = {
        "experiment_closed_train_pairs": len(selected_train),
        "experiment_closed_dev_pairs": len(selected_dev),
        "excluded_low_support_train_pairs": len(train_pairs) - len(selected_train) - len(selected_dev),
        "train_experiments": len(train_experiments),
        "dev_experiments": len(dev_experiments),
        "train_dev_experiment_overlap": len(train_experiments & dev_experiments),
        "dev_tasks": len(dev_tasks),
        "train_tasks": len(train_tasks),
        "dominant_dev_task_share": max(dev_tasks.values()) / len(selected_dev) if selected_dev else None,
        "dev_tasks_with_ge_20_pairs": sum(value >= 20 for value in dev_tasks.values()),
        "original_test_experiments_structure_only": len(test_experiments),
        "test_experiments_overlapping_train_role": len(test_experiments & train_experiments),
        "test_experiments_overlapping_dev_role": len(test_experiments & dev_experiments),
        "test_only_experiments_used_for_role_allocation": 0,
        "dev_pairs_per_task": dict(sorted(dev_tasks.items())),
        "train_pairs_per_task": dict(sorted(train_tasks.items())),
    }
    return experiment_rows, metrics


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def run(args: argparse.Namespace) -> int:
    run_path = locked(args.run_manifest, RUN_MANIFEST_SHA256)
    pair_path = locked(args.pair_structure, PAIR_STRUCTURE_SHA256)
    upstream_path = locked(args.support_summary, SUPPORT_SUMMARY_SHA256)
    source_root = Path(args.source_root).resolve()
    if not source_root.is_dir() or source_root.is_symlink():
        raise AuditError("source root is absent or symlinked")
    output = Path(args.output).resolve()
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if output.exists() or staging.exists():
        raise AuditError("output or staging path already exists")

    run_rows_input = load_jsonl(run_path, RUN_FIELDS)
    pair_rows_input = load_jsonl(pair_path, PAIR_FIELDS)
    upstream = json.loads(upstream_path.read_text(encoding="utf-8"))
    if upstream.get("senior_source_commit") != SENIOR_COMMIT:
        raise AuditError("upstream senior commit mismatch")
    runs = validate_runs(run_rows_input)
    archive_paths, source_inventory_sha = inventory_archives(source_root)
    archive_rows = scan_archives(archive_paths, source_root, args.workers)
    archive_errors = sum(row["status"] != "ok" for row in archive_rows)
    sources = archive_run_sources(archive_rows)
    run_batch_rows, run_batch, missing_runs, ambiguous_runs = attach_batches(runs, sources)
    pair_rows, pair_counts = validate_pairs(pair_rows_input, runs, run_batch)
    experiment_rows, support = assign_experiment_roles(pair_rows)

    upstream_inventory = upstream.get("inventory", {})
    count_reproduction = {
        "original_train_pairs": pair_counts.get("original_train", 0)
        == upstream_inventory.get("original_train_pairs"),
        "original_test_pairs_structure_only": pair_counts.get("original_test", 0)
        == upstream_inventory.get("original_test_pairs_structure_only"),
        "current_runs": len(runs) == upstream_inventory.get("current_runs"),
    }
    identity_criteria = {
        "input_counts_reproduce_upstream": all(count_reproduction.values()),
        "archive_scan_errors_eq_0": archive_errors == 0,
        "run_source_missing_eq_0": missing_runs == 0,
        "run_source_ambiguous_eq_0": ambiguous_runs == 0,
        "pair_identity_incomplete_eq_0": pair_counts.get("identity_incomplete", 0) == 0,
        "pair_cross_true_batch_eq_0": pair_counts.get("cross_batch", 0) == 0,
        "pair_task_mismatch_eq_0": pair_counts.get("task_mismatch", 0) == 0,
    }
    support_criteria = {
        "train_dev_experiment_overlap_eq_0": support["train_dev_experiment_overlap"] == 0,
        "test_only_experiments_used_for_role_allocation_eq_0": support[
            "test_only_experiments_used_for_role_allocation"
        ]
        == 0,
        "dev_pairs_ge_400": support["experiment_closed_dev_pairs"] >= 400,
        "dev_tasks_ge_8": support["dev_tasks"] >= 8,
        "dominant_dev_task_share_le_0_35": support["dominant_dev_task_share"] is not None
        and support["dominant_dev_task_share"] <= 0.35,
        "dev_tasks_with_ge_20_pairs_ge_6": support["dev_tasks_with_ge_20_pairs"] >= 6,
        "train_pairs_ge_2000": support["experiment_closed_train_pairs"] >= 2000,
        "train_experiments_ge_5": support["train_experiments"] >= 5,
        "dev_experiments_ge_5": support["dev_experiments"] >= 5,
    }
    identity_pass = all(identity_criteria.values())
    if not identity_pass:
        status_value = "IDENTITY_UNAVAILABLE"
    elif not all(support_criteria.values()):
        status_value = "INSUFFICIENT_EXPERIMENT_CLOSED_SUPPORT"
    else:
        status_value = "EXPERIMENT_CLOSED_TRAIN_DEV_SUPPORT_FEASIBLE"

    summary = {
        "protocol": PROTOCOL,
        "status": status_value,
        "source_commit": args.source_commit,
        "senior_source_commit": SENIOR_COMMIT,
        "inputs": {
            "run_manifest_sha256": RUN_MANIFEST_SHA256,
            "pair_structure_sha256": PAIR_STRUCTURE_SHA256,
            "support_summary_sha256": SUPPORT_SUMMARY_SHA256,
            "source_inventory_sha256": source_inventory_sha,
            "source_days": list(SOURCE_DAYS),
        },
        "inventory": {
            "archives": len(archive_rows),
            "archive_scan_errors": archive_errors,
            "archive_member_headers": sum(row.get("members", 0) for row in archive_rows),
            "env_member_headers_seen": sum(row.get("env_member_headers_seen", 0) for row in archive_rows),
            "checkpoint_journal_headers": sum(
                row.get("checkpoint_journal_headers", 0) for row in archive_rows
            ),
            "anonymous_runs": len(runs),
            "unique_run_batch_matches": len(run_batch),
            "missing_runs": missing_runs,
            "ambiguous_runs": ambiguous_runs,
            "true_batches": len(set(run_batch.values())),
            "original_train_pairs": pair_counts.get("original_train", 0),
            "original_test_pairs_structure_only": pair_counts.get("original_test", 0),
            "pair_identity_incomplete": pair_counts.get("identity_incomplete", 0),
            "pair_cross_true_batch": pair_counts.get("cross_batch", 0),
            "pair_task_mismatch": pair_counts.get("task_mismatch", 0),
        },
        "experiment_closed_support": support,
        "count_reproduction": count_reproduction,
        "identity_criteria": identity_criteria,
        "support_criteria": support_criteria,
        "configuration": {
            "split_domain": SPLIT_DOMAIN,
            "minimum_experiments_per_task": 5,
            "dev_fraction": 0.2,
            "dev_rounding": "max(1,floor(0.2*n))",
            "workers": args.workers,
        },
        "scope": {
            "numeric_grade_used": False,
            "pair_orientation_used": False,
            "raw_code_used": False,
            "frozen_test_effect_used": False,
            "model_trained": False,
            "gpu": 0,
            "api_calls": 0,
            "archive_member_payload_reads": 0,
            "env_member_payload_reads": 0,
            "archives_extracted": 0,
        },
    }

    staging.mkdir(parents=True)
    sanitized_archives = [
        {key: value for key, value in row.items() if key != "run_batches"} for row in archive_rows
    ]
    write_json(staging / "summary.json", summary)
    write_jsonl(staging / "archive_manifest.jsonl", sanitized_archives)
    write_jsonl(staging / "run_batch_manifest.jsonl", run_batch_rows)
    write_jsonl(staging / "pair_batch_structure.jsonl", pair_rows)
    write_jsonl(staging / "experiment_split.jsonl", experiment_rows)
    names = (
        "summary.json",
        "archive_manifest.jsonl",
        "run_batch_manifest.jsonl",
        "pair_batch_structure.jsonl",
        "experiment_split.jsonl",
    )
    write_json(staging / "sha256_manifest.json", {name: sha256_file(staging / name) for name in names})
    staging.replace(output)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--run-manifest", required=True)
    value.add_argument("--pair-structure", required=True)
    value.add_argument("--support-summary", required=True)
    value.add_argument("--source-root", required=True)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--output", required=True)
    value.add_argument("--workers", type=int, default=2, choices=(1, 2, 3, 4))
    return value


def main() -> int:
    try:
        return run(parser().parse_args())
    except (AuditError, OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"SENIOR_BATCH_IDENTITY_SUPPORT_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
