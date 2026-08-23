#!/usr/bin/env python3
"""Outcome-aware evaluation of a pre-truth component-breadth prediction escrow.

The complete prediction escrow is authenticated before any label vault is
opened.  The evaluator then independently reconstructs the frozen selected
parents, applies the pre-registered support gates, and only computes effects
when every gate passes.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import itertools
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

from phase1 import score_channel_future_truth_support as truth_reference


PROTOCOL = "critic-component-breadth-future-evaluation-v1"
PROTOCOL_SHA256 = "1596c6f2abdfdd8b8880937f41099d81db74151e491175c123e581d9b028fdad"
PREDICTION_PROTOCOL = "critic-component-breadth-future-escrow-v1"
PREDICTION_CONTRACT_SHA256 = "c52a71c36edb30a5dec965d6509387b386347acb50ac5e6a3ca789a778fd472b"
PREDICTION_STATUS = "FUTURE_COMPONENT_BREADTH_PREDICTION_ESCROW_COMPLETE"
BASE_PROTOCOL_SHA256 = "54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d"
OUTPUT_PROTOCOL = "critic-component-breadth-future-evaluation-output-v1"
STATUS_INSUFFICIENT = "FUTURE_COMPONENT_BREADTH_EVALUATION_INSUFFICIENT_RAW_SUPPORT"
STATUS_POSITIVE = "FUTURE_COMPONENT_BREADTH_EVALUATION_PRIMARY_POSITIVE"
STATUS_NONPOSITIVE = "FUTURE_COMPONENT_BREADTH_EVALUATION_PRIMARY_NOT_POSITIVE"
ARMS = ("broad", "concentrated", "random")
SEEDS = (20260823, 20260824, 20260825)
MODEL_KEYS = tuple(f"{arm}_s{seed}" for seed in SEEDS for arm in ARMS)
PAIR_BASE_KEYS = {"task", "run_id", "parent", "left", "right", "pair_key_sha256"}
PAIR_KEYS = PAIR_BASE_KEYS | {
    field
    for key in MODEL_KEYS
    for field in (f"{key}_margin_left_minus_right", f"{key}_selected")
}
TOLERANCE = 1e-12


class EvaluationError(RuntimeError):
    """A frozen input, support, or evaluation invariant failed."""


def digest(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            state.update(block)
    return state.hexdigest()


def valid_sha(value: Any, label: str, *, length: int = 64) -> str:
    if not isinstance(value, str):
        raise EvaluationError(f"invalid {label}")
    lowered = value.lower()
    if len(lowered) != length or any(character not in "0123456789abcdef" for character in lowered):
        raise EvaluationError(f"invalid {label}")
    return lowered


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def compact(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def read_object(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise EvaluationError(f"{label} is not a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EvaluationError(f"cannot read {label}") from error
    if not isinstance(value, dict):
        raise EvaluationError(f"{label} is not an object")
    return value


def read_rows(
    path: Path, label: str, expected_keys: set[str] | None = None, *, allow_empty: bool = False
) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise EvaluationError(f"{label} is not a regular file")
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for number, line in enumerate(handle, 1):
                if not line.strip():
                    raise EvaluationError(f"blank row in {label}:{number}")
                value = json.loads(line)
                if not isinstance(value, dict) or (
                    expected_keys is not None and set(value) != expected_keys
                ):
                    raise EvaluationError(f"schema mismatch in {label}:{number}")
                rows.append(value)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EvaluationError(f"cannot read {label}") from error
    if not rows and not allow_empty:
        raise EvaluationError(f"{label} is empty")
    return rows


def load_protocol(path: Path, expected_sha: str) -> dict[str, Any]:
    if valid_sha(expected_sha, "evaluation protocol SHA") != PROTOCOL_SHA256:
        raise EvaluationError("evaluation protocol expected SHA mismatch")
    if digest(path) != PROTOCOL_SHA256:
        raise EvaluationError("evaluation protocol file SHA mismatch")
    value = read_object(path, "evaluation protocol")
    entry = value.get("entry_contract") or {}
    primary = value.get("primary") or {}
    support = primary.get("support_gates") or {}
    positive = primary.get("positive_rule") or {}
    bootstrap = (value.get("inference") or {}).get("bootstrap") or {}
    inference = value.get("inference") or {}
    output = value.get("output_contract") or {}
    resources = value.get("resources") or {}
    claim = value.get("claim_boundary") or {}
    if (
        value.get("protocol") != PROTOCOL
        or value.get("status") != "PREREGISTERED_OUTCOME_EVALUATOR_BEFORE_FUTURE_TRUTH_OPEN"
        or value.get("parent_prediction_contract_sha256") != PREDICTION_CONTRACT_SHA256
        or entry.get("prediction_status") != PREDICTION_STATUS
        or entry.get("base_truth_protocol_sha256") != BASE_PROTOCOL_SHA256
        or entry.get("prediction_artifact_manifest_must_verify_before_label_vault_open") is not True
        or entry.get("selected_parent_reconstruction_before_metric") is not True
        or entry.get("outcome_dependent_reselection_allowed") is not False
        or primary.get("truth_tie_absolute_tolerance") != TOLERANCE
        or primary.get("official_five_decimal_grid_required") is not True
        or primary.get("prediction_tie_credit") != 0.5
        or primary.get("task_minimum_role")
        != "minimum analyzability and breadth floor, not a power guarantee"
        or support.get("all_must_pass_before_any_primary_effect_is_computed") is not True
        or support.get("raw_nontied_selected_parents_minimum") != 200
        or support.get("selected_physical_runs_with_raw_nontied_parent_minimum") != 150
        or support.get("tasks_with_raw_nontied_selected_parent_minimum") != 50
        or support.get("dominant_task_share_of_raw_nontied_selected_parents_maximum") != 0.2
        or positive.get("point_estimate_gte") != 0.02
        or positive.get("every_seed_effect_gt") != 0.0
        or positive.get("task_cluster_bootstrap_ci95_low_gt") != 0.0
        or positive.get("every_leave_one_task_out_effect_gt") != 0.0
        or positive.get("all_conditions_required") is not True
        or inference.get("selection_seeds") != list(SEEDS)
        or inference.get("arms") != list(ARMS)
        or inference.get("selection_seed_role")
        != "nuisance robustness choices, not independent experimental replications or effective sample-size units"
        or bootstrap.get("replicates") != 20000
        or bootstrap.get("seed") != 20260831
        or bootstrap.get("resample_index_algorithm")
        != "uint64_big_endian_first8_sha256(seed\\0replicate\\0position)_mod_n_tasks"
        or bootstrap.get("quantile_algorithm") != "Hyndman-Fan type 7 linear interpolation"
        or output.get("raw_card_level_labels_written") is not False
        or output.get("pair_level_truth_orientations_written") is not False
        or output.get("task_metrics_written_only_if_primary_support_passes") is not True
        or output.get("primary_effect_fields_written_only_if_primary_support_passes") is not True
        or output.get("insufficient_support_status") != STATUS_INSUFFICIENT
        or output.get("positive_status") != STATUS_POSITIVE
        or output.get("nonpositive_status") != STATUS_NONPOSITIVE
        or resources != {"api_calls": 0, "base_llm_updates": 0, "gpu_jobs": 0, "new_model_fits": 0}
        or "component_or_run_breadth_isolated_as_the_causal_mechanism"
        not in (claim.get("forbidden") or [])
    ):
        raise EvaluationError("evaluation protocol semantics mismatch")
    return value


def validate_prediction(
    prediction_dir: Path,
    expected_summary_sha: str,
    expected_manifest_sha: str,
    expected_cohort_sha: str,
    protocol: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Authenticate and load predictions before any outcome-bearing file is opened."""
    if prediction_dir.is_symlink() or not prediction_dir.is_dir():
        raise EvaluationError("prediction escrow is not a regular directory")
    if {path.name for path in prediction_dir.iterdir()} != {
        "artifact_manifest.json",
        "endpoint_scores.csv",
        "pair_predictions.jsonl",
        "training_selection_receipts.jsonl",
        "summary.json",
    }:
        raise EvaluationError("prediction escrow has missing or extra artifacts")
    manifest_path = prediction_dir / "artifact_manifest.json"
    summary_path = prediction_dir / "summary.json"
    if digest(manifest_path) != valid_sha(expected_manifest_sha, "prediction manifest SHA"):
        raise EvaluationError("prediction artifact manifest SHA mismatch")
    manifest = read_object(manifest_path, "prediction artifact manifest")
    artifacts = manifest.get("artifacts")
    expected_names = {
        "endpoint_scores.csv",
        "pair_predictions.jsonl",
        "training_selection_receipts.jsonl",
        "summary.json",
    }
    if (
        manifest.get("protocol") != f"{PREDICTION_PROTOCOL}-artifact-manifest-v1"
        or manifest.get("contract_sha256") != PREDICTION_CONTRACT_SHA256
        or not isinstance(artifacts, dict)
        or set(artifacts) != expected_names
    ):
        raise EvaluationError("prediction artifact manifest contract mismatch")
    for name in sorted(expected_names):
        path = prediction_dir / name
        item = artifacts[name]
        if (
            path.is_symlink()
            or not path.is_file()
            or not isinstance(item, dict)
            or set(item) != {"sha256", "bytes"}
            or digest(path) != valid_sha(item.get("sha256"), f"{name} SHA")
            or path.stat().st_size != item.get("bytes")
        ):
            raise EvaluationError(f"prediction artifact mismatch: {name}")
    if digest(summary_path) != valid_sha(expected_summary_sha, "prediction summary SHA"):
        raise EvaluationError("prediction summary SHA mismatch")
    summary = read_object(summary_path, "prediction summary")
    scope = summary.get("scope") or {}
    required_scope = (protocol["entry_contract"]["prediction_scope_must_assert"])
    outputs = summary.get("outputs") or {}
    cohort_sha = valid_sha(expected_cohort_sha, "cohort summary SHA")
    if (
        summary.get("protocol") != PREDICTION_PROTOCOL
        or summary.get("contract_sha256") != PREDICTION_CONTRACT_SHA256
        or summary.get("status") != PREDICTION_STATUS
        or any(scope.get(key) != value for key, value in required_scope.items())
        or scope.get("gpu_jobs") != 0
        or scope.get("api_calls") != 0
        or scope.get("base_llm_updates") != 0
        or (summary.get("inputs") or {}).get("cohort_summary_sha256") != cohort_sha
        or outputs.get("pair_predictions_sha256") != artifacts["pair_predictions.jsonl"]["sha256"]
        or outputs.get("endpoint_scores_sha256") != artifacts["endpoint_scores.csv"]["sha256"]
        or outputs.get("training_selection_receipts_sha256")
        != artifacts["training_selection_receipts.jsonl"]["sha256"]
    ):
        raise EvaluationError("prediction summary contract mismatch")
    rows = read_rows(prediction_dir / "pair_predictions.jsonl", "pair predictions", PAIR_KEYS)
    seen: set[tuple[str, str]] = set()
    ties = collections.Counter({key: 0 for key in MODEL_KEYS})
    for row in rows:
        left, right = row.get("left"), row.get("right")
        identity = (left, right)
        if (
            not all(isinstance(row.get(key), str) and row[key] for key in ("task", "run_id", "parent", "left", "right"))
            or not left < right
            or identity in seen
            or row.get("pair_key_sha256")
            != hashlib.sha256("\0".join(identity).encode()).hexdigest()
        ):
            raise EvaluationError("invalid or duplicate prediction pair identity")
        seen.add(identity)
        for key in MODEL_KEYS:
            margin = row.get(f"{key}_margin_left_minus_right")
            selected = row.get(f"{key}_selected")
            if isinstance(margin, bool) or not isinstance(margin, (int, float)) or not math.isfinite(float(margin)):
                raise EvaluationError("invalid prediction margin")
            expected = left if margin > 0 else right if margin < 0 else "tie"
            if selected != expected:
                raise EvaluationError("prediction orientation/margin mismatch")
            ties[key] += margin == 0
    inventory = summary.get("future_inventory") or {}
    if (
        inventory.get("eligible_structural_pairs") != len(rows)
        or inventory.get("ties") != dict(ties)
    ):
        raise EvaluationError("prediction inventory mismatch")
    return rows, summary


