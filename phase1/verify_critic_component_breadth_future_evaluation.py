#!/usr/bin/env python3
"""Independent verifier for the outcome-aware component-breadth evaluation.

The verifier deliberately does not import the outcome evaluator.  It authenticates
the complete pre-truth prediction escrow before opening any outcome-bearing intake,
reconstructs the frozen parent lottery and vault join, recomputes every support and
statistical field, and then checks the evaluation artifact field by field.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import itertools
import json
import math
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable


EVALUATION_PROTOCOL = "critic-component-breadth-future-evaluation-v1"
EVALUATION_PROTOCOL_SHA256 = "1596c6f2abdfdd8b8880937f41099d81db74151e491175c123e581d9b028fdad"

# Parent prediction binding: when the parent prediction contract is intentionally
# revised, synchronize this single object and EVALUATION_PROTOCOL_SHA256 after the
# evaluation protocol has been re-hashed.  No other parent SHA literal is allowed.
PARENT_PREDICTION_BINDING = {
    "protocol": "critic-component-breadth-future-escrow-v1",
    "contract_sha256": "c52a71c36edb30a5dec965d6509387b386347acb50ac5e6a3ca789a778fd472b",
    "status": "FUTURE_COMPONENT_BREADTH_PREDICTION_ESCROW_COMPLETE",
}

BASE_PROTOCOL = "score-channel-future-identifiability-cohort-v1"
BASE_PROTOCOL_SHA256 = "54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d"
COHORT_PROTOCOL = "score-channel-future-identity-cohort-v1"
SELECTED_ROW_SCHEMA = "score-channel-future-selected-parent-v1"
OUTPUT_PROTOCOL = "critic-component-breadth-future-evaluation-output-v1"
VERIFICATION_PROTOCOL = "critic-component-breadth-future-evaluation-independent-verification-v1"
STATUS_INSUFFICIENT = "FUTURE_COMPONENT_BREADTH_EVALUATION_INSUFFICIENT_RAW_SUPPORT"
STATUS_POSITIVE = "FUTURE_COMPONENT_BREADTH_EVALUATION_PRIMARY_POSITIVE"
STATUS_NONPOSITIVE = "FUTURE_COMPONENT_BREADTH_EVALUATION_PRIMARY_NOT_POSITIVE"
ARMS = ("broad", "concentrated", "random")
SEEDS = (20260823, 20260824, 20260825)
MODEL_KEYS = tuple(f"{arm}_s{seed}" for seed in SEEDS for arm in ARMS)
TOLERANCE = 1e-12

PAIR_BASE_KEYS = {"task", "run_id", "parent", "left", "right", "pair_key_sha256"}
PAIR_KEYS = PAIR_BASE_KEYS | {
    field
    for key in MODEL_KEYS
    for field in (f"{key}_margin_left_minus_right", f"{key}_selected")
}
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
STRUCTURAL_PAIR_KEYS = {"task", "run_id", "parent", "left", "right"}
VAULT_KEYS = {
    "card_id",
    "task",
    "run_id",
    "graded",
    "y_norm",
    "eligible_by_start_time",
}
SELECTED_KEYS = {
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
TASK_METRIC_KEYS = {
    "truth",
    "task",
    "selection_seed",
    "arm",
    "informative_parents",
    "informative_pairs",
    "parent_macro_accuracy",
    "parent_macro_log_loss",
}
LOTO_KEYS = {"truth", "dropped_task", "effect"}


class VerificationError(RuntimeError):
    """A frozen identity, outcome, statistic, or output field failed verification."""


def stable_file_bytes(path: Path, label: str) -> bytes:
    """Read one regular file without following a final symlink and reject mutation."""
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
    payload = b"".join(chunks)
    before_identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    after_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if before_identity != after_identity or len(payload) != before.st_size:
        raise VerificationError(f"{label} changed while being read")
    return payload


def digest(path: Path) -> str:
    return hashlib.sha256(stable_file_bytes(path, str(path))).hexdigest()


def checked_payload(path: Path, label: str, expected_sha: Any) -> bytes:
    payload = stable_file_bytes(path, label)
    if hashlib.sha256(payload).hexdigest() != valid_sha(expected_sha, f"{label} SHA"):
        raise VerificationError(f"{label} SHA mismatch")
    return payload


def valid_sha(value: Any, label: str, *, length: int = 64) -> str:
    if not isinstance(value, str):
        raise VerificationError(f"invalid {label}")
    lowered = value.lower()
    if len(lowered) != length or any(character not in "0123456789abcdef" for character in lowered):
        raise VerificationError(f"invalid {label}")
    return lowered


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def compact(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def object_from_bytes(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot read {label}") from error
    if not isinstance(value, dict):
        raise VerificationError(f"{label} is not an object")
    return value


def read_object(path: Path, label: str) -> dict[str, Any]:
    return object_from_bytes(stable_file_bytes(path, label), label)


def rows_from_bytes(
    payload: bytes,
    label: str,
    expected_keys: set[str] | None = None,
    *,
    allow_empty: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for number, line in enumerate(payload.decode("utf-8").splitlines(), 1):
            if not line.strip():
                raise VerificationError(f"blank row in {label}:{number}")
            value = json.loads(line)
            if not isinstance(value, dict) or (
                expected_keys is not None and set(value) != expected_keys
            ):
                raise VerificationError(f"schema mismatch in {label}:{number}")
            rows.append(value)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot read {label}") from error
    if not rows and not allow_empty:
        raise VerificationError(f"{label} is empty")
    return rows


def read_rows(
    path: Path,
    label: str,
    expected_keys: set[str] | None = None,
    *,
    allow_empty: bool = False,
) -> list[dict[str, Any]]:
    return rows_from_bytes(
        stable_file_bytes(path, label),
        label,
        expected_keys,
        allow_empty=allow_empty,
    )


def finite_or_none(value: Any, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise VerificationError(f"non-finite {label}")
    return float(value)


def load_evaluation_protocol(path: Path, expected_sha: str) -> dict[str, Any]:
    if valid_sha(expected_sha, "evaluation protocol SHA") != EVALUATION_PROTOCOL_SHA256:
        raise VerificationError("evaluation protocol expected SHA mismatch")
    value = object_from_bytes(
        checked_payload(path, "evaluation protocol", EVALUATION_PROTOCOL_SHA256),
        "evaluation protocol",
    )
    entry = value.get("entry_contract") or {}
    primary = value.get("primary") or {}
    support = primary.get("support_gates") or {}
    positive = primary.get("positive_rule") or {}
    inference = value.get("inference") or {}
    bootstrap = inference.get("bootstrap") or {}
    secondary = value.get("secondary") or {}
    output = value.get("output_contract") or {}
    claim = value.get("claim_boundary") or {}
    if (
        value.get("protocol") != EVALUATION_PROTOCOL
        or value.get("status") != "PREREGISTERED_OUTCOME_EVALUATOR_BEFORE_FUTURE_TRUTH_OPEN"
        or value.get("parent_prediction_contract_sha256")
        != PARENT_PREDICTION_BINDING["contract_sha256"]
        or entry.get("prediction_status") != PARENT_PREDICTION_BINDING["status"]
        or entry.get("base_truth_protocol_sha256") != BASE_PROTOCOL_SHA256
        or entry.get("prediction_artifact_manifest_must_verify_before_label_vault_open") is not True
        or entry.get("selected_parent_reconstruction_before_metric") is not True
        or entry.get("outcome_dependent_reselection_allowed") is not False
        or primary.get("truth_tie_absolute_tolerance") != TOLERANCE
        or primary.get("official_five_decimal_grid_required") is not True
        or primary.get("prediction_tie_credit") != 0.5
        or primary.get("task_minimum_role")
        != "minimum analyzability and breadth floor, not a power guarantee"
        or primary.get("aggregation_order")
        != [
            "average informative pair credits within each selected parent",
            "average selected-parent metrics within each task",
            "average the three frozen selection seeds within each task",
            "average task metrics with equal task weight",
        ]
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
        or bootstrap.get("cluster") != "task"
        or bootstrap.get("replicates") != 20000
        or bootstrap.get("seed") != 20260831
        or bootstrap.get("resample_index_algorithm")
        != "uint64_big_endian_first8_sha256(seed\\0replicate\\0position)_mod_n_tasks"
        or bootstrap.get("interval") != "two-sided percentile"
        or bootstrap.get("quantiles") != [0.025, 0.975]
        or bootstrap.get("quantile_algorithm") != "Hyndman-Fan type 7 linear interpolation"
        or (secondary.get("faithful_normalized_truth") or {}).get("may_rescue_primary") is not False
        or (secondary.get("log_loss") or {}).get("may_rescue_primary") is not False
        or (secondary.get("random_arm") or {}).get("may_rescue_primary") is not False
        or output.get("raw_card_level_labels_written") is not False
        or output.get("pair_level_truth_orientations_written") is not False
        or output.get("task_metrics_written_only_if_primary_support_passes") is not True
        or output.get("primary_effect_fields_written_only_if_primary_support_passes") is not True
        or output.get("insufficient_support_status") != STATUS_INSUFFICIENT
        or output.get("positive_status") != STATUS_POSITIVE
        or output.get("nonpositive_status") != STATUS_NONPOSITIVE
        or "component_or_run_breadth_isolated_as_the_causal_mechanism"
        not in (claim.get("forbidden") or [])
        or value.get("resources")
        != {"api_calls": 0, "base_llm_updates": 0, "gpu_jobs": 0, "new_model_fits": 0}
    ):
        raise VerificationError("evaluation protocol semantics mismatch")
    return value


def authenticate_prediction_artifact(
    prediction_dir: Path,
    expected_summary_sha: str,
    expected_manifest_sha: str,
    expected_cohort_sha: str,
    protocol: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Authenticate every parent artifact before any outcome-bearing path is opened."""
    if prediction_dir.is_symlink() or not prediction_dir.is_dir():
        raise VerificationError("prediction escrow is not a regular directory")
    if {path.name for path in prediction_dir.iterdir()} != {
        "artifact_manifest.json",
        "endpoint_scores.csv",
        "pair_predictions.jsonl",
        "training_selection_receipts.jsonl",
        "summary.json",
    }:
        raise VerificationError("prediction escrow has missing or extra artifacts")
    expected_files = {
        "artifact_manifest.json",
        "endpoint_scores.csv",
        "pair_predictions.jsonl",
        "training_selection_receipts.jsonl",
        "summary.json",
    }
    payloads = {
        name: stable_file_bytes(prediction_dir / name, f"prediction artifact {name}")
        for name in sorted(expected_files)
    }
    manifest_path = prediction_dir / "artifact_manifest.json"
    summary_path = prediction_dir / "summary.json"
    if (
        hashlib.sha256(payloads["artifact_manifest.json"]).hexdigest()
        != valid_sha(expected_manifest_sha, "prediction manifest SHA")
    ):
        raise VerificationError("prediction artifact manifest SHA mismatch")
    manifest = object_from_bytes(
        payloads["artifact_manifest.json"], "prediction artifact manifest"
    )
    expected_names = {
        "endpoint_scores.csv",
        "pair_predictions.jsonl",
        "training_selection_receipts.jsonl",
        "summary.json",
    }
    artifacts = manifest.get("artifacts")
    if (
        manifest.get("protocol")
        != f"{PARENT_PREDICTION_BINDING['protocol']}-artifact-manifest-v1"
        or manifest.get("contract_sha256") != PARENT_PREDICTION_BINDING["contract_sha256"]
        or not isinstance(artifacts, dict)
        or set(artifacts) != expected_names
    ):
        raise VerificationError("prediction artifact manifest contract mismatch")
    for name in sorted(expected_names):
        item = artifacts[name]
        if (
            not isinstance(item, dict)
            or set(item) != {"sha256", "bytes"}
            or hashlib.sha256(payloads[name]).hexdigest()
            != valid_sha(item.get("sha256"), f"{name} SHA")
            or isinstance(item.get("bytes"), bool)
            or item.get("bytes") != len(payloads[name])
        ):
            raise VerificationError(f"prediction artifact mismatch: {name}")
    if (
        hashlib.sha256(payloads["summary.json"]).hexdigest()
        != valid_sha(expected_summary_sha, "prediction summary SHA")
    ):
        raise VerificationError("prediction summary SHA mismatch")
    summary = object_from_bytes(payloads["summary.json"], "prediction summary")
    required_scope = protocol["entry_contract"]["prediction_scope_must_assert"]
    scope = summary.get("scope") or {}
    outputs = summary.get("outputs") or {}
    cohort_sha = valid_sha(expected_cohort_sha, "cohort summary SHA")
    if (
        summary.get("protocol") != PARENT_PREDICTION_BINDING["protocol"]
        or summary.get("contract_sha256") != PARENT_PREDICTION_BINDING["contract_sha256"]
        or summary.get("status") != PARENT_PREDICTION_BINDING["status"]
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
        raise VerificationError("prediction summary contract mismatch")
    rows = rows_from_bytes(payloads["pair_predictions.jsonl"], "pair predictions", PAIR_KEYS)
    seen: set[tuple[str, str]] = set()
    ties = collections.Counter({key: 0 for key in MODEL_KEYS})
    for row in rows:
        left, right = row.get("left"), row.get("right")
        identity = (left, right)
        if (
            not all(
                isinstance(row.get(key), str) and row[key]
                for key in ("task", "run_id", "parent", "left", "right")
            )
            or not isinstance(left, str)
            or not isinstance(right, str)
            or not left < right
            or identity in seen
            or row.get("pair_key_sha256") != sha_text("\0".join(identity))
        ):
            raise VerificationError("invalid or duplicate prediction pair identity")
        seen.add(identity)
        for key in MODEL_KEYS:
            margin = row.get(f"{key}_margin_left_minus_right")
            selected = row.get(f"{key}_selected")
            if (
                isinstance(margin, bool)
                or not isinstance(margin, (int, float))
                or not math.isfinite(float(margin))
            ):
                raise VerificationError("invalid prediction margin")
            expected = left if margin > 0 else right if margin < 0 else "tie"
            if selected != expected:
                raise VerificationError("prediction orientation/margin mismatch")
            ties[key] += margin == 0
    inventory = summary.get("future_inventory") or {}
    if inventory.get("eligible_structural_pairs") != len(rows) or inventory.get("ties") != dict(ties):
        raise VerificationError("prediction inventory mismatch")
    if {path.name for path in prediction_dir.iterdir()} != expected_files or any(
        stable_file_bytes(prediction_dir / name, f"prediction artifact {name} recheck")
        != payloads[name]
        for name in sorted(expected_files)
    ):
        raise VerificationError("prediction artifact changed during authentication")
    return rows, summary


def load_base_protocol(path: Path) -> dict[str, Any]:
    value = object_from_bytes(
        checked_payload(path, "base truth protocol", BASE_PROTOCOL_SHA256),
        "base truth protocol",
    )
    closure = value.get("cohort_closure") or {}
    selection = value.get("parent_selection") or {}
    if (
        value.get("protocol") != BASE_PROTOCOL
        or value.get("status") != "FROZEN_OUTCOME_UNREAD_WAITING_COHORT"
        or closure.get("accepted_unique_physical_run_target") != 300
        or closure.get("include_complete_boundary_archive") is not True
        or closure.get("label_or_score_may_affect_closure") is not False
        or selection.get("seed") != 20260813
        or selection.get("max_parents_per_physical_run") != 2
        or selection.get("candidate_count_minimum") != 2
        or selection.get("score_magnitude_used_for_eligibility_or_lottery") is not False
        or selection.get("old_assignments_may_reshuffle") is not False
    ):
        raise VerificationError("base truth protocol semantics mismatch")
    return value


def load_closed_cohort(
    cohort_dir: Path, expected_summary_sha: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    summary_path = cohort_dir / "summary.json"
    summary = object_from_bytes(
        checked_payload(summary_path, "cohort summary", expected_summary_sha),
        "closed cohort summary",
    )
    inputs = summary.get("inputs") or {}
    outputs = summary.get("outputs") or {}
    closure = summary.get("closure") or {}
    inventory = summary.get("inventory") or {}
    blindness = summary.get("blindness") or {}
    if (
        summary.get("protocol") != COHORT_PROTOCOL
        or summary.get("status") != "FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD"
        or inputs.get("protocol_sha256") != BASE_PROTOCOL_SHA256
        or closure.get("accepted_unique_physical_run_target") != 300
        or closure.get("complete_boundary_archive_included") is not True
        or closure.get("remaining_runs_to_target") != 0
        or not isinstance(closure.get("boundary_archive"), str)
        or blindness.get("label_vault_opened") is not False
        or blindness.get("score_or_outcome_opened") is not False
        or blindness.get("truth_support_computed") is not False
        or blindness.get("replay_submission_authorized") is not False
    ):
        raise VerificationError("cohort is not closed and truth-unread")
    runs_path = cohort_dir / "cohort_runs.jsonl"
    archives_path = cohort_dir / "cohort_archives.jsonl"
    runs = rows_from_bytes(
        checked_payload(runs_path, "cohort runs", outputs.get("cohort_runs_sha256")),
        "cohort runs",
        RUN_KEYS,
    )
    archives = rows_from_bytes(
        checked_payload(
            archives_path, "cohort archives", outputs.get("cohort_archives_sha256")
        ),
        "cohort archives",
        ARCHIVE_KEYS,
    )
    if (
        len(runs) < 300
        or inventory.get("selected_physical_runs") != len(runs)
        or inventory.get("selected_archives") != len(archives)
    ):
        raise VerificationError("cohort inventory mismatch")

    archive_by_drop: dict[str, dict[str, Any]] = {}
    order: list[tuple[int, bytes]] = []
    cumulative = 0
    for row in archives:
        drop = row.get("drop_id")
        count = row.get("physical_runs")
        relative = row.get("archive_relative_path")
        mtime = row.get("mtime_ns")
        if (
            not isinstance(drop, str)
            or not drop
            or Path(drop).name != drop
            or drop in archive_by_drop
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
            or not isinstance(relative, str)
            or relative.count("/") != 1
            or not relative.endswith(".tar.gz")
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or isinstance(mtime, bool)
            or not isinstance(mtime, int)
            or mtime < 0
        ):
            raise VerificationError("invalid cohort archive row")
        cumulative += count
        if row.get("cumulative_unique_physical_runs") != cumulative:
            raise VerificationError("cohort cumulative run count mismatch")
        valid_sha(row.get("archive_sha256"), "archive SHA")
        valid_sha(row.get("intake_summary_sha256"), "intake summary SHA")
        valid_sha(row.get("source_provenance_sha256"), "source provenance SHA")
        archive_by_drop[drop] = row
        order.append((mtime, relative.encode("utf-8")))
    if order != sorted(order):
        raise VerificationError("cohort archives are not in frozen order")
    if cumulative != len(runs) or archives[-1]["archive_relative_path"] != closure["boundary_archive"]:
        raise VerificationError("cohort boundary mismatch")

    seen: set[str] = set()
    run_counts: collections.Counter[str] = collections.Counter()
    task_counts: collections.Counter[str] = collections.Counter()
    for row in runs:
        journal = valid_sha(row.get("journal_sha256"), "journal SHA")
        drop, task, run_id = row.get("drop_id"), row.get("task"), row.get("run_id")
        archive = archive_by_drop.get(str(drop))
        if (
            run_id != f"journal:{journal}"
            or run_id in seen
            or not isinstance(task, str)
            or not task
            or archive is None
            or row.get("archive_relative_path") != archive["archive_relative_path"]
            or row.get("archive_sha256") != archive["archive_sha256"]
        ):
            raise VerificationError("invalid cohort run identity")
        seen.add(run_id)
        run_counts[str(drop)] += 1
        task_counts[task] += 1
    if any(run_counts[drop] != row["physical_runs"] for drop, row in archive_by_drop.items()):
        raise VerificationError("cohort archive/run membership mismatch")
    if (
        inventory.get("per_task_selected_runs") != dict(sorted(task_counts.items()))
        or inventory.get("selected_tasks") != len(task_counts)
    ):
        raise VerificationError("cohort task inventory mismatch")
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
        raise VerificationError("cohort input manifest mismatch")
    return runs, summary


def verify_intake(
    state_root: Path, drop_id: str, expected_sha: str
) -> tuple[Path, dict[str, Any]]:
    intake = state_root / "intakes" / drop_id
    if (
        intake.is_symlink()
        or not intake.is_dir()
        or intake.resolve().parent != (state_root / "intakes").resolve()
    ):
        raise VerificationError("unsafe intake directory")
    summary_path = intake / "summary.json"
    summary = object_from_bytes(
        checked_payload(summary_path, "intake summary", expected_sha),
        "intake summary",
    )
    blindness = summary.get("blindness") or {}
    security = summary.get("security") or {}
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
        or blindness.get("labels_used_for_run_selection") is not False
        or blindness.get("labels_used_for_endpoint_selection") is not False
        or blindness.get("label_values_printed") is not False
        or blindness.get("metrics_computed") != []
        or any(security.get(key) != value for key, value in expected_security.items())
    ):
        raise VerificationError("intake blindness/security contract mismatch")
    return intake, summary


def load_truth_state(
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
        raise VerificationError("cohort intake summary manifest missing")
    siblings: dict[tuple[str, str, str], set[str]] = collections.defaultdict(set)
    edges: dict[tuple[str, str, str], set[tuple[str, str]]] = collections.defaultdict(set)
    owners: dict[str, tuple[str, str, str]] = {}
    vault: dict[str, dict[str, Any]] = {}
    seen_vault_cards: set[str] = set()
    summary_shas: dict[str, str] = {}
    for drop in sorted(expected_summaries):
        intake, summary = verify_intake(state_root, drop, expected_summaries[drop])
        summary_shas[drop] = expected_summaries[drop]
        outputs = summary.get("outputs") or {}
        pair_path = intake / "eligible_structural_pairs.jsonl"
        vault_path = intake / "label_vault.jsonl"
        pair_rows = rows_from_bytes(
            checked_payload(
                pair_path,
                f"{drop} structural pairs",
                outputs.get("eligible_structural_pairs_sha256"),
            ),
            f"{drop} structural pairs",
            STRUCTURAL_PAIR_KEYS,
            allow_empty=True,
        )
        vault_rows = rows_from_bytes(
            checked_payload(vault_path, f"{drop} label vault", outputs.get("label_vault_sha256")),
            f"{drop} label vault",
            VAULT_KEYS,
            allow_empty=True,
        )
        for row in pair_rows:
            run_id, task, parent = row.get("run_id"), row.get("task"), row.get("parent")
            left, right = row.get("left"), row.get("right")
            key = (task, run_id, parent)
            edge = (left, right)
            if (
                allowed.get(str(run_id)) != (task, drop)
                or not all(isinstance(item, str) and item for item in (task, run_id, parent, left, right))
                or not left < right
                or parent in {left, right}
                or edge in edges[key]
            ):
                raise VerificationError("invalid or duplicate structural pair")
            edges[key].add(edge)
            siblings[key].update(edge)
            for child in edge:
                if owners.setdefault(child, key) != key:
                    raise VerificationError("structural child has multiple parents")
        for row in vault_rows:
            run_id, task, card = row.get("run_id"), row.get("task"), row.get("card_id")
            if (
                allowed.get(str(run_id)) != (task, drop)
                or not isinstance(card, str)
                or not card
                or card in seen_vault_cards
                or not isinstance(row.get("eligible_by_start_time"), bool)
            ):
                raise VerificationError("invalid or duplicate label-vault identity")
            seen_vault_cards.add(card)
            finite_or_none(row.get("graded"), "graded")
            finite_or_none(row.get("y_norm"), "y_norm")
            if row["eligible_by_start_time"]:
                vault[card] = row
    for key, children in siblings.items():
        ordered = sorted(children)
        expected = {
            (left, right)
            for position, left in enumerate(ordered)
            for right in ordered[position + 1 :]
        }
        if edges[key] != expected:
            raise VerificationError("structural pair set is not a complete sibling clique")
        task, run_id, _ = key
        for child in children:
            row = vault.get(child)
            if row is None or row["task"] != task or row["run_id"] != run_id:
                raise VerificationError("structural child is missing from eligible label vault")
    return siblings, vault, dict(sorted(summary_shas.items()))


def reconstruct_selected_parents(
    runs: list[dict[str, Any]],
    siblings: dict[tuple[str, str, str], set[str]],
    vault: dict[str, dict[str, Any]],
    *,
    seed: int,
    max_parents: int,
) -> tuple[list[dict[str, Any]], int, int]:
    per_run: dict[str, list[tuple[str, str, list[str]]]] = collections.defaultdict(list)
    eligible = 0
    for (task, run_id, parent), children in siblings.items():
        finite = sorted(child for child in children if vault[child]["graded"] is not None)
        if len(finite) < 2:
            continue
        eligible += 1
        key = sha_text(f"{seed}|{run_id}|{parent}")
        per_run[run_id].append((key, parent, finite))
    selected: list[dict[str, Any]] = []
    runs_with = 0
    selected_cards: set[str] = set()
    for run in runs:
        candidates = sorted(per_run.get(run["run_id"], []), key=lambda item: (item[0], item[1]))
        if candidates:
            runs_with += 1
        for rank, (key, parent, children) in enumerate(candidates[:max_parents], 1):
            if selected_cards.intersection(children):
                raise VerificationError("candidate appears in multiple selected parents")
            selected_cards.update(children)
            selected.append(
                {
                    "schema_version": SELECTED_ROW_SCHEMA,
                    "task": run["task"],
                    "run_id": run["run_id"],
                    "parent_id": parent,
                    "source_intake": run["drop_id"],
                    "selection_rank_in_run": rank,
                    "selection_key_sha256": key,
                    "candidate_card_ids": children,
                    "candidate_count": len(children),
                    "candidate_identity_sha256": sha_text(compact(children)),
                }
            )
    return selected, eligible, runs_with


def reconstruct_outcomes_and_selection(
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
        raise VerificationError("symlinked evaluation input is forbidden")
    base = load_base_protocol(base_protocol_path)
    runs, cohort_summary = load_closed_cohort(cohort_dir, expected_cohort_sha)
    observed = rows_from_bytes(
        checked_payload(selected_path, "selected parents", expected_selected_sha),
        "selected parents",
        SELECTED_KEYS,
    )
    siblings, vault, intake_shas = load_truth_state(state_root, runs, cohort_summary)
    spec = base["parent_selection"]
    expected, eligible, runs_with = reconstruct_selected_parents(
        runs,
        siblings,
        vault,
        seed=spec["seed"],
        max_parents=spec["max_parents_per_physical_run"],
    )
    if [compact(row) for row in observed] != [compact(row) for row in expected]:
        raise VerificationError("selected parents differ from independent lottery reconstruction")
    return expected, vault, {
        "intake_summary_sha256": intake_shas,
        "eligible_parents_before_per_run_cap": eligible,
        "runs_with_eligible_parent": runs_with,
    }


def prediction_map(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    mapped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["left"], row["right"])
        if key in mapped:
            raise VerificationError("duplicate prediction pair")
        mapped[key] = row
    return mapped


def support_census(
    selected: list[dict[str, Any]],
    vault: dict[str, dict[str, Any]],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    per_task: collections.Counter[str] = collections.Counter()
    runs: set[str] = set()
    cards_seen: set[str] = set()
    raw_pairs = 0
    for parent in selected:
        cards = parent["candidate_card_ids"]
        cards_seen.update(cards)
        values: list[float] = []
        for card in cards:
            value = vault.get(card, {}).get("graded")
            if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
                raise VerificationError("selected candidate lacks finite official grade")
            number = float(value)
            if not math.isfinite(number) or abs(number - round(number, 5)) > TOLERANCE:
                raise VerificationError("official grade is off the frozen five-decimal grid")
            values.append(number)
        informative = sum(
            abs(values[left] - values[right]) > TOLERANCE
            for left, right in itertools.combinations(range(len(values)), 2)
        )
        raw_pairs += informative
        if informative:
            per_task[parent["task"]] += 1
            runs.add(parent["run_id"])
    total = sum(per_task.values())
    dominant = max(per_task, key=lambda task: (per_task[task], task)) if per_task else None
    dominant_count = per_task.get(dominant, 0) if dominant else 0
    dominant_share = dominant_count / total if total else None
    spec = protocol["primary"]["support_gates"]
    gates = {
        "raw_nontied_selected_parents": total >= spec["raw_nontied_selected_parents_minimum"],
        "selected_physical_runs_with_raw_nontied_parent": len(runs)
        >= spec["selected_physical_runs_with_raw_nontied_parent_minimum"],
        "tasks_with_raw_nontied_selected_parent": len(per_task)
        >= spec["tasks_with_raw_nontied_selected_parent_minimum"],
        "dominant_task_share_of_raw_nontied_selected_parents": dominant_share is not None
        and dominant_share <= spec["dominant_task_share_of_raw_nontied_selected_parents_maximum"],
    }
    return {
        "counts": {
            "selected_parents": len(selected),
            "selected_candidates": len(cards_seen),
            "raw_nontied_selected_parents": total,
            "raw_nontied_pairs": raw_pairs,
            "selected_physical_runs_with_raw_nontied_parent": len(runs),
            "tasks_with_raw_nontied_selected_parent": len(per_task),
        },
        "per_task_raw_nontied_selected_parents": dict(sorted(per_task.items())),
        "balance": {
            "dominant_task": dominant,
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
    if signed >= 0.0:
        return math.log1p(math.exp(-signed))
    return -signed + math.log1p(math.exp(signed))


def task_metrics(
    selected: list[dict[str, Any]],
    vault: dict[str, dict[str, Any]],
    predictions: dict[tuple[str, str], dict[str, Any]],
    truth_key: str,
) -> list[dict[str, Any]]:
    if truth_key not in {"graded", "y_norm"}:
        raise VerificationError("unsupported truth key")
    parent_values: dict[tuple[str, str], list[tuple[float, float, int]]] = collections.defaultdict(list)
    for parent in selected:
        cards = sorted(parent["candidate_card_ids"])
        for model_key in MODEL_KEYS:
            credits: list[float] = []
            losses: list[float] = []
            for left, right in itertools.combinations(cards, 2):
                row = predictions.get((left, right))
                if (
                    row is None
                    or row["task"] != parent["task"]
                    or row["run_id"] != parent["run_id"]
                    or row["parent"] != parent["parent_id"]
                ):
                    raise VerificationError("selected parent pair is absent or misbound in predictions")
                left_value = vault[left][truth_key]
                right_value = vault[right][truth_key]
                if left_value is None or right_value is None:
                    continue
                difference = float(left_value) - float(right_value)
                if not math.isfinite(difference) or abs(difference) <= TOLERANCE:
                    continue
                margin = float(row[f"{model_key}_margin_left_minus_right"])
                credits.append(pair_credit(margin, difference))
                losses.append(pair_log_loss(margin, difference))
            if credits:
                parent_values[(parent["task"], model_key)].append(
                    (sum(credits) / len(credits), sum(losses) / len(losses), len(credits))
                )
    rows: list[dict[str, Any]] = []
    for (task, model_key), values in sorted(parent_values.items()):
        arm, seed_text = model_key.rsplit("_s", 1)
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
        raise VerificationError("invalid type-7 quantile input")
    if len(sorted_values) == 1:
        return sorted_values[0]
    index = (len(sorted_values) - 1) * probability
    lower = int(math.floor(index))
    fraction = index - lower
    if lower + 1 == len(sorted_values):
        return sorted_values[lower]
    return sorted_values[lower] + fraction * (
        sorted_values[lower + 1] - sorted_values[lower]
    )


def bootstrap_interval(
    task_effects: dict[str, float], *, seed: int, replicates: int
) -> tuple[float, float]:
    tasks = sorted(task_effects)
    if not tasks or replicates < 1:
        raise VerificationError("empty task bootstrap")
    values = [task_effects[task] for task in tasks]
    count = len(tasks)
    draws: list[float] = []
    for replicate in range(replicates):
        total = 0.0
        for position in range(count):
            payload = f"{seed}\0{replicate}\0{position}".encode()
            index = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % count
            total += values[index]
        draws.append(total / count)
    draws.sort()
    return type7_quantile(draws, 0.025), type7_quantile(draws, 0.975)


def summarize_metrics(
    rows: list[dict[str, Any]], protocol: dict[str, Any], *, primary: bool
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    index = {(row["task"], row["selection_seed"], row["arm"]): row for row in rows}
    tasks = sorted({row["task"] for row in rows})
    if not tasks or any(
        (task, seed, arm) not in index for task in tasks for seed in SEEDS for arm in ARMS
    ):
        raise VerificationError("task metric support differs across frozen models")
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
            raise VerificationError("leave-one-task-out needs at least two tasks")
        loto.append(
            {
                "truth": rows[0]["truth"],
                "dropped_task": task,
                "effect": sum(remaining) / len(remaining),
            }
        )
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


def recompute_statistics(
    selected: list[dict[str, Any]],
    vault: dict[str, dict[str, Any]],
    prediction_rows: list[dict[str, Any]],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    predictions = prediction_map(prediction_rows)
    support = support_census(selected, vault, protocol)
    if not support["gates"]["all_pass"]:
        return {
            "status": STATUS_INSUFFICIENT,
            "support": support,
            "effects": None,
            "task_rows": [],
            "loto_rows": [],
        }
    raw_rows = task_metrics(selected, vault, predictions, "graded")
    normalized_rows = task_metrics(selected, vault, predictions, "y_norm")
    raw_summary, raw_loto = summarize_metrics(raw_rows, protocol, primary=True)
    normalized_summary, normalized_loto = summarize_metrics(
        normalized_rows, protocol, primary=False
    )
    positive = raw_summary["positive_conditions"]["all_pass"]
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
    return {
        "status": STATUS_POSITIVE if positive else STATUS_NONPOSITIVE,
        "support": support,
        "effects": effects,
        "task_rows": raw_rows + normalized_rows,
        "loto_rows": raw_loto + normalized_loto,
    }


def repository_head(repo: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise VerificationError("cannot resolve evaluation source commit")
    return valid_sha(completed.stdout.strip(), "evaluation source commit", length=40)


def expected_summary(
    statistics: dict[str, Any],
    prediction_summary: dict[str, Any],
    truth_inputs: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    task_rows = statistics["task_rows"]
    return {
        "protocol": OUTPUT_PROTOCOL,
        "evaluation_protocol_sha256": EVALUATION_PROTOCOL_SHA256,
        "prediction_contract_sha256": PARENT_PREDICTION_BINDING["contract_sha256"],
        "status": statistics["status"],
        "source_commit": repository_head(args.repo_root),
        "source_sha256": digest(
            args.repo_root.absolute()
            / "phase1"
            / "evaluate_critic_component_breadth_future_escrow.py"
        ),
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
        "support": statistics["support"],
        "effects": statistics["effects"],
        "scope": {
            "prediction_authenticated_before_label_vault_open": True,
            "selected_parents_independently_reconstructed": True,
            "outcome_dependent_reselection": False,
            "raw_card_level_labels_written": False,
            "pair_level_truth_orientations_written": False,
            "primary_effect_computed": statistics["support"]["gates"]["all_pass"],
            "task_metrics_written": bool(task_rows),
            "gpu_jobs": 0,
            "api_calls": 0,
            "new_model_fits": 0,
            "base_llm_updates": 0,
        },
    }


def compare_exact(expected: Any, observed: Any, location: str = "root") -> None:
    if type(expected) is not type(observed):
        raise VerificationError(f"output type mismatch at {location}")
    if isinstance(expected, dict):
        if set(expected) != set(observed):
            raise VerificationError(f"output keys mismatch at {location}")
        for key in sorted(expected):
            compare_exact(expected[key], observed[key], f"{location}.{key}")
        return
    if isinstance(expected, list):
        if len(expected) != len(observed):
            raise VerificationError(f"output length mismatch at {location}")
        for index, (left, right) in enumerate(zip(expected, observed)):
            compare_exact(left, right, f"{location}[{index}]")
        return
    if isinstance(expected, float):
        if not math.isfinite(expected) or not math.isfinite(observed) or expected != observed:
            raise VerificationError(f"output numeric mismatch at {location}")
        return
    if expected != observed:
        raise VerificationError(f"output value mismatch at {location}")


def validate_evaluation_artifact(
    evaluation_dir: Path,
    expected_summary_sha: str,
    expected_manifest_sha: str,
    expected: dict[str, Any],
    task_rows: list[dict[str, Any]],
    loto_rows: list[dict[str, Any]],
) -> dict[str, str]:
    if evaluation_dir.is_symlink() or not evaluation_dir.is_dir():
        raise VerificationError("evaluation artifact is not a regular directory")
    expected_names = {"summary.json"}
    if task_rows:
        expected_names.update(("task_metrics.jsonl", "leave_one_task_out.jsonl"))
    directory_names = {
        child.name
        for child in evaluation_dir.iterdir()
        if child.name != "artifact_manifest.json"
    }
    if directory_names != expected_names or any(
        child.is_symlink() or not child.is_file() for child in evaluation_dir.iterdir()
    ):
        raise VerificationError("evaluation artifact file set mismatch")
    all_names = expected_names | {"artifact_manifest.json"}
    payloads = {
        name: stable_file_bytes(evaluation_dir / name, f"evaluation artifact {name}")
        for name in sorted(all_names)
    }
    if (
        hashlib.sha256(payloads["artifact_manifest.json"]).hexdigest()
        != valid_sha(expected_manifest_sha, "evaluation manifest SHA")
    ):
        raise VerificationError("evaluation manifest SHA mismatch")
    if (
        hashlib.sha256(payloads["summary.json"]).hexdigest()
        != valid_sha(expected_summary_sha, "evaluation summary SHA")
    ):
        raise VerificationError("evaluation summary SHA mismatch")
    manifest = object_from_bytes(payloads["artifact_manifest.json"], "evaluation artifact manifest")
    artifacts = manifest.get("artifacts")
    if (
        manifest.get("protocol") != f"{OUTPUT_PROTOCOL}-artifact-manifest-v1"
        or manifest.get("evaluation_protocol_sha256") != EVALUATION_PROTOCOL_SHA256
        or not isinstance(artifacts, dict)
        or set(artifacts) != expected_names
    ):
        raise VerificationError("evaluation artifact manifest contract mismatch")
    hashes: dict[str, str] = {}
    for name in sorted(expected_names):
        item = artifacts[name]
        observed_sha = hashlib.sha256(payloads[name]).hexdigest()
        if (
            not isinstance(item, dict)
            or set(item) != {"sha256", "bytes"}
            or observed_sha != valid_sha(item.get("sha256"), f"evaluation {name} SHA")
            or isinstance(item.get("bytes"), bool)
            or item.get("bytes") != len(payloads[name])
        ):
            raise VerificationError(f"evaluation artifact mismatch: {name}")
        hashes[name] = observed_sha
    observed_summary = object_from_bytes(payloads["summary.json"], "evaluation summary")
    compare_exact(expected, observed_summary, "summary")
    if task_rows:
        observed_tasks = rows_from_bytes(
            payloads["task_metrics.jsonl"], "evaluation task metrics", TASK_METRIC_KEYS
        )
        observed_loto = rows_from_bytes(
            payloads["leave_one_task_out.jsonl"], "evaluation LOTO", LOTO_KEYS
        )
        compare_exact(task_rows, observed_tasks, "task_metrics")
        compare_exact(loto_rows, observed_loto, "leave_one_task_out")
    if {path.name for path in evaluation_dir.iterdir()} != all_names or any(
        stable_file_bytes(evaluation_dir / name, f"evaluation artifact {name} recheck")
        != payloads[name]
        for name in sorted(all_names)
    ):
        raise VerificationError("evaluation artifact changed during verification")
    return hashes


def write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise VerificationError("verification receipt path already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        temporary.write_bytes(canonical_bytes(receipt))
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def bind_repository_sources(args: argparse.Namespace) -> dict[str, Path]:
    repo_root = args.repo_root.absolute()
    sources = {
        "protocol": repo_root / "phase1" / "critic_component_breadth_future_evaluation_v1.json",
        "base_protocol": repo_root / "phase1" / "score_channel_future_identifiability_protocol_v1.json",
        "evaluator": repo_root / "phase1" / "evaluate_critic_component_breadth_future_escrow.py",
        "verifier": repo_root / "phase1" / "verify_critic_component_breadth_future_evaluation.py",
    }
    if (
        repo_root.is_symlink()
        or not repo_root.is_dir()
        or repo_root != repo_root.resolve()
        or args.protocol.absolute() != sources["protocol"]
        or args.base_protocol.absolute() != sources["base_protocol"]
        or Path(__file__).absolute() != sources["verifier"]
        or any(path.is_symlink() or not path.is_file() for path in sources.values())
    ):
        raise VerificationError("verifier source/input path binding mismatch")
    return sources


def verify(args: argparse.Namespace) -> dict[str, Any]:
    sources = bind_repository_sources(args)
    source_commit_before = repository_head(args.repo_root)
    protocol = load_evaluation_protocol(args.protocol, args.expect_protocol_sha256)

    # This call must complete before base/cohort/state/selected/evaluation paths are opened.
    prediction_rows, prediction_summary = authenticate_prediction_artifact(
        args.prediction_dir,
        args.expect_prediction_summary_sha256,
        args.expect_prediction_manifest_sha256,
        args.expect_cohort_summary_sha256,
        protocol,
    )
    selected, vault, truth_inputs = reconstruct_outcomes_and_selection(
        args.base_protocol,
        args.cohort_dir,
        args.expect_cohort_summary_sha256,
        args.state_root,
        args.selected_parents,
        args.expect_selected_parents_sha256,
    )
    statistics = recompute_statistics(selected, vault, prediction_rows, protocol)
    expected = expected_summary(statistics, prediction_summary, truth_inputs, args)
    artifact_hashes = validate_evaluation_artifact(
        args.evaluation_dir,
        args.expect_evaluation_summary_sha256,
        args.expect_evaluation_manifest_sha256,
        expected,
        statistics["task_rows"],
        statistics["loto_rows"],
    )
    source_commit_after = repository_head(args.repo_root)
    if source_commit_after != source_commit_before:
        raise VerificationError("source commit changed during independent verification")
    receipt = {
        "protocol": VERIFICATION_PROTOCOL,
        "status": f"VERIFIED_{statistics['status']}",
        "evaluation_protocol_sha256": EVALUATION_PROTOCOL_SHA256,
        "parent_prediction_contract_sha256": PARENT_PREDICTION_BINDING["contract_sha256"],
        "prediction_summary_sha256": valid_sha(
            args.expect_prediction_summary_sha256, "prediction summary SHA"
        ),
        "prediction_manifest_sha256": valid_sha(
            args.expect_prediction_manifest_sha256, "prediction manifest SHA"
        ),
        "cohort_summary_sha256": valid_sha(
            args.expect_cohort_summary_sha256, "cohort summary SHA"
        ),
        "selected_parents_sha256": valid_sha(
            args.expect_selected_parents_sha256, "selected parents SHA"
        ),
        "evaluation_summary_sha256": valid_sha(
            args.expect_evaluation_summary_sha256, "evaluation summary SHA"
        ),
        "evaluation_manifest_sha256": valid_sha(
            args.expect_evaluation_manifest_sha256, "evaluation manifest SHA"
        ),
        "evaluation_artifact_sha256": artifact_hashes,
        "source_commit": source_commit_before,
        "evaluator_source_sha256": digest(sources["evaluator"]),
        "verifier_source_sha256": digest(sources["verifier"]),
        "base_protocol_sha256": digest(sources["base_protocol"]),
        "support_gates_all_pass": statistics["support"]["gates"]["all_pass"],
        "primary_effect_verified": statistics["effects"] is not None,
        "primary_positive": (
            statistics["effects"]["primary_positive"]
            if statistics["effects"] is not None
            else None
        ),
        "outcome_evaluator_module_imported": False,
        "access_attestation": {
            "prediction_authenticated_before_outcome_open": True,
            "selected_parents_independently_reconstructed": True,
            "raw_card_level_labels_written": False,
            "pair_level_truth_orientations_written": False,
            "gpu_jobs": 0,
            "api_calls": 0,
            "new_model_fits": 0,
            "base_llm_updates": 0,
        },
    }
    write_receipt(args.receipt, receipt)
    return receipt


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
    parser.add_argument("--evaluation-dir", required=True, type=Path)
    parser.add_argument("--expect-evaluation-summary-sha256", required=True)
    parser.add_argument("--expect-evaluation-manifest-sha256", required=True)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    try:
        receipt = verify(arguments())
    except (
        VerificationError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        print(f"COMPONENT_BREADTH_FUTURE_EVALUATION_VERIFY_ERROR: {error}", file=sys.stderr)
        return 2
    print(compact(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
