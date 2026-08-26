#!/usr/bin/env python3
"""Independently verify the clean-provenance Decision-Corpus index v7."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from phase1 import decision_corpus_evidence_index_v7_schema as schema


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


def resolve_file(repo_root: Path, relative: str, suffix: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise VerificationError(f"unsafe evidence path: {relative}")
    resolved = (repo_root / candidate).resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as error:
        raise VerificationError(f"evidence escapes repository root: {relative}") from error
    if not resolved.is_file() or resolved.suffix != suffix:
        raise VerificationError(f"evidence file is missing: {relative}")
    return resolved


def resolve_json(repo_root: Path, relative: str) -> Path:
    return resolve_file(repo_root, relative, ".json")


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
        if isinstance(current, dict) and component in current:
            current = current[component]
        elif isinstance(current, list) and component.isdigit():
            index = int(component)
            if index >= len(current):
                raise VerificationError(
                    f"list index outside JSON assertion path: {assertion_path}"
                )
            current = current[index]
        else:
            raise VerificationError(f"missing JSON assertion path: {assertion_path}")
    return current


def merged_contract(
    source: dict[str, Any], key: str, additions: dict[str, Any]
) -> dict[str, Any]:
    original = source.get(key)
    if not isinstance(original, dict):
        raise VerificationError(f"source v5 lacks object contract: {key}")
    overlap = set(original).intersection(additions)
    if overlap:
        raise VerificationError(f"v7 additions overwrite source {key}: {sorted(overlap)}")
    return {**copy.deepcopy(original), **copy.deepcopy(additions)}


def expected_index(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    source_path = resolve_json(repo_root, schema.SOURCE_INDEX_RELATIVE)
    if normalized_sha256(source_path) != schema.SOURCE_INDEX_SHA256_NORMALIZED_LF:
        raise VerificationError("source v5 index normalized SHA-256 mismatch")
    source = json.loads(normalized_utf8_lf(source_path).decode("utf-8"))
    if (
        source.get("protocol") != schema.SOURCE_PROTOCOL
        or source.get("status") != schema.SOURCE_STATUS
    ):
        raise VerificationError("source v5 protocol/status mismatch")
    if [entry.get("name") for entry in source.get("entries", [])] != (
        schema.SOURCE_ENTRY_NAMES
    ):
        raise VerificationError("source v5 entry order or membership changed")

    registry = resolve_json(repo_root, schema.WITHDRAWAL_REGISTRY["path"])
    if normalized_sha256(registry) != schema.WITHDRAWAL_REGISTRY[
        "sha256_normalized_lf"
    ]:
        raise VerificationError("withdrawal registry normalized SHA-256 mismatch")

    replacements = copy.deepcopy(schema.REPLACEMENT_ENTRIES)
    entries = copy.deepcopy(source["entries"][:8]) + replacements + copy.deepcopy(
        source["entries"][8:]
    )
    return {
        "protocol": schema.PROTOCOL,
        "status": schema.STATUS,
        "source_v5_index": {
            "path": schema.SOURCE_INDEX_RELATIVE,
            "sha256_normalized_lf": schema.SOURCE_INDEX_SHA256_NORMALIZED_LF,
        },
        "provenance_repair": {
            "withdrawal_registry": copy.deepcopy(schema.WITHDRAWAL_REGISTRY),
            "source_v6_read_or_inherited": False,
            "forbidden_evidence_path_fragments": copy.deepcopy(
                schema.FORBIDDEN_EVIDENCE_PATH_FRAGMENTS
            ),
            "replacement_entry_names": [entry["name"] for entry in replacements],
            "historical_files_deleted_or_overwritten": False,
            "v1_provenance_retroactively_repaired": False,
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
        raise VerificationError("v7 index differs from independent reconstruction")

    artifact_paths: set[str] = set()
    bound_paths: set[str] = set()
    assertion_count = 0
    verified_entries: list[dict[str, Any]] = []
    for entry in payload["entries"]:
        if not all(entry.get(key) for key in ("name", "estimand", "supported_claim")):
            raise VerificationError("entry lacks name, estimand, or claim")
        if not entry.get("does_not_prove"):
            raise VerificationError(f"entry lacks boundary: {entry.get('name')}")
        verified_bound: list[dict[str, Any]] = []
        for bound in entry.get("bound_files", []):
            relative = bound["path"]
            if relative in artifact_paths or relative in bound_paths:
                raise VerificationError(f"duplicate evidence path: {relative}")
            if any(
                fragment in relative
                for fragment in schema.FORBIDDEN_EVIDENCE_PATH_FRAGMENTS
            ):
                raise VerificationError(f"withdrawn bound path used as evidence: {relative}")
            bound_paths.add(relative)
            suffix = {"jsonl": ".jsonl", "csv": ".csv"}.get(bound["format"])
            if suffix is None:
                raise VerificationError(f"unsupported bound format: {bound['format']}")
            resolved = resolve_file(repo_root, relative, suffix)
            actual_sha = normalized_sha256(resolved)
            if actual_sha != bound["sha256_normalized_lf"]:
                raise VerificationError(f"bound-file contract mismatch: {relative}")
            rows = verify_bound_payload(resolved, bound)
            verified_bound.append(
                {
                    "path": relative,
                    "format": bound["format"],
                    "sha256_normalized_lf": actual_sha,
                    "verified_row_count": rows,
                }
            )

        verified_artifacts: list[dict[str, Any]] = []
        for artifact in entry["artifacts"]:
            relative = artifact["path"]
            if relative in artifact_paths or relative in bound_paths:
                raise VerificationError(f"duplicate evidence path: {relative}")
            if any(
                fragment in relative
                for fragment in schema.FORBIDDEN_EVIDENCE_PATH_FRAGMENTS
            ):
                raise VerificationError(f"withdrawn artifact used as evidence: {relative}")
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
        "status": "INDEPENDENTLY_VERIFIED_CLEAN_PROVENANCE_EVIDENCE_INDEX",
        "index_sha256_normalized_lf": normalized_sha256(index_path),
        "source_v5_index_sha256_normalized_lf": (
            schema.SOURCE_INDEX_SHA256_NORMALIZED_LF
        ),
        "entry_count": len(payload["entries"]),
        "artifact_count": len(artifact_paths),
        "bound_file_count": len(bound_paths),
        "json_assertion_count": assertion_count,
        "scope": payload["scope"],
        "reporting_contract": payload["reporting_contract"],
        "verified_entries": verified_entries,
        "producer_function_imported": False,
        "source_v6_read_or_inherited": False,
        "withdrawn_evidence_paths_used": False,
        "prediction_pair_files_opened": False,
        "prediction_values_read_or_aggregated": False,
        "prospective_outcomes_read": False,
        "accuracy_effect_or_search_utility_computed": False,
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
