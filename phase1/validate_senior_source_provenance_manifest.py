#!/usr/bin/env python3
"""Validate producer-side run-to-source provenance without reading outcomes.

The validator is deliberately independent of the corpus/pair producers.  It reads
only the frozen run manifest, the proposed provenance JSONL, and tar headers.  Tar
member payloads (including journals, code, stdout, grades, and credentials) are
never opened.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tarfile
from collections import Counter
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


PROTOCOL = "senior-source-provenance-manifest-v1"
RUN_RE = re.compile(r"^(.+_seed_[0-9]+_id_[0-9a-f]+)__(\d{4}-\d{2}-\d{2})$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
EXPECTED_RUN_FIELDS = {
    "cards",
    "config_sha256",
    "curve_order_sha256",
    "dev_order_sha256",
    "original_hold",
    "role",
    "run_id",
    "task",
}
PROVENANCE_FIELDS = {
    "archive_path",
    "archive_sha256",
    "batch_id",
    "producer_commit",
    "run_id",
    "source_date",
    "task",
}


class ContractError(RuntimeError):
    """Raised when any provenance-contract condition fails closed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def rows_sha256(rows: Iterable[dict[str, Any]]) -> str:
    payload = "".join(canonical_json(row) + "\n" for row in rows).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def checked_input(path_value: str | Path, expected_sha256: str) -> Path:
    if not SHA256_RE.fullmatch(expected_sha256):
        raise ContractError("expected input SHA-256 is invalid")
    path = Path(path_value).resolve()
    if not path.is_file() or path.is_symlink():
        raise ContractError(f"input is absent, symlinked, or non-regular: {path.name}")
    raw = path.read_bytes()
    if CREDENTIAL.search(raw):
        raise ContractError(f"credential-shaped bytes refused: {path.name}")
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ContractError(f"input SHA-256 mismatch: {path.name}")
    return path


