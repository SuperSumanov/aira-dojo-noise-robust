#!/usr/bin/env python3
"""Recover source sibling identities from parent lineage without reading outcomes."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


PROTOCOL = "source-opportunity-identity-recovery-v1"
STATUS_HIGH = "VERIFIED_HIGH_COVERAGE_SOURCE_IDENTITY_RECOVERY"
STATUS_PARTIAL = "PARTIAL_SOURCE_IDENTITY_RECOVERY"
STATUS_UNSUPPORTED = "SOURCE_IDENTITY_RECOVERY_UNSUPPORTED"
ROLES = ("train", "frozen", "extension")
HEX40 = re.compile(r"[0-9a-f]{40}")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-(?:ws-)?[A-Za-z0-9._-]{20,}|"
    rb"AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class RecoveryError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_credentials(path: Path) -> None:
    overlap = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            payload = overlap + chunk
            if CREDENTIAL.search(payload):
                raise RecoveryError(f"credential-shaped bytes refused in {path.name}")
            overlap = payload[-256:]


def required_text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise RecoveryError(f"invalid text in {where}")
    return value


def parse_bool(value: str, where: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise RecoveryError(f"invalid bool in {where}")


def load_lineage(cards_path: Path) -> tuple[dict[str, tuple[str, ...]], dict[str, set[str]], int]:
    parent_declared: dict[str, tuple[str, ...]] = {}
    retained: dict[str, set[str]] = collections.defaultdict(set)
    count = 0
    with cards_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            count += 1
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RecoveryError(f"invalid card JSON line {line_number}") from exc
            if not isinstance(value, dict):
                raise RecoveryError(f"invalid card object line {line_number}")
            card_id = required_text(value.get("id"), f"card id line {line_number}")
            if card_id in parent_declared:
                raise RecoveryError(f"duplicate card id {card_id}")
            lineage = value.get("lineage")
            if not isinstance(lineage, dict):
                raise RecoveryError(f"invalid lineage line {line_number}")
            children = lineage.get("children_ids")
            if not isinstance(children, list) or any(
                not isinstance(child, str) or not child for child in children
            ):
                raise RecoveryError(f"invalid children_ids line {line_number}")
            if len(children) != len(set(children)):
                raise RecoveryError(f"duplicate children_ids line {line_number}")
            parent_declared[card_id] = tuple(children)
            parent = lineage.get("parent_id")
            if parent is not None:
                parent = required_text(parent, f"parent line {line_number}")
                if card_id in retained[parent]:
                    raise RecoveryError(f"duplicate retained relation {card_id}")
                retained[parent].add(card_id)
    if not parent_declared:
        raise RecoveryError("empty cards input")
    return parent_declared, retained, count


def recover_rows(
    parent_csv: Path,
    parent_declared: dict[str, tuple[str, ...]],
    retained: dict[str, set[str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    with parent_csv.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "role",
            "parent",
            "source_declared_size",
            "raw_card_child_count",
            "parent_card_present",
        }
        if reader.fieldnames is None or not required <= set(reader.fieldnames):
            raise RecoveryError("parent CSV schema mismatch")
        for line_number, source in enumerate(reader, 2):
            role = required_text(source.get("role"), f"role line {line_number}")
            parent = required_text(source.get("parent"), f"parent line {line_number}")
            if role not in ROLES or (role, parent) in seen:
                raise RecoveryError(f"invalid role/parent line {line_number}")
            seen.add((role, parent))
            try:
                source_size = int(source["source_declared_size"])
                retained_count = int(source["raw_card_child_count"])
            except (TypeError, ValueError) as exc:
                raise RecoveryError(f"invalid sizes line {line_number}") from exc
            if source_size < 2 or not 0 < retained_count <= source_size:
                raise RecoveryError(f"impossible sizes line {line_number}")
            parent_present = parse_bool(source["parent_card_present"], f"line {line_number}")
            actual_retained = set(retained.get(parent, set()))
            if len(actual_retained) != retained_count:
                raise RecoveryError(f"retained count mismatch for {role}:{parent}")
            if parent_present != (parent in parent_declared):
                raise RecoveryError(f"parent presence mismatch for {role}:{parent}")
            declared = set(parent_declared[parent]) if parent_present else set()
            contains_retained = parent_present and actual_retained <= declared
            missing_expected = source_size - retained_count
            exact = (
                parent_present
                and contains_retained
                and len(declared) == source_size
                and len(declared - actual_retained) == missing_expected
            )
            incomplete = retained_count < source_size
            if not parent_present:
                reason = "ORPHAN_PARENT_CARD"
            elif not contains_retained:
                reason = "DECLARED_CHILDREN_MISS_RETAINED"
            elif len(declared) != source_size:
                reason = "DECLARED_CHILD_COUNT_DIFFERS_FROM_SOURCE_SIZE"
            elif len(declared - actual_retained) != missing_expected:
                reason = "MISSING_IDENTITY_COUNT_MISMATCH"
            else:
                reason = "EXACT_IDENTITY_RECOVERY"
            rows.append(
                {
                    "role": role,
                    "parent": parent,
                    "source_declared_size": source_size,
                    "retained_child_count": retained_count,
                    "source_incomplete": incomplete,
                    "parent_card_present": parent_present,
                    "parent_declared_child_count": len(declared),
                    "parent_contains_retained": contains_retained,
                    "exact_identity_recoverable": exact,
                    "missing_identity_count": missing_expected if exact else 0,
                    "missing_child_ids": sorted(declared - actual_retained) if exact else [],
                    "reason": reason,
                    "missing_status": "UNKNOWN" if incomplete else "NOT_APPLICABLE",
                    "missing_outcome": "UNKNOWN" if incomplete else "NOT_APPLICABLE",
                }
            )
    if not rows:
        raise RecoveryError("empty parent CSV")
    return sorted(rows, key=lambda row: (row["role"], row["parent"]))


def fraction(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def summarize(rows: list[dict[str, Any]], card_rows: int, source_commit: str) -> dict[str, Any]:
    incomplete = [row for row in rows if row["source_incomplete"]]
    controls = [
        row
        for row in rows
        if not row["source_incomplete"] and row["parent_card_present"]
    ]
    recovered = sum(bool(row["exact_identity_recoverable"]) for row in incomplete)
    control_ok = sum(bool(row["exact_identity_recoverable"]) for row in controls)
    role_summary: dict[str, Any] = {}
    for role in ROLES:
        selected = [row for row in incomplete if row["role"] == role]
        count = len(selected)
        exact = sum(bool(row["exact_identity_recoverable"]) for row in selected)
        role_summary[role] = {
            "source_incomplete_parents": count,
            "exact_identity_recoverable_parents": exact,
            "exact_identity_recovery_rate": fraction(exact, count),
            "recovered_missing_identities": sum(
                int(row["missing_identity_count"]) for row in selected
            ),
            "orphan_incomplete_parents": sum(
                not bool(row["parent_card_present"]) for row in selected
            ),
        }
    overall_rate = fraction(recovered, len(incomplete))
    control_rate = fraction(control_ok, len(controls))
    positive_control_pass = control_rate == 1.0
    high = (
        positive_control_pass
        and overall_rate is not None
        and overall_rate >= 0.80
        and role_summary["train"]["exact_identity_recovery_rate"] is not None
        and role_summary["train"]["exact_identity_recovery_rate"] >= 0.75
        and role_summary["frozen"]["exact_identity_recovery_rate"] is not None
        and role_summary["frozen"]["exact_identity_recovery_rate"] >= 0.75
    )
    status = STATUS_HIGH if high else STATUS_PARTIAL if recovered else STATUS_UNSUPPORTED
    return {
        "protocol": PROTOCOL,
        "status": status,
        "source_commit": source_commit,
        "scope": {
            "accesses_label_fields": False,
            "reads_numeric_outcomes": False,
            "reads_pair_orientation": False,
            "reads_first960": False,
            "recovers_identity_only": True,
            "claims_missing_status": False,
            "gpu": 0,
            "api_calls": 0,
        },
        "card_rows": card_rows,
        "parent_rows": len(rows),
        "source_incomplete_parents": len(incomplete),
        "exact_identity_recoverable_parents": recovered,
        "exact_identity_recovery_rate": overall_rate,
        "complete_parent_positive_controls": len(controls),
        "complete_parent_positive_controls_passed": control_ok,
        "complete_parent_positive_control_rate": control_rate,
        "roles": role_summary,
        "criteria": {
            "complete_non_orphan_control_rate_eq_1": positive_control_pass,
            "overall_recovery_rate_ge_0_80": overall_rate is not None and overall_rate >= 0.80,
            "train_recovery_rate_ge_0_75": role_summary["train"]["exact_identity_recovery_rate"] is not None
            and role_summary["train"]["exact_identity_recovery_rate"] >= 0.75,
            "frozen_recovery_rate_ge_0_75": role_summary["frozen"]["exact_identity_recovery_rate"] is not None
            and role_summary["frozen"]["exact_identity_recovery_rate"] >= 0.75,
        },
        "opportunity_identity_registry_claim_allowed": high,
        "complete_labeled_choice_set_claim_allowed": False,
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run(args: argparse.Namespace) -> int:
    source_commit = args.source_commit
    if not isinstance(source_commit, str) or not HEX40.fullmatch(source_commit):
        raise RecoveryError("source commit must be a full lowercase SHA-1")
    cards_path = Path(args.cards).resolve()
    parent_csv = Path(args.per_parent).resolve()
    for path in (cards_path, parent_csv):
        if not path.is_file():
            raise RecoveryError(f"missing input: {path}")
        scan_credentials(path)
    output = Path(args.output).resolve()
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if output.exists() or staging.exists():
        raise RecoveryError("output path already exists")
    parent_declared, retained, card_rows = load_lineage(cards_path)
    rows = recover_rows(parent_csv, parent_declared, retained)
    summary = summarize(rows, card_rows, source_commit)
    summary["input_sha256"] = {
        "cards": sha256_file(cards_path),
        "per_parent": sha256_file(parent_csv),
    }
    staging.mkdir(parents=True)
    try:
        write_json(staging / "summary.json", summary)
        with (staging / "per_parent.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
        (staging / "command.txt").write_text(
            " ".join(sys.argv) + "\n", encoding="utf-8", newline="\n"
        )
        manifest = {
            name: sha256_file(staging / name)
            for name in ("summary.json", "per_parent.jsonl", "command.txt")
        }
        write_json(staging / "sha256_manifest.json", manifest)
        for path in staging.iterdir():
            scan_credentials(path)
        staging.replace(output)
    except Exception:
        raise
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--cards", required=True)
    value.add_argument("--per-parent", required=True)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        return run(parser().parse_args())
    except RecoveryError as exc:
        print(f"SOURCE_IDENTITY_RECOVERY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
