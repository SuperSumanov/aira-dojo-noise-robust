"""Append-only, outcome-blind prediction escrow for parent-relative transition arms."""

from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

from phase1 import critic_static_source_component_oof as static_base
from phase1 import critic_transition_static_component_oof as transition_features
from phase1 import prospective_wl_graph_escrow as blind_snapshot
from phase1 import transition_future_fullfit as fullfit


PROTOCOL = "prospective-transition-future-escrow-v1"
ESCROW_PROTOCOL = "transition-future-escrow-v1"
ACTIVATION_STATUS = "TRANSITION_FUTURE_ESCROW_ACTIVE"
ACTIVATION_VERIFY_STATUS = "INDEPENDENT_TRANSITION_FUTURE_ACTIVATION_VERIFIED"
MODEL_VERIFY_STATUS = "INDEPENDENT_TRANSITION_FUTURE_FULLFIT_VERIFIED"
ARMS = fullfit.ARMS
PAIR_FIELDS = (
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
    *ARMS,
)


class EscrowError(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise EscrowError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(value, dict), f"expected object: {path.name}")
    return value


def locked(path: Path, expected: str) -> Path:
    resolved = path.resolve()
    check(resolved.is_file() and sha256_file(resolved) == expected, f"locked input differs: {path.name}")
    return resolved


def parse_utc(value: str) -> dt.datetime:
    check(isinstance(value, str) and value.endswith("Z"), "UTC timestamp must end in Z")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise EscrowError("invalid UTC timestamp") from error
    check(parsed.tzinfo is not None, "UTC timestamp is naive")
    return parsed.astimezone(dt.timezone.utc)


def verify_chain(args: argparse.Namespace) -> tuple[dict[str, Any], dt.datetime, dict[str, Any]]:
    protocol_path = locked(args.protocol, args.expect_protocol_sha256)
    activation_path = locked(args.activation, args.expect_activation_sha256)
    activation_verification_path = locked(
        args.activation_verification, args.expect_activation_verification_sha256
    )
    model_summary_path = locked(args.model_summary, args.expect_model_summary_sha256)
    model_spec_path = locked(args.model_spec, args.expect_model_spec_sha256)
    train_reference_path = locked(args.train_reference, args.expect_train_reference_sha256)
    model_verification_path = locked(
        args.model_verification, args.expect_model_verification_sha256
    )
    protocol = read_object(protocol_path)
    activation = read_object(activation_path)
    activation_verification = read_object(activation_verification_path)
    model_summary = read_object(model_summary_path)
    model_spec = read_object(model_spec_path)
    model_verification = read_object(model_verification_path)
    check(protocol.get("protocol") == ESCROW_PROTOCOL, "protocol identity differs")
    source_paths = protocol.get("source_paths")
    check(isinstance(source_paths, list) and source_paths, "protocol source paths missing")
    protocol_sha, source_hashes = fullfit.bind_source(
        args.repo_root.resolve(), args.source_commit, protocol_path
    )
    check(protocol_sha == args.expect_protocol_sha256, "protocol source hash differs")
    expected_activation_inputs = {
        "model_spec_sha256": args.expect_model_spec_sha256,
        "model_summary_sha256": args.expect_model_summary_sha256,
        "model_verification_sha256": args.expect_model_verification_sha256,
        "protocol_sha256": args.expect_protocol_sha256,
        "train_reference_sha256": args.expect_train_reference_sha256,
    }
    check(
        activation.get("status") == ACTIVATION_STATUS
        and activation.get("source_commit") == args.source_commit
        and activation.get("source_file_sha256") == source_hashes
        and activation.get("inputs") == expected_activation_inputs,
        "activation chain differs",
    )
    check(
        activation_verification.get("status") == ACTIVATION_VERIFY_STATUS
        and activation_verification.get("activation_sha256") == args.expect_activation_sha256
        and activation_verification.get("source_commit") == args.source_commit
        and activation_verification.get("producer_imported") is False,
        "activation verification differs",
    )
    check(
        model_summary.get("outputs", {}).get("model_spec_sha256")
        == args.expect_model_spec_sha256
        and model_summary.get("outputs", {}).get("train_reference_sha256")
        == args.expect_train_reference_sha256
        and model_verification.get("status") == MODEL_VERIFY_STATUS
        and model_verification.get("producer_summary_sha256")
        == args.expect_model_summary_sha256
        and model_verification.get("producer_imported") is False,
        "model verification chain differs",
    )
    check(
        sha256_file(model_spec_path) == args.expect_model_spec_sha256
        and sha256_file(train_reference_path) == args.expect_train_reference_sha256,
        "model artifacts changed",
    )
    return model_spec, parse_utc(activation["activated_at_utc"]), {
        "activation": activation,
        "model_summary": model_summary,
        "source_hashes": source_hashes,
    }