def load_jsonl(path: Path, exact_fields: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise ContractError(f"blank JSONL line at {path.name}:{line_number}")
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ContractError(f"invalid JSON at {path.name}:{line_number}") from exc
            if not isinstance(row, dict) or set(row) != exact_fields:
                raise ContractError(f"schema mismatch at {path.name}:{line_number}")
            rows.append(row)
    if not rows:
        raise ContractError(f"empty JSONL input: {path.name}")
    return rows


def safe_relative_parts(value: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ContractError("unsafe archive path spelling")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts:
        raise ContractError("archive path must be relative and traversal-free")
    parts = tuple(part for part in pure.parts if part not in {"", "."})
    if not parts or "/".join(parts) != value:
        raise ContractError("archive path is not canonical POSIX spelling")
    return parts


def safe_tar_parts(value: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ContractError("unsafe tar member spelling")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts:
        raise ContractError("unsafe tar member path")
    parts = tuple(part for part in pure.parts if part not in {"", "."})
    if not parts:
        raise ContractError("empty tar member path")
    return parts


def validate_expected_runs(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    runs: dict[str, dict[str, Any]] = {}
    for row in rows:
        run_id = row["run_id"]
        task = row["task"]
        parsed = RUN_RE.fullmatch(run_id) if isinstance(run_id, str) else None
        if parsed is None or run_id in runs:
            raise ContractError("expected run identity is invalid or duplicated")
        if not isinstance(task, str) or not task:
            raise ContractError("expected run task is invalid")
        runs[run_id] = {
            "run_id": run_id,
            "task": task,
            "source_run_name": parsed.group(1),
            "run_date": parsed.group(2),
        }
    return runs


def validate_provenance_rows(
    rows: list[dict[str, Any]], expected_runs: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    if [row["run_id"] for row in rows] != sorted(row["run_id"] for row in rows):
        raise ContractError("provenance rows must be sorted by run_id")

    provenance: dict[str, dict[str, Any]] = {}
    for row in rows:
        run_id = row["run_id"]
        if not isinstance(run_id, str) or run_id in provenance:
            raise ContractError("provenance run_id is invalid or duplicated")
        expected = expected_runs.get(run_id)
        if expected is None:
            raise ContractError("provenance contains an unexpected run_id")
        if row["task"] != expected["task"]:
            raise ContractError("provenance task does not match frozen run manifest")
        source_date = row["source_date"]
        try:
            parsed_date = date.fromisoformat(source_date)
        except (TypeError, ValueError) as exc:
            raise ContractError("source_date must be an ISO calendar date") from exc
        if source_date != expected["run_date"]:
            raise ContractError("source_date does not match the run identity suffix")
        archive_parts = safe_relative_parts(row["archive_path"])
        expected_day_prefix = parsed_date.strftime("%m%d")
        if not (
            archive_parts[0] == expected_day_prefix
            or archive_parts[0].startswith(expected_day_prefix + "-")
        ):
            raise ContractError("archive path day does not match source_date")
        batch_id = row["batch_id"]
        if (
            not isinstance(batch_id, str)
            or not batch_id
            or batch_id in {".", ".."}
            or "/" in batch_id
            or "\\" in batch_id
            or "\x00" in batch_id
        ):
            raise ContractError("batch_id must be one safe tar-path component")
        if not isinstance(row["archive_sha256"], str) or not SHA256_RE.fullmatch(row["archive_sha256"]):
            raise ContractError("archive_sha256 is invalid")
        if not isinstance(row["producer_commit"], str) or not GIT_COMMIT_RE.fullmatch(row["producer_commit"]):
            raise ContractError("producer_commit must be a full 40-hex Git commit")
        provenance[run_id] = {**row, "source_run_name": expected["source_run_name"]}

    missing = sorted(set(expected_runs) - set(provenance))
    if missing:
        raise ContractError(f"provenance does not cover {len(missing)} expected runs")
    return provenance


def resolve_archive(source_root: Path, relative_path: str) -> Path:
    parts = safe_relative_parts(relative_path)
    candidate = source_root.joinpath(*parts)
    cursor = source_root
    for part in parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ContractError("archive path contains a symlink component")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(source_root)
    except (FileNotFoundError, ValueError) as exc:
        raise ContractError("archive is absent or escapes source_root") from exc
    mode = resolved.stat().st_mode
    if not stat.S_ISREG(mode):
        raise ContractError("archive is not a regular file")
    return resolved


def scan_archive(path: Path, relative_path: str, expected_sha256: str) -> dict[str, Any]:
    before = path.stat()
    if sha256_file(path) != expected_sha256:
        raise ContractError(f"archive SHA-256 mismatch: {relative_path}")

    members = 0
    declared_bytes = 0
    checkpoint_headers = 0
    journals: Counter[tuple[str, str]] = Counter()
    try:
        with tarfile.open(path, mode="r|*") as archive:
            for member in archive:
                members += 1
                declared_bytes += max(0, int(member.size))
                if members > 1_000_000 or declared_bytes > 256 * 1024**3:
                    raise ContractError("archive resource cap exceeded")
                parts = safe_tar_parts(member.name)
                if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                    raise ContractError("unsupported tar member type")
                if len(parts) >= 3 and parts[-2:] == ("checkpoint", "journal.jsonl"):
                    if not member.isfile():
                        raise ContractError("checkpoint journal header is not a regular file")
                    checkpoint_headers += 1
                    journals[(parts[0], parts[-3])] += 1
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise ContractError(f"archive header scan failed: {relative_path}") from exc

    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise ContractError("archive changed during validation")
    if checkpoint_headers == 0:
        raise ContractError("archive has zero checkpoint journal headers")
    return {
        "relative_path": relative_path,
        "sha256": expected_sha256,
        "size": before.st_size,
        "members": members,
        "declared_member_bytes": declared_bytes,
        "checkpoint_journal_headers": checkpoint_headers,
        "journals": journals,
    }


def validate_archives(
    provenance: dict[str, dict[str, Any]], source_root_value: str | Path
) -> list[dict[str, Any]]:
    source_root_input = Path(source_root_value)
    if source_root_input.is_symlink():
        raise ContractError("source_root must not be a symlink")
    try:
        source_root = source_root_input.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ContractError("source_root does not exist") from exc
    if not source_root.is_dir():
        raise ContractError("source_root is not a directory")

    archive_digests: dict[str, str] = {}
    for row in provenance.values():
        previous = archive_digests.setdefault(row["archive_path"], row["archive_sha256"])
        if previous != row["archive_sha256"]:
            raise ContractError("one archive_path has conflicting SHA-256 values")

    scanned: dict[str, dict[str, Any]] = {}
    for relative_path in sorted(archive_digests):
        archive_path = resolve_archive(source_root, relative_path)
        scanned[relative_path] = scan_archive(
            archive_path, relative_path, archive_digests[relative_path]
        )

    referenced_counts: Counter[str] = Counter()
    for row in provenance.values():
        archive = scanned[row["archive_path"]]
        key = (row["batch_id"], row["source_run_name"])
        if archive["journals"].get(key, 0) != 1:
            raise ContractError("run is not backed by exactly one matching checkpoint journal header")
        referenced_counts[row["archive_path"]] += 1

    return [
        {
            "relative_path": relative_path,
            "sha256": scanned[relative_path]["sha256"],
            "size": scanned[relative_path]["size"],
            "members": scanned[relative_path]["members"],
            "declared_member_bytes": scanned[relative_path]["declared_member_bytes"],
            "checkpoint_journal_headers": scanned[relative_path]["checkpoint_journal_headers"],
            "referenced_runs": referenced_counts[relative_path],
        }
        for relative_path in sorted(scanned)
    ]


def validate(
    expected_runs_path: str | Path,
    expected_runs_sha256: str,
    provenance_path: str | Path,
    provenance_sha256: str,
    source_root: str | Path,
) -> dict[str, Any]:
    expected_path = checked_input(expected_runs_path, expected_runs_sha256)
    proposed_path = checked_input(provenance_path, provenance_sha256)
    expected_rows = load_jsonl(expected_path, EXPECTED_RUN_FIELDS)
    proposed_rows = load_jsonl(proposed_path, PROVENANCE_FIELDS)
    expected_runs = validate_expected_runs(expected_rows)
    provenance = validate_provenance_rows(proposed_rows, expected_runs)
    archive_rows = validate_archives(provenance, source_root)

    canonical_rows = [
        {field: provenance[run_id][field] for field in sorted(PROVENANCE_FIELDS)}
        for run_id in sorted(provenance)
    ]
    task_counts = Counter(row["task"] for row in canonical_rows)
    commits = sorted({row["producer_commit"] for row in canonical_rows})
    criteria = {
        "exact_schema": True,
        "expected_run_coverage_complete": len(canonical_rows) == len(expected_runs),
        "unexpected_runs_eq_0": set(provenance) == set(expected_runs),
        "duplicate_run_ids_eq_0": len(provenance) == len(canonical_rows),
        "task_mismatches_eq_0": all(
            row["task"] == expected_runs[row["run_id"]]["task"] for row in canonical_rows
        ),
        "source_date_mismatches_eq_0": all(
            row["source_date"] == expected_runs[row["run_id"]]["run_date"] for row in canonical_rows
        ),
        "archive_hashes_verified": True,
        "archive_headers_verified": True,
        "each_run_has_exactly_one_matching_journal_header": True,
        "archive_member_payloads_opened_eq_0": True,
    }
    if not all(criteria.values()):
        raise ContractError("internal criteria inconsistency")
    return {
        "protocol": PROTOCOL,
        "formal_status": "PROVENANCE_VERIFIED",
        "inputs": {
            "expected_runs_sha256": expected_runs_sha256,
            "provenance_manifest_sha256": provenance_sha256,
        },
        "inventory": {
            "expected_runs": len(expected_runs),
            "provenance_rows": len(canonical_rows),
            "tasks": len(task_counts),
            "archives": len(archive_rows),
            "producer_commits": len(commits),
            "runs_per_task": dict(sorted(task_counts.items())),
        },
        "criteria": criteria,
        "mapping_sha256": rows_sha256(canonical_rows),
        "producer_commits": commits,
        "archives": archive_rows,
        "access_attestation": {
            "tar_headers_read": True,
            "tar_member_payloads_opened": False,
            "outcomes_or_grades_read": False,
            "model_fit_or_gpu_used": False,
        },
    }


def write_receipt(path_value: str | Path, receipt: dict[str, Any]) -> None:
    path = Path(path_value).resolve()
    if path.exists():
        raise ContractError("output receipt already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    if temporary.exists():
        raise ContractError("temporary receipt path already exists")
    try:
        temporary.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-runs", required=True)
    parser.add_argument("--expect-runs-sha256", required=True)
    parser.add_argument("--provenance-manifest", required=True)
    parser.add_argument("--expect-provenance-sha256", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        receipt = validate(
            args.expected_runs,
            args.expect_runs_sha256,
            args.provenance_manifest,
            args.expect_provenance_sha256,
            args.source_root,
        )
        write_receipt(args.output, receipt)
    except (ContractError, OSError) as exc:
        print(f"PROVENANCE_CONTRACT_FAIL type={type(exc).__name__}", file=os.sys.stderr)
        return 2
    print(
        "PROVENANCE_CONTRACT_PASS "
        f"runs={receipt['inventory']['provenance_rows']} "
        f"archives={receipt['inventory']['archives']} "
        f"mapping_sha256={receipt['mapping_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
