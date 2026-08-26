#!/usr/bin/env python3
"""Migrate ABC crosswalk v1 into a clean-provenance v2."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from typing import Any

from phase1 import agentic_benchmark_checklist_crosswalk_v2_schema as frozen


class BuildError(RuntimeError):
    pass


def normalized_lf_bytes(path: Path) -> bytes:
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise BuildError(f"cannot read UTF-8 artifact: {path}") from error
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def normalized_sha256(path: Path) -> str:
    return hashlib.sha256(normalized_lf_bytes(path)).hexdigest()


def resolve_evidence(repo_root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise BuildError(f"unsafe evidence path: {relative}")
    if pure.parts[0] != "phase1":
        raise BuildError(f"evidence outside phase1: {relative}")
    unresolved = repo_root.joinpath(*pure.parts)
    if unresolved.is_symlink():
        raise BuildError(f"symlinked evidence is forbidden: {relative}")
    resolved = unresolved.resolve()
    phase1_root = (repo_root / "phase1").resolve()
    if phase1_root not in resolved.parents or not resolved.is_file():
        raise BuildError(f"missing or escaped evidence path: {relative}")
    return resolved


def load_source(repo_root: Path, source_path: Path) -> dict[str, Any]:
    expected = (repo_root / frozen.SOURCE_PATH).resolve()
    source_path = source_path.resolve()
    if source_path != expected:
        raise BuildError("source must be the frozen ABC crosswalk v1 human template")
    if normalized_sha256(source_path) != frozen.SOURCE_SHA256_NORMALIZED_LF:
        raise BuildError("source crosswalk v1 normalized SHA-256 mismatch")
    try:
        value = json.loads(normalized_lf_bytes(source_path).decode("utf-8"))
    except json.JSONDecodeError as error:
        raise BuildError("source crosswalk v1 is invalid JSON") from error
    if (
        value.get("protocol") != frozen.SOURCE_PROTOCOL
        or value.get("status") != frozen.SOURCE_STATUS
    ):
        raise BuildError("source crosswalk v1 protocol/status mismatch")
    if tuple(item.get("id") for item in value.get("items", [])) != (
        frozen.EXPECTED_ITEM_IDS
    ):
        raise BuildError("source ABC item set or order changed")
    if not set(frozen.REMOVED_EVIDENCE_IDS).issubset(value.get("evidence_catalog", {})):
        raise BuildError("source does not contain every frozen removed evidence id")
    return value


def transform_evidence_ids(item: dict[str, Any]) -> None:
    transformed: list[str] = []
    for evidence_id in item["local_evidence_ids"]:
        replacement = frozen.EVIDENCE_ID_REPLACEMENTS.get(evidence_id, evidence_id)
        if replacement not in transformed:
            transformed.append(replacement)
    for evidence_id in frozen.ITEM_EXTRA_EVIDENCE.get(item["id"], ()):
        if evidence_id not in transformed:
            transformed.append(evidence_id)
    item["local_evidence_ids"] = transformed
    if item["id"] in frozen.ITEM_RATIONALE_REPLACEMENTS:
        item["rationale"] = frozen.ITEM_RATIONALE_REPLACEMENTS[item["id"]]


def migrate(repo_root: Path, source_path: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    source = load_source(repo_root, source_path)
    payload = copy.deepcopy(source)
    payload["protocol"] = frozen.PROTOCOL
    payload["status"] = frozen.STATUS
    payload["assessment_date"] = "2026-08-26"
    payload["source_v1_template"] = {
        "path": frozen.SOURCE_PATH,
        "sha256_normalized_lf": frozen.SOURCE_SHA256_NORMALIZED_LF,
        "used_for_human_item_text_and_conservative_statuses_only": True,
        "source_evidence_artifacts_opened": False,
        "source_access_attestation_inherited": False,
    }
    payload["provenance_repair"] = {
        "removed_evidence_ids": list(frozen.REMOVED_EVIDENCE_IDS),
        "added_clean_evidence_ids": list(frozen.ADDED_EVIDENCE),
        "withdrawn_artifacts_used_as_v2_evidence": False,
        "v6_or_value_reading_matrix_inherited": False,
        "human_statuses_upgraded_during_migration": False,
        "historical_files_deleted_or_overwritten": False,
    }
    payload["access_attestation"] = copy.deepcopy(frozen.ACCESS_ATTESTATION)

    catalog = copy.deepcopy(source["evidence_catalog"])
    for evidence_id in frozen.REMOVED_EVIDENCE_IDS:
        del catalog[evidence_id]
    overlap = set(catalog).intersection(frozen.ADDED_EVIDENCE)
    if overlap:
        raise BuildError(f"added evidence IDs collide with source: {sorted(overlap)}")
    catalog.update(copy.deepcopy(frozen.ADDED_EVIDENCE))
    for evidence_id, evidence in catalog.items():
        relative = evidence["path"]
        if any(
            fragment in relative
            for fragment in frozen.FORBIDDEN_EVIDENCE_PATH_FRAGMENTS
        ):
            raise BuildError(f"withdrawn evidence path remains: {evidence_id}")
        resolved = resolve_evidence(repo_root, relative)
        if normalized_sha256(resolved) != evidence["sha256_normalized_lf"]:
            raise BuildError(f"evidence hash mismatch: {evidence_id}")
    payload["evidence_catalog"] = catalog

    for item in payload["items"]:
        transform_evidence_ids(item)
        if any(value in frozen.REMOVED_EVIDENCE_IDS for value in item["local_evidence_ids"]):
            raise BuildError(f"removed evidence id remains in item: {item['id']}")
        if item["status"] != next(
            source_item["status"]
            for source_item in source["items"]
            if source_item["id"] == item["id"]
        ):
            raise BuildError(f"migration changed human status: {item['id']}")

    referenced = {
        evidence_id
        for item in payload["items"]
        for evidence_id in item["local_evidence_ids"]
    }
    if referenced != set(catalog):
        raise BuildError(
            f"catalog/reference mismatch: missing={sorted(set(catalog) - referenced)} "
            f"unknown={sorted(referenced - set(catalog))}"
        )
    return payload


def atomic_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise BuildError(f"output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--source-crosswalk", required=True)
    parser.add_argument("--out", required=True)
    arguments = parser.parse_args()
    payload = migrate(Path(arguments.repo_root), Path(arguments.source_crosswalk))
    atomic_json(Path(arguments.out).resolve(), payload)
    print(frozen.STATUS)


if __name__ == "__main__":
    main()