def verify_refit(
    model_spec: dict[str, Any],
    training_rows: list[dict[str, Any]],
    training_matrices: dict[str, np.ndarray],
    training_receipt: dict[str, Any],
    models: dict[str, Any],
    training_margins: dict[str, np.ndarray],
    fit_receipts: dict[str, Any],
    reference_path: Path,
) -> float:
    expected_spec = {
        "arms": list(ARMS),
        "estimator": {
            "class": "sklearn.ensemble.HistGradientBoostingClassifier",
            **fullfit.MODEL_PARAMETERS,
        },
        "feature_receipt": training_receipt["feature_receipt"],
        "fit_receipts": fit_receipts,
        "format": "deterministic-full-refit-spec-and-reference-v1",
        "orientation": "canonical left-right; positive margin favors left",
        "protocol": fullfit.PROTOCOL,
    }
    check(model_spec == expected_spec, "full refit model specification differs")
    expected_rows = fullfit.reference_rows(training_rows, training_margins)
    with reference_path.open(encoding="utf-8", newline="") as handle:
        observed = list(csv.DictReader(handle))
    check(len(observed) == len(expected_rows), "training reference row count differs")
    maximum = 0.0
    identities = ("pair_id", "task", "parent", "left", "right", "split")
    for actual, expected in zip(observed, expected_rows):
        check(all(actual[field] == expected[field] for field in identities), "training reference identity differs")
        for arm in ARMS:
            difference = abs(float(actual[arm]) - expected[arm])
            maximum = max(maximum, difference)
            check(difference <= 1e-12, f"training reference margin differs: {arm}")
    check(set(models) == set(ARMS) and set(training_matrices) == set(ARMS), "model arm set differs")
    return maximum


def blind_vectors(cards: dict[str, dict[str, Any]], identifiers: set[str]):
    vectors = {}
    sources = {}
    for identifier in sorted(identifiers):
        card = cards[identifier]
        features = static_base.feature_dict(card)
        vector = np.asarray([features[name] for name in static_base.CODE_FEATURES], dtype=np.float64)
        check(np.isfinite(vector).all(), "blind static feature is non-finite")
        vectors[identifier] = vector
        sources[identifier] = card["code"]
    return vectors, sources


def pair_id(task: str, run: str, parent: str, left: str, right: str) -> str:
    return hashlib.sha256("\0".join((task, run, parent, left, right)).encode()).hexdigest()


