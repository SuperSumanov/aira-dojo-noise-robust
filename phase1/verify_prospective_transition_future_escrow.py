"""Independent full-refit verifier for transition future prediction escrow."""

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
from sklearn.ensemble import HistGradientBoostingClassifier

from phase1 import verify_critic_static_source_component_oof as independent_base
from phase1 import verify_critic_transition_static_component_oof as independent_transition
from phase1 import verify_prospective_wl_graph_escrow as independent_snapshot


PRODUCER_PROTOCOL = "prospective-transition-future-escrow-v1"
ESCROW_PROTOCOL = "transition-future-escrow-v1"
STATUS = "INDEPENDENT_PROSPECTIVE_TRANSITION_FUTURE_ESCROW_VERIFIED"
ARMS = independent_transition.ARMS
MODEL_PARAMETERS = {
    "loss": "log_loss",
    "max_iter": 300,
    "learning_rate": 0.08,
    "max_leaf_nodes": 31,
    "max_depth": None,
    "min_samples_leaf": 20,
    "l2_regularization": 0.0,
    "early_stopping": False,
    "random_state": 7,
}
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


class VerifyError(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise VerifyError(message)


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


def parse_utc(value: Any) -> dt.datetime:
    check(isinstance(value, str) and value.endswith("Z"), "UTC timestamp format differs")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise VerifyError("UTC timestamp invalid") from error
    check(parsed.tzinfo is not None, "UTC timestamp naive")
    return parsed.astimezone(dt.timezone.utc)


def bind_source(repo: Path, commit: str, protocol_path: Path):
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(
        ["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all"],
        text=True,
    ).strip()
    check(head == commit and not dirty, "source commit/clean worktree differs")
    protocol = read_object(protocol_path)
    check(protocol.get("protocol") == ESCROW_PROTOCOL, "protocol identity differs")
    paths = protocol.get("source_paths")
    check(isinstance(paths, list) and paths, "protocol source paths missing")
    hashes = {}
    for relative in paths:
        check(isinstance(relative, str), "non-string source path")
        path = repo / relative
        current = subprocess.check_output(
            ["git", "-C", str(repo), "hash-object", str(path)], text=True
        ).strip()
        committed = subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", f"{commit}:{relative}"], text=True
        ).strip()
        check(current == committed, f"source path differs: {relative}")
        hashes[relative] = sha256_file(path)
    return protocol, dict(sorted(hashes.items()))


def load_training(cards: Path, train: Path, dev: Path):
    for role, path in (("cards", cards), ("train", train), ("dev", dev)):
        independent_base.identify(path, role)
    rows = independent_base.load_rows(train, "train") + independent_base.load_rows(dev, "dev")
    rows.sort(key=independent_base.identity)
    required = {
        identifier
        for row in rows
        for identifier in (row["better"], row["worse"], row["parent"])
    }
    vectors, sources, run_of, task_of, config_of, inventory = (
        independent_transition.cards_with_parent_source(cards, required)
    )
    check(all(task_of[row["parent"]] == row["task"] for row in rows), "training parent task differs")
    _units, integrity = independent_base.parent_closed_units(rows, run_of, task_of, config_of)
    matrices, feature_receipt = independent_transition.independent_matrices(rows, vectors, sources)
    support = {
        "codes": {hashlib.sha256(sources[identifier].encode()).hexdigest() for identifier in required},
        "ids": required,
        "runs": {run_of[identifier] for identifier in required},
    }
    return rows, matrices, support, {
        "card_inventory": inventory,
        "component_integrity": integrity,
        "feature_receipt": feature_receipt,
    }


