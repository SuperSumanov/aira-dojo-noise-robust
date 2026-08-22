#!/usr/bin/env python3
"""Independent verifier for the closed-cohort future truth-support gate.

This module intentionally does not import the producer.  It independently
rebuilds the finite-grade parent lottery and the aggregate y_norm gap table.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any


FROZEN_PROTOCOL_SHA256 = "54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d"
PROTOCOL = "score-channel-future-identifiability-cohort-v1"
COHORT_PROTOCOL = "score-channel-future-identity-cohort-v1"
OUTPUT_PROTOCOL = "score-channel-future-truth-support-v1"
ROW_SCHEMA = "score-channel-future-selected-parent-v1"
SHA_RX = re.compile(r"[0-9a-f]{64}")
RUN_KEYS = {
    "archive_relative_path", "archive_sha256", "drop_id", "endpoints",
    "flow_status", "generation_started_at_utc", "journal_sha256", "run_id", "task",
}
ARCHIVE_KEYS = {
    "archive_relative_path", "archive_sha256", "archive_size",
    "cumulative_unique_physical_runs", "drop_id", "intake_summary_sha256",
    "mtime_ns", "physical_runs", "source_provenance_sha256",
}
PAIR_KEYS = {"task", "run_id", "parent", "left", "right"}
VAULT_KEYS = {"card_id", "task", "run_id", "graded", "y_norm", "eligible_by_start_time"}
SELECTED_KEYS = {
    "schema_version", "task", "run_id", "parent_id", "source_intake",
    "selection_rank_in_run", "selection_key_sha256", "candidate_card_ids",
    "candidate_count", "candidate_identity_sha256",
}


class VerificationError(RuntimeError):
    """Raised when independent reconstruction disagrees or an input drifts."""


def digest(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            state.update(block)
    return state.hexdigest()


def text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def check_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA_RX.fullmatch(value.lower()) is None:
        raise VerificationError(f"invalid {label}")
    return value.lower()


def object_at(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise VerificationError(f"{label} is not a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot read {label}") from error
    if not isinstance(value, dict):
        raise VerificationError(f"{label} is not an object")
    return value


def rows_at(path: Path, label: str, keys: set[str], *, empty_ok: bool = False) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise VerificationError(f"{label} is not a regular file")
    result: list[dict[str, Any]] = []
    try:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line:
                raise VerificationError(f"blank line in {label}")
            row = json.loads(line)
            if not isinstance(row, dict) or set(row) != keys:
                raise VerificationError(f"{label} schema mismatch at row {number}")
            result.append(row)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot read {label}") from error
    if not result and not empty_ok:
        raise VerificationError(f"{label} is empty")
    return result


def numeric_or_none(value: Any, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise VerificationError(f"non-finite {label}")
    return float(value)


def protocol_at(path: Path, expected_sha: str) -> dict[str, Any]:
    if check_sha(expected_sha, "protocol SHA") != FROZEN_PROTOCOL_SHA256 or digest(path) != FROZEN_PROTOCOL_SHA256:
        raise VerificationError("protocol SHA mismatch")
    protocol = object_at(path, "protocol")
    selection = protocol.get("parent_selection") or {}
    truth = protocol.get("truth_support") or {}
    gates = protocol.get("eligibility_gates_for_requesting_replay_design") or {}
    if (
        protocol.get("protocol") != PROTOCOL
        or protocol.get("status") != "FROZEN_OUTCOME_UNREAD_WAITING_COHORT"
        or selection.get("seed") != 20260813
        or selection.get("max_parents_per_physical_run") != 2
        or selection.get("score_magnitude_used_for_eligibility_or_lottery") is not False
        or truth.get("absolute_tolerance") != 1e-12
        or truth.get("raw_labels_written") is not False
        or gates.get("nontied_selected_parents_minimum") != 80
        or gates.get("tasks_with_nontied_parent_minimum") != 8
        or gates.get("dominant_nontied_task_share_maximum") != 0.25
        or gates.get("selected_physical_runs_minimum") != 60
    ):
        raise VerificationError("protocol contract mismatch")
    return protocol


def closed_runs(
    cohort_dir: Path,
    expected_protocol_sha: str,
    expected_summary_sha: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    protocol_sha = check_sha(expected_protocol_sha, "protocol SHA")
    summary_path = cohort_dir / "summary.json"
    if digest(summary_path) != check_sha(expected_summary_sha, "cohort summary SHA"):
        raise VerificationError("cohort summary SHA mismatch")
    summary = object_at(summary_path, "cohort summary")
    inputs, outputs = summary.get("inputs") or {}, summary.get("outputs") or {}
    closure, blindness = summary.get("closure") or {}, summary.get("blindness") or {}
    inventory = summary.get("inventory") or {}
    if (
        summary.get("protocol") != COHORT_PROTOCOL
        or summary.get("status") != "FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD"
        or inputs.get("protocol_sha256") != protocol_sha
        or closure.get("accepted_unique_physical_run_target") != 300
        or closure.get("remaining_runs_to_target") != 0
        or closure.get("complete_boundary_archive_included") is not True
        or not isinstance(closure.get("boundary_archive"), str)
        or blindness.get("label_vault_opened") is not False
        or blindness.get("score_or_outcome_opened") is not False
        or blindness.get("truth_support_computed") is not False
        or blindness.get("replay_submission_authorized") is not False
    ):
        raise VerificationError("cohort closure/blindness mismatch")
    runs_path = cohort_dir / "cohort_runs.jsonl"
    archives_path = cohort_dir / "cohort_archives.jsonl"
    if (
        digest(runs_path) != check_sha(outputs.get("cohort_runs_sha256"), "cohort runs SHA")
        or digest(archives_path) != check_sha(outputs.get("cohort_archives_sha256"), "cohort archives SHA")
    ):
        raise VerificationError("cohort output SHA mismatch")
    runs = rows_at(runs_path, "cohort runs", RUN_KEYS)
    archives = rows_at(archives_path, "cohort archives", ARCHIVE_KEYS)
    if len(runs) < 300 or inventory.get("selected_physical_runs") != len(runs):
        raise VerificationError("cohort run count mismatch")

    archive_by_drop: dict[str, dict[str, Any]] = {}
    archive_order: list[tuple[int, bytes]] = []
    seen_relative: set[str] = set()
    cumulative = 0
    for row in archives:
        drop, relative = row.get("drop_id"), row.get("archive_relative_path")
        physical_runs = row.get("physical_runs")
        archive_size, mtime_ns = row.get("archive_size"), row.get("mtime_ns")
        if (
            not isinstance(drop, str)
            or not drop
            or Path(drop).name != drop
            or drop in archive_by_drop
            or not isinstance(relative, str)
            or relative.count("/") != 1
            or not relative.endswith(".tar.gz")
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or relative in seen_relative
            or isinstance(physical_runs, bool)
            or not isinstance(physical_runs, int)
            or physical_runs < 0
            or isinstance(archive_size, bool)
            or not isinstance(archive_size, int)
            or archive_size < 0
            or isinstance(mtime_ns, bool)
            or not isinstance(mtime_ns, int)
            or mtime_ns < 0
        ):
            raise VerificationError("invalid cohort archive row")
        cumulative += physical_runs
        if row.get("cumulative_unique_physical_runs") != cumulative:
            raise VerificationError("cohort archive cumulative mismatch")
        check_sha(row.get("archive_sha256"), "archive SHA")
        check_sha(row.get("intake_summary_sha256"), "intake summary SHA")
        check_sha(row.get("source_provenance_sha256"), "source provenance SHA")
        archive_by_drop[drop] = row
        seen_relative.add(relative)
        archive_order.append((mtime_ns, relative.encode("utf-8")))
    if archive_order != sorted(archive_order):
        raise VerificationError("cohort archive order mismatch")
    if (
        cumulative != len(runs)
        or archives[-1]["archive_relative_path"] != closure["boundary_archive"]
        or inventory.get("selected_archives") != len(archives)
    ):
        raise VerificationError("cohort archive boundary mismatch")

    seen: set[str] = set()
    tasks: Counter[str] = Counter()
    runs_by_drop: Counter[str] = Counter()
    for row in runs:
        journal = check_sha(row.get("journal_sha256"), "journal SHA")
        drop = row.get("drop_id")
        archive = archive_by_drop.get(str(drop))
        endpoints = row.get("endpoints")
        flow_status = row.get("flow_status")
        if (
            row.get("run_id") != f"journal:{journal}"
            or row["run_id"] in seen
            or not isinstance(row.get("task"), str)
            or not row["task"]
            or archive is None
            or row.get("archive_relative_path") != archive["archive_relative_path"]
            or row.get("archive_sha256") != archive["archive_sha256"]
            or isinstance(endpoints, bool)
            or not isinstance(endpoints, int)
            or endpoints < 0
            or flow_status not in {"scoreable", "no_scoreable_code"}
            or flow_status != ("scoreable" if endpoints else "no_scoreable_code")
            or not isinstance(row.get("generation_started_at_utc"), str)
            or not row["generation_started_at_utc"]
        ):
            raise VerificationError("invalid cohort run row")
        seen.add(row["run_id"])
        tasks[row["task"]] += 1
        runs_by_drop[str(drop)] += 1
    if any(runs_by_drop[drop] != row["physical_runs"] for drop, row in archive_by_drop.items()):
        raise VerificationError("cohort archive/run membership mismatch")
    if (
        inventory.get("per_task_selected_runs") != dict(sorted(tasks.items()))
        or inventory.get("selected_tasks") != len(tasks)
    ):
        raise VerificationError("cohort task inventory mismatch")
    intake_hashes = inputs.get("intake_summary_sha256")
    provenance_hashes = inputs.get("source_provenance_sha256")
    if (
        not isinstance(intake_hashes, dict)
        or not isinstance(provenance_hashes, dict)
        or set(intake_hashes) != set(archive_by_drop)
        or set(provenance_hashes) != set(archive_by_drop)
        or any(
            intake_hashes[drop] != row["intake_summary_sha256"]
            or provenance_hashes[drop] != row["source_provenance_sha256"]
            for drop, row in archive_by_drop.items()
        )
    ):
        raise VerificationError("cohort archive/input hash manifest mismatch")
    return runs, summary


def read_truth_state(
    state_root: Path,
    runs: list[dict[str, Any]],
    cohort_summary: dict[str, Any],
) -> tuple[dict[tuple[str, str, str], set[str]], dict[str, dict[str, Any]]]:
    allowed = {row["run_id"]: (row["task"], row["drop_id"]) for row in runs}
    intake_hashes = (cohort_summary.get("inputs") or {}).get("intake_summary_sha256")
    drops = sorted({row["drop_id"] for row in runs})
    if not isinstance(intake_hashes, dict) or set(intake_hashes) != set(drops):
        raise VerificationError("cohort intake hash manifest mismatch")

    siblings: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    edges: dict[tuple[str, str, str], set[tuple[str, str]]] = defaultdict(set)
    owner: dict[str, tuple[str, str, str]] = {}
    vault: dict[str, dict[str, Any]] = {}
    for drop in drops:
        intake = state_root / "intakes" / drop
        if intake.is_symlink() or not intake.is_dir() or intake.resolve().parent != (state_root / "intakes").resolve():
            raise VerificationError("unsafe intake directory")
        summary_path = intake / "summary.json"
        if digest(summary_path) != check_sha(intake_hashes[drop], "intake summary SHA"):
            raise VerificationError("intake summary SHA mismatch")
        summary = object_at(summary_path, "intake summary")
        blind, security = summary.get("blindness") or {}, summary.get("security") or {}
        if (
            summary.get("protocol") != "prospective_drop_intake_v1"
            or summary.get("status") != "PROSPECTIVE_DROP_INTAKE_COMPLETE"
            or blind.get("labels_used_for_run_selection") is not False
            or blind.get("labels_used_for_endpoint_selection") is not False
            or blind.get("label_values_printed") is not False
            or blind.get("metrics_computed") != []
            or security.get("credential_shaped_journals") != 0
            or security.get("env_members_read") is not False
            or security.get("live_event_journal_members_read") is not False
        ):
            raise VerificationError("intake safety contract mismatch")
        outputs = summary.get("outputs") or {}
        pair_path, vault_path = intake / "eligible_structural_pairs.jsonl", intake / "label_vault.jsonl"
        if (
            digest(pair_path) != check_sha(outputs.get("eligible_structural_pairs_sha256"), "pair SHA")
            or digest(vault_path) != check_sha(outputs.get("label_vault_sha256"), "vault SHA")
        ):
            raise VerificationError("truth input SHA mismatch")

        for row in rows_at(pair_path, "structural pairs", PAIR_KEYS, empty_ok=True):
            run_id, task, parent = row.get("run_id"), row.get("task"), row.get("parent")
            left, right = row.get("left"), row.get("right")
            if (
                allowed.get(str(run_id)) != (task, drop)
                or any(not isinstance(value, str) or not value for value in (parent, left, right))
                or not left < right
                or parent in {left, right}
            ):
                raise VerificationError("invalid structural pair")
            key = (task, run_id, parent)
            pair = (left, right)
            if pair in edges[key]:
                raise VerificationError("duplicate structural pair")
            edges[key].add(pair)
            siblings[key].update(pair)
            for card in pair:
                previous = owner.setdefault(card, key)
                if previous != key:
                    raise VerificationError("card belongs to multiple parents")

        for row in rows_at(vault_path, "label vault", VAULT_KEYS, empty_ok=True):
            card = row.get("card_id")
            if (
                allowed.get(str(row.get("run_id"))) != (row.get("task"), drop)
                or not isinstance(card, str)
                or not card
                or card in vault
                or not isinstance(row.get("eligible_by_start_time"), bool)
            ):
                raise VerificationError("invalid label-vault row")
            numeric_or_none(row.get("graded"), "graded")
            numeric_or_none(row.get("y_norm"), "y_norm")
            if row["eligible_by_start_time"]:
                vault[card] = row

    for key, cards in siblings.items():
        ordered = sorted(cards)
        clique = {(a, b) for index, a in enumerate(ordered) for b in ordered[index + 1 :]}
        if edges[key] != clique:
            raise VerificationError("incomplete structural sibling clique")
        task, run_id, _ = key
        if any(card not in vault or vault[card]["task"] != task or vault[card]["run_id"] != run_id for card in cards):
            raise VerificationError("structural card missing from eligible vault")
    return siblings, vault


def reconstruct_selection(
    runs: list[dict[str, Any]],
    siblings: dict[tuple[str, str, str], set[str]],
    vault: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    choices: dict[str, list[tuple[str, str, list[str]]]] = defaultdict(list)
    eligible = 0
    for (_, run_id, parent), cards in siblings.items():
        finite = sorted(card for card in cards if vault[card]["graded"] is not None)
        if len(finite) >= 2:
            eligible += 1
            key = text_digest(f"20260813|{run_id}|{parent}")
            choices[run_id].append((key, parent, finite))
    selected: list[dict[str, Any]] = []
    runs_with = 0
    seen_cards: set[str] = set()
    for run in runs:
        ordered = sorted(choices.get(run["run_id"], []), key=lambda item: (item[0], item[1]))
        runs_with += int(bool(ordered))
        for rank, (key, parent, cards) in enumerate(ordered[:2], 1):
            if seen_cards.intersection(cards):
                raise VerificationError("card appears in multiple selected parents")
            seen_cards.update(cards)
            selected.append({
                "schema_version": ROW_SCHEMA,
                "task": run["task"],
                "run_id": run["run_id"],
                "parent_id": parent,
                "source_intake": run["drop_id"],
                "selection_rank_in_run": rank,
                "selection_key_sha256": key,
                "candidate_card_ids": cards,
                "candidate_count": len(cards),
                "candidate_identity_sha256": text_digest(canonical(cards)),
            })
    return selected, eligible, runs_with


def reconstruct_aggregate(
    selected: list[dict[str, Any]],
    vault: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    edges = [0.0, 0.0001, 0.0003, 0.001, 0.003, 0.01, 0.03, 0.1, 0.3, math.inf]
    labels = [f"[{low:g},{'infinity' if math.isinf(high) else f'{high:g}'})" for low, high in zip(edges, edges[1:])]
    bins = {label: 0 for label in labels}
    by_task: dict[str, dict[str, int]] = defaultdict(
        lambda: {"selected_parents": 0, "truth_available_parents": 0, "nontied_parents": 0}
    )
    tied = nontied = unavailable = 0
    for row in selected:
        task = row["task"]
        by_task[task]["selected_parents"] += 1
        values = [vault[card]["y_norm"] for card in row["candidate_card_ids"]]
        if any(value is None for value in values):
            unavailable += 1
            continue
        gap = max(float(value) for value in values) - min(float(value) for value in values)
        by_task[task]["truth_available_parents"] += 1
        index = next((i for i in range(len(edges) - 1) if edges[i] <= gap < edges[i + 1]), None)
        if index is None:
            raise VerificationError("gap outside frozen bins")
        bins[labels[index]] += 1
        if gap > 1e-12:
            nontied += 1
            by_task[task]["nontied_parents"] += 1
        else:
            tied += 1
    positive = {task: row["nontied_parents"] for task, row in by_task.items() if row["nontied_parents"]}
    dominant = max(positive, key=lambda task: (positive[task], task)) if positive else None
    dominant_n = positive.get(dominant, 0) if dominant else 0
    share = dominant_n / nontied if nontied else None
    selected_runs = len({row["run_id"] for row in selected})
    gates = {
        "nontied_selected_parents": nontied >= 80,
        "tasks_with_nontied_parent": len(positive) >= 8,
        "dominant_nontied_task_share": share is not None and share <= 0.25,
        "selected_physical_runs": selected_runs >= 60,
    }
    return {
        "counts": {
            "selected_parents": len(selected),
            "selected_candidates": sum(row["candidate_count"] for row in selected),
            "selected_physical_runs": selected_runs,
            "selected_tasks": len(by_task),
            "truth_available_parents": tied + nontied,
            "truth_unavailable_parents": unavailable,
            "tied_parents": tied,
            "nontied_parents": nontied,
            "tasks_with_nontied_parent": len(positive),
        },
        "gap_distribution": bins,
        "per_task": dict(sorted(by_task.items())),
        "balance": {
            "dominant_nontied_task": dominant,
            "dominant_nontied_parents": dominant_n,
            "dominant_nontied_task_share": share,
        },
        "gates": {**gates, "all_pass": all(gates.values())},
    }


def verify(
    protocol_path: Path,
    expected_protocol_sha: str,
    cohort_dir: Path,
    expected_cohort_summary_sha: str,
    state_root: Path,
    truth_dir: Path,
    receipt_path: Path,
) -> dict[str, Any]:
    protocol_sha = check_sha(expected_protocol_sha, "protocol SHA")
    cohort_summary_sha = check_sha(expected_cohort_summary_sha, "cohort summary SHA")
    protocol = protocol_at(protocol_path, protocol_sha)
    runs, cohort_summary = closed_runs(cohort_dir, protocol_sha, cohort_summary_sha)
    siblings, vault = read_truth_state(state_root, runs, cohort_summary)
    expected_rows, eligible, runs_with = reconstruct_selection(runs, siblings, vault)
    actual_path = truth_dir / "selected_parents.jsonl"
    actual_rows = rows_at(actual_path, "selected parents", SELECTED_KEYS, empty_ok=True)
    expected_bytes = "".join(canonical(row) + "\n" for row in expected_rows).encode("utf-8")
    if actual_rows != expected_rows or actual_path.read_bytes() != expected_bytes:
        raise VerificationError("selected-parent reconstruction mismatch")

    summary_path = truth_dir / "summary.json"
    summary = object_at(summary_path, "truth-support summary")
    aggregate = reconstruct_aggregate(expected_rows, vault)
    all_pass = aggregate["gates"]["all_pass"]
    expected_status = (
        "TRUTH_SUPPORT_ELIGIBLE_REPLAY_DESIGN_REQUEST_ONLY"
        if all_pass
        else "TRUTH_SUPPORT_KILL_NO_REPLAY_REQUEST"
    )
    identity = summary.get("identity") or {}
    decision = summary.get("decision") or {}
    blindness = summary.get("blindness") or {}
    outputs = summary.get("outputs") or {}
    inputs = summary.get("inputs") or {}
    selection = summary.get("selection") or {}
    truth = summary.get("truth_support") or {}
    implementation = summary.get("implementation") or {}
    frozen_selection = protocol["parent_selection"]
    frozen_truth = protocol["truth_support"]
    frozen_gates = protocol["eligibility_gates_for_requesting_replay_design"]
    if (
        summary.get("protocol") != OUTPUT_PROTOCOL
        or summary.get("status") != expected_status
        or inputs.get("protocol_sha256") != protocol_sha
        or inputs.get("cohort_summary_sha256") != cohort_summary_sha
        or inputs.get("cohort_runs_sha256") != digest(cohort_dir / "cohort_runs.jsonl")
        or inputs.get("cohort_archives_sha256") != digest(cohort_dir / "cohort_archives.jsonl")
        or inputs.get("intake_summary_sha256")
        != (cohort_summary.get("inputs") or {}).get("intake_summary_sha256")
        or selection.get("seed") != frozen_selection["seed"]
        or selection.get("ordering") != frozen_selection["ordering"]
        or selection.get("max_parents_per_physical_run")
        != frozen_selection["max_parents_per_physical_run"]
        or selection.get("parent_eligibility") != frozen_selection["eligibility"]
        or selection.get("score_magnitude_used_for_eligibility_or_lottery") is not False
        or selection.get("outcome_dependent_reselection") is not False
        or identity.get("closed_before_label_open") is not True
        or identity.get("cohort_physical_runs") != len(runs)
        or identity.get("eligible_parents_before_per_run_cap") != eligible
        or identity.get("runs_with_eligible_parent") != runs_with
        or identity.get("runs_without_eligible_parent") != len(runs) - runs_with
        or truth.get("definition") != frozen_truth["primary_informative_definition"]
        or truth.get("absolute_tolerance") != frozen_truth["absolute_tolerance"]
        or truth.get("fixed_gap_edges") != frozen_truth["fixed_gap_edges"]
        or truth.get("counts") != aggregate["counts"]
        or truth.get("gap_distribution") != aggregate["gap_distribution"]
        or truth.get("per_task") != aggregate["per_task"]
        or truth.get("balance") != aggregate["balance"]
        or truth.get("gates") != aggregate["gates"]
        or decision.get("all_gates_must_pass") is not True
        or decision.get("replay_design_request_eligible") is not all_pass
        or decision.get("replay_submission_authorized") is not False
        or decision.get("gpu_jobs_authorized") != 0
        or decision.get("failure_action") != frozen_gates["failure_action"]
        or decision.get("pass_action") != frozen_gates["pass_action"]
        or blindness.get("label_vault_opened_after_identity_closure") is not True
        or blindness.get("graded_values_used_beyond_finiteness_for_selection") is not False
        or blindness.get("raw_label_values_written") is not False
        or blindness.get("y_norm_used_for_selection") is not False
        or blindness.get("blind_code_view_opened") is not False
        or blindness.get("score_directory_opened") is not False
        or blindness.get("replay_outcomes_opened") is not False
        or outputs.get("selected_parents_sha256") != digest(actual_path)
        or not isinstance(implementation.get("source_commit"), str)
        or re.fullmatch(r"[0-9a-f]{40}", implementation["source_commit"]) is None
        or check_sha(implementation.get("script_sha256"), "producer script SHA")
        != digest(Path(__file__).with_name("score_channel_future_truth_support.py"))
    ):
        raise VerificationError("truth-support summary reconstruction mismatch")

    receipt = {
        "protocol": "score-channel-future-truth-support-independent-verification-v1",
        "status": "PASS_ELIGIBLE_REPLAY_DESIGN_REQUEST_ONLY" if all_pass else "PASS_KILL_NO_REPLAY_REQUEST",
        "producer_module_imported": False,
        "protocol_sha256": protocol_sha,
        "cohort_summary_sha256": cohort_summary_sha,
        "truth_support_summary_sha256": digest(summary_path),
        "selected_parents_sha256": digest(actual_path),
        "selected_parents": len(expected_rows),
        "nontied_parents": aggregate["counts"]["nontied_parents"],
        "tasks_with_nontied_parent": aggregate["counts"]["tasks_with_nontied_parent"],
        "all_gates_pass": all_pass,
        "replay_submission_authorized": False,
        "raw_labels_written": False,
    }
    if receipt_path.exists():
        raise FileExistsError(f"refusing to overwrite verification receipt: {receipt_path}")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{receipt_path.name}.", dir=receipt_path.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(
            json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, receipt_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return receipt


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--cohort-dir", required=True, type=Path)
    parser.add_argument("--expect-cohort-summary-sha256", required=True)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--truth-dir", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    result = verify(
        args.protocol,
        args.expect_protocol_sha256,
        args.cohort_dir,
        args.expect_cohort_summary_sha256,
        args.state_root,
        args.truth_dir,
        args.receipt,
    )
    print(canonical(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
