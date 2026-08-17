#!/usr/bin/env python3
"""Independently verify failure-taxonomy artifacts without importing the producer."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any


PROTOCOL = "source-opportunity-failure-taxonomy-v1"
PASS_STATUS = "VERIFIED_STRUCTURED_FAILURE_MEMORY_SUPPORT"
VERIFY_STATUS = "INDEPENDENT_FAILURE_TAXONOMY_VERIFIED"
HEX40 = set("0123456789abcdef")
HEX64 = set("0123456789abcdef")
STRUCTURED = frozenset(
    {
        "ARTIFACT_OUTPUT_CONTRACT",
        "RESOURCE_OOM",
        "RESOURCE_TIMEOUT",
        "DEPENDENCY_IMPORT",
        "PYTHON_SYNTAX",
        "FILESYSTEM_INPUT_PATH",
        "LIBRARY_API_ATTRIBUTE",
        "DATA_SCHEMA_SHAPE_TYPE",
        "PROCESS_SIGNAL",
    }
)
UNSTRUCTURED = frozenset({"NO_DIAGNOSTIC_TEXT", "OTHER_TRACEBACK", "NON_TRACEBACK_TEXT"})
UNRECOVERED = frozenset({"TARGET_NODE_NOT_REFINDABLE", "CREDENTIAL_JOURNAL_SKIPPED"})
ALLOWED_CATEGORIES = STRUCTURED | UNSTRUCTURED | UNRECOVERED
CONTRACT_RELATED = frozenset({"ARTIFACT_OUTPUT_CONTRACT", "DATA_SCHEMA_SHAPE_TYPE"})
ROW_KEYS = frozenset(
    {
        "child_id",
        "source_journal_sha256",
        "category",
        "rule_id",
        "diagnostic_text_present",
        "diagnostic_text_bytes",
        "diagnostic_text_sha256",
    }
)
ARTIFACT_NAMES = frozenset(
    {"summary.json", "per_child.jsonl", "command.txt", "sha256_manifest.json"}
)


class VerificationError(RuntimeError):
    pass


def is_hex(value: Any, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and set(value).issubset(HEX40 if length == 40 else HEX64)
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise VerificationError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid JSON file {path.name}: {exc}") from exc


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    raise VerificationError(f"blank JSONL line {line_number}")
                try:
                    row = json.loads(line, object_pairs_hook=reject_duplicate_keys)
                except json.JSONDecodeError as exc:
                    raise VerificationError(f"invalid JSONL line {line_number}") from exc
                if not isinstance(row, dict):
                    raise VerificationError(f"non-object JSONL line {line_number}")
                rows.append(row)
    except (OSError, UnicodeDecodeError) as exc:
        raise VerificationError(f"cannot read per-child artifact: {exc}") from exc
    return rows


def require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise VerificationError(f"{label} mismatch: {actual!r} != {expected!r}")


def verify_manifest(artifact: Path) -> dict[str, str]:
    actual_names = {path.name for path in artifact.iterdir() if path.is_file()}
    require_equal(actual_names, ARTIFACT_NAMES, "artifact filenames")
    manifest = load_json(artifact / "sha256_manifest.json")
    if not isinstance(manifest, dict):
        raise VerificationError("manifest must be an object")
    expected_names = ARTIFACT_NAMES - {"sha256_manifest.json"}
    require_equal(set(manifest), expected_names, "manifest filenames")
    for name in sorted(expected_names):
        digest = manifest[name]
        if not is_hex(digest, 64):
            raise VerificationError(f"invalid manifest digest for {name}")
        require_equal(sha256_file(artifact / name), digest, f"manifest digest {name}")
    return manifest


def verify_command(
    command_path: Path,
    source_commit: str,
    status_sha256: str,
    targets: int,
) -> None:
    try:
        tokens = shlex.split(command_path.read_text(encoding="utf-8"), posix=True)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise VerificationError(f"invalid command artifact: {exc}") from exc
    require_equal(
        tokens[:3],
        ["python", "-m", "phase1.source_opportunity_failure_taxonomy"],
        "module command prefix",
    )
    if tokens.count("--output") != 1 or tokens[tokens.index("--output") + 1] != "<OUTPUT>":
        raise VerificationError("command output must be the canonical placeholder")
    expected_singletons = {
        "--expect-status-sha256": status_sha256,
        "--expect-targets": str(targets),
        "--source-commit": source_commit,
    }
    for flag, expected in expected_singletons.items():
        if tokens.count(flag) != 1 or tokens[tokens.index(flag) + 1] != expected:
            raise VerificationError(f"command mismatch for {flag}")
    if tokens.count("--root") < 1:
        raise VerificationError("command has no provenance roots")


def validate_rows(rows: list[dict[str, Any]], expected_targets: int) -> None:
    require_equal(len(rows), expected_targets, "per-child row count")
    child_ids: list[str] = []
    for index, row in enumerate(rows, 1):
        require_equal(frozenset(row), ROW_KEYS, f"row {index} fields")
        child = row["child_id"]
        if not isinstance(child, str) or child.count("__") < 1:
            raise VerificationError(f"invalid child_id at row {index}")
        if not is_hex(row["source_journal_sha256"], 64):
            raise VerificationError(f"invalid source journal SHA at row {index}")
        category = row["category"]
        if category not in ALLOWED_CATEGORIES:
            raise VerificationError(f"unknown category at row {index}")
        rule_id = row["rule_id"]
        if not isinstance(rule_id, str) or not rule_id.startswith(category + ":"):
            raise VerificationError(f"invalid rule ID at row {index}")
        present = row["diagnostic_text_present"]
        if not isinstance(present, bool):
            raise VerificationError(f"non-boolean diagnostic presence at row {index}")
        byte_count = row["diagnostic_text_bytes"]
        digest = row["diagnostic_text_sha256"]
        if category in UNRECOVERED:
            if present or byte_count is not None or digest is not None:
                raise VerificationError(f"unrecovered row exposes diagnostic metadata at row {index}")
        else:
            if not isinstance(byte_count, int) or isinstance(byte_count, bool) or byte_count < 0:
                raise VerificationError(f"invalid diagnostic byte count at row {index}")
            if not is_hex(digest, 64):
                raise VerificationError(f"invalid diagnostic SHA at row {index}")
            if present and byte_count == 0:
                raise VerificationError(f"present diagnostic has zero bytes at row {index}")
        child_ids.append(child)
    if child_ids != sorted(child_ids) or len(set(child_ids)) != len(child_ids):
        raise VerificationError("child IDs are not unique and strictly sorted")


def recompute(rows: list[dict[str, Any]], credential_shas: int) -> dict[str, Any]:
    total = len(rows)
    categories = collections.Counter(row["category"] for row in rows)
    refound = sum(row["category"] not in UNRECOVERED for row in rows)
    diagnostic = sum(row["diagnostic_text_present"] for row in rows)
    structured = sum(row["category"] in STRUCTURED for row in rows)
    contract_related = sum(row["category"] in CONTRACT_RELATED for row in rows)
    per_task = collections.Counter(row["child_id"].split("__", 1)[0] for row in rows)
    per_task_structured = collections.Counter(
        row["child_id"].split("__", 1)[0]
        for row in rows
        if row["category"] in STRUCTURED
    )
    dominant = max(per_task_structured.values(), default=0)
    gates = {
        "target_refind_rate_ge_0_95": refound / total >= 0.95,
        "diagnostic_text_share_ge_0_50": diagnostic / total >= 0.50,
        "structured_category_share_ge_0_50": structured / total >= 0.50,
        "structured_tasks_ge_10": len(per_task_structured) >= 10,
        "dominant_structured_task_share_le_0_50": dominant / structured <= 0.50 if structured else False,
        "credential_target_journal_shas_eq_0": credential_shas == 0,
    }
    return {
        "targets": total,
        "target_nodes_refound": refound,
        "target_refind_rate": refound / total,
        "diagnostic_text_present": diagnostic,
        "diagnostic_text_share": diagnostic / total,
        "structured_category_nodes": structured,
        "structured_category_share": structured / total,
        "contract_related_nodes": contract_related,
        "contract_related_share": contract_related / total,
        "tasks": len(per_task),
        "structured_tasks": len(per_task_structured),
        "dominant_structured_task_share": dominant / structured if structured else None,
        "categories": dict(sorted(categories.items())),
        "per_task_targets": dict(sorted(per_task.items())),
        "per_task_structured": dict(sorted(per_task_structured.items())),
        "criteria": gates,
    }


def verify(args: argparse.Namespace) -> dict[str, Any]:
    artifact = Path(args.artifact).resolve()
    if not artifact.is_dir():
        raise VerificationError("artifact directory missing")
    if not is_hex(args.expect_source_commit, 40):
        raise VerificationError("expected source commit must be a lowercase SHA-1")
    if not is_hex(args.expect_status_sha256, 64):
        raise VerificationError("expected status digest must be a lowercase SHA-256")
    if args.expect_targets < 1:
        raise VerificationError("expected target count must be positive")

    manifest = verify_manifest(artifact)
    summary = load_json(artifact / "summary.json")
    if not isinstance(summary, dict):
        raise VerificationError("summary must be an object")
    rows = load_rows(artifact / "per_child.jsonl")
    validate_rows(rows, args.expect_targets)
    verify_command(
        artifact / "command.txt",
        args.expect_source_commit,
        args.expect_status_sha256,
        args.expect_targets,
    )

    require_equal(summary.get("protocol"), PROTOCOL, "protocol")
    require_equal(summary.get("source_commit"), args.expect_source_commit, "source commit")
    require_equal(summary.get("status_per_child_sha256"), args.expect_status_sha256, "status digest")
    inventory = summary.get("journal_inventory")
    if not isinstance(inventory, dict):
        raise VerificationError("journal inventory missing")
    credential_shas = inventory.get("credential_target_journal_shas_skipped")
    if not isinstance(credential_shas, int) or isinstance(credential_shas, bool):
        raise VerificationError("invalid credential journal count")
    computed = recompute(rows, credential_shas)
    for key, expected in computed.items():
        require_equal(summary.get(key), expected, key)
    passed = all(computed["criteria"].values())
    require_equal(summary.get("status"), PASS_STATUS if passed else "INSUFFICIENT_STRUCTURED_FAILURE_MEMORY_SUPPORT", "status")
    require_equal(summary.get("failure_memory_support_claim_allowed"), passed, "support claim flag")
    require_equal(summary.get("contract_method_effect_claim_allowed"), False, "method-effect flag")
    scope = summary.get("scope")
    if not isinstance(scope, dict):
        raise VerificationError("scope missing")
    forbidden_true = (
        "emits_raw_diagnostic_text",
        "reads_code",
        "reads_numeric_grade",
        "reads_pair_orientation",
        "reads_frozen_or_extension_target_nodes",
        "reads_env_or_tar_other_members",
    )
    if any(scope.get(key) is not False for key in forbidden_true):
        raise VerificationError("scope contains a forbidden read or raw-text emission")
    require_equal(scope.get("role"), "train_only", "scope role")
    require_equal(scope.get("gpu"), 0, "GPU count")
    require_equal(scope.get("api_calls"), 0, "API call count")

    return {
        "protocol": "independent-failure-taxonomy-verifier-v1",
        "status": VERIFY_STATUS if passed else "INDEPENDENT_FAILURE_TAXONOMY_VERIFIED_AS_INSUFFICIENT",
        "producer_status": summary["status"],
        "source_commit": args.expect_source_commit,
        "status_per_child_sha256": args.expect_status_sha256,
        "targets": len(rows),
        "structured_category_nodes": computed["structured_category_nodes"],
        "structured_category_share": computed["structured_category_share"],
        "structured_tasks": computed["structured_tasks"],
        "dominant_structured_task_share": computed["dominant_structured_task_share"],
        "credential_target_journal_shas_skipped": credential_shas,
        "artifact_manifest": manifest,
        "producer_imported": False,
        "raw_diagnostic_field_present": False,
    }


def write_atomic(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise VerificationError("verification output already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--artifact", required=True)
    value.add_argument("--expect-source-commit", required=True)
    value.add_argument("--expect-status-sha256", required=True)
    value.add_argument("--expect-targets", type=int, required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        args = parser().parse_args()
        result = verify(args)
        write_atomic(Path(args.output).resolve(), result)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (VerificationError, OSError) as exc:
        print(f"FAILURE_TAXONOMY_VERIFICATION_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
