#!/usr/bin/env python3
"""Independently verify Decision-Corpus evidence index v6."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from phase1 import decision_corpus_evidence_index_v6_schema as schema


class VerificationError(RuntimeError):
    pass


def normalized_utf8_lf(path: Path) -> bytes:
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as error:
        raise VerificationError(f"artifact is not UTF-8: {path}") from error
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def normalized_sha256(path: Path) -> str:
    return hashlib.sha256(normalized_utf8_lf(path)).hexdigest()


def resolve_json(repo_root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise VerificationError(f"absolute artifact path is forbidden: {relative}")
    resolved = (repo_root / candidate).resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as error:
        raise VerificationError(f"artifact escapes repository root: {relative}") from error
    if not resolved.is_file() or resolved.suffix != ".json":
        raise VerificationError(f"JSON artifact is missing: {relative}")
    return resolved


def resolve_bound_file(repo_root: Path, relative: str, expected_format: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise VerificationError(f"absolute bound-file path is forbidden: {relative}")
    resolved = (repo_root / candidate).resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as error:
        raise VerificationError(f"bound file escapes repository root: {relative}") from error
    expected_suffix = {"jsonl": ".jsonl", "csv": ".csv"}.get(expected_format)
    if expected_suffix is None:
        raise VerificationError(f"unsupported bound-file format: {expected_format}")
    if not resolved.is_file() or resolved.suffix != expected_suffix:
        raise VerificationError(f"{expected_format.upper()} bound file is missing: {relative}")
    return resolved


def verify_bound_payload(path: Path, specification: dict[str, Any]) -> int:
    lines = normalized_utf8_lf(path).decode("utf-8").splitlines()
    if len(lines) != specification["line_count"]:
        raise VerificationError(f"bound-file line count mismatch: {specification['path']}")
    if specification["format"] == "jsonl":
        for line_number, line in enumerate(lines, 1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise VerificationError(
                    f"invalid JSONL at {specification['path']}:{line_number}"
                ) from error
            if not isinstance(value, dict):
                raise VerificationError(
                    f"non-object JSONL row at {specification['path']}:{line_number}"
                )
        return len(lines)
    if specification["format"] == "csv":
        rows = list(csv.reader(lines))
        if not rows or rows[0] != specification["header"]:
            raise VerificationError(f"bound CSV header mismatch: {specification['path']}")
        if len(rows) - 1 != specification["data_row_count"]:
            raise VerificationError(f"bound CSV data-row mismatch: {specification['path']}")
        if any(len(row) != len(rows[0]) for row in rows[1:]):
            raise VerificationError(f"bound CSV width mismatch: {specification['path']}")
        return len(rows) - 1
    raise VerificationError(f"unsupported bound-file format: {specification['format']}")


def asserted_value(payload: Any, assertion_path: str) -> Any:
    if isinstance(payload, dict) and assertion_path in payload:
        return payload[assertion_path]
    current = payload
    for component in assertion_path.split("."):
        if not isinstance(current, dict) or component not in current:
            raise VerificationError(f"missing JSON assertion path: {assertion_path}")
        current = current[component]
    return current


def merged_contract(source: dict[str, Any], key: str, additions: dict[str, Any]) -> dict[str, Any]:
    original = source.get(key)
    if not isinstance(original, dict):
        raise VerificationError(f"source v5 lacks object contract: {key}")
    overlap = set(original).intersection(additions)
    if overlap:
        raise VerificationError(f"v6 additions overwrite source {key}: {sorted(overlap)}")
    return {**copy.deepcopy(original), **copy.deepcopy(additions)}


def expected_index(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    source_path = (repo_root / schema.SOURCE_INDEX_RELATIVE).resolve()
    if normalized_sha256(source_path) != schema.SOURCE_INDEX_SHA256_NORMALIZED_LF:
        raise VerificationError("source v5 index normalized SHA-256 mismatch")
    source = json.loads(normalized_utf8_lf(source_path).decode("utf-8"))
    if source.get("protocol") != schema.SOURCE_PROTOCOL:
        raise VerificationError("source v5 protocol mismatch")
    if source.get("status") != schema.SOURCE_STATUS:
        raise VerificationError("source v5 status mismatch")
    if [entry.get("name") for entry in source.get("entries", [])] != schema.SOURCE_ENTRY_NAMES:
        raise VerificationError("source v5 entry order or membership changed")

    entry = copy.deepcopy(schema.COVERAGE_ENTRY)
    for artifact in entry["artifacts"]:
        resolved = resolve_json(repo_root, artifact["path"])
        if normalized_sha256(resolved) != artifact["sha256_normalized_lf"]:
            raise VerificationError(f"pinned artifact SHA mismatch: {artifact['path']}")

    entries = copy.deepcopy(source["entries"])
    entries.insert(8, entry)
    return {
        "protocol": schema.PROTOCOL,
        "status": schema.STATUS,
        "source_v5_index": {
            "path": schema.SOURCE_INDEX_RELATIVE,
            "sha256_normalized_lf": schema.SOURCE_INDEX_SHA256_NORMALIZED_LF,
        },
        "scope": merged_contract(source, "scope", schema.SCOPE_ADDITIONS),
        "reporting_contract": merged_contract(
            source, "reporting_contract", schema.REPORTING_CONTRACT_ADDITIONS
        ),
        "entries": entries,
    }


def verify_index(repo_root: Path, index_path: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    index_path = index_path.resolve()
    payload = json.loads(normalized_utf8_lf(index_path).decode("utf-8"))
    if payload != expected_index(repo_root):
        raise VerificationError("v6 index differs from independent reconstruction")

    artifact_paths: set[str] = set()
    bound_paths: set[str] = set()
    assertion_count = 0
    verified_entries: list[dict[str, Any]] = []
    for entry in payload["entries"]:
        if not entry.get("estimand") or not entry.get("supported_claim"):
            raise VerificationError(f"entry lacks estimand/claim: {entry.get('name')}")
        if not entry.get("does_not_prove"):
            raise VerificationError(f"entry lacks boundary: {entry.get('name')}")
        verified_bound: list[dict[str, Any]] = []
        for bound in entry.get("bound_files", []):
            relative = bound["path"]
            if relative in bound_paths or relative in artifact_paths:
                raise VerificationError(f"duplicate evidence path: {relative}")
            bound_paths.add(relative)
            resolved = resolve_bound_file(repo_root, relative, bound["format"])
            actual_sha = normalized_sha256(resolved)
            if actual_sha != bound["sha256_normalized_lf"]:
                raise VerificationError(f"bound-file contract mismatch: {relative}")
            verified_row_count = verify_bound_payload(resolved, bound)
            verified_bound.append(
                {
                    "path": relative,
                    "format": bound["format"],
                    "sha256_normalized_lf": actual_sha,
                    "line_count": bound["line_count"],
                    "verified_row_count": verified_row_count,
                }
            )
        verified_artifacts: list[dict[str, Any]] = []
        for artifact in entry["artifacts"]:
            relative = artifact["path"]
            if relative in artifact_paths or relative in bound_paths:
                raise VerificationError(f"duplicate evidence path: {relative}")
            artifact_paths.add(relative)
            resolved = resolve_json(repo_root, relative)
            actual_sha = normalized_sha256(resolved)
            if actual_sha != artifact["sha256_normalized_lf"]:
                raise VerificationError(f"normalized SHA mismatch: {relative}")
            artifact_payload = json.loads(normalized_utf8_lf(resolved).decode("utf-8"))
            assertions = artifact.get("json_assertions")
            if not isinstance(assertions, dict) or not assertions:
                raise VerificationError(f"artifact lacks assertions: {relative}")
            for assertion_path, expected_value in assertions.items():
                if asserted_value(artifact_payload, assertion_path) != expected_value:
                    raise VerificationError(
                        f"JSON assertion mismatch: {relative}:{assertion_path}"
                    )
                assertion_count += 1
            verified_artifacts.append(
                {
                    "path": relative,
                    "sha256_normalized_lf": actual_sha,
                    "json_assertions": len(assertions),
                }
            )
        verified_entries.append(
            {
                "name": entry["name"],
                "bound_files": verified_bound,
                "artifacts": verified_artifacts,
            }
        )

    return {
        "protocol": schema.PROTOCOL,
        "status": "INDEPENDENTLY_VERIFIED_COMMON_SUPPORT_EVIDENCE_INDEX",
        "index_sha256_normalized_lf": normalized_sha256(index_path),
        "source_v5_index_sha256_normalized_lf": schema.SOURCE_INDEX_SHA256_NORMALIZED_LF,
        "entry_count": len(payload["entries"]),
        "artifact_count": len(artifact_paths),
        "bound_file_count": len(bound_paths),
        "json_assertion_count": assertion_count,
        "scope": payload["scope"],
        "reporting_contract": payload["reporting_contract"],
        "verified_entries": verified_entries,
        "producer_function_imported": False,
        "prospective_outcomes_read": False,
        "prediction_values_aggregated": False,
    }


def atomic_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise VerificationError(f"output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--index", required=True)
    parser.add_argument("--out", required=True)
    arguments = parser.parse_args()
    receipt = verify_index(Path(arguments.repo_root), Path(arguments.index))
    atomic_json(Path(arguments.out).resolve(), receipt)
    print(receipt["status"])


if __name__ == "__main__":
    main()
