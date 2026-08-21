#!/usr/bin/env python3
"""Build an exact-field, decision-time-only view of source-choice groups."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterator


ROLES = ("train", "frozen", "extension")
RAW_SCHEMA = "source-choice-group-v2"
MODEL_SCHEMA = "source-choice-decision-group-v2"
CLUSTER_SCHEMA = "source-choice-cluster-manifest-v1"
OPERATOR_MAP = {"draft": "Draft", "improve": "Improve"}
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
BLOCKED_MODEL_FIELDS = {
    "provenance",
    "source_journal_sha256",
    "role",
    "run_id_sha256",
    "parent_id_sha256",
}
EXPECTED_SCOPE = {
    "raw_materialization_bytes_read": True,
    "train_labels_preserved": True,
    "frozen_or_extension_label_vault_read": False,
    "winner_or_group_membership_changed": False,
    "model_training_or_scoring": False,
    "prospective_outcome_used": False,
    "first960_used": False,
    "gpu": 0,
    "api_calls": 0,
    "base_llm_updated": False,
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class DecisionViewError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def require_hash(value: Any, where: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise DecisionViewError(f"invalid SHA-256: {where}")
    return value


def require_text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise DecisionViewError(f"invalid text: {where}")
    return value


def require_int(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DecisionViewError(f"invalid integer: {where}")
    return value


def load_json(path: Path, where: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DecisionViewError(f"invalid JSON: {where}") from exc
    if not isinstance(value, dict):
        raise DecisionViewError(f"JSON root is not an object: {where}")
    return value


def load_protocol(path: Path) -> dict[str, Any]:
    value = load_json(path, "protocol")
    if set(value) != {
        "protocol",
        "source",
        "expected",
        "model_group_fields",
        "train_only_group_fields",
        "model_candidate_fields",
        "cluster_manifest_fields",
        "blocked_model_fields",
        "operator_projection",
        "scope",
    }:
        raise DecisionViewError("protocol top-level fields differ")
    if value["protocol"] != "source-choice-decision-view-v2":
        raise DecisionViewError("protocol name differs")
    if value["scope"] != EXPECTED_SCOPE:
        raise DecisionViewError("protocol scope differs")
    if set(value["model_group_fields"]) != MODEL_BASE_FIELDS:
        raise DecisionViewError("model group allowlist differs")
    if set(value["train_only_group_fields"]) != {"winner_candidate_sha256"}:
        raise DecisionViewError("train-only allowlist differs")
    if set(value["model_candidate_fields"]) != MODEL_CANDIDATE_FIELDS:
        raise DecisionViewError("model candidate allowlist differs")
    if set(value["cluster_manifest_fields"]) != CLUSTER_FIELDS:
        raise DecisionViewError("cluster allowlist differs")
    if set(value["blocked_model_fields"]) != BLOCKED_MODEL_FIELDS:
        raise DecisionViewError("blocked-field list differs")
    projection = value["operator_projection"]
    if (
        not isinstance(projection, dict)
        or set(projection) != {
            "mode",
            "mapping",
            "expected_input_counts_by_role",
            "expected_output_counts_by_role",
            "expected_canonicalized_by_role",
        }
        or projection.get("mode") != "casefold-fixed-enum-v1"
        or projection.get("mapping") != OPERATOR_MAP
        or set(projection.get("expected_input_counts_by_role", {})) != set(ROLES)
        or set(projection.get("expected_output_counts_by_role", {})) != set(ROLES)
        or set(projection.get("expected_canonicalized_by_role", {})) != set(ROLES)
    ):
        raise DecisionViewError("operator projection contract differs")
    return value


def canonical_operator(value: Any) -> str:
    operator = require_text(value, "operator")
    projected = OPERATOR_MAP.get(operator.casefold())
    if projected is None:
        raise DecisionViewError("operator is outside fixed enum")
    return projected


def canonical_rows(path: Path, where: str) -> Iterator[dict[str, Any]]:
    with path.open("rb") as handle:
        for number, line in enumerate(handle, 1):
            if not line.endswith(b"\n"):
                raise DecisionViewError(f"unterminated JSONL row: {where}:{number}")
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DecisionViewError(f"invalid JSONL row: {where}:{number}") from exc
            if not isinstance(value, dict) or canonical(value) + b"\n" != line:
                raise DecisionViewError(f"non-canonical JSONL row: {where}:{number}")
            yield value


def parse_sources(values: list[str]) -> dict[str, Path]:
    output: dict[str, Path] = {}
    for item in values:
        if "=" not in item:
            raise DecisionViewError("source must be ROLE=PATH")
        role, raw_path = item.split("=", 1)
        if role not in ROLES or role in output:
            raise DecisionViewError("source role invalid or repeated")
        output[role] = Path(raw_path).resolve()
    if set(output) != set(ROLES):
        raise DecisionViewError("all three source roles are required")
    return output


def write_json(path: Path, value: Any) -> None:
    if path.exists():
        raise DecisionViewError(f"refusing to overwrite: {path.name}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode() + b"\n")
    os.replace(temporary, path)


def validate_source_receipts(
    protocol: dict[str, Any], summary_path: Path, manifest_path: Path, verification_path: Path
) -> dict[str, Any]:
    source = protocol["source"]
    bindings = {
        "summary_sha256": summary_path,
        "manifest_sha256": manifest_path,
        "independent_verification_sha256": verification_path,
    }
    for key, path in bindings.items():
        if not path.is_file() or sha256_file(path) != source[key]:
            raise DecisionViewError(f"source receipt hash differs: {key}")
    summary = load_json(summary_path, "source summary")
    verification = load_json(verification_path, "source independent verification")
    if (
        summary.get("status") != "SOURCE_CHOICE_BENCHMARK_MATERIALIZED_AND_SEALED"
        or summary.get("source_commit") != source["materialization_commit"]
        or verification.get("status")
        != "INDEPENDENT_SOURCE_CHOICE_BENCHMARK_MATERIALIZATION_VERIFIED"
        or verification.get("producer_imported") is not False
        or verification.get("source_commit") != source["materialization_commit"]
        or verification.get("public_summary_sha256") != source["summary_sha256"]
        or verification.get("public_manifest_sha256") != source["manifest_sha256"]
    ):
        raise DecisionViewError("source receipt semantic binding differs")
    expected = protocol["expected"]
    if (
        summary.get("groups") != expected["groups"]
        or summary.get("candidate_slots") != expected["candidate_slots"]
        or summary.get("groups_by_role") != expected["groups_by_role"]
        or summary.get("candidate_slots_by_role") != expected["candidate_slots_by_role"]
        or summary.get("frozen_public_winner_fields") != 0
        or summary.get("extension_public_winner_fields") != 0
        or summary.get("frozen_labels_used_for_model_or_scoring") is not False
    ):
        raise DecisionViewError("source summary census differs")
    return summary


def build(arguments: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(arguments.protocol).resolve()
    summary_path = Path(arguments.source_summary).resolve()
    manifest_path = Path(arguments.source_manifest).resolve()
    verification_path = Path(arguments.source_verification).resolve()
    output = Path(arguments.output).resolve()
    if output.exists():
        raise DecisionViewError("output directory already exists")
    protocol = load_protocol(protocol_path)
    source_summary = validate_source_receipts(
        protocol, summary_path, manifest_path, verification_path
    )
    sources = parse_sources(arguments.source)
    source_keys = {
        "train": "train_groups_sha256",
        "frozen": "frozen_inputs_sha256",
        "extension": "extension_inputs_sha256",
    }
    for role, path in sources.items():
        if not path.is_file() or sha256_file(path) != protocol["source"][source_keys[role]]:
            raise DecisionViewError(f"source data hash differs: {role}")

    output.mkdir(parents=True)
    group_counts: collections.Counter[str] = collections.Counter()
    candidate_counts: collections.Counter[str] = collections.Counter()
    winner_counts: collections.Counter[str] = collections.Counter()
    removed_counts: collections.Counter[str] = collections.Counter()
    operator_input_counts = {role: collections.Counter() for role in ROLES}
    operator_output_counts = {role: collections.Counter() for role in ROLES}
    operator_canonicalized_counts: collections.Counter[str] = collections.Counter()
    task_names: set[str] = set()
    group_ids: set[str] = set()
    candidate_ids: set[str] = set()
    model_paths = {role: output / f"{role}_model.jsonl" for role in ROLES}
    cluster_path = output / "cluster_manifest.jsonl"

    with cluster_path.open("xb") as cluster_handle:
        for role in ROLES:
            with model_paths[role].open("xb") as model_handle:
                for number, raw in enumerate(canonical_rows(sources[role], role), 1):
                    expected_raw_fields = set(RAW_BASE_FIELDS)
                    if role == "train":
                        expected_raw_fields.add("winner_candidate_sha256")
                    if set(raw) != expected_raw_fields or raw.get("schema_version") != RAW_SCHEMA:
                        raise DecisionViewError(f"raw group fields/schema differ: {role}:{number}")
                    if raw.get("role") != role:
                        raise DecisionViewError(f"raw role differs: {role}:{number}")
                    group_id = require_hash(raw.get("group_id"), "group")
                    run_id = require_hash(raw.get("run_id_sha256"), "run")
                    parent_id = require_hash(raw.get("parent_id_sha256"), "parent")
                    task = require_text(raw.get("task"), "task")
                    source_size = require_int(raw.get("source_size"), "source size")
                    candidates = raw.get("candidates")
                    if (
                        group_id in group_ids
                        or not isinstance(candidates, list)
                        or source_size < 2
                        or len(candidates) != source_size
                    ):
                        raise DecisionViewError(f"raw group closure differs: {role}:{number}")
                    group_ids.add(group_id)
                    task_names.add(task)
                    projected_candidates: list[dict[str, Any]] = []
                    current_ids: list[str] = []
                    for candidate_number, candidate in enumerate(candidates, 1):
                        if not isinstance(candidate, dict) or set(candidate) != RAW_CANDIDATE_FIELDS:
                            raise DecisionViewError(
                                f"raw candidate fields differ: {role}:{number}:{candidate_number}"
                            )
                        candidate_id = require_hash(candidate.get("candidate_id_sha256"), "candidate")
                        code = require_text(candidate.get("code"), "code")
                        code_hash = require_hash(candidate.get("code_sha256"), "code")
                        raw_operator = require_text(candidate.get("operator"), "operator")
                        operator = canonical_operator(raw_operator)
                        step = require_int(candidate.get("step"), "step")
                        depth = require_int(candidate.get("depth"), "depth")
                        provenance = candidate.get("provenance")
                        journal_hash = candidate.get("source_journal_sha256")
                        if (
                            candidate_id in candidate_ids
                            or sha256_bytes(code.encode("utf-8")) != code_hash
                            or provenance not in {"card", "journal_recovered"}
                            or (provenance == "card" and journal_hash is not None)
                            or (
                                provenance == "journal_recovered"
                                and require_hash(journal_hash, "journal") != journal_hash
                            )
                        ):
                            raise DecisionViewError(
                                f"raw candidate closure differs: {role}:{number}:{candidate_number}"
                            )
                        candidate_ids.add(candidate_id)
                        current_ids.append(candidate_id)
                        operator_input_counts[role][raw_operator] += 1
                        operator_output_counts[role][operator] += 1
                        operator_canonicalized_counts[role] += int(raw_operator != operator)
                        projected = {
                            "candidate_id_sha256": candidate_id,
                            "code": code,
                            "code_sha256": code_hash,
                            "operator": operator,
                            "step": step,
                            "depth": depth,
                        }
                        if set(projected) != MODEL_CANDIDATE_FIELDS:
                            raise DecisionViewError("internal candidate projection differs")
                        projected_candidates.append(projected)
                        removed_counts["provenance"] += 1
                        removed_counts["source_journal_sha256"] += 1
                    if current_ids != sorted(current_ids) or len(current_ids) != len(set(current_ids)):
                        raise DecisionViewError(f"candidate identity/order differs: {role}:{number}")
                    model = {
                        "schema_version": MODEL_SCHEMA,
                        "group_id": group_id,
                        "task": task,
                        "source_size": source_size,
                        "candidates": projected_candidates,
                    }
                    if role == "train":
                        winner = require_hash(raw.get("winner_candidate_sha256"), "winner")
                        if winner not in set(current_ids):
                            raise DecisionViewError(f"train winner closure differs: {number}")
                        model["winner_candidate_sha256"] = winner
                        winner_counts[role] += 1
                    if set(model) != MODEL_BASE_FIELDS | (
                        {"winner_candidate_sha256"} if role == "train" else set()
                    ):
                        raise DecisionViewError("internal model group projection differs")
                    cluster = {
                        "schema_version": CLUSTER_SCHEMA,
                        "group_id": group_id,
                        "role": role,
                        "task": task,
                        "run_id_sha256": run_id,
                        "parent_id_sha256": parent_id,
                        "source_size": source_size,
                    }
                    if set(cluster) != CLUSTER_FIELDS:
                        raise DecisionViewError("internal cluster projection differs")
                    model_handle.write(canonical(model) + b"\n")
                    cluster_handle.write(canonical(cluster) + b"\n")
                    group_counts[role] += 1
                    candidate_counts[role] += source_size

    expected = protocol["expected"]
    input_operator_counts = {
        role: dict(sorted(operator_input_counts[role].items())) for role in ROLES
    }
    output_operator_counts = {
        role: dict(sorted(operator_output_counts[role].items())) for role in ROLES
    }
    canonicalized_operator_counts = {
        role: operator_canonicalized_counts[role] for role in ROLES
    }
    operator_projection = protocol["operator_projection"]
    if (
        sum(group_counts.values()) != expected["groups"]
        or sum(candidate_counts.values()) != expected["candidate_slots"]
        or dict(group_counts) != expected["groups_by_role"]
        or dict(candidate_counts) != expected["candidate_slots_by_role"]
        or len(task_names) != expected["tasks"]
        or len(group_ids) != expected["groups"]
        or len(candidate_ids) != expected["candidate_slots"]
        or winner_counts["train"] != expected["train_winner_fields"]
        or winner_counts["frozen"] != expected["frozen_winner_fields"]
        or winner_counts["extension"] != expected["extension_winner_fields"]
        or dict(removed_counts) != expected["blocked_candidate_fields_removed"]
        or input_operator_counts != operator_projection["expected_input_counts_by_role"]
        or output_operator_counts != operator_projection["expected_output_counts_by_role"]
        or canonicalized_operator_counts
        != operator_projection["expected_canonicalized_by_role"]
    ):
        raise DecisionViewError("projected census differs from protocol")

    output_hashes = {path.name: sha256_file(path) for path in (*model_paths.values(), cluster_path)}
    summary = {
        "protocol": protocol["protocol"],
        "status": "SOURCE_CHOICE_DECISION_VIEW_V2_READY",
        "source_materialization_commit": protocol["source"]["materialization_commit"],
        "source_summary_sha256": protocol["source"]["summary_sha256"],
        "groups": sum(group_counts.values()),
        "candidate_slots": sum(candidate_counts.values()),
        "tasks": len(task_names),
        "groups_by_role": dict(group_counts),
        "candidate_slots_by_role": dict(candidate_counts),
        "winner_fields_by_role": {role: winner_counts[role] for role in ROLES},
        "blocked_candidate_fields_removed": dict(removed_counts),
        "operator_input_counts_by_role": input_operator_counts,
        "operator_output_counts_by_role": output_operator_counts,
        "operator_canonicalized_by_role": canonicalized_operator_counts,
        "operator_values_outside_fixed_enum": 0,
        "blocked_fields_present_in_model_objects": 0,
        "model_group_fields": protocol["model_group_fields"],
        "train_only_group_fields": protocol["train_only_group_fields"],
        "model_candidate_fields": protocol["model_candidate_fields"],
        "cluster_manifest_fields": protocol["cluster_manifest_fields"],
        "cluster_metadata_exposed_to_model": False,
        "frozen_or_extension_label_vault_read": False,
        "sealed_vault_sha256_opaque": source_summary["sealed_vault_outputs_opaque"],
        "outputs": output_hashes,
        "scope": protocol["scope"],
        "predictor_or_search_utility_claim_allowed": False,
    }
    write_json(output / "summary.json", summary)
    write_json(output / "sha256_manifest.json", output_hashes)
    return summary


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--protocol", required=True)
    value.add_argument("--source-summary", required=True)
    value.add_argument("--source-manifest", required=True)
    value.add_argument("--source-verification", required=True)
    value.add_argument("--source", action="append", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        result = build(parser().parse_args())
        print(
            f"{result['status']} groups={result['groups']} candidates={result['candidate_slots']}"
        )
        return 0
    except DecisionViewError as exc:
        print(f"SOURCE_CHOICE_DECISION_VIEW_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
