#!/usr/bin/env python3
"""Verify outcome-blind prediction escrows across provisional first-960 churn.

The source registry is append-only, but the chronological first-960 prefix is
not: a late-uploaded run with an earlier generation timestamp can enter the
prefix and displace its previous tail.  This verifier therefore binds every
artifact to its immutable snapshot, checks exact predictions on the cohort
intersection, and requires every support addition/removal to be explained by
the frozen chronological ordering rule.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable

from phase1 import verify_wl_graph_escrow_append as wl_append


PROTOCOL = "provisional-first960-snapshot-chain-v1"
STATUS = "PROVISIONAL_FIRST960_SNAPSHOT_CHAIN_INDEPENDENTLY_VERIFIED"
COHORT_RUN_TARGET = 960
RUN_FIELDS = {
    "run_id",
    "task",
    "drop_id",
    "flow_status",
    "endpoints",
    "generation_started_at_utc",
    "source_sha256",
}
TRANSITION_ARMS = ("child_code", "transition_only", "child_plus_transition")
TRANSITION_PAIR_FIELDS = {
    "pair_id",
    "task",
    "run_id",
    "parent",
    "left",
    "right",
    "generation_started_at_utc",
    "temporal_stratum",
    "parent_source_present",
    "left_code_sha256",
    "right_code_sha256",
    "parent_code_sha256",
    "training_endpoint_id_overlap",
    "training_run_id_overlap",
    "training_code_sha_overlap",
    "source_novel",
    "finite_all_arms",
    "nontie_all_arms",
    "strict_effect_eligible",
    *TRANSITION_ARMS,
}
TRANSITION_FIXED_INPUTS = {
    "activation_sha256",
    "activation_verification_sha256",
    "cards_sha256",
    "dev_sha256",
    "model_spec_sha256",
    "model_summary_sha256",
    "model_verification_sha256",
    "protocol_sha256",
    "train_reference_sha256",
    "train_sha256",
}
SHA_RE = re.compile(r"[0-9a-f]{64}")


class SnapshotChainError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SnapshotChainError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"expected JSON object: {path.name}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank JSONL row: {path.name}:{line_number}")
            row = json.loads(line)
            require(isinstance(row, dict), f"non-object JSONL row: {path.name}:{line_number}")
            rows.append(row)
    return rows


def _valid_sha(value: Any) -> bool:
    return isinstance(value, str) and SHA_RE.fullmatch(value) is not None


def _run_order(row: dict[str, Any]) -> tuple[str, str, str]:
    return row["generation_started_at_utc"], row["source_sha256"], row["run_id"]


def _subsequence(needle: Iterable[str], haystack: Iterable[str]) -> bool:
    iterator = iter(haystack)
    return all(any(candidate == wanted for candidate in iterator) for wanted in needle)


def load_snapshot(root: Path, expected_sha: str) -> dict[str, Any]:
    require(_valid_sha(expected_sha), "invalid expected snapshot SHA")
    root = root.resolve()
    summary_path = root / "accumulator" / "summary.json"
    all_path = root / "accumulator" / "provisional_runs.jsonl"
    selected_path = root / "accumulator" / "provisional_first960_runs.jsonl"
    summary = read_object(summary_path)
    all_rows = read_jsonl(all_path)
    selected = read_jsonl(selected_path)
    for row in (*all_rows, *selected):
        require(set(row) == RUN_FIELDS, "provisional run schema mismatch")
        require(
            isinstance(row["run_id"], str)
            and row["run_id"]
            and row["flow_status"] == "scoreable"
            and isinstance(row["endpoints"], int)
            and row["endpoints"] > 0
            and _valid_sha(row["source_sha256"]),
            "invalid provisional run row",
        )
    all_ids = [row["run_id"] for row in all_rows]
    selected_ids = [row["run_id"] for row in selected]
    require(len(set(all_ids)) == len(all_ids), "duplicate all-run identity")
    require(len(set(selected_ids)) == len(selected_ids), "duplicate selected-run identity")
    require(all_rows == sorted(all_rows, key=_run_order), "all-run order differs from frozen rule")
    require(selected == all_rows[:COHORT_RUN_TARGET], "first-960 file is not the exact prefix")
    inventory = summary.get("inventory", {})
    outputs = summary.get("outputs", {})
    security = summary.get("security", {})
    require(inventory.get("eligible_runs") == len(all_rows), "eligible-run inventory mismatch")
    require(
        inventory.get("provisional_first960_runs") == len(selected),
        "first-960 run inventory mismatch",
    )
    require(outputs.get("provisional_runs_sha256") == sha256_file(all_path), "all-run hash mismatch")
    require(
        outputs.get("provisional_first960_runs_sha256") == sha256_file(selected_path),
        "first-960 hash mismatch",
    )
    require(
        security.get("label_vault_opened") is False
        and security.get("outcome_files_opened") == []
        and security.get("scorer_prediction_files_opened") == [],
        "snapshot blindness scope mismatch",
    )
    return {
        "root": str(root),
        "snapshot_sha256": expected_sha,
        "summary": summary,
        "summary_sha256": sha256_file(summary_path),
        "all": all_rows,
        "selected": selected,
    }


def _load_wl_artifact(root: Path, expected_summary_sha: str) -> dict[str, Any]:
    require(_valid_sha(expected_summary_sha), "invalid WL summary SHA")
    require(
        sha256_file(root / "summary.json") == expected_summary_sha,
        "WL artifact summary hash mismatch",
    )
    try:
        summary, endpoints, pairs = wl_append._load_artifact(root)
    except wl_append.AppendVerificationError as error:
        raise SnapshotChainError(str(error)) from error
    return {"summary": summary, "endpoints": endpoints, "pairs": pairs}


def _transition_pair_id(row: dict[str, Any]) -> str:
    fields = (row["task"], row["run_id"], row["parent"], row["left"], row["right"])
    return hashlib.sha256("\0".join(fields).encode()).hexdigest()


def _load_transition_artifact(root: Path, expected_summary_sha: str) -> dict[str, Any]:
    require(_valid_sha(expected_summary_sha), "invalid transition summary SHA")
    summary_path = root / "summary.json"
    require(sha256_file(summary_path) == expected_summary_sha, "transition summary hash mismatch")
    summary = read_object(summary_path)
    pairs_path = root / "pairs.jsonl"
    require(
        summary.get("outputs")
        == {"pairs": "pairs.jsonl", "pairs_sha256": sha256_file(pairs_path)},
        "transition output binding mismatch",
    )
    rows: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(pairs_path):
        require(set(row) == TRANSITION_PAIR_FIELDS, "transition pair schema mismatch")
        key = row.get("pair_id")
        require(_valid_sha(key) and key == _transition_pair_id(row) and key not in rows, "invalid transition pair identity")
        require(
            row.get("temporal_stratum") in {"support_only", "strict_future"}
            and isinstance(row.get("run_id"), str)
            and row.get("left") < row.get("right"),
            "invalid transition pair metadata",
        )
        for arm in TRANSITION_ARMS:
            value = row[arm]
            require(value is None or (isinstance(value, (int, float)) and math.isfinite(value)), "invalid transition margin")
        rows[key] = row
    scope = summary.get("scope", {})
    require(
        summary.get("protocol") == "prospective-transition-future-escrow-v1"
        and scope.get("prospective_outcomes_read") is False
        and scope.get("effect_metrics_computed") == []
        and scope.get("gpu") == 0
        and scope.get("api_calls") == 0
        and scope.get("base_llm_updates") == 0,
        "transition blindness/resource scope mismatch",
    )
    require(
        summary.get("support", {}).get("inventory", {}).get("all_pairs") == len(rows),
        "transition pair inventory mismatch",
    )
    return {"summary": summary, "endpoints": {}, "pairs": rows}


def load_artifact(family: str, root: Path, expected_summary_sha: str) -> dict[str, Any]:
    if family == "wl_graph":
        return _load_wl_artifact(root.resolve(), expected_summary_sha)
    if family == "transition":
        return _load_transition_artifact(root.resolve(), expected_summary_sha)
    raise SnapshotChainError("unknown escrow family")


def verify_frozen_identity(family: str, prior: dict[str, Any], current: dict[str, Any]) -> None:
    left, right = prior["summary"], current["summary"]
    require(left.get("source_commit") == right.get("source_commit"), "scorer commit changed")
    require(left.get("source_file_sha256") == right.get("source_file_sha256"), "scorer source changed")
    if family == "wl_graph":
        require(left.get("activation") == right.get("activation"), "WL activation changed")
        for key in wl_append.FIXED_INPUT_KEYS:
            require(left.get("inputs", {}).get(key) == right.get("inputs", {}).get(key), f"WL fixed input changed: {key}")
    else:
        prior_inputs = left.get("inputs", {})
        current_inputs = right.get("inputs", {})
        require(set(prior_inputs) == TRANSITION_FIXED_INPUTS | {"snapshot_sha256"}, "prior transition input schema mismatch")
        require(set(current_inputs) == TRANSITION_FIXED_INPUTS | {"snapshot_sha256"}, "current transition input schema mismatch")
        for key in TRANSITION_FIXED_INPUTS:
            require(prior_inputs[key] == current_inputs[key], f"transition fixed input changed: {key}")
        require(left.get("model_refit") == right.get("model_refit"), "transition model refit identity changed")


def verify_independent_receipt(
    family: str,
    receipt_path: Path,
    current_summary_sha: str,
    current_snapshot_sha: str,
    current: dict[str, Any],
) -> dict[str, Any]:
    receipt = read_object(receipt_path)
    require(receipt.get("artifact_summary_sha256") == current_summary_sha, "independent receipt summary binding mismatch")
    require(receipt.get("effect_metrics_computed", receipt.get("scope", {}).get("effect_metrics_computed")) == [], "independent receipt contains effect metrics")
    if family == "wl_graph":
        require(
            receipt.get("status") == "INDEPENDENT_PROSPECTIVE_WL_GRAPH_ESCROW_VERIFIED"
            and receipt.get("snapshot_sha256") == current_snapshot_sha
            and receipt.get("endpoints") == len(current["endpoints"])
            and receipt.get("pairs") == len(current["pairs"])
            and receipt.get("prospective_outcomes_read") is False,
            "WL independent receipt mismatch",
        )
        differences = receipt.get("maximum_absolute_score_difference", {})
        require(set(differences) == set(wl_append.ARMS), "WL independent arm set mismatch")
        require(
            all(
                isinstance(value, (int, float)) and 0.0 <= value <= 1e-12
                for value in differences.values()
            ),
            "WL independent numerical mismatch",
        )
    else:
        scope = receipt.get("scope", {})
        require(
            receipt.get("status") == "INDEPENDENT_PROSPECTIVE_TRANSITION_FUTURE_ESCROW_VERIFIED"
            and receipt.get("pairs") == len(current["pairs"])
            and scope.get("prospective_outcomes_read") is False
            and scope.get("effect_metrics_computed") == []
            and 0.0 <= receipt.get("maximum_future_margin_difference", 1.0) <= 1e-12
            and 0.0 <= receipt.get("maximum_training_reference_difference", 1.0) <= 1e-12,
            "transition independent receipt mismatch",
        )
    return {"path_sha256": sha256_file(receipt_path), "status": receipt["status"]}


def _rows_by_run(rows: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for key, row in rows.items():
        result.setdefault(row["run_id"], set()).add(key)
    return result


def verify(args: argparse.Namespace) -> dict[str, Any]:
    prior_snapshot = load_snapshot(args.prior_snapshot_root, args.expect_prior_snapshot_sha256)
    current_snapshot = load_snapshot(args.current_snapshot_root, args.expect_current_snapshot_sha256)
    require(
        args.expect_prior_snapshot_sha256 != args.expect_current_snapshot_sha256,
        "snapshot did not advance",
    )
    prior = load_artifact(args.family, args.prior_artifact, args.expect_prior_summary_sha256)
    current = load_artifact(args.family, args.current_artifact, args.expect_current_summary_sha256)
    require(
        prior["summary"].get("inputs", {}).get("snapshot_sha256") == args.expect_prior_snapshot_sha256,
        "prior artifact snapshot binding mismatch",
    )
    require(
        current["summary"].get("inputs", {}).get("snapshot_sha256") == args.expect_current_snapshot_sha256,
        "current artifact snapshot binding mismatch",
    )
    verify_frozen_identity(args.family, prior, current)

    prior_all = {row["run_id"]: row for row in prior_snapshot["all"]}
    current_all = {row["run_id"]: row for row in current_snapshot["all"]}
    require(set(prior_all) <= set(current_all), "prior physical run disappeared")
    require(all(current_all[key] == row for key, row in prior_all.items()), "prior physical run row changed")
    require(
        _subsequence(prior_all, current_all),
        "prior chronological run sequence is not a subsequence",
    )

    prior_selected = [row["run_id"] for row in prior_snapshot["selected"]]
    current_selected = [row["run_id"] for row in current_snapshot["selected"]]
    prior_selected_set = set(prior_selected)
    current_selected_set = set(current_selected)
    added_runs = current_selected_set - prior_selected_set
    removed_runs = prior_selected_set - current_selected_set
    unchanged_runs = prior_selected_set & current_selected_set
    require(
        not removed_runs or len(current_snapshot["all"]) > COHORT_RUN_TARGET,
        "cohort removal before target is reached",
    )
    current_rank = {run_id: index for index, run_id in enumerate(current_all)}
    require(
        all(current_rank[run_id] >= COHORT_RUN_TARGET for run_id in removed_runs),
        "removed run remains inside current chronological prefix",
    )
    require(
        all(current_rank[run_id] < COHORT_RUN_TARGET for run_id in added_runs),
        "added run is outside current chronological prefix",
    )

    for kind in ("endpoints", "pairs"):
        prior_rows = prior[kind]
        current_rows = current[kind]
        common = set(prior_rows) & set(current_rows)
        require(
            all(prior_rows[key] == current_rows[key] for key in common),
            f"shared {kind} prediction row changed",
        )
        require(
            all(prior_rows[key]["run_id"] in removed_runs for key in set(prior_rows) - set(current_rows)),
            f"prior-only {kind} row is not explained by displaced runs",
        )
        require(
            all(current_rows[key]["run_id"] in added_runs for key in set(current_rows) - set(prior_rows)),
            f"current-only {kind} row is not explained by entering runs",
        )

    if args.family == "wl_graph":
        require(
            {row["run_id"] for row in prior["endpoints"].values()} == prior_selected_set,
            "prior WL endpoint support differs from selected cohort",
        )
        require(
            {row["run_id"] for row in current["endpoints"].values()} == current_selected_set,
            "current WL endpoint support differs from selected cohort",
        )
    else:
        require(
            {row["run_id"] for row in prior["pairs"].values()} <= prior_selected_set
            and {row["run_id"] for row in current["pairs"].values()} <= current_selected_set,
            "transition pair support falls outside selected cohort",
        )
        if removed_runs:
            require(
                current["summary"].get("append", {}).get("prior_used") is False,
                "transition churn artifact must be independently rebuilt without legacy prior-survival gate",
            )

    independent = verify_independent_receipt(
        args.family,
        args.current_independent_verification,
        args.expect_current_summary_sha256,
        args.expect_current_snapshot_sha256,
        current,
    )
    closure = current_snapshot["summary"].get("closure", {})
    closure_final = (
        closure.get("provided") is True
        and closure.get("all_scheduled_runs_uploaded") is True
        and closure.get("outcomes_read") is False
        and len(current_selected) == COHORT_RUN_TARGET
    )
    return {
        "protocol": PROTOCOL,
        "status": STATUS,
        "family": args.family,
        "snapshots": {
            "prior": {
                "sha256": args.expect_prior_snapshot_sha256,
                "accumulator_summary_sha256": prior_snapshot["summary_sha256"],
                "all_runs": len(prior_snapshot["all"]),
                "selected_runs": len(prior_selected),
            },
            "current": {
                "sha256": args.expect_current_snapshot_sha256,
                "accumulator_summary_sha256": current_snapshot["summary_sha256"],
                "all_runs": len(current_snapshot["all"]),
                "selected_runs": len(current_selected),
            },
        },
        "source_append_invariants": {
            "prior_run_set_contained": True,
            "prior_run_rows_exact": True,
            "prior_run_sequence_subsequence": True,
            "byte_prefix_required": False,
        },
        "cohort_churn": {
            "target_runs": COHORT_RUN_TARGET,
            "unchanged_runs": len(unchanged_runs),
            "added_runs": len(added_runs),
            "removed_runs": len(removed_runs),
            "added_run_ids_sha256": hashlib.sha256("\n".join(sorted(added_runs)).encode()).hexdigest(),
            "removed_run_ids_sha256": hashlib.sha256("\n".join(sorted(removed_runs)).encode()).hexdigest(),
            "all_changes_explained_by_frozen_order": True,
        },
        "prediction_intersection": {
            kind: {
                "prior": len(prior[kind]),
                "current": len(current[kind]),
                "common": len(set(prior[kind]) & set(current[kind])),
                "prior_only": len(set(prior[kind]) - set(current[kind])),
                "current_only": len(set(current[kind]) - set(prior[kind])),
                "common_rows_exact": True,
            }
            for kind in ("endpoints", "pairs")
        },
        "independent_current_verification": independent,
        "closure": {
            "final_first960_identity": closure_final,
            "support_gate_is_provisional_until_closure": not closure_final,
        },
        "scope": {
            "prospective_outcomes_read": False,
            "effect_metrics_computed": [],
            "prediction_values_printed": False,
            "gpu": 0,
            "api_calls": 0,
            "base_llm_updates": 0,
        },
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--family", required=True, choices=("wl_graph", "transition"))
    value.add_argument("--prior-snapshot-root", required=True, type=Path)
    value.add_argument("--current-snapshot-root", required=True, type=Path)
    value.add_argument("--expect-prior-snapshot-sha256", required=True)
    value.add_argument("--expect-current-snapshot-sha256", required=True)
    value.add_argument("--prior-artifact", required=True, type=Path)
    value.add_argument("--current-artifact", required=True, type=Path)
    value.add_argument("--expect-prior-summary-sha256", required=True)
    value.add_argument("--expect-current-summary-sha256", required=True)
    value.add_argument("--current-independent-verification", required=True, type=Path)
    value.add_argument("--output", required=True, type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    if args.output.exists():
        print("PROVISIONAL_FIRST960_CHAIN_ERROR: output exists", file=sys.stderr)
        return 2
    temporary = args.output.with_name(f"{args.output.name}.tmp.{os.getpid()}")
    if temporary.exists():
        print("PROVISIONAL_FIRST960_CHAIN_ERROR: temporary output exists", file=sys.stderr)
        return 2
    try:
        receipt = verify(args)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(
            json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, args.output)
    except (SnapshotChainError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"PROVISIONAL_FIRST960_CHAIN_ERROR: {error}", file=sys.stderr)
        return 2
    print(
        STATUS,
        f"family={receipt['family']}",
        f"added_runs={receipt['cohort_churn']['added_runs']}",
        f"removed_runs={receipt['cohort_churn']['removed_runs']}",
        "outcomes_read=false",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
