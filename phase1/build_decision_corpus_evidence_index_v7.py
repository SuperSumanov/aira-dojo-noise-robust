#!/usr/bin/env python3
"""Build the clean-provenance Decision-Corpus evidence index v7."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from phase1 import decision_corpus_evidence_index_v7_schema as frozen


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
    if candidate.is_absolute() or ".." in candidate.parts:
        raise BuildError(f"unsafe artifact path: {relative}")
    resolved = (repo_root / candidate).resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as error:
        raise BuildError(f"artifact escapes repository root: {relative}") from error
    if not resolved.is_file() or resolved.suffix != ".json":
        raise BuildError(f"JSON artifact is missing: {relative}")
    return resolved


def merged_contract(
    source: dict[str, Any], key: str, additions: dict[str, Any]
) -> dict[str, Any]:
    original = source.get(key)
    if not isinstance(original, dict):
        raise BuildError(f"source v5 lacks object contract: {key}")
    overlap = set(original).intersection(additions)
    if overlap:
        raise BuildError(f"v7 additions overwrite source {key}: {sorted(overlap)}")
    return {**copy.deepcopy(original), **copy.deepcopy(additions)}


def check_artifact_paths(repo_root: Path, entries: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for entry in entries:
        for artifact in entry.get("artifacts", []):
            relative = artifact["path"]
            if relative in seen:
                raise BuildError(f"duplicate evidence path: {relative}")
            seen.add(relative)
            if any(
                fragment in relative
                for fragment in frozen.FORBIDDEN_EVIDENCE_PATH_FRAGMENTS
            ):
                raise BuildError(f"withdrawn evidence path is forbidden in v7: {relative}")
            resolved = resolve_json(repo_root, relative)
            if normalized_sha256(resolved) != artifact["sha256_normalized_lf"]:
                raise BuildError(f"pinned artifact SHA mismatch: {relative}")


def build_index(repo_root: Path, source_index_path: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    source_index_path = source_index_path.resolve()
    expected_source = (repo_root / frozen.SOURCE_INDEX_RELATIVE).resolve()
    if source_index_path != expected_source:
        raise BuildError("source index path is not the frozen unaffected v5 index")
    if normalized_sha256(source_index_path) != frozen.SOURCE_INDEX_SHA256_NORMALIZED_LF:
        raise BuildError("source v5 index normalized SHA-256 mismatch")

    source = json.loads(normalized_utf8_lf(source_index_path).decode("utf-8"))
    if (
        source.get("protocol") != frozen.SOURCE_PROTOCOL
        or source.get("status") != frozen.SOURCE_STATUS
    ):
        raise BuildError("source v5 protocol/status mismatch")
    if [entry.get("name") for entry in source.get("entries", [])] != (
        frozen.SOURCE_ENTRY_NAMES
    ):
        raise BuildError("source v5 entry order or membership changed")

    registry = resolve_json(repo_root, frozen.WITHDRAWAL_REGISTRY["path"])
    if normalized_sha256(registry) != frozen.WITHDRAWAL_REGISTRY[
        "sha256_normalized_lf"
    ]:
        raise BuildError("withdrawal registry normalized SHA-256 mismatch")

    replacements = copy.deepcopy(frozen.REPLACEMENT_ENTRIES)
    entries = copy.deepcopy(source["entries"][:8]) + replacements + copy.deepcopy(
        source["entries"][8:]
    )
    check_artifact_paths(repo_root, entries)
    return {
        "protocol": frozen.PROTOCOL,
        "status": frozen.STATUS,
        "source_v5_index": {
            "path": frozen.SOURCE_INDEX_RELATIVE,
            "sha256_normalized_lf": frozen.SOURCE_INDEX_SHA256_NORMALIZED_LF,
        },
        "provenance_repair": {
            "withdrawal_registry": copy.deepcopy(frozen.WITHDRAWAL_REGISTRY),
            "source_v6_read_or_inherited": False,
            "forbidden_evidence_path_fragments": copy.deepcopy(
                frozen.FORBIDDEN_EVIDENCE_PATH_FRAGMENTS
            ),
            "replacement_entry_names": [entry["name"] for entry in replacements],
            "historical_files_deleted_or_overwritten": False,
            "v1_provenance_retroactively_repaired": False,
        },
        "scope": merged_contract(source, "scope", frozen.SCOPE_ADDITIONS),
        "reporting_contract": merged_contract(
            source, "reporting_contract", frozen.REPORTING_CONTRACT_ADDITIONS
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
    print(frozen.STATUS)


if __name__ == "__main__":
    main()
