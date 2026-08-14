#!/usr/bin/env python3
"""Independent verifier for source opportunity identity recovery."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


PRODUCER_PROTOCOL = "source-opportunity-identity-recovery-v1"
PROTOCOL = "source-opportunity-identity-recovery-independent-verifier-v1"
STATUS = "VERIFIED_SOURCE_OPPORTUNITY_IDENTITY_RECOVERY"
HIGH = "VERIFIED_HIGH_COVERAGE_SOURCE_IDENTITY_RECOVERY"
PARTIAL = "PARTIAL_SOURCE_IDENTITY_RECOVERY"
UNSUPPORTED = "SOURCE_IDENTITY_RECOVERY_UNSUPPORTED"
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


def parse_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot parse {path.name}") from exc


def text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise VerificationError(f"bad text in {where}")
    return value


def boolean(value: str, where: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise VerificationError(f"bad bool in {where}")


def read_cards(path: Path) -> tuple[dict[str, set[str]], dict[str, set[str]], int]:
    declared: dict[str, set[str]] = {}
    retained: dict[str, set[str]] = collections.defaultdict(set)
    count = 0
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            count += 1
            try:
                card = json.loads(line)
            except json.JSONDecodeError as exc:
                raise VerificationError(f"bad card line {line_number}") from exc
            card_id = text(card.get("id"), f"card {line_number}")
            lineage = card.get("lineage")
            if card_id in declared or not isinstance(lineage, dict):
                raise VerificationError(f"bad lineage line {line_number}")
            child_list = lineage.get("children_ids")
            if not isinstance(child_list, list) or any(
                not isinstance(item, str) or not item for item in child_list
            ):
                raise VerificationError(f"bad children line {line_number}")
            if len(child_list) != len(set(child_list)):
                raise VerificationError(f"duplicate children line {line_number}")
            declared[card_id] = set(child_list)
            parent = lineage.get("parent_id")
            if parent is not None:
                parent = text(parent, f"parent {line_number}")
                if card_id in retained[parent]:
                    raise VerificationError(f"duplicate relation {card_id}")
                retained[parent].add(card_id)
    if not declared:
        raise VerificationError("empty cards")
    return declared, retained, count


def expected_rows(
    path: Path, declared: dict[str, set[str]], retained: dict[str, set[str]]
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    keys: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        needed = {
            "role",
            "parent",
            "source_declared_size",
            "raw_card_child_count",
            "parent_card_present",
        }
        if reader.fieldnames is None or not needed <= set(reader.fieldnames):
            raise VerificationError("parent CSV schema mismatch")
        for line_number, source in enumerate(reader, 2):
            role = text(source.get("role"), f"role {line_number}")
            parent = text(source.get("parent"), f"parent {line_number}")
            if role not in ROLES or (role, parent) in keys:
                raise VerificationError(f"bad key line {line_number}")
            keys.add((role, parent))
            try:
                source_count = int(source["source_declared_size"])
                retained_count = int(source["raw_card_child_count"])
            except (TypeError, ValueError) as exc:
                raise VerificationError(f"bad counts line {line_number}") from exc
            parent_present = boolean(source["parent_card_present"], f"line {line_number}")
            raw = set(retained.get(parent, set()))
            if len(raw) != retained_count or parent_present != (parent in declared):
                raise VerificationError(f"upstream mismatch {role}:{parent}")
            parent_children = declared[parent] if parent_present else set()
            contains = parent_present and raw <= parent_children
            expected_missing = source_count - retained_count
            exact = (
                parent_present
                and contains
                and len(parent_children) == source_count
                and len(parent_children - raw) == expected_missing
            )
            incomplete = retained_count < source_count
            if not parent_present:
                reason = "ORPHAN_PARENT_CARD"
            elif not contains:
                reason = "DECLARED_CHILDREN_MISS_RETAINED"
            elif len(parent_children) != source_count:
                reason = "DECLARED_CHILD_COUNT_DIFFERS_FROM_SOURCE_SIZE"
            elif len(parent_children - raw) != expected_missing:
                reason = "MISSING_IDENTITY_COUNT_MISMATCH"
            else:
                reason = "EXACT_IDENTITY_RECOVERY"
            result.append(
                {
                    "role": role,
                    "parent": parent,
                    "source_declared_size": source_count,
                    "retained_child_count": retained_count,
                    "source_incomplete": incomplete,
                    "parent_card_present": parent_present,
                    "parent_declared_child_count": len(parent_children),
                    "parent_contains_retained": contains,
                    "exact_identity_recoverable": exact,
                    "missing_identity_count": expected_missing if exact else 0,
                    "missing_child_ids": sorted(parent_children - raw) if exact else [],
                    "reason": reason,
                    "missing_status": "UNKNOWN" if incomplete else "NOT_APPLICABLE",
                    "missing_outcome": "UNKNOWN" if incomplete else "NOT_APPLICABLE",
                }
            )
    if not result:
        raise VerificationError("empty parent rows")
    return sorted(result, key=lambda row: (row["role"], row["parent"]))


def rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def expected_summary(
    rows: list[dict[str, Any]], card_rows: int, source_commit: str
) -> dict[str, Any]:
    incomplete = [row for row in rows if row["source_incomplete"]]
    controls = [row for row in rows if not row["source_incomplete"] and row["parent_card_present"]]
    recovered = sum(row["exact_identity_recoverable"] for row in incomplete)
    control_pass = sum(row["exact_identity_recoverable"] for row in controls)
    roles: dict[str, Any] = {}
    for role in ROLES:
        selected = [row for row in incomplete if row["role"] == role]
        exact = sum(row["exact_identity_recoverable"] for row in selected)
        roles[role] = {
            "source_incomplete_parents": len(selected),
            "exact_identity_recoverable_parents": exact,
            "exact_identity_recovery_rate": rate(exact, len(selected)),
            "recovered_missing_identities": sum(row["missing_identity_count"] for row in selected),
            "orphan_incomplete_parents": sum(not row["parent_card_present"] for row in selected),
        }
    overall = rate(recovered, len(incomplete))
    control = rate(control_pass, len(controls))
    control_ok = control == 1.0
    train_rate = roles["train"]["exact_identity_recovery_rate"]
    frozen_rate = roles["frozen"]["exact_identity_recovery_rate"]
    high = (
        control_ok
        and overall is not None
        and overall >= 0.80
        and train_rate is not None
        and train_rate >= 0.75
        and frozen_rate is not None
        and frozen_rate >= 0.75
    )
    status = HIGH if high else PARTIAL if recovered else UNSUPPORTED
    return {
        "protocol": PRODUCER_PROTOCOL,
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
        "exact_identity_recovery_rate": overall,
        "complete_parent_positive_controls": len(controls),
        "complete_parent_positive_controls_passed": control_pass,
        "complete_parent_positive_control_rate": control,
        "roles": roles,
        "criteria": {
            "complete_non_orphan_control_rate_eq_1": control_ok,
            "overall_recovery_rate_ge_0_80": overall is not None and overall >= 0.80,
            "train_recovery_rate_ge_0_75": train_rate is not None and train_rate >= 0.75,
            "frozen_recovery_rate_ge_0_75": frozen_rate is not None and frozen_rate >= 0.75,
        },
        "opportunity_identity_registry_claim_allowed": high,
        "complete_labeled_choice_set_claim_allowed": False,
    }


def verify(args: argparse.Namespace) -> int:
    root = Path(args.recovery_root).resolve()
    cards = Path(args.cards).resolve()
    parent_csv = Path(args.per_parent).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise VerificationError("output exists")
    for path in (cards, parent_csv, root / "summary.json", root / "per_parent.jsonl"):
        if not path.is_file():
            raise VerificationError(f"missing input {path}")
        reject_credentials(path)
    manifest = parse_json(root / "sha256_manifest.json")
    if not isinstance(manifest, dict):
        raise VerificationError("bad producer manifest")
    for name in ("summary.json", "per_parent.jsonl", "command.txt"):
        if manifest.get(name) != digest(root / name):
            raise VerificationError(f"producer hash mismatch for {name}")
    summary = parse_json(root / "summary.json")
    declared, retained, card_count = read_cards(cards)
    rows = expected_rows(parent_csv, declared, retained)
    actual_rows = [
        json.loads(line)
        for line in (root / "per_parent.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if actual_rows != rows:
        raise VerificationError("per-parent identity recovery mismatch")
    source_commit = summary.get("source_commit")
    if not isinstance(source_commit, str):
        raise VerificationError("missing source commit")
    expected = expected_summary(rows, card_count, source_commit)
    expected["input_sha256"] = {"cards": digest(cards), "per_parent": digest(parent_csv)}
    if summary != expected:
        raise VerificationError("producer summary mismatch")
    receipt = {
        "protocol": PROTOCOL,
        "status": STATUS,
        "producer_protocol": summary["protocol"],
        "producer_status": summary["status"],
        "source_commit": source_commit,
        "imports_producer": False,
        "parent_rows": len(rows),
        "source_incomplete_parents": summary["source_incomplete_parents"],
        "exact_identity_recoverable_parents": summary["exact_identity_recoverable_parents"],
        "exact_identity_recovery_rate": summary["exact_identity_recovery_rate"],
        "producer_summary_sha256": digest(root / "summary.json"),
        "producer_per_parent_sha256": digest(root / "per_parent.jsonl"),
        "reads_first960": False,
        "reads_numeric_outcomes": False,
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
    value.add_argument("--recovery-root", required=True)
    value.add_argument("--cards", required=True)
    value.add_argument("--per-parent", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        return verify(parser().parse_args())
    except VerificationError as exc:
        print(f"SOURCE_IDENTITY_VERIFICATION_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