def refit(matrices: dict[str, np.ndarray]):
    models = {}
    margins = {}
    receipts = {}
    for arm in ARMS:
        values = matrices[arm]
        design = np.vstack((values, -values))
        labels = np.r_[np.ones(len(values), dtype=np.int8), np.zeros(len(values), dtype=np.int8)]
        model = HistGradientBoostingClassifier(**MODEL_PARAMETERS).fit(design, labels)
        check(model.n_iter_ == 300, f"{arm} refit iterations differ")
        direct = model.decision_function(values)
        reverse_direct = model.decision_function(-values)
        forward = np.asarray(0.5 * (direct - reverse_direct), dtype=np.float64)
        reverse = np.asarray(0.5 * (reverse_direct - direct), dtype=np.float64)
        error = float(np.max(np.abs(forward + reverse)))
        check(np.isfinite(forward).all() and error <= 1e-12, f"{arm} training scores differ")
        models[arm] = model
        margins[arm] = forward
        receipts[arm] = {
            "anti_symmetry_max_abs": error,
            "features": int(values.shape[1]),
            "fit_matrix_sha256": independent_base.numeric_hash(values),
            "n_iter": int(model.n_iter_),
            "training_pairs": len(values),
            "training_rows_symmetric": len(design),
        }
    return models, margins, receipts


def verify_model_artifacts(args, feature_receipt, rows, training_margins, fit_receipts):
    model_spec_path = locked(args.model_spec, args.expect_model_spec_sha256)
    reference_path = locked(args.train_reference, args.expect_train_reference_sha256)
    expected_spec = {
        "arms": list(ARMS),
        "estimator": {
            "class": "sklearn.ensemble.HistGradientBoostingClassifier",
            **MODEL_PARAMETERS,
        },
        "feature_receipt": feature_receipt,
        "fit_receipts": fit_receipts,
        "format": "deterministic-full-refit-spec-and-reference-v1",
        "orientation": "canonical left-right; positive margin favors left",
        "protocol": "transition-future-fullfit-v1",
    }
    check(read_object(model_spec_path) == expected_spec, "model specification differs")
    with reference_path.open(encoding="utf-8", newline="") as handle:
        actual = list(csv.DictReader(handle))
    check(len(actual) == len(rows), "training reference length differs")
    maximum = 0.0
    for index, (observed, row) in enumerate(zip(actual, rows)):
        task, parent, left, right = independent_base.identity(row)
        pair_hash = hashlib.sha256("\0".join((task, parent, left, right)).encode()).hexdigest()
        check(
            tuple(observed[field] for field in ("pair_id", "task", "parent", "left", "right", "split"))
            == (pair_hash, task, parent, left, right, row["intask_split"]),
            "training reference identity differs",
        )
        orientation = 1.0 if row["better"] == left else -1.0
        for arm in ARMS:
            difference = abs(float(observed[arm]) - orientation * training_margins[arm][index])
            maximum = max(maximum, difference)
            check(difference <= 1e-12, f"training reference score differs: {arm}")
    return maximum


def endpoint_vectors(cards: dict[str, dict[str, Any]], identifiers: set[str]):
    positions = {name: index for index, name in enumerate(independent_base.FEATURES)}
    code_positions = [positions[name] for name in independent_base.CODE]
    vectors = {}
    sources = {}
    for identifier in sorted(identifiers):
        extracted = independent_base.extract_features(cards[identifier])
        check(tuple(sorted(extracted)) == independent_base.FEATURES, "future feature names differ")
        full = np.asarray([extracted[name] for name in independent_base.FEATURES], dtype=np.float64)
        vectors[identifier] = full[code_positions]
        sources[identifier] = cards[identifier]["code"]
    return vectors, sources


