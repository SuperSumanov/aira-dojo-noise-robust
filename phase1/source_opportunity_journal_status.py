#!/usr/bin/env python3
"""Recover execution/evaluation availability for missing sibling identities."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


PROTOCOL = "source-opportunity-journal-status-v1"
STATUS_HIGH = "VERIFIED_HIGH_COVERAGE_MISSING_STATUS_REGISTRY"
STATUS_PARTIAL = "PARTIAL_MISSING_STATUS_REGISTRY"
STATUS_UNSUPPORTED = "MISSING_STATUS_REGISTRY_UNSUPPORTED"
HEX40 = re.compile(r"[0-9a-f]{40}")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-(?:ws-)?[A-Za-z0-9._-]{16,}|"
    rb"hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{16,}|"
    rb"AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer\s+[A-Za-z0-9._-]{20,}|"
    rb"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY)"
)


class StatusError(RuntimeError):
    pass


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_file(path: Path) -> None:
    overlap = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            payload = overlap + chunk
            if CREDENTIAL.search(payload):
                raise StatusError(f"credential-shaped bytes refused in {path.name}")
            overlap = payload[-256:]


def parse_roots(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise StatusError("root must be ALIAS=PATH")
        alias, raw_path = value.split("=", 1)
        if not re.fullmatch(r"[a-z0-9_]+", alias) or alias in result:
            raise StatusError("root alias is invalid or duplicated")
        path = Path(raw_path).resolve()
        if not path.is_dir():
            raise StatusError(f"root is not a directory: {alias}")
        result[alias] = path
    if not result:
        raise StatusError("no journal roots")
    return result


def canonical_journals(root: Path) -> list[Path]:
    by_run: dict[Path, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file() or path.name.lower() != "journal.jsonl":
            continue
        run_dir = path.parent.parent
        current = by_run.get(run_dir)
        if current is None or (
            "checkpoint" in path.parts and "checkpoint" not in current.parts
        ):
            by_run[run_dir] = path
    return [by_run[key] for key in sorted(by_run, key=lambda item: item.as_posix())]


def load_targets(path: Path) -> tuple[dict[str, dict[str, str]], int]:
    targets: dict[str, dict[str, str]] = {}
    parents = 0
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise StatusError(f"invalid identity registry line {line_number}") from exc
            if not isinstance(row, dict):
                raise StatusError(f"invalid identity row {line_number}")
            if not row.get("source_incomplete") or not row.get("exact_identity_recoverable"):
                continue
            parent = row.get("parent")
            role = row.get("role")
            missing = row.get("missing_child_ids")
            if not isinstance(parent, str) or not parent or role not in {
                "train",
                "frozen",
                "extension",
            }:
                raise StatusError(f"invalid target context line {line_number}")
            if not isinstance(missing, list) or not missing:
                raise StatusError(f"invalid missing identities line {line_number}")
            parents += 1
            for child in missing:
                if not isinstance(child, str) or not child or child in targets:
                    raise StatusError(f"duplicate/invalid target child line {line_number}")
                targets[child] = {"parent": parent, "role": role}
    if not targets:
        raise StatusError("identity registry has no recoverable missing targets")
    return targets, parents


def decode_journal(blob: bytes, where: str) -> tuple[str, list[dict[str, Any]]]:
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StatusError(f"journal is not UTF-8: {where}") from exc
    nodes: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            node = json.loads(line)
        except json.JSONDecodeError as exc:
            raise StatusError(f"invalid journal JSON {where}:{line_number}") from exc
        if not isinstance(node, dict):
            raise StatusError(f"journal row is not an object {where}:{line_number}")
        nodes.append(node)
    task = next(
        (
            str((node.get("metric_info") or {})["competition_id"])
            for node in nodes
            if isinstance(node.get("metric_info"), dict)
            and (node.get("metric_info") or {}).get("competition_id")
        ),
        None,
    )
    if not nodes or not task:
        raise StatusError(f"journal has no nodes/task: {where}")
    return task, nodes


def node_card_id(task: str, node: dict[str, Any]) -> str:
    raw = node.get("id", node.get("step"))
    return f"{task}__{raw}"


def classify(node: dict[str, Any]) -> tuple[str, bool, bool]:
    exit_code = node.get("exit_code")
    metric = node.get("metric_info")
    metric = metric if isinstance(metric, dict) else {}
    grade_present = metric.get("score") is not None
    thresholds_present = any(
        metric.get(f"{name}_threshold") is not None
        for name in ("gold", "silver", "bronze")
    )
    if isinstance(exit_code, int) and not isinstance(exit_code, bool) and exit_code != 0:
        category = "EXECUTION_ERROR"
    elif exit_code == 0 and not grade_present:
        category = "OFFICIAL_GRADE_ABSENT"
    elif exit_code == 0 and grade_present and not thresholds_present:
        category = "NORMALIZATION_METADATA_ABSENT"
    elif exit_code == 0 and grade_present and thresholds_present:
        category = "UNEXPLAINED_FILTER"
    else:
        category = "EXECUTION_STATUS_UNKNOWN"
    return category, grade_present, thresholds_present


def scan_roots(
    roots: dict[str, Path], targets: dict[str, dict[str, str]]
) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, Any]]:
    hits: dict[str, dict[str, dict[str, Any]]] = collections.defaultdict(dict)
    root_stats: dict[str, Any] = {}
    credential_hashes: list[str] = []
    for alias, root in sorted(roots.items()):
        journals = canonical_journals(root)
        parsed = matched = credentials = malformed = 0
        for journal in journals:
            blob = journal.read_bytes()
            relative = journal.relative_to(root).as_posix()
            path_hash = sha256_bytes(f"{alias}:{relative}".encode("utf-8"))
            if CREDENTIAL.search(blob):
                credentials += 1
                credential_hashes.append(path_hash)
                continue
            try:
                task, nodes = decode_journal(blob, path_hash)
            except StatusError:
                malformed += 1
                continue
            parsed += 1
            by_step = {node.get("step"): node for node in nodes}
            journal_sha = sha256_bytes(blob)
            journal_matched = False
            for node in nodes:
                child_id = node_card_id(task, node)
                if child_id not in targets:
                    continue
                parents = node.get("parents") or []
                parent_id = None
                if isinstance(parents, list) and len(parents) == 1 and parents[0] in by_step:
                    parent_id = node_card_id(task, by_step[parents[0]])
                category, grade_present, thresholds_present = classify(node)
                record = {
                    "source_journal_sha256": journal_sha,
                    "journal_path_sha256": path_hash,
                    "parent_id": parent_id,
                    "category": category,
                    "official_grade_present": grade_present,
                    "normalization_threshold_present": thresholds_present,
                }
                previous = hits[child_id].get(journal_sha)
                if previous is not None and previous != record:
                    raise StatusError(f"same journal SHA yields conflicting child {child_id}")
                hits[child_id][journal_sha] = record
                journal_matched = True
            if journal_matched:
                matched += 1
        root_stats[alias] = {
            "canonical_journals": len(journals),
            "parsed_journals": parsed,
            "target_matching_journals": matched,
            "credential_shape_journals_skipped": credentials,
            "malformed_journals_skipped": malformed,
        }
    return hits, {
        "roots": root_stats,
        "credential_path_sha256": sorted(credential_hashes),
    }


def build_rows(
    targets: dict[str, dict[str, str]],
    hits: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows = []
    for child, target in sorted(targets.items()):
        candidates = hits.get(child, {})
        if len(candidates) == 0:
            row = {
                "child_id": child,
                "expected_parent_id": target["parent"],
                "role": target["role"],
                "status": "SOURCE_JOURNAL_NOT_FOUND",
                "source_journal_sha256": None,
                "journal_parent_id": None,
                "parent_match": False,
                "category": "UNKNOWN",
                "official_grade_present": None,
                "normalization_threshold_present": None,
            }
        elif len(candidates) > 1:
            row = {
                "child_id": child,
                "expected_parent_id": target["parent"],
                "role": target["role"],
                "status": "SOURCE_JOURNAL_COLLISION",
                "source_journal_sha256": None,
                "journal_parent_id": None,
                "parent_match": False,
                "category": "UNKNOWN",
                "official_grade_present": None,
                "normalization_threshold_present": None,
            }
        else:
            record = next(iter(candidates.values()))
            parent_match = record["parent_id"] == target["parent"]
            row = {
                "child_id": child,
                "expected_parent_id": target["parent"],
                "role": target["role"],
                "status": "UNIQUE_NODE_RECOVERED",
                "source_journal_sha256": record["source_journal_sha256"],
                "journal_parent_id": record["parent_id"],
                "parent_match": parent_match,
                "category": record["category"],
                "official_grade_present": record["official_grade_present"],
                "normalization_threshold_present": record[
                    "normalization_threshold_present"
                ],
            }
        rows.append(row)
    return rows


def summarize(
    rows: list[dict[str, Any]], parent_targets: int, inventory: dict[str, Any]
) -> dict[str, Any]:
    recovered = [row for row in rows if row["status"] == "UNIQUE_NODE_RECOVERED"]
    collisions = sum(row["status"] == "SOURCE_JOURNAL_COLLISION" for row in rows)
    parent_mismatch = sum(not row["parent_match"] for row in recovered)
    recovery_rate = len(recovered) / len(rows)
    categories = collections.Counter(row["category"] for row in recovered)
    roles: dict[str, Any] = {}
    for role in ("train", "frozen", "extension"):
        selected = [row for row in rows if row["role"] == role]
        selected_recovered = [
            row for row in selected if row["status"] == "UNIQUE_NODE_RECOVERED"
        ]
        roles[role] = {
            "target_missing_identities": len(selected),
            "unique_nodes_recovered": len(selected_recovered),
            "node_recovery_rate": len(selected_recovered) / len(selected) if selected else None,
            "parent_mismatches": sum(not row["parent_match"] for row in selected_recovered),
            "categories": dict(
                sorted(collections.Counter(row["category"] for row in selected_recovered).items())
            ),
        }
    high = recovery_rate >= 0.80 and collisions == 0 and parent_mismatch == 0
    status = STATUS_HIGH if high else STATUS_PARTIAL if recovered and collisions == 0 else STATUS_UNSUPPORTED
    return {
        "protocol": PROTOCOL,
        "status": status,
        "scope": {
            "reads_numeric_grade": False,
            "records_code_or_stdout": False,
            "reads_pair_orientation": False,
            "reads_first960": False,
            "reads_env_or_tar_other_members": False,
            "gpu": 0,
            "api_calls": 0,
        },
        "target_parents": parent_targets,
        "target_missing_identities": len(rows),
        "unique_nodes_recovered": len(recovered),
        "node_recovery_rate": recovery_rate,
        "source_journal_collisions": collisions,
        "journal_parent_mismatches": parent_mismatch,
        "categories": dict(sorted(categories.items())),
        "roles": roles,
        "journal_inventory": inventory,
        "criteria": {
            "node_recovery_rate_ge_0_80": recovery_rate >= 0.80,
            "source_journal_collisions_eq_0": collisions == 0,
            "journal_parent_mismatches_eq_0": parent_mismatch == 0,
        },
        "missing_status_registry_claim_allowed": high,
        "missing_at_random_claim_allowed": False,
        "complete_labeled_choice_set_claim_allowed": False,
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run(args: argparse.Namespace) -> int:
    if not isinstance(args.source_commit, str) or not HEX40.fullmatch(args.source_commit):
        raise StatusError("source commit must be a full lowercase SHA-1")
    registry = Path(args.identity_registry).resolve()
    if not registry.is_file():
        raise StatusError("identity registry missing")
    scan_file(registry)
    roots = parse_roots(args.root)
    output = Path(args.output).resolve()
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if output.exists() or staging.exists():
        raise StatusError("output already exists")
    targets, parent_targets = load_targets(registry)
    hits, inventory = scan_roots(roots, targets)
    rows = build_rows(targets, hits)
    summary = summarize(rows, parent_targets, inventory)
    summary["source_commit"] = args.source_commit
    summary["identity_registry_sha256"] = sha256_file(registry)
    staging.mkdir(parents=True)
    write_json(staging / "summary.json", summary)
    with (staging / "per_child.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    (staging / "command.txt").write_text(
        " ".join(sys.argv) + "\n", encoding="utf-8", newline="\n"
    )
    manifest = {
        name: sha256_file(staging / name)
        for name in ("summary.json", "per_child.jsonl", "command.txt")
    }
    write_json(staging / "sha256_manifest.json", manifest)
    for path in staging.iterdir():
        scan_file(path)
    staging.replace(output)
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--identity-registry", required=True)
    value.add_argument("--root", action="append", required=True)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        return run(parser().parse_args())
    except StatusError as exc:
        print(f"SOURCE_JOURNAL_STATUS_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