def score_snapshot(
    cards: dict[str, dict[str, Any]],
    pairs: list[tuple[str, str]],
    activated_at: dt.datetime,
    models: dict[str, Any],
    training_support: dict[str, Any],
):
    covered = []
    pair_metadata = []
    for left, right in pairs:
        left_card = cards[left]
        right_card = cards[right]
        check(
            left < right
            and left_card["task"] == right_card["task"]
            and left_card["run"] == right_card["run"]
            and left_card["parent"] == right_card["parent"],
            "canonical pair grouping differs",
        )
        parent = left_card["parent"]
        parent_present = parent in cards
        if parent_present:
            check(
                cards[parent]["task"] == left_card["task"]
                and cards[parent]["run"] == left_card["run"],
                "parent source task/run differs",
            )
            covered.append(
                {
                    "task": left_card["task"],
                    "parent": parent,
                    "better": left,
                    "worse": right,
                }
            )
        pair_metadata.append((left, right, parent_present))
    covered_ids = {
        identifier
        for row in covered
        for identifier in (row["better"], row["worse"], row["parent"])
    }
    if covered:
        vectors, sources = blind_vectors(cards, covered_ids)
        matrices, matrix_receipt = transition_features.feature_matrices(covered, vectors, sources)
        margins, antisymmetry = fullfit.score_differences(models, matrices)
    else:
        matrix_receipt = {"matrix_shapes": {arm: [0, 0] for arm in ARMS}}
        margins = {arm: np.asarray([], dtype=np.float64) for arm in ARMS}
        antisymmetry = {arm: 0.0 for arm in ARMS}
    covered_index = 0
    output = []
    for left, right, parent_present in pair_metadata:
        left_card = cards[left]
        right_card = cards[right]
        parent = left_card["parent"]
        generation = left_card["generation_started_at_utc"]
        check(generation == right_card["generation_started_at_utc"], "pair generation time differs")
        strict = parse_utc(generation) > activated_at
        identifiers = {left, right, parent}
        endpoint_overlap = bool(identifiers & training_support["support_ids"])
        run_overlap = left_card["run"] in training_support["support_runs"]
        code_values = {left_card["code_sha256"], right_card["code_sha256"]}
        parent_sha = cards[parent]["code_sha256"] if parent_present else None
        if parent_sha is not None:
            code_values.add(parent_sha)
        code_overlap = bool(code_values & training_support["support_code_sha256"])
        source_novel = not endpoint_overlap and not run_overlap and not code_overlap
        if parent_present:
            arm_values = {arm: float(margins[arm][covered_index]) for arm in ARMS}
            covered_index += 1
            finite = all(math.isfinite(value) for value in arm_values.values())
            nontie = all(value != 0.0 for value in arm_values.values())
        else:
            arm_values = {arm: None for arm in ARMS}
            finite = False
            nontie = False
        output.append(
            {
                "pair_id": pair_id(left_card["task"], left_card["run"], parent, left, right),
                "task": left_card["task"],
                "run_id": left_card["run"],
                "parent": parent,
                "left": left,
                "right": right,
                "generation_started_at_utc": generation,
                "temporal_stratum": "strict_future" if strict else "support_only",
                "parent_source_present": parent_present,
                "left_code_sha256": left_card["code_sha256"],
                "right_code_sha256": right_card["code_sha256"],
                "parent_code_sha256": parent_sha,
                "training_endpoint_id_overlap": endpoint_overlap,
                "training_run_id_overlap": run_overlap,
                "training_code_sha_overlap": code_overlap,
                "source_novel": source_novel,
                "finite_all_arms": finite,
                "nontie_all_arms": nontie,
                "strict_effect_eligible": strict and parent_present and source_novel and finite and nontie,
                **arm_values,
            }
        )
    check(covered_index == len(covered), "covered margin accounting differs")
    return output, matrix_receipt, antisymmetry


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            check(tuple(row) == PAIR_FIELDS, "pair output schema/order differs")
            handle.write(json.dumps(row, sort_keys=False, allow_nan=False) + "\n")


def load_prior(path: Path, expected_summary_sha: str):
    root = path.resolve()
    summary_path = root / "summary.json"
    check(sha256_file(summary_path) == expected_summary_sha, "prior summary hash differs")
    summary = read_object(summary_path)
    pairs_path = root / "pairs.jsonl"
    check(sha256_file(pairs_path) == summary.get("outputs", {}).get("pairs_sha256"), "prior pairs hash differs")
    rows = []
    with pairs_path.open(encoding="utf-8") as handle:
        for line in handle:
            value = json.loads(line)
            check(isinstance(value, dict) and tuple(value) == PAIR_FIELDS, "prior pair schema differs")
            rows.append(value)
    return summary, rows


