"""Audit published b0 sibling sets against pre-filter journal sibling counts.

The cards corpus keeps only nodes with usable labels, but each retained card's ``n_siblings`` was
computed from the full journal before that filtering.  This audit distinguishes a complete source
choice set from a complete pair graph over the retained labeled fragment.  It never uses code,
observations, pair orientation, gaps, predictions, or first-960 artifacts.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable


PROTOCOL = "raw-choice-set-completeness-v1"
STATUS_COMPLETE = "VERIFIED_COMPLETE_SOURCE_CHOICE_SETS"
STATUS_PROVENANCE_HOLD = "STRUCTURALLY_COMPLETE_REQUIRES_SOURCE_SIZE_PROVENANCE"
STATUS_FRAGMENT = "VERIFIED_LABELED_SIBLING_FRAGMENT_BOUNDARY"
STATUS_INVALID = "INVALID_PUBLISHED_SIBLING_STRUCTURE"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-(?:ws-)?[A-Za-z0-9._-]{20,}|"
    rb"AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
ROLES = ("train", "frozen", "extension")
PER_PARENT_FIELDS = (
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


class AuditError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def credential_scan(path: Path) -> None:
    overlap = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            payload = overlap + chunk
            if CREDENTIAL.search(payload):
                raise AuditError(f"credential-shaped bytes refused in {path.name}")
            overlap = payload[-256:]


def finite_grade(card: dict[str, Any]) -> bool:
    try:
        value = float((card.get("label") or {}).get("graded"))
    except (TypeError, ValueError):
        return False
    return math.isfinite(value)


def required_text(row: dict[str, Any], key: str, where: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise AuditError(f"invalid {key} in {where}")
    return value


def load_run_map(path: Path) -> dict[str, str]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict) or any(
        not isinstance(key, str) or not isinstance(run, str) or not run
        for key, run in value.items()
    ):
        raise AuditError("invalid run map")
    return value


def load_card_structure(
    path: Path, run_map: dict[str, str]
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]], int]:
    cards: dict[str, dict[str, Any]] = {}
    children: dict[str, list[str]] = collections.defaultdict(list)
    rows = 0
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            rows += 1
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AuditError(f"invalid card JSON at line {line_no}") from exc
            if not isinstance(value, dict):
                raise AuditError(f"card line {line_no} is not an object")
            card_id = required_text(value, "id", f"card line {line_no}")
            if card_id in cards:
                raise AuditError(f"duplicate card ID at line {line_no}")
            task_value = value.get("task")
            lineage = value.get("lineage")
            if not isinstance(task_value, dict) or not isinstance(lineage, dict):
                raise AuditError(f"card structural schema mismatch at line {line_no}")
            task = required_text(task_value, "name", f"card line {line_no}")
            run_id = value.get("run_id")
            if not isinstance(run_id, str) or not run_id:
                run_id = run_map.get(card_id)
            if not isinstance(run_id, str) or not run_id:
                raise AuditError(f"card missing physical run at line {line_no}")
            if run_map.get(card_id) != run_id:
                raise AuditError(f"card/run-map mismatch at line {line_no}")
            parent = lineage.get("parent_id")
            if parent is not None and (not isinstance(parent, str) or not parent):
                raise AuditError(f"invalid parent ID at line {line_no}")
            n_siblings = lineage.get("n_siblings")
            if n_siblings is not None and (
                isinstance(n_siblings, bool) or not isinstance(n_siblings, int) or n_siblings < 0
            ):
                raise AuditError(f"invalid n_siblings at line {line_no}")
            children_ids = lineage.get("children_ids")
            if not isinstance(children_ids, list) or any(
                not isinstance(child, str) or not child for child in children_ids
            ):
                raise AuditError(f"invalid children_ids at line {line_no}")
            if len(children_ids) != len(set(children_ids)):
                raise AuditError(f"duplicate children_ids at line {line_no}")
            cards[card_id] = {
                "task": task,
                "run_id": run_id,
                "parent": parent,
                "n_siblings": n_siblings,
                "children_ids": tuple(children_ids),
                "finite": finite_grade(value),
            }
            if parent:
                children[parent].append(card_id)
    if not cards:
        raise AuditError("cards input is empty")
    return cards, children, rows


def load_pair_groups(paths: dict[str, Path]) -> tuple[dict[tuple[str, str], dict[str, Any]], int]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    total_rows = 0
    endpoint_roles: dict[str, str] = {}
    for role in ROLES:
        path = paths[role]
        with path.open(encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                total_rows += 1
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise AuditError(f"invalid {role} pair JSON at line {line_no}") from exc
                if not isinstance(value, dict) or value.get("budget") != 0:
                    raise AuditError(f"non-b0 or invalid row in {role} line {line_no}")
                parent = required_text(value, "parent", f"{role} line {line_no}")
                better = required_text(value, "better", f"{role} line {line_no}")
                worse = required_text(value, "worse", f"{role} line {line_no}")
                task = required_text(value, "task", f"{role} line {line_no}")
                run_id = required_text(value, "run_id", f"{role} line {line_no}")
                if better == worse:
                    raise AuditError(f"self pair in {role} line {line_no}")
                declared = value.get("set_size")
                if isinstance(declared, bool) or not isinstance(declared, int) or declared < 2:
                    raise AuditError(f"invalid set_size in {role} line {line_no}")
                key = (role, parent)
                group = groups.setdefault(
                    key,
                    {
                        "role": role,
                        "parent": parent,
                        "tasks": set(),
                        "runs": set(),
                        "declared": set(),
                        "endpoints": set(),
                        "edges": set(),
                        "rows": 0,
                    },
                )
                edge = tuple(sorted((better, worse)))
                if edge in group["edges"]:
                    raise AuditError(f"duplicate pair edge in {role}:{parent}")
                group["tasks"].add(task)
                group["runs"].add(run_id)
                group["declared"].add(declared)
                group["endpoints"].update((better, worse))
                group["edges"].add(edge)
                group["rows"] += 1
                for endpoint in (better, worse):
                    previous = endpoint_roles.setdefault(endpoint, role)
                    if previous != role:
                        raise AuditError("endpoint appears in multiple release roles")
    if not groups:
        raise AuditError("pair inputs are empty")
    return groups, total_rows


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def histogram(rows: Iterable[dict[str, Any]], field: str) -> dict[str, int]:
    counts = collections.Counter(str(row[field]) for row in rows)
    def order(item: tuple[str, int]) -> tuple[int, int | str]:
        try:
            return (0, int(item[0]))
        except ValueError:
            return (1, item[0])

    return dict(sorted(counts.items(), key=order))


def summarize_role(rows: list[dict[str, Any]]) -> dict[str, Any]:
    parent_count = len(rows)
    finite_coverage = [
        float(row["finite_endpoint_coverage"])
        for row in rows
        if row["finite_endpoint_coverage"] is not None
    ]
    raw_retention = [
        float(row["raw_source_retention"])
        for row in rows
        if row["raw_source_retention"] is not None
    ]
    finite_retention = [
        float(row["finite_source_retention"])
        for row in rows
        if row["finite_source_retention"] is not None
    ]

    def mean_or_none(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    return {
        "parents": parent_count,
        "pair_rows": sum(int(row["pair_rows"]) for row in rows),
        "runs": len({row["run_id"] for row in rows}),
        "tasks": len({row["task"] for row in rows}),
        "endpoint_fidelity_parents": sum(bool(row["endpoint_fidelity"]) for row in rows),
        "declared_matches_finite_parents": sum(
            bool(row["declared_matches_finite"]) for row in rows
        ),
        "full_finite_endpoint_coverage_parents": sum(value == 1.0 for value in finite_coverage),
        "raw_equals_source_parents": sum(bool(row["raw_equals_source"]) for row in rows),
        "finite_equals_source_parents": sum(bool(row["finite_equals_source"]) for row in rows),
        "source_size_consistent_parents": sum(
            bool(row["source_size_consistent"]) for row in rows
        ),
        "source_size_not_smaller_than_raw_parents": sum(
            bool(row["source_size_not_smaller_than_raw"]) for row in rows
        ),
        "raw_context_consistent_parents": sum(
            bool(row["raw_context_consistent"]) for row in rows
        ),
        "endpoints_all_finite_parents": sum(
            bool(row["endpoints_all_finite"]) for row in rows
        ),
        "parent_context_consistent_parents": sum(
            bool(row["parent_context_consistent"]) for row in rows
        ),
        "parent_children_contains_raw_when_present_parents": sum(
            bool(row["parent_children_contains_raw"])
            for row in rows
            if row["parent_card_present"]
        ),
        "source_size_gt_five_parents": sum(bool(row["source_size_gt_five"]) for row in rows),
        "orphan_parent_cards": sum(not bool(row["parent_card_present"]) for row in rows),
        "mean_finite_endpoint_coverage": mean_or_none(finite_coverage),
        "mean_raw_source_retention": mean_or_none(raw_retention),
        "mean_finite_source_retention": mean_or_none(finite_retention),
        "source_declared_size_histogram": histogram(rows, "source_declared_size"),
        "raw_card_child_count_histogram": histogram(rows, "raw_card_child_count"),
        "finite_card_child_count_histogram": histogram(rows, "finite_card_child_count"),
        "published_endpoint_count_histogram": histogram(rows, "published_endpoint_count"),
    }


def audit_parent(
    group: dict[str, Any], cards: dict[str, dict[str, Any]], children: dict[str, list[str]]
) -> dict[str, Any]:
    if len(group["tasks"]) != 1 or len(group["runs"]) != 1 or len(group["declared"]) != 1:
        raise AuditError(f"inconsistent pair context for {group['role']}:{group['parent']}")
    task = next(iter(group["tasks"]))
    run_id = next(iter(group["runs"]))
    declared = next(iter(group["declared"]))
    parent = group["parent"]
    raw_ids = set(children.get(parent, ()))
    if not raw_ids:
        raise AuditError(f"published parent has no retained direct children: {parent}")
    finite_ids = {card_id for card_id in raw_ids if cards[card_id]["finite"]}
    endpoints = set(group["endpoints"])
    raw_context_consistent = all(
        cards[card_id]["task"] == task
        and cards[card_id]["run_id"] == run_id
        and cards[card_id]["parent"] == parent
        for card_id in raw_ids
    )
    endpoints_all_finite = endpoints <= finite_ids
    endpoint_fidelity = endpoints_all_finite and raw_context_consistent
    sibling_sizes = {
        cards[card_id]["n_siblings"] + 1
        for card_id in raw_ids
        if cards[card_id]["n_siblings"] is not None
    }
    source_size_consistent = len(sibling_sizes) == 1 and all(
        cards[card_id]["n_siblings"] is not None for card_id in raw_ids
    )
    source_size = next(iter(sibling_sizes)) if source_size_consistent else None
    source_size_not_smaller = source_size is not None and source_size >= len(raw_ids)
    parent_card = cards.get(parent)
    parent_children = set(parent_card["children_ids"]) if parent_card else set()
    parent_context_consistent = parent_card is None or (
        parent_card["task"] == task and parent_card["run_id"] == run_id
    )
    finite_endpoint_count = len(endpoints & finite_ids)
    expected_edges = len(finite_ids) * (len(finite_ids) - 1) // 2
    row = {
        "role": group["role"],
        "task": task,
        "run_id": run_id,
        "parent": parent,
        "pair_rows": group["rows"],
        "unique_edges": len(group["edges"]),
        "published_endpoint_count": len(endpoints),
        "declared_set_size": declared,
        "raw_card_child_count": len(raw_ids),
        "finite_card_child_count": len(finite_ids),
        "source_declared_size": source_size,
        "source_size_consistent": source_size_consistent,
        "source_size_not_smaller_than_raw": source_size_not_smaller,
        "raw_context_consistent": raw_context_consistent,
        "endpoints_all_finite": endpoints_all_finite,
        "endpoint_fidelity": endpoint_fidelity,
        "declared_matches_finite": declared == len(finite_ids),
        "finite_endpoint_coverage": ratio(finite_endpoint_count, len(finite_ids)),
        "pair_graph_coverage_over_finite": ratio(len(group["edges"]), expected_edges),
        "raw_source_retention": ratio(len(raw_ids), source_size) if source_size_not_smaller else None,
        "finite_source_retention": ratio(len(finite_ids), source_size) if source_size_not_smaller else None,
        "raw_equals_source": source_size_not_smaller and len(raw_ids) == source_size,
        "finite_equals_source": source_size_not_smaller and len(finite_ids) == source_size,
        "parent_card_present": parent_card is not None,
        "parent_context_consistent": parent_context_consistent,
        "parent_children_declared_count": len(parent_children) if parent_card else 0,
        "parent_children_contains_raw": raw_ids <= parent_children if parent_card else False,
        "source_size_gt_five": source_size is not None and source_size > 5,
    }
    return row


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run(args: argparse.Namespace) -> int:
    source_commit = args.source_commit
    if not isinstance(source_commit, str) or not HEX40.fullmatch(source_commit):
        raise AuditError("source commit must be a full lowercase SHA-1")
    cards_path = Path(args.cards).resolve()
    run_map_path = Path(args.run_map).resolve()
    pair_paths = {role: Path(getattr(args, role)).resolve() for role in ROLES}
    input_paths = {"cards": cards_path, "run_map": run_map_path, **pair_paths}
    for path in input_paths.values():
        if not path.is_file():
            raise AuditError(f"missing input: {path}")
        credential_scan(path)

    output = Path(args.output).resolve()
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if output.exists() or staging.exists():
        raise AuditError("output and staging paths must not pre-exist")

    run_map = load_run_map(run_map_path)
    cards, children, card_rows = load_card_structure(cards_path, run_map)
    groups, pair_rows = load_pair_groups(pair_paths)
    per_parent = [audit_parent(group, cards, children) for _, group in sorted(groups.items())]
    by_role = {
        role: summarize_role([row for row in per_parent if row["role"] == role])
        for role in ROLES
    }
    endpoint_integrity = all(row["endpoint_fidelity"] for row in per_parent)
    declaration_integrity = all(row["declared_matches_finite"] for row in per_parent)
    source_metadata_integrity = all(
        row["source_size_consistent"] and row["source_size_not_smaller_than_raw"]
        for row in per_parent
    )
    raw_context_integrity = all(row["raw_context_consistent"] for row in per_parent)
    parent_metadata_integrity = all(
        row["parent_context_consistent"]
        and (not row["parent_card_present"] or row["parent_children_contains_raw"])
        for row in per_parent
    )
    endpoint_complete = all(row["finite_endpoint_coverage"] == 1.0 for row in per_parent)
    source_complete = all(
        row["source_size_consistent"]
        and row["raw_equals_source"]
        and row["finite_equals_source"]
        for row in per_parent
    )
    integrity = (
        endpoint_integrity
        and declaration_integrity
        and source_metadata_integrity
        and raw_context_integrity
        and parent_metadata_integrity
    )
    structurally_complete = integrity and endpoint_complete and source_complete
    source_size_gt_five_present = any(row["source_size_gt_five"] for row in per_parent)
    provenance_hold = structurally_complete and source_size_gt_five_present
    complete = structurally_complete and not provenance_hold
    status = (
        STATUS_COMPLETE
        if complete
        else STATUS_PROVENANCE_HOLD
        if provenance_hold
        else STATUS_FRAGMENT
        if integrity
        else STATUS_INVALID
    )
    summary = {
        "protocol": PROTOCOL,
        "status": status,
        "source_commit": source_commit,
        "scope": {
            "reads_card_code": False,
            "reads_card_observations": False,
            "uses_numeric_outcome_magnitude": False,
            "reads_outcome_availability": True,
            "reads_pair_orientation": False,
            "reads_pair_gap": False,
            "reads_first960": False,
            "gpu": 0,
            "api_calls": 0,
        },
        "card_rows": card_rows,
        "pair_rows": pair_rows,
        "parents": len(per_parent),
        "roles": by_role,
        "criteria": {
            "endpoint_fidelity_all": endpoint_integrity,
            "finite_set_declaration_all": declaration_integrity,
            "source_metadata_consistent_all": source_metadata_integrity,
            "raw_context_consistent_all": raw_context_integrity,
            "parent_metadata_consistent_all": parent_metadata_integrity,
            "finite_endpoint_coverage_all": endpoint_complete,
            "source_choice_set_retained_all": source_complete,
            "source_size_gt_five_provenance_resolved": not source_size_gt_five_present,
        },
        "choice_set_faithful_claim_allowed": complete,
        "labeled_sibling_fragment_claim_allowed": integrity,
        "source_size_gt_five_requires_provenance": source_size_gt_five_present,
        "input_sha256": {name: sha256_file(path) for name, path in input_paths.items()},
    }

    staging.mkdir(parents=True)
    try:
        write_json(staging / "summary.json", summary)
        with (staging / "per_parent.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=PER_PARENT_FIELDS)
            writer.writeheader()
            writer.writerows(per_parent)
        (staging / "command.txt").write_text(
            " ".join(sys.argv) + "\n", encoding="utf-8", newline="\n"
        )
        hashes = {
            path.name: sha256_file(path)
            for path in sorted(staging.iterdir())
            if path.is_file()
        }
        write_json(staging / "sha256_manifest.json", hashes)
        staging.replace(output)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--cards", required=True)
    result.add_argument("--run-map", required=True)
    result.add_argument("--train", required=True)
    result.add_argument("--frozen", required=True)
    result.add_argument("--extension", required=True)
    result.add_argument("--source-commit", required=True)
    result.add_argument("--output", required=True)
    return result


def main() -> int:
    try:
        return run(parser().parse_args())
    except (AuditError, OSError, json.JSONDecodeError) as exc:
        print(f"RAW_CHOICE_SET_AUDIT_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
