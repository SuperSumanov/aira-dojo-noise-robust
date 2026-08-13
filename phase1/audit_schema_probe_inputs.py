#!/usr/bin/env python3
"""Freeze public-input metadata for the schema/probe smoke without exposing row values."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from pathlib import Path


TASKS = ["tabular-playground-series-may-2022", "spooky-author-identification"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_shape(path: Path) -> tuple[int, int, list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if not header:
            raise RuntimeError(f"empty CSV: {path}")
        rows = 0
        for row in reader:
            if len(row) != len(header):
                raise RuntimeError(f"ragged CSV: {path} row={rows + 2}")
            rows += 1
    return rows, len(header), header


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise RuntimeError(f"refusing existing output: {args.out}")
    records = []
    for task in TASKS:
        public = args.data_dir / task / "prepared" / "public"
        if not public.is_dir():
            raise RuntimeError(f"public directory missing: {public}")
        files = sorted(path for path in public.rglob("*") if path.is_file())
        samples = [path for path in files if path.name == "sample_submission.csv"]
        if len(samples) != 1:
            raise RuntimeError(f"sample submission count={len(samples)} for {task}")
        file_rows = []
        for path in files:
            row = {
                "relative_path": str(path.relative_to(public)),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            if path.suffix.lower() == ".csv":
                rows, columns, header = csv_shape(path)
                row.update({"rows": rows, "columns": columns, "header": header})
            file_rows.append(row)
        records.append(
            {
                "task": task,
                "public_dir": str(public),
                "file_count": len(files),
                "sample_submission_count": len(samples),
                "files": file_rows,
            }
        )
    payload = {
        "schema_version": 1,
        "tasks_frozen_before_generation": TASKS,
        "seed_frozen_before_generation": 861,
        "public_only": True,
        "tasks": records,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{args.out.name}.", dir=args.out.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, args.out)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    print(f"SCHEMA_PROBE_INPUT_AUDIT_PASS tasks={len(records)}")


if __name__ == "__main__":
    main()
