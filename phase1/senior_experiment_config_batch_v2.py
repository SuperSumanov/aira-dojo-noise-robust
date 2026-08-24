#!/usr/bin/env python3
"""Atomically export a prompt-sensitive v2 sidecar for one future run batch.

Every config path must point to an unarchived producer-side ``dojo_config.json``.
The command validates the complete batch before creating the output, so a bad
run cannot leave a partial provenance sidecar.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
from typing import Any, Iterable

import phase1.senior_experiment_config_v2 as single
import phase1.validate_senior_experiment_config_manifest as v1


class BatchExportError(RuntimeError):
    """Raised when a complete future batch cannot be exported safely."""


def make_rows(
    config_paths: Iterable[str | Path],
    *,
    task: str,
    generator_release: str,
    hardware: str,
) -> list[dict[str, Any]]:
    paths = list(config_paths)
    if not paths:
        raise BatchExportError("at least one explicit dojo config is required")
    rows = [
        single.make_row(
            single.load_dojo_config(path),
            task=task,
            generator_release=generator_release,
            hardware=hardware,
        )
        for path in paths
    ]
    run_ids = [row["run_id"] for row in rows]
    if len(run_ids) != len(set(run_ids)):
        raise BatchExportError("duplicate physical run ID in producer batch")
    rows.sort(key=lambda row: row["run_id"].encode("utf-8"))
    return rows


def encoded_rows(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        raise BatchExportError("refusing to encode an empty producer batch")
    try:
        raw = "".join(v1.canonical_json(row) + "\n" for row in rows).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise BatchExportError("batch rows are not canonical finite JSON") from exc
    if v1.CREDENTIAL.search(raw):
        raise BatchExportError("credential-shaped bytes in encoded batch sidecar")
    return raw


def write_batch(path_value: str | Path, rows: list[dict[str, Any]]) -> str:
    unresolved = Path(path_value)
    if unresolved.suffix != ".jsonl":
        raise BatchExportError("batch sidecar output must use .jsonl")
    if unresolved.is_symlink() or unresolved.exists():
        raise BatchExportError("batch sidecar output already exists or is symlinked")
    raw = encoded_rows(rows)
    path = unresolved.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    if temporary.exists():
        raise BatchExportError("temporary batch sidecar already exists")
    try:
        with temporary.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return hashlib.sha256(raw).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dojo-config", action="append", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--generator-release", required=True)
    parser.add_argument("--hardware", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        rows = make_rows(
            args.dojo_config,
            task=args.task,
            generator_release=args.generator_release,
            hardware=args.hardware,
        )
        manifest_sha256 = write_batch(args.output, rows)
    except (BatchExportError, single.ExportError, OSError) as exc:
        print(
            f"SENIOR_CONFIG_V2_BATCH_EXPORT_FAIL type={type(exc).__name__}",
            file=os.sys.stderr,
        )
        return 2
    print(
        "SENIOR_CONFIG_V2_BATCH_EXPORT_PASS "
        f"rows={len(rows)} manifest_sha256={manifest_sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
