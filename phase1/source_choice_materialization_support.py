#!/usr/bin/env python3
"""Outcome-free support gate for materializing source-choice benchmark groups."""

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
from typing import Any, Iterable


PROTOCOL = "source-choice-materialization-support-v1"
STATUS_PASS = "SOURCE_CHOICE_MATERIALIZATION_SUPPORT_FEASIBLE"
STATUS_FAIL = "INSUFFICIENT_SOURCE_CHOICE_MATERIALIZATION_SUPPORT"
ROLES = ("train", "frozen", "extension")
EXPECTED_SCOPE = {
    "code_bytes_read": False,
    "numeric_grade_read": False,
    "gap_read": False,
    "prospective_outcome_read": False,
    "hurdle_model_result_read": False,
    "raw_archive_or_journal_read": False,
    "candidate_identity_emitted": False,
    "gpu": 0,
    "api_calls": 0,
    "base_llm_updated": False,
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-(?:ws-)?[A-Za-z0-9._-]{16,}|"
    rb"hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    rb"AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|"
    rb"Bearer\s+[A-Za-z0-9._~-]{20,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
ANSWER_FIELDS = (
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
CONSTRUCTION_FIELDS = (
    "role",
    "parent",
    "task",
    "run_id",
    "source_size",
    "eligible",
    "exclusion_reasons",
)


class SupportError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def scan_file(path: Path) -> None:
    overlap = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            payload = overlap + chunk
            if CREDENTIAL.search(payload):
                raise SupportError(f"credential-shaped bytes refused in {path.name}")
            overlap = payload[-256:]


def required_text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise SupportError(f"invalid text at {where}")
    return value


def parse_bool(value: Any, where: str) -> bool:
    if value in (True, "True"):
        return True
    if value in (False, "False"):
        return False
    raise SupportError(f"invalid boolean at {where}")


def parse_int(value: Any, where: str, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise SupportError(f"invalid integer at {where}")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise SupportError(f"invalid integer at {where}") from exc
    if str(parsed) != str(value).strip() or parsed < minimum:
        raise SupportError(f"integer outside contract at {where}")
    return parsed


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def load_protocol(path: Path) -> dict[str, Any]:
    scan_file(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SupportError("invalid protocol JSON") from exc
    if not isinstance(value, dict) or value.get("protocol") != PROTOCOL:
        raise SupportError("protocol identity mismatch")
    for field in (
        "input_answerability_per_parent_sha256",
        "input_hurdle_construction_sha256",
    ):
        if not isinstance(value.get(field), str) or not SHA256.fullmatch(value[field]):
            raise SupportError(f"invalid protocol digest: {field}")
    for field in (
        "expected_answerability_rows",
        "expected_status_winners",
        "expected_identity_available_incomplete_rows",
        "minimum_materializable_status_winners",
        "minimum_train_materializable_status_winners",
        "minimum_frozen_materializable_status_winners",
        "minimum_tasks_with_materializable_status_winner",
        "minimum_tasks_with_at_least_20_materializable_status_winners",
    ):
        if isinstance(value.get(field), bool) or not isinstance(value.get(field), int) or value[field] <= 0:
            raise SupportError(f"invalid protocol integer: {field}")
    for field in (
        "minimum_materializable_status_winner_rate_all_parents",
        "minimum_code_complete_share_of_status_winners",
        "minimum_train_code_complete_share_of_status_winners",
        "minimum_frozen_code_complete_share_of_status_winners",
        "minimum_variable_arity_share",
        "maximum_dominant_task_share",
    ):
        number = value.get(field)
        if isinstance(number, bool) or not isinstance(number, (int, float)):
            raise SupportError(f"invalid protocol fraction: {field}")
        if not math.isfinite(float(number)) or not 0.0 <= float(number) <= 1.0:
            raise SupportError(f"protocol fraction outside [0,1]: {field}")
    for field in (
        "expected_construction_rows_by_role",
        "expected_eligible_construction_rows_by_role",
    ):
        counts = value.get(field)
        if not isinstance(counts, dict) or set(counts) != set(ROLES):
            raise SupportError(f"invalid role count map: {field}")
        if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in counts.values()):
            raise SupportError(f"invalid role count value: {field}")
    if sum(value["expected_construction_rows_by_role"].values()) != value[
        "expected_identity_available_incomplete_rows"
    ]:
        raise SupportError("construction row total is inconsistent")
    if value.get("allow_result_rescue") is not False:
        raise SupportError("result rescue must remain disabled")
    if value.get("require_train_frozen_parent_overlap") != 0:
        raise SupportError("train/frozen parent overlap requirement must be zero")
    if value.get("require_train_frozen_run_overlap") != 0:
        raise SupportError("train/frozen run overlap requirement must be zero")
    if value.get("scope") != EXPECTED_SCOPE:
        raise SupportError("protocol scope declaration drifted")
    return value


def load_answerability(path: Path, protocol: dict[str, Any]) -> list[dict[str, Any]]:
    if sha256_file(path) != protocol["input_answerability_per_parent_sha256"]:
        raise SupportError("answerability input SHA mismatch")
    scan_file(path)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != ANSWER_FIELDS:
            raise SupportError("answerability schema mismatch")
        for line_number, raw in enumerate(reader, 2):
            role = required_text(raw.get("role"), f"answer row {line_number}:role")
            task = required_text(raw.get("task"), f"answer row {line_number}:task")
            parent_sha = required_text(raw.get("parent_sha256"), f"answer row {line_number}:parent")
            run_sha = required_text(raw.get("run_id_sha256"), f"answer row {line_number}:run")
            if role not in ROLES or not SHA256.fullmatch(parent_sha) or not SHA256.fullmatch(run_sha):
                raise SupportError(f"invalid answer context at row {line_number}")
            key = (role, parent_sha)
            if key in seen:
                raise SupportError(f"duplicate answer parent at row {line_number}")
            seen.add(key)
            source_children = parse_int(raw.get("source_children"), f"answer row {line_number}:source", 2)
            finite_children = parse_int(raw.get("finite_children"), f"answer row {line_number}:finite", 2)
            if finite_children > source_children:
                raise SupportError(f"finite count exceeds source at row {line_number}")
            identity = parse_bool(raw.get("source_identity_available"), f"answer row {line_number}:identity")
            winner = parse_bool(raw.get("status_winner_identified"), f"answer row {line_number}:winner")
            if winner and not identity:
                raise SupportError(f"winner without source identity at row {line_number}")
            rows.append(
                {
                    "role": role,
                    "task": task,
                    "parent_sha256": parent_sha,
                    "run_id_sha256": run_sha,
                    "source_children": source_children,
                    "finite_children": finite_children,
                    "source_identity_available": identity,
                    "status_winner_identified": winner,
                }
            )
    if len(rows) != protocol["expected_answerability_rows"]:
        raise SupportError("answerability row count mismatch")
    if sum(row["status_winner_identified"] for row in rows) != protocol["expected_status_winners"]:
        raise SupportError("status winner count mismatch")
    return rows


def load_construction(path: Path, protocol: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    if sha256_file(path) != protocol["input_hurdle_construction_sha256"]:
        raise SupportError("hurdle construction input SHA mismatch")
    scan_file(path)
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    role_counts = collections.Counter()
    eligible_counts = collections.Counter()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CONSTRUCTION_FIELDS:
            raise SupportError("hurdle construction schema mismatch")
        for line_number, raw in enumerate(reader, 2):
            role = required_text(raw.get("role"), f"construction row {line_number}:role")
            parent = required_text(raw.get("parent"), f"construction row {line_number}:parent")
            task = required_text(raw.get("task"), f"construction row {line_number}:task")
            run_id = required_text(raw.get("run_id"), f"construction row {line_number}:run")
            if role not in ROLES:
                raise SupportError(f"invalid construction role at row {line_number}")
            parent_sha = hash_text(parent)
            key = (role, parent_sha)
            if key in rows:
                raise SupportError(f"duplicate construction parent at row {line_number}")
            eligible = parse_bool(raw.get("eligible"), f"construction row {line_number}:eligible")
            reasons = str(raw.get("exclusion_reasons") or "")
            if eligible and reasons:
                raise SupportError(f"eligible construction row has exclusion reason at row {line_number}")
            rows[key] = {
                "role": role,
                "task": task,
                "parent_sha256": parent_sha,
                "run_id_sha256": hash_text(run_id),
                "source_size": parse_int(raw.get("source_size"), f"construction row {line_number}:source", 2),
                "eligible": eligible,
            }
            role_counts[role] += 1
            eligible_counts[role] += int(eligible)
    actual_roles = {role: role_counts[role] for role in ROLES}
    actual_eligible = {role: eligible_counts[role] for role in ROLES}
    if actual_roles != protocol["expected_construction_rows_by_role"]:
        raise SupportError("construction role counts mismatch")
    if actual_eligible != protocol["expected_eligible_construction_rows_by_role"]:
        raise SupportError("eligible construction role counts mismatch")
    return rows


def summarize_group(rows: Iterable[dict[str, Any]], stratum: str) -> dict[str, Any]:
    values = list(rows)
    winners = [row for row in values if row["status_winner_identified"]]
    materializable = [row for row in values if row["materializable_status_winner"]]
    variable = [row for row in materializable if row["source_children"] >= 3]
    return {
        "stratum": stratum,
        "parents": len(values),
        "runs": len({row["run_id_sha256"] for row in values}),
        "tasks": len({row["task"] for row in values}),
        "status_winners": len(winners),
        "materializable_status_winners": len(materializable),
        "materializable_status_winner_rate_all_parents": ratio(len(materializable), len(values)),
        "code_complete_share_of_status_winners": ratio(len(materializable), len(winners)),
        "candidate_slots": sum(row["source_children"] for row in materializable),
        "variable_arity_materializable_winners": len(variable),
        "variable_arity_share": ratio(len(variable), len(materializable)),
    }


def build_summary(
    answer_rows: list[dict[str, Any]],
    construction: dict[tuple[str, str], dict[str, Any]],
    protocol: dict[str, Any],
    source_commit: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    joined: list[dict[str, Any]] = []
    matched_construction: set[tuple[str, str]] = set()
    for row in answer_rows:
        key = (row["role"], row["parent_sha256"])
        incomplete = row["source_children"] > row["finite_children"]
        if row["source_identity_available"] and incomplete:
            structural = construction.get(key)
            if structural is None:
                raise SupportError(f"missing construction row for {key}")
            matched_construction.add(key)
            for field in ("task", "run_id_sha256"):
                if structural[field] != row[field]:
                    raise SupportError(f"construction context mismatch for {key}:{field}")
            if structural["source_size"] != row["source_children"]:
                raise SupportError(f"construction source size mismatch for {key}")
            code_reference_complete = bool(structural["eligible"])
            source_kind = "identity_recovered_incomplete"
        elif not incomplete:
            if not row["source_identity_available"]:
                raise SupportError(f"complete source row lacks identity for {key}")
            code_reference_complete = True
            source_kind = "published_complete"
        else:
            code_reference_complete = False
            source_kind = "identity_unavailable_incomplete"
        joined.append(
            {
                **row,
                "source_kind": source_kind,
                "candidate_code_reference_complete": code_reference_complete,
                "materializable_status_winner": (
                    row["status_winner_identified"] and code_reference_complete
                ),
            }
        )
    expected_incomplete = protocol["expected_identity_available_incomplete_rows"]
    if len(matched_construction) != expected_incomplete or matched_construction != set(construction):
        raise SupportError("construction join is not one-to-one complete")

    overall = summarize_group(joined, "all")
    roles = {role: summarize_group((row for row in joined if row["role"] == role), role) for role in ROLES}
    by_task = collections.Counter(
        row["task"] for row in joined if row["materializable_status_winner"]
    )
    task_rows = [
        {
            "task": task,
            **summarize_group((row for row in joined if row["task"] == task), task),
        }
        for task in sorted({row["task"] for row in joined})
    ]
    if by_task:
        dominant_task, dominant_count = max(by_task.items(), key=lambda item: (item[1], item[0]))
    else:
        dominant_task, dominant_count = None, 0
    dominant_share = ratio(dominant_count, overall["materializable_status_winners"])
    tasks_at_least_20 = sum(count >= 20 for count in by_task.values())
    train_parent = {row["parent_sha256"] for row in joined if row["role"] == "train"}
    frozen_parent = {row["parent_sha256"] for row in joined if row["role"] == "frozen"}
    train_run = {row["run_id_sha256"] for row in joined if row["role"] == "train"}
    frozen_run = {row["run_id_sha256"] for row in joined if row["role"] == "frozen"}
    parent_overlap = len(train_parent & frozen_parent)
    run_overlap = len(train_run & frozen_run)

    criteria = {
        "materializable_status_winners_ge_minimum": overall["materializable_status_winners"]
        >= protocol["minimum_materializable_status_winners"],
        "materializable_status_winner_rate_all_parents_ge_minimum": (
            overall["materializable_status_winner_rate_all_parents"] or 0.0
        )
        >= protocol["minimum_materializable_status_winner_rate_all_parents"],
        "code_complete_share_of_status_winners_ge_minimum": (
            overall["code_complete_share_of_status_winners"] or 0.0
        )
        >= protocol["minimum_code_complete_share_of_status_winners"],
        "train_materializable_status_winners_ge_minimum": roles["train"]["materializable_status_winners"]
        >= protocol["minimum_train_materializable_status_winners"],
        "frozen_materializable_status_winners_ge_minimum": roles["frozen"]["materializable_status_winners"]
        >= protocol["minimum_frozen_materializable_status_winners"],
        "train_code_complete_share_of_status_winners_ge_minimum": (
            roles["train"]["code_complete_share_of_status_winners"] or 0.0
        )
        >= protocol["minimum_train_code_complete_share_of_status_winners"],
        "frozen_code_complete_share_of_status_winners_ge_minimum": (
            roles["frozen"]["code_complete_share_of_status_winners"] or 0.0
        )
        >= protocol["minimum_frozen_code_complete_share_of_status_winners"],
        "tasks_with_materializable_status_winner_ge_minimum": len(by_task)
        >= protocol["minimum_tasks_with_materializable_status_winner"],
        "tasks_with_at_least_20_materializable_status_winners_ge_minimum": tasks_at_least_20
        >= protocol["minimum_tasks_with_at_least_20_materializable_status_winners"],
        "variable_arity_share_ge_minimum": (overall["variable_arity_share"] or 0.0)
        >= protocol["minimum_variable_arity_share"],
        "dominant_task_share_le_maximum": (
            dominant_share if dominant_share is not None else 1.0
        )
        <= protocol["maximum_dominant_task_share"],
        "train_frozen_parent_overlap_eq_required": parent_overlap
        == protocol["require_train_frozen_parent_overlap"],
        "train_frozen_run_overlap_eq_required": run_overlap
        == protocol["require_train_frozen_run_overlap"],
    }
    claim_allowed = all(criteria.values())
    summary = {
        "protocol": PROTOCOL,
        "status": STATUS_PASS if claim_allowed else STATUS_FAIL,
        "source_commit": source_commit,
        "inputs": {
            "answerability_per_parent_sha256": protocol["input_answerability_per_parent_sha256"],
            "hurdle_construction_sha256": protocol["input_hurdle_construction_sha256"],
        },
        "scope": protocol["scope"],
        "overall": overall,
        "roles": roles,
        "support": {
            "tasks_with_materializable_status_winner": len(by_task),
            "tasks_with_at_least_20_materializable_status_winners": tasks_at_least_20,
            "dominant_task": dominant_task,
            "dominant_task_count": dominant_count,
            "dominant_task_share": dominant_share,
            "train_frozen_parent_overlap": parent_overlap,
            "train_frozen_run_overlap": run_overlap,
            "source_kinds": dict(sorted(collections.Counter(row["source_kind"] for row in joined).items())),
            "code_reference_complete_by_source_kind": dict(
                sorted(
                    collections.Counter(
                        row["source_kind"]
                        for row in joined
                        if row["candidate_code_reference_complete"]
                    ).items()
                )
            ),
        },
        "criteria": criteria,
        "materialization_s1_authorized": claim_allowed,
        "complete_v11_choice_set_claim_allowed": False,
        "predictor_or_search_utility_claim_allowed": False,
    }
    return summary, task_rows


def atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def write_task_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise SupportError("empty task output")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run(arguments: argparse.Namespace) -> int:
    if not re.fullmatch(r"[0-9a-f]{40}", arguments.source_commit):
        raise SupportError("source commit must be a full lowercase SHA-1")
    protocol_path = Path(arguments.protocol).resolve()
    answer_path = Path(arguments.answerability_per_parent).resolve()
    construction_path = Path(arguments.hurdle_construction).resolve()
    for path in (protocol_path, answer_path, construction_path):
        if not path.is_file():
            raise SupportError(f"missing input: {path.name}")
    output = Path(arguments.output).resolve()
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if output.exists() or staging.exists():
        raise SupportError("output path already exists")
    protocol = load_protocol(protocol_path)
    answer_rows = load_answerability(answer_path, protocol)
    construction = load_construction(construction_path, protocol)
    summary, task_rows = build_summary(answer_rows, construction, protocol, arguments.source_commit)
    staging.mkdir(parents=True)
    atomic_json(staging / "summary.json", summary)
    write_task_csv(staging / "per_task.csv", task_rows)
    atomic_json(
        staging / "sha256_manifest.json",
        {
            "summary.json": sha256_file(staging / "summary.json"),
            "per_task.csv": sha256_file(staging / "per_task.csv"),
        },
    )
    for path in staging.iterdir():
        scan_file(path)
    staging.replace(output)
    print(
        f"SOURCE_CHOICE_MATERIALIZATION_SUPPORT_DONE status={summary['status']} "
        f"materializable={summary['overall']['materializable_status_winners']} "
        f"coverage={summary['overall']['code_complete_share_of_status_winners']}"
    )
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--protocol", required=True)
    value.add_argument("--answerability-per-parent", required=True)
    value.add_argument("--hurdle-construction", required=True)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        return run(parser().parse_args())
    except SupportError as exc:
        print(f"SOURCE_CHOICE_MATERIALIZATION_SUPPORT_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
