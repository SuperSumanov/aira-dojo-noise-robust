#!/usr/bin/env python3
"""Independent verifier for the additive future raw-grade support audit.

This module does not import the extension producer or the base producer. It
uses the already independent base-verifier reconstruction and independently
recomputes the official-grade aggregate on those exact selected rows.
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
import subprocess
import tempfile
from typing import Any

from phase1 import verify_score_channel_future_truth_support as base_verify


PROTOCOL = "score-channel-future-raw-grade-support-extension-v1"
OUTPUT_PROTOCOL = "score-channel-future-raw-grade-support-v1"
BASE_OUTPUT_PROTOCOL = "score-channel-future-truth-support-v1"
BASE_RECEIPT_PROTOCOL = "score-channel-future-truth-support-independent-verification-v1"
FROZEN_PROTOCOL_SHA256 = "4b13814ad53758d21e7f7b531ede5b9a63fd244c7e305833d0513eb77195c8c0"
BASE_PROTOCOL_SHA256 = "54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d"
BASE_PRODUCER_SHA256 = "7df41993d978ae4942d9d8a5dac7ff0a06ae9564edfba30e2d420c7e4a24aa60"
BASE_VERIFIER_SHA256 = "090bcf603aecac3181705206690fe29da7012c20c92d0fe832be65f11503ea4f"
TOLERANCE = 1e-12
SHA_RX = re.compile(r"[0-9a-f]{64}")


class RawSupportVerificationError(RuntimeError):
    """Raised on any extension, base, or reconstruction mismatch."""


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            state.update(block)
    return state.hexdigest()


def sha(value: Any, label: str, *, length: int = 64) -> str:
    if not isinstance(value, str):
        raise RawSupportVerificationError(f"invalid {label}")
    lowered = value.lower()
    valid = (
        SHA_RX.fullmatch(lowered) is not None
        if length == 64
        else len(lowered) == length and all(ch in "0123456789abcdef" for ch in lowered)
    )
    if not valid:
        raise RawSupportVerificationError(f"invalid {label}")
    return lowered


def obj(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RawSupportVerificationError(f"{label} is not a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RawSupportVerificationError(f"cannot read {label}") from error
    if not isinstance(value, dict):
        raise RawSupportVerificationError(f"{label} is not an object")
    return value


def rows(path: Path, label: str) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise RawSupportVerificationError(f"{label} is not a regular file")
    result: list[dict[str, Any]] = []
    try:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line:
                raise RawSupportVerificationError(f"blank line in {label}")
            row = json.loads(line)
            if not isinstance(row, dict) or set(row) != base_verify.SELECTED_KEYS:
                raise RawSupportVerificationError(f"{label} schema mismatch at row {number}")
            result.append(row)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RawSupportVerificationError(f"cannot read {label}") from error
    if not result:
        raise RawSupportVerificationError(f"{label} is empty")
    return result


def protocol(path: Path, expected_sha: str) -> dict[str, Any]:
    if sha(expected_sha, "extension protocol SHA") != FROZEN_PROTOCOL_SHA256 or digest(path) != FROZEN_PROTOCOL_SHA256:
        raise RawSupportVerificationError("extension protocol SHA mismatch")
    value = obj(path, "extension protocol")
    activation = value.get("activation_evidence") or {}
    contract = value.get("base_contract") or {}
    grader = value.get("grader_contract") or {}
    estimand = value.get("parallel_estimand") or {}
    gates = value.get("raw_support_gates_for_separate_design_request") or {}
    limits = value.get("interpretation_limits") or {}
    if (
        value.get("protocol") != PROTOCOL
        or value.get("status") != "FROZEN_FUTURE_OUTCOME_UNREAD_WAITING_BASE_TRUTH"
        or activation.get("formal_analysis_sha256") != "38788c89ca8231428482d9bea1a43e5a641eda7a6efa26dec89eb6499e594ba5"
        or activation.get("independent_verification_sha256") != "4b56b9e2e3cb9c52f390dd92b3877f818ef7b2edecc27cde919c06a09fb22789"
        or activation.get("material_aliasing_status") != "MATERIAL_Y_NORM_ALIASING"
        or activation.get("alias_parents") != 147
        or activation.get("alias_tasks") != 16
        or activation.get("impossible_direction_parents") != 0
        or contract.get("protocol_sha256") != BASE_PROTOCOL_SHA256
        or contract.get("producer_sha256") != BASE_PRODUCER_SHA256
        or contract.get("independent_verifier_sha256") != BASE_VERIFIER_SHA256
        or contract.get("base_y_norm_status_must_remain_unchanged") is not True
        or contract.get("base_selected_parent_rows_must_be_reused_byte_exactly") is not True
        or contract.get("outcome_dependent_reselection_allowed") is not False
        or grader.get("mlebench_git_commit") != "507f92e1138bb6e40dac5c6ee7a6758e6424bf97"
        or grader.get("grade_helpers_sha256") != "7d55512a893699b2e17041f3cd3bd0c2aba955c73f50872b3c69238546b87005"
        or grader.get("official_score_operation") != "round(score, 5)"
        or grader.get("unrounded_score_recovery_claim_allowed") is not False
        or estimand.get("absolute_tolerance") != TOLERANCE
        or estimand.get("official_five_decimal_grid_required") is not True
        or estimand.get("cross_task_raw_gap_bins_allowed") is not False
        or estimand.get("task_orientation_required_for_support_counts") is not False
        or estimand.get("raw_label_values_written") is not False
        or gates.get("nontied_selected_parents_minimum") != 80
        or gates.get("tasks_with_nontied_parent_minimum") != 8
        or gates.get("dominant_nontied_task_share_maximum") != 0.25
        or gates.get("selected_physical_runs_minimum") != 60
        or gates.get("all_must_pass") is not True
        or limits.get("raw_gate_may_overwrite_or_reverse_base_y_norm_status") is not False
        or limits.get("replay_submission_authorized") is not False
        or limits.get("gpu_jobs_authorized") != 0
        or limits.get("future_replay_outcomes_may_be_opened") is not False
    ):
        raise RawSupportVerificationError("extension protocol contract mismatch")
    return value


def repository_head(repo: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    value = completed.stdout.strip()
    if completed.returncode or len(value) != 40:
        raise RawSupportVerificationError("cannot resolve source commit")
    return sha(value, "source commit", length=40)


def verify_grader(repo: Path, helper: Path, frozen: dict[str, Any]) -> tuple[str, str]:
    grader = frozen["grader_contract"]
    helper_sha = digest(helper)
    if helper_sha != grader["grade_helpers_sha256"]:
        raise RawSupportVerificationError("grade helper SHA mismatch")
    if "rounded_score = round(score, 5)" not in helper.read_text(encoding="utf-8"):
        raise RawSupportVerificationError("five-decimal grader statement missing")
    commit = repository_head(repo)
    if commit != grader["mlebench_git_commit"]:
        raise RawSupportVerificationError("MLE-bench commit mismatch")
    return commit, helper_sha


def raw_aggregate(selected: list[dict[str, Any]], vault: dict[str, dict[str, Any]]) -> dict[str, Any]:
    task_rows: dict[str, Counter[str]] = defaultdict(Counter)
    total: Counter[str] = Counter()
    cards_seen: set[str] = set()
    runs_seen: set[str] = set()
    for parent in selected:
        task = parent["task"]
        card_ids = parent["candidate_card_ids"]
        if len(card_ids) < 2 or cards_seen.intersection(card_ids):
            raise RawSupportVerificationError("invalid selected candidate reuse")
        cards_seen.update(card_ids)
        runs_seen.add(parent["run_id"])
        raw_values: list[float] = []
        normalized_values: list[float] = []
        normalized_available = True
        for card in card_ids:
            grade = vault[card]["graded"]
            if grade is None:
                raise RawSupportVerificationError("selected card has missing grade")
            numeric = float(grade)
            if not math.isfinite(numeric) or abs(numeric - round(numeric, 5)) > TOLERANCE:
                raise RawSupportVerificationError("official grade is not on five-decimal grid")
            raw_values.append(numeric)
            normalized = vault[card]["y_norm"]
            if normalized is None:
                normalized_available = False
            else:
                normalized_values.append(float(normalized))

        raw_nontied = max(raw_values) - min(raw_values) > TOLERANCE
        total["selected"] += 1
        total["raw_nontied" if raw_nontied else "raw_tied"] += 1
        task_rows[task]["selected_parents"] += 1
        task_rows[task]["raw_nontied_parents" if raw_nontied else "raw_tied_parents"] += 1
        if not normalized_available:
            total["norm_unavailable"] += 1
            task_rows[task]["normalized_unavailable_parents"] += 1
            continue
        norm_nontied = max(normalized_values) - min(normalized_values) > TOLERANCE
        total["norm_nontied" if norm_nontied else "norm_tied"] += 1
        task_rows[task]["normalized_nontied_parents" if norm_nontied else "normalized_tied_parents"] += 1
        if not norm_nontied:
            if all(abs(value) <= TOLERANCE for value in normalized_values):
                boundary = "all_zero"
            elif all(abs(value - 1.0) <= TOLERANCE for value in normalized_values):
                boundary = "all_one"
            else:
                boundary = "interior"
            total[f"boundary_{boundary}"] += 1
            task_rows[task][f"normalized_tied_{boundary}"] += 1
        if raw_nontied and not norm_nontied:
            total["alias"] += 1
            task_rows[task]["alias_parents"] += 1
        if norm_nontied and not raw_nontied:
            total["impossible"] += 1
            task_rows[task]["impossible_direction_parents"] += 1

    if total["impossible"]:
        raise RawSupportVerificationError("impossible normalization direction observed")
    task_support = {
        task: row["raw_nontied_parents"]
        for task, row in task_rows.items()
        if row["raw_nontied_parents"] > 0
    }
    dominant_task = max(task_support, key=lambda task: (task_support[task], task)) if task_support else None
    dominant_count = task_support.get(dominant_task, 0) if dominant_task else 0
    dominant_share = dominant_count / total["raw_nontied"] if total["raw_nontied"] else None
    gates = {
        "nontied_selected_parents": total["raw_nontied"] >= 80,
        "tasks_with_nontied_parent": len(task_support) >= 8,
        "dominant_nontied_task_share": dominant_share is not None and dominant_share <= 0.25,
        "selected_physical_runs": len(runs_seen) >= 60,
    }
    return {
        "counts": {
            "selected_parents": total["selected"],
            "selected_candidates": len(cards_seen),
            "selected_physical_runs": len(runs_seen),
            "selected_tasks": len(task_rows),
            "raw_tied_parents": total["raw_tied"],
            "raw_nontied_parents": total["raw_nontied"],
            "tasks_with_raw_nontied_parent": len(task_support),
            "normalized_truth_unavailable_parents": total["norm_unavailable"],
            "normalized_tied_parents": total["norm_tied"],
            "normalized_nontied_parents": total["norm_nontied"],
            "alias_parents": total["alias"],
            "alias_tasks": sum(row["alias_parents"] > 0 for row in task_rows.values()),
            "impossible_direction_parents": total["impossible"],
            "official_five_decimal_grid_violations": 0,
        },
        "normalized_tied_boundary_counts": {
            "all_zero": total["boundary_all_zero"],
            "all_one": total["boundary_all_one"],
            "interior": total["boundary_interior"],
        },
        "per_task": {
            task: {key: int(value) for key, value in sorted(row.items())}
            for task, row in sorted(task_rows.items())
        },
        "balance": {
            "dominant_raw_nontied_task": dominant_task,
            "dominant_raw_nontied_parents": dominant_count,
            "dominant_raw_nontied_task_share": dominant_share,
        },
        "gates": {**gates, "all_pass": all(gates.values())},
    }


def verify(args: argparse.Namespace) -> dict[str, Any]:
    frozen = protocol(args.protocol, args.expect_protocol_sha256)
    if digest(args.base_protocol) != BASE_PROTOCOL_SHA256 or args.expect_base_protocol_sha256 != BASE_PROTOCOL_SHA256:
        raise RawSupportVerificationError("base protocol SHA mismatch")
    if digest(Path(base_verify.__file__)) != BASE_VERIFIER_SHA256:
        raise RawSupportVerificationError("base independent verifier drift")
    base_verify.protocol_at(args.base_protocol, args.expect_base_protocol_sha256)
    runs, cohort_summary = base_verify.closed_runs(
        args.cohort_dir,
        args.expect_base_protocol_sha256,
        args.expect_cohort_summary_sha256,
    )
    siblings, vault = base_verify.read_truth_state(args.state_root, runs, cohort_summary)
    selected, eligible, runs_with = base_verify.reconstruct_selection(runs, siblings, vault)
    normalized = base_verify.reconstruct_aggregate(selected, vault)

    base_summary_path = args.base_truth_dir / "summary.json"
    base_selected_path = args.base_truth_dir / "selected_parents.jsonl"
    expected_base_summary_sha = sha(args.expect_base_truth_summary_sha256, "base summary SHA")
    expected_selected_sha = sha(args.expect_base_selected_sha256, "base selected SHA")
    expected_base_receipt_sha = sha(args.expect_base_verification_sha256, "base receipt SHA")
    if digest(base_summary_path) != expected_base_summary_sha or digest(base_selected_path) != expected_selected_sha:
        raise RawSupportVerificationError("base output SHA mismatch")
    if digest(args.base_verification) != expected_base_receipt_sha:
        raise RawSupportVerificationError("base receipt SHA mismatch")
    base_summary = obj(base_summary_path, "base summary")
    base_receipt = obj(args.base_verification, "base verification receipt")
    actual_selected = rows(base_selected_path, "base selected parents")
    base_pass = normalized["gates"]["all_pass"]
    expected_base_status = (
        "TRUTH_SUPPORT_ELIGIBLE_REPLAY_DESIGN_REQUEST_ONLY" if base_pass else "TRUTH_SUPPORT_KILL_NO_REPLAY_REQUEST"
    )
    expected_receipt_status = (
        "PASS_ELIGIBLE_REPLAY_DESIGN_REQUEST_ONLY" if base_pass else "PASS_KILL_NO_REPLAY_REQUEST"
    )
    if (
        actual_selected != selected
        or base_summary.get("protocol") != BASE_OUTPUT_PROTOCOL
        or base_summary.get("status") != expected_base_status
        or (base_summary.get("inputs") or {}).get("protocol_sha256") != BASE_PROTOCOL_SHA256
        or (base_summary.get("inputs") or {}).get("cohort_summary_sha256") != args.expect_cohort_summary_sha256
        or (base_summary.get("outputs") or {}).get("selected_parents_sha256") != expected_selected_sha
        or (base_summary.get("truth_support") or {}).get("counts") != normalized["counts"]
        or (base_summary.get("truth_support") or {}).get("gap_distribution") != normalized["gap_distribution"]
        or (base_summary.get("truth_support") or {}).get("per_task") != normalized["per_task"]
        or (base_summary.get("truth_support") or {}).get("balance") != normalized["balance"]
        or (base_summary.get("truth_support") or {}).get("gates") != normalized["gates"]
        or (base_summary.get("decision") or {}).get("replay_submission_authorized") is not False
        or base_receipt.get("protocol") != BASE_RECEIPT_PROTOCOL
        or base_receipt.get("status") != expected_receipt_status
        or base_receipt.get("truth_support_summary_sha256") != expected_base_summary_sha
        or base_receipt.get("selected_parents_sha256") != expected_selected_sha
        or base_receipt.get("producer_module_imported") is not False
        or base_receipt.get("replay_submission_authorized") is not False
    ):
        raise RawSupportVerificationError("base output independent reconstruction mismatch")

    grader = frozen["grader_contract"]
    grader_commit, helper_sha = verify_grader(args.mlebench_repo, args.grade_helpers, frozen)

    raw = raw_aggregate(selected, vault)
    summary_path = args.extension_dir / "summary.json"
    summary = obj(summary_path, "raw-grade extension summary")
    inputs = summary.get("inputs") or {}
    selection = summary.get("selection") or {}
    base_gate = summary.get("base_y_norm_gate") or {}
    raw_support = summary.get("raw_grade_support") or {}
    decision = summary.get("decision") or {}
    blindness = summary.get("blindness") or {}
    implementation = summary.get("implementation") or {}
    raw_pass = raw["gates"]["all_pass"]
    expected_status = (
        "RAW_GRADE_SUPPORT_ELIGIBLE_SEPARATE_DESIGN_REQUEST_ONLY"
        if raw_pass
        else "RAW_GRADE_SUPPORT_KILL_NO_REPLAY_REQUEST"
    )
    producer_path = Path(__file__).with_name("score_channel_future_raw_grade_support.py")
    expected_intakes = (cohort_summary.get("inputs") or {}).get("intake_summary_sha256")
    if (
        summary.get("protocol") != OUTPUT_PROTOCOL
        or summary.get("status") != expected_status
        or inputs.get("extension_protocol_sha256") != FROZEN_PROTOCOL_SHA256
        or inputs.get("base_protocol_sha256") != BASE_PROTOCOL_SHA256
        or inputs.get("cohort_summary_sha256") != args.expect_cohort_summary_sha256
        or inputs.get("cohort_runs_sha256") != digest(args.cohort_dir / "cohort_runs.jsonl")
        or inputs.get("cohort_archives_sha256") != digest(args.cohort_dir / "cohort_archives.jsonl")
        or inputs.get("intake_summary_sha256") != expected_intakes
        or inputs.get("base_truth_summary_sha256") != expected_base_summary_sha
        or inputs.get("base_selected_parents_sha256") != expected_selected_sha
        or inputs.get("base_independent_verification_sha256") != expected_base_receipt_sha
        or inputs.get("mlebench_git_commit") != grader_commit
        or inputs.get("grade_helpers_sha256") != helper_sha
        or selection.get("selected_parent_rows_reused_byte_exactly") is not True
        or selection.get("selected_parents_sha256") != expected_selected_sha
        or selection.get("outcome_dependent_reselection") is not False
        or selection.get("eligible_parents_before_per_run_cap") != eligible
        or selection.get("runs_with_eligible_parent") != runs_with
        or base_gate.get("status") != expected_base_status
        or base_gate.get("all_gates_pass") is not base_pass
        or base_gate.get("counts") != normalized["counts"]
        or base_gate.get("gates") != normalized["gates"]
        or base_gate.get("status_overwritten_or_reversed") is not False
        or raw_support.get("definition") != frozen["parallel_estimand"]["raw_informative_definition"]
        or raw_support.get("absolute_tolerance") != TOLERANCE
        or raw_support.get("official_five_decimal_grid_required") is not True
        or raw_support.get("cross_task_raw_gap_bins_reported") is not False
        or raw_support.get("counts") != raw["counts"]
        or raw_support.get("normalized_tied_boundary_counts") != raw["normalized_tied_boundary_counts"]
        or raw_support.get("per_task") != raw["per_task"]
        or raw_support.get("balance") != raw["balance"]
        or raw_support.get("gates") != raw["gates"]
        or decision.get("raw_grade_separate_design_request_eligible") is not raw_pass
        or decision.get("base_y_norm_decision_unchanged") is not True
        or decision.get("replay_submission_authorized") is not False
        or decision.get("gpu_jobs_authorized") != 0
        or decision.get("pass_action") != frozen["raw_support_gates_for_separate_design_request"]["pass_action"]
        or decision.get("failure_action") != frozen["raw_support_gates_for_separate_design_request"]["failure_action"]
        or blindness.get("identity_closed_before_label_open") is not True
        or blindness.get("base_selected_parent_rows_reused") is not True
        or blindness.get("raw_grade_used_for_parent_selection") is not False
        or blindness.get("y_norm_used_for_parent_selection") is not False
        or blindness.get("task_orientation_opened") is not False
        or blindness.get("blind_code_view_opened") is not False
        or blindness.get("score_directory_opened") is not False
        or blindness.get("replay_outcomes_opened") is not False
        or blindness.get("raw_label_values_written") is not False
        or implementation.get("source_commit") != repository_head(args.repo)
        or implementation.get("script_sha256") != digest(producer_path)
        or implementation.get("base_producer_sha256") != BASE_PRODUCER_SHA256
    ):
        raise RawSupportVerificationError("raw-grade extension summary reconstruction mismatch")

    receipt = {
        "protocol": "score-channel-future-raw-grade-support-independent-verification-v1",
        "status": "VERIFIED_" + expected_status,
        "extension_producer_module_imported": False,
        "base_producer_module_imported": False,
        "base_independent_verifier_sha256": digest(Path(base_verify.__file__)),
        "extension_protocol_sha256": FROZEN_PROTOCOL_SHA256,
        "cohort_summary_sha256": sha(args.expect_cohort_summary_sha256, "cohort summary SHA"),
        "base_truth_summary_sha256": expected_base_summary_sha,
        "base_selected_parents_sha256": expected_selected_sha,
        "base_verification_sha256": expected_base_receipt_sha,
        "extension_summary_sha256": digest(summary_path),
        "selected_parents": raw["counts"]["selected_parents"],
        "raw_nontied_parents": raw["counts"]["raw_nontied_parents"],
        "tasks_with_raw_nontied_parent": raw["counts"]["tasks_with_raw_nontied_parent"],
        "raw_gates_all_pass": raw_pass,
        "base_y_norm_status_unchanged": True,
        "replay_submission_authorized": False,
        "raw_labels_written": False,
    }
    if args.receipt.exists():
        raise FileExistsError(f"refusing to overwrite raw-grade verification receipt: {args.receipt}")
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{args.receipt.name}.", dir=args.receipt.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        temporary.write_text(
            json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, args.receipt)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return receipt


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--base-protocol", required=True, type=Path)
    parser.add_argument("--expect-base-protocol-sha256", required=True)
    parser.add_argument("--cohort-dir", required=True, type=Path)
    parser.add_argument("--expect-cohort-summary-sha256", required=True)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--base-truth-dir", required=True, type=Path)
    parser.add_argument("--expect-base-truth-summary-sha256", required=True)
    parser.add_argument("--expect-base-selected-sha256", required=True)
    parser.add_argument("--base-verification", required=True, type=Path)
    parser.add_argument("--expect-base-verification-sha256", required=True)
    parser.add_argument("--extension-dir", required=True, type=Path)
    parser.add_argument("--mlebench-repo", required=True, type=Path)
    parser.add_argument("--grade-helpers", required=True, type=Path)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    result = verify(arguments())
    print(canonical(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
