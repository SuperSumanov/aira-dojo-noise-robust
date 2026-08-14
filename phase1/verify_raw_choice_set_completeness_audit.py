"""Independent verifier for the raw choice-set completeness audit.

This module deliberately does not import ``raw_choice_set_completeness_audit``.  It re-reads the
structural inputs, reconstructs every parent row, checks the producer hashes and manifest, and emits
a separate receipt.  Pair orientation and outcome magnitude are never used.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any


AUDIT_PROTOCOL = "raw-choice-set-completeness-v1"
VERIFY_PROTOCOL = "raw-choice-set-completeness-independent-verifier-v1"
VERIFY_STATUS = "VERIFIED_RAW_CHOICE_SET_COMPLETENESS_AUDIT"
STATUS_COMPLETE = "VERIFIED_COMPLETE_SOURCE_CHOICE_SETS"
STATUS_PROVENANCE_HOLD = "STRUCTURALLY_COMPLETE_REQUIRES_SOURCE_SIZE_PROVENANCE"
STATUS_FRAGMENT = "VERIFIED_LABELED_SIBLING_FRAGMENT_BOUNDARY"
STATUS_INVALID = "INVALID_PUBLISHED_SIBLING_STRUCTURE"
ROLES = ("train", "frozen", "extension")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-(?:ws-)?[A-Za-z0-9._-]{20,}|"
    rb"AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class VerificationError(RuntimeError):
    pass


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def reject_credentials(path: Path) -> None:
    overlap = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            payload = overlap + chunk
            if CREDENTIAL.search(payload):
                raise VerificationError(f"credential-shaped bytes refused in {path.name}")
            overlap = payload[-256:]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot parse {path.name}") from exc


def finite_available(card: dict[str, Any]) -> bool:
    try:
        value = float((card.get("label") or {}).get("graded"))
    except (TypeError, ValueError):
        return False
    return math.isfinite(value)


def text_field(row: dict[str, Any], field: str, where: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise VerificationError(f"invalid {field} in {where}")
    return value


def read_structure(
    cards_path: Path, run_map_path: Path
) -> tuple[dict[str, dict[str, Any]], dict[str, set[str]], int]:
    run_map = load_json(run_map_path)
    if not isinstance(run_map, dict):
        raise VerificationError("run map is not an object")
    cards: dict[str, dict[str, Any]] = {}
    children: dict[str, set[str]] = collections.defaultdict(set)
    count = 0
    with cards_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            count += 1
            try:
                card = json.loads(line)
            except json.JSONDecodeError as exc:
                raise VerificationError(f"bad card JSON line {line_number}") from exc
            card_id = text_field(card, "id", f"card {line_number}")
            if card_id in cards:
                raise VerificationError(f"duplicate card {card_id}")
            task_obj = card.get("task")
            lineage = card.get("lineage")
            if not isinstance(task_obj, dict) or not isinstance(lineage, dict):
                raise VerificationError(f"bad card structure line {line_number}")
            task = text_field(task_obj, "name", f"card {line_number}")
            run_id = card.get("run_id") or run_map.get(card_id)
            if not isinstance(run_id, str) or run_map.get(card_id) != run_id:
                raise VerificationError(f"run-map mismatch line {line_number}")
            parent = lineage.get("parent_id")
            if parent is not None and (not isinstance(parent, str) or not parent):
                raise VerificationError(f"bad parent line {line_number}")
            sibling_count = lineage.get("n_siblings")
            if sibling_count is not None and (
                isinstance(sibling_count, bool)
                or not isinstance(sibling_count, int)
                or sibling_count < 0
            ):
                raise VerificationError(f"bad n_siblings line {line_number}")
            declared_children = lineage.get("children_ids")
            if not isinstance(declared_children, list) or any(
                not isinstance(item, str) or not item for item in declared_children
            ):
                raise VerificationError(f"bad children_ids line {line_number}")
            if len(declared_children) != len(set(declared_children)):
                raise VerificationError(f"duplicate children_ids line {line_number}")
            cards[card_id] = {
                "task": task,
                "run": run_id,
                "parent": parent,
                "source_size": sibling_count + 1 if sibling_count is not None else None,
                "declared_children": set(declared_children),
                "finite": finite_available(card),
            }
            if parent:
                if card_id in children[parent]:
                    raise VerificationError(f"duplicate child relation for {card_id}")
                children[parent].add(card_id)
    if not cards:
        raise VerificationError("empty cards")
    return cards, children, count


def read_groups(pair_paths: dict[str, Path]) -> tuple[dict[tuple[str, str], dict[str, Any]], int]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    endpoint_role: dict[str, str] = {}
    total = 0
    for role in ROLES:
        with pair_paths[role].open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                total += 1
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise VerificationError(f"bad {role} JSON line {line_number}") from exc
                if not isinstance(row, dict) or row.get("budget") != 0:
                    raise VerificationError(f"non-b0 row in {role}:{line_number}")
                parent = text_field(row, "parent", f"{role}:{line_number}")
                left = text_field(row, "better", f"{role}:{line_number}")
                right = text_field(row, "worse", f"{role}:{line_number}")
                task = text_field(row, "task", f"{role}:{line_number}")
                run_id = text_field(row, "run_id", f"{role}:{line_number}")
                declared = row.get("set_size")
                if left == right or isinstance(declared, bool) or not isinstance(declared, int):
                    raise VerificationError(f"bad pair row in {role}:{line_number}")
                key = (role, parent)
                group = groups.setdefault(
                    key,
                    {
                        "tasks": set(),
                        "runs": set(),
                        "declared": set(),
                        "endpoints": set(),
                        "edges": set(),
                        "rows": 0,
                    },
                )
                edge = tuple(sorted((left, right)))
                if edge in group["edges"]:
                    raise VerificationError(f"duplicate edge in {role}:{parent}")
                group["tasks"].add(task)
                group["runs"].add(run_id)
                group["declared"].add(declared)
                group["endpoints"].update((left, right))
                group["edges"].add(edge)
                group["rows"] += 1
                for endpoint in (left, right):
                    previous = endpoint_role.setdefault(endpoint, role)
                    if previous != role:
                        raise VerificationError("endpoint crosses release roles")
    if not groups:
        raise VerificationError("empty pair inputs")
    return groups, total


def quotient(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def parent_row(
    role: str,
    parent: str,
    group: dict[str, Any],
    cards: dict[str, dict[str, Any]],
    children: dict[str, set[str]],
) -> dict[str, Any]:
    if any(len(group[field]) != 1 for field in ("tasks", "runs", "declared")):
        raise VerificationError(f"inconsistent context for {role}:{parent}")
    task = next(iter(group["tasks"]))
    run_id = next(iter(group["runs"]))
    declared = next(iter(group["declared"]))
    raw = set(children.get(parent, set()))
    if not raw:
        raise VerificationError(f"no retained children for {parent}")
    finite = {item for item in raw if cards[item]["finite"]}
    endpoints = set(group["endpoints"])
    raw_context = all(
        cards[item]["task"] == task
        and cards[item]["run"] == run_id
        and cards[item]["parent"] == parent
        for item in raw
    )
    endpoint_finite = endpoints <= finite
    source_values = {cards[item]["source_size"] for item in raw}
    source_consistent = len(source_values) == 1 and None not in source_values
    source_size = next(iter(source_values)) if source_consistent else None
    source_not_smaller = source_size is not None and source_size >= len(raw)
    parent_card = cards.get(parent)
    parent_context = parent_card is None or (
        parent_card["task"] == task and parent_card["run"] == run_id
    )
    parent_contains = (
        raw <= parent_card["declared_children"] if parent_card is not None else False
    )
    expected_edges = len(finite) * (len(finite) - 1) // 2
    return {
        "role": role,
        "task": task,
        "run_id": run_id,
        "parent": parent,
        "pair_rows": group["rows"],
        "unique_edges": len(group["edges"]),
        "published_endpoint_count": len(endpoints),
        "declared_set_size": declared,
        "raw_card_child_count": len(raw),
        "finite_card_child_count": len(finite),
        "source_declared_size": source_size,
        "source_size_consistent": source_consistent,
        "source_size_not_smaller_than_raw": source_not_smaller,
        "raw_context_consistent": raw_context,
        "endpoints_all_finite": endpoint_finite,
        "endpoint_fidelity": endpoint_finite and raw_context,
        "declared_matches_finite": declared == len(finite),
        "finite_endpoint_coverage": quotient(len(endpoints & finite), len(finite)),
        "pair_graph_coverage_over_finite": quotient(len(group["edges"]), expected_edges),
        "raw_source_retention": quotient(len(raw), source_size) if source_not_smaller else None,
        "finite_source_retention": (
            quotient(len(finite), source_size) if source_not_smaller else None
        ),
        "raw_equals_source": source_not_smaller and len(raw) == source_size,
        "finite_equals_source": source_not_smaller and len(finite) == source_size,
        "parent_card_present": parent_card is not None,
        "parent_context_consistent": parent_context,
        "parent_children_declared_count": (
            len(parent_card["declared_children"]) if parent_card is not None else 0
        ),
        "parent_children_contains_raw": parent_contains,
        "source_size_gt_five": source_size is not None and source_size > 5,
    }


def csv_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    return str(value)


def count_histogram(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(collections.Counter(str(row[field]) for row in rows))


def role_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
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

    def average(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    return {
        "parents": len(rows),
        "pair_rows": sum(int(row["pair_rows"]) for row in rows),
        "runs": len({row["run_id"] for row in rows}),
        "tasks": len({row["task"] for row in rows}),
        "endpoint_fidelity_parents": sum(bool(row["endpoint_fidelity"]) for row in rows),
        "declared_matches_finite_parents": sum(
            bool(row["declared_matches_finite"]) for row in rows
        ),
        "full_finite_endpoint_coverage_parents": sum(
            value == 1.0 for value in finite_coverage
        ),
        "raw_equals_source_parents": sum(bool(row["raw_equals_source"]) for row in rows),
        "finite_equals_source_parents": sum(
            bool(row["finite_equals_source"]) for row in rows
        ),
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
        "source_size_gt_five_parents": sum(
            bool(row["source_size_gt_five"]) for row in rows
        ),
        "orphan_parent_cards": sum(not bool(row["parent_card_present"]) for row in rows),
        "mean_finite_endpoint_coverage": average(finite_coverage),
        "mean_raw_source_retention": average(raw_retention),
        "mean_finite_source_retention": average(finite_retention),
        "source_declared_size_histogram": count_histogram(rows, "source_declared_size"),
        "raw_card_child_count_histogram": count_histogram(rows, "raw_card_child_count"),
        "finite_card_child_count_histogram": count_histogram(
            rows, "finite_card_child_count"
        ),
        "published_endpoint_count_histogram": count_histogram(
            rows, "published_endpoint_count"
        ),
    }


def compare_parent_csv(path: Path, expected: list[dict[str, Any]]) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        actual_rows = list(reader)
    if len(actual_rows) != len(expected):
        raise VerificationError("per_parent row count mismatch")
    actual_by_key: dict[tuple[str, str], dict[str, str]] = {}
    for row in actual_rows:
        key = (row.get("role", ""), row.get("parent", ""))
        if key in actual_by_key:
            raise VerificationError("duplicate per_parent key")
        actual_by_key[key] = row
    for expected_row in expected:
        key = (expected_row["role"], expected_row["parent"])
        actual = actual_by_key.get(key)
        if actual is None:
            raise VerificationError(f"missing per_parent row {key}")
        if set(actual) != set(expected_row):
            raise VerificationError(f"per_parent columns mismatch at {key}")
        for field, value in expected_row.items():
            if actual[field] != csv_text(value):
                raise VerificationError(f"per_parent mismatch at {key}:{field}")


def expected_verdict(rows: list[dict[str, Any]]) -> tuple[str, dict[str, bool]]:
    endpoint = all(row["endpoint_fidelity"] for row in rows)
    declared = all(row["declared_matches_finite"] for row in rows)
    source_metadata = all(
        row["source_size_consistent"] and row["source_size_not_smaller_than_raw"]
        for row in rows
    )
    raw_context = all(row["raw_context_consistent"] for row in rows)
    parent_metadata = all(
        row["parent_context_consistent"]
        and (not row["parent_card_present"] or row["parent_children_contains_raw"])
        for row in rows
    )
    endpoint_complete = all(row["finite_endpoint_coverage"] == 1.0 for row in rows)
    source_complete = all(
        row["source_size_consistent"]
        and row["raw_equals_source"]
        and row["finite_equals_source"]
        for row in rows
    )
    source_gt_five = any(row["source_size_gt_five"] for row in rows)
    integrity = endpoint and declared and source_metadata and raw_context and parent_metadata
    structural_complete = integrity and endpoint_complete and source_complete
    status = (
        STATUS_COMPLETE
        if structural_complete and not source_gt_five
        else STATUS_PROVENANCE_HOLD
        if structural_complete
        else STATUS_FRAGMENT
        if integrity
        else STATUS_INVALID
    )
    return status, {
        "endpoint_fidelity_all": endpoint,
        "finite_set_declaration_all": declared,
        "source_metadata_consistent_all": source_metadata,
        "raw_context_consistent_all": raw_context,
        "parent_metadata_consistent_all": parent_metadata,
        "finite_endpoint_coverage_all": endpoint_complete,
        "source_choice_set_retained_all": source_complete,
        "source_size_gt_five_provenance_resolved": not source_gt_five,
    }


def verify(args: argparse.Namespace) -> int:
    audit_root = Path(args.audit_root).resolve()
    summary_path = audit_root / "summary.json"
    parent_path = audit_root / "per_parent.csv"
    manifest_path = audit_root / "sha256_manifest.json"
    command_path = audit_root / "command.txt"
    cards_path = Path(args.cards).resolve()
    run_map_path = Path(args.run_map).resolve()
    pair_paths = {role: Path(getattr(args, role)).resolve() for role in ROLES}
    output_path = Path(args.output).resolve()
    paths = [
        cards_path,
        run_map_path,
        *pair_paths.values(),
        summary_path,
        parent_path,
        manifest_path,
        command_path,
    ]
    if output_path.exists():
        raise VerificationError("verification output already exists")
    for path in paths:
        if not path.is_file():
            raise VerificationError(f"missing input {path}")
        reject_credentials(path)

    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        raise VerificationError("invalid producer manifest")
    for path in (summary_path, parent_path, command_path):
        if manifest.get(path.name) != digest(path):
            raise VerificationError(f"producer manifest mismatch for {path.name}")

    cards, children, card_count = read_structure(cards_path, run_map_path)
    groups, pair_count = read_groups(pair_paths)
    rows = [
        parent_row(role, parent, group, cards, children)
        for (role, parent), group in sorted(groups.items())
    ]
    compare_parent_csv(parent_path, rows)
    expected_status, criteria = expected_verdict(rows)
    summary = load_json(summary_path)
    if not isinstance(summary, dict) or summary.get("protocol") != AUDIT_PROTOCOL:
        raise VerificationError("wrong audit protocol")
    if summary.get("status") != expected_status:
        raise VerificationError("summary status mismatch")
    if summary.get("criteria") != criteria:
        raise VerificationError("summary criteria mismatch")
    if summary.get("card_rows") != card_count or summary.get("pair_rows") != pair_count:
        raise VerificationError("summary row count mismatch")
    if summary.get("parents") != len(rows):
        raise VerificationError("summary parent count mismatch")
    expected_roles = {
        role: role_summary([row for row in rows if row["role"] == role]) for role in ROLES
    }
    if summary.get("roles") != expected_roles:
        raise VerificationError("summary role aggregates mismatch")
    input_paths = {"cards": cards_path, "run_map": run_map_path, **pair_paths}
    input_hashes = {name: digest(path) for name, path in input_paths.items()}
    if summary.get("input_sha256") != input_hashes:
        raise VerificationError("summary input hashes mismatch")
    claim_allowed = expected_status == STATUS_COMPLETE
    if summary.get("choice_set_faithful_claim_allowed") is not claim_allowed:
        raise VerificationError("choice-set claim flag mismatch")
    integrity = expected_status != STATUS_INVALID
    if summary.get("labeled_sibling_fragment_claim_allowed") is not integrity:
        raise VerificationError("fragment claim flag mismatch")
    source_gt_five = any(row["source_size_gt_five"] for row in rows)
    if summary.get("source_size_gt_five_requires_provenance") is not source_gt_five:
        raise VerificationError("source-size provenance flag mismatch")
    scope = summary.get("scope")
    required_scope = {
        "reads_card_code": False,
        "reads_card_observations": False,
        "uses_numeric_outcome_magnitude": False,
        "reads_outcome_availability": True,
        "reads_pair_orientation": False,
        "reads_pair_gap": False,
        "reads_first960": False,
        "gpu": 0,
        "api_calls": 0,
    }
    if scope != required_scope:
        raise VerificationError("producer scope declaration mismatch")

    receipt = {
        "protocol": VERIFY_PROTOCOL,
        "status": VERIFY_STATUS,
        "producer_protocol": AUDIT_PROTOCOL,
        "producer_status": expected_status,
        "producer_summary_sha256": digest(summary_path),
        "producer_per_parent_sha256": digest(parent_path),
        "source_commit": summary.get("source_commit"),
        "card_rows": card_count,
        "pair_rows": pair_count,
        "parents": len(rows),
        "criteria_recomputed": criteria,
        "input_sha256_recomputed": input_hashes,
        "choice_set_faithful_claim_allowed": claim_allowed,
        "reads_pair_orientation": False,
        "uses_numeric_outcome_magnitude": False,
        "reads_first960": False,
        "imports_producer": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--audit-root", required=True)
    result.add_argument("--cards", required=True)
    result.add_argument("--run-map", required=True)
    result.add_argument("--train", required=True)
    result.add_argument("--frozen", required=True)
    result.add_argument("--extension", required=True)
    result.add_argument("--output", required=True)
    return result


def main() -> int:
    try:
        return verify(parser().parse_args())
    except (VerificationError, OSError, json.JSONDecodeError) as exc:
        print(f"RAW_CHOICE_SET_VERIFICATION_ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
