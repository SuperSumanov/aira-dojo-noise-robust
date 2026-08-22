#!/usr/bin/env python3
"""Additive official-grade support audit for the closed future cohort.

The frozen y_norm truth-support output remains untouched. This extension reuses
its selected parent rows exactly and reports only aggregate support under the
official five-decimal ``graded`` value. It never writes card-level labels.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile
from typing import Any

from phase1 import score_channel_future_truth_support as base


PROTOCOL = "score-channel-future-raw-grade-support-extension-v1"
OUTPUT_PROTOCOL = "score-channel-future-raw-grade-support-v1"
BASE_OUTPUT_PROTOCOL = "score-channel-future-truth-support-v1"
BASE_VERIFICATION_PROTOCOL = "score-channel-future-truth-support-independent-verification-v1"
FROZEN_PROTOCOL_SHA256 = "4b13814ad53758d21e7f7b531ede5b9a63fd244c7e305833d0513eb77195c8c0"
BASE_PROTOCOL_SHA256 = "54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d"
BASE_PRODUCER_SHA256 = "7df41993d978ae4942d9d8a5dac7ff0a06ae9564edfba30e2d420c7e4a24aa60"
BASE_VERIFIER_SHA256 = "090bcf603aecac3181705206690fe29da7012c20c92d0fe832be65f11503ea4f"
SHA256_RX = re.compile(r"[0-9a-f]{64}")
TOLERANCE = 1e-12


class RawSupportError(RuntimeError):
    """Fail-closed extension contract or input error."""


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            state.update(block)
    return state.hexdigest()


def valid_sha(value: Any, label: str, *, length: int = 64) -> str:
    if not isinstance(value, str):
        raise RawSupportError(f"invalid {label}")
    lowered = value.lower()
    valid = (
        SHA256_RX.fullmatch(lowered) is not None
        if length == 64
        else len(lowered) == length and all(ch in "0123456789abcdef" for ch in lowered)
    )
    if not valid:
        raise RawSupportError(f"invalid {label}")
    return lowered


def object_file(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RawSupportError(f"{label} is not a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RawSupportError(f"cannot read {label}") from error
    if not isinstance(value, dict):
        raise RawSupportError(f"{label} is not an object")
    return value


def rows_file(path: Path, label: str) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise RawSupportError(f"{label} is not a regular file")
    rows: list[dict[str, Any]] = []
    try:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line:
                raise RawSupportError(f"blank row in {label}")
            row = json.loads(line)
            if not isinstance(row, dict) or set(row) != base.ROW_KEYS:
                raise RawSupportError(f"{label} schema mismatch at row {number}")
            rows.append(row)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RawSupportError(f"cannot read {label}") from error
    if not rows:
        raise RawSupportError(f"{label} is empty")
    return rows


def load_protocol(path: Path, expected_sha: str) -> dict[str, Any]:
    expected = valid_sha(expected_sha, "extension protocol SHA")
    if expected != FROZEN_PROTOCOL_SHA256 or digest(path) != expected:
        raise RawSupportError("extension protocol SHA mismatch")
    value = object_file(path, "raw-grade extension protocol")
    activation = value.get("activation_evidence") or {}
    contract = value.get("base_contract") or {}
    grader = value.get("grader_contract") or {}
    estimand = value.get("parallel_estimand") or {}
    gates = value.get("raw_support_gates_for_separate_design_request") or {}
    limits = value.get("interpretation_limits") or {}
    scope = value.get("scope") or {}
    if (
        value.get("protocol") != PROTOCOL
        or value.get("status") != "FROZEN_FUTURE_OUTCOME_UNREAD_WAITING_BASE_TRUTH"
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
        or estimand.get("all_tasks_reported") is not True
        or estimand.get("cross_task_raw_gap_bins_allowed") is not False
        or estimand.get("task_orientation_required_for_support_counts") is not False
        or estimand.get("raw_label_values_written") is not False
        or gates.get("nontied_selected_parents_minimum") != 80
        or gates.get("tasks_with_nontied_parent_minimum") != 8
        or gates.get("dominant_nontied_task_share_maximum") != 0.25
        or gates.get("selected_physical_runs_minimum") != 60
        or gates.get("all_must_pass") is not True
        or limits.get("base_y_norm_gate_is_still_primary_for_its_original_estimand") is not True
        or limits.get("raw_gate_may_overwrite_or_reverse_base_y_norm_status") is not False
        or limits.get("raw_gate_is_a_separately_named_measurement_amendment") is not True
        or limits.get("replay_submission_authorized") is not False
        or limits.get("gpu_jobs_authorized") != 0
        or limits.get("future_replay_outcomes_may_be_opened") is not False
        or scope.get("gpu_jobs") != 0
        or scope.get("api_calls") != 0
        or scope.get("model_fits") != 0
    ):
        raise RawSupportError("extension protocol contract mismatch")
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
        raise RawSupportError("cannot resolve source commit")
    return valid_sha(value, "source commit", length=40)


def verify_grader(repo: Path, helper: Path, protocol: dict[str, Any]) -> tuple[str, str]:
    grader = protocol["grader_contract"]
    helper_sha = digest(helper)
    if helper_sha != grader["grade_helpers_sha256"]:
        raise RawSupportError("grade helper SHA mismatch")
    if "rounded_score = round(score, 5)" not in helper.read_text(encoding="utf-8"):
        raise RawSupportError("official five-decimal statement missing")
    commit = repository_head(repo)
    if commit != grader["mlebench_git_commit"]:
        raise RawSupportError("MLE-bench commit mismatch")
    return commit, helper_sha


def validate_base_output(
    truth_dir: Path,
    expected_summary_sha: str,
    expected_selected_sha: str,
    verification_path: Path,
    expected_verification_sha: str,
    expected_protocol_sha: str,
    expected_cohort_sha: str,
    reconstructed: list[dict[str, Any]],
    reconstructed_aggregate: dict[str, Any],
) -> tuple[dict[str, Any], str, str, str]:
    summary_path = truth_dir / "summary.json"
    selected_path = truth_dir / "selected_parents.jsonl"
    summary_sha = valid_sha(expected_summary_sha, "base truth summary SHA")
    selected_sha = valid_sha(expected_selected_sha, "base selected-parent SHA")
    verification_sha = valid_sha(expected_verification_sha, "base verification SHA")
    if digest(summary_path) != summary_sha or digest(selected_path) != selected_sha:
        raise RawSupportError("base truth output SHA mismatch")
    if digest(verification_path) != verification_sha:
        raise RawSupportError("base verification receipt SHA mismatch")
    summary = object_file(summary_path, "base truth summary")
    receipt = object_file(verification_path, "base truth verification receipt")
    selected = rows_file(selected_path, "base selected parents")
    decision = summary.get("decision") or {}
    truth = summary.get("truth_support") or {}
    outputs = summary.get("outputs") or {}
    expected_status = (
        "TRUTH_SUPPORT_ELIGIBLE_REPLAY_DESIGN_REQUEST_ONLY"
        if reconstructed_aggregate["gates"]["all_pass"]
        else "TRUTH_SUPPORT_KILL_NO_REPLAY_REQUEST"
    )
    expected_receipt_status = (
        "PASS_ELIGIBLE_REPLAY_DESIGN_REQUEST_ONLY"
        if reconstructed_aggregate["gates"]["all_pass"]
        else "PASS_KILL_NO_REPLAY_REQUEST"
    )
    if selected != reconstructed:
        raise RawSupportError("base selected-parent rows differ from frozen reconstruction")
    if (
        summary.get("protocol") != BASE_OUTPUT_PROTOCOL
        or summary.get("status") != expected_status
        or (summary.get("inputs") or {}).get("protocol_sha256") != expected_protocol_sha
        or (summary.get("inputs") or {}).get("cohort_summary_sha256") != expected_cohort_sha
        or outputs.get("selected_parents_sha256") != selected_sha
        or truth.get("counts") != reconstructed_aggregate["counts"]
        or truth.get("gap_distribution") != reconstructed_aggregate["gap_distribution"]
        or truth.get("per_task") != reconstructed_aggregate["per_task"]
        or truth.get("balance") != reconstructed_aggregate["balance"]
        or truth.get("gates") != reconstructed_aggregate["gates"]
        or decision.get("replay_design_request_eligible") is not reconstructed_aggregate["gates"]["all_pass"]
        or decision.get("replay_submission_authorized") is not False
        or decision.get("gpu_jobs_authorized") != 0
        or receipt.get("protocol") != BASE_VERIFICATION_PROTOCOL
        or receipt.get("status") != expected_receipt_status
        or receipt.get("protocol_sha256") != expected_protocol_sha
        or receipt.get("cohort_summary_sha256") != expected_cohort_sha
        or receipt.get("truth_support_summary_sha256") != summary_sha
        or receipt.get("selected_parents_sha256") != selected_sha
        or receipt.get("all_gates_pass") is not reconstructed_aggregate["gates"]["all_pass"]
        or receipt.get("replay_submission_authorized") is not False
        or receipt.get("raw_labels_written") is not False
        or receipt.get("producer_module_imported") is not False
    ):
        raise RawSupportError("base truth output or verification contract mismatch")
    return summary, summary_sha, selected_sha, verification_sha


def tie_boundary(values: list[float]) -> str:
    if max(values) - min(values) > TOLERANCE:
        raise RawSupportError("boundary requested for non-tied normalized values")
    if all(abs(value) <= TOLERANCE for value in values):
        return "all_zero"
    if all(abs(value - 1.0) <= TOLERANCE for value in values):
        return "all_one"
    return "interior"


def aggregate_raw(
    selected: list[dict[str, Any]],
    vault: dict[str, dict[str, Any]],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    per_task: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    counts: collections.Counter[str] = collections.Counter()
    seen_cards: set[str] = set()
    for parent in selected:
        task = parent["task"]
        cards = list(parent["candidate_card_ids"])
        if len(cards) < 2 or seen_cards.intersection(cards):
            raise RawSupportError("invalid or reused selected candidate")
        seen_cards.update(cards)
        raw = [vault[card]["graded"] for card in cards]
        if any(value is None for value in raw):
            raise RawSupportError("base-selected parent contains missing graded value")
        raw_values = [float(value) for value in raw]
        if any(abs(value - round(value, 5)) > TOLERANCE for value in raw_values):
            raise RawSupportError("official grade is off the frozen five-decimal grid")
        raw_varies = max(raw_values) - min(raw_values) > TOLERANCE
        normalized = [vault[card]["y_norm"] for card in cards]
        normalized_available = all(value is not None for value in normalized)
        normalized_values = [float(value) for value in normalized if value is not None]
        normalized_varies = (
            max(normalized_values) - min(normalized_values) > TOLERANCE
            if normalized_available
            else False
        )

        counts["selected_parents"] += 1
        counts["raw_nontied" if raw_varies else "raw_tied"] += 1
        per_task[task]["selected_parents"] += 1
        per_task[task]["raw_nontied_parents" if raw_varies else "raw_tied_parents"] += 1
        if not normalized_available:
            counts["normalized_unavailable"] += 1
            per_task[task]["normalized_unavailable_parents"] += 1
        else:
            counts["normalized_nontied" if normalized_varies else "normalized_tied"] += 1
            per_task[task][
                "normalized_nontied_parents" if normalized_varies else "normalized_tied_parents"
            ] += 1
            if not normalized_varies:
                boundary = tie_boundary(normalized_values)
                counts[f"normalized_tied_{boundary}"] += 1
                per_task[task][f"normalized_tied_{boundary}"] += 1
            if raw_varies and not normalized_varies:
                counts["alias_parents"] += 1
                per_task[task]["alias_parents"] += 1
            if normalized_varies and not raw_varies:
                counts["impossible_direction"] += 1
                per_task[task]["impossible_direction_parents"] += 1

    if counts["impossible_direction"]:
        raise RawSupportError("normalization created ordering absent from raw grade")
    raw_by_task = {
        task: row["raw_nontied_parents"]
        for task, row in per_task.items()
        if row["raw_nontied_parents"]
    }
    dominant_task = max(raw_by_task, key=lambda item: (raw_by_task[item], item)) if raw_by_task else None
    dominant_count = raw_by_task.get(dominant_task, 0) if dominant_task is not None else 0
    dominant_share = dominant_count / counts["raw_nontied"] if counts["raw_nontied"] else None
    selected_runs = len({row["run_id"] for row in selected})
    gate_spec = protocol["raw_support_gates_for_separate_design_request"]
    gates = {
        "nontied_selected_parents": counts["raw_nontied"] >= gate_spec["nontied_selected_parents_minimum"],
        "tasks_with_nontied_parent": len(raw_by_task) >= gate_spec["tasks_with_nontied_parent_minimum"],
        "dominant_nontied_task_share": dominant_share is not None
        and dominant_share <= gate_spec["dominant_nontied_task_share_maximum"],
        "selected_physical_runs": selected_runs >= gate_spec["selected_physical_runs_minimum"],
    }
    return {
        "counts": {
            "selected_parents": counts["selected_parents"],
            "selected_candidates": len(seen_cards),
            "selected_physical_runs": selected_runs,
            "selected_tasks": len(per_task),
            "raw_tied_parents": counts["raw_tied"],
            "raw_nontied_parents": counts["raw_nontied"],
            "tasks_with_raw_nontied_parent": len(raw_by_task),
            "normalized_truth_unavailable_parents": counts["normalized_unavailable"],
            "normalized_tied_parents": counts["normalized_tied"],
            "normalized_nontied_parents": counts["normalized_nontied"],
            "alias_parents": counts["alias_parents"],
            "alias_tasks": sum(row["alias_parents"] > 0 for row in per_task.values()),
            "impossible_direction_parents": counts["impossible_direction"],
            "official_five_decimal_grid_violations": 0,
        },
        "normalized_tied_boundary_counts": {
            "all_zero": counts["normalized_tied_all_zero"],
            "all_one": counts["normalized_tied_all_one"],
            "interior": counts["normalized_tied_interior"],
        },
        "per_task": {
            task: {key: int(value) for key, value in sorted(row.items())}
            for task, row in sorted(per_task.items())
        },
        "balance": {
            "dominant_raw_nontied_task": dominant_task,
            "dominant_raw_nontied_parents": dominant_count,
            "dominant_raw_nontied_task_share": dominant_share,
        },
        "gates": {**gates, "all_pass": all(gates.values())},
    }


def produce(args: argparse.Namespace) -> dict[str, Any]:
    if args.out_dir.exists():
        raise FileExistsError(f"refusing to overwrite raw-grade support output: {args.out_dir}")
    protocol = load_protocol(args.protocol, args.expect_protocol_sha256)
    if digest(args.base_protocol) != BASE_PROTOCOL_SHA256 or args.expect_base_protocol_sha256 != BASE_PROTOCOL_SHA256:
        raise RawSupportError("base protocol SHA mismatch")
    if digest(Path(base.__file__)) != BASE_PRODUCER_SHA256:
        raise RawSupportError("base producer implementation drift")
    base_protocol = base.load_protocol(args.base_protocol, args.expect_base_protocol_sha256)
    runs, cohort_summary = base.load_cohort(
        args.cohort_dir,
        args.expect_base_protocol_sha256,
        args.expect_cohort_summary_sha256,
    )
    siblings, vault, intake_shas = base.load_truth_inputs(args.state_root, runs, cohort_summary)
    selection = base_protocol["parent_selection"]
    selected, eligible, runs_with = base.select_parents(
        runs,
        siblings,
        vault,
        selection["seed"],
        selection["max_parents_per_physical_run"],
    )
    normalized_aggregate = base.aggregate_truth(selected, vault, base_protocol)
    base_summary, base_summary_sha, selected_sha, base_verification_sha = validate_base_output(
        args.base_truth_dir,
        args.expect_base_truth_summary_sha256,
        args.expect_base_selected_sha256,
        args.base_verification,
        args.expect_base_verification_sha256,
        args.expect_base_protocol_sha256,
        args.expect_cohort_summary_sha256,
        selected,
        normalized_aggregate,
    )
    grader_commit, helper_sha = verify_grader(args.mlebench_repo, args.grade_helpers, protocol)
    raw = aggregate_raw(selected, vault, protocol)
    raw_pass = raw["gates"]["all_pass"]

    args.out_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{args.out_dir.name}.tmp.", dir=args.out_dir.parent))
    try:
        summary = {
            "protocol": OUTPUT_PROTOCOL,
            "status": (
                "RAW_GRADE_SUPPORT_ELIGIBLE_SEPARATE_DESIGN_REQUEST_ONLY"
                if raw_pass
                else "RAW_GRADE_SUPPORT_KILL_NO_REPLAY_REQUEST"
            ),
            "inputs": {
                "extension_protocol_sha256": valid_sha(args.expect_protocol_sha256, "extension protocol SHA"),
                "base_protocol_sha256": BASE_PROTOCOL_SHA256,
                "cohort_summary_sha256": valid_sha(args.expect_cohort_summary_sha256, "cohort summary SHA"),
                "cohort_runs_sha256": digest(args.cohort_dir / "cohort_runs.jsonl"),
                "cohort_archives_sha256": digest(args.cohort_dir / "cohort_archives.jsonl"),
                "intake_summary_sha256": dict(sorted(intake_shas.items())),
                "base_truth_summary_sha256": base_summary_sha,
                "base_selected_parents_sha256": selected_sha,
                "base_independent_verification_sha256": base_verification_sha,
                "mlebench_git_commit": grader_commit,
                "grade_helpers_sha256": helper_sha,
            },
            "selection": {
                "selected_parent_rows_reused_byte_exactly": True,
                "selected_parents_sha256": selected_sha,
                "outcome_dependent_reselection": False,
                "eligible_parents_before_per_run_cap": eligible,
                "runs_with_eligible_parent": runs_with,
            },
            "base_y_norm_gate": {
                "status": base_summary["status"],
                "all_gates_pass": normalized_aggregate["gates"]["all_pass"],
                "counts": normalized_aggregate["counts"],
                "gates": normalized_aggregate["gates"],
                "status_overwritten_or_reversed": False,
            },
            "raw_grade_support": {
                "definition": protocol["parallel_estimand"]["raw_informative_definition"],
                "absolute_tolerance": TOLERANCE,
                "official_five_decimal_grid_required": True,
                "cross_task_raw_gap_bins_reported": False,
                **raw,
            },
            "decision": {
                "raw_grade_separate_design_request_eligible": raw_pass,
                "base_y_norm_decision_unchanged": True,
                "replay_submission_authorized": False,
                "gpu_jobs_authorized": 0,
                "pass_action": protocol["raw_support_gates_for_separate_design_request"]["pass_action"],
                "failure_action": protocol["raw_support_gates_for_separate_design_request"]["failure_action"],
            },
            "blindness": {
                "identity_closed_before_label_open": True,
                "base_selected_parent_rows_reused": True,
                "raw_grade_used_for_parent_selection": False,
                "y_norm_used_for_parent_selection": False,
                "task_orientation_opened": False,
                "blind_code_view_opened": False,
                "score_directory_opened": False,
                "replay_outcomes_opened": False,
                "raw_label_values_written": False,
            },
            "implementation": {
                "source_commit": repository_head(args.repo),
                "script_sha256": digest(Path(__file__)),
                "base_producer_sha256": digest(Path(base.__file__)),
                "python": platform.python_version(),
            },
        }
        (temporary / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, args.out_dir)
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
    parser.add_argument("--mlebench-repo", required=True, type=Path)
    parser.add_argument("--grade-helpers", required=True, type=Path)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    summary = produce(args)
    print(canonical({
        "status": summary["status"],
        "base_y_norm_status": summary["base_y_norm_gate"]["status"],
        "raw_nontied_parents": summary["raw_grade_support"]["counts"]["raw_nontied_parents"],
        "raw_nontied_tasks": summary["raw_grade_support"]["counts"]["tasks_with_raw_nontied_parent"],
        "raw_design_request_eligible": summary["decision"]["raw_grade_separate_design_request_eligible"],
        "replay_submission_authorized": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
