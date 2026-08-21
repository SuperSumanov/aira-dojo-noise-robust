#!/usr/bin/env python3
"""Measure source-winner answerability from published and validity relations."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence


PROTOCOL = "source-decision-answerability-v1"
STATUS_PASS = "VERIFIED_MATERIAL_SOURCE_WINNER_ANSWERABILITY_RECOVERY"
STATUS_BELOW = "SOURCE_WINNER_ANSWERABILITY_BELOW_MATERIAL_GATE"
STATUS_SUPPORT = "INSUFFICIENT_TASK_SUPPORT_FOR_SOURCE_WINNER_ANSWERABILITY"
ROLES = ("train", "frozen", "extension")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-(?:ws-)?[A-Za-z0-9._-]{16,}|"
    rb"hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    rb"AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|"
    rb"Bearer\s+[A-Za-z0-9._~-]{20,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
UPSTREAM_FIELDS = (
    "role",
    "task",
    "run_id",
    "parent",
    "pair_rows",
    "unique_edges",
    "published_endpoint_count",
    "declared_set_size",
    "raw_card_child_count",
    "finite_card_child_count",
    "source_declared_size",
    "source_size_consistent",
    "source_size_not_smaller_than_raw",
    "raw_context_consistent",
    "endpoints_all_finite",
    "endpoint_fidelity",
    "declared_matches_finite",
    "finite_endpoint_coverage",
    "pair_graph_coverage_over_finite",
    "raw_source_retention",
    "finite_source_retention",
    "raw_equals_source",
    "finite_equals_source",
    "parent_card_present",
    "parent_context_consistent",
    "parent_children_declared_count",
    "parent_children_contains_raw",
    "source_size_gt_five",
)
PARENT_OUTPUT_FIELDS = (
    "role",
    "task",
    "run_id_sha256",
    "parent_sha256",
    "source_children",
    "finite_children",
    "source_identity_available",
    "missing_identity_children",
    "certified_invalid_children",
    "unknown_source_children",
    "published_direct_relations",
    "status_direct_relations",
    "execution_only_direct_relations",
    "published_transitive_relations",
    "status_transitive_relations",
    "execution_only_transitive_relations",
    "published_top_set_size",
    "status_top_set_size",
    "execution_only_top_set_size",
    "published_winner_identified",
    "status_winner_identified",
    "execution_only_winner_identified",
    "newly_identified_by_status",
    "newly_identified_execution_only",
)
AGGREGATE_FIELDS = (
    "stratum_type",
    "stratum",
    "parents",
    "runs",
    "source_pair_capacity",
    "source_identity_available_parents",
    "published_direct_relations",
    "status_direct_relations",
    "execution_only_direct_relations",
    "published_transitive_relations",
    "status_transitive_relations",
    "execution_only_transitive_relations",
    "published_winners",
    "status_winners",
    "execution_only_winners",
    "newly_identified_by_status",
    "newly_identified_execution_only",
    "published_winner_rate",
    "status_winner_rate",
    "execution_only_winner_rate",
    "status_winner_rate_gain",
    "execution_only_winner_rate_gain",
    "status_unanswered_gap_recovery",
    "execution_only_unanswered_gap_recovery",
    "published_relation_coverage",
    "status_direct_relation_coverage",
    "status_transitive_relation_coverage",
    "execution_only_transitive_relation_coverage",
)


class AnswerabilityError(RuntimeError):
    pass


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def normalized_lf_digest(path: Path) -> str:
    blob = path.read_bytes()
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AnswerabilityError(f"input is not UTF-8: {path.name}") from exc
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def scan_file(path: Path) -> None:
    overlap = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            payload = overlap + chunk
            if CREDENTIAL.search(payload):
                raise AnswerabilityError(f"credential-shaped bytes refused in {path.name}")
            overlap = payload[-256:]


def comb2(value: int) -> int:
    return value * (value - 1) // 2


def ratio(numerator: int | float, denominator: int | float) -> float | None:
    return numerator / denominator if denominator else None


def required_text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise AnswerabilityError(f"invalid text at {where}")
    return value


def parse_bool(value: Any, where: str) -> bool:
    if value is True or value == "True":
        return True
    if value is False or value == "False":
        return False
    raise AnswerabilityError(f"invalid boolean at {where}")


def parse_int(value: Any, where: str) -> int:
    if isinstance(value, bool):
        raise AnswerabilityError(f"invalid integer at {where}")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise AnswerabilityError(f"invalid integer at {where}") from exc
    if result < 0:
        raise AnswerabilityError(f"negative integer at {where}")
    return result


def load_protocol(path: Path) -> dict[str, Any]:
    scan_file(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AnswerabilityError("invalid protocol JSON") from exc
    if not isinstance(value, dict) or value.get("protocol") != PROTOCOL:
        raise AnswerabilityError("invalid protocol identity")
    for field in ("input_per_parent_sha256", "input_identity_sha256", "input_status_edges_sha256"):
        if not isinstance(value.get(field), str) or not SHA256.fullmatch(value[field]):
            raise AnswerabilityError(f"invalid protocol digest: {field}")
    pair_inputs = value.get("pair_inputs")
    if not isinstance(pair_inputs, dict) or set(pair_inputs) != set(ROLES):
        raise AnswerabilityError("invalid pair input mapping")
    for role in ROLES:
        item = pair_inputs[role]
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("sha256_normalized_lf"), str)
            or not SHA256.fullmatch(item["sha256_normalized_lf"])
        ):
            raise AnswerabilityError(f"invalid pair digest for {role}")
    for field in (
        "expected_parent_rows",
        "expected_identity_rows",
        "expected_published_edges",
        "expected_validity_edges",
        "expected_certified_invalid_children",
        "material_min_newly_identified_parents",
        "minimum_supported_tasks",
        "minimum_task_source_pair_capacity",
        "minimum_tasks_with_positive_gain",
    ):
        item = value.get(field)
        if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
            raise AnswerabilityError(f"invalid protocol integer: {field}")
    for field in (
        "material_min_overall_winner_rate_gain",
        "material_min_train_winner_rate_gain",
        "material_min_frozen_winner_rate_gain",
        "material_min_status_winner_rate",
        "maximum_dominant_added_winner_task_share",
    ):
        item = value.get(field)
        if (
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not math.isfinite(float(item))
            or not 0 <= float(item) <= 1
        ):
            raise AnswerabilityError(f"invalid protocol fraction: {field}")
    roles = value.get("expected_role_parent_counts")
    pair_roles = value.get("expected_role_pair_counts")
    pair_null_runs = value.get("expected_role_pair_null_run_counts")
    if (
        not isinstance(roles, dict)
        or set(roles) != set(ROLES)
        or any(isinstance(count, bool) or not isinstance(count, int) or count < 0 for count in roles.values())
        or sum(roles.values()) != value["expected_parent_rows"]
    ):
        raise AnswerabilityError("invalid role parent counts")
    if (
        not isinstance(pair_roles, dict)
        or set(pair_roles) != set(ROLES)
        or any(isinstance(count, bool) or not isinstance(count, int) or count < 0 for count in pair_roles.values())
        or sum(pair_roles.values()) != value["expected_published_edges"]
    ):
        raise AnswerabilityError("invalid role pair counts")
    if (
        not isinstance(pair_null_runs, dict)
        or set(pair_null_runs) != set(ROLES)
        or any(
            isinstance(count, bool) or not isinstance(count, int) or count < 0
            for count in pair_null_runs.values()
        )
        or any(pair_null_runs[role] > pair_roles[role] for role in ROLES)
    ):
        raise AnswerabilityError("invalid role pair null-run counts")
    if value.get("certifiable_categories") != ["EXECUTION_ERROR", "OFFICIAL_GRADE_ABSENT"]:
        raise AnswerabilityError("certifiable category contract changed")
    return value


def load_parents(path: Path, protocol: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    if digest(path) != protocol["input_per_parent_sha256"]:
        raise AnswerabilityError("per-parent input SHA mismatch")
    scan_file(path)
    parents: dict[tuple[str, str], dict[str, Any]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != UPSTREAM_FIELDS:
            raise AnswerabilityError("per-parent input fields mismatch")
        for line_number, raw in enumerate(reader, 2):
            role = required_text(raw.get("role"), f"parent row {line_number}:role")
            task = required_text(raw.get("task"), f"parent row {line_number}:task")
            run_id = required_text(raw.get("run_id"), f"parent row {line_number}:run")
            parent = required_text(raw.get("parent"), f"parent row {line_number}:parent")
            if role not in ROLES or (role, parent) in parents:
                raise AnswerabilityError(f"invalid/duplicate parent at row {line_number}")
            source = parse_int(raw.get("source_declared_size"), f"parent row {line_number}:source")
            finite = parse_int(raw.get("finite_card_child_count"), f"parent row {line_number}:finite")
            endpoints = parse_int(raw.get("published_endpoint_count"), f"parent row {line_number}:endpoints")
            edges = parse_int(raw.get("unique_edges"), f"parent row {line_number}:edges")
            pair_rows = parse_int(raw.get("pair_rows"), f"parent row {line_number}:pair_rows")
            if source < 2 or not 2 <= finite == endpoints <= source:
                raise AnswerabilityError(f"invalid source/finite funnel at row {line_number}")
            if pair_rows != edges or edges > comb2(finite):
                raise AnswerabilityError(f"pair edge accounting mismatch at row {line_number}")
            for field in (
                "source_size_consistent",
                "source_size_not_smaller_than_raw",
                "raw_context_consistent",
                "endpoints_all_finite",
                "endpoint_fidelity",
                "declared_matches_finite",
                "parent_context_consistent",
            ):
                if not parse_bool(raw.get(field), f"parent row {line_number}:{field}"):
                    raise AnswerabilityError(f"upstream structural gate failed at row {line_number}")
            parents[(role, parent)] = {
                "role": role,
                "task": task,
                "run_id": run_id,
                "parent": parent,
                "source_children": source,
                "finite_children": finite,
                "published_unique_edges": edges,
            }
    if len(parents) != protocol["expected_parent_rows"]:
        raise AnswerabilityError("parent row count mismatch")
    role_counts = collections.Counter(row["role"] for row in parents.values())
    if {role: role_counts[role] for role in ROLES} != protocol["expected_role_parent_counts"]:
        raise AnswerabilityError("parent role count mismatch")
    return parents


def load_identity(
    path: Path,
    protocol: dict[str, Any],
    parents: dict[tuple[str, str], dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    if digest(path) != protocol["input_identity_sha256"]:
        raise AnswerabilityError("identity registry SHA mismatch")
    scan_file(path)
    identities: dict[tuple[str, str], dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AnswerabilityError(f"invalid identity JSON at line {line_number}") from exc
            if not isinstance(raw, dict):
                raise AnswerabilityError(f"identity row is not an object at line {line_number}")
            role = required_text(raw.get("role"), f"identity line {line_number}:role")
            parent = required_text(raw.get("parent"), f"identity line {line_number}:parent")
            key = (role, parent)
            if key not in parents or key in identities:
                raise AnswerabilityError(f"identity parent mismatch at line {line_number}")
            source = parse_int(raw.get("source_declared_size"), f"identity line {line_number}:source")
            retained = parse_int(raw.get("retained_child_count"), f"identity line {line_number}:retained")
            incomplete = parse_bool(raw.get("source_incomplete"), f"identity line {line_number}:incomplete")
            exact = parse_bool(raw.get("exact_identity_recoverable"), f"identity line {line_number}:exact")
            missing_count = parse_int(raw.get("missing_identity_count"), f"identity line {line_number}:missing_count")
            missing = raw.get("missing_child_ids")
            if not isinstance(missing, list) or any(not isinstance(child, str) or not child for child in missing):
                raise AnswerabilityError(f"invalid missing identity list at line {line_number}")
            if len(missing) != len(set(missing)) or len(missing) != missing_count:
                raise AnswerabilityError(f"missing identity count mismatch at line {line_number}")
            parent_row = parents[key]
            if source != parent_row["source_children"] or retained != parent_row["finite_children"]:
                raise AnswerabilityError(f"identity/parent count mismatch at line {line_number}")
            if incomplete != (source > retained):
                raise AnswerabilityError(f"incomplete flag mismatch at line {line_number}")
            if incomplete and exact and missing_count != source - retained:
                raise AnswerabilityError(f"exact missing identity mismatch at line {line_number}")
            if incomplete and not exact and missing_count != 0:
                raise AnswerabilityError(f"unavailable identity was partially promoted at line {line_number}")
            if not incomplete and missing_count != 0:
                raise AnswerabilityError(f"complete parent has missing identities at line {line_number}")
            identities[key] = {
                "source_identity_available": (not incomplete) or exact,
                "missing_child_ids": set(missing),
                "source_incomplete": incomplete,
                "exact_identity_recoverable": exact,
            }
    if len(identities) != protocol["expected_identity_rows"] or set(identities) != set(parents):
        raise AnswerabilityError("identity registry parent closure mismatch")
    return identities


def parse_pair_arguments(values: Sequence[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise AnswerabilityError("pair input must be ROLE=PATH")
        role, raw_path = value.split("=", 1)
        if role not in ROLES or role in result:
            raise AnswerabilityError("invalid/duplicate pair role")
        path = Path(raw_path).resolve()
        if not path.is_file():
            raise AnswerabilityError(f"pair input missing for {role}")
        result[role] = path
    if set(result) != set(ROLES):
        raise AnswerabilityError("pair roles incomplete")
    return result


def load_pairs(
    paths: dict[str, Path],
    protocol: dict[str, Any],
    parents: dict[tuple[str, str], dict[str, Any]],
) -> dict[tuple[str, str], dict[str, set[Any]]]:
    grouped: dict[tuple[str, str], dict[str, set[Any]]] = {
        key: {"nodes": set(), "edges": set(), "unordered": set()} for key in parents
    }
    global_unordered: set[tuple[str, str, str, str]] = set()
    role_counts: collections.Counter[str] = collections.Counter()
    null_run_counts: collections.Counter[str] = collections.Counter()
    for role in ROLES:
        path = paths[role]
        expected = protocol["pair_inputs"][role]["sha256_normalized_lf"]
        if normalized_lf_digest(path) != expected:
            raise AnswerabilityError(f"pair input SHA mismatch for {role}")
        scan_file(path)
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise AnswerabilityError(f"invalid pair JSON {role}:{line_number}") from exc
                if not isinstance(raw, dict):
                    raise AnswerabilityError(f"pair row is not an object {role}:{line_number}")
                task = required_text(raw.get("task"), f"pair {role}:{line_number}:task")
                raw_run_id = raw.get("run_id")
                if raw_run_id is None:
                    null_run_counts[role] += 1
                    run_id = None
                else:
                    run_id = required_text(raw_run_id, f"pair {role}:{line_number}:run")
                parent = required_text(raw.get("parent"), f"pair {role}:{line_number}:parent")
                better = required_text(raw.get("better"), f"pair {role}:{line_number}:better")
                worse = required_text(raw.get("worse"), f"pair {role}:{line_number}:worse")
                if better == worse:
                    raise AnswerabilityError(f"self pair at {role}:{line_number}")
                key = (role, parent)
                if key not in parents:
                    raise AnswerabilityError(f"pair parent absent at {role}:{line_number}")
                parent_row = parents[key]
                if task != parent_row["task"] or (
                    run_id is not None and run_id != parent_row["run_id"]
                ):
                    raise AnswerabilityError(f"pair context mismatch at {role}:{line_number}")
                undirected = tuple(sorted((better, worse)))
                global_key = (role, parent, undirected[0], undirected[1])
                if global_key in global_unordered:
                    raise AnswerabilityError(f"duplicate unordered pair at {role}:{line_number}")
                global_unordered.add(global_key)
                grouped[key]["nodes"].update((better, worse))
                grouped[key]["edges"].add((better, worse))
                grouped[key]["unordered"].add(undirected)
                role_counts[role] += 1
    if {role: role_counts[role] for role in ROLES} != protocol["expected_role_pair_counts"]:
        raise AnswerabilityError("pair role counts mismatch")
    if {role: null_run_counts[role] for role in ROLES} != protocol[
        "expected_role_pair_null_run_counts"
    ]:
        raise AnswerabilityError("pair null-run schema mismatch")
    if sum(role_counts.values()) != protocol["expected_published_edges"]:
        raise AnswerabilityError("published edge count mismatch")
    for key, parent in parents.items():
        value = grouped[key]
        if len(value["nodes"]) != parent["finite_children"]:
            raise AnswerabilityError(f"finite endpoint closure mismatch: {key}")
        if len(value["edges"]) != parent["published_unique_edges"]:
            raise AnswerabilityError(f"published edge closure mismatch: {key}")
    return grouped


def load_status_edges(
    path: Path,
    protocol: dict[str, Any],
    parents: dict[tuple[str, str], dict[str, Any]],
    identities: dict[tuple[str, str], dict[str, Any]],
    pairs: dict[tuple[str, str], dict[str, set[Any]]],
) -> dict[tuple[str, str], list[tuple[str, str, str]]]:
    if digest(path) != protocol["input_status_edges_sha256"]:
        raise AnswerabilityError("status edge SHA mismatch")
    scan_file(path)
    grouped: dict[tuple[str, str], list[tuple[str, str, str]]] = collections.defaultdict(list)
    seen: set[tuple[str, str, str, str]] = set()
    invalid_children: set[str] = set()
    categories: collections.Counter[str] = collections.Counter()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AnswerabilityError(f"invalid status edge JSON at line {line_number}") from exc
            if not isinstance(raw, dict):
                raise AnswerabilityError(f"status edge is not an object at line {line_number}")
            role = required_text(raw.get("role"), f"status edge {line_number}:role")
            task = required_text(raw.get("task"), f"status edge {line_number}:task")
            run_id = required_text(raw.get("run_id"), f"status edge {line_number}:run")
            parent = required_text(raw.get("parent"), f"status edge {line_number}:parent")
            valid = required_text(raw.get("valid_child_id"), f"status edge {line_number}:valid")
            invalid = required_text(raw.get("invalid_child_id"), f"status edge {line_number}:invalid")
            category = required_text(raw.get("invalid_category"), f"status edge {line_number}:category")
            if raw.get("relation") != "VALIDITY_DOMINANCE" or category not in protocol["certifiable_categories"]:
                raise AnswerabilityError(f"status edge contract mismatch at line {line_number}")
            key = (role, parent)
            if key not in parents:
                raise AnswerabilityError(f"status edge parent absent at line {line_number}")
            parent_row = parents[key]
            if task != parent_row["task"] or run_id != parent_row["run_id"]:
                raise AnswerabilityError(f"status edge context mismatch at line {line_number}")
            if valid not in pairs[key]["nodes"] or invalid not in identities[key]["missing_child_ids"]:
                raise AnswerabilityError(f"status edge endpoint mismatch at line {line_number}")
            edge_key = (role, parent, valid, invalid)
            if edge_key in seen:
                raise AnswerabilityError(f"duplicate status edge at line {line_number}")
            seen.add(edge_key)
            invalid_children.add(invalid)
            categories[category] += 1
            grouped[key].append((valid, invalid, category))
    if len(seen) != protocol["expected_validity_edges"]:
        raise AnswerabilityError("status edge count mismatch")
    if len(invalid_children) != protocol["expected_certified_invalid_children"]:
        raise AnswerabilityError("certified invalid child count mismatch")
    expected_categories = protocol.get("expected_validity_edge_categories")
    if dict(sorted(categories.items())) != expected_categories:
        raise AnswerabilityError("status edge category count mismatch")
    for key, rows in grouped.items():
        finite = pairs[key]["nodes"]
        by_invalid: dict[str, set[str]] = collections.defaultdict(set)
        for valid, invalid, _ in rows:
            by_invalid[invalid].add(valid)
        if any(valids != finite for valids in by_invalid.values()):
            raise AnswerabilityError(f"status invalid child lacks all finite dominators: {key}")
    return dict(grouped)


def graph_summary(nodes: set[str], edges: set[tuple[str, str]]) -> dict[str, Any]:
    if len(nodes) < 2 or any(left not in nodes or right not in nodes or left == right for left, right in edges):
        raise AnswerabilityError("invalid graph nodes/edges")
    adjacency: dict[str, set[str]] = {node: set() for node in nodes}
    indegree: dict[str, int] = {node: 0 for node in nodes}
    for left, right in edges:
        if right not in adjacency[left]:
            adjacency[left].add(right)
            indegree[right] += 1
    queue = collections.deque(sorted(node for node in nodes if indegree[node] == 0))
    order: list[str] = []
    remaining = dict(indegree)
    while queue:
        node = queue.popleft()
        order.append(node)
        for child in sorted(adjacency[node]):
            remaining[child] -= 1
            if remaining[child] == 0:
                queue.append(child)
    if len(order) != len(nodes):
        raise AnswerabilityError("relation graph contains a cycle")
    reach: dict[str, set[str]] = {node: set() for node in nodes}
    for node in reversed(order):
        for child in adjacency[node]:
            reach[node].add(child)
            reach[node].update(reach[child])
    winners = sorted(node for node in nodes if len(reach[node]) == len(nodes) - 1)
    top_set = sorted(node for node in nodes if indegree[node] == 0)
    if len(winners) > 1 or (len(winners) == 1 and top_set != winners):
        raise AnswerabilityError("winner/top-set consistency failed")
    return {
        "direct_relations": len(edges),
        "transitive_relations": sum(len(values) for values in reach.values()),
        "top_set_size": len(top_set),
        "winner": winners[0] if winners else None,
    }


def hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_parent_rows(
    parents: dict[tuple[str, str], dict[str, Any]],
    identities: dict[tuple[str, str], dict[str, Any]],
    pairs: dict[tuple[str, str], dict[str, set[Any]]],
    status_edges: dict[tuple[str, str], list[tuple[str, str, str]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in sorted(parents):
        parent = parents[key]
        identity = identities[key]
        finite_nodes = set(pairs[key]["nodes"])
        missing_nodes = set(identity["missing_child_ids"])
        identity_available = bool(identity["source_identity_available"])
        if identity_available:
            source_nodes = finite_nodes | missing_nodes
            if len(source_nodes) != parent["source_children"] or finite_nodes & missing_nodes:
                raise AnswerabilityError(f"source identity closure mismatch: {key}")
        else:
            source_nodes = set(finite_nodes)
            if parent["source_children"] <= len(source_nodes):
                raise AnswerabilityError(f"unavailable identity has no missing slots: {key}")
        published_edges = set(pairs[key]["edges"])
        status_rows = status_edges.get(key, [])
        primary_validity = {(valid, invalid) for valid, invalid, _ in status_rows}
        execution_validity = {
            (valid, invalid)
            for valid, invalid, category in status_rows
            if category == "EXECUTION_ERROR"
        }
        primary_edges = published_edges | primary_validity
        execution_edges = published_edges | execution_validity
        baseline = graph_summary(source_nodes, published_edges)
        primary = graph_summary(source_nodes, primary_edges)
        execution = graph_summary(source_nodes, execution_edges)
        if not identity_available:
            baseline_winner = primary_winner = execution_winner = None
            baseline_top = primary_top = execution_top = None
        else:
            baseline_winner = baseline["winner"]
            primary_winner = primary["winner"]
            execution_winner = execution["winner"]
            baseline_top = baseline["top_set_size"]
            primary_top = primary["top_set_size"]
            execution_top = execution["top_set_size"]
        if baseline_winner is not None and (
            primary_winner != baseline_winner or execution_winner != baseline_winner
        ):
            raise AnswerabilityError(f"status edges changed an identified finite winner: {key}")
        certified_invalid = {invalid for _, invalid, _ in status_rows}
        unknown_children = parent["source_children"] - len(finite_nodes) - len(certified_invalid)
        if unknown_children < 0:
            raise AnswerabilityError(f"negative unknown source children: {key}")
        rows.append(
            {
                "role": parent["role"],
                "task": parent["task"],
                "run_id": parent["run_id"],
                "run_id_sha256": hash_text(parent["run_id"]),
                "parent_sha256": hash_text(parent["parent"]),
                "source_children": parent["source_children"],
                "finite_children": parent["finite_children"],
                "source_identity_available": identity_available,
                "missing_identity_children": len(missing_nodes) if identity_available else None,
                "certified_invalid_children": len(certified_invalid),
                "unknown_source_children": unknown_children,
                "published_direct_relations": baseline["direct_relations"],
                "status_direct_relations": primary["direct_relations"],
                "execution_only_direct_relations": execution["direct_relations"],
                "published_transitive_relations": baseline["transitive_relations"],
                "status_transitive_relations": primary["transitive_relations"],
                "execution_only_transitive_relations": execution["transitive_relations"],
                "published_top_set_size": baseline_top,
                "status_top_set_size": primary_top,
                "execution_only_top_set_size": execution_top,
                "published_winner": baseline_winner,
                "status_winner": primary_winner,
                "execution_only_winner": execution_winner,
                "published_winner_identified": baseline_winner is not None,
                "status_winner_identified": primary_winner is not None,
                "execution_only_winner_identified": execution_winner is not None,
                "newly_identified_by_status": baseline_winner is None and primary_winner is not None,
                "newly_identified_execution_only": baseline_winner is None and execution_winner is not None,
            }
        )
    return rows


def aggregate(rows: Iterable[dict[str, Any]], stratum_type: str, stratum: str) -> dict[str, Any]:
    values = list(rows)
    totals: dict[str, Any] = {
        "stratum_type": stratum_type,
        "stratum": stratum,
        "parents": len(values),
        "runs": len({row["run_id"] for row in values}),
        "source_pair_capacity": sum(comb2(row["source_children"]) for row in values),
        "source_identity_available_parents": sum(row["source_identity_available"] for row in values),
        "published_direct_relations": sum(row["published_direct_relations"] for row in values),
        "status_direct_relations": sum(row["status_direct_relations"] for row in values),
        "execution_only_direct_relations": sum(row["execution_only_direct_relations"] for row in values),
        "published_transitive_relations": sum(row["published_transitive_relations"] for row in values),
        "status_transitive_relations": sum(row["status_transitive_relations"] for row in values),
        "execution_only_transitive_relations": sum(row["execution_only_transitive_relations"] for row in values),
        "published_winners": sum(row["published_winner_identified"] for row in values),
        "status_winners": sum(row["status_winner_identified"] for row in values),
        "execution_only_winners": sum(row["execution_only_winner_identified"] for row in values),
        "newly_identified_by_status": sum(row["newly_identified_by_status"] for row in values),
        "newly_identified_execution_only": sum(row["newly_identified_execution_only"] for row in values),
    }
    if not (
        totals["published_winners"] <= totals["execution_only_winners"] <= totals["status_winners"]
        <= totals["source_identity_available_parents"] <= totals["parents"]
    ):
        raise AnswerabilityError(f"winner monotonicity failed for {stratum_type}:{stratum}")
    unanswered = totals["parents"] - totals["published_winners"]
    totals.update(
        {
            "published_winner_rate": ratio(totals["published_winners"], totals["parents"]),
            "status_winner_rate": ratio(totals["status_winners"], totals["parents"]),
            "execution_only_winner_rate": ratio(totals["execution_only_winners"], totals["parents"]),
            "status_winner_rate_gain": ratio(totals["newly_identified_by_status"], totals["parents"]),
            "execution_only_winner_rate_gain": ratio(
                totals["newly_identified_execution_only"], totals["parents"]
            ),
            "status_unanswered_gap_recovery": ratio(totals["newly_identified_by_status"], unanswered),
            "execution_only_unanswered_gap_recovery": ratio(
                totals["newly_identified_execution_only"], unanswered
            ),
            "published_relation_coverage": ratio(
                totals["published_direct_relations"], totals["source_pair_capacity"]
            ),
            "status_direct_relation_coverage": ratio(
                totals["status_direct_relations"], totals["source_pair_capacity"]
            ),
            "status_transitive_relation_coverage": ratio(
                totals["status_transitive_relations"], totals["source_pair_capacity"]
            ),
            "execution_only_transitive_relation_coverage": ratio(
                totals["execution_only_transitive_relations"], totals["source_pair_capacity"]
            ),
        }
    )
    return totals


def analyze(rows: list[dict[str, Any]], protocol: dict[str, Any], source_commit: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    overall = aggregate(rows, "overall", "all")
    roles = {
        role: aggregate((row for row in rows if row["role"] == role), "role", role)
        for role in ROLES
    }
    task_ids = sorted({row["task"] for row in rows})
    task_rows = [
        aggregate((row for row in rows if row["task"] == task), "task", task)
        for task in task_ids
    ]
    supported = [
        row
        for row in task_rows
        if row["source_pair_capacity"] >= protocol["minimum_task_source_pair_capacity"]
    ]
    positive = [row for row in supported if row["newly_identified_by_status"] > 0]
    execution_positive = [
        row for row in supported if row["newly_identified_execution_only"] > 0
    ]
    dominant = (
        max((row["newly_identified_by_status"] for row in task_rows), default=0)
        / overall["newly_identified_by_status"]
        if overall["newly_identified_by_status"]
        else None
    )
    execution_dominant = (
        max((row["newly_identified_execution_only"] for row in task_rows), default=0)
        / overall["newly_identified_execution_only"]
        if overall["newly_identified_execution_only"]
        else None
    )
    criteria = {
        "supported_tasks_ge_minimum": len(supported) >= protocol["minimum_supported_tasks"],
        "newly_identified_parents_ge_material_minimum": overall["newly_identified_by_status"]
        >= protocol["material_min_newly_identified_parents"],
        "overall_winner_rate_gain_ge_material_minimum": overall["status_winner_rate_gain"]
        >= protocol["material_min_overall_winner_rate_gain"],
        "train_winner_rate_gain_ge_material_minimum": roles["train"]["status_winner_rate_gain"]
        >= protocol["material_min_train_winner_rate_gain"],
        "frozen_winner_rate_gain_ge_material_minimum": roles["frozen"]["status_winner_rate_gain"]
        >= protocol["material_min_frozen_winner_rate_gain"],
        "status_winner_rate_ge_material_minimum": overall["status_winner_rate"]
        >= protocol["material_min_status_winner_rate"],
        "tasks_with_positive_gain_ge_minimum": len(positive)
        >= protocol["minimum_tasks_with_positive_gain"],
        "dominant_added_winner_task_share_le_maximum": dominant is not None
        and dominant <= protocol["maximum_dominant_added_winner_task_share"],
    }
    execution_criteria = {
        "newly_identified_parents_ge_material_minimum": overall["newly_identified_execution_only"]
        >= protocol["material_min_newly_identified_parents"],
        "overall_winner_rate_gain_ge_material_minimum": overall["execution_only_winner_rate_gain"]
        >= protocol["material_min_overall_winner_rate_gain"],
        "train_winner_rate_gain_ge_material_minimum": roles["train"]["execution_only_winner_rate_gain"]
        >= protocol["material_min_train_winner_rate_gain"],
        "frozen_winner_rate_gain_ge_material_minimum": roles["frozen"]["execution_only_winner_rate_gain"]
        >= protocol["material_min_frozen_winner_rate_gain"],
        "status_winner_rate_ge_material_minimum": overall["execution_only_winner_rate"]
        >= protocol["material_min_status_winner_rate"],
        "tasks_with_positive_gain_ge_minimum": len(execution_positive)
        >= protocol["minimum_tasks_with_positive_gain"],
        "dominant_added_winner_task_share_le_maximum": execution_dominant is not None
        and execution_dominant <= protocol["maximum_dominant_added_winner_task_share"],
    }
    support_ok = criteria["supported_tasks_ge_minimum"]
    all_material = all(criteria.values()) and all(execution_criteria.values())
    status = STATUS_SUPPORT if not support_ok else STATUS_PASS if all_material else STATUS_BELOW
    summary = {
        "protocol": PROTOCOL,
        "status": status,
        "source_commit": source_commit,
        "claim_allowed": status == STATUS_PASS,
        "scope": {
            "numeric_grade_used": False,
            "gap_used": False,
            "code_or_observation_used": False,
            "prospective_outcome_used": False,
            "pair_orientation_used": True,
            "validity_status_used": True,
            "inferred_relations_are_logged_comparisons": False,
            "complete_total_order_claim_allowed": False,
            "predictor_or_search_utility_claim_allowed": False,
            "gpu": 0,
            "api_calls": 0,
            "base_llm_updated": False,
        },
        "inputs": {
            "per_parent_sha256": protocol["input_per_parent_sha256"],
            "identity_sha256": protocol["input_identity_sha256"],
            "status_edges_sha256": protocol["input_status_edges_sha256"],
            "pair_sha256_normalized_lf": {
                role: protocol["pair_inputs"][role]["sha256_normalized_lf"] for role in ROLES
            },
        },
        "overall": overall,
        "roles": roles,
        "support": {
            "all_tasks": len(task_rows),
            "supported_tasks": len(supported),
            "supported_task_ids": [row["stratum"] for row in supported],
            "tasks_with_positive_gain": len(positive),
            "execution_only_tasks_with_positive_gain": len(execution_positive),
            "dominant_added_winner_task_share": dominant,
            "execution_only_dominant_added_winner_task_share": execution_dominant,
        },
        "criteria": criteria,
        "execution_error_only_sensitivity_criteria": execution_criteria,
    }
    return summary, task_rows


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def csv_value(value: Any) -> Any:
    return "" if value is None else value


def run(args: argparse.Namespace) -> int:
    if not isinstance(args.source_commit, str) or not HEX40.fullmatch(args.source_commit):
        raise AnswerabilityError("source commit must be a full lowercase SHA-1")
    protocol_path = Path(args.protocol).resolve()
    parent_path = Path(args.per_parent).resolve()
    identity_path = Path(args.identity_registry).resolve()
    status_path = Path(args.status_edges).resolve()
    for path in (protocol_path, parent_path, identity_path, status_path):
        if not path.is_file():
            raise AnswerabilityError(f"missing input: {path}")
    protocol = load_protocol(protocol_path)
    parents = load_parents(parent_path, protocol)
    identities = load_identity(identity_path, protocol, parents)
    pair_paths = parse_pair_arguments(args.pair)
    pairs = load_pairs(pair_paths, protocol, parents)
    status_edges = load_status_edges(status_path, protocol, parents, identities, pairs)
    parent_rows = build_parent_rows(parents, identities, pairs, status_edges)
    summary, task_rows = analyze(parent_rows, protocol, args.source_commit)
    output = Path(args.output).resolve()
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if output.exists() or staging.exists():
        raise AnswerabilityError("output path already exists")
    staging.mkdir(parents=True)
    try:
        write_json(staging / "summary.json", summary)
        with (staging / "per_parent.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=PARENT_OUTPUT_FIELDS, lineterminator="\n")
            writer.writeheader()
            for row in parent_rows:
                writer.writerow({field: csv_value(row[field]) for field in PARENT_OUTPUT_FIELDS})
        with (staging / "per_task.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=AGGREGATE_FIELDS, lineterminator="\n")
            writer.writeheader()
            for row in task_rows:
                writer.writerow({field: csv_value(row[field]) for field in AGGREGATE_FIELDS})
        manifest = {
            name: digest(staging / name)
            for name in ("summary.json", "per_parent.csv", "per_task.csv")
        }
        write_json(staging / "sha256_manifest.json", manifest)
        for path in staging.iterdir():
            scan_file(path)
        staging.replace(output)
    except Exception:
        if staging.exists():
            for child in staging.iterdir():
                child.unlink()
            staging.rmdir()
        raise
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--protocol", required=True)
    value.add_argument("--per-parent", required=True)
    value.add_argument("--identity-registry", required=True)
    value.add_argument("--status-edges", required=True)
    value.add_argument("--pair", action="append", required=True)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        return run(parser().parse_args())
    except (AnswerabilityError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"SOURCE_DECISION_ANSWERABILITY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
