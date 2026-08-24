#!/usr/bin/env python3
"""Build the common-support Decision-Corpus evidence index v6."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from phase1 import decision_corpus_evidence_index_v6_schema as frozen


PROTOCOL = frozen.PROTOCOL
STATUS = frozen.STATUS
SOURCE_PROTOCOL = frozen.SOURCE_PROTOCOL
SOURCE_STATUS = frozen.SOURCE_STATUS
SOURCE_INDEX_RELATIVE = frozen.SOURCE_INDEX_RELATIVE
SOURCE_INDEX_SHA256_NORMALIZED_LF = frozen.SOURCE_INDEX_SHA256_NORMALIZED_LF
SOURCE_ENTRY_NAMES = frozen.SOURCE_ENTRY_NAMES
SCOPE_ADDITIONS = frozen.SCOPE_ADDITIONS
REPORTING_CONTRACT_ADDITIONS = frozen.REPORTING_CONTRACT_ADDITIONS
COVERAGE_ENTRY = frozen.COVERAGE_ENTRY


class BuildError(RuntimeError):
    pass


def normalized_utf8_lf(path: Path) -> bytes:
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as error:
        raise BuildError(f"artifact is not UTF-8 JSON: {path}") from error
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def normalized_sha256(path: Path) -> str:
    return hashlib.sha256(normalized_utf8_lf(path)).hexdigest()


def resolve_json(repo_root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise BuildError(f"absolute artifact path is forbidden: {relative}")
    resolved = (repo_root / candidate).resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as error:
        raise BuildError(f"artifact escapes repository root: {relative}") from error
    if not resolved.is_file() or resolved.suffix != ".json":
        raise BuildError(f"JSON artifact is missing: {relative}")
    return resolved


def merged_contract(source: dict[str, Any], key: str, additions: dict[str, Any]) -> dict[str, Any]:
    original = source.get(key)
    if not isinstance(original, dict):
        raise BuildError(f"source v5 lacks object contract: {key}")
    overlap = set(original).intersection(additions)
    if overlap:
        raise BuildError(f"v6 additions overwrite source {key}: {sorted(overlap)}")
    return {**copy.deepcopy(original), **copy.deepcopy(additions)}


def build_index(repo_root: Path, source_index_path: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    source_index_path = source_index_path.resolve()
    expected_source = (repo_root / SOURCE_INDEX_RELATIVE).resolve()
    if source_index_path != expected_source:
        raise BuildError("source index path is not the frozen v5 index")
    if normalized_sha256(source_index_path) != SOURCE_INDEX_SHA256_NORMALIZED_LF:
        raise BuildError("source v5 index normalized SHA-256 mismatch")

    source = json.loads(normalized_utf8_lf(source_index_path).decode("utf-8"))
    if source.get("protocol") != SOURCE_PROTOCOL or source.get("status") != SOURCE_STATUS:
        raise BuildError("source v5 protocol/status mismatch")
    if [entry.get("name") for entry in source.get("entries", [])] != SOURCE_ENTRY_NAMES:
        raise BuildError("source v5 entry order or membership changed")

    entry = copy.deepcopy(COVERAGE_ENTRY)
    for artifact in entry["artifacts"]:
        resolved = resolve_json(repo_root, artifact["path"])
        if normalized_sha256(resolved) != artifact["sha256_normalized_lf"]:
            raise BuildError(f"pinned artifact SHA mismatch: {artifact['path']}")

    entries = copy.deepcopy(source["entries"])
    entries.insert(8, entry)
    return {
        "protocol": PROTOCOL,
        "status": STATUS,
        "source_v5_index": {
            "path": SOURCE_INDEX_RELATIVE,
            "sha256_normalized_lf": SOURCE_INDEX_SHA256_NORMALIZED_LF,
        },
        "scope": merged_contract(source, "scope", SCOPE_ADDITIONS),
        "reporting_contract": merged_contract(
            source, "reporting_contract", REPORTING_CONTRACT_ADDITIONS
        ),
        "entries": entries,
    }


def atomic_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise BuildError(f"output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--source-index", required=True)
    parser.add_argument("--out", required=True)
    arguments = parser.parse_args()
    payload = build_index(Path(arguments.repo_root), Path(arguments.source_index))
    atomic_json(Path(arguments.out).resolve(), payload)
    print(STATUS)


if __name__ == "__main__":
    main()