def load_selected_and_truth(
    base_protocol_path: Path,
    cohort_dir: Path,
    expected_cohort_sha: str,
    state_root: Path,
    selected_path: Path,
    expected_selected_sha: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    if (
        base_protocol_path.is_symlink()
        or cohort_dir.is_symlink()
        or state_root.is_symlink()
        or selected_path.is_symlink()
    ):
        raise EvaluationError("symlinked evaluation input is forbidden")
    if digest(base_protocol_path) != BASE_PROTOCOL_SHA256:
        raise EvaluationError("base truth protocol SHA mismatch")
    try:
        base_protocol = truth_reference.load_protocol(base_protocol_path, BASE_PROTOCOL_SHA256)
        runs, cohort_summary = truth_reference.load_cohort(
            cohort_dir, BASE_PROTOCOL_SHA256, valid_sha(expected_cohort_sha, "cohort summary SHA")
        )
    except truth_reference.TruthSupportError as error:
        raise EvaluationError(f"cohort/base protocol reconstruction failed: {error}") from error
    if digest(selected_path) != valid_sha(expected_selected_sha, "selected parents SHA"):
        raise EvaluationError("selected parents SHA mismatch")
    selected = read_rows(
        selected_path, "selected parents", truth_reference.ROW_KEYS
    )

    # This is deliberately the first outcome-bearing read in the evaluator.
    try:
        siblings, vault, intake_shas = truth_reference.load_truth_inputs(
            state_root, runs, cohort_summary
        )
        spec = base_protocol["parent_selection"]
        reconstructed, eligible, runs_with = truth_reference.select_parents(
            runs, siblings, vault, spec["seed"], spec["max_parents_per_physical_run"]
        )
    except truth_reference.TruthSupportError as error:
        raise EvaluationError(f"truth/selection reconstruction failed: {error}") from error
    if [compact(row) for row in selected] != [compact(row) for row in reconstructed]:
        raise EvaluationError("selected parents differ from frozen lottery reconstruction")
    return selected, vault, {
        "intake_summary_sha256": dict(sorted(intake_shas.items())),
        "eligible_parents_before_per_run_cap": eligible,
        "runs_with_eligible_parent": runs_with,
    }


def pair_map(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(row["left"], row["right"]): row for row in rows}


def support_census(
    selected: list[dict[str, Any]], vault: dict[str, dict[str, Any]], protocol: dict[str, Any]
) -> dict[str, Any]:
    per_task: collections.Counter[str] = collections.Counter()
    runs: set[str] = set()
    candidates: set[str] = set()
    raw_nontied_pairs = 0
    for parent in selected:
        cards = parent["candidate_card_ids"]
        candidates.update(cards)
        values: list[float] = []
        for card in cards:
            value = vault.get(card, {}).get("graded")
            if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
                raise EvaluationError("selected candidate lacks finite official grade")
            number = float(value)
            if not math.isfinite(number) or abs(number - round(number, 5)) > TOLERANCE:
                raise EvaluationError("official grade is off the frozen five-decimal grid")
            values.append(number)
        informative = sum(
            abs(values[left] - values[right]) > TOLERANCE
            for left, right in itertools.combinations(range(len(values)), 2)
        )
        raw_nontied_pairs += informative
        if informative:
            per_task[parent["task"]] += 1
            runs.add(parent["run_id"])
    total = sum(per_task.values())
    dominant_task = max(per_task, key=lambda task: (per_task[task], task)) if per_task else None
    dominant_count = per_task.get(dominant_task, 0) if dominant_task else 0
    dominant_share = dominant_count / total if total else None
    limits = protocol["primary"]["support_gates"]
    gates = {
        "raw_nontied_selected_parents": total >= limits["raw_nontied_selected_parents_minimum"],
        "selected_physical_runs_with_raw_nontied_parent": len(runs)
        >= limits["selected_physical_runs_with_raw_nontied_parent_minimum"],
        "tasks_with_raw_nontied_selected_parent": len(per_task)
        >= limits["tasks_with_raw_nontied_selected_parent_minimum"],
        "dominant_task_share_of_raw_nontied_selected_parents": dominant_share is not None
        and dominant_share <= limits["dominant_task_share_of_raw_nontied_selected_parents_maximum"],
    }
    return {
        "counts": {
            "selected_parents": len(selected),
            "selected_candidates": len(candidates),
            "raw_nontied_selected_parents": total,
            "raw_nontied_pairs": raw_nontied_pairs,
            "selected_physical_runs_with_raw_nontied_parent": len(runs),
            "tasks_with_raw_nontied_selected_parent": len(per_task),
        },
        "per_task_raw_nontied_selected_parents": dict(sorted(per_task.items())),
        "balance": {
            "dominant_task": dominant_task,
            "dominant_task_raw_nontied_selected_parents": dominant_count,
            "dominant_task_share": dominant_share,
        },
        "gates": {**gates, "all_pass": all(gates.values())},
    }


def pair_credit(margin: float, truth_difference: float) -> float:
    if margin == 0.0:
        return 0.5
    return 1.0 if margin * truth_difference > 0.0 else 0.0


def pair_log_loss(margin: float, truth_difference: float) -> float:
    signed = margin if truth_difference > 0.0 else -margin
    if signed >= 0:
        return math.log1p(math.exp(-signed))
    return -signed + math.log1p(math.exp(signed))


def task_metrics(
    selected: list[dict[str, Any]],
    vault: dict[str, dict[str, Any]],
    predictions: dict[tuple[str, str], dict[str, Any]],
    truth_key: str,
) -> list[dict[str, Any]]:
    parent_values: dict[tuple[str, str], list[tuple[float, float, int]]] = collections.defaultdict(list)
    for parent in selected:
        card_ids = sorted(parent["candidate_card_ids"])
        for key in MODEL_KEYS:
            credits: list[float] = []
            losses: list[float] = []
            for left, right in itertools.combinations(card_ids, 2):
                row = predictions.get((left, right))
                if (
                    row is None
                    or row["task"] != parent["task"]
                    or row["run_id"] != parent["run_id"]
                    or row["parent"] != parent["parent_id"]
                ):
                    raise EvaluationError("selected parent pair is absent or misbound in prediction escrow")
                left_value, right_value = vault[left][truth_key], vault[right][truth_key]
                if left_value is None or right_value is None:
                    continue
                difference = float(left_value) - float(right_value)
                if not math.isfinite(difference) or abs(difference) <= TOLERANCE:
                    continue
                margin = float(row[f"{key}_margin_left_minus_right"])
                credits.append(pair_credit(margin, difference))
                losses.append(pair_log_loss(margin, difference))
            if credits:
                parent_values[(parent["task"], key)].append(
                    (sum(credits) / len(credits), sum(losses) / len(losses), len(credits))
                )
    rows: list[dict[str, Any]] = []
    for (task, key), values in sorted(parent_values.items()):
        arm, seed_text = key.rsplit("_s", 1)
        rows.append(
            {
                "truth": truth_key,
                "task": task,
                "selection_seed": int(seed_text),
                "arm": arm,
                "informative_parents": len(values),
                "informative_pairs": sum(item[2] for item in values),
                "parent_macro_accuracy": sum(item[0] for item in values) / len(values),
                "parent_macro_log_loss": sum(item[1] for item in values) / len(values),
            }
        )
    return rows


def type7_quantile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values or not 0.0 <= probability <= 1.0:
        raise EvaluationError("invalid type-7 quantile input")
    if len(sorted_values) == 1:
        return sorted_values[0]
    index = (len(sorted_values) - 1) * probability
    lower = int(math.floor(index))
    fraction = index - lower
    if lower + 1 == len(sorted_values):
        return sorted_values[lower]
    return sorted_values[lower] + fraction * (sorted_values[lower + 1] - sorted_values[lower])


def bootstrap_interval(
    task_effects: dict[str, float], *, seed: int, replicates: int
) -> tuple[float, float]:
    tasks = sorted(task_effects)
    if not tasks or replicates < 1:
        raise EvaluationError("empty task bootstrap")
    values = [task_effects[task] for task in tasks]
    n_tasks = len(tasks)
    draws: list[float] = []
    for replicate in range(replicates):
        total = 0.0
        for position in range(n_tasks):
            payload = f"{seed}\0{replicate}\0{position}".encode()
            index = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % n_tasks
            total += values[index]
        draws.append(total / n_tasks)
    draws.sort()
    return type7_quantile(draws, 0.025), type7_quantile(draws, 0.975)


def summarize_metrics(
    rows: list[dict[str, Any]], protocol: dict[str, Any], *, primary: bool
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    index = {
        (row["task"], row["selection_seed"], row["arm"]): row for row in rows
    }
    tasks = sorted({row["task"] for row in rows})
    complete = [
        task
        for task in tasks
        if all((task, seed, arm) in index for seed in SEEDS for arm in ARMS)
    ]
    if complete != tasks or not tasks:
        raise EvaluationError("task metric support differs across frozen models")
    seed_effects = {
        str(seed): sum(
            index[(task, seed, "broad")]["parent_macro_accuracy"]
            - index[(task, seed, "concentrated")]["parent_macro_accuracy"]
            for task in tasks
        )
        / len(tasks)
        for seed in SEEDS
    }
    task_effects = {
        task: sum(
            index[(task, seed, "broad")]["parent_macro_accuracy"]
            - index[(task, seed, "concentrated")]["parent_macro_accuracy"]
            for seed in SEEDS
        )
        / len(SEEDS)
        for task in tasks
    }
    point = sum(task_effects.values()) / len(task_effects)
    accuracies = {
        arm: sum(
            index[(task, seed, arm)]["parent_macro_accuracy"]
            for task in tasks
            for seed in SEEDS
        )
        / (len(tasks) * len(SEEDS))
        for arm in ARMS
    }
    losses = {
        arm: sum(
            index[(task, seed, arm)]["parent_macro_log_loss"]
            for task in tasks
            for seed in SEEDS
        )
        / (len(tasks) * len(SEEDS))
        for arm in ARMS
    }
    loto: list[dict[str, Any]] = []
    for task in tasks:
        remaining = [value for name, value in task_effects.items() if name != task]
        if not remaining:
            raise EvaluationError("leave-one-task-out needs at least two tasks")
        loto.append({"truth": rows[0]["truth"], "dropped_task": task, "effect": sum(remaining) / len(remaining)})
    bootstrap = protocol["inference"]["bootstrap"]
    low, high = bootstrap_interval(
        task_effects, seed=bootstrap["seed"], replicates=bootstrap["replicates"]
    )
    summary: dict[str, Any] = {
        "truth": rows[0]["truth"],
        "tasks": len(tasks),
        "task_macro_accuracy": accuracies,
        "task_macro_log_loss": losses,
        "broad_minus_concentrated_accuracy": point,
        "broad_minus_concentrated_log_loss": losses["broad"] - losses["concentrated"],
        "broad_minus_concentrated_accuracy_by_seed": seed_effects,
        "task_cluster_bootstrap_ci95": [low, high],
        "leave_one_task_out_min": min(row["effect"] for row in loto),
        "leave_one_task_out_max": max(row["effect"] for row in loto),
    }
    if primary:
        rule = protocol["primary"]["positive_rule"]
        conditions = {
            "point_estimate": point >= rule["point_estimate_gte"],
            "every_seed": all(value > rule["every_seed_effect_gt"] for value in seed_effects.values()),
            "bootstrap_ci95_low": low > rule["task_cluster_bootstrap_ci95_low_gt"],
            "every_leave_one_task_out": all(
                row["effect"] > rule["every_leave_one_task_out_effect_gt"] for row in loto
            ),
        }
        summary["positive_conditions"] = {**conditions, "all_pass": all(conditions.values())}
    return summary, loto


def repository_head(repo: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise EvaluationError("cannot resolve evaluator source commit")
    return valid_sha(completed.stdout.strip(), "evaluator source commit", length=40)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(compact(row) + "\n")


def bind_repository_sources(args: argparse.Namespace) -> tuple[Path, Path]:
    repo_root = args.repo_root.absolute()
    expected_protocol = repo_root / "phase1" / "critic_component_breadth_future_evaluation_v1.json"
    expected_base = repo_root / "phase1" / "score_channel_future_identifiability_protocol_v1.json"
    expected_evaluator = repo_root / "phase1" / "evaluate_critic_component_breadth_future_escrow.py"
    if (
        repo_root.is_symlink()
        or not repo_root.is_dir()
        or repo_root != repo_root.resolve()
        or args.protocol.absolute() != expected_protocol
        or args.base_protocol.absolute() != expected_base
        or Path(__file__).absolute() != expected_evaluator
        or any(path.is_symlink() for path in (args.protocol, args.base_protocol, expected_evaluator))
    ):
        raise EvaluationError("evaluator source/input path binding mismatch")
    return repo_root, expected_evaluator


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    repo_root, evaluator_source = bind_repository_sources(args)
    protocol = load_protocol(args.protocol, args.expect_protocol_sha256)
    output = args.output.resolve()
    if output.exists():
        raise EvaluationError("evaluation output path already exists")

    # Authentication and full prediction parsing must finish before the vault opens.
    prediction_rows, prediction_summary = validate_prediction(
        args.prediction_dir,
        args.expect_prediction_summary_sha256,
        args.expect_prediction_manifest_sha256,
        args.expect_cohort_summary_sha256,
        protocol,
    )
    selected, vault, truth_inputs = load_selected_and_truth(
        args.base_protocol,
        args.cohort_dir,
        args.expect_cohort_summary_sha256,
        args.state_root.resolve(),
        args.selected_parents,
        args.expect_selected_parents_sha256,
    )
    predictions = pair_map(prediction_rows)
    support = support_census(selected, vault, protocol)

    task_rows: list[dict[str, Any]] = []
    loto_rows: list[dict[str, Any]] = []
    effects: dict[str, Any] | None = None
    if support["gates"]["all_pass"]:
        raw_rows = task_metrics(selected, vault, predictions, "graded")
        normalized_rows = task_metrics(selected, vault, predictions, "y_norm")
        raw_summary, raw_loto = summarize_metrics(raw_rows, protocol, primary=True)
        normalized_summary, normalized_loto = summarize_metrics(
            normalized_rows, protocol, primary=False
        )
        positive = raw_summary["positive_conditions"]["all_pass"]
        status = STATUS_POSITIVE if positive else STATUS_NONPOSITIVE
        task_rows = raw_rows + normalized_rows
        loto_rows = raw_loto + normalized_loto
        effects = {
            "primary_official_five_decimal_raw_grade": raw_summary,
            "faithful_normalized_secondary": {
                **normalized_summary,
                "confirmatory_claim_allowed": False,
                "may_rescue_primary": False,
            },
            "primary_positive": positive,
            "random_arm_role": "descriptive sanity baseline only; cannot rescue primary",
            "normalized_and_log_loss_may_rescue_primary": False,
        }
    else:
        status = STATUS_INSUFFICIENT

    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp.", dir=output.parent))
    try:
        if task_rows:
            write_jsonl(staging / "task_metrics.jsonl", task_rows)
            write_jsonl(staging / "leave_one_task_out.jsonl", loto_rows)
        summary: dict[str, Any] = {
            "protocol": OUTPUT_PROTOCOL,
            "evaluation_protocol_sha256": PROTOCOL_SHA256,
            "prediction_contract_sha256": PREDICTION_CONTRACT_SHA256,
            "status": status,
            "source_commit": repository_head(repo_root),
            "source_sha256": digest(evaluator_source),
            "inputs": {
                "prediction_summary_sha256": valid_sha(
                    args.expect_prediction_summary_sha256, "prediction summary SHA"
                ),
                "prediction_manifest_sha256": valid_sha(
                    args.expect_prediction_manifest_sha256, "prediction manifest SHA"
                ),
                "prediction_pair_sha256": prediction_summary["outputs"]["pair_predictions_sha256"],
                "cohort_summary_sha256": valid_sha(
                    args.expect_cohort_summary_sha256, "cohort summary SHA"
                ),
                "selected_parents_sha256": valid_sha(
                    args.expect_selected_parents_sha256, "selected parents SHA"
                ),
                **truth_inputs,
            },
            "support": support,
            "effects": effects,
            "scope": {
                "prediction_authenticated_before_label_vault_open": True,
                "selected_parents_independently_reconstructed": True,
                "outcome_dependent_reselection": False,
                "raw_card_level_labels_written": False,
                "pair_level_truth_orientations_written": False,
                "primary_effect_computed": support["gates"]["all_pass"],
                "task_metrics_written": bool(task_rows),
                "gpu_jobs": 0,
                "api_calls": 0,
                "new_model_fits": 0,
                "base_llm_updates": 0,
            },
        }
        summary_path = staging / "summary.json"
        summary_path.write_bytes(canonical(summary))
        artifact_names = ["summary.json"]
        if task_rows:
            artifact_names.extend(("task_metrics.jsonl", "leave_one_task_out.jsonl"))
        manifest = {
            "protocol": f"{OUTPUT_PROTOCOL}-artifact-manifest-v1",
            "evaluation_protocol_sha256": PROTOCOL_SHA256,
            "artifacts": {
                name: {
                    "sha256": digest(staging / name),
                    "bytes": (staging / name).stat().st_size,
                }
                for name in artifact_names
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
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path(__file__).with_name("critic_component_breadth_future_evaluation_v1.json"),
    )
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--prediction-dir", required=True, type=Path)
    parser.add_argument("--expect-prediction-summary-sha256", required=True)
    parser.add_argument("--expect-prediction-manifest-sha256", required=True)
    parser.add_argument("--base-protocol", required=True, type=Path)
    parser.add_argument("--cohort-dir", required=True, type=Path)
    parser.add_argument("--expect-cohort-summary-sha256", required=True)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--selected-parents", required=True, type=Path)
    parser.add_argument("--expect-selected-parents-sha256", required=True)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    try:
        summary = evaluate(arguments())
    except (
        EvaluationError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        KeyError,
        ValueError,
    ) as error:
        print(f"COMPONENT_BREADTH_FUTURE_EVALUATION_ERROR: {error}", file=sys.stderr)
        return 2
    print(compact(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
