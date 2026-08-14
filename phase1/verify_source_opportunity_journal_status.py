#!/usr/bin/env python3
"""Independent verifier for missing sibling journal status recovery."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


PROTOCOL = "source-opportunity-journal-status-independent-verifier-v1"
STATUS = "VERIFIED_SOURCE_OPPORTUNITY_JOURNAL_STATUS"
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-(?:ws-)?[A-Za-z0-9._-]{16,}|"
    rb"hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{16,}|"
    rb"AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer\s+[A-Za-z0-9._-]{20,}|"
    rb"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY)"
)


class VerificationError(RuntimeError):
    pass


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


def roots(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for raw in values:
        if "=" not in raw:
            raise VerificationError("root syntax")
        alias, path_text = raw.split("=", 1)
        path = Path(path_text).resolve()
        if not re.fullmatch(r"[a-z0-9_]+", alias) or alias in result or not path.is_dir():
            raise VerificationError("bad root")
        result[alias] = path
    if not result:
        raise VerificationError("no roots")
    return result


def canonical(root: Path) -> list[Path]:
    selected: dict[Path, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file() or path.name.lower() != "journal.jsonl":
            continue
        run = path.parent.parent
        current = selected.get(run)
        if current is None or (
            "checkpoint" in path.parts and "checkpoint" not in current.parts
        ):
            selected[run] = path
    return [selected[key] for key in sorted(selected, key=lambda item: item.as_posix())]


def identity_targets(path: Path) -> tuple[dict[str, dict[str, str]], int]:
    result: dict[str, dict[str, str]] = {}
    parent_count = 0
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise VerificationError(f"bad identity row {line_number}") from exc
            if not row.get("source_incomplete") or not row.get("exact_identity_recoverable"):
                continue
            parent = row.get("parent")
            role = row.get("role")
            missing = row.get("missing_child_ids")
            if not isinstance(parent, str) or role not in {"train", "frozen", "extension"}:
                raise VerificationError(f"bad target context {line_number}")
            if not isinstance(missing, list) or not missing:
                raise VerificationError(f"bad target children {line_number}")
            parent_count += 1
            for child in missing:
                if not isinstance(child, str) or not child or child in result:
                    raise VerificationError(f"bad target child {line_number}")
                result[child] = {"parent": parent, "role": role}
    if not result:
        raise VerificationError("no targets")
    return result, parent_count


def decode(blob: bytes) -> tuple[str, list[dict[str, Any]]]:
    try:
        lines = blob.decode("utf-8").splitlines()
        nodes = [json.loads(line) for line in lines if line.strip()]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError("malformed journal") from exc
    if not nodes or any(not isinstance(node, dict) for node in nodes):
        raise VerificationError("malformed journal")
    task = next(
        (
            str(node["metric_info"]["competition_id"])
            for node in nodes
            if isinstance(node.get("metric_info"), dict)
            and node["metric_info"].get("competition_id")
        ),
        None,
    )
    if not task:
        raise VerificationError("journal task absent")
    return task, nodes


def card_id(task: str, node: dict[str, Any]) -> str:
    return f"{task}__{node.get('id', node.get('step'))}"


def category(node: dict[str, Any]) -> tuple[str, bool, bool]:
    exit_code = node.get("exit_code")
    metric = node.get("metric_info") if isinstance(node.get("metric_info"), dict) else {}
    grade = metric.get("score") is not None
    threshold = any(
        metric.get(f"{name}_threshold") is not None
        for name in ("gold", "silver", "bronze")
    )
    if isinstance(exit_code, int) and not isinstance(exit_code, bool) and exit_code != 0:
        label = "EXECUTION_ERROR"
    elif exit_code == 0 and not grade:
        label = "OFFICIAL_GRADE_ABSENT"
    elif exit_code == 0 and grade and not threshold:
        label = "NORMALIZATION_METADATA_ABSENT"
    elif exit_code == 0 and grade and threshold:
        label = "UNEXPLAINED_FILTER"
    else:
        label = "EXECUTION_STATUS_UNKNOWN"
    return label, grade, threshold


def rescan(
    root_map: dict[str, Path], targets: dict[str, dict[str, str]]
) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, Any]]:
    hits: dict[str, dict[str, dict[str, Any]]] = collections.defaultdict(dict)
    stats: dict[str, Any] = {}
    credential_hashes = []
    for alias, root in sorted(root_map.items()):
        journals = canonical(root)
        parsed = matched = credential_count = malformed = 0
        for journal in journals:
            blob = journal.read_bytes()
            relative = journal.relative_to(root).as_posix()
            path_hash = digest_bytes(f"{alias}:{relative}".encode())
            if CREDENTIAL.search(blob):
                credential_count += 1
                credential_hashes.append(path_hash)
                continue
            try:
                task, nodes = decode(blob)
            except VerificationError:
                malformed += 1
                continue
            parsed += 1
            by_step = {node.get("step"): node for node in nodes}
            source_sha = digest_bytes(blob)
            found = False
            for node in nodes:
                child = card_id(task, node)
                if child not in targets:
                    continue
                parent_steps = node.get("parents") or []
                parent = None
                if isinstance(parent_steps, list) and len(parent_steps) == 1 and parent_steps[0] in by_step:
                    parent = card_id(task, by_step[parent_steps[0]])
                label, grade, threshold = category(node)
                record = {
                    "source_journal_sha256": source_sha,
                    "parent_id": parent,
                    "category": label,
                    "official_grade_present": grade,
                    "normalization_threshold_present": threshold,
                }
                previous = hits[child].get(source_sha)
                if previous is not None and previous != record:
                    raise VerificationError("same-source conflict")
                hits[child][source_sha] = record
                found = True
            if found:
                matched += 1
        stats[alias] = {
            "canonical_journals": len(journals),
            "parsed_journals": parsed,
            "target_matching_journals": matched,
            "credential_shape_journals_skipped": credential_count,
            "malformed_journals_skipped": malformed,
        }
    return hits, {"roots": stats, "credential_path_sha256": sorted(credential_hashes)}


def child_rows(
    targets: dict[str, dict[str, str]], hits: dict[str, dict[str, dict[str, Any]]]
) -> list[dict[str, Any]]:
    result = []
    for child, target in sorted(targets.items()):
        sources = hits.get(child, {})
        base = {
            "child_id": child,
            "expected_parent_id": target["parent"],
            "role": target["role"],
        }
        if not sources:
            row = {
                **base,
                "status": "SOURCE_JOURNAL_NOT_FOUND",
                "source_journal_sha256": None,
                "journal_parent_id": None,
                "parent_match": False,
                "category": "UNKNOWN",
                "official_grade_present": None,
                "normalization_threshold_present": None,
            }
        elif len(sources) > 1:
            row = {
                **base,
                "status": "SOURCE_JOURNAL_COLLISION",
                "source_journal_sha256": None,
                "journal_parent_id": None,
                "parent_match": False,
                "category": "UNKNOWN",
                "official_grade_present": None,
                "normalization_threshold_present": None,
            }
        else:
            record = next(iter(sources.values()))
            row = {
                **base,
                "status": "UNIQUE_NODE_RECOVERED",
                "source_journal_sha256": record["source_journal_sha256"],
                "journal_parent_id": record["parent_id"],
                "parent_match": record["parent_id"] == target["parent"],
                "category": record["category"],
                "official_grade_present": record["official_grade_present"],
                "normalization_threshold_present": record[
                    "normalization_threshold_present"
                ],
            }
        result.append(row)
    return result


def verify(args: argparse.Namespace) -> int:
    recovery = Path(args.status_root).resolve()
    registry = Path(args.identity_registry).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise VerificationError("output exists")
    for path in (registry, recovery / "summary.json", recovery / "per_child.jsonl"):
        if not path.is_file():
            raise VerificationError("missing input")
        reject_credentials(path)
    manifest = load_json(recovery / "sha256_manifest.json")
    for name in ("summary.json", "per_child.jsonl", "command.txt"):
        if not isinstance(manifest, dict) or manifest.get(name) != digest(recovery / name):
            raise VerificationError("producer hash mismatch")
    targets, parent_count = identity_targets(registry)
    hits, inventory = rescan(roots(args.root), targets)
    expected_rows = child_rows(targets, hits)
    actual_rows = [
        json.loads(line)
        for line in (recovery / "per_child.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if actual_rows != expected_rows:
        raise VerificationError("per-child status mismatch")
    summary = load_json(recovery / "summary.json")
    recovered = [row for row in expected_rows if row["status"] == "UNIQUE_NODE_RECOVERED"]
    collisions = sum(row["status"] == "SOURCE_JOURNAL_COLLISION" for row in expected_rows)
    mismatches = sum(not row["parent_match"] for row in recovered)
    categories = dict(sorted(collections.Counter(row["category"] for row in recovered).items()))
    if (
        summary.get("target_parents") != parent_count
        or summary.get("target_missing_identities") != len(expected_rows)
        or summary.get("unique_nodes_recovered") != len(recovered)
        or summary.get("node_recovery_rate") != len(recovered) / len(expected_rows)
        or summary.get("source_journal_collisions") != collisions
        or summary.get("journal_parent_mismatches") != mismatches
        or summary.get("categories") != categories
        or summary.get("journal_inventory") != inventory
        or summary.get("identity_registry_sha256") != digest(registry)
    ):
        raise VerificationError("producer summary mismatch")
    receipt = {
        "protocol": PROTOCOL,
        "status": STATUS,
        "producer_status": summary["status"],
        "source_commit": summary["source_commit"],
        "imports_producer": False,
        "target_missing_identities": len(expected_rows),
        "unique_nodes_recovered": len(recovered),
        "node_recovery_rate": len(recovered) / len(expected_rows),
        "source_journal_collisions": collisions,
        "journal_parent_mismatches": mismatches,
        "producer_summary_sha256": digest(recovery / "summary.json"),
        "producer_per_child_sha256": digest(recovery / "per_child.jsonl"),
        "reads_numeric_grade": False,
        "reads_first960": False,
    }
    output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    reject_credentials(output)
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--status-root", required=True)
    value.add_argument("--identity-registry", required=True)
    value.add_argument("--root", action="append", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        return verify(parser().parse_args())
    except VerificationError as exc:
        print(f"SOURCE_JOURNAL_STATUS_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
