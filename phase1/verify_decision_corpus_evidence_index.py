#!/usr/bin/env python3
"""Independently verify the provisional Decision-Corpus evidence index.

The index binds separate attestations by hash and status.  This verifier never
imports any attestation producer and deliberately does not merge estimands.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


PROTOCOL = "decision_corpus_evidence_index_v1"
INDEX_STATUS = "PROVISIONAL_EVIDENCE_STACK_AWAITING_FIRST960"
REQUIRED_ENTRIES = {
    "decision_corpus",
    "label_repeatability",
    "normalized_clone",
    "deployment_cost",
    "prospective_gate",
}
REQUIRED_SCOPE = {
    "estimands_merged": False,
    "prospective_outcomes_read": False,
    "prospective_vault_open_allowed": False,
    "frozen_accuracy_computed_by_deployment_cost": False,
    "release_complete": False,
}


class VerificationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
        raise VerificationError(f"artifact is missing or not a file: {relative}")
    return resolved


def dotted_value(payload: Any, dotted_path: str) -> Any:
    current = payload
    for component in dotted_path.split("."):
        if not isinstance(current, dict) or component not in current:
            raise VerificationError(f"missing JSON assertion path: {dotted_path}")
        current = current[component]
    return current


def verify_index(repo_root: Path, index_path: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    index_path = index_path.resolve()
    try:
        index_path.relative_to(repo_root)
    except ValueError as error:
        raise VerificationError("index must be inside the repository root") from error
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    if payload.get("protocol") != PROTOCOL:
        raise VerificationError("index protocol mismatch")
    if payload.get("status") != INDEX_STATUS:
        raise VerificationError("index status mismatch")
    if payload.get("scope") != REQUIRED_SCOPE:
        raise VerificationError("index scope is not the frozen provisional scope")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise VerificationError("entries must be a list")
    names = [entry.get("name") for entry in entries if isinstance(entry, dict)]
    if len(names) != len(entries) or set(names) != REQUIRED_ENTRIES or len(set(names)) != len(names):
        raise VerificationError("evidence entry names are missing, duplicated, or unexpected")
    estimands = [entry.get("estimand") for entry in entries]
    if any(not isinstance(value, str) or not value for value in estimands):
        raise VerificationError("every entry needs a non-empty estimand")
    if len(set(estimands)) != len(estimands):
        raise VerificationError("attestation estimands must remain distinct")

    verified: list[dict[str, Any]] = []
    artifact_paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry.get("does_not_prove"), str) or not entry["does_not_prove"]:
            raise VerificationError(f"{entry['name']} lacks a does_not_prove boundary")
        artifacts = entry.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            raise VerificationError(f"{entry['name']} has no artifacts")
        verified_artifacts: list[dict[str, Any]] = []
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                raise VerificationError("artifact entry must be an object")
            relative = artifact.get("path")
            expected_sha = artifact.get("sha256")
            if not isinstance(relative, str) or not isinstance(expected_sha, str):
                raise VerificationError("artifact path/hash must be strings")
            if relative in artifact_paths:
                raise VerificationError(f"artifact path is duplicated: {relative}")
            artifact_paths.add(relative)
            resolved = resolve_artifact(repo_root, relative)
            actual_sha = sha256(resolved)
            if actual_sha != expected_sha:
                raise VerificationError(f"artifact SHA mismatch: {relative}")
            assertions = artifact.get("json_assertions", {})
            if not isinstance(assertions, dict):
                raise VerificationError("json_assertions must be an object")
            if assertions:
                artifact_payload = json.loads(resolved.read_text(encoding="utf-8"))
                for dotted_path, expected in assertions.items():
                    if dotted_value(artifact_payload, dotted_path) != expected:
                        raise VerificationError(
                            f"JSON assertion mismatch: {relative}:{dotted_path}"
                        )
            verified_artifacts.append(
                {
                    "path": relative,
                    "sha256": actual_sha,
                    "json_assertions": len(assertions),
                }
            )
        verified.append({"name": entry["name"], "artifacts": verified_artifacts})

    return {
        "protocol": PROTOCOL,
        "status": "INDEPENDENTLY_VERIFIED_DECISION_CORPUS_EVIDENCE_INDEX",
        "index_sha256": sha256(index_path),
        "entry_count": len(entries),
        "artifact_count": len(artifact_paths),
        "required_entries": sorted(REQUIRED_ENTRIES),
        "scope": REQUIRED_SCOPE,
        "verified_entries": verified,
        "producer_imported": False,
    }


def atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
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
    output = Path(arguments.out).resolve()
    if output.exists():
        raise VerificationError(f"verification output already exists: {output}")
    receipt = verify_index(Path(arguments.repo_root), Path(arguments.index))
    atomic_json(output, receipt)
    print(receipt["status"])


if __name__ == "__main__":
    main()
