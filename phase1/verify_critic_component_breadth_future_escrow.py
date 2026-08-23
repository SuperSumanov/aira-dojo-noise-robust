#!/usr/bin/env python3
"""Independent source-refit verification of the future component-breadth escrow."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import itertools
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from phase1 import verify_critic_component_breadth_equal_budget as selection_reference


PROTOCOL = "critic-component-breadth-future-escrow-v1"
STATUS = "FUTURE_COMPONENT_BREADTH_PREDICTION_ESCROW_COMPLETE"
CONTRACT_SHA256 = "c52a71c36edb30a5dec965d6509387b386347acb50ac5e6a3ca789a778fd472b"
COHORT_PROTOCOL_SHA256 = "54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d"
ARMS = ("broad", "concentrated", "random")
BLIND_KEYS = {
    "card_id", "task", "run_id", "code", "code_sha256", "lineage",
    "generation_started_at_utc", "source_sha256",
}
LINEAGE_KEYS = {"depth", "step", "n_siblings", "op", "parent"}
RUN_KEYS = {
    "archive_relative_path", "archive_sha256", "drop_id", "endpoints", "flow_status",
    "generation_started_at_utc", "journal_sha256", "run_id", "task",
}
ARCHIVE_KEYS = {
    "archive_relative_path", "archive_sha256", "archive_size",
    "cumulative_unique_physical_runs", "drop_id", "intake_summary_sha256", "mtime_ns",
    "physical_runs", "source_provenance_sha256",
}
PAIR_KEYS = {"task", "run_id", "parent", "left", "right"}
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class VerificationError(RuntimeError):
    """Independent reconstruction or artifact mismatch."""


def digest(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            state.update(block)
    return state.hexdigest()


def stable_file_bytes(path: Path, label: str) -> bytes:
    """Read one regular file through a no-follow descriptor and reject mutation."""
    if path.is_symlink():
        raise VerificationError(f"symlinked {label}")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise VerificationError(f"cannot open stable {label}") from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise VerificationError(f"non-regular {label}")
        chunks: list[bytes] = []
        while True:
            block = os.read(descriptor, 1 << 20)
            if not block:
                break
            chunks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    payload = b"".join(chunks)
    if identity_before != identity_after or len(payload) != before.st_size:
        raise VerificationError(f"{label} changed while being read")
    return payload


def rows_from_bytes(payload: bytes, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        text = payload.decode("utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            if not line:
                raise VerificationError(f"blank JSONL row: {label}:{number}")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise VerificationError(f"JSONL object mismatch: {label}:{number}")
            rows.append(value)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot decode {label}") from error
    return rows


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def credential_free(path: Path) -> bool:
    overlap = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            window = overlap + chunk
            if CREDENTIAL.search(window):
                return False
            overlap = window[-512:]
    return True


def load_contract(path: Path) -> dict[str, Any]:
    if digest(path) != CONTRACT_SHA256:
        raise VerificationError("future escrow contract identity mismatch")
    value = json.loads(path.read_text(encoding="utf-8"))
    evaluation = value.get("evaluation_after_truth_open") or {}
    support = evaluation.get("support_gates") or {}
    normalized = evaluation.get("faithful_normalized_secondary") or {}
    claim = value.get("claim_boundary") or {}
    alias = (claim.get("known_before_freeze") or {}).get("raw_vs_y_norm_alias_audit") or {}
    if (
        not isinstance(value, dict)
        or value.get("protocol") != PROTOCOL
        or value.get("status") != "PREREGISTERED_PREDICTION_ESCROW_WAITING_CLOSED_COHORT"
        or (value.get("selection") or {}).get("seeds") != [20260823, 20260824, 20260825]
        or (value.get("selection") or {}).get("expected_pairs_per_arm_seed") != 2353
        or (value.get("cohort") or {}).get("source_identity_protocol_sha256")
        != COHORT_PROTOCOL_SHA256
        or (value.get("cohort") or {}).get("raw_archive_completeness_claim_allowed") is not False
        or (value.get("cohort") or {}).get("first_closure_anchor_required") is not True
        or (value.get("cohort") or {}).get("first_closure_anchor_path")
        != "/research/d7/spc/yzyang4/score-channel-future-identity-cohort/FIRST_CLOSED_COHORT_ANCHOR.json"
        or (value.get("resources") or {}).get("maximum_unique_cpu_critic_fits_per_implementation") != 9
        or support.get("raw_nontied_selected_parents_minimum") != 200
        or support.get("raw_nontied_contributing_physical_runs_minimum") != 150
        or support.get("tasks_with_raw_nontied_selected_parent_minimum") != 50
        or support.get("dominant_task_selected_parent_share_maximum") != 0.2
        or normalized.get("confirmatory_claim_allowed") is not False
        or normalized.get("may_rescue_primary") is not False
        or evaluation.get("tie_credit_for_exact_zero_prediction_margin") != 0.5
        or evaluation.get("truth_tied_pair_credit") is not None
        or alias.get("alias_parents") != 147
        or alias.get("alias_tasks") != 16
        or alias.get("known_before_raw_endpoint_selection") is not True
        or "component_or_run_breadth_isolated_as_the_causal_mechanism"
        not in (claim.get("forbidden") or [])
    ):
        raise VerificationError("future escrow contract semantics mismatch")
    return value


def repository_head(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    value = result.stdout.strip().lower()
    if result.returncode or len(value) != 40 or any(character not in "0123456789abcdef" for character in value):
        raise VerificationError("cannot resolve source commit")
    return value


def read_jsonl(path: Path, expected_keys: set[str] | None = None) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise VerificationError(f"not a regular JSONL file: {path.name}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                raise VerificationError(f"blank JSONL row: {path.name}:{number}")
            value = json.loads(line)
            if not isinstance(value, dict) or (expected_keys is not None and set(value) != expected_keys):
                raise VerificationError(f"JSONL schema mismatch: {path.name}:{number}")
            rows.append(value)
    return rows


def valid_sha(value: Any, label: str, *, length: int = 64) -> str:
    if not isinstance(value, str):
        raise VerificationError(f"invalid {label}")
    lowered = value.lower()
    if len(lowered) != length or any(character not in "0123456789abcdef" for character in lowered):
        raise VerificationError(f"invalid {label}")
    return lowered


def read_object(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise VerificationError(f"{label} is not a regular file")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise VerificationError(f"{label} is not an object")
    return value


def load_cohort_identity(
    cohort_dir: Path, expected_summary_sha: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if cohort_dir.is_symlink() or not cohort_dir.is_dir():
        raise VerificationError("independent cohort directory is unsafe")
    summary_path = cohort_dir / "summary.json"
    if digest(summary_path) != valid_sha(expected_summary_sha, "cohort summary SHA"):
        raise VerificationError("independent cohort summary SHA mismatch")
    summary = read_object(summary_path, "cohort summary")
    inputs, outputs = summary.get("inputs") or {}, summary.get("outputs") or {}
    closure, inventory = summary.get("closure") or {}, summary.get("inventory") or {}
    blindness = summary.get("blindness") or {}
    if (
        summary.get("protocol") != "score-channel-future-identity-cohort-v1"
        or summary.get("status") != "FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD"
        or inputs.get("protocol_sha256") != COHORT_PROTOCOL_SHA256
        or closure.get("accepted_unique_physical_run_target") != 300
        or closure.get("complete_boundary_archive_included") is not True
        or closure.get("remaining_runs_to_target") != 0
        or not isinstance(closure.get("boundary_archive"), str)
        or blindness.get("label_vault_opened") is not False
        or blindness.get("score_or_outcome_opened") is not False
        or blindness.get("truth_support_computed") is not False
        or blindness.get("replay_submission_authorized") is not False
    ):
        raise VerificationError("independent cohort closure contract mismatch")
    runs_path = cohort_dir / "cohort_runs.jsonl"
    archives_path = cohort_dir / "cohort_archives.jsonl"
    if (
        digest(runs_path) != valid_sha(outputs.get("cohort_runs_sha256"), "cohort runs SHA")
        or digest(archives_path)
        != valid_sha(outputs.get("cohort_archives_sha256"), "cohort archives SHA")
    ):
        raise VerificationError("independent cohort output SHA mismatch")
    runs = read_jsonl(runs_path, RUN_KEYS)
    archives = read_jsonl(archives_path, ARCHIVE_KEYS)
    if (
        len(runs) < 300
        or inventory.get("selected_physical_runs") != len(runs)
        or inventory.get("selected_archives") != len(archives)
    ):
        raise VerificationError("independent cohort inventory mismatch")
    archive_by_drop: dict[str, dict[str, Any]] = {}
    cumulative = 0
    ordering: list[tuple[int, bytes]] = []
    for row in archives:
        drop, relative = row.get("drop_id"), row.get("archive_relative_path")
        count, mtime = row.get("physical_runs"), row.get("mtime_ns")
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
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
            or isinstance(mtime, bool)
            or not isinstance(mtime, int)
            or mtime < 0
        ):
            raise VerificationError("independent cohort archive row mismatch")
        cumulative += count
        if row.get("cumulative_unique_physical_runs") != cumulative:
            raise VerificationError("independent cohort cumulative count mismatch")
        for key in ("archive_sha256", "intake_summary_sha256", "source_provenance_sha256"):
            valid_sha(row.get(key), f"cohort {key}")
        archive_by_drop[drop] = row
        ordering.append((mtime, relative.encode("utf-8")))
    if (
        ordering != sorted(ordering)
        or cumulative != len(runs)
        or archives[-1]["archive_relative_path"] != closure["boundary_archive"]
    ):
        raise VerificationError("independent cohort order/boundary mismatch")
    seen: set[str] = set()
    per_drop: collections.Counter[str] = collections.Counter()
    per_task: collections.Counter[str] = collections.Counter()
    for row in runs:
        journal = valid_sha(row.get("journal_sha256"), "cohort journal SHA")
        drop, run, task = row.get("drop_id"), row.get("run_id"), row.get("task")
        archive = archive_by_drop.get(str(drop))
        endpoints, flow = row.get("endpoints"), row.get("flow_status")
        if (
            run != f"journal:{journal}"
            or run in seen
            or not isinstance(task, str)
            or not task
            or archive is None
            or row.get("archive_relative_path") != archive["archive_relative_path"]
            or row.get("archive_sha256") != archive["archive_sha256"]
            or not isinstance(row.get("generation_started_at_utc"), str)
            or not row["generation_started_at_utc"]
            or isinstance(endpoints, bool)
            or not isinstance(endpoints, int)
            or endpoints < 0
            or flow not in {"scoreable", "no_scoreable_code"}
            or (flow == "scoreable") != (endpoints > 0)
        ):
            raise VerificationError("independent cohort run identity mismatch")
        seen.add(run)
        per_drop[str(drop)] += 1
        per_task[task] += 1
    if any(per_drop[drop] != row["physical_runs"] for drop, row in archive_by_drop.items()):
        raise VerificationError("independent cohort archive membership mismatch")
    if (
        inventory.get("per_task_selected_runs") != dict(sorted(per_task.items()))
        or inventory.get("selected_tasks") != len(per_task)
    ):
        raise VerificationError("independent cohort task inventory mismatch")
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
        raise VerificationError("independent cohort input hash registry mismatch")
    return runs, archives, summary


def verify_intake_identity(
    state_root: Path, archive: dict[str, Any]
) -> tuple[Path, dict[str, Any]]:
    intake = state_root / "intakes" / archive["drop_id"]
    if (
        intake.is_symlink()
        or not intake.is_dir()
        or intake.resolve().parent != (state_root / "intakes").resolve()
    ):
        raise VerificationError("independent intake path is unsafe")
    summary_path = intake / "summary.json"
    if digest(summary_path) != archive["intake_summary_sha256"]:
        raise VerificationError("independent intake summary SHA mismatch")
    summary = read_object(summary_path, "intake summary")
    security, blindness = summary.get("security") or {}, summary.get("blindness") or {}
    configuration = summary.get("configuration") or {}
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
    if (
        summary.get("protocol") != "prospective_drop_intake_v1"
        or summary.get("status") != "PROSPECTIVE_DROP_INTAKE_COMPLETE"
        or configuration.get("archive_selection") != "explicit_names"
        or configuration.get("selected_archive_names")
        != [Path(archive["archive_relative_path"]).name]
        or blindness.get("labels_used_for_run_selection") is not False
        or blindness.get("labels_used_for_endpoint_selection") is not False
        or blindness.get("label_values_printed") is not False
        or blindness.get("metrics_computed") != []
        or any(security.get(key) != value for key, value in expected_security.items())
    ):
        raise VerificationError("independent intake contract mismatch")
    return intake, summary


def validate_training(
    rows: list[dict[str, Any]], runs: dict[str, str], configs: dict[str, tuple[Any, ...]]
) -> dict[str, Any]:
    components: dict[str, str] = {}
    for row in rows:
        component = row["pair_component_id"]
        if component in components and components[component] != row["task"]:
            raise VerificationError("training component crosses tasks")
        components[component] = row["task"]
        if configs[row["better"]] != configs[row["worse"]] or configs[row["better"]][0] != row["task"]:
            raise VerificationError("training pair exact-config mismatch")
    return {
        "pairs": len(rows),
        "tasks": len({row["task"] for row in rows}),
        "components": len(components),
        "runs": len({runs[item] for row in rows for item in (row["better"], row["worse"])}),
    }


def validate_selections(
    chosen: dict[tuple[int, str], list[dict[str, Any]]],
    runs: dict[str, str],
    contract: dict[str, Any],
) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    expected = contract["selection"]
    for seed in expected["seeds"]:
        by_arm = {
            arm: selection_reference.selection_receipt(seed, arm, chosen[(seed, arm)], runs)
            for arm in ARMS
        }
        receipts.extend(by_arm[arm] for arm in ARMS)
        if (
            {row["pairs"] for row in by_arm.values()} != {expected["expected_pairs_per_arm_seed"]}
            or len({row["task_pair_budget_sha256"] for row in by_arm.values()}) != 1
            or by_arm["broad"]["components"] != expected["expected_broad_components_per_seed"]
            or by_arm["concentrated"]["components"] != expected["expected_concentrated_components_per_seed"]
            or by_arm["broad"]["runs"] - by_arm["concentrated"]["runs"]
            != expected["expected_broad_minus_concentrated_runs_by_seed"][str(seed)]
            or any(
                row["task_pair_budget_sha256"] != expected["expected_task_pair_budget_sha256"]
                or row["unordered_pairs_sha256"]
                != expected["expected_unordered_pairs_sha256"][f"{arm}_s{seed}"]
                for arm, row in by_arm.items()
            )
        ):
            raise VerificationError("independent training selection receipt mismatch")
    return receipts


def load_future(
    state_root: Path,
    cohort_dir: Path,
    expected_cohort_summary_sha: str,
) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], dict[str, Any],
    dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, Any],
]:
    runs, archives, cohort_summary = load_cohort_identity(
        cohort_dir, expected_cohort_summary_sha
    )
    allowed = {row["run_id"]: row for row in runs}
    for row in runs:
        endpoints = row.get("endpoints")
        flow = row.get("flow_status")
        if (
            isinstance(endpoints, bool)
            or not isinstance(endpoints, int)
            or endpoints < 0
            or flow not in {"scoreable", "no_scoreable_code"}
            or (flow == "scoreable") != (endpoints > 0)
            or not isinstance(row.get("generation_started_at_utc"), str)
            or not row["generation_started_at_utc"]
        ):
            raise VerificationError("independent cohort run flow mismatch")
    cards: dict[str, dict[str, Any]] = {}
    pairs: list[dict[str, Any]] = []
    pair_keys: set[tuple[str, str]] = set()
    intake_hashes: dict[str, str] = {}
    blind_hashes: dict[str, str] = {}
    structure_hashes: dict[str, str] = {}
    for archive in archives:
        drop = archive["drop_id"]
        intake, summary = verify_intake_identity(state_root, archive)
        outputs = summary.get("outputs") or {}
        configuration = summary.get("configuration") or {}
        blind = intake / "eligible_blind_manifest.jsonl"
        structure = intake / "eligible_structural_pairs.jsonl"
        blind_sha = outputs.get("eligible_blind_manifest_sha256")
        structure_sha = outputs.get("eligible_structural_pairs_sha256")
        if (
            not isinstance(blind_sha, str) or digest(blind) != blind_sha
            or not isinstance(structure_sha, str) or digest(structure) != structure_sha
            or not credential_free(blind) or not credential_free(structure)
            or configuration.get("archive_selection") != "explicit_names"
            or configuration.get("selected_archive_names")
            != [Path(archive["archive_relative_path"]).name]
        ):
            raise VerificationError("independent blind input hash/security mismatch")
        intake_hashes[drop] = archive["intake_summary_sha256"]
        blind_hashes[drop] = blind_sha
        structure_hashes[drop] = structure_sha
        blind_rows = read_jsonl(blind, BLIND_KEYS)
        pair_rows = read_jsonl(structure, PAIR_KEYS)
        inventory = summary.get("inventory") or {}
        if (
            inventory.get("eligible_endpoints") != len(blind_rows)
            or inventory.get("eligible_structural_pairs") != len(pair_rows)
        ):
            raise VerificationError("independent intake support inventory mismatch")
        for row in blind_rows:
            lineage = row.get("lineage")
            if not isinstance(lineage, dict) or set(lineage) != LINEAGE_KEYS:
                raise VerificationError("independent blind lineage mismatch")
            identifier, run_id, task, code = row["card_id"], row["run_id"], row["task"], row["code"]
            owner = allowed.get(run_id)
            if (
                not all(isinstance(value, str) and value for value in (identifier, run_id, task, code))
                or identifier in cards or owner is None or owner["drop_id"] != drop
                or owner["task"] != task or owner["journal_sha256"] != row["source_sha256"]
                or owner["generation_started_at_utc"] != row["generation_started_at_utc"]
                or run_id != f"journal:{row['source_sha256']}"
                or hashlib.sha256(code.encode()).hexdigest() != row["code_sha256"]
            ):
                raise VerificationError("independent blind endpoint mismatch")
            for key in ("depth", "step", "n_siblings"):
                value = lineage[key]
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise VerificationError("independent blind lineage integer mismatch")
            cards[identifier] = {
                "task": task,
                "run_id": run_id,
                "parent": lineage["parent"],
                "code": code,
                "code_sha256": row["code_sha256"],
                "generation_started_at_utc": row["generation_started_at_utc"],
                "n_siblings": lineage["n_siblings"],
            }
        for row in pair_rows:
            left, right = row["left"], row["right"]
            key = tuple(sorted((left, right)))
            owner = allowed.get(row["run_id"])
            if (
                not left < right or key in pair_keys or owner is None or owner["drop_id"] != drop
                or left not in cards or right not in cards
                or any(
                    cards[item]["task"] != row["task"]
                    or cards[item]["run_id"] != row["run_id"]
                    or cards[item]["parent"] != row["parent"]
                    for item in (left, right)
                )
            ):
                raise VerificationError("independent structural pair mismatch")
            pair_keys.add(key)
            pairs.append(row)
    if not cards or not pairs:
        raise VerificationError("independent future support is empty")
    counts = collections.Counter(row["run_id"] for row in cards.values())
    if any(
        allowed[run]["endpoints"] != counts.get(run, 0)
        or (allowed[run]["flow_status"] == "scoreable") != (counts.get(run, 0) > 0)
        for run in allowed
    ):
        raise VerificationError("independent endpoint/run accounting mismatch")
    groups: dict[tuple[str, str, str], set[str]] = collections.defaultdict(set)
    claims: dict[tuple[str, str, str], set[int]] = collections.defaultdict(set)
    for identifier, card in cards.items():
        if card["parent"]:
            group = card["task"], card["run_id"], card["parent"]
            groups[group].add(identifier)
            claims[group].add(card["n_siblings"])
    expected_edges = {
        (task, run, parent, left, right)
        for (task, run, parent), children in groups.items()
        for left, right in itertools.combinations(sorted(children), 2)
    }
    observed_edges: set[tuple[str, str, str, str, str]] = set()
    for row in pairs:
        observed_edges.add((row["task"], row["run_id"], row["parent"], row["left"], row["right"]))
    if observed_edges != expected_edges:
        raise VerificationError("independent sibling population mismatch")
    if any(
        len(values) != 1 or next(iter(values)) < len(groups[group]) - 1
        for group, values in claims.items()
    ):
        raise VerificationError("independent sibling-count claim mismatch")
    pairs.sort(key=lambda row: (row["task"], row["run_id"], row["parent"], row["left"], row["right"]))
    inputs = {
        "intake_summary_sha256": dict(sorted(intake_hashes.items())),
        "eligible_blind_manifest_sha256": dict(sorted(blind_hashes.items())),
        "eligible_structural_pairs_sha256": dict(sorted(structure_hashes.items())),
    }
    return runs, archives, cohort_summary, cards, pairs, inputs


def refit_scores(
    selected: list[dict[str, Any]],
    training_codes: dict[str, str],
    training_runs: dict[str, str],
    future_cards: dict[str, dict[str, Any]],
) -> tuple[dict[str, float], dict[str, Any]]:
    train_ids = sorted({item for row in selected for item in (row["better"], row["worse"])})
    future_ids = sorted(future_cards)
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        max_features=30000,
        min_df=3,
        sublinear_tf=True,
        dtype=np.float64,
    )
    train_matrix = vectorizer.fit_transform([training_codes[item][:20000] for item in train_ids]).tocsr()
    index = {identifier: position for position, identifier in enumerate(train_ids)}
    better = np.fromiter((index[row["better"]] for row in selected), dtype=np.int64)
    worse = np.fromiter((index[row["worse"]] for row in selected), dtype=np.int64)
    differences = train_matrix[better] - train_matrix[worse]
    design = sparse.vstack((differences, -differences), format="csr")
    labels = np.r_[np.ones(len(selected), dtype=np.int8), np.zeros(len(selected), dtype=np.int8)]
    model = LogisticRegression(C=0.5, max_iter=1500, solver="lbfgs", random_state=0).fit(design, labels)
    weights = np.asarray(model.coef_, dtype=np.float64).reshape(-1)
    forward = np.asarray(differences.dot(weights), dtype=np.float64).reshape(-1)
    reverse = np.asarray((-differences).dot(weights), dtype=np.float64).reshape(-1)
    anti = float(np.max(np.abs(forward + reverse)))
    if int(model.n_iter_[0]) >= 1500 or not np.isfinite(weights).all() or anti != 0.0:
        raise VerificationError("independent critic fit failed")
    matrix = vectorizer.transform([future_cards[item]["code"][:20000] for item in future_ids])
    values = np.asarray(matrix.dot(weights), dtype=np.float64).reshape(-1)
    if values.shape != (len(future_ids),) or not np.isfinite(values).all():
        raise VerificationError("independent future score failed")
    return dict(zip(future_ids, map(float, values))), {
        "train_pairs": len(selected),
        "train_endpoints": len(train_ids),
        "train_runs": len({training_runs[item] for item in train_ids}),
        "train_components": len({row["pair_component_id"] for row in selected}),
        "train_tasks": len({row["task"] for row in selected}),
        "vocabulary_size": len(vectorizer.vocabulary_),
        "lr_iterations": int(model.n_iter_[0]),
        "lr_intercept": float(model.intercept_[0]),
        "coef_l2": float(np.linalg.norm(weights)),
        "anti_symmetry_max_abs": anti,
        "future_endpoints_scored": len(future_ids),
    }


def close_enough(expected: Any, observed: Any, location: str = "root") -> float:
    if isinstance(expected, dict):
        if not isinstance(observed, dict) or set(expected) != set(observed):
            raise VerificationError(f"mapping mismatch at {location}")
        return max(
            (close_enough(value, observed[key], f"{location}.{key}") for key, value in expected.items()),
            default=0.0,
        )
    if isinstance(expected, list):
        if not isinstance(observed, list) or len(expected) != len(observed):
            raise VerificationError(f"list mismatch at {location}")
        return max(
            (close_enough(left, right, f"{location}[{index}]") for index, (left, right) in enumerate(zip(expected, observed))),
            default=0.0,
        )
    if isinstance(expected, float):
        try:
            difference = abs(expected - float(observed))
        except (TypeError, ValueError) as error:
            raise VerificationError(f"numeric mismatch at {location}") from error
        if not np.isfinite(difference) or difference > 1e-12:
            raise VerificationError(f"numeric mismatch at {location}: {difference}")
        return difference
    if expected != observed:
        raise VerificationError(f"value mismatch at {location}")
    return 0.0


def verify(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.absolute()
    expected_contract = repo_root / "phase1" / "critic_component_breadth_future_escrow_v1.json"
    expected_source_contract = repo_root / "phase1" / "critic_component_breadth_equal_budget_v1.json"
    expected_producer = repo_root / "phase1" / "critic_component_breadth_future_escrow.py"
    if (
        args.contract.absolute() != expected_contract
        or args.source_selection_contract.absolute() != expected_source_contract
        or args.producer_source.absolute() != expected_producer
        or any(path.is_symlink() for path in (args.contract, args.source_selection_contract, args.producer_source))
        or args.state_root.is_symlink()
        or args.cohort_dir.is_symlink()
    ):
        raise VerificationError("verifier source/input path binding mismatch")
    contract = load_contract(args.contract)
    source_contract = selection_reference.load_contract(args.source_selection_contract)
    selection_reference.attest(args.training_cards, "cards")
    selection_reference.attest(args.train_pairs, "train")
    train = selection_reference.pair_file(args.train_pairs, "train")
    needed = {item for row in train for item in (row["better"], row["worse"])}
    training_codes, training_runs, training_configs, card_inventory = selection_reference.card_projection(
        args.training_cards, needed
    )
    training_integrity = validate_training(train, training_runs, training_configs)
    chosen, _, _ = selection_reference.selections(train, [], source_contract)
    selection_receipts = validate_selections(chosen, training_runs, contract)
    cohort_runs, _archives, _cohort_summary, future_cards, future_pairs, future_inputs = load_future(
        args.state_root, args.cohort_dir, args.expect_cohort_summary_sha256
    )
    training_code_shas = {hashlib.sha256(code.encode()).hexdigest() for code in training_codes.values()}
    if set(future_cards) & set(training_codes) or {row["code_sha256"] for row in future_cards.values()} & training_code_shas:
        raise VerificationError("independent future/training overlap")

    scores: dict[str, dict[str, float]] = {identifier: {} for identifier in future_cards}
    fit_receipts: dict[tuple[int, str], dict[str, Any]] = {}
    model_keys: list[str] = []
    for seed in contract["selection"]["seeds"]:
        for arm in ARMS:
            key = f"{arm}_s{seed}"
            model_keys.append(key)
            values, receipt = refit_scores(chosen[(seed, arm)], training_codes, training_runs, future_cards)
            for identifier, value in values.items():
                scores[identifier][key] = value
            fit_receipts[(seed, arm)] = receipt

    expected_files = {
        "endpoint_scores.csv", "pair_predictions.jsonl", "training_selection_receipts.jsonl",
        "summary.json", "artifact_manifest.json",
    }
    if (
        args.artifact.is_symlink()
        or not args.artifact.is_dir()
        or args.artifact.absolute() != args.artifact.resolve()
        or {path.name for path in args.artifact.iterdir()} != expected_files
    ):
        raise VerificationError("artifact file set mismatch")
    payloads = {
        name: stable_file_bytes(args.artifact / name, f"artifact {name}")
        for name in sorted(expected_files)
    }
    manifest = json.loads(payloads["artifact_manifest.json"].decode("utf-8"))
    artifact_names = expected_files - {"artifact_manifest.json"}
    expected_manifest = {
        "protocol": f"{PROTOCOL}-artifact-manifest-v1",
        "contract_sha256": CONTRACT_SHA256,
        "artifacts": {
            name: {
                "sha256": hashlib.sha256(payloads[name]).hexdigest(),
                "bytes": len(payloads[name]),
            }
            for name in sorted(artifact_names)
        },
    }
    close_enough(expected_manifest, manifest, "manifest")

    reader = csv.DictReader(io.StringIO(payloads["endpoint_scores.csv"].decode("utf-8"), newline=""))
    expected_fields = [
        "card_id", "task", "run_id", "parent", "code_sha256", "generation_started_at_utc", *model_keys
    ]
    if reader.fieldnames != expected_fields:
        raise VerificationError("endpoint score field mismatch")
    endpoint_rows = list(reader)
    if [row["card_id"] for row in endpoint_rows] != sorted(future_cards):
        raise VerificationError("endpoint score order/coverage mismatch")
    maximum_difference = 0.0
    for row in endpoint_rows:
        identifier = row["card_id"]
        card = future_cards[identifier]
        expected_identity = {
            "task": card["task"], "run_id": card["run_id"], "parent": card["parent"],
            "code_sha256": card["code_sha256"],
            "generation_started_at_utc": card["generation_started_at_utc"],
        }
        if any(row[key] != value for key, value in expected_identity.items()):
            raise VerificationError("endpoint identity mismatch")
        for key in model_keys:
            difference = abs(float(row[key]) - scores[identifier][key])
            if not np.isfinite(difference) or difference > 1e-12:
                raise VerificationError("independent endpoint score mismatch")
            maximum_difference = max(maximum_difference, difference)

    observed_pairs = rows_from_bytes(payloads["pair_predictions.jsonl"], "pair predictions")
    if len(observed_pairs) != len(future_pairs):
        raise VerificationError("pair prediction count mismatch")
    for index, (source, observed) in enumerate(zip(future_pairs, observed_pairs)):
        expected: dict[str, Any] = {
            **source,
            "pair_key_sha256": hashlib.sha256("\0".join((source["left"], source["right"])).encode()).hexdigest(),
        }
        for key in model_keys:
            margin = scores[source["left"]][key] - scores[source["right"]][key]
            expected[f"{key}_margin_left_minus_right"] = float(format(margin, ".17g"))
            expected[f"{key}_selected"] = source["left"] if margin > 0 else source["right"] if margin < 0 else "tie"
        maximum_difference = max(maximum_difference, close_enough(expected, observed, f"pair[{index}]"))

    observed_receipts = rows_from_bytes(
        payloads["training_selection_receipts.jsonl"], "training selection receipts"
    )
    expected_receipts = [
        {**row, **fit_receipts[(row["selection_seed"], row["arm"])]}
        for row in selection_receipts
    ]
    maximum_difference = max(
        maximum_difference, close_enough(expected_receipts, observed_receipts, "training_receipts")
    )
    tie_counts = {key: 0 for key in model_keys}
    for pair in future_pairs:
        for key in model_keys:
            tie_counts[key] += scores[pair["left"]][key] == scores[pair["right"]][key]
    expected_summary = {
        "protocol": PROTOCOL,
        "contract_sha256": CONTRACT_SHA256,
        "status": STATUS,
        "source_commit": repository_head(args.repo_root),
        "source_sha256": digest(args.producer_source),
        "inputs": {
            "training_cards": contract["inputs"]["training_cards"],
            "component_clean_train": contract["inputs"]["component_clean_train"],
            "cohort_summary_sha256": args.expect_cohort_summary_sha256,
            "cohort_runs_sha256": digest(args.cohort_dir / "cohort_runs.jsonl"),
            "cohort_archives_sha256": digest(args.cohort_dir / "cohort_archives.jsonl"),
            **future_inputs,
        },
        "training": {
            "card_inventory": card_inventory,
            "integrity": training_integrity,
            "selection_receipts": selection_receipts,
            "unique_cpu_critic_fits": len(model_keys),
        },
        "future_inventory": {
            "identity_cohort_runs": len(cohort_runs),
            "identity_cohort_tasks": len({row["task"] for row in cohort_runs}),
            "blind_endpoints": len(future_cards),
            "eligible_structural_pairs": len(future_pairs),
            "blind_runs": len({row["run_id"] for row in future_cards.values()}),
            "blind_tasks": len({row["task"] for row in future_cards.values()}),
            "ties": tie_counts,
            "training_endpoint_id_overlap": 0,
            "training_code_sha256_overlap": 0,
        },
        "outputs": {
            "endpoint_scores_sha256": hashlib.sha256(payloads["endpoint_scores.csv"]).hexdigest(),
            "pair_predictions_sha256": hashlib.sha256(payloads["pair_predictions.jsonl"]).hexdigest(),
            "training_selection_receipts_sha256": hashlib.sha256(
                payloads["training_selection_receipts.jsonl"]
            ).hexdigest(),
        },
        "scope": {
            "cohort_identity_closed_before_scoring": True,
            "label_vault_path_accepted": False,
            "label_vault_read": False,
            "accuracy_computed": False,
            "outcome_metric_computed": False,
            "raw_grade_read": False,
            "y_norm_read": False,
            "score_directory_opened": False,
            "gpu_jobs": 0,
            "api_calls": 0,
            "base_llm_updates": 0,
        },
        "future_evaluation_frozen_in_contract": contract["evaluation_after_truth_open"],
    }
    observed_summary = json.loads(payloads["summary.json"].decode("utf-8"))
    maximum_difference = max(maximum_difference, close_enough(expected_summary, observed_summary, "summary"))
    if {path.name for path in args.artifact.iterdir()} != expected_files or any(
        hashlib.sha256(stable_file_bytes(args.artifact / name, f"artifact {name} recheck")).digest()
        != hashlib.sha256(payloads[name]).digest()
        for name in expected_files
    ):
        raise VerificationError("artifact changed during independent verification")
    source_commit = repository_head(repo_root)
    receipt = {
        "protocol": f"verify-{PROTOCOL}-v1",
        "status": "INDEPENDENT_SOURCE_REFIT_PASS",
        "contract_sha256": CONTRACT_SHA256,
        "artifact_manifest_sha256": hashlib.sha256(payloads["artifact_manifest.json"]).hexdigest(),
        "source_commit": source_commit,
        "producer_source_sha256": digest(expected_producer),
        "verifier_source_sha256": digest(Path(__file__)),
        "selection_reference_source_sha256": digest(Path(selection_reference.__file__)),
        "source_selection_contract_sha256": digest(expected_source_contract),
        "training_cards_sha256": digest(args.training_cards),
        "training_pairs_sha256": digest(args.train_pairs),
        "cohort_summary_sha256": valid_sha(
            args.expect_cohort_summary_sha256, "cohort summary SHA"
        ),
        "future_endpoints": len(future_cards),
        "future_pairs": len(future_pairs),
        "unique_cpu_critic_refits": len(model_keys),
        "maximum_numeric_difference": maximum_difference,
        "label_vault_read": False,
        "outcome_metrics_computed": [],
    }
    if args.output.exists() or args.output.is_symlink():
        raise VerificationError("verification output exists")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as handle:
        handle.write(canonical(receipt))
    return receipt


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-cards", required=True, type=Path)
    parser.add_argument("--train-pairs", required=True, type=Path)
    parser.add_argument("--cohort-dir", required=True, type=Path)
    parser.add_argument("--expect-cohort-summary-sha256", required=True)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--contract", type=Path,
        default=Path(__file__).with_name("critic_component_breadth_future_escrow_v1.json"),
    )
    parser.add_argument(
        "--source-selection-contract", type=Path,
        default=Path(__file__).with_name("critic_component_breadth_equal_budget_v1.json"),
    )
    parser.add_argument(
        "--producer-source", type=Path,
        default=Path(__file__).with_name("critic_component_breadth_future_escrow.py"),
    )
    return parser.parse_args()


def main() -> int:
    try:
        receipt = verify(arguments())
    except (
        VerificationError,
        selection_reference.VerificationError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        KeyError,
        ValueError,
    ) as error:
        print(f"COMPONENT_BREADTH_FUTURE_ESCROW_VERIFY_ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
