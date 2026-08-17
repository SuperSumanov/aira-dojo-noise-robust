#!/usr/bin/env python3
"""Describe public sample-submission contracts without reading labels or private data."""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import json
import math
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Iterable


INT_RE = re.compile(r"^[+-]?[0-9]+$")
ALLOWED_TASK_TYPES = {"image-cls", "nlp", "tabular"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stream_sha256(handle: BinaryIO) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _read_tasks(path: Path) -> list[tuple[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, dialect="excel-tab"))
    tasks: list[tuple[str, str]] = []
    for row in rows:
        task, task_type = row.get("task", ""), row.get("task_type", "")
        if not task or "/" in task or "\\" in task or task_type not in ALLOWED_TASK_TYPES:
            raise ValueError(f"invalid task manifest row: {row!r}")
        tasks.append((task, task_type))
    names = [task for task, _ in tasks]
    if len(names) != len(set(names)) or names != sorted(names):
        raise ValueError("task manifest must contain unique rows sorted by task")
    return tasks


def _classify(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return "empty"
    if stripped.lower() in {"true", "false"}:
        return "bool"
    if INT_RE.fullmatch(stripped):
        return "int"
    try:
        number = float(stripped)
    except ValueError:
        return "string"
    return "float" if math.isfinite(number) else "nonfinite"


def _candidate(public_dir: Path) -> Path | None:
    if not public_dir.is_dir():
        return None
    candidates = []
    for path in public_dir.iterdir():
        if not path.is_file():
            continue
        lower = path.name.lower()
        if lower in {"sample_submission.csv", "samplesubmission.csv"}:
            candidates.append(path)
        elif "sample_submission" in lower and lower.endswith(".csv.zip"):
            candidates.append(path)
    if len(candidates) > 1:
        raise ValueError(f"ambiguous sample-submission candidates in {public_dir}")
    return candidates[0] if candidates else None


def _validate_resolved(path: Path, public_dir: Path) -> None:
    resolved = path.resolve(strict=True)
    public_resolved = public_dir.resolve(strict=True)
    if resolved.parent != public_resolved:
        raise ValueError(f"sample submission resolves outside its public directory: {path}")
    if "private" in {part.lower() for part in resolved.parts}:
        raise ValueError(f"private path is forbidden: {path}")


def _open_csv(
    path: Path,
) -> tuple[io.TextIOWrapper, str | None, int | None, zipfile.ZipFile | None]:
    if path.name.lower().endswith(".zip"):
        archive = zipfile.ZipFile(path)
        members = [item for item in archive.infolist() if not item.is_dir() and item.filename.lower().endswith(".csv")]
        if len(members) != 1:
            archive.close()
            raise ValueError(f"expected exactly one CSV member in {path}")
        member = members[0]
        if member.file_size > 2 * 1024 * 1024 * 1024:
            archive.close()
            raise ValueError(f"CSV member exceeds the 2 GiB safety cap in {path}")
        member_path = PurePosixPath(member.filename)
        if member_path.is_absolute() or ".." in member_path.parts:
            archive.close()
            raise ValueError(f"unsafe zip member in {path}")
        binary = archive.open(member)
        text = io.TextIOWrapper(binary, encoding="utf-8-sig", newline="")
        return text, member.filename, member.file_size, archive
    return path.open(encoding="utf-8-sig", newline=""), None, None, None


def _member_sha256(path: Path, member_name: str | None) -> str:
    if member_name is None:
        return _sha256(path)
    with zipfile.ZipFile(path) as archive, archive.open(member_name) as handle:
        return _stream_sha256(handle)


def _inspect_csv(path: Path) -> dict:
    handle, member_name, member_bytes, archive = _open_csv(path)
    try:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError(f"empty sample submission: {path}") from exc
        if not header or any(not name for name in header) or len(header) != len(set(header)):
            raise ValueError(f"invalid or duplicate header in {path}")
        observed = [set() for _ in header]
        empty_counts = [0 for _ in header]
        row_count = 0
        for row in reader:
            row_count += 1
            if len(row) != len(header):
                raise ValueError(f"row-width mismatch at data row {row_count} in {path}")
            for index, value in enumerate(row):
                category = _classify(value)
                observed[index].add(category)
                if category == "empty":
                    empty_counts[index] += 1
    finally:
        handle.close()
        if archive is not None:
            archive.close()

    inferred = [sorted(categories) if categories else ["no_rows"] for categories in observed]
    schema_payload = {"columns": header, "observed_types": inferred}
    schema_signature = hashlib.sha256(
        json.dumps(schema_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    width = len(header)
    width_bucket = "1-2" if width <= 2 else "3-10" if width <= 10 else ">10"
    return {
        "archive_member": member_name,
        "archive_member_uncompressed_bytes": member_bytes,
        "csv_content_sha256": _member_sha256(path, member_name),
        "row_count": row_count,
        "column_count": width,
        "columns": header,
        "observed_types": inferred,
        "empty_value_counts": empty_counts,
        "schema_signature": schema_signature,
        "width_bucket": width_bucket,
    }


def audit(data_root: Path, task_manifest: Path) -> dict:
    data_root = data_root.resolve(strict=True)
    tasks = _read_tasks(task_manifest)
    task_rows = []
    schema_counts: collections.Counter[str] = collections.Counter()
    width_buckets: set[str] = set()
    by_type = {task_type: {"tasks": 0, "contracts": 0} for task_type in sorted(ALLOWED_TASK_TYPES)}

    for task, task_type in tasks:
        by_type[task_type]["tasks"] += 1
        public_dir = data_root / task / "prepared" / "public"
        sample = _candidate(public_dir)
        description = public_dir / "description.md"
        if description.is_file():
            _validate_resolved(description, public_dir)
        row = {
            "task": task,
            "task_type": task_type,
            "public_dir_present": public_dir.is_dir(),
            "description_present": description.is_file(),
            "description_sha256": _sha256(description) if description.is_file() else None,
            "description_bytes": description.stat().st_size if description.is_file() else None,
            "contract_present": sample is not None,
        }
        if sample is not None:
            _validate_resolved(sample, public_dir)
            inspected = _inspect_csv(sample)
            row.update(
                {
                    "sample_submission_path": str(sample.relative_to(data_root)).replace("\\", "/"),
                    "source_bytes": sample.stat().st_size,
                    "source_sha256": _sha256(sample),
                    **inspected,
                }
            )
            by_type[task_type]["contracts"] += 1
            schema_counts[inspected["schema_signature"]] += 1
            width_buckets.add(inspected["width_bucket"])
        task_rows.append(row)

    found = sum(row["contract_present"] for row in task_rows)
    dominant = max(schema_counts.values(), default=0)
    header_gate = {
        "minimum_unique_schema_signatures": 8,
        "maximum_dominant_schema_share": 0.5,
        "minimum_width_buckets": 3,
        "observed_unique_schema_signatures": len(schema_counts),
        "observed_dominant_schema_share": dominant / found if found else None,
        "observed_width_buckets": sorted(width_buckets),
    }
    header_gate["passed"] = bool(
        found
        and header_gate["observed_unique_schema_signatures"] >= header_gate["minimum_unique_schema_signatures"]
        and header_gate["observed_dominant_schema_share"] <= header_gate["maximum_dominant_schema_share"]
        and len(width_buckets) >= header_gate["minimum_width_buckets"]
    )
    return {
        "protocol": "public_artifact_contract_support_v1",
        "input_contract": {
            "task_manifest_name": task_manifest.name,
            "task_manifest_sha256": _sha256(task_manifest),
            "private_paths_allowed": False,
            "train_or_test_feature_files_read": False,
            "official_labels_or_outcomes_read": False,
            "raw_sample_values_emitted": False,
        },
        "summary": {
            "tasks": len(tasks),
            "contracts_found": found,
            "descriptions_found": sum(row["description_present"] for row in task_rows),
            "coverage_by_task_type": by_type,
            "coverage_was_seen_during_exploratory_path_inventory": True,
            "coverage_is_confirmatory": False,
            "header_heterogeneity_gate": header_gate,
        },
        "tasks": task_rows,
        "decision": {
            "artifact_contract_is_nontrivial": header_gate["passed"],
            "method_effect_claim_allowed": False,
            "paid_experiment_authorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--task-manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.data_root, args.task_manifest.resolve(strict=True))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