def summarize_support(rows: list[dict[str, Any]]) -> dict[str, Any]:
    strict = [row for row in rows if row["temporal_stratum"] == "strict_future"]
    strict_covered = [row for row in strict if row["parent_source_present"]]
    eligible = [row for row in rows if row["strict_effect_eligible"]]
    task_counts = collections.Counter(row["task"] for row in eligible)
    gates = {
        "dominant_pair_task_share_at_most_0_25": (
            max(task_counts.values()) / len(eligible) <= 0.25 if eligible else False
        ),
        "minimum_150_physical_runs": len({row["run_id"] for row in eligible}) >= 150,
        "minimum_1500_eligible_pairs": len(eligible) >= 1500,
        "minimum_15_tasks": len(task_counts) >= 15,
        "parent_source_coverage_at_least_0_80": (
            len(strict_covered) / len(strict) >= 0.80 if strict else False
        ),
        "strict_training_endpoint_overlap_zero": not any(
            row["training_endpoint_id_overlap"] for row in strict
        ),
        "strict_training_run_overlap_zero": not any(
            row["training_run_id_overlap"] for row in strict
        ),
        "eligible_training_code_overlap_zero_after_exclusion": not any(
            row["training_code_sha_overlap"] for row in eligible
        ),
    }
    return {
        "gates": gates,
        "inventory": {
            "all_pairs": len(rows),
            "eligible_pairs": len(eligible),
            "eligible_runs": len({row["run_id"] for row in eligible}),
            "eligible_tasks": len(task_counts),
            "strict_pairs": len(strict),
            "strict_pairs_with_training_code_overlap": sum(
                row["training_code_sha_overlap"] for row in strict
            ),
            "strict_pairs_with_training_endpoint_overlap": sum(
                row["training_endpoint_id_overlap"] for row in strict
            ),
            "strict_pairs_with_training_run_overlap": sum(
                row["training_run_id_overlap"] for row in strict
            ),
            "strict_pairs_with_parent_source": len(strict_covered),
            "strict_parent_source_coverage": len(strict_covered) / len(strict) if strict else 0.0,
            "support_only_pairs": len(rows) - len(strict),
        },
        "status": (
            "TRANSITION_ESCROW_FUTURE_SUPPORT_READY_OUTCOMES_STILL_LOCKED"
            if all(gates.values())
            else "TRANSITION_ESCROW_INSUFFICIENT_FUTURE_SUPPORT"
        ),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    model_spec, activated_at, chain = verify_chain(args)
    training_rows, training_matrices, training_receipt = fullfit.load_training(
        args.training_cards, args.train_pairs, args.dev_pairs
    )
    models, training_margins, fit_receipts = fullfit.fit_full(training_matrices)
    reference_difference = verify_refit(
        model_spec,
        training_rows,
        training_matrices,
        training_receipt,
        models,
        training_margins,
        fit_receipts,
        args.train_reference,
    )
    cards, pairs, snapshot_metadata = blind_snapshot.load_snapshot(
        args.state_root,
        args.snapshot_root,
        args.expect_snapshot_sha256,
        activated_at,
    )
    rows, future_matrix_receipt, antisymmetry = score_snapshot(
        cards, pairs, activated_at, models, training_receipt
    )
    prior_summary = None
    if args.prior_artifact is not None:
        check(args.expect_prior_summary_sha256 is not None, "prior summary SHA missing")
        prior_summary, prior_rows = load_prior(args.prior_artifact, args.expect_prior_summary_sha256)
        current = {row["pair_id"]: row for row in rows}
        check(len(current) == len(rows), "current pair IDs repeat")
        check(
            all(current.get(row["pair_id"]) == row for row in prior_rows),
            "append-only prior row survival failed",
        )
    support = summarize_support(rows)
    output = args.output.resolve()
    check(not output.exists(), "refusing to overwrite output")
    output.mkdir(parents=True)
    pairs_path = output / "pairs.jsonl"
    write_jsonl(pairs_path, rows)
    summary = {
        "append": {
            "prior_pairs": prior_summary.get("support", {}).get("inventory", {}).get("all_pairs", 0)
            if prior_summary
            else 0,
            "prior_summary_sha256": args.expect_prior_summary_sha256,
            "prior_used": prior_summary is not None,
            "survival_exact": True,
        },
        "inputs": {
            "activation_sha256": args.expect_activation_sha256,
            "activation_verification_sha256": args.expect_activation_verification_sha256,
            "cards_sha256": static_base.EXPECTED["cards"][0],
            "dev_sha256": static_base.EXPECTED["dev"][0],
            "model_spec_sha256": args.expect_model_spec_sha256,
            "model_summary_sha256": args.expect_model_summary_sha256,
            "model_verification_sha256": args.expect_model_verification_sha256,
            "protocol_sha256": args.expect_protocol_sha256,
            "snapshot_sha256": args.expect_snapshot_sha256,
            "train_reference_sha256": args.expect_train_reference_sha256,
            "train_sha256": static_base.EXPECTED["train"][0],
        },
        "model_refit": {
            "fit_receipts": fit_receipts,
            "maximum_training_reference_difference": reference_difference,
        },
        "outputs": {
            "pairs": pairs_path.name,
            "pairs_sha256": sha256_file(pairs_path),
        },
        "protocol": PROTOCOL,
        "scope": {
            "api_calls": 0,
            "base_llm_updates": 0,
            "effect_metrics_computed": [],
            "gpu": 0,
            "prospective_outcomes_read": False,
        },
        "snapshot": snapshot_metadata,
        "source_commit": args.source_commit,
        "source_file_sha256": chain["source_hashes"],
        "status": support["status"],
        "support": support,
        "transition_scoring": {
            "anti_symmetry_max_abs": antisymmetry,
            "future_matrix_receipt": future_matrix_receipt,
            "nontie_required_for_all_three_arms": True,
        },
    }
    summary_path = output / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return summary


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--repo-root", required=True, type=Path)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--protocol", required=True, type=Path)
    value.add_argument("--expect-protocol-sha256", required=True)
    value.add_argument("--activation", required=True, type=Path)
    value.add_argument("--expect-activation-sha256", required=True)
    value.add_argument("--activation-verification", required=True, type=Path)
    value.add_argument("--expect-activation-verification-sha256", required=True)
    value.add_argument("--model-summary", required=True, type=Path)
    value.add_argument("--expect-model-summary-sha256", required=True)
    value.add_argument("--model-spec", required=True, type=Path)
    value.add_argument("--expect-model-spec-sha256", required=True)
    value.add_argument("--train-reference", required=True, type=Path)
    value.add_argument("--expect-train-reference-sha256", required=True)
    value.add_argument("--model-verification", required=True, type=Path)
    value.add_argument("--expect-model-verification-sha256", required=True)
    value.add_argument("--training-cards", required=True, type=Path)
    value.add_argument("--train-pairs", required=True, type=Path)
    value.add_argument("--dev-pairs", required=True, type=Path)
    value.add_argument("--state-root", required=True, type=Path)
    value.add_argument("--snapshot-root", required=True, type=Path)
    value.add_argument("--expect-snapshot-sha256", required=True)
    value.add_argument("--prior-artifact", type=Path)
    value.add_argument("--expect-prior-summary-sha256")
    value.add_argument("--output", required=True, type=Path)
    return value


def main() -> int:
    try:
        summary = run(parser().parse_args())
    except (
        EscrowError,
        fullfit.FullFitError,
        static_base.AuditError,
        blind_snapshot.EscrowError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"PROSPECTIVE_TRANSITION_FUTURE_ESCROW_ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"status": summary["status"], "pairs": summary["support"]["inventory"]["all_pairs"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
