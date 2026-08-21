#!/usr/bin/env python3
"""Independent verifier for senior augmented true-batch identity support.

This module deliberately does not import the scientific producer.  Like the producer,
it reads tar headers only and never opens an archive member payload.
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
from typing import Any


PROTOCOL = "senior-augmented-true-batch-identity-support-v2"
VERIFY_PROTOCOL = "senior-augmented-true-batch-identity-support-verifier-v2"
SPLIT_DOMAIN = "senior-experiment-closed-dev-v1|20260821"
RUN_SHA = "bd707dd992a131d03dc20bdc981626826325f461e086a945b2f85fc41c2c171b"
PAIR_SHA = "52ffcdc0b7cc4486b61de0c664c7c057c26171a520372ca2071d55f2fb7a127b"
UPSTREAM_SHA = "7745dd157e41dc96a00ac76979afa6369f06395b0aa8ad67756de4d84e7297e8"
RUN_RE = re.compile(r"^(.+_seed_[0-9]+_id_[0-9a-f]+)__(\d{4}-\d{2}-\d{2})$")
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
EXPECTED_FILES = {
    "archive_manifest.jsonl",
    "experiment_split.jsonl",
    "pair_batch_structure.jsonl",
    "run_batch_manifest.jsonl",
    "sha256_manifest.json",
    "summary.json",
}


class VerifyError(RuntimeError):
    pass


def digest_file(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def domain_hash(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                raise VerifyError(f"blank JSONL row: {path.name}:{number}")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise VerifyError("JSONL row is not an object")
            rows.append(value)
    return rows


def verify_locked(path: Path, expected: str) -> None:
    if not path.is_file() or path.is_symlink() or digest_file(path) != expected:
        raise VerifyError(f"locked input mismatch: {path.name}")


def normalized_parts(value: str) -> tuple[str, ...]:
    if not value or "\\" in value or "\x00" in value:
        raise VerifyError("unsafe tar member spelling")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise VerifyError("unsafe tar member path")
    parts = tuple(part for part in path.parts if part not in {"", "."})
    if not parts:
        raise VerifyError("empty tar member path")
    return parts


def verify_archive(path: Path, root: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    before = path.stat()
    if path.is_symlink() or not stat.S_ISREG(before.st_mode):
        raise VerifyError("source archive is not a regular file")
    members = declared = env_headers = journal_headers = 0
    run_batches: dict[str, str] = {}
    with tarfile.open(path, "r|*") as handle:
        for member in handle:
            members += 1
            declared += max(0, int(member.size))
            if members > 1_000_000 or declared > 256 * 1024**3:
                raise VerifyError("archive resource cap exceeded")
            parts = normalized_parts(member.name)
            if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                raise VerifyError("unsupported tar member type")
            env_headers += parts[-1] == "env_variables.json"
            if len(parts) >= 3 and parts[-2:] == ("checkpoint", "journal.jsonl"):
                if not member.isfile():
                    raise VerifyError("checkpoint journal header is not a regular file")
                journal_headers += 1
                prior = run_batches.setdefault(parts[-3], parts[0])
                if prior != parts[0]:
                    raise VerifyError("one run directory appears under multiple batches in one archive")
            # No extractfile()/extract() call is permitted here.
    sha = digest_file(path)
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise VerifyError("source archive changed during scan")
    if not journal_headers:
        raise VerifyError("archive has no checkpoint journal headers")
    return {
        "relative_path": relative,
        "size": before.st_size,
        "mtime_ns": before.st_mtime_ns,
        "sha256": sha,
        "members": members,
        "declared_member_bytes": declared,
        "env_member_headers_seen": env_headers,
        "checkpoint_journal_headers": journal_headers,
        "run_batches": run_batches,
        "status": "ok",
    }


def source_paths(root: Path) -> tuple[list[Path], str]:
    paths: list[Path] = []
    metadata = []
    for day in SOURCE_DAYS:
        directory = root / day
        if not directory.is_dir() or directory.is_symlink():
            raise VerifyError("required source day unavailable")
        candidates = sorted((path for path in directory.iterdir() if path.is_file()), key=lambda path: path.name)
        if not candidates:
            raise VerifyError("required source day empty")
        for path in candidates:
            info = path.stat()
            if path.is_symlink() or not stat.S_ISREG(info.st_mode):
                raise VerifyError("source file is not regular")
            paths.append(path)
            metadata.append(
                {
                    "relative_path": path.relative_to(root).as_posix(),
                    "size": info.st_size,
                    "mtime_ns": info.st_mtime_ns,
                }
            )
    blob = b"".join(
        (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode()
        for row in metadata
    )
    return paths, hashlib.sha256(blob).hexdigest()


def scan_all(paths: list[Path], root: Path, workers: int) -> list[dict[str, Any]]:
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        future_paths = {pool.submit(verify_archive, path, root): path for path in paths}
        for future in concurrent.futures.as_completed(future_paths):
            path = future_paths[future]
            try:
                rows.append(future.result())
            except (VerifyError, OSError, tarfile.TarError, EOFError) as exc:
                rows.append(
                    {
                        "relative_path": path.relative_to(root).as_posix(),
                        "status": "error",
                        "error_type": "AuditError" if isinstance(exc, VerifyError) else type(exc).__name__,
                        "error_sha256": hashlib.sha256(str(exc).encode("utf-8")).hexdigest(),
                    }
                )
    return sorted(rows, key=lambda row: row["relative_path"])


def rebuild_run_batches(
    run_input: list[dict[str, Any]], archives: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    candidates: dict[str, set[tuple[str, str]]] = collections.defaultdict(set)
    for archive in archives:
        day = archive["relative_path"].split("/", 1)[0]
        for run_name, batch in archive["run_batches"].items():
            candidates[run_name].add((day, batch))
    output = []
    mapping = {}
    seen = set()
    for row in sorted(run_input, key=lambda item: item["run_id"]):
        run_id = row["run_id"]
        if run_id in seen:
            raise VerifyError("duplicate run")
        seen.add(run_id)
        parsed = RUN_RE.fullmatch(run_id)
        if parsed is None:
            raise VerifyError("run regex mismatch")
        sources = sorted(candidates.get(parsed.group(1), set()))
        if len(sources) == 1:
            day, batch = sources[0]
            batch_sha = domain_hash("senior-true-batch-v1", day, batch)
            mapping[run_id] = batch_sha
            match_status = "unique"
        elif not sources:
            day = batch_sha = None
            match_status = "missing"
        else:
            day = batch_sha = None
            match_status = "ambiguous"
        output.append(
            {
                "run_id": run_id,
                "task": row["task"],
                "original_hold": row["original_hold"],
                "source_match_status": match_status,
                "source_candidate_batches": len(sources),
                "source_day": day,
                "batch_sha256": batch_sha,
            }
        )
    return output, mapping


def rebuild_pair_rows(
    pair_input: list[dict[str, Any]], run_input: list[dict[str, Any]], mapping: dict[str, str]
) -> list[dict[str, Any]]:
    runs = {row["run_id"]: row for row in run_input}
    output = []
    seen = set()
    for pair in pair_input:
        key = pair["pair_key_sha256"]
        if key in seen:
            raise VerifyError("duplicate pair")
        seen.add(key)
        run_ids = pair["run_ids"]
        if any(run_id not in runs for run_id in run_ids):
            raise VerifyError("unknown run")
        task_match = all(runs[run_id]["task"] == pair["task"] for run_id in run_ids)
        batches = [mapping.get(run_id) for run_id in run_ids]
        complete = all(value is not None for value in batches)
        same = complete and len(set(batches)) == 1
        output.append(
            {
                "pair_key_sha256": key,
                "original_split": pair["original_split"],
                "task": pair["task"],
                "batch_sha256": batches[0] if same else None,
                "identity_complete": complete,
                "same_true_batch": same,
                "task_match": task_match,
            }
        )
    return output


def rebuild_split(pair_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    valid = [row for row in pair_rows if row["identity_complete"] and row["same_true_batch"] and row["task_match"]]
    train = [row for row in valid if row["original_split"] == "train"]
    test = [row for row in valid if row["original_split"] == "test"]
    train_counts = collections.Counter((row["task"], row["batch_sha256"]) for row in train)
    test_counts = collections.Counter((row["task"], row["batch_sha256"]) for row in test)
    task_batches: dict[str, list[str]] = collections.defaultdict(list)
    for task, batch in train_counts:
        task_batches[task].append(batch)
    roles = {}
    for task, values in task_batches.items():
        batches = sorted(set(values))
        if len(batches) < 5:
            roles.update({(task, batch): "excluded_low_support" for batch in batches})
        else:
            ordered = sorted(batches, key=lambda batch: domain_hash(SPLIT_DOMAIN, task, batch))
            dev_count = max(1, math.floor(0.2 * len(ordered)))
            roles.update(
                {(task, batch): "dev" if index < dev_count else "train" for index, batch in enumerate(ordered)}
            )
    split_rows = [
        {
            "task": task,
            "batch_sha256": batch,
            "role": roles[(task, batch)],
            "train_structure_pairs": train_counts[(task, batch)],
            "test_structure_pairs_same_experiment": test_counts[(task, batch)],
            "split_order_sha256": domain_hash(SPLIT_DOMAIN, task, batch),
        }
        for task, batch in sorted(train_counts)
    ]
    chosen_train = [row for row in train if roles[(row["task"], row["batch_sha256"])] == "train"]
    chosen_dev = [row for row in train if roles[(row["task"], row["batch_sha256"])] == "dev"]
    train_tasks = collections.Counter(row["task"] for row in chosen_train)
    dev_tasks = collections.Counter(row["task"] for row in chosen_dev)
    train_exp = {key for key, role in roles.items() if role == "train"}
    dev_exp = {key for key, role in roles.items() if role == "dev"}
    test_exp = set(test_counts)
    support = {
        "experiment_closed_train_pairs": len(chosen_train),
        "experiment_closed_dev_pairs": len(chosen_dev),
        "excluded_low_support_train_pairs": len(train) - len(chosen_train) - len(chosen_dev),
        "train_experiments": len(train_exp),
        "dev_experiments": len(dev_exp),
        "train_dev_experiment_overlap": len(train_exp & dev_exp),
        "dev_tasks": len(dev_tasks),
        "train_tasks": len(train_tasks),
        "dominant_dev_task_share": max(dev_tasks.values()) / len(chosen_dev) if chosen_dev else None,
        "dev_tasks_with_ge_20_pairs": sum(value >= 20 for value in dev_tasks.values()),
        "original_test_experiments_structure_only": len(test_exp),
        "test_experiments_overlapping_train_role": len(test_exp & train_exp),
        "test_experiments_overlapping_dev_role": len(test_exp & dev_exp),
        "test_only_experiments_used_for_role_allocation": 0,
        "dev_pairs_per_task": dict(sorted(dev_tasks.items())),
        "train_pairs_per_task": dict(sorted(train_tasks.items())),
    }
    return split_rows, support


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise VerifyError("verification output exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def run(args: argparse.Namespace) -> int:
    run_path = Path(args.run_manifest).resolve()
    pair_path = Path(args.pair_structure).resolve()
    upstream_path = Path(args.support_summary).resolve()
    verify_locked(run_path, RUN_SHA)
    verify_locked(pair_path, PAIR_SHA)
    verify_locked(upstream_path, UPSTREAM_SHA)
    result = Path(args.result_dir).resolve()
    if not result.is_dir() or result.is_symlink():
        raise VerifyError("result directory unavailable")
    if {path.name for path in result.iterdir()} != EXPECTED_FILES:
        raise VerifyError("result file set mismatch")
    manifest_path = result / "sha256_manifest.json"
    if digest_file(manifest_path) != args.expect_result_manifest_sha256:
        raise VerifyError("result manifest digest mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if set(manifest) != EXPECTED_FILES - {"sha256_manifest.json"}:
        raise VerifyError("result manifest entries mismatch")
    for name, expected in manifest.items():
        if digest_file(result / name) != expected:
            raise VerifyError("result artifact digest mismatch")

    summary = json.loads((result / "summary.json").read_text(encoding="utf-8"))
    if summary.get("protocol") != PROTOCOL:
        raise VerifyError("summary protocol mismatch")
    run_input = read_jsonl(run_path)
    pair_input = read_jsonl(pair_path)
    root = Path(args.source_root).resolve()
    paths, source_inventory_sha = source_paths(root)
    archives = scan_all(paths, root, args.workers)
    archived_expected = read_jsonl(result / "archive_manifest.jsonl")
    archived_actual = [{key: value for key, value in row.items() if key != "run_batches"} for row in archives]
    if archived_actual != archived_expected:
        raise VerifyError("archive manifest does not independently reproduce")
    run_rows, mapping = rebuild_run_batches(run_input, archives)
    if run_rows != read_jsonl(result / "run_batch_manifest.jsonl"):
        raise VerifyError("run-batch join does not independently reproduce")
    pair_rows = rebuild_pair_rows(pair_input, run_input, mapping)
    if pair_rows != read_jsonl(result / "pair_batch_structure.jsonl"):
        raise VerifyError("pair-batch structure does not independently reproduce")
    split_rows, support = rebuild_split(pair_rows)
    if split_rows != read_jsonl(result / "experiment_split.jsonl"):
        raise VerifyError("experiment split does not independently reproduce")
    if support != summary.get("experiment_closed_support"):
        raise VerifyError("support metrics do not independently reproduce")
    if source_inventory_sha != summary.get("inputs", {}).get("source_inventory_sha256"):
        raise VerifyError("source inventory digest mismatch")

    verification = {
        "protocol": VERIFY_PROTOCOL,
        "verified": True,
        "verified_status": summary["status"],
        "result_manifest_sha256": args.expect_result_manifest_sha256,
        "source_inventory_sha256": source_inventory_sha,
        "archives_rescanned": len(archives),
        "runs_rejoined": len(run_rows),
        "pairs_rejoined": len(pair_rows),
        "experiments_reassigned": len(split_rows),
        "scope": {
            "archive_member_payload_reads": 0,
            "env_member_payload_reads": 0,
            "numeric_grade_used": False,
            "pair_orientation_used": False,
            "raw_code_used": False,
            "frozen_test_effect_used": False,
            "model_trained": False,
            "gpu": 0,
            "api_calls": 0,
        },
    }
    write_new(Path(args.output).resolve(), verification)
    print(json.dumps(verification, sort_keys=True, separators=(",", ":")))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-manifest", required=True)
    parser.add_argument("--pair-structure", required=True)
    parser.add_argument("--support-summary", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--result-dir", required=True)
    parser.add_argument("--expect-result-manifest-sha256", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--workers", type=int, default=2, choices=(1, 2, 3, 4))
    args = parser.parse_args()
    try:
        return run(args)
    except (VerifyError, OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, tarfile.TarError) as exc:
        print(f"SENIOR_BATCH_IDENTITY_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
