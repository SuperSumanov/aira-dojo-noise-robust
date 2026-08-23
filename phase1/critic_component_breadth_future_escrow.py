#!/usr/bin/env python3
"""Fit the frozen component-breadth arms and escrow future outcome-blind scores."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import itertools
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression


PROTOCOL = "critic-component-breadth-future-escrow-v1"
STATUS = "FUTURE_COMPONENT_BREADTH_PREDICTION_ESCROW_COMPLETE"
CONTRACT_SHA256 = "c52a71c36edb30a5dec965d6509387b386347acb50ac5e6a3ca789a778fd472b"
ARMS = ("broad", "concentrated", "random")
SHA256_RX = re.compile(r"[0-9a-f]{64}")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
RUN_KEYS = {
    "archive_relative_path", "archive_sha256", "drop_id", "endpoints", "flow_status",
    "generation_started_at_utc", "journal_sha256", "run_id", "task",
}
ARCHIVE_KEYS = {
    "archive_relative_path", "archive_sha256", "archive_size",
    "cumulative_unique_physical_runs", "drop_id", "intake_summary_sha256", "mtime_ns",
    "physical_runs", "source_provenance_sha256",
}
BLIND_KEYS = {
    "card_id", "task", "run_id", "code", "code_sha256", "lineage",
    "generation_started_at_utc", "source_sha256",
}
LINEAGE_KEYS = {"depth", "step", "n_siblings", "op", "parent"}
PAIR_KEYS = {"task", "run_id", "parent", "left", "right"}


class EscrowError(RuntimeError):
    """Fail-closed protocol, provenance, or numerical error."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def compact(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def valid_sha(value: Any, label: str, *, length: int = 64) -> str:
    if not isinstance(value, str):
        raise EscrowError(f"invalid {label}")
    lowered = value.lower()
    valid = (
        SHA256_RX.fullmatch(lowered) is not None
        if length == 64
        else len(lowered) == length and all(character in "0123456789abcdef" for character in lowered)
    )
    if not valid:
        raise EscrowError(f"invalid {label}")
    return lowered


