#!/usr/bin/env python3
"""Independent reconstruction for source-choice materialization support."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any


PROTOCOL = "source-choice-materialization-support-v1"
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
    "role", "task", "run_id_sha256", "parent_sha256", "source_children",
    "finite_children", "source_identity_available", "missing_identity_children",
    "certified_invalid_children", "unknown_source_children", "published_direct_relations",
    "status_direct_relations", "execution_only_direct_relations",
    "published_transitive_relations", "status_transitive_relations",
    "execution_only_transitive_relations", "published_top_set_size",
    "status_top_set_size", "execution_only_top_set_size", "published_winner_identified",
    "status_winner_identified", "execution_only_winner_identified",
    "newly_identified_by_status", "newly_identified_execution_only",
)
CONSTRUCTION_FIELDS = (
    "role", "parent", "task", "run_id", "source_size", "eligible", "exclusion_reasons",
)


class VerificationError(RuntimeError):
    pass


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def hashed(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def reject_credentials(path: Path) -> None:
    previous = b""
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            payload = previous + chunk
            if CREDENTIAL.search(payload):
                raise VerificationError(f"credential shape in {path.name}")
            previous = payload[-256:]


def text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise VerificationError(f"invalid text: {where}")
    return value


def boolean(value: Any, where: str) -> bool:
    if value in (True, "True"):
        return True
    if value in (False, "False"):
        return False
    raise VerificationError(f"invalid bool: {where}")


def integer(value: Any, where: str, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise VerificationError(f"invalid integer: {where}")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise VerificationError(f"invalid integer: {where}") from exc
    if str(parsed) != str(value).strip() or parsed < minimum:
        raise VerificationError(f"integer outside contract: {where}")
    return parsed


def fraction(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def read_protocol(path: Path) -> dict[str, Any]:
    reject_credentials(path)
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerificationError("protocol JSON invalid") from exc
    if not isinstance(result, dict) or result.get("protocol") != PROTOCOL:
        raise VerificationError("protocol mismatch")
    if result.get("allow_result_rescue") is not False:
        raise VerificationError("protocol permits result rescue")
    if result.get("require_train_frozen_parent_overlap") != 0:
        raise VerificationError("parent overlap requirement is not zero")
    if result.get("require_train_frozen_run_overlap") != 0:
        raise VerificationError("run overlap requirement is not zero")
    if result.get("scope") != EXPECTED_SCOPE:
        raise VerificationError("protocol scope drifted")
    for name in ("input_answerability_per_parent_sha256", "input_hurdle_construction_sha256"):
        if not isinstance(result.get(name), str) or not SHA256.fullmatch(result[name]):
            raise VerificationError(f"bad digest declaration: {name}")
    for name in (
        "minimum_materializable_status_winner_rate_all_parents",
        "minimum_code_complete_share_of_status_winners",
        "minimum_train_code_complete_share_of_status_winners",
        "minimum_frozen_code_complete_share_of_status_winners",
        "minimum_variable_arity_share",
        "maximum_dominant_task_share",
    ):
        number = result.get(name)
        if isinstance(number, bool) or not isinstance(number, (int, float)):
            raise VerificationError(f"bad fraction declaration: {name}")
        if not math.isfinite(float(number)) or not 0 <= float(number) <= 1:
            raise VerificationError(f"fraction outside range: {name}")
    for name in (
        "expected_answerability_rows",
        "expected_status_winners",
        "expected_identity_available_incomplete_rows",
        "minimum_materializable_status_winners",
        "minimum_train_materializable_status_winners",
        "minimum_frozen_materializable_status_winners",
        "minimum_tasks_with_materializable_status_winner",
        "minimum_tasks_with_at_least_20_materializable_status_winners",
    ):
        if isinstance(result.get(name), bool) or not isinstance(result.get(name), int) or result[name] <= 0:
            raise VerificationError(f"bad positive integer declaration: {name}")
    for name in ("expected_construction_rows_by_role", "expected_eligible_construction_rows_by_role"):
        counts = result.get(name)
        if not isinstance(counts, dict) or set(counts) != set(ROLES):
            raise VerificationError(f"bad role map: {name}")
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts.values()):
            raise VerificationError(f"bad role-map count: {name}")
    if sum(result["expected_construction_rows_by_role"].values()) != result[
        "expected_identity_available_incomplete_rows"
    ]:
        raise VerificationError("construction row declaration is inconsistent")
    return result


def read_answer_rows(path: Path, protocol: dict[str, Any]) -> list[dict[str, Any]]:
    if digest(path) != protocol["input_answerability_per_parent_sha256"]:
        raise VerificationError("answer input hash mismatch")
    reject_credentials(path)
    output: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != ANSWER_FIELDS:
            raise VerificationError("answer schema mismatch")
        for number, raw in enumerate(reader, 2):
            role = text(raw.get("role"), f"answer:{number}:role")
            task = text(raw.get("task"), f"answer:{number}:task")
            parent = text(raw.get("parent_sha256"), f"answer:{number}:parent")
            run = text(raw.get("run_id_sha256"), f"answer:{number}:run")
            if role not in ROLES or not SHA256.fullmatch(parent) or not SHA256.fullmatch(run):
                raise VerificationError(f"answer context invalid: {number}")
            key = (role, parent)
            if key in identities:
                raise VerificationError(f"answer duplicate: {number}")
            identities.add(key)
            source = integer(raw.get("source_children"), f"answer:{number}:source", 2)
            finite = integer(raw.get("finite_children"), f"answer:{number}:finite", 2)
            available = boolean(raw.get("source_identity_available"), f"answer:{number}:available")
            winner = boolean(raw.get("status_winner_identified"), f"answer:{number}:winner")
            if finite > source or (winner and not available):
                raise VerificationError(f"answer invariant failed: {number}")
            output.append(
                {
                    "role": role,
                    "task": task,
                    "parent_sha256": parent,
                    "run_id_sha256": run,
                    "source_children": source,
                    "finite_children": finite,
                    "source_identity_available": available,
                    "status_winner_identified": winner,
                }
            )
    if len(output) != protocol["expected_answerability_rows"]:
        raise VerificationError("answer row count mismatch")
    if sum(row["status_winner_identified"] for row in output) != protocol["expected_status_winners"]:
        raise VerificationError("winner count mismatch")
    return output


def read_construction_rows(
    path: Path, protocol: dict[str, Any]
) -> dict[tuple[str, str], dict[str, Any]]:
    if digest(path) != protocol["input_hurdle_construction_sha256"]:
        raise VerificationError("construction input hash mismatch")
    reject_credentials(path)
    output: dict[tuple[str, str], dict[str, Any]] = {}
    counts = collections.Counter()
    eligible_counts = collections.Counter()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CONSTRUCTION_FIELDS:
            raise VerificationError("construction schema mismatch")
        for number, raw in enumerate(reader, 2):
            role = text(raw.get("role"), f"construction:{number}:role")
            parent_raw = text(raw.get("parent"), f"construction:{number}:parent")
            task = text(raw.get("task"), f"construction:{number}:task")
            run_raw = text(raw.get("run_id"), f"construction:{number}:run")
            if role not in ROLES:
                raise VerificationError(f"construction role invalid: {number}")
            parent = hashed(parent_raw)
            key = (role, parent)
            if key in output:
                raise VerificationError(f"construction duplicate: {number}")
            eligible = boolean(raw.get("eligible"), f"construction:{number}:eligible")
            if eligible and str(raw.get("exclusion_reasons") or ""):
                raise VerificationError(f"eligible row has exclusion: {number}")
            output[key] = {
                "task": task,
                "run_id_sha256": hashed(run_raw),
                "source_size": integer(raw.get("source_size"), f"construction:{number}:source", 2),
                "eligible": eligible,
            }
            counts[role] += 1
            eligible_counts[role] += int(eligible)
    if {role: counts[role] for role in ROLES} != protocol["expected_construction_rows_by_role"]:
        raise VerificationError("construction role totals mismatch")
    if {role: eligible_counts[role] for role in ROLES} != protocol[
        "expected_eligible_construction_rows_by_role"
    ]:
        raise VerificationError("eligible construction totals mismatch")
    return output


def group_summary(rows: list[dict[str, Any]], name: str) -> dict[str, Any]:
    winners = [row for row in rows if row["status_winner_identified"]]
    ready = [row for row in rows if row["materializable_status_winner"]]
    variable = sum(row["source_children"] >= 3 for row in ready)
    return {
        "stratum": name,
        "parents": len(rows),
        "runs": len({row["run_id_sha256"] for row in rows}),
        "tasks": len({row["task"] for row in rows}),
        "status_winners": len(winners),
        "materializable_status_winners": len(ready),
        "materializable_status_winner_rate_all_parents": fraction(len(ready), len(rows)),
        "code_complete_share_of_status_winners": fraction(len(ready), len(winners)),
        "candidate_slots": sum(row["source_children"] for row in ready),
        "variable_arity_materializable_winners": variable,
        "variable_arity_share": fraction(variable, len(ready)),
    }


def independent_reconstruction(
    answer_rows: list[dict[str, Any]],
    construction: dict[tuple[str, str], dict[str, Any]],
    protocol: dict[str, Any],
    source_commit: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    consumed: set[tuple[str, str]] = set()
    for answer in answer_rows:
        key = (answer["role"], answer["parent_sha256"])
        incomplete = answer["source_children"] != answer["finite_children"]
        if answer["source_identity_available"] and incomplete:
            joined = construction.get(key)
            if joined is None:
                raise VerificationError(f"missing construction join: {key}")
            consumed.add(key)
            if (
                joined["task"] != answer["task"]
                or joined["run_id_sha256"] != answer["run_id_sha256"]
                or joined["source_size"] != answer["source_children"]
            ):
                raise VerificationError(f"construction join mismatch: {key}")
            complete = bool(joined["eligible"])
            kind = "identity_recovered_incomplete"
        elif not incomplete:
            if not answer["source_identity_available"]:
                raise VerificationError(f"complete source identity unavailable: {key}")
            complete = True
            kind = "published_complete"
        else:
            complete = False
            kind = "identity_unavailable_incomplete"
        rows.append(
            {
                **answer,
                "source_kind": kind,
                "candidate_code_reference_complete": complete,
                "materializable_status_winner": answer["status_winner_identified"] and complete,
            }
        )
    if consumed != set(construction) or len(consumed) != protocol[
        "expected_identity_available_incomplete_rows"
    ]:
        raise VerificationError("construction join closure failed")

    overall = group_summary(rows, "all")
    roles = {
        role: group_summary([row for row in rows if row["role"] == role], role)
        for role in ROLES
    }
    all_tasks = sorted({row["task"] for row in rows})
    task_rows = [
        {"task": task, **group_summary([row for row in rows if row["task"] == task], task)}
        for task in all_tasks
    ]
    task_counts = collections.Counter(
        row["task"] for row in rows if row["materializable_status_winner"]
    )
    if not task_counts:
        dominant_task, dominant_count = None, 0
    else:
        dominant_task, dominant_count = max(task_counts.items(), key=lambda item: (item[1], item[0]))
    dominant_share = fraction(dominant_count, overall["materializable_status_winners"])
    tasks_20 = sum(count >= 20 for count in task_counts.values())
    train = [row for row in rows if row["role"] == "train"]
    frozen = [row for row in rows if row["role"] == "frozen"]
    parent_overlap = len(
        {row["parent_sha256"] for row in train} & {row["parent_sha256"] for row in frozen}
    )
    run_overlap = len(
        {row["run_id_sha256"] for row in train} & {row["run_id_sha256"] for row in frozen}
    )
    criteria = {
        "materializable_status_winners_ge_minimum": overall["materializable_status_winners"]
        >= protocol["minimum_materializable_status_winners"],
        "materializable_status_winner_rate_all_parents_ge_minimum": (
            overall["materializable_status_winner_rate_all_parents"] or 0.0
        ) >= protocol["minimum_materializable_status_winner_rate_all_parents"],
        "code_complete_share_of_status_winners_ge_minimum": (
            overall["code_complete_share_of_status_winners"] or 0.0
        ) >= protocol["minimum_code_complete_share_of_status_winners"],
        "train_materializable_status_winners_ge_minimum": roles["train"]["materializable_status_winners"]
        >= protocol["minimum_train_materializable_status_winners"],
        "frozen_materializable_status_winners_ge_minimum": roles["frozen"]["materializable_status_winners"]
        >= protocol["minimum_frozen_materializable_status_winners"],
        "train_code_complete_share_of_status_winners_ge_minimum": (
            roles["train"]["code_complete_share_of_status_winners"] or 0.0
        ) >= protocol["minimum_train_code_complete_share_of_status_winners"],
        "frozen_code_complete_share_of_status_winners_ge_minimum": (
            roles["frozen"]["code_complete_share_of_status_winners"] or 0.0
        ) >= protocol["minimum_frozen_code_complete_share_of_status_winners"],
        "tasks_with_materializable_status_winner_ge_minimum": len(task_counts)
        >= protocol["minimum_tasks_with_materializable_status_winner"],
        "tasks_with_at_least_20_materializable_status_winners_ge_minimum": tasks_20
        >= protocol["minimum_tasks_with_at_least_20_materializable_status_winners"],
        "variable_arity_share_ge_minimum": (overall["variable_arity_share"] or 0.0)
        >= protocol["minimum_variable_arity_share"],
        "dominant_task_share_le_maximum": (dominant_share if dominant_share is not None else 1.0)
        <= protocol["maximum_dominant_task_share"],
        "train_frozen_parent_overlap_eq_required": parent_overlap
        == protocol["require_train_frozen_parent_overlap"],
        "train_frozen_run_overlap_eq_required": run_overlap
        == protocol["require_train_frozen_run_overlap"],
    }
    allowed = all(criteria.values())
    return {
        "protocol": PROTOCOL,
        "status": (
            "SOURCE_CHOICE_MATERIALIZATION_SUPPORT_FEASIBLE"
            if allowed
            else "INSUFFICIENT_SOURCE_CHOICE_MATERIALIZATION_SUPPORT"
        ),
        "source_commit": source_commit,
        "inputs": {
            "answerability_per_parent_sha256": protocol["input_answerability_per_parent_sha256"],
            "hurdle_construction_sha256": protocol["input_hurdle_construction_sha256"],
        },
        "scope": protocol["scope"],
        "overall": overall,
        "roles": roles,
        "support": {
            "tasks_with_materializable_status_winner": len(task_counts),
            "tasks_with_at_least_20_materializable_status_winners": tasks_20,
            "dominant_task": dominant_task,
            "dominant_task_count": dominant_count,
            "dominant_task_share": dominant_share,
            "train_frozen_parent_overlap": parent_overlap,
            "train_frozen_run_overlap": run_overlap,
            "source_kinds": dict(sorted(collections.Counter(row["source_kind"] for row in rows).items())),
            "code_reference_complete_by_source_kind": dict(
                sorted(
                    collections.Counter(
                        row["source_kind"] for row in rows if row["candidate_code_reference_complete"]
                    ).items()
                )
            ),
        },
        "criteria": criteria,
        "materialization_s1_authorized": allowed,
        "complete_v11_choice_set_claim_allowed": False,
        "predictor_or_search_utility_claim_allowed": False,
    }, task_rows


def expected_task_csv(rows: list[dict[str, Any]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def verify(arguments: argparse.Namespace) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{40}", arguments.source_commit):
        raise VerificationError("source commit is invalid")
    paths = {
        "protocol": Path(arguments.protocol).resolve(),
        "answer": Path(arguments.answerability_per_parent).resolve(),
        "construction": Path(arguments.hurdle_construction).resolve(),
        "artifact": Path(arguments.artifact).resolve(),
    }
    if any(not path.exists() for path in paths.values()):
        raise VerificationError("required input/artifact is missing")
    protocol = read_protocol(paths["protocol"])
    answer = read_answer_rows(paths["answer"], protocol)
    construction = read_construction_rows(paths["construction"], protocol)
    expected_summary, expected_tasks = independent_reconstruction(
        answer, construction, protocol, arguments.source_commit
    )
    summary_path = paths["artifact"] / "summary.json"
    task_path = paths["artifact"] / "per_task.csv"
    manifest_path = paths["artifact"] / "sha256_manifest.json"
    for path in (summary_path, task_path, manifest_path):
        if not path.is_file():
            raise VerificationError(f"artifact member missing: {path.name}")
        reject_credentials(path)
    actual_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if actual_summary != expected_summary:
        raise VerificationError("producer summary differs from independent reconstruction")
    if task_path.read_bytes().replace(b"\r\n", b"\n") != expected_task_csv(expected_tasks):
        raise VerificationError("producer per-task CSV differs from independent reconstruction")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_manifest = {
        "summary.json": digest(summary_path),
        "per_task.csv": digest(task_path),
    }
    if manifest != expected_manifest:
        raise VerificationError("producer manifest mismatch")
    return {
        "protocol": "independent-source-choice-materialization-support-verifier-v1",
        "status": "INDEPENDENT_SOURCE_CHOICE_MATERIALIZATION_SUPPORT_VERIFIED",
        "producer_status": actual_summary["status"],
        "source_commit": arguments.source_commit,
        "producer_imported": "phase1.source_choice_materialization_support" in sys.modules,
        "materializable_status_winners": actual_summary["overall"]["materializable_status_winners"],
        "code_complete_share_of_status_winners": actual_summary["overall"][
            "code_complete_share_of_status_winners"
        ],
        "criteria_all_pass": all(actual_summary["criteria"].values()),
        "summary_sha256": digest(summary_path),
        "per_task_sha256": digest(task_path),
    }


def atomic_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise VerificationError("verification output already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--protocol", required=True)
    value.add_argument("--answerability-per-parent", required=True)
    value.add_argument("--hurdle-construction", required=True)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--artifact", required=True)
    value.add_argument("--output", required=True)
    return value


def main() -> int:
    try:
        arguments = parser().parse_args()
        receipt = verify(arguments)
        if receipt["producer_imported"]:
            raise VerificationError("producer imported by independent verifier")
        atomic_json(Path(arguments.output).resolve(), receipt)
        print(receipt["status"])
        return 0
    except VerificationError as exc:
        print(f"SOURCE_CHOICE_MATERIALIZATION_VERIFY_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
