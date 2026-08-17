#!/usr/bin/env python3
"""Independent verifier for score-channel prospective analysis.

This module intentionally does not import the producer.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import os
import random
from pathlib import Path
from typing import Any


SEED = 20260813
BOOTSTRAPS = 10_000
SELECTION_KEYS = {
    "schema_version", "task", "run_id", "parent_id", "source_intake",
    "selection_rank_in_run", "selection_key_sha256", "candidate_card_ids",
    "candidate_count", "candidate_identity_sha256",
}
RESULT_KEYS = {
    "schema_version", "card_id", "competition", "task", "run_id", "parent",
    "source_intake", "selection_rank_in_run", "shard_id", "cap_seconds",
    "code_sha256", "rc", "wall_seconds", "stdout_val", "val_how",
    "stdout_bytes", "stderr_bytes", "stdout_sha256", "stderr_sha256",
    "sub_exists", "submission_bytes", "submission_sha256",
    "submission_line_count", "submission_header_sha256", "grader_rc",
    "sub_score", "grader_output_sha256", "execution_attempts",
    "manifest_sha256", "approval_sha256", "worker_source_commit",
}
VAULT_KEYS = {"card_id", "task", "run_id", "graded", "y_norm", "eligible_by_start_time"}


class VerifyError(RuntimeError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            state.update(block)
    return state.hexdigest()


def valid_sha(value: Any, label: str, length: int = 64) -> str:
    if (
        not isinstance(value, str) or len(value) != length
        or any(character not in "0123456789abcdef" for character in value.lower())
    ):
        raise VerifyError(f"invalid {label}")
    return value.lower()


def finite(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(float(value))


def object_file(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        canonical(value)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise VerifyError(f"invalid {label}") from error
    if not isinstance(value, dict):
        raise VerifyError(f"non-object {label}")
    return value


def row_file(path: Path, label: str, allow_empty: bool = False) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise VerifyError(f"cannot read {label}") from error
    if not lines and not allow_empty:
        raise VerifyError(f"empty {label}")
    rows = []
    for number, line in enumerate(lines, 1):
        if not line:
            raise VerifyError(f"blank {label} line")
        try:
            row = json.loads(line)
            canonical(row)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise VerifyError(f"invalid {label} line {number}") from error
        if not isinstance(row, dict):
            raise VerifyError(f"non-object {label} row")
        rows.append(row)
    return rows


def expected_credit(signal: dict[str, float], truth: dict[str, float]) -> float:
    if not signal or set(signal) != set(truth):
        raise VerifyError("signal/truth support mismatch")
    signal_best = max(signal.values())
    selected = [key for key, value in signal.items() if abs(value - signal_best) <= 1e-12]
    truth_best = max(truth.values())
    winners = {key for key, value in truth.items() if abs(value - truth_best) <= 1e-12}
    return sum(key in winners for key in selected) / len(selected)


def bootstrap(rows: list[dict[str, Any]], cluster: str) -> list[float]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row in rows:
        grouped[str(row[cluster])].append(float(row["delta"]))
    keys = sorted(grouped)
    if not keys:
        raise VerifyError("empty bootstrap")
    generator = random.Random(SEED)
    values = []
    for _ in range(BOOTSTRAPS):
        sampled = [generator.choice(keys) for _ in keys]
        flattened = [item for key in sampled for item in grouped[key]]
        values.append(sum(flattened) / len(flattened))
    values.sort()
    return [values[int(0.025 * BOOTSTRAPS)], values[int(0.975 * BOOTSTRAPS)]]


def sign_test(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row in rows:
        grouped[row["run_id"]].append(float(row["delta"]))
    effects = [sum(items) / len(items) for items in grouped.values()]
    positive = sum(value > 1e-12 for value in effects)
    negative = sum(value < -1e-12 for value in effects)
    tied = len(effects) - positive - negative
    informative = positive + negative
    if informative:
        small = min(positive, negative)
        p_value = min(
            1.0,
            2 * sum(math.comb(informative, index) for index in range(small + 1)) / (2 ** informative),
        )
    else:
        p_value = 1.0
    return {
        "positive": positive, "negative": negative, "tied": tied,
        "informative": informative, "exact_p_two_sided": p_value,
    }


def load_selected(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    summary = object_file(root / "summary.json", "selection summary")
    rows_path = root / "selected_parents.jsonl"
    if (
        summary.get("protocol") != "score-channel-parent-selection-v1"
        or digest(rows_path) != valid_sha((summary.get("outputs") or {}).get("selected_parents_sha256"), "selection SHA")
    ):
        raise VerifyError("selection binding mismatch")
    rows = row_file(rows_path, "selection")
    cards: set[str] = set()
    parents: set[tuple[str, str]] = set()
    for row in rows:
        key = (row.get("run_id"), row.get("parent_id"))
        children = row.get("candidate_card_ids")
        if (
            set(row) != SELECTION_KEYS
            or row.get("schema_version") != "score-channel-parent-selection-row-v1"
            or key in parents
            or not isinstance(children, list)
            or children != sorted(set(children))
            or len(children) < 2
            or any(child in cards for child in children)
        ):
            raise VerifyError("invalid selection row")
        parents.add(key)
        cards.update(children)
    return rows, summary


def load_labels(
    intake_root: Path, selected: list[dict[str, Any]], summary: dict[str, Any]
) -> dict[str, float]:
    wanted: dict[str, set[str]] = collections.defaultdict(set)
    identity: dict[str, tuple[str, str]] = {}
    for row in selected:
        for card in row["candidate_card_ids"]:
            wanted[row["source_intake"]].add(card)
            identity[card] = (row["task"], row["run_id"])
    bindings = (summary.get("inputs") or {}).get("intake_summary_sha256")
    if not isinstance(bindings, dict):
        raise VerifyError("missing intake bindings")
    labels: dict[str, float] = {}
    for intake, cards in sorted(wanted.items()):
        root = intake_root / intake
        summary_path = root / "summary.json"
        if digest(summary_path) != valid_sha(bindings.get(intake), "intake SHA"):
            raise VerifyError("intake summary SHA mismatch")
        intake_summary = object_file(summary_path, "intake summary")
        vault = root / "label_vault.jsonl"
        if digest(vault) != valid_sha((intake_summary.get("outputs") or {}).get("label_vault_sha256"), "vault SHA"):
            raise VerifyError("vault SHA mismatch")
        for row in row_file(vault, "vault", allow_empty=True):
            card = row.get("card_id")
            if card not in cards:
                continue
            if (
                set(row) != VAULT_KEYS or card in labels
                or (row.get("task"), row.get("run_id")) != identity[card]
                or row.get("eligible_by_start_time") is not True
                or not finite(row.get("graded")) or not finite(row.get("y_norm"))
            ):
                raise VerifyError("invalid selected label")
            labels[card] = float(row["y_norm"])
    if set(labels) != set(identity):
        raise VerifyError("selected labels incomplete")
    return labels


def load_replay(root: Path, selected_cards: set[str]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    summary_path = root / "summary.json"
    manifest_path = root / "replay_manifest.jsonl"
    summary = object_file(summary_path, "replay summary")
    if (
        summary.get("protocol") != "score-channel-replay-manifest-v1"
        or digest(manifest_path) != valid_sha((summary.get("outputs") or {}).get("replay_manifest_sha256"), "manifest SHA")
    ):
        raise VerifyError("replay binding mismatch")
    manifests = {}
    for row in row_file(manifest_path, "replay manifest"):
        card = row.get("card_id")
        if card in manifests or card not in selected_cards or row.get("cap_seconds") != 120:
            raise VerifyError("invalid replay identity")
        manifests[card] = row
    if set(manifests) != selected_cards:
        raise VerifyError("replay candidates differ from selection")
    return manifests, summary


def load_results(
    paths: list[Path], expected: list[str], manifests: dict[str, dict[str, Any]],
    summary: dict[str, Any], approval_sha: str, approved_worker_commit: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    if len(paths) != 4 or len(expected) != 4:
        raise VerifyError("four result files are required")
    results = {}
    shas = {}
    shard_hashes = (summary.get("outputs") or {}).get("shard_sha256")
    shard_counts = (summary.get("counts") or {}).get("shard_candidate_replays")
    seen_shards = set()
    worker_commits = set()
    for path, expected_sha in zip(paths, expected, strict=True):
        expected_sha = valid_sha(expected_sha, "result SHA")
        if digest(path) != expected_sha:
            raise VerifyError("result SHA mismatch")
        rows = row_file(path, "results")
        file_shards = {row.get("shard_id") for row in rows}
        if len(file_shards) != 1:
            raise VerifyError("mixed result shard")
        shard = next(iter(file_shards))
        if shard in seen_shards or shard not in range(4) or len(rows) != shard_counts.get(str(shard)):
            raise VerifyError("duplicate or incomplete result shard")
        seen_shards.add(shard)
        for row in rows:
            card = row.get("card_id")
            manifest = manifests.get(card)
            if set(row) != RESULT_KEYS or card in results or manifest is None:
                raise VerifyError("result schema or identity mismatch")
            for key in (
                "card_id", "competition", "task", "run_id", "parent", "source_intake",
                "selection_rank_in_run", "shard_id", "cap_seconds", "code_sha256",
            ):
                if row.get(key) != manifest.get(key):
                    raise VerifyError("result/manifest identity mismatch")
            if (
                row.get("manifest_sha256") != shard_hashes.get(str(shard))
                or row.get("approval_sha256") != approval_sha
                or finite(row.get("stdout_val")) != (row.get("val_how") in {"keyed", "bare"})
                or (finite(row.get("sub_score")) and row.get("sub_exists") is not True)
            ):
                raise VerifyError("result signal binding mismatch")
            worker_commits.add(valid_sha(row.get("worker_source_commit"), "worker commit", length=40))
            results[card] = row
        shas[str(shard)] = expected_sha
    if (
        set(results) != set(manifests)
        or seen_shards != set(range(4))
        or worker_commits != {approved_worker_commit}
    ):
        raise VerifyError("results incomplete")
    return results, dict(sorted(shas.items()))


def recompute_rows(
    selected: list[dict[str, Any]], labels: dict[str, float],
    results: dict[str, dict[str, Any]], orientation: dict[str, int],
) -> list[dict[str, Any]]:
    output = []
    for parent in selected:
        common = [
            card for card in parent["candidate_card_ids"]
            if finite(results[card].get("sub_score"))
            and results[card].get("val_how") == "keyed"
            and finite(results[card].get("stdout_val"))
        ]
        if len(common) < 2:
            continue
        direction = orientation[parent["task"]]
        truth = {card: labels[card] for card in common}
        external = {card: direction * float(results[card]["sub_score"]) for card in common}
        stdout = {card: direction * float(results[card]["stdout_val"]) for card in common}
        a = expected_credit(external, truth)
        b = expected_credit(stdout, truth)
        output.append({
            "task": parent["task"], "run_id": parent["run_id"],
            "parent_id": parent["parent_id"],
            "selection_rank_in_run": parent["selection_rank_in_run"],
            "candidate_count": len(parent["candidate_card_ids"]),
            "common_candidate_count": len(common),
            "external_top1_credit": a, "stdout_top1_credit": b, "delta": a - b,
        })
    return output


def recompute_summary(
    rows: list[dict[str, Any]], selected: list[dict[str, Any]], manifests: dict[str, dict[str, Any]],
    results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not rows:
        return {
            "status": "INSUFFICIENT_COMMON_CHANNEL_COVERAGE",
            "method_positive_claim_allowed": False,
            "counts": {
                "selected_parents": len(selected), "planned_replays": len(manifests),
                "common_parents": 0, "common_cards": 0,
            },
        }
    parent_lookup = {(row["run_id"], row["parent_id"]): row for row in selected}
    common_cards = {
        card for row in rows
        for card in parent_lookup[row["run_id"], row["parent_id"]]["candidate_card_ids"]
        if finite(results[card].get("sub_score")) and results[card].get("val_how") == "keyed"
    }
    external = sum(row["external_top1_credit"] for row in rows) / len(rows)
    stdout = sum(row["stdout_top1_credit"] for row in rows) / len(rows)
    delta = external - stdout
    run_ci = bootstrap(rows, "run_id")
    task_ci = bootstrap(rows, "task")
    sign = sign_test(rows)
    tasks = sorted({row["task"] for row in rows})
    per_task = {
        task: {
            "parents": sum(row["task"] == task for row in rows),
            "delta": sum(row["delta"] for row in rows if row["task"] == task)
            / sum(row["task"] == task for row in rows),
        }
        for task in tasks
    }
    loto = {}
    for held in tasks:
        values = [row["delta"] for row in rows if row["task"] != held]
        if values:
            loto[held] = sum(values) / len(values)
    criteria = {
        "direction_positive": delta > 0,
        "run_sign_p_lt_0_05": sign["exact_p_two_sided"] < 0.05,
        "run_clustered_ci_lower_gt_0": run_ci[0] > 0,
        "task_loto_all_gt_neg_0_10": bool(loto) and min(loto.values()) > -0.10,
    }
    if delta <= 0:
        status = "SCORE_CHANNEL_MECHANISM_KILL"
    elif all(criteria.values()):
        status = "SCORE_CHANNEL_MECHANISM_GO"
    else:
        status = "SCORE_CHANNEL_MECHANISM_BORDERLINE"
    return {
        "status": status,
        "method_positive_claim_allowed": status == "SCORE_CHANNEL_MECHANISM_GO",
        "counts": {
            "selected_parents": len(selected), "planned_replays": len(manifests),
            "common_parents": len(rows), "common_cards": len(common_cards),
            "common_runs": len({row["run_id"] for row in rows}),
            "common_tasks": len(tasks),
            "finite_external_cards": sum(finite(row.get("sub_score")) for row in results.values()),
            "keyed_stdout_cards": sum(row.get("val_how") == "keyed" for row in results.values()),
            "both_channels_cards": sum(
                finite(row.get("sub_score")) and row.get("val_how") == "keyed"
                for row in results.values()
            ),
        },
        "headline": {
            "external_top1": external, "stdout_top1": stdout, "delta": delta,
            "run_clustered_ci95": run_ci, "task_clustered_ci95": task_ci,
            "run_sign": sign, "task_loto_delta": dict(sorted(loto.items())),
            "per_task": per_task,
        },
        "criteria": criteria,
    }


def csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    converted = []
    for row in rows:
        converted.append({
            "task": row["task"], "run_id": row["run_id"], "parent_id": row["parent_id"],
            "selection_rank_in_run": int(row["selection_rank_in_run"]),
            "candidate_count": int(row["candidate_count"]),
            "common_candidate_count": int(row["common_candidate_count"]),
            "external_top1_credit": float(row["external_top1_credit"]),
            "stdout_top1_credit": float(row["stdout_top1_credit"]),
            "delta": float(row["delta"]),
        })
    return converted


def verify(args: argparse.Namespace) -> dict[str, Any]:
    primary = object_file(args.analysis_dir / "summary.json", "primary summary")
    if primary.get("protocol") != "score-channel-prospective-analysis-v1":
        raise VerifyError("wrong primary protocol")
    selected, selection_summary = load_selected(args.selection_dir)
    selected_cards = {card for row in selected for card in row["candidate_card_ids"]}
    labels = load_labels(args.intake_root, selected, selection_summary)
    manifests, replay_summary = load_replay(args.replay_dir, selected_cards)

    approval_sha = valid_sha(args.expect_approval_sha256, "approval SHA")
    if digest(args.approval) != approval_sha:
        raise VerifyError("approval SHA mismatch")
    approval = object_file(args.approval, "approval")
    if (
        approval.get("protocol") != "score-channel-replay-approval-v1"
        or approval.get("approved") is not True
        or approval.get("cap_seconds") != 120
        or approval.get("shards") != 4
        or approval.get("gpus_per_shard") != 1
        or approval.get("base_llm_update") is not False
        or approval.get("llm_api_calls") != 0
        or approval.get("online_hf") is not True
        or approval.get("fresh_workspace_per_candidate") is not True
        or approval.get("replay_manifest_sha256") != digest(args.replay_dir / "replay_manifest.jsonl")
        or approval.get("replay_summary_sha256") != digest(args.replay_dir / "summary.json")
    ):
        raise VerifyError("approval binding mismatch")
    approved_worker_commit = valid_sha(
        approval.get("worker_source_commit"), "approved worker commit", length=40
    )

    orientation_sha = valid_sha(args.expect_orientation_sha256, "orientation SHA")
    if digest(args.orientation) != orientation_sha:
        raise VerifyError("orientation SHA mismatch")
    orientation_receipt = object_file(args.orientation, "orientation")
    orientation = orientation_receipt.get("orientation")
    tasks = {row["task"] for row in selected}
    if (
        orientation_receipt.get("protocol") != "score-channel-task-orientation-v1"
        or orientation_receipt.get("outcomes_read") is not False
        or not isinstance(orientation, dict)
        or any(isinstance(orientation.get(task), bool) or orientation.get(task) not in {-1, 1} for task in tasks)
    ):
        raise VerifyError("orientation contract mismatch")
    fixed_orientation = {task: int(orientation[task]) for task in tasks}

    results, result_shas = load_results(
        args.result, args.expect_result_sha256, manifests, replay_summary, approval_sha,
        approved_worker_commit,
    )
    rows = recompute_rows(selected, labels, results, fixed_orientation)
    decision = recompute_summary(rows, selected, manifests, results)
    if csv_rows(args.analysis_dir / "per_set.csv") != rows:
        raise VerifyError("primary per-set CSV differs from independent reconstruction")
    for key in ("status", "method_positive_claim_allowed", "counts", "headline", "criteria"):
        if primary.get(key) != decision.get(key):
            raise VerifyError(f"primary summary differs for {key}")
    expected_inputs = {
        "selection_summary_sha256": digest(args.selection_dir / "summary.json"),
        "selected_parents_sha256": digest(args.selection_dir / "selected_parents.jsonl"),
        "replay_summary_sha256": digest(args.replay_dir / "summary.json"),
        "replay_manifest_sha256": digest(args.replay_dir / "replay_manifest.jsonl"),
        "approval_sha256": approval_sha,
        "orientation_sha256": orientation_sha,
        "result_sha256_by_shard": result_shas,
    }
    if primary.get("inputs") != expected_inputs:
        raise VerifyError("primary input receipt mismatch")
    return {
        "protocol": "score-channel-prospective-analysis-independent-verifier-v1",
        "status": "VERIFIED_SCORE_CHANNEL_PROSPECTIVE_ANALYSIS",
        "primary_summary_sha256": digest(args.analysis_dir / "summary.json"),
        "primary_per_set_sha256": digest(args.analysis_dir / "per_set.csv"),
        "decision": decision,
        "inputs": expected_inputs,
        "producer_imported": False,
    }


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-dir", type=Path, required=True)
    parser.add_argument("--replay-dir", type=Path, required=True)
    parser.add_argument("--intake-root", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--expect-approval-sha256", required=True)
    parser.add_argument("--orientation", type=Path, required=True)
    parser.add_argument("--expect-orientation-sha256", required=True)
    parser.add_argument("--result", type=Path, action="append", required=True)
    parser.add_argument("--expect-result-sha256", action="append", required=True)
    parser.add_argument("--analysis-dir", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if args.receipt.exists():
        print("SCORE_CHANNEL_VERIFY_ERROR: refusing to overwrite receipt", file=os.sys.stderr)
        return 2
    try:
        value = verify(args)
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
            encoding="utf-8", newline="\n",
        )
    except (VerifyError, OSError, ValueError) as error:
        print(f"SCORE_CHANNEL_VERIFY_ERROR: {error}", file=os.sys.stderr)
        return 2
    print(canonical({"status": value["status"], "decision": value["decision"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