def score_future(cards, pairs, activated_at, models, training_support):
    covered_rows = []
    metadata = []
    for left, right in pairs:
        left_card, right_card = cards[left], cards[right]
        check(
            left < right
            and left_card["task"] == right_card["task"]
            and left_card["run"] == right_card["run"]
            and left_card["parent"] == right_card["parent"],
            "future pair grouping differs",
        )
        parent = left_card["parent"]
        present = parent in cards
        if present:
            check(
                cards[parent]["task"] == left_card["task"]
                and cards[parent]["run"] == left_card["run"],
                "future parent task/run differs",
            )
            covered_rows.append(
                {"task": left_card["task"], "parent": parent, "better": left, "worse": right}
            )
        metadata.append((left, right, present))
    covered_ids = {
        identifier
        for row in covered_rows
        for identifier in (row["better"], row["worse"], row["parent"])
    }
    if covered_rows:
        vectors, sources = endpoint_vectors(cards, covered_ids)
        matrices, matrix_receipt = independent_transition.independent_matrices(
            covered_rows, vectors, sources
        )
        margins = {}
        antisymmetry = {}
        for arm in ARMS:
            direct = models[arm].decision_function(matrices[arm])
            reverse_direct = models[arm].decision_function(-matrices[arm])
            forward = np.asarray(0.5 * (direct - reverse_direct), dtype=np.float64)
            reverse = np.asarray(0.5 * (reverse_direct - direct), dtype=np.float64)
            error = float(np.max(np.abs(forward + reverse)))
            check(np.isfinite(forward).all() and error <= 1e-12, f"future {arm} scoring differs")
            margins[arm] = forward
            antisymmetry[arm] = error
    else:
        matrix_receipt = {"matrix_shapes": {arm: [0, 0] for arm in ARMS}}
        margins = {arm: np.asarray([]) for arm in ARMS}
        antisymmetry = {arm: 0.0 for arm in ARMS}
    output = []
    covered_index = 0
    for left, right, present in metadata:
        left_card, right_card = cards[left], cards[right]
        parent = left_card["parent"]
        generation = left_card["generation_started_at_utc"]
        check(generation == right_card["generation_started_at_utc"], "future pair time differs")
        strict = parse_utc(generation) > activated_at
        endpoint_overlap = bool({left, right, parent} & training_support["ids"])
        run_overlap = left_card["run"] in training_support["runs"]
        code_hashes = {left_card["code_sha256"], right_card["code_sha256"]}
        parent_sha = cards[parent]["code_sha256"] if present else None
        if parent_sha is not None:
            code_hashes.add(parent_sha)
        code_overlap = bool(code_hashes & training_support["codes"])
        source_novel = not endpoint_overlap and not run_overlap and not code_overlap
        if present:
            values = {arm: float(margins[arm][covered_index]) for arm in ARMS}
            covered_index += 1
            finite = all(math.isfinite(value) for value in values.values())
            nontie = all(value != 0.0 for value in values.values())
        else:
            values = {arm: None for arm in ARMS}
            finite = nontie = False
        identity = hashlib.sha256(
            "\0".join((left_card["task"], left_card["run"], parent, left, right)).encode()
        ).hexdigest()
        output.append(
            {
                "pair_id": identity,
                "task": left_card["task"],
                "run_id": left_card["run"],
                "parent": parent,
                "left": left,
                "right": right,
                "generation_started_at_utc": generation,
                "temporal_stratum": "strict_future" if strict else "support_only",
                "parent_source_present": present,
                "left_code_sha256": left_card["code_sha256"],
                "right_code_sha256": right_card["code_sha256"],
                "parent_code_sha256": parent_sha,
                "training_endpoint_id_overlap": endpoint_overlap,
                "training_run_id_overlap": run_overlap,
                "training_code_sha_overlap": code_overlap,
                "source_novel": source_novel,
                "finite_all_arms": finite,
                "nontie_all_arms": nontie,
                "strict_effect_eligible": strict and present and source_novel and finite and nontie,
                **values,
            }
        )
    check(covered_index == len(covered_rows), "future margin accounting differs")
    return output, matrix_receipt, antisymmetry


