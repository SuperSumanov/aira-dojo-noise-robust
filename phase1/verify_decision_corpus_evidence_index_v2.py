#!/usr/bin/env python3
"""Independently verify the source-aware Decision-Corpus evidence index v2."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from phase1 import decision_corpus_evidence_index_v2_schema as schema


class VerificationError(RuntimeError):
    pass


def normalized_utf8_lf(path: Path) -> bytes:
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as error:
        raise VerificationError(f"artifact is not UTF-8 JSON: {path}") from error
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def normalized_sha256(path: Path) -> str:
    return hashlib.sha256(normalized_utf8_lf(path)).hexdigest()


def resolve_artifact(repo_root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise VerificationError(f"absolute artifact path is forbidden: {relative}")
    resolved = (repo_root / candidate).resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as error:
        raise VerificationError(f"artifact escapes repository root: {relative}") from error
    if not resolved.is_file():
        raise VerificationError(f"artifact is missing: {relative}")
    if resolved.suffix != ".json":
        raise VerificationError(f"evidence artifact is not JSON: {relative}")
    return resolved


def dotted_value(payload: Any, dotted_path: str) -> Any:
    current = payload
    for component in dotted_path.split("."):
        if not isinstance(current, dict) or component not in current:
            raise VerificationError(f"missing JSON assertion path: {dotted_path}")
        current = current[component]
    return current


def expected_index(repo_root: Path) -> dict[str, Any]:
    """Reconstruct the frozen v2 schema without importing the producer function."""
    source_path = (repo_root / schema.SOURCE_INDEX_RELATIVE).resolve()
    if normalized_sha256(source_path) != schema.SOURCE_INDEX_SHA256_NORMALIZED_LF:
        raise VerificationError("source v1 index normalized SHA-256 mismatch")
    source = json.loads(normalized_utf8_lf(source_path).decode("utf-8"))
    if source.get("protocol") != schema.SOURCE_PROTOCOL:
        raise VerificationError("source v1 protocol mismatch")
    if source.get("status") != schema.SOURCE_STATUS:
        raise VerificationError("source v1 status mismatch")

    expected_names = [
        "decision_corpus",
        "label_repeatability",
        "normalized_clone",
        "deployment_cost",
        "prospective_gate",
    ]
    if [entry.get("name") for entry in source.get("entries", [])] != expected_names:
        raise VerificationError("source v1 entry order or membership changed")

    inherited: dict[str, dict[str, Any]] = {}
    for original in source["entries"]:
        entry = copy.deepcopy(original)
        name = entry["name"]
        entry["supported_claim"] = schema.SUPPORTED_CLAIMS[name]
        for artifact in entry["artifacts"]:
            resolved = resolve_artifact(repo_root, artifact["path"])
            artifact.pop("sha256", None)
            artifact["sha256_normalized_lf"] = normalized_sha256(resolved)
        inherited[name] = entry

    source_entry = copy.deepcopy(schema.SOURCE_ENTRY)
    for artifact in source_entry["artifacts"]:
        resolved = resolve_artifact(repo_root, artifact["path"])
        artifact["sha256_normalized_lf"] = normalized_sha256(resolved)
    inherited["source_opportunity"] = source_entry

    order = [
        "decision_corpus",
        "source_opportunity",
        "label_repeatability",
        "normalized_clone",
        "deployment_cost",
        "prospective_gate",
    ]
    return {
        "protocol": schema.PROTOCOL,
        "status": schema.STATUS,
        "source_v1_index": {
            "path": schema.SOURCE_INDEX_RELATIVE,
            "sha256_normalized_lf": schema.SOURCE_INDEX_SHA256_NORMALIZED_LF,
        },
        "scope": schema.SCOPE,
        "reporting_contract": schema.REPORTING_CONTRACT,
        "entries": [inherited[name] for name in order],
    }


def verify_index(repo_root: Path, index_path: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    index_path = index_path.resolve()
    try:
        index_path.relative_to(repo_root)
    except ValueError as error:
        raise VerificationError("index must be inside repository root") from error

    payload = json.loads(normalized_utf8_lf(index_path).decode("utf-8"))
    expected = expected_index(repo_root)
    if payload != expected:
        raise VerificationError("v2 index differs from independently reconstructed schema")

    artifact_paths: set[str] = set()
    assertion_count = 0
    verified_entries: list[dict[str, Any]] = []
    for entry in payload["entries"]:
        if not entry.get("estimand") or not entry.get("supported_claim"):
            raise VerificationError(f"entry lacks estimand/claim: {entry.get('name')}")
        if not entry.get("does_not_prove"):
            raise VerificationError(f"entry lacks boundary: {entry.get('name')}")
        verified_artifacts: list[dict[str, Any]] = []
        for artifact in entry["artifacts"]:
            relative = artifact["path"]
            if relative in artifact_paths:
                raise VerificationError(f"duplicate artifact path: {relative}")
            artifact_paths.add(relative)
            resolved = resolve_artifact(repo_root, relative)
            actual_sha = normalized_sha256(resolved)
            if actual_sha != artifact["sha256_normalized_lf"]:
                raise VerificationError(f"normalized SHA mismatch: {relative}")
            artifact_payload = json.loads(normalized_utf8_lf(resolved).decode("utf-8"))
            assertions = artifact.get("json_assertions")
            if not isinstance(assertions, dict) or not assertions:
                raise VerificationError(f"artifact lacks assertions: {relative}")
            for dotted_path, expected_value in assertions.items():
                if dotted_value(artifact_payload, dotted_path) != expected_value:
                    raise VerificationError(
                        f"JSON assertion mismatch: {relative}:{dotted_path}"
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
            {"name": entry["name"], "artifacts": verified_artifacts}
        )

    return {
        "protocol": schema.PROTOCOL,
        "status": "INDEPENDENTLY_VERIFIED_SOURCE_AWARE_EVIDENCE_INDEX",
        "index_sha256_normalized_lf": normalized_sha256(index_path),
        "source_v1_index_sha256_normalized_lf": (
            schema.SOURCE_INDEX_SHA256_NORMALIZED_LF
        ),
        "entry_count": len(payload["entries"]),
        "artifact_count": len(artifact_paths),
        "json_assertion_count": assertion_count,
        "scope": schema.SCOPE,
        "reporting_contract": schema.REPORTING_CONTRACT,
        "verified_entries": verified_entries,
        "producer_function_imported": False,
        "prospective_outcomes_read": False,
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
