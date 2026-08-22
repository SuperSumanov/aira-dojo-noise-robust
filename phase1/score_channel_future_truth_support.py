#!/usr/bin/env python3
"""Outcome-aware truth-support gate for a *closed* future score-channel cohort.

Identity closure is verified before any label vault is opened.  Parent selection
uses only finite ``graded`` availability plus the frozen SHA-256 lottery.  Raw
``graded``/``y_norm`` values are never written; only aggregate gap counts leave
the process.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import platform
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Iterable


PROTOCOL = "score-channel-future-identifiability-cohort-v1"
COHORT_PROTOCOL = "score-channel-future-identity-cohort-v1"
OUTPUT_PROTOCOL = "score-channel-future-truth-support-v1"
ROW_SCHEMA = "score-channel-future-selected-parent-v1"
FROZEN_PROTOCOL_SHA256 = (
    "54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d"
)
SHA256_RX = re.compile(r"[0-9a-f]{64}")
RUN_KEYS = {
    "archive_relative_path",
    "archive_sha256",
    "drop_id",
    "endpoints",
    "flow_status",
    "generation_started_at_utc",
    "journal_sha256",
    "run_id",
    "task",
}
ARCHIVE_KEYS = {
    "archive_relative_path",
    "archive_sha256",
    "archive_size",
    "cumulative_unique_physical_runs",
    "drop_id",
    "intake_summary_sha256",
    "mtime_ns",
    "physical_runs",
    "source_provenance_sha256",
}
PAIR_KEYS = {"task", "run_id", "parent", "left", "right"}
VAULT_KEYS = {
    "card_id",
    "task",
    "run_id",
    "graded",
    "y_norm",
    "eligible_by_start_time",
}
ROW_KEYS = {
    "schema_version",
    "task",
    "run_id",
    "parent_id",
    "source_intake",
    "selection_rank_in_run",
    "selection_key_sha256",
    "candidate_card_ids",
    "candidate_count",
    "candidate_identity_sha256",
}


class TruthSupportError(RuntimeError):
    """Fail-closed protocol, identity, or label-support error."""


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            state.update(block)
    return state.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def valid_sha(value: Any, label: str, *, length: int = 64) -> str:
    if not isinstance(value, str):
        raise TruthSupportError(f"invalid {label}")
    lowered = value.lower()
    if length == 64:
        valid = SHA256_RX.fullmatch(lowered) is not None
    else:
        valid = len(lowered) == length and all(ch in "0123456789abcdef" for ch in lowered)
    if not valid:
        raise TruthSupportError(f"invalid {label}")
    return lowered


def read_object(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise TruthSupportError(f"{label} is not a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise TruthSupportError(f"cannot read {label}") from error
    if not isinstance(value, dict):
        raise TruthSupportError(f"{label} is not an object")
    return value


def read_rows(
    path: Path,
    label: str,
    expected_keys: set[str],
    *,
    allow_empty: bool = False,
) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise TruthSupportError(f"{label} is not a regular file")
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for number, line in enumerate(handle, 1):
                if not line.strip():
                    raise TruthSupportError(f"blank row in {label}")
                value = json.loads(line)
                if not isinstance(value, dict) or set(value) != expected_keys:
                    raise TruthSupportError(f"{label} schema mismatch at row {number}")
                rows.append(value)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise TruthSupportError(f"cannot read {label}") from error
    if not rows and not allow_empty:
        raise TruthSupportError(f"{label} is empty")
    return rows


def finite_or_none(value: Any, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise TruthSupportError(f"non-finite {label}")
    return float(value)


def load_protocol(path: Path, expected_sha: str) -> dict[str, Any]:
    expected = valid_sha(expected_sha, "protocol SHA")
    if expected != FROZEN_PROTOCOL_SHA256 or sha256(path) != expected:
        raise TruthSupportError("frozen protocol SHA mismatch")
    value = read_object(path, "future truth-support protocol")
    closure = value.get("cohort_closure") or {}
    selection = value.get("parent_selection") or {}
    truth = value.get("truth_support") or {}
    gates = value.get("eligibility_gates_for_requesting_replay_design") or {}
    scope = value.get("scope") or {}
    if (
        value.get("protocol") != PROTOCOL
        or value.get("status") != "FROZEN_OUTCOME_UNREAD_WAITING_COHORT"
        or closure.get("accepted_unique_physical_run_target") != 300
        or closure.get("include_complete_boundary_archive") is not True
        or closure.get("label_or_score_may_affect_closure") is not False
        or selection.get("seed") != 20260813
        or selection.get("max_parents_per_physical_run") != 2
        or selection.get("candidate_count_minimum") != 2
        or selection.get("score_magnitude_used_for_eligibility_or_lottery") is not False
        or selection.get("old_assignments_may_reshuffle") is not False
        or truth.get("absolute_tolerance") != 1e-12
        or truth.get("raw_labels_written") is not False
        or gates.get("nontied_selected_parents_minimum") != 80
        or gates.get("tasks_with_nontied_parent_minimum") != 8
        or gates.get("dominant_nontied_task_share_maximum") != 0.25
        or gates.get("selected_physical_runs_minimum") != 60
        or gates.get("all_must_pass") is not True
        or scope.get("gpu_jobs_authorized") != 0
        or scope.get("model_fits") != 0
    ):
        raise TruthSupportError("frozen protocol contract mismatch")
    edges = truth.get("fixed_gap_edges")
    if edges != [0.0, 0.0001, 0.0003, 0.001, 0.003, 0.01, 0.03, 0.1, 0.3, "infinity"]:
        raise TruthSupportError("frozen gap edges mismatch")
    return value


def load_cohort(
    cohort_dir: Path,
    protocol_sha: str,
    expected_summary_sha: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    summary_path = cohort_dir / "summary.json"
    if sha256(summary_path) != valid_sha(expected_summary_sha, "cohort summary SHA"):
        raise TruthSupportError("cohort summary SHA mismatch")
    summary = read_object(summary_path, "closed cohort summary")
    inputs = summary.get("inputs") or {}
    outputs = summary.get("outputs") or {}
    closure = summary.get("closure") or {}
    inventory = summary.get("inventory") or {}
    blindness = summary.get("blindness") or {}
    if (
        summary.get("protocol") != COHORT_PROTOCOL
        or summary.get("status") != "FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD"
        or inputs.get("protocol_sha256") != protocol_sha
        or closure.get("accepted_unique_physical_run_target") != 300
        or closure.get("complete_boundary_archive_included") is not True
        or closure.get("remaining_runs_to_target") != 0
        or not isinstance(closure.get("boundary_archive"), str)
        or blindness.get("label_vault_opened") is not False
        or blindness.get("score_or_outcome_opened") is not False
        or blindness.get("truth_support_computed") is not False
        or blindness.get("replay_submission_authorized") is not False
    ):
        raise TruthSupportError("cohort is not a closed truth-unread identity cohort")

    runs_path = cohort_dir / "cohort_runs.jsonl"
    archives_path = cohort_dir / "cohort_archives.jsonl"
    if (
        sha256(runs_path) != valid_sha(outputs.get("cohort_runs_sha256"), "cohort runs SHA")
        or sha256(archives_path) != valid_sha(outputs.get("cohort_archives_sha256"), "cohort archives SHA")
    ):
        raise TruthSupportError("cohort output SHA mismatch")
    runs = read_rows(runs_path, "cohort runs", RUN_KEYS)
    archives = read_rows(archives_path, "cohort archives", ARCHIVE_KEYS)
    if (
        len(runs) < 300
        or inventory.get("selected_physical_runs") != len(runs)
        or inventory.get("selected_archives") != len(archives)
    ):
        raise TruthSupportError("closed cohort run count mismatch")
    seen_runs: set[str] = set()
    archive_by_drop: dict[str, dict[str, Any]] = {}
    cumulative = 0
    archive_order: list[tuple[int, bytes]] = []
    for row in archives:
        drop_id = row.get("drop_id")
        count = row.get("physical_runs")
        cumulative_value = row.get("cumulative_unique_physical_runs")
        relative = row.get("archive_relative_path")
        mtime_ns = row.get("mtime_ns")
        if (
            not isinstance(drop_id, str)
            or not drop_id
            or Path(drop_id).name != drop_id
            or drop_id in archive_by_drop
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
            or not isinstance(relative, str)
            or relative.count("/") != 1
            or not relative.endswith(".tar.gz")
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or isinstance(mtime_ns, bool)
            or not isinstance(mtime_ns, int)
            or mtime_ns < 0
        ):
            raise TruthSupportError("invalid cohort archive row")
        cumulative += count
        if cumulative_value != cumulative:
            raise TruthSupportError("cohort archive cumulative count mismatch")
        valid_sha(row.get("archive_sha256"), "cohort archive SHA")
        valid_sha(row.get("intake_summary_sha256"), "cohort intake summary SHA")
        valid_sha(row.get("source_provenance_sha256"), "cohort provenance SHA")
        archive_by_drop[drop_id] = row
        archive_order.append((mtime_ns, relative.encode("utf-8")))
    if archive_order != sorted(archive_order):
        raise TruthSupportError("cohort archives are not in frozen order")
    if cumulative != len(runs) or archives[-1]["archive_relative_path"] != closure["boundary_archive"]:
        raise TruthSupportError("cohort boundary archive mismatch")

    run_count_by_drop: collections.Counter[str] = collections.Counter()
    task_counts: collections.Counter[str] = collections.Counter()
    for row in runs:
        run_id, task, drop_id = row.get("run_id"), row.get("task"), row.get("drop_id")
        journal = valid_sha(row.get("journal_sha256"), "cohort journal SHA")
        archive = archive_by_drop.get(str(drop_id))
        if (
            run_id != f"journal:{journal}"
            or run_id in seen_runs
            or not isinstance(task, str)
            or not task
            or archive is None
            or row.get("archive_relative_path") != archive["archive_relative_path"]
            or row.get("archive_sha256") != archive["archive_sha256"]
        ):
            raise TruthSupportError("invalid cohort run identity")
        seen_runs.add(run_id)
        run_count_by_drop[str(drop_id)] += 1
        task_counts[task] += 1
    if any(run_count_by_drop[drop] != row["physical_runs"] for drop, row in archive_by_drop.items()):
        raise TruthSupportError("cohort archive/run membership mismatch")
    if inventory.get("per_task_selected_runs") != dict(sorted(task_counts.items())):
        raise TruthSupportError("cohort task inventory mismatch")
    if inventory.get("selected_tasks") != len(task_counts):
        raise TruthSupportError("cohort selected-task count mismatch")
    expected_intakes = inputs.get("intake_summary_sha256")
    expected_provenance = inputs.get("source_provenance_sha256")
    if (
        not isinstance(expected_intakes, dict)
        or not isinstance(expected_provenance, dict)
        or set(expected_intakes) != set(archive_by_drop)
        or set(expected_provenance) != set(archive_by_drop)
        or any(
            expected_intakes[drop] != row["intake_summary_sha256"]
            or expected_provenance[drop] != row["source_provenance_sha256"]
            for drop, row in archive_by_drop.items()
        )
    ):
        raise TruthSupportError("cohort archive/input hash manifest mismatch")
    return runs, summary


def verify_intake_summary(
    state_root: Path,
    drop_id: str,
    expected_sha: str,
) -> tuple[Path, dict[str, Any]]:
    intake = state_root / "intakes" / drop_id
    if intake.is_symlink() or not intake.is_dir() or intake.resolve().parent != (state_root / "intakes").resolve():
        raise TruthSupportError("unsafe intake directory")
    summary_path = intake / "summary.json"
    if sha256(summary_path) != valid_sha(expected_sha, "intake summary SHA"):
        raise TruthSupportError("intake summary SHA mismatch")
    summary = read_object(summary_path, "intake summary")
    blindness = summary.get("blindness") or {}
    security = summary.get("security") or {}
    if (
        summary.get("protocol") != "prospective_drop_intake_v1"
        or summary.get("status") != "PROSPECTIVE_DROP_INTAKE_COMPLETE"
        or blindness.get("labels_used_for_run_selection") is not False
        or blindness.get("labels_used_for_endpoint_selection") is not False
        or blindness.get("label_values_printed") is not False
        or blindness.get("metrics_computed") != []
    ):
        raise TruthSupportError("intake blindness contract mismatch")
    expected_security = {
        "credential_shaped_journals": 0,
        "env_members_extracted": False,
        "env_members_read": False,
        "journal_scanned_before_json": True,
        "live_event_journal_members_read": False,
        "precutoff_code_sha256_overlap": 0,
        "precutoff_endpoint_id_overlap": 0,
        "raw_journals_written": False,
    }
    if any(security.get(key) != value for key, value in expected_security.items()):
        raise TruthSupportError("intake security contract mismatch")
    return intake, summary


def load_truth_inputs(
    state_root: Path,
    runs: list[dict[str, Any]],
    cohort_summary: dict[str, Any],
) -> tuple[
    dict[tuple[str, str, str], set[str]],
    dict[str, dict[str, Any]],
    dict[str, str],
]:
    allowed = {row["run_id"]: (row["task"], row["drop_id"]) for row in runs}
    expected_summaries = (cohort_summary.get("inputs") or {}).get("intake_summary_sha256")
    if not isinstance(expected_summaries, dict):
        raise TruthSupportError("cohort intake summary manifest missing")
    selected_drops = sorted(expected_summaries)

    sibling_sets: dict[tuple[str, str, str], set[str]] = collections.defaultdict(set)
    pair_edges: dict[tuple[str, str, str], set[tuple[str, str]]] = collections.defaultdict(set)
    child_owner: dict[str, tuple[str, str, str]] = {}
    vault: dict[str, dict[str, Any]] = {}
    summary_shas: dict[str, str] = {}

    for drop_id in selected_drops:
        intake, summary = verify_intake_summary(state_root, drop_id, expected_summaries[drop_id])
        summary_shas[drop_id] = expected_summaries[drop_id]
        outputs = summary.get("outputs") or {}
        pairs_path = intake / "eligible_structural_pairs.jsonl"
        vault_path = intake / "label_vault.jsonl"
        if (
            sha256(pairs_path) != valid_sha(outputs.get("eligible_structural_pairs_sha256"), "structural pairs SHA")
            or sha256(vault_path) != valid_sha(outputs.get("label_vault_sha256"), "label vault SHA")
        ):
            raise TruthSupportError("intake truth-input SHA mismatch")

        for row in read_rows(pairs_path, f"{drop_id} structural pairs", PAIR_KEYS, allow_empty=True):
            run_id, task, parent = row.get("run_id"), row.get("task"), row.get("parent")
            left, right = row.get("left"), row.get("right")
            identity = allowed.get(str(run_id))
            if (
                identity != (task, drop_id)
                or any(not isinstance(value, str) or not value for value in (parent, left, right))
                or not left < right
                or parent in {left, right}
            ):
                raise TruthSupportError("invalid structural pair identity")
            key = (task, run_id, parent)
            edge = (left, right)
            if edge in pair_edges[key]:
                raise TruthSupportError("duplicate structural pair")
            pair_edges[key].add(edge)
            sibling_sets[key].update(edge)
            for child in edge:
                owner = child_owner.setdefault(child, key)
                if owner != key:
                    raise TruthSupportError("structural child has multiple parents")

        for row in read_rows(vault_path, f"{drop_id} label vault", VAULT_KEYS, allow_empty=True):
            run_id, task, card_id = row.get("run_id"), row.get("task"), row.get("card_id")
            if (
                allowed.get(str(run_id)) != (task, drop_id)
                or not isinstance(card_id, str)
                or not card_id
                or card_id in vault
                or not isinstance(row.get("eligible_by_start_time"), bool)
            ):
                raise TruthSupportError("invalid or duplicate label-vault identity")
            finite_or_none(row.get("graded"), "graded")
            finite_or_none(row.get("y_norm"), "y_norm")
            if row["eligible_by_start_time"]:
                vault[card_id] = row

    for key, children in sibling_sets.items():
        ordered = sorted(children)
        expected_edges = {
            (left, right)
            for index, left in enumerate(ordered)
            for right in ordered[index + 1 :]
        }
        if pair_edges[key] != expected_edges:
            raise TruthSupportError("structural pair set is not a complete sibling clique")
        task, run_id, _ = key
        for child in children:
            row = vault.get(child)
            if row is None or row["task"] != task or row["run_id"] != run_id:
                raise TruthSupportError("structural child is missing from eligible label vault")
    return sibling_sets, vault, summary_shas


def select_parents(
    runs: list[dict[str, Any]],
    sibling_sets: dict[tuple[str, str, str], set[str]],
    vault: dict[str, dict[str, Any]],
    seed: int,
    max_parents: int,
) -> tuple[list[dict[str, Any]], int, int]:
    per_run: dict[str, list[tuple[str, str, list[str]]]] = collections.defaultdict(list)
    eligible_parents = 0
    for (task, run_id, parent_id), children in sibling_sets.items():
        finite_children = sorted(child for child in children if vault[child]["graded"] is not None)
        if len(finite_children) < 2:
            continue
        eligible_parents += 1
        key = sha256_text(f"{seed}|{run_id}|{parent_id}")
        per_run[run_id].append((key, parent_id, finite_children))

    selected: list[dict[str, Any]] = []
    runs_with_eligible = 0
    selected_cards: set[str] = set()
    for run in runs:
        candidates = sorted(per_run.get(run["run_id"], []), key=lambda item: (item[0], item[1]))
        if candidates:
            runs_with_eligible += 1
        for rank, (key, parent_id, children) in enumerate(candidates[:max_parents], 1):
            if selected_cards.intersection(children):
                raise TruthSupportError("candidate appears in multiple selected parents")
            selected_cards.update(children)
            selected.append(
                {
                    "schema_version": ROW_SCHEMA,
                    "task": run["task"],
                    "run_id": run["run_id"],
                    "parent_id": parent_id,
                    "source_intake": run["drop_id"],
                    "selection_rank_in_run": rank,
                    "selection_key_sha256": key,
                    "candidate_card_ids": children,
                    "candidate_count": len(children),
                    "candidate_identity_sha256": sha256_text(canonical(children)),
                }
            )
    return selected, eligible_parents, runs_with_eligible


def gap_bin_labels(edges: list[Any]) -> list[str]:
    labels: list[str] = []
    for low, high in zip(edges, edges[1:]):
        high_text = "infinity" if high == "infinity" else f"{float(high):g}"
        labels.append(f"[{float(low):g},{high_text})")
    return labels


def gap_bin_index(gap: float, edges: list[Any]) -> int:
    numeric = [math.inf if edge == "infinity" else float(edge) for edge in edges]
    for index in range(len(numeric) - 1):
        if numeric[index] <= gap < numeric[index + 1]:
            return index
    raise TruthSupportError("truth gap falls outside frozen bins")


def aggregate_truth(
    selected: list[dict[str, Any]],
    vault: dict[str, dict[str, Any]],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    truth = protocol["truth_support"]
    tolerance = float(truth["absolute_tolerance"])
    edges = truth["fixed_gap_edges"]
    labels = gap_bin_labels(edges)
    bins = {label: 0 for label in labels}
    per_task: dict[str, dict[str, int]] = collections.defaultdict(
        lambda: {"selected_parents": 0, "truth_available_parents": 0, "nontied_parents": 0}
    )
    tied = nontied = unavailable = 0
    for parent in selected:
        task = parent["task"]
        per_task[task]["selected_parents"] += 1
        values = [vault[card]["y_norm"] for card in parent["candidate_card_ids"]]
        if any(value is None for value in values):
            unavailable += 1
            continue
        gap = max(float(value) for value in values) - min(float(value) for value in values)
        if gap < 0 or not math.isfinite(gap):
            raise TruthSupportError("invalid truth gap")
        per_task[task]["truth_available_parents"] += 1
        bins[labels[gap_bin_index(gap, edges)]] += 1
        if gap > tolerance:
            nontied += 1
            per_task[task]["nontied_parents"] += 1
        else:
            tied += 1

    nontied_counts = {
        task: counts["nontied_parents"]
        for task, counts in sorted(per_task.items())
        if counts["nontied_parents"] > 0
    }
    dominant_task = max(nontied_counts, key=lambda task: (nontied_counts[task], task)) if nontied_counts else None
    dominant_count = nontied_counts.get(dominant_task, 0) if dominant_task is not None else 0
    dominant_share = dominant_count / nontied if nontied else None
    selected_runs = len({row["run_id"] for row in selected})
    gates_spec = protocol["eligibility_gates_for_requesting_replay_design"]
    gates = {
        "nontied_selected_parents": nontied >= gates_spec["nontied_selected_parents_minimum"],
        "tasks_with_nontied_parent": len(nontied_counts) >= gates_spec["tasks_with_nontied_parent_minimum"],
        "dominant_nontied_task_share": dominant_share is not None
        and dominant_share <= gates_spec["dominant_nontied_task_share_maximum"],
        "selected_physical_runs": selected_runs >= gates_spec["selected_physical_runs_minimum"],
    }
    all_pass = all(gates.values())
    return {
        "counts": {
            "selected_parents": len(selected),
            "selected_candidates": sum(row["candidate_count"] for row in selected),
            "selected_physical_runs": selected_runs,
            "selected_tasks": len(per_task),
            "truth_available_parents": tied + nontied,
            "truth_unavailable_parents": unavailable,
            "tied_parents": tied,
            "nontied_parents": nontied,
            "tasks_with_nontied_parent": len(nontied_counts),
        },
        "gap_distribution": bins,
        "per_task": dict(sorted(per_task.items())),
        "balance": {
            "dominant_nontied_task": dominant_task,
            "dominant_nontied_parents": dominant_count,
            "dominant_nontied_task_share": dominant_share,
        },
        "gates": {**gates, "all_pass": all_pass},
    }


def repository_head(repo: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    value = completed.stdout.strip()
    if completed.returncode or len(value) != 40:
        raise TruthSupportError("cannot resolve source commit")
    return valid_sha(value, "source commit", length=40)


def write_rows(path: Path, rows: Iterable[dict[str, Any]]) -> str:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            if set(row) != ROW_KEYS:
                raise TruthSupportError("internal selected-parent schema mismatch")
            handle.write(canonical(row) + "\n")
    return sha256(path)


def produce(
    protocol_path: Path,
    expected_protocol_sha: str,
    cohort_dir: Path,
    expected_cohort_summary_sha: str,
    state_root: Path,
    repo: Path,
    out_dir: Path,
) -> dict[str, Any]:
    if out_dir.exists():
        raise FileExistsError(f"refusing to overwrite truth-support output: {out_dir}")
    protocol = load_protocol(protocol_path, expected_protocol_sha)
    runs, cohort_summary = load_cohort(cohort_dir, expected_protocol_sha, expected_cohort_summary_sha)
    sibling_sets, vault, intake_shas = load_truth_inputs(state_root, runs, cohort_summary)
    selection_spec = protocol["parent_selection"]
    selected, eligible_parents, runs_with_eligible = select_parents(
        runs,
        sibling_sets,
        vault,
        selection_spec["seed"],
        selection_spec["max_parents_per_physical_run"],
    )
    aggregate = aggregate_truth(selected, vault, protocol)
    all_pass = aggregate["gates"]["all_pass"]

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.tmp.", dir=out_dir.parent))
    try:
        rows_sha = write_rows(temporary / "selected_parents.jsonl", selected)
        summary = {
            "protocol": OUTPUT_PROTOCOL,
            "status": (
                "TRUTH_SUPPORT_ELIGIBLE_REPLAY_DESIGN_REQUEST_ONLY"
                if all_pass
                else "TRUTH_SUPPORT_KILL_NO_REPLAY_REQUEST"
            ),
            "selection": {
                "seed": selection_spec["seed"],
                "ordering": selection_spec["ordering"],
                "max_parents_per_physical_run": selection_spec["max_parents_per_physical_run"],
                "parent_eligibility": selection_spec["eligibility"],
                "score_magnitude_used_for_eligibility_or_lottery": False,
                "outcome_dependent_reselection": False,
            },
            "inputs": {
                "protocol_sha256": valid_sha(expected_protocol_sha, "protocol SHA"),
                "cohort_summary_sha256": valid_sha(expected_cohort_summary_sha, "cohort summary SHA"),
                "cohort_runs_sha256": sha256(cohort_dir / "cohort_runs.jsonl"),
                "cohort_archives_sha256": sha256(cohort_dir / "cohort_archives.jsonl"),
                "intake_summary_sha256": dict(sorted(intake_shas.items())),
            },
            "identity": {
                "closed_before_label_open": True,
                "cohort_physical_runs": len(runs),
                "eligible_parents_before_per_run_cap": eligible_parents,
                "runs_with_eligible_parent": runs_with_eligible,
                "runs_without_eligible_parent": len(runs) - runs_with_eligible,
            },
            "truth_support": {
                "definition": protocol["truth_support"]["primary_informative_definition"],
                "absolute_tolerance": protocol["truth_support"]["absolute_tolerance"],
                "fixed_gap_edges": protocol["truth_support"]["fixed_gap_edges"],
                **aggregate,
            },
            "decision": {
                "all_gates_must_pass": True,
                "replay_design_request_eligible": all_pass,
                "replay_submission_authorized": False,
                "gpu_jobs_authorized": 0,
                "failure_action": protocol["eligibility_gates_for_requesting_replay_design"]["failure_action"],
                "pass_action": protocol["eligibility_gates_for_requesting_replay_design"]["pass_action"],
            },
            "blindness": {
                "label_vault_opened_after_identity_closure": True,
                "graded_values_used_beyond_finiteness_for_selection": False,
                "y_norm_used_for_selection": False,
                "raw_label_values_written": False,
                "blind_code_view_opened": False,
                "score_directory_opened": False,
                "replay_outcomes_opened": False,
            },
            "outputs": {"selected_parents_sha256": rows_sha},
            "implementation": {
                "source_commit": repository_head(repo),
                "script_sha256": sha256(Path(__file__)),
                "python": platform.python_version(),
            },
        }
        (temporary / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, out_dir)
    except Exception:
        for child in temporary.iterdir():
            child.unlink()
        temporary.rmdir()
        raise
    return summary


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--cohort-dir", required=True, type=Path)
    parser.add_argument("--expect-cohort-summary-sha256", required=True)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    summary = produce(
        args.protocol,
        args.expect_protocol_sha256,
        args.cohort_dir,
        args.expect_cohort_summary_sha256,
        args.state_root,
        args.repo,
        args.out_dir,
    )
    print(
        canonical(
            {
                "status": summary["status"],
                "selected_parents": summary["truth_support"]["counts"]["selected_parents"],
                "nontied_parents": summary["truth_support"]["counts"]["nontied_parents"],
                "tasks_with_nontied_parent": summary["truth_support"]["counts"]["tasks_with_nontied_parent"],
                "replay_design_request_eligible": summary["decision"]["replay_design_request_eligible"],
                "replay_submission_authorized": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