def support_summary(rows):
    strict = [row for row in rows if row["temporal_stratum"] == "strict_future"]
    covered = [row for row in strict if row["parent_source_present"]]
    eligible = [row for row in rows if row["strict_effect_eligible"]]
    tasks = collections.Counter(row["task"] for row in eligible)
    gates = {
        "dominant_pair_task_share_at_most_0_25": max(tasks.values()) / len(eligible) <= 0.25 if eligible else False,
        "minimum_150_physical_runs": len({row["run_id"] for row in eligible}) >= 150,
        "minimum_1500_eligible_pairs": len(eligible) >= 1500,
        "minimum_15_tasks": len(tasks) >= 15,
        "parent_source_coverage_at_least_0_80": len(covered) / len(strict) >= 0.8 if strict else False,
        "strict_training_endpoint_overlap_zero": not any(row["training_endpoint_id_overlap"] for row in strict),
        "strict_training_run_overlap_zero": not any(row["training_run_id_overlap"] for row in strict),
        "eligible_training_code_overlap_zero_after_exclusion": not any(row["training_code_sha_overlap"] for row in eligible),
    }
    inventory = {
        "all_pairs": len(rows),
        "eligible_pairs": len(eligible),
        "eligible_runs": len({row["run_id"] for row in eligible}),
        "eligible_tasks": len(tasks),
        "strict_pairs": len(strict),
        "strict_pairs_with_training_code_overlap": sum(row["training_code_sha_overlap"] for row in strict),
        "strict_pairs_with_training_endpoint_overlap": sum(row["training_endpoint_id_overlap"] for row in strict),
        "strict_pairs_with_training_run_overlap": sum(row["training_run_id_overlap"] for row in strict),
        "strict_pairs_with_parent_source": len(covered),
        "strict_parent_source_coverage": len(covered) / len(strict) if strict else 0.0,
        "support_only_pairs": len(rows) - len(strict),
    }
    return {
        "gates": gates,
        "inventory": inventory,
        "status": "TRANSITION_ESCROW_FUTURE_SUPPORT_READY_OUTCOMES_STILL_LOCKED" if all(gates.values()) else "TRANSITION_ESCROW_INSUFFICIENT_FUTURE_SUPPORT",
    }


def snapshot_metadata(state_root, snapshot_root, snapshot_sha, cards, pairs, activated_at):
    registry_path = snapshot_root / "intake_registry.jsonl"
    registry = list(independent_snapshot.read_jsonl(registry_path))
    summary_hashes = {}
    manifest_hashes = {}
    for entry in registry:
        intake = Path(entry["intake_dir"])
        summary = independent_snapshot.read_object(intake / "summary.json")
        summary_hashes[entry["drop_id"]] = entry["summary_sha256"]
        manifest_hashes[entry["drop_id"]] = summary["outputs"]["eligible_blind_manifest_sha256"]
    runs_path = snapshot_root / "accumulator" / "provisional_runs.jsonl"
    runs = list(independent_snapshot.read_jsonl(runs_path))
    ordered = sorted(runs, key=lambda row: (row["generation_started_at_utc"], row["source_sha256"], row["run_id"]))
    selected = ordered[:960]
    run_strata = collections.Counter(
        "strict_post_activation_primary" if parse_utc(row["generation_started_at_utc"]) > activated_at else "outcome_unread_support_only"
        for row in selected
    )
    pair_strata = collections.Counter(
        "strict_post_activation_primary" if parse_utc(cards[left]["generation_started_at_utc"]) > activated_at else "outcome_unread_support_only"
        for left, _right in pairs
    )
    accumulator_path = snapshot_root / "accumulator" / "summary.json"
    inventory = independent_snapshot.read_object(accumulator_path)["inventory"]
    checks = {
        "transactions": inventory.get("drops") == len(registry),
        "all_eligible_runs": inventory.get("eligible_runs") == len(runs),
        "all_eligible_endpoints": inventory.get("eligible_endpoints") >= len(cards),
        "provisional_first960_runs": inventory.get("provisional_first960_runs") == len(selected),
        "provisional_first960_endpoints": inventory.get("provisional_first960_endpoints") == len(cards),
        "provisional_first960_pairs": inventory.get("provisional_first960_structural_pairs") == len(pairs),
    }
    check(all(checks.values()), "independent snapshot cross-check differs")
    return {
        "snapshot_sha256": snapshot_sha,
        "intake_registry_sha256": sha256_file(registry_path),
        "provisional_runs_sha256": sha256_file(runs_path),
        "accumulator_summary_sha256": sha256_file(accumulator_path),
        "intake_summary_sha256": dict(sorted(summary_hashes.items())),
        "blind_manifest_sha256": dict(sorted(manifest_hashes.items())),
        "cross_checks_against_accumulator": checks,
        "run_strata": dict(sorted(run_strata.items())),
        "pair_strata": dict(sorted(pair_strata.items())),
    }


