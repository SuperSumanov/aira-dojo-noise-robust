#!/usr/bin/env python3
"""Independent source rebuild for source-decision answerability artifacts."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


ROLES = ("train", "frozen", "extension")
PROTOCOL = "source-decision-answerability-v1"
PARENT_FIELDS = (
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
AGG_FIELDS = (
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


class VerificationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def normalized_lf_sha(path: Path) -> str:
    text = path.read_bytes().decode("utf-8")
    return hashlib.sha256(
        text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    ).hexdigest()


def comb2(value: int) -> int:
    return value * (value - 1) // 2


def fraction(numerator: int | float, denominator: int | float) -> float | None:
    return numerator / denominator if denominator else None


def text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise VerificationError(f"invalid text at {where}")
    return value


def boolean(value: Any, where: str) -> bool:
    if value is True or value == "True":
        return True
    if value is False or value == "False":
        return False
    raise VerificationError(f"invalid boolean at {where}")


def integer(value: Any, where: str) -> int:
    if isinstance(value, bool):
        raise VerificationError(f"invalid integer at {where}")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise VerificationError(f"invalid integer at {where}") from exc
    if result < 0:
        raise VerificationError(f"negative integer at {where}")
    return result


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerificationError(f"invalid JSON: {path.name}") from exc


def parse_pairs(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for item in values:
        if "=" not in item:
            raise VerificationError("pair argument missing role")
        role, raw = item.split("=", 1)
        if role not in ROLES or role in result:
            raise VerificationError("pair role invalid or duplicated")
        result[role] = Path(raw).resolve()
    if set(result) != set(ROLES):
        raise VerificationError("pair roles incomplete")
    return result


def rebuild(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    protocol = load_json(Path(args.protocol).resolve())
    if not isinstance(protocol, dict) or protocol.get("protocol") != PROTOCOL:
        raise VerificationError("protocol identity mismatch")
    parent_path = Path(args.per_parent).resolve()
    identity_path = Path(args.identity_registry).resolve()
    status_path = Path(args.status_edges).resolve()
    if sha256_file(parent_path) != protocol.get("input_per_parent_sha256"):
        raise VerificationError("parent digest mismatch")
    if sha256_file(identity_path) != protocol.get("input_identity_sha256"):
        raise VerificationError("identity digest mismatch")
    if sha256_file(status_path) != protocol.get("input_status_edges_sha256"):
        raise VerificationError("status digest mismatch")

    parents: dict[tuple[str, str], dict[str, Any]] = {}
    with parent_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "role",
            "task",
            "run_id",
            "parent",
            "source_declared_size",
            "finite_card_child_count",
            "published_endpoint_count",
            "unique_edges",
        }
        if reader.fieldnames is None or not required <= set(reader.fieldnames):
            raise VerificationError("parent schema mismatch")
        for line_number, raw in enumerate(reader, 2):
            role = text(raw.get("role"), f"parent:{line_number}:role")
            parent = text(raw.get("parent"), f"parent:{line_number}:parent")
            key = (role, parent)
            if role not in ROLES or key in parents:
                raise VerificationError("parent identity invalid or duplicated")
            source = integer(raw.get("source_declared_size"), f"parent:{line_number}:source")
            finite = integer(raw.get("finite_card_child_count"), f"parent:{line_number}:finite")
            endpoints = integer(raw.get("published_endpoint_count"), f"parent:{line_number}:endpoints")
            edges = integer(raw.get("unique_edges"), f"parent:{line_number}:edges")
            if source < 2 or finite < 2 or finite != endpoints or finite > source or edges > comb2(finite):
                raise VerificationError("parent count contract mismatch")
            parents[key] = {
                "role": role,
                "task": text(raw.get("task"), f"parent:{line_number}:task"),
                "run_id": text(raw.get("run_id"), f"parent:{line_number}:run"),
                "parent": parent,
                "source": source,
                "finite": finite,
                "published": edges,
            }
    if len(parents) != protocol.get("expected_parent_rows"):
        raise VerificationError("parent row count mismatch")

    identities: dict[tuple[str, str], dict[str, Any]] = {}
    with identity_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            raw = json.loads(line)
            if not isinstance(raw, dict):
                raise VerificationError("identity row not object")
            key = (raw.get("role"), raw.get("parent"))
            if key not in parents or key in identities:
                raise VerificationError(f"identity key mismatch at {line_number}")
            incomplete = boolean(raw.get("source_incomplete"), f"identity:{line_number}:incomplete")
            exact = boolean(raw.get("exact_identity_recoverable"), f"identity:{line_number}:exact")
            missing = raw.get("missing_child_ids")
            if not isinstance(missing, list) or any(not isinstance(item, str) or not item for item in missing):
                raise VerificationError("identity missing list invalid")
            expected_missing = parents[key]["source"] - parents[key]["finite"]
            available = (not incomplete) or exact
            if available and len(missing) != expected_missing:
                raise VerificationError("available identity count mismatch")
            if not available and missing:
                raise VerificationError("unavailable identity was partially emitted")
            identities[key] = {"available": available, "missing": set(missing)}
    if len(identities) != protocol.get("expected_identity_rows") or set(identities) != set(parents):
        raise VerificationError("identity parent closure mismatch")

    pair_paths = parse_pairs(args.pair)
    pair_groups: dict[tuple[str, str], dict[str, set[Any]]] = {
        key: {"nodes": set(), "edges": set(), "undirected": set()} for key in parents
    }
    pair_role_counts = collections.Counter()
    pair_null_runs = collections.Counter()
    for role in ROLES:
        path = pair_paths[role]
        if normalized_lf_sha(path) != protocol["pair_inputs"][role]["sha256_normalized_lf"]:
            raise VerificationError(f"pair digest mismatch for {role}")
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                raw = json.loads(line)
                parent = text(raw.get("parent"), f"pair:{role}:{line_number}:parent")
                key = (role, parent)
                if key not in parents:
                    raise VerificationError("pair parent absent")
                raw_run_id = raw.get("run_id")
                if raw_run_id is None:
                    pair_null_runs[role] += 1
                elif not isinstance(raw_run_id, str) or not raw_run_id:
                    raise VerificationError("pair run identity invalid")
                if raw.get("task") != parents[key]["task"] or (
                    raw_run_id is not None and raw_run_id != parents[key]["run_id"]
                ):
                    raise VerificationError("pair context mismatch")
                better = text(raw.get("better"), f"pair:{role}:{line_number}:better")
                worse = text(raw.get("worse"), f"pair:{role}:{line_number}:worse")
                undirected = tuple(sorted((better, worse)))
                if better == worse or undirected in pair_groups[key]["undirected"]:
                    raise VerificationError("pair duplicate/self edge")
                pair_groups[key]["nodes"].update((better, worse))
                pair_groups[key]["edges"].add((better, worse))
                pair_groups[key]["undirected"].add(undirected)
                pair_role_counts[role] += 1
    if {role: pair_role_counts[role] for role in ROLES} != protocol.get("expected_role_pair_counts"):
        raise VerificationError("pair role accounting mismatch")
    if {role: pair_null_runs[role] for role in ROLES} != protocol.get(
        "expected_role_pair_null_run_counts"
    ):
        raise VerificationError("pair null-run schema mismatch")
    for key, parent in parents.items():
        if len(pair_groups[key]["nodes"]) != parent["finite"]:
            raise VerificationError("pair endpoint closure mismatch")
        if len(pair_groups[key]["edges"]) != parent["published"]:
            raise VerificationError("pair edge closure mismatch")

    status_groups: dict[tuple[str, str], list[tuple[str, str, str]]] = collections.defaultdict(list)
    status_seen: set[tuple[str, str, str, str]] = set()
    invalid_seen: set[str] = set()
    categories = collections.Counter()
    with status_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            raw = json.loads(line)
            role = raw.get("role")
            parent = raw.get("parent")
            key = (role, parent)
            if key not in parents:
                raise VerificationError("status parent absent")
            valid = text(raw.get("valid_child_id"), f"status:{line_number}:valid")
            invalid = text(raw.get("invalid_child_id"), f"status:{line_number}:invalid")
            category = text(raw.get("invalid_category"), f"status:{line_number}:category")
            edge_key = (str(role), str(parent), valid, invalid)
            if edge_key in status_seen or raw.get("relation") != "VALIDITY_DOMINANCE":
                raise VerificationError("status edge duplicate/contract mismatch")
            if valid not in pair_groups[key]["nodes"] or invalid not in identities[key]["missing"]:
                raise VerificationError("status endpoint closure mismatch")
            status_seen.add(edge_key)
            invalid_seen.add(invalid)
            categories[category] += 1
            status_groups[key].append((valid, invalid, category))
    if len(status_seen) != protocol.get("expected_validity_edges"):
        raise VerificationError("status edge count mismatch")
    if len(invalid_seen) != protocol.get("expected_certified_invalid_children"):
        raise VerificationError("invalid child count mismatch")
    if dict(sorted(categories.items())) != protocol.get("expected_validity_edge_categories"):
        raise VerificationError("status category accounting mismatch")

    def close(nodes: set[str], edges: set[tuple[str, str]]) -> tuple[int, int, int, str | None]:
        adjacency = {node: set() for node in nodes}
        incoming = {node: 0 for node in nodes}
        for left, right in edges:
            if left not in nodes or right not in nodes or left == right:
                raise VerificationError("graph endpoint mismatch")
            adjacency[left].add(right)
            incoming[right] += 1
        reach: dict[str, set[str]] = {}
        for start in nodes:
            visited: set[str] = set()
            queue = collections.deque(adjacency[start])
            while queue:
                node = queue.popleft()
                if node == start:
                    raise VerificationError("graph cycle detected")
                if node in visited:
                    continue
                visited.add(node)
                queue.extend(adjacency[node] - visited)
            reach[start] = visited
        winners = sorted(node for node, values in reach.items() if len(values) == len(nodes) - 1)
        top = sorted(node for node in nodes if incoming[node] == 0)
        if len(winners) > 1 or (winners and winners != top):
            raise VerificationError("winner/top mismatch")
        return len(edges), sum(len(values) for values in reach.values()), len(top), winners[0] if winners else None

    rows: list[dict[str, Any]] = []
    for key in sorted(parents):
        parent = parents[key]
        identity = identities[key]
        finite = set(pair_groups[key]["nodes"])
        nodes = finite | identity["missing"] if identity["available"] else finite
        if identity["available"] and len(nodes) != parent["source"]:
            raise VerificationError("source set count mismatch")
        published_edges = set(pair_groups[key]["edges"])
        primary_validity = {(left, right) for left, right, _ in status_groups.get(key, [])}
        exec_validity = {
            (left, right)
            for left, right, category in status_groups.get(key, [])
            if category == "EXECUTION_ERROR"
        }
        base = close(nodes, published_edges)
        primary = close(nodes, published_edges | primary_validity)
        execution = close(nodes, published_edges | exec_validity)
        if identity["available"]:
            base_winner, primary_winner, exec_winner = base[3], primary[3], execution[3]
            base_top, primary_top, exec_top = base[2], primary[2], execution[2]
        else:
            base_winner = primary_winner = exec_winner = None
            base_top = primary_top = exec_top = None
        if base_winner is not None and (primary_winner != base_winner or exec_winner != base_winner):
            raise VerificationError("identified winner changed")
        certified = {right for _, right, _ in status_groups.get(key, [])}
        row = {
            "role": parent["role"],
            "task": parent["task"],
            "run_id": parent["run_id"],
            "run_id_sha256": hashlib.sha256(parent["run_id"].encode()).hexdigest(),
            "parent_sha256": hashlib.sha256(parent["parent"].encode()).hexdigest(),
            "source_children": parent["source"],
            "finite_children": parent["finite"],
            "source_identity_available": identity["available"],
            "missing_identity_children": len(identity["missing"]) if identity["available"] else None,
            "certified_invalid_children": len(certified),
            "unknown_source_children": parent["source"] - parent["finite"] - len(certified),
            "published_direct_relations": base[0],
            "status_direct_relations": primary[0],
            "execution_only_direct_relations": execution[0],
            "published_transitive_relations": base[1],
            "status_transitive_relations": primary[1],
            "execution_only_transitive_relations": execution[1],
            "published_top_set_size": base_top,
            "status_top_set_size": primary_top,
            "execution_only_top_set_size": exec_top,
            "published_winner_identified": base_winner is not None,
            "status_winner_identified": primary_winner is not None,
            "execution_only_winner_identified": exec_winner is not None,
            "newly_identified_by_status": base_winner is None and primary_winner is not None,
            "newly_identified_execution_only": base_winner is None and exec_winner is not None,
        }
        rows.append(row)

    def aggregate(values: Iterable[dict[str, Any]], kind: str, name: str) -> dict[str, Any]:
        selected = list(values)
        result: dict[str, Any] = {
            "stratum_type": kind,
            "stratum": name,
            "parents": len(selected),
            "runs": len({row["run_id"] for row in selected}),
            "source_pair_capacity": sum(comb2(row["source_children"]) for row in selected),
            "source_identity_available_parents": sum(row["source_identity_available"] for row in selected),
        }
        for field in (
            "published_direct_relations",
            "status_direct_relations",
            "execution_only_direct_relations",
            "published_transitive_relations",
            "status_transitive_relations",
            "execution_only_transitive_relations",
        ):
            result[field] = sum(row[field] for row in selected)
        result["published_winners"] = sum(row["published_winner_identified"] for row in selected)
        result["status_winners"] = sum(row["status_winner_identified"] for row in selected)
        result["execution_only_winners"] = sum(row["execution_only_winner_identified"] for row in selected)
        result["newly_identified_by_status"] = sum(row["newly_identified_by_status"] for row in selected)
        result["newly_identified_execution_only"] = sum(
            row["newly_identified_execution_only"] for row in selected
        )
        unanswered = result["parents"] - result["published_winners"]
        result.update(
            {
                "published_winner_rate": fraction(result["published_winners"], result["parents"]),
                "status_winner_rate": fraction(result["status_winners"], result["parents"]),
                "execution_only_winner_rate": fraction(result["execution_only_winners"], result["parents"]),
                "status_winner_rate_gain": fraction(result["newly_identified_by_status"], result["parents"]),
                "execution_only_winner_rate_gain": fraction(
                    result["newly_identified_execution_only"], result["parents"]
                ),
                "status_unanswered_gap_recovery": fraction(result["newly_identified_by_status"], unanswered),
                "execution_only_unanswered_gap_recovery": fraction(
                    result["newly_identified_execution_only"], unanswered
                ),
                "published_relation_coverage": fraction(
                    result["published_direct_relations"], result["source_pair_capacity"]
                ),
                "status_direct_relation_coverage": fraction(
                    result["status_direct_relations"], result["source_pair_capacity"]
                ),
                "status_transitive_relation_coverage": fraction(
                    result["status_transitive_relations"], result["source_pair_capacity"]
                ),
                "execution_only_transitive_relation_coverage": fraction(
                    result["execution_only_transitive_relations"], result["source_pair_capacity"]
                ),
            }
        )
        return result

    overall = aggregate(rows, "overall", "all")
    role_rows = {
        role: aggregate((row for row in rows if row["role"] == role), "role", role)
        for role in ROLES
    }
    tasks = sorted({row["task"] for row in rows})
    task_rows = [
        aggregate((row for row in rows if row["task"] == task), "task", task)
        for task in tasks
    ]
    supported = [
        row for row in task_rows if row["source_pair_capacity"] >= protocol["minimum_task_source_pair_capacity"]
    ]
    positive = [row for row in supported if row["newly_identified_by_status"] > 0]
    exec_positive = [row for row in supported if row["newly_identified_execution_only"] > 0]
    dominant = max((row["newly_identified_by_status"] for row in task_rows), default=0) / overall[
        "newly_identified_by_status"
    ] if overall["newly_identified_by_status"] else None
    exec_dominant = max((row["newly_identified_execution_only"] for row in task_rows), default=0) / overall[
        "newly_identified_execution_only"
    ] if overall["newly_identified_execution_only"] else None
    criteria = {
        "supported_tasks_ge_minimum": len(supported) >= protocol["minimum_supported_tasks"],
        "newly_identified_parents_ge_material_minimum": overall["newly_identified_by_status"]
        >= protocol["material_min_newly_identified_parents"],
        "overall_winner_rate_gain_ge_material_minimum": overall["status_winner_rate_gain"]
        >= protocol["material_min_overall_winner_rate_gain"],
        "train_winner_rate_gain_ge_material_minimum": role_rows["train"]["status_winner_rate_gain"]
        >= protocol["material_min_train_winner_rate_gain"],
        "frozen_winner_rate_gain_ge_material_minimum": role_rows["frozen"]["status_winner_rate_gain"]
        >= protocol["material_min_frozen_winner_rate_gain"],
        "status_winner_rate_ge_material_minimum": overall["status_winner_rate"]
        >= protocol["material_min_status_winner_rate"],
        "tasks_with_positive_gain_ge_minimum": len(positive) >= protocol["minimum_tasks_with_positive_gain"],
        "dominant_added_winner_task_share_le_maximum": dominant is not None
        and dominant <= protocol["maximum_dominant_added_winner_task_share"],
    }
    exec_criteria = {
        "newly_identified_parents_ge_material_minimum": overall["newly_identified_execution_only"]
        >= protocol["material_min_newly_identified_parents"],
        "overall_winner_rate_gain_ge_material_minimum": overall["execution_only_winner_rate_gain"]
        >= protocol["material_min_overall_winner_rate_gain"],
        "train_winner_rate_gain_ge_material_minimum": role_rows["train"]["execution_only_winner_rate_gain"]
        >= protocol["material_min_train_winner_rate_gain"],
        "frozen_winner_rate_gain_ge_material_minimum": role_rows["frozen"]["execution_only_winner_rate_gain"]
        >= protocol["material_min_frozen_winner_rate_gain"],
        "status_winner_rate_ge_material_minimum": overall["execution_only_winner_rate"]
        >= protocol["material_min_status_winner_rate"],
        "tasks_with_positive_gain_ge_minimum": len(exec_positive)
        >= protocol["minimum_tasks_with_positive_gain"],
        "dominant_added_winner_task_share_le_maximum": exec_dominant is not None
        and exec_dominant <= protocol["maximum_dominant_added_winner_task_share"],
    }
    if not criteria["supported_tasks_ge_minimum"]:
        status = "INSUFFICIENT_TASK_SUPPORT_FOR_SOURCE_WINNER_ANSWERABILITY"
    elif all(criteria.values()) and all(exec_criteria.values()):
        status = "VERIFIED_MATERIAL_SOURCE_WINNER_ANSWERABILITY_RECOVERY"
    else:
        status = "SOURCE_WINNER_ANSWERABILITY_BELOW_MATERIAL_GATE"
    summary = {
        "protocol": PROTOCOL,
        "status": status,
        "source_commit": args.source_commit,
        "claim_allowed": status == "VERIFIED_MATERIAL_SOURCE_WINNER_ANSWERABILITY_RECOVERY",
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
        "roles": role_rows,
        "support": {
            "all_tasks": len(task_rows),
            "supported_tasks": len(supported),
            "supported_task_ids": [row["stratum"] for row in supported],
            "tasks_with_positive_gain": len(positive),
            "execution_only_tasks_with_positive_gain": len(exec_positive),
            "dominant_added_winner_task_share": dominant,
            "execution_only_dominant_added_winner_task_share": exec_dominant,
        },
        "criteria": criteria,
        "execution_error_only_sensitivity_criteria": exec_criteria,
    }
    return rows, task_rows, summary


def parse_parent_artifact(path: Path) -> list[dict[str, Any]]:
    bool_fields = {
        "source_identity_available",
        "published_winner_identified",
        "status_winner_identified",
        "execution_only_winner_identified",
        "newly_identified_by_status",
        "newly_identified_execution_only",
    }
    nullable_ints = {
        "missing_identity_children",
        "published_top_set_size",
        "status_top_set_size",
        "execution_only_top_set_size",
    }
    text_fields = {"role", "task", "run_id_sha256", "parent_sha256"}
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != PARENT_FIELDS:
            raise VerificationError("parent artifact fields mismatch")
        for raw in reader:
            row: dict[str, Any] = {}
            for field in PARENT_FIELDS:
                value = raw[field]
                if field in text_fields:
                    row[field] = value
                elif field in bool_fields:
                    row[field] = boolean(value, f"artifact:{field}")
                elif field in nullable_ints:
                    row[field] = None if value == "" else integer(value, f"artifact:{field}")
                else:
                    row[field] = integer(value, f"artifact:{field}")
            rows.append(row)
    return rows


def parse_task_artifact(path: Path) -> list[dict[str, Any]]:
    integer_fields = set(AGG_FIELDS[2:17])
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != AGG_FIELDS:
            raise VerificationError("task artifact fields mismatch")
        for raw in reader:
            row: dict[str, Any] = {"stratum_type": raw["stratum_type"], "stratum": raw["stratum"]}
            for field in AGG_FIELDS[2:]:
                if field in integer_fields:
                    row[field] = integer(raw[field], f"task artifact:{field}")
                else:
                    row[field] = None if raw[field] == "" else float(raw[field])
            rows.append(row)
    return rows


def verify(args: argparse.Namespace) -> dict[str, Any]:
    artifact = Path(args.artifact).resolve()
    expected_names = {"summary.json", "per_parent.csv", "per_task.csv", "sha256_manifest.json"}
    if not artifact.is_dir() or {path.name for path in artifact.iterdir() if path.is_file()} != expected_names:
        raise VerificationError("artifact file set mismatch")
    manifest = load_json(artifact / "sha256_manifest.json")
    for name in ("summary.json", "per_parent.csv", "per_task.csv"):
        if not isinstance(manifest, dict) or manifest.get(name) != sha256_file(artifact / name):
            raise VerificationError(f"manifest mismatch for {name}")
    expected_rows, expected_tasks, expected_summary = rebuild(args)
    public_rows = [{field: row[field] for field in PARENT_FIELDS} for row in expected_rows]
    if parse_parent_artifact(artifact / "per_parent.csv") != public_rows:
        raise VerificationError("per-parent independent reconstruction mismatch")
    if parse_task_artifact(artifact / "per_task.csv") != expected_tasks:
        raise VerificationError("per-task independent reconstruction mismatch")
    if load_json(artifact / "summary.json") != expected_summary:
        raise VerificationError("summary independent reconstruction mismatch")
    return {
        "protocol": "independent-source-decision-answerability-verifier-v1",
        "status": "INDEPENDENT_SOURCE_DECISION_ANSWERABILITY_VERIFIED",
        "producer_status": expected_summary["status"],
        "parents": len(expected_rows),
        "published_winners": expected_summary["overall"]["published_winners"],
        "status_winners": expected_summary["overall"]["status_winners"],
        "newly_identified_by_status": expected_summary["overall"]["newly_identified_by_status"],
        "producer_imported": False,
        "summary_sha256": sha256_file(artifact / "summary.json"),
    }


def main() -> int:
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--protocol", required=True)
        parser.add_argument("--per-parent", required=True)
        parser.add_argument("--identity-registry", required=True)
        parser.add_argument("--status-edges", required=True)
        parser.add_argument("--pair", action="append", required=True)
        parser.add_argument("--source-commit", required=True)
        parser.add_argument("--artifact", required=True)
        parser.add_argument("--output", required=True)
        args = parser.parse_args()
        if not re.fullmatch(r"[0-9a-f]{40}", args.source_commit):
            raise VerificationError("source commit invalid")
        result = verify(args)
        output = Path(args.output).resolve()
        if output.exists():
            raise VerificationError("verification output exists")
        output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (VerificationError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"SOURCE_DECISION_ANSWERABILITY_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
