#!/usr/bin/env python3
"""Independent verifier for the exact-field source-choice decision view."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys
from itertools import zip_longest
from pathlib import Path
from typing import Any, Iterator


ROLES = ("train", "frozen", "extension")
RAW_SCHEMA = "source-choice-group-v2"
MODEL_SCHEMA = "source-choice-decision-group-v1"
CLUSTER_SCHEMA = "source-choice-cluster-manifest-v1"
RAW_BASE_FIELDS = {
    "schema_version",
    "group_id",
    "role",
    "task",
    "run_id_sha256",
    "parent_id_sha256",
    "source_size",
    "candidates",
}
RAW_CANDIDATE_FIELDS = {
    "candidate_id_sha256",
    "code",
    "code_sha256",
    "operator",
    "step",
    "depth",
    "provenance",
    "source_journal_sha256",
}
MODEL_BASE_FIELDS = {"schema_version", "group_id", "task", "source_size", "candidates"}
MODEL_CANDIDATE_FIELDS = {
    "candidate_id_sha256",
    "code",
    "code_sha256",
    "operator",
    "step",
    "depth",
}
CLUSTER_FIELDS = {
    "schema_version",
    "group_id",
    "role",
    "task",
    "run_id_sha256",
    "parent_id_sha256",
    "source_size",
}
BLOCKED = {"provenance", "source_journal_sha256", "role", "run_id_sha256", "parent_id_sha256"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class VerificationError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def valid_hash(value: Any, where: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise VerificationError(f"invalid hash: {where}")
    return value


def valid_text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise VerificationError(f"invalid text: {where}")
    return value


def valid_int(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise VerificationError(f"invalid integer: {where}")
    return value


def json_object(path: Path, where: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid JSON: {where}") from exc
    if not isinstance(value, dict):
        raise VerificationError(f"non-object JSON: {where}")
    return value


def jsonl(path: Path, where: str) -> Iterator[dict[str, Any]]:
    with path.open("rb") as handle:
        for number, line in enumerate(handle, 1):
            if not line.endswith(b"\n"):
                raise VerificationError(f"unterminated row: {where}:{number}")
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise VerificationError(f"invalid row: {where}:{number}") from exc
            if not isinstance(value, dict) or canonical(value) + b"\n" != line:
                raise VerificationError(f"non-canonical row: {where}:{number}")
            yield value


def source_map(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for item in values:
        if "=" not in item:
            raise VerificationError("source must be ROLE=PATH")
        role, path = item.split("=", 1)
        if role not in ROLES or role in result:
            raise VerificationError("source role invalid")
        result[role] = Path(path).resolve()
    if set(result) != set(ROLES):
        raise VerificationError("source role coverage differs")
    return result


def atomic_json(path: Path, value: Any) -> None:
    if path.exists():
        raise VerificationError("verification output already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode() + b"\n")
    os.replace(temporary, path)


def verify(arguments: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(arguments.protocol).resolve()
    source_summary_path = Path(arguments.source_summary).resolve()
    source_manifest_path = Path(arguments.source_manifest).resolve()
    source_verification_path = Path(arguments.source_verification).resolve()
    view = Path(arguments.view).resolve()
    sources = source_map(arguments.source)
    protocol = json_object(protocol_path, "protocol")
    if (
        protocol.get("protocol") != "source-choice-decision-view-v1"
        or set(protocol.get("model_group_fields", [])) != MODEL_BASE_FIELDS
        or set(protocol.get("train_only_group_fields", [])) != {"winner_candidate_sha256"}
        or set(protocol.get("model_candidate_fields", [])) != MODEL_CANDIDATE_FIELDS
        or set(protocol.get("cluster_manifest_fields", [])) != CLUSTER_FIELDS
        or set(protocol.get("blocked_model_fields", [])) != BLOCKED
        or protocol.get("scope", {}).get("frozen_or_extension_label_vault_read") is not False
    ):
        raise VerificationError("protocol contract differs")
    source = protocol["source"]
    receipt_bindings = {
        source_summary_path: source["summary_sha256"],
        source_manifest_path: source["manifest_sha256"],
        source_verification_path: source["independent_verification_sha256"],
    }
    for path, expected_hash in receipt_bindings.items():
        if not path.is_file() or digest(path) != expected_hash:
            raise VerificationError("source receipt hash differs")
    source_summary = json_object(source_summary_path, "source summary")
    source_verification = json_object(source_verification_path, "source verification")
    if (
        source_summary.get("status") != "SOURCE_CHOICE_BENCHMARK_MATERIALIZED_AND_SEALED"
        or source_summary.get("source_commit") != source["materialization_commit"]
        or source_verification.get("status")
        != "INDEPENDENT_SOURCE_CHOICE_BENCHMARK_MATERIALIZATION_VERIFIED"
        or source_verification.get("producer_imported") is not False
    ):
        raise VerificationError("source receipt semantics differ")
    source_hash_keys = {
        "train": "train_groups_sha256",
        "frozen": "frozen_inputs_sha256",
        "extension": "extension_inputs_sha256",
    }
    for role, path in sources.items():
        if not path.is_file() or digest(path) != source[source_hash_keys[role]]:
            raise VerificationError(f"source data hash differs: {role}")

    required_view_files = {
        *(f"{role}_model.jsonl" for role in ROLES),
        "cluster_manifest.jsonl",
        "summary.json",
        "sha256_manifest.json",
    }
    if not view.is_dir() or {path.name for path in view.iterdir()} != required_view_files:
        raise VerificationError("view file set differs")
    cluster_iter = iter(jsonl(view / "cluster_manifest.jsonl", "cluster"))
    group_counts: collections.Counter[str] = collections.Counter()
    candidate_counts: collections.Counter[str] = collections.Counter()
    removed_counts: collections.Counter[str] = collections.Counter()
    winner_counts: collections.Counter[str] = collections.Counter()
    groups_seen: set[str] = set()
    candidates_seen: set[str] = set()
    tasks: set[str] = set()

    for role in ROLES:
        raw_iter = jsonl(sources[role], f"source {role}")
        model_iter = jsonl(view / f"{role}_model.jsonl", f"model {role}")
        for number, pair in enumerate(zip_longest(raw_iter, model_iter), 1):
            raw, model = pair
            if raw is None or model is None:
                raise VerificationError(f"row count differs: {role}")
            raw_fields = set(RAW_BASE_FIELDS) | (
                {"winner_candidate_sha256"} if role == "train" else set()
            )
            model_fields = set(MODEL_BASE_FIELDS) | (
                {"winner_candidate_sha256"} if role == "train" else set()
            )
            if (
                set(raw) != raw_fields
                or raw.get("schema_version") != RAW_SCHEMA
                or raw.get("role") != role
                or set(model) != model_fields
                or model.get("schema_version") != MODEL_SCHEMA
                or BLOCKED & set(model)
            ):
                raise VerificationError(f"group fields differ: {role}:{number}")
            group_id = valid_hash(raw.get("group_id"), "group")
            run_id = valid_hash(raw.get("run_id_sha256"), "run")
            parent_id = valid_hash(raw.get("parent_id_sha256"), "parent")
            task = valid_text(raw.get("task"), "task")
            source_size = valid_int(raw.get("source_size"), "source size")
            raw_candidates = raw.get("candidates")
            model_candidates = model.get("candidates")
            if (
                group_id in groups_seen
                or source_size < 2
                or not isinstance(raw_candidates, list)
                or not isinstance(model_candidates, list)
                or len(raw_candidates) != source_size
                or len(model_candidates) != source_size
                or model.get("group_id") != group_id
                or model.get("task") != task
                or model.get("source_size") != source_size
            ):
                raise VerificationError(f"group closure differs: {role}:{number}")
            groups_seen.add(group_id)
            tasks.add(task)
            current_ids: list[str] = []
            for candidate_number, (raw_candidate, model_candidate) in enumerate(
                zip(raw_candidates, model_candidates), 1
            ):
                if (
                    not isinstance(raw_candidate, dict)
                    or set(raw_candidate) != RAW_CANDIDATE_FIELDS
                    or not isinstance(model_candidate, dict)
                    or set(model_candidate) != MODEL_CANDIDATE_FIELDS
                    or BLOCKED & set(model_candidate)
                ):
                    raise VerificationError(
                        f"candidate fields differ: {role}:{number}:{candidate_number}"
                    )
                expected_candidate = {
                    key: raw_candidate[key] for key in MODEL_CANDIDATE_FIELDS
                }
                if model_candidate != expected_candidate:
                    raise VerificationError(
                        f"candidate projection differs: {role}:{number}:{candidate_number}"
                    )
                candidate_id = valid_hash(raw_candidate.get("candidate_id_sha256"), "candidate")
                code = valid_text(raw_candidate.get("code"), "code")
                code_hash = valid_hash(raw_candidate.get("code_sha256"), "code")
                if (
                    candidate_id in candidates_seen
                    or hashlib.sha256(code.encode("utf-8")).hexdigest() != code_hash
                ):
                    raise VerificationError("candidate identity/code closure differs")
                candidates_seen.add(candidate_id)
                current_ids.append(candidate_id)
                removed_counts["provenance"] += 1
                removed_counts["source_journal_sha256"] += 1
            if current_ids != sorted(current_ids) or len(current_ids) != len(set(current_ids)):
                raise VerificationError("candidate order differs")
            if role == "train":
                winner = valid_hash(raw.get("winner_candidate_sha256"), "winner")
                if winner not in set(current_ids) or model.get("winner_candidate_sha256") != winner:
                    raise VerificationError("train winner projection differs")
                winner_counts[role] += 1
            cluster = next(cluster_iter, None)
            expected_cluster = {
                "schema_version": CLUSTER_SCHEMA,
                "group_id": group_id,
                "role": role,
                "task": task,
                "run_id_sha256": run_id,
                "parent_id_sha256": parent_id,
                "source_size": source_size,
            }
            if cluster != expected_cluster or set(cluster or {}) != CLUSTER_FIELDS:
                raise VerificationError(f"cluster projection differs: {role}:{number}")
            group_counts[role] += 1
            candidate_counts[role] += source_size
    if next(cluster_iter, None) is not None:
        raise VerificationError("cluster manifest has extra rows")

    expected = protocol["expected"]
    if (
        sum(group_counts.values()) != expected["groups"]
        or sum(candidate_counts.values()) != expected["candidate_slots"]
        or dict(group_counts) != expected["groups_by_role"]
        or dict(candidate_counts) != expected["candidate_slots_by_role"]
        or len(tasks) != expected["tasks"]
        or len(groups_seen) != expected["groups"]
        or len(candidates_seen) != expected["candidate_slots"]
        or winner_counts["train"] != expected["train_winner_fields"]
        or winner_counts["frozen"] != expected["frozen_winner_fields"]
        or winner_counts["extension"] != expected["extension_winner_fields"]
        or dict(removed_counts) != expected["blocked_candidate_fields_removed"]
    ):
        raise VerificationError("verified census differs")

    output_paths = {
        **{f"{role}_model.jsonl": view / f"{role}_model.jsonl" for role in ROLES},
        "cluster_manifest.jsonl": view / "cluster_manifest.jsonl",
    }
    output_hashes = {name: digest(path) for name, path in output_paths.items()}
    manifest = json_object(view / "sha256_manifest.json", "view manifest")
    summary = json_object(view / "summary.json", "view summary")
    if (
        manifest != output_hashes
        or summary.get("status") != "SOURCE_CHOICE_DECISION_VIEW_READY"
        or summary.get("outputs") != output_hashes
        or summary.get("groups") != expected["groups"]
        or summary.get("candidate_slots") != expected["candidate_slots"]
        or summary.get("blocked_fields_present_in_model_objects") != 0
        or summary.get("blocked_candidate_fields_removed")
        != expected["blocked_candidate_fields_removed"]
        or summary.get("frozen_or_extension_label_vault_read") is not False
        or summary.get("cluster_metadata_exposed_to_model") is not False
    ):
        raise VerificationError("summary/manifest differs")
    return {
        "protocol": "independent-source-choice-decision-view-verifier-v1",
        "status": "INDEPENDENT_SOURCE_CHOICE_DECISION_VIEW_VERIFIED",
        "producer_imported": False,
        "source_materialization_commit": source["materialization_commit"],
        "groups": expected["groups"],
        "candidate_slots": expected["candidate_slots"],
        "blocked_candidate_fields_removed": dict(removed_counts),
        "blocked_fields_present_in_model_objects": 0,
        "frozen_or_extension_label_vault_read": False,
        "view_summary_sha256": digest(view / "summary.json"),
        "view_manifest_sha256": digest(view / "sha256_manifest.json"),
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--protocol", required=True)
    value.add_argument("--source-summary", required=True)
    value.add_argument("--source-manifest", required=True)
    value.add_argument("--source-verification", required=True)
    value.add_argument("--source", action="append", required=True)
    value.add_argument("--view", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        arguments = parser().parse_args()
        result = verify(arguments)
        atomic_json(Path(arguments.output).resolve(), result)
        print(result["status"])
        return 0
    except VerificationError as exc:
        print(f"SOURCE_CHOICE_DECISION_VIEW_VERIFICATION_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