def compare_rows(path: Path, expected):
    observed = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            check(isinstance(row, dict) and tuple(row) == PAIR_FIELDS, "producer pair schema differs")
            observed.append(row)
    check(len(observed) == len(expected), "producer pair count differs")
    maximum = 0.0
    for actual, wanted in zip(observed, expected):
        for field in PAIR_FIELDS:
            if field in ARMS and actual[field] is not None:
                difference = abs(float(actual[field]) - float(wanted[field]))
                maximum = max(maximum, difference)
                check(difference <= 1e-12, f"producer future margin differs: {field}")
            else:
                check(actual[field] == wanted[field], f"producer future field differs: {field}")
    return observed, maximum


def verify(args: argparse.Namespace):
    protocol_path = locked(args.protocol, args.expect_protocol_sha256)
    protocol, source_hashes = bind_source(args.repo_root.resolve(), args.source_commit, protocol_path)
    activation_path = locked(args.activation, args.expect_activation_sha256)
    activation_verify_path = locked(args.activation_verification, args.expect_activation_verification_sha256)
    model_summary_path = locked(args.model_summary, args.expect_model_summary_sha256)
    model_verify_path = locked(args.model_verification, args.expect_model_verification_sha256)
    activation = read_object(activation_path)
    activation_verification = read_object(activation_verify_path)
    model_summary = read_object(model_summary_path)
    model_verification = read_object(model_verify_path)
    check(
        activation.get("status") == "TRANSITION_FUTURE_ESCROW_ACTIVE"
        and activation.get("source_commit") == args.source_commit
        and activation.get("source_file_sha256") == source_hashes
        and activation_verification.get("status") == "INDEPENDENT_TRANSITION_FUTURE_ACTIVATION_VERIFIED"
        and activation_verification.get("activation_sha256") == args.expect_activation_sha256
        and model_verification.get("status") == "INDEPENDENT_TRANSITION_FUTURE_FULLFIT_VERIFIED"
        and model_verification.get("producer_summary_sha256") == args.expect_model_summary_sha256,
        "activation/model chain differs",
    )
    expected_activation_inputs = {
        "model_spec_sha256": args.expect_model_spec_sha256,
        "model_summary_sha256": args.expect_model_summary_sha256,
        "model_verification_sha256": args.expect_model_verification_sha256,
        "protocol_sha256": args.expect_protocol_sha256,
        "train_reference_sha256": args.expect_train_reference_sha256,
    }
    check(activation.get("inputs") == expected_activation_inputs, "activation input hashes differ")
    training_rows, training_matrices, training_support, training_receipt = load_training(
        args.training_cards, args.train_pairs, args.dev_pairs
    )
    models, training_margins, fit_receipts = refit(training_matrices)
    reference_difference = verify_model_artifacts(
        args,
        training_receipt["feature_receipt"],
        training_rows,
        training_margins,
        fit_receipts,
    )
    activated_at = parse_utc(activation["activated_at_utc"])
    cards, pairs = independent_snapshot.load_cohort(
        args.state_root, args.snapshot_root, args.expect_snapshot_sha256
    )
    expected_rows, future_matrix, antisymmetry = score_future(
        cards, pairs, activated_at, models, training_support
    )
    artifact = args.artifact.resolve()
    summary_path = artifact / "summary.json"
    pairs_path = artifact / "pairs.jsonl"
    summary = read_object(summary_path)
    observed_rows, maximum_future = compare_rows(pairs_path, expected_rows)
    support = support_summary(expected_rows)
    metadata = snapshot_metadata(
        args.state_root.resolve(),
        args.snapshot_root.resolve(),
        args.expect_snapshot_sha256,
        cards,
        pairs,
        activated_at,
    )
    if args.prior_artifact is None:
        append = {"prior_pairs": 0, "prior_summary_sha256": None, "prior_used": False, "survival_exact": True}
    else:
        check(args.expect_prior_summary_sha256 is not None, "prior summary SHA missing")
        prior_summary_path = args.prior_artifact / "summary.json"
        check(sha256_file(prior_summary_path) == args.expect_prior_summary_sha256, "prior summary differs")
        prior_summary = read_object(prior_summary_path)
        prior_pairs_path = args.prior_artifact / "pairs.jsonl"
        check(sha256_file(prior_pairs_path) == prior_summary["outputs"]["pairs_sha256"], "prior pair hash differs")
        current = {row["pair_id"]: row for row in observed_rows}
        prior_count = 0
        with prior_pairs_path.open(encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                check(current.get(row["pair_id"]) == row, "prior row survival differs")
                prior_count += 1
        append = {"prior_pairs": prior_count, "prior_summary_sha256": args.expect_prior_summary_sha256, "prior_used": True, "survival_exact": True}
    expected_inputs = {
        "activation_sha256": args.expect_activation_sha256,
        "activation_verification_sha256": args.expect_activation_verification_sha256,
        "cards_sha256": independent_base.EXPECTED["cards"][0],
        "dev_sha256": independent_base.EXPECTED["dev"][0],
        "model_spec_sha256": args.expect_model_spec_sha256,
        "model_summary_sha256": args.expect_model_summary_sha256,
        "model_verification_sha256": args.expect_model_verification_sha256,
        "protocol_sha256": args.expect_protocol_sha256,
        "snapshot_sha256": args.expect_snapshot_sha256,
        "train_reference_sha256": args.expect_train_reference_sha256,
        "train_sha256": independent_base.EXPECTED["train"][0],
    }
    expected_static = {
        "append": append,
        "inputs": expected_inputs,
        "model_refit": {"fit_receipts": fit_receipts, "maximum_training_reference_difference": reference_difference},
        "outputs": {"pairs": "pairs.jsonl", "pairs_sha256": sha256_file(pairs_path)},
        "protocol": PRODUCER_PROTOCOL,
        "scope": {"api_calls": 0, "base_llm_updates": 0, "effect_metrics_computed": [], "gpu": 0, "prospective_outcomes_read": False},
        "snapshot": metadata,
        "source_commit": args.source_commit,
        "source_file_sha256": source_hashes,
        "status": support["status"],
        "support": support,
        "transition_scoring": {"anti_symmetry_max_abs": antisymmetry, "future_matrix_receipt": future_matrix, "nontie_required_for_all_three_arms": True},
    }
    check(summary == expected_static, "producer summary differs from independent reconstruction")
    return {
        "all_summary_fields_exact": True,
        "artifact_summary_sha256": sha256_file(summary_path),
        "maximum_future_margin_difference": maximum_future,
        "maximum_training_reference_difference": reference_difference,
        "pairs": len(expected_rows),
        "producer_imported": False,
        "protocol": "prospective-transition-future-independent-verifier-v1",
        "source_commit": args.source_commit,
        "status": STATUS,
        "support_status": support["status"],
        "scope": {"effect_metrics_computed": [], "prospective_outcomes_read": False, "gpu": 0, "api_calls": 0},
    }


def parser():
    value = argparse.ArgumentParser(description=__doc__)
    for name in (
        "protocol", "activation", "activation_verification", "model_summary", "model_spec",
        "train_reference", "model_verification",
    ):
        value.add_argument(f"--{name.replace('_', '-')}", required=True, type=Path)
        value.add_argument(f"--expect-{name.replace('_', '-')}-sha256", required=True)
    value.add_argument("--repo-root", required=True, type=Path)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--training-cards", required=True, type=Path)
    value.add_argument("--train-pairs", required=True, type=Path)
    value.add_argument("--dev-pairs", required=True, type=Path)
    value.add_argument("--state-root", required=True, type=Path)
    value.add_argument("--snapshot-root", required=True, type=Path)
    value.add_argument("--expect-snapshot-sha256", required=True)
    value.add_argument("--prior-artifact", type=Path)
    value.add_argument("--expect-prior-summary-sha256")
    value.add_argument("--artifact", required=True, type=Path)
    value.add_argument("--output", required=True, type=Path)
    return value


def main():
    args = parser().parse_args()
    if args.output.exists():
        print("PROSPECTIVE_TRANSITION_FUTURE_VERIFY_ERROR: output exists", file=sys.stderr)
        return 2
    try:
        receipt = verify(args)
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n")
    except (
        VerifyError,
        independent_base.VerificationError,
        independent_transition.TransitionVerificationError,
        independent_snapshot.VerifyError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"PROSPECTIVE_TRANSITION_FUTURE_VERIFY_ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"status": STATUS, "pairs": receipt["pairs"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