def read_object(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise EscrowError(f"{label} is not a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EscrowError(f"cannot read {label}") from error
    if not isinstance(value, dict):
        raise EscrowError(f"{label} is not an object")
    return value


def read_rows(
    path: Path, label: str, expected_keys: set[str] | None = None, *, allow_empty: bool = False
) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise EscrowError(f"{label} is not a regular file")
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for number, line in enumerate(handle, 1):
                if not line.strip():
                    raise EscrowError(f"blank {label} row {number}")
                value = json.loads(line)
                if not isinstance(value, dict) or (
                    expected_keys is not None and set(value) != expected_keys
                ):
                    raise EscrowError(f"{label} schema mismatch at row {number}")
                rows.append(value)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EscrowError(f"cannot read {label}") from error
    if not rows and not allow_empty:
        raise EscrowError(f"{label} is empty")
    return rows


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
    if path.is_symlink() or sha256_file(path) != CONTRACT_SHA256:
        raise EscrowError("contract identity mismatch")
    contract = read_object(path, "component-breadth future contract")
    selection = contract.get("selection") or {}
    model = contract.get("model") or {}
    cohort = contract.get("cohort") or {}
    resources = contract.get("resources") or {}
    prediction = contract.get("prediction_escrow") or {}
    evaluation = contract.get("evaluation_after_truth_open") or {}
    support = evaluation.get("support_gates") or {}
    normalized = evaluation.get("faithful_normalized_secondary") or {}
    claim = contract.get("claim_boundary") or {}
    known = claim.get("known_before_freeze") or {}
    alias = known.get("raw_vs_y_norm_alias_audit") or {}
    if (
        contract.get("protocol") != PROTOCOL
        or contract.get("status") != "PREREGISTERED_PREDICTION_ESCROW_WAITING_CLOSED_COHORT"
        or selection.get("seeds") != [20260823, 20260824, 20260825]
        or selection.get("fraction_per_task") != 0.5
        or selection.get("expected_pairs_per_arm_seed") != 2353
        or selection.get("expected_broad_components_per_seed") != 127
        or selection.get("expected_concentrated_components_per_seed") != 53
        or selection.get("expected_broad_minus_concentrated_runs_by_seed")
        != {"20260823": 205, "20260824": 206, "20260825": 205}
        or selection.get("source_contract_sha256")
        != "1dc28d105922741d0c6a8263d9b2ebd2566d1a28de3dec1eb8f490116f7e6316"
        or selection.get("expected_task_pair_budget_sha256")
        != "e2181914f41949efb6333c4848ccaf74c30485545a1389671693b55fc5e3c966"
        or set(selection.get("expected_unordered_pairs_sha256") or {})
        != {f"{arm}_s{seed}" for seed in [20260823, 20260824, 20260825] for arm in ARMS}
        or model
        != {
            "code_prefix_chars": 20000,
            "lr_C": 0.5,
            "lr_max_iter": 1500,
            "lr_random_state": 0,
            "lr_solver": "lbfgs",
            "margin_excludes_intercept": True,
            "mirrored_pair_training": True,
            "tfidf_analyzer": "char_wb",
            "tfidf_dtype": "float64",
            "tfidf_max_features": 30000,
            "tfidf_min_df": 3,
            "tfidf_ngram_range": [3, 5],
            "tfidf_sublinear_tf": True,
        }
        or cohort.get("accepted_unique_physical_run_target") != 300
        or cohort.get("closed_status") != "FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD"
        or cohort.get("cohort_protocol") != "score-channel-future-identity-cohort-v1"
        or cohort.get("raw_archive_completeness_claim_allowed") is not False
        or cohort.get("first_closure_anchor_required") is not True
        or cohort.get("first_closure_anchor_path")
        != "/research/d7/spc/yzyang4/score-channel-future-identity-cohort/FIRST_CLOSED_COHORT_ANCHOR.json"
        or cohort.get("source_identity_protocol_sha256")
        != "54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d"
        or resources.get("gpu_jobs") != 0
        or resources.get("api_calls") != 0
        or resources.get("base_llm_updates") != 0
        or resources.get("maximum_unique_cpu_critic_fits_per_implementation") != 9
        or prediction.get("label_vault_path_accepted_by_cli") is not False
        or prediction.get("accuracy_or_outcome_metric_computed") is not False
        or support.get("raw_nontied_selected_parents_minimum") != 200
        or support.get("raw_nontied_contributing_physical_runs_minimum") != 150
        or support.get("tasks_with_raw_nontied_selected_parent_minimum") != 50
        or support.get("dominant_task_selected_parent_share_maximum") != 0.2
        or normalized.get("confirmatory_claim_allowed") is not False
        or normalized.get("may_rescue_primary") is not False
        or evaluation.get("task_minimum_role")
        != "minimum analyzability and breadth floor, not a power guarantee"
        or evaluation.get("tie_credit_for_exact_zero_prediction_margin") != 0.5
        or evaluation.get("truth_tied_pair_credit") is not None
        or known.get("future_cohort_labels_or_scores_read") is not False
        or alias.get("alias_parents") != 147
        or alias.get("alias_tasks") != 16
        or alias.get("known_before_raw_endpoint_selection") is not True
        or alias.get("impossible_direction_parents") != 0
        or "component_or_run_breadth_isolated_as_the_causal_mechanism"
        not in (claim.get("forbidden") or [])
    ):
        raise EscrowError("contract semantics mismatch")
    for role in ("training_cards", "component_clean_train"):
        receipt = (contract.get("inputs") or {}).get(role) or {}
        valid_sha(receipt.get("sha256"), f"{role} SHA")
        if isinstance(receipt.get("bytes"), bool) or not isinstance(receipt.get("bytes"), int) or receipt["bytes"] <= 0:
            raise EscrowError(f"invalid {role} byte receipt")
    return contract


def verify_input(path: Path, receipt: dict[str, Any], label: str) -> None:
    if (
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_size != receipt["bytes"]
        or sha256_file(path) != receipt["sha256"]
    ):
        raise EscrowError(f"{label} input identity mismatch")


def pair_identity(row: dict[str, Any]) -> str:
    try:
        left, right = sorted((row["better"], row["worse"]))
        values = row["task"], row["parent"], left, right
    except (KeyError, TypeError, ValueError) as error:
        raise EscrowError("invalid training pair identity") from error
    if not all(isinstance(value, str) and value for value in values) or left == right:
        raise EscrowError("invalid training pair identity")
    return "|".join(values)


def read_training_pairs(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    identities: set[str] = set()
    for row in read_rows(path, "component-clean train"):
        if (
            row.get("intask_split") != "train"
            or row.get("outer_intask_split") != "train"
            or row.get("train_dev_protocol") != "pair-graph-component-train-dev-split-v1"
            or row.get("train_dev_seed") != 20260821
            or row.get("train_dev_target_numerator") != 1
            or row.get("train_dev_target_denominator") != 10
            or not isinstance(row.get("pair_component_id"), str)
            or SHA256_RX.fullmatch(row["pair_component_id"]) is None
        ):
            raise EscrowError("component-clean train receipt mismatch")
        identity = pair_identity(row)
        if identity in identities:
            raise EscrowError("duplicate training pair")
        identities.add(identity)
        rows.append(row)
    return rows


def load_training_cards(
    path: Path, needed: set[str]
) -> tuple[dict[str, str], dict[str, str], dict[str, tuple[Any, ...]], dict[str, Any]]:
    grouped = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(grouped, dict):
        raise EscrowError("training Cards root is not grouped")
    codes: dict[str, str] = {}
    runs: dict[str, str] = {}
    configs: dict[str, tuple[Any, ...]] = {}
    seen: set[str] = set()
    total = 0
    for run_id, rows in grouped.items():
        if not isinstance(run_id, str) or not run_id or not isinstance(rows, list):
            raise EscrowError("invalid training Cards group")
        for row in rows:
            total += 1
            identifier = row.get("id") if isinstance(row, dict) else None
            if not isinstance(identifier, str) or not identifier or identifier in seen:
                raise EscrowError("invalid or duplicate training card")
            seen.add(identifier)
            if identifier not in needed:
                continue
            task_object = row.get("task")
            task = task_object.get("name") if isinstance(task_object, dict) else None
            config = (
                task, row.get("client"), row.get("hardware"), row.get("time_limit"),
                row.get("execution_timeout"),
            )
            if (
                not isinstance(row.get("code"), str)
                or not all(isinstance(value, str) and value for value in config[:3])
                or not all(isinstance(value, int) and not isinstance(value, bool) for value in config[3:])
            ):
                raise EscrowError("needed training card lacks code or provenance")
            codes[identifier] = row["code"]
            runs[identifier] = run_id
            configs[identifier] = config
    if set(codes) != needed:
        raise EscrowError("training pair endpoint missing from Cards")
    return codes, runs, configs, {
        "cards": total, "run_groups": len(grouped), "needed_cards": len(needed)
    }


def validate_training_pairs(
    rows: list[dict[str, Any]], runs: dict[str, str], configs: dict[str, tuple[Any, ...]]
) -> dict[str, Any]:
    component_tasks: dict[str, str] = {}
    for row in rows:
        component = row["pair_component_id"]
        if component in component_tasks and component_tasks[component] != row["task"]:
            raise EscrowError("training component crosses tasks")
        component_tasks[component] = row["task"]
        if configs[row["better"]] != configs[row["worse"]] or configs[row["better"]][0] != row["task"]:
            raise EscrowError("training pair violates exact configuration")
    return {
        "pairs": len(rows),
        "tasks": len({row["task"] for row in rows}),
        "components": len(component_tasks),
        "runs": len({runs[endpoint] for row in rows for endpoint in (row["better"], row["worse"])}),
    }


def selection_rank(seed: int, arm: str, value: str) -> str:
    return hashlib.sha256(f"{seed}|{arm}|{value}".encode()).hexdigest()


def choose_broad(groups: dict[str, list[dict[str, Any]]], target: int, seed: int) -> list[dict[str, Any]]:
    components = sorted(groups, key=lambda item: selection_rank(seed, "broad-component", item))
    chosen = [
        min(groups[component], key=lambda row: selection_rank(seed, "broad-floor", pair_identity(row)))
        for component in components[: min(target, len(components))]
    ]
    selected = {pair_identity(row) for row in chosen}
    remaining = [
        row for component in sorted(groups) for row in groups[component]
        if pair_identity(row) not in selected
    ]
    remaining.sort(key=lambda row: selection_rank(seed, "broad-fill", pair_identity(row)))
    return chosen + remaining[: target - len(chosen)]


def choose_concentrated(groups: dict[str, list[dict[str, Any]]], target: int, seed: int) -> list[dict[str, Any]]:
    components = sorted(
        groups, key=lambda item: (-len(groups[item]), selection_rank(seed, "concentrated-component", item))
    )
    chosen: list[dict[str, Any]] = []
    for component in components:
        needed = target - len(chosen)
        if needed <= 0:
            break
        candidates = sorted(
            groups[component], key=lambda row: selection_rank(seed, "concentrated-pair", pair_identity(row))
        )
        chosen.extend(candidates[:needed])
    return chosen


def choose_random(groups: dict[str, list[dict[str, Any]]], target: int, seed: int) -> list[dict[str, Any]]:
    rows = [row for component in sorted(groups) for row in groups[component]]
    rows.sort(key=lambda row: selection_rank(seed, "random-pair", pair_identity(row)))
    return rows[:target]


def build_selections(
    rows: list[dict[str, Any]], runs: dict[str, str], contract: dict[str, Any]
) -> tuple[dict[tuple[int, str], list[dict[str, Any]]], list[dict[str, Any]]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    for row in rows:
        grouped[row["task"]][row["pair_component_id"]].append(row)
    selections: dict[tuple[int, str], list[dict[str, Any]]] = {}
    task_budgets: dict[tuple[int, str], dict[str, int]] = {}
    for seed in contract["selection"]["seeds"]:
        for task in sorted(grouped):
            groups = grouped[task]
            target = math.ceil(contract["selection"]["fraction_per_task"] * sum(map(len, groups.values())))
            chosen = {
                "broad": choose_broad(groups, target, seed),
                "concentrated": choose_concentrated(groups, target, seed),
                "random": choose_random(groups, target, seed),
            }
            if any(len(values) != target or len({pair_identity(row) for row in values}) != target for values in chosen.values()):
                raise EscrowError("selection pair-budget or uniqueness mismatch")
            for arm, values in chosen.items():
                selections.setdefault((seed, arm), []).extend(values)
                task_budgets.setdefault((seed, arm), {})[task] = target

    receipts: list[dict[str, Any]] = []
    expected_runs = contract["selection"]["expected_broad_minus_concentrated_runs_by_seed"]
    for seed in contract["selection"]["seeds"]:
        seed_receipts: dict[str, dict[str, Any]] = {}
        for arm in ARMS:
            selected = selections[(seed, arm)]
            identities = sorted(pair_identity(row) for row in selected)
            receipt = {
                "selection_seed": seed,
                "arm": arm,
                "pairs": len(selected),
                "tasks": len(task_budgets[(seed, arm)]),
                "task_pair_budget_sha256": hashlib.sha256(
                    ("\n".join(f"{task}|{task_budgets[(seed, arm)][task]}" for task in sorted(task_budgets[(seed, arm)])) + "\n").encode()
                ).hexdigest(),
                "components": len({row["pair_component_id"] for row in selected}),
                "endpoints": len({endpoint for row in selected for endpoint in (row["better"], row["worse"])}),
                "runs": len({runs[endpoint] for row in selected for endpoint in (row["better"], row["worse"])}),
                "unordered_pairs_sha256": hashlib.sha256(("\n".join(identities) + "\n").encode()).hexdigest(),
            }
            receipts.append(receipt)
            seed_receipts[arm] = receipt
        if (
            {item["pairs"] for item in seed_receipts.values()}
            != {contract["selection"]["expected_pairs_per_arm_seed"]}
            or len({item["task_pair_budget_sha256"] for item in seed_receipts.values()}) != 1
            or seed_receipts["broad"]["components"]
            != contract["selection"]["expected_broad_components_per_seed"]
            or seed_receipts["concentrated"]["components"]
            != contract["selection"]["expected_concentrated_components_per_seed"]
            or seed_receipts["broad"]["runs"] - seed_receipts["concentrated"]["runs"]
            != expected_runs[str(seed)]
            or any(
                item["task_pair_budget_sha256"]
                != contract["selection"]["expected_task_pair_budget_sha256"]
                or item["unordered_pairs_sha256"]
                != contract["selection"]["expected_unordered_pairs_sha256"][f"{arm}_s{seed}"]
                for arm, item in seed_receipts.items()
            )
        ):
            raise EscrowError("frozen training selection receipt mismatch")
    return selections, receipts


def load_cohort(
    cohort_dir: Path, expected_summary_sha: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if cohort_dir.is_symlink() or not cohort_dir.is_dir():
        raise EscrowError("unsafe cohort directory")
    summary_path = cohort_dir / "summary.json"
    if sha256_file(summary_path) != valid_sha(expected_summary_sha, "cohort summary SHA"):
        raise EscrowError("cohort summary SHA mismatch")
    summary = read_object(summary_path, "closed cohort summary")
    inputs, outputs = summary.get("inputs") or {}, summary.get("outputs") or {}
    closure, inventory = summary.get("closure") or {}, summary.get("inventory") or {}
    blindness = summary.get("blindness") or {}
    if (
        summary.get("protocol") != "score-channel-future-identity-cohort-v1"
        or summary.get("status") != "FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD"
        or inputs.get("protocol_sha256")
        != "54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d"
        or closure.get("accepted_unique_physical_run_target") != 300
        or closure.get("complete_boundary_archive_included") is not True
        or closure.get("remaining_runs_to_target") != 0
        or not isinstance(closure.get("boundary_archive"), str)
        or blindness.get("label_vault_opened") is not False
        or blindness.get("score_or_outcome_opened") is not False
        or blindness.get("truth_support_computed") is not False
        or blindness.get("replay_submission_authorized") is not False
    ):
        raise EscrowError("cohort is not closed and truth-unread")
    runs_path, archives_path = cohort_dir / "cohort_runs.jsonl", cohort_dir / "cohort_archives.jsonl"
    if (
        sha256_file(runs_path) != valid_sha(outputs.get("cohort_runs_sha256"), "cohort runs SHA")
        or sha256_file(archives_path) != valid_sha(outputs.get("cohort_archives_sha256"), "cohort archives SHA")
    ):
        raise EscrowError("cohort output SHA mismatch")
    runs = read_rows(runs_path, "cohort runs", RUN_KEYS)
    archives = read_rows(archives_path, "cohort archives", ARCHIVE_KEYS)
    if len(runs) < 300 or inventory.get("selected_physical_runs") != len(runs) or inventory.get("selected_archives") != len(archives):
        raise EscrowError("closed cohort inventory mismatch")
    archive_by_drop: dict[str, dict[str, Any]] = {}
    cumulative = 0
    ordering: list[tuple[int, bytes]] = []
    for row in archives:
        drop, relative, count, mtime = row.get("drop_id"), row.get("archive_relative_path"), row.get("physical_runs"), row.get("mtime_ns")
        if (
            not isinstance(drop, str) or not drop or Path(drop).name != drop or drop in archive_by_drop
            or not isinstance(relative, str) or relative.count("/") != 1 or not relative.endswith(".tar.gz")
            or Path(relative).is_absolute() or ".." in Path(relative).parts
            or isinstance(count, bool) or not isinstance(count, int) or count < 0
            or isinstance(mtime, bool) or not isinstance(mtime, int) or mtime < 0
        ):
            raise EscrowError("invalid cohort archive row")
        cumulative += count
        if row.get("cumulative_unique_physical_runs") != cumulative:
            raise EscrowError("cohort cumulative run mismatch")
        for key in ("archive_sha256", "intake_summary_sha256", "source_provenance_sha256"):
            valid_sha(row.get(key), f"cohort {key}")
        archive_by_drop[drop] = row
        ordering.append((mtime, relative.encode("utf-8")))
    if ordering != sorted(ordering) or cumulative != len(runs) or archives[-1]["archive_relative_path"] != closure["boundary_archive"]:
        raise EscrowError("cohort archive order/boundary mismatch")
    seen: set[str] = set()
    counts: collections.Counter[str] = collections.Counter()
    tasks: collections.Counter[str] = collections.Counter()
    for row in runs:
        journal = valid_sha(row.get("journal_sha256"), "cohort journal SHA")
        drop, run, task = row.get("drop_id"), row.get("run_id"), row.get("task")
        archive = archive_by_drop.get(str(drop))
        endpoints = row.get("endpoints")
        flow = row.get("flow_status")
        if (
            run != f"journal:{journal}" or run in seen or not isinstance(task, str) or not task
            or archive is None or row.get("archive_relative_path") != archive["archive_relative_path"]
            or row.get("archive_sha256") != archive["archive_sha256"]
            or not isinstance(row.get("generation_started_at_utc"), str)
            or not row["generation_started_at_utc"]
            or isinstance(endpoints, bool)
            or not isinstance(endpoints, int)
            or endpoints < 0
            or flow not in {"scoreable", "no_scoreable_code"}
            or (flow == "scoreable") != (endpoints > 0)
        ):
            raise EscrowError("invalid cohort run identity")
        seen.add(run)
        counts[str(drop)] += 1
        tasks[task] += 1
    if any(counts[drop] != row["physical_runs"] for drop, row in archive_by_drop.items()):
        raise EscrowError("cohort archive/run membership mismatch")
    if (
        inventory.get("per_task_selected_runs") != dict(sorted(tasks.items()))
        or inventory.get("selected_tasks") != len(tasks)
    ):
        raise EscrowError("cohort task inventory mismatch")
    intake_hashes = inputs.get("intake_summary_sha256")
    if (
        not isinstance(intake_hashes, dict) or set(intake_hashes) != set(archive_by_drop)
        or any(intake_hashes[drop] != row["intake_summary_sha256"] for drop, row in archive_by_drop.items())
    ):
        raise EscrowError("cohort intake hash registry mismatch")
    return runs, archives, summary


def verify_intake(
    state_root: Path, archive: dict[str, Any]
) -> tuple[Path, dict[str, Any]]:
    drop = archive["drop_id"]
    intake = state_root / "intakes" / drop
    if intake.is_symlink() or not intake.is_dir() or intake.resolve().parent != (state_root / "intakes").resolve():
        raise EscrowError("unsafe intake directory")
    summary_path = intake / "summary.json"
    if sha256_file(summary_path) != archive["intake_summary_sha256"]:
        raise EscrowError("intake summary SHA mismatch")
    summary = read_object(summary_path, "intake summary")
    security, blindness = summary.get("security") or {}, summary.get("blindness") or {}
    if (
        summary.get("protocol") != "prospective_drop_intake_v1"
        or summary.get("status") != "PROSPECTIVE_DROP_INTAKE_COMPLETE"
        or (summary.get("configuration") or {}).get("archive_selection") != "explicit_names"
        or (summary.get("configuration") or {}).get("selected_archive_names")
        != [Path(archive["archive_relative_path"]).name]
        or blindness.get("labels_used_for_run_selection") is not False
        or blindness.get("labels_used_for_endpoint_selection") is not False
        or blindness.get("label_values_printed") is not False
        or blindness.get("metrics_computed") != []
    ):
        raise EscrowError("intake blindness/binding mismatch")
    expected_security = {
        "credential_shaped_journals": 0, "env_members_extracted": False,
        "env_members_read": False, "journal_scanned_before_json": True,
        "live_event_journal_members_read": False, "precutoff_code_sha256_overlap": 0,
        "precutoff_endpoint_id_overlap": 0, "raw_journals_written": False,
    }
    if any(security.get(key) != value for key, value in expected_security.items()):
        raise EscrowError("intake security contract mismatch")
    return intake, summary


def load_future_blind(
    state_root: Path, runs: list[dict[str, Any]], archives: list[dict[str, Any]]
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    allowed = {row["run_id"]: row for row in runs}
    cards: dict[str, dict[str, Any]] = {}
    pairs: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    blind_hashes: dict[str, str] = {}
    pair_hashes: dict[str, str] = {}
    intake_hashes: dict[str, str] = {}
    for archive in archives:
        drop = archive["drop_id"]
        intake, summary = verify_intake(state_root, archive)
        outputs = summary.get("outputs") or {}
        blind_path = intake / "eligible_blind_manifest.jsonl"
        pair_path = intake / "eligible_structural_pairs.jsonl"
        blind_sha = valid_sha(outputs.get("eligible_blind_manifest_sha256"), "blind manifest SHA")
        pair_sha = valid_sha(outputs.get("eligible_structural_pairs_sha256"), "structural pair SHA")
        if sha256_file(blind_path) != blind_sha or sha256_file(pair_path) != pair_sha:
            raise EscrowError("intake blind-input SHA mismatch")
        if not credential_free(blind_path) or not credential_free(pair_path):
            raise EscrowError("credential-shaped bytes in blind input")
        blind_hashes[drop], pair_hashes[drop] = blind_sha, pair_sha
        intake_hashes[drop] = archive["intake_summary_sha256"]
        blind_rows = read_rows(blind_path, f"{drop} blind manifest", BLIND_KEYS, allow_empty=True)
        pair_rows = read_rows(pair_path, f"{drop} structural pairs", PAIR_KEYS, allow_empty=True)
        intake_inventory = summary.get("inventory") or {}
        if (
            intake_inventory.get("eligible_endpoints") != len(blind_rows)
            or intake_inventory.get("eligible_structural_pairs") != len(pair_rows)
        ):
            raise EscrowError("intake eligible support inventory mismatch")
        for row in blind_rows:
            lineage = row.get("lineage")
            if not isinstance(lineage, dict) or set(lineage) != LINEAGE_KEYS:
                raise EscrowError("blind lineage schema mismatch")
            identifier, run, task, code = row["card_id"], row["run_id"], row["task"], row["code"]
            cohort_run = allowed.get(run)
            if (
                not all(isinstance(value, str) and value for value in (identifier, run, task, code))
                or identifier in cards or cohort_run is None or cohort_run["drop_id"] != drop
                or cohort_run["task"] != task or cohort_run["journal_sha256"] != row["source_sha256"]
                or cohort_run["generation_started_at_utc"] != row["generation_started_at_utc"]
                or hashlib.sha256(code.encode()).hexdigest() != row["code_sha256"]
                or run != f"journal:{row['source_sha256']}"
            ):
                raise EscrowError("invalid or duplicate blind endpoint")
            valid_sha(row["code_sha256"], "blind code SHA")
            valid_sha(row["source_sha256"], "blind source SHA")
            for key in ("depth", "step", "n_siblings"):
                value = lineage[key]
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise EscrowError("blind lineage integer invalid")
            if not isinstance(lineage["parent"], str) or not isinstance(lineage["op"], str):
                raise EscrowError("blind lineage string invalid")
            cards[identifier] = {
                "task": task, "run_id": run, "parent": lineage["parent"], "code": code,
                "code_sha256": row["code_sha256"],
                "generation_started_at_utc": row["generation_started_at_utc"],
                "source_sha256": row["source_sha256"],
                "n_siblings": lineage["n_siblings"],
            }
        for row in pair_rows:
            left, right, run, task, parent = row["left"], row["right"], row["run_id"], row["task"], row["parent"]
            key = tuple(sorted((left, right)))
            if (
                not all(isinstance(value, str) and value for value in (left, right, run, task, parent))
                or not left < right or key in seen_pairs or allowed.get(run, {}).get("drop_id") != drop
                or left not in cards or right not in cards
                or any(cards[item]["task"] != task or cards[item]["run_id"] != run or cards[item]["parent"] != parent for item in (left, right))
            ):
                raise EscrowError("invalid or duplicate structural pair")
            seen_pairs.add(key)
            pairs.append(row)
    if not cards or not pairs:
        raise EscrowError("closed cohort has empty eligible blind support")
    endpoint_counts = collections.Counter(row["run_id"] for row in cards.values())
    for run, expected in allowed.items():
        count = endpoint_counts.get(run, 0)
        if expected["endpoints"] != count or (expected["flow_status"] == "scoreable") != (count > 0):
            raise EscrowError("blind endpoint/run accounting mismatch")
    groups: dict[tuple[str, str, str], set[str]] = collections.defaultdict(set)
    sibling_claims: dict[tuple[str, str, str], set[int]] = collections.defaultdict(set)
    for identifier, card in cards.items():
        if card["parent"]:
            group = card["task"], card["run_id"], card["parent"]
            groups[group].add(identifier)
            sibling_claims[group].add(card["n_siblings"])
    expected_edges = {
        (task, run, parent, left, right)
        for (task, run, parent), children in groups.items()
        for left, right in itertools.combinations(sorted(children), 2)
    }
    observed_edges: set[tuple[str, str, str, str, str]] = set()
    for row in pairs:
        observed_edges.add((row["task"], row["run_id"], row["parent"], row["left"], row["right"]))
    if observed_edges != expected_edges:
        raise EscrowError("structural sibling pair population is incomplete or contains extras")
    if any(
        len(claims) != 1 or next(iter(claims)) < len(groups[group]) - 1
        for group, claims in sibling_claims.items()
    ):
        raise EscrowError("blind sibling-count claims are inconsistent with manifest groups")
    pairs.sort(key=lambda row: (row["task"], row["run_id"], row["parent"], row["left"], row["right"]))
    return cards, pairs, {
        "intake_summary_sha256": dict(sorted(intake_hashes.items())),
        "eligible_blind_manifest_sha256": dict(sorted(blind_hashes.items())),
        "eligible_structural_pairs_sha256": dict(sorted(pair_hashes.items())),
    }


def fit_and_score(
    selected: list[dict[str, Any]], training_codes: dict[str, str], training_runs: dict[str, str],
    future_cards: dict[str, dict[str, Any]], contract: dict[str, Any]
) -> tuple[dict[str, float], dict[str, Any]]:
    train_ids = sorted({endpoint for row in selected for endpoint in (row["better"], row["worse"])})
    future_ids = sorted(future_cards)
    vectorizer = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(3, 5), max_features=30000, min_df=3,
        sublinear_tf=True, dtype=np.float64,
    )
    train_matrix = vectorizer.fit_transform([training_codes[item][:20000] for item in train_ids]).tocsr()
    positions = {identifier: index for index, identifier in enumerate(train_ids)}
    better = np.fromiter((positions[row["better"]] for row in selected), dtype=np.int64)
    worse = np.fromiter((positions[row["worse"]] for row in selected), dtype=np.int64)
    difference = train_matrix[better] - train_matrix[worse]
    design = sparse.vstack((difference, -difference), format="csr")
    labels = np.concatenate((np.ones(len(selected), dtype=np.int8), np.zeros(len(selected), dtype=np.int8)))
    model = LogisticRegression(C=0.5, max_iter=1500, solver="lbfgs", random_state=0).fit(design, labels)
    weights = np.asarray(model.coef_, dtype=np.float64).reshape(-1)
    if int(model.n_iter_[0]) >= 1500 or not np.isfinite(weights).all() or not np.isfinite(model.intercept_).all():
        raise EscrowError("critic fit convergence/finite gate failed")
    reverse = np.asarray((-difference).dot(weights), dtype=np.float64).reshape(-1)
    forward = np.asarray(difference.dot(weights), dtype=np.float64).reshape(-1)
    anti = float(np.max(np.abs(forward + reverse)))
    if anti != 0.0:
        raise EscrowError("critic margin is not exactly antisymmetric")
    future_matrix = vectorizer.transform([future_cards[item]["code"][:20000] for item in future_ids])
    values = np.asarray(future_matrix.dot(weights), dtype=np.float64).reshape(-1)
    if values.shape != (len(future_ids),) or not np.isfinite(values).all():
        raise EscrowError("invalid future critic scores")
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


def reverify_future_inputs(
    state_root: Path,
    cohort_dir: Path,
    expected_cohort_summary_sha: str,
    cohort_summary: dict[str, Any],
    future_inputs: dict[str, Any],
) -> None:
    if sha256_file(cohort_dir / "summary.json") != expected_cohort_summary_sha:
        raise EscrowError("cohort summary changed during fit")
    outputs = cohort_summary.get("outputs") or {}
    if (
        sha256_file(cohort_dir / "cohort_runs.jsonl") != outputs.get("cohort_runs_sha256")
        or sha256_file(cohort_dir / "cohort_archives.jsonl")
        != outputs.get("cohort_archives_sha256")
    ):
        raise EscrowError("cohort identity files changed during fit")
    for field, filename in (
        ("intake_summary_sha256", "summary.json"),
        ("eligible_blind_manifest_sha256", "eligible_blind_manifest.jsonl"),
        ("eligible_structural_pairs_sha256", "eligible_structural_pairs.jsonl"),
    ):
        receipts = future_inputs.get(field)
        if not isinstance(receipts, dict):
            raise EscrowError("future input receipt missing during recheck")
        for drop, expected in receipts.items():
            path = state_root / "intakes" / drop / filename
            if path.is_symlink() or sha256_file(path) != expected:
                raise EscrowError("future blind input changed during fit")


def repository_head(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise EscrowError("cannot resolve source commit")
    return valid_sha(result.stdout.strip(), "source commit", length=40)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(compact(row) + "\n")


def produce(args: argparse.Namespace) -> dict[str, Any]:
    expected_contract = args.repo_root.absolute() / "phase1" / "critic_component_breadth_future_escrow_v1.json"
    if (
        args.repo_root.is_symlink()
        or args.contract.absolute() != expected_contract
        or args.contract.is_symlink()
    ):
        raise EscrowError("producer source/contract path binding mismatch")
    contract = load_contract(args.contract)
    output = args.output.absolute()
    if (
        args.output.is_symlink()
        or args.state_root.is_symlink()
        or args.cohort_dir.is_symlink()
        or output.exists()
    ):
        raise EscrowError("output path exists")
    cohort_runs, cohort_archives, cohort_summary = load_cohort(
        args.cohort_dir, args.expect_cohort_summary_sha256
    )
    future_cards, future_pairs, future_inputs = load_future_blind(
        args.state_root.resolve(), cohort_runs, cohort_archives
    )
    verify_input(args.training_cards, contract["inputs"]["training_cards"], "training Cards")
    verify_input(args.train_pairs, contract["inputs"]["component_clean_train"], "component-clean train")
    train = read_training_pairs(args.train_pairs)
    needed = {endpoint for row in train for endpoint in (row["better"], row["worse"])}
    training_codes, training_runs, training_configs, card_inventory = load_training_cards(args.training_cards, needed)
    training_integrity = validate_training_pairs(train, training_runs, training_configs)
    selections, selection_receipts = build_selections(train, training_runs, contract)
    training_code_shas = {hashlib.sha256(code.encode()).hexdigest() for code in training_codes.values()}
    if set(future_cards) & set(training_codes) or {row["code_sha256"] for row in future_cards.values()} & training_code_shas:
        raise EscrowError("future endpoint ID/code overlaps training support")

    scores: dict[str, dict[str, float]] = {identifier: {} for identifier in future_cards}
    fit_receipts: dict[tuple[int, str], dict[str, Any]] = {}
    model_keys: list[str] = []
    for seed in contract["selection"]["seeds"]:
        for arm in ARMS:
            key = f"{arm}_s{seed}"
            model_keys.append(key)
            arm_scores, receipt = fit_and_score(
                selections[(seed, arm)], training_codes, training_runs, future_cards, contract
            )
            for identifier, value in arm_scores.items():
                scores[identifier][key] = value
            fit_receipts[(seed, arm)] = receipt

    verify_input(args.training_cards, contract["inputs"]["training_cards"], "training Cards recheck")
    verify_input(args.train_pairs, contract["inputs"]["component_clean_train"], "component-clean train recheck")
    reverify_future_inputs(
        args.state_root.resolve(),
        args.cohort_dir,
        args.expect_cohort_summary_sha256,
        cohort_summary,
        future_inputs,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp.", dir=output.parent))
    try:
        endpoint_path = staging / "endpoint_scores.csv"
        endpoint_fields = [
            "card_id", "task", "run_id", "parent", "code_sha256", "generation_started_at_utc",
            *model_keys,
        ]
        with endpoint_path.open("x", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=endpoint_fields, lineterminator="\n")
            writer.writeheader()
            for identifier in sorted(future_cards):
                card = future_cards[identifier]
                writer.writerow({
                    "card_id": identifier, "task": card["task"], "run_id": card["run_id"],
                    "parent": card["parent"], "code_sha256": card["code_sha256"],
                    "generation_started_at_utc": card["generation_started_at_utc"],
                    **{key: format(scores[identifier][key], ".17g") for key in model_keys},
                })
        pair_path = staging / "pair_predictions.jsonl"
        tie_counts = {key: 0 for key in model_keys}
        pair_rows: list[dict[str, Any]] = []
        for pair in future_pairs:
            row: dict[str, Any] = {
                **pair,
                "pair_key_sha256": hashlib.sha256(
                    "\0".join((pair["left"], pair["right"])).encode()
                ).hexdigest(),
            }
            for key in model_keys:
                margin = scores[pair["left"]][key] - scores[pair["right"]][key]
                selected = pair["left"] if margin > 0 else pair["right"] if margin < 0 else "tie"
                tie_counts[key] += margin == 0
                row[f"{key}_margin_left_minus_right"] = float(format(margin, ".17g"))
                row[f"{key}_selected"] = selected
            pair_rows.append(row)
        write_jsonl(pair_path, pair_rows)
        receipt_path = staging / "training_selection_receipts.jsonl"
        write_jsonl(receipt_path, [
            {**row, **fit_receipts[(row["selection_seed"], row["arm"])]}
            for row in selection_receipts
        ])
        summary = {
            "protocol": PROTOCOL,
            "contract_sha256": CONTRACT_SHA256,
            "status": STATUS,
            "source_commit": repository_head(args.repo_root),
            "source_sha256": sha256_file(Path(__file__)),
            "inputs": {
                "training_cards": contract["inputs"]["training_cards"],
                "component_clean_train": contract["inputs"]["component_clean_train"],
                "cohort_summary_sha256": args.expect_cohort_summary_sha256,
                "cohort_runs_sha256": sha256_file(args.cohort_dir / "cohort_runs.jsonl"),
                "cohort_archives_sha256": sha256_file(args.cohort_dir / "cohort_archives.jsonl"),
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
                "endpoint_scores_sha256": sha256_file(endpoint_path),
                "pair_predictions_sha256": sha256_file(pair_path),
                "training_selection_receipts_sha256": sha256_file(receipt_path),
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
        (staging / "summary.json").write_bytes(canonical(summary))
        names = (
            "endpoint_scores.csv", "pair_predictions.jsonl", "training_selection_receipts.jsonl", "summary.json"
        )
        manifest = {
            "protocol": f"{PROTOCOL}-artifact-manifest-v1",
            "contract_sha256": CONTRACT_SHA256,
            "artifacts": {
                name: {"sha256": sha256_file(staging / name), "bytes": (staging / name).stat().st_size}
                for name in names
            },
        }
        (staging / "artifact_manifest.json").write_bytes(canonical(manifest))
        os.replace(staging, output)
    except Exception:
        for child in staging.iterdir():
            child.unlink()
        staging.rmdir()
        raise
    return summary


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-cards", required=True, type=Path)
    parser.add_argument("--train-pairs", required=True, type=Path)
    parser.add_argument("--cohort-dir", required=True, type=Path)
    parser.add_argument("--expect-cohort-summary-sha256", required=True)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--contract", type=Path,
        default=Path(__file__).with_name("critic_component_breadth_future_escrow_v1.json"),
    )
    return parser.parse_args()


def main() -> int:
    try:
        summary = produce(arguments())
    except (EscrowError, OSError, UnicodeError, json.JSONDecodeError, KeyError, ValueError) as error:
        print(f"COMPONENT_BREADTH_FUTURE_ESCROW_ERROR: {error}", file=sys.stderr)
        return 2
    print(compact(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
