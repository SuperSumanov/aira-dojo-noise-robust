"""Independent refit verifier for the frozen transition future model receipt."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

from phase1 import verify_critic_static_source_component_oof as independent_base
from phase1 import verify_critic_transition_static_component_oof as independent_transition


PRODUCER_PROTOCOL = "transition-future-fullfit-v1"
ESCROW_PROTOCOL = "transition-future-escrow-v1"
VERIFY_PROTOCOL = "transition-future-fullfit-independent-verifier-v1"
PRODUCER_STATUS = "TRANSITION_FUTURE_FULLFIT_COMPLETE_PENDING_INDEPENDENT_VERIFICATION"
STATUS = "INDEPENDENT_TRANSITION_FUTURE_FULLFIT_VERIFIED"
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
    check(isinstance(value, dict), f"expected JSON object: {path.name}")
    return value


def bind_source(repo: Path, commit: str, protocol_path: Path) -> tuple[str, dict[str, str]]:
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    check(head == commit, "source commit mismatch")
    protocol = read_object(protocol_path)
    check(protocol.get("protocol") == ESCROW_PROTOCOL, "escrow protocol identity mismatch")
    paths = protocol.get("source_paths")
    check(isinstance(paths, list) and paths, "escrow source paths missing")
    hashes = {}
    for relative in paths:
        check(isinstance(relative, str), "non-string source path")
        path = repo / relative
        check(path.is_file(), f"bound source missing: {relative}")
        actual_blob = subprocess.check_output(
            ["git", "-C", str(repo), "hash-object", str(path)], text=True
        ).strip()
        expected_blob = subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", f"{commit}:{relative}"], text=True
        ).strip()
        check(actual_blob == expected_blob, f"bound source differs from commit: {relative}")
        hashes[relative] = sha256_file(path)
    return sha256_file(protocol_path), dict(sorted(hashes.items()))


def load_training(cards: Path, train: Path, dev: Path):
    for role, path in (("cards", cards), ("train", train), ("dev", dev)):
        independent_base.identify(path, role)
    rows = independent_base.load_rows(train, "train") + independent_base.load_rows(dev, "dev")
    rows.sort(key=independent_base.identity)
    check(len(rows) == independent_base.EXPECTED_COUNTS["pairs"], "training pair count differs")
    required = {
        identifier
        for row in rows
        for identifier in (row["better"], row["worse"], row["parent"])
    }
    vectors, sources, run_of, task_of, config_of, inventory = (
        independent_transition.cards_with_parent_source(cards, required)
    )
    check(
        all(task_of[row["parent"]] == row["task"] for row in rows),
        "independent parent task differs from pair task",
    )
    _units, integrity = independent_base.parent_closed_units(
        rows, run_of, task_of, config_of
    )
    matrices, feature_receipt = independent_transition.independent_matrices(
        rows, vectors, sources
    )
    return rows, matrices, {
        "card_inventory": inventory,
        "component_integrity": integrity,
        "feature_receipt": feature_receipt,
        "needed_cards": len(required),
    }


def refit(matrices: dict[str, np.ndarray]):
    margins = {}
    receipts = {}
    for arm in ARMS:
        values = matrices[arm]
        design = np.vstack((values, -values))
        targets = np.r_[
            np.ones(len(values), dtype=np.int8),
            np.zeros(len(values), dtype=np.int8),
        ]
        estimator = HistGradientBoostingClassifier(**MODEL_PARAMETERS)
        estimator.fit(design, targets)
        check(estimator.n_iter_ == 300, f"{arm} independent iteration count differs")
        direct = estimator.decision_function(values)
        reversed_direct = estimator.decision_function(-values)
        forward = np.asarray(0.5 * (direct - reversed_direct), dtype=np.float64)
        reverse = np.asarray(0.5 * (reversed_direct - direct), dtype=np.float64)
        error = float(np.max(np.abs(forward + reverse)))
        check(np.isfinite(forward).all() and error <= 1e-12, f"{arm} independent scoring failed")
        margins[arm] = forward
        receipts[arm] = {
            "anti_symmetry_max_abs": error,
            "features": int(values.shape[1]),
            "fit_matrix_sha256": independent_base.numeric_hash(values),
            "n_iter": int(estimator.n_iter_),
            "training_pairs": len(values),
            "training_rows_symmetric": len(design),
        }
    return margins, receipts


def expected_reference(rows: list[dict[str, Any]], margins: dict[str, np.ndarray]):
    output = []
    for index, row in enumerate(rows):
        task, parent, left, right = independent_base.identity(row)
        orientation = 1.0 if row["better"] == left else -1.0
        pair_id = hashlib.sha256("\0".join((task, parent, left, right)).encode()).hexdigest()
        output.append(
            {
                "pair_id": pair_id,
                "task": task,
                "parent": parent,
                "left": left,
                "right": right,
                "split": row["intask_split"],
                **{arm: float(orientation * margins[arm][index]) for arm in ARMS},
            }
        )
    return output


def compare_reference(path: Path, expected: list[dict[str, Any]]) -> float:
    with path.open(encoding="utf-8", newline="") as handle:
        actual = list(csv.DictReader(handle))
    check(len(actual) == len(expected), "reference row count differs")
    maximum = 0.0
    identity_fields = ("pair_id", "task", "parent", "left", "right", "split")
    for observed, wanted in zip(actual, expected):
        check(
            all(observed.get(field) == wanted[field] for field in identity_fields),
            "reference identity/order differs",
        )
        for arm in ARMS:
            difference = abs(float(observed[arm]) - wanted[arm])
            maximum = max(maximum, difference)
            check(difference <= 1e-12, f"reference margin differs: {arm}")
    return maximum


def verify(args: argparse.Namespace) -> dict[str, Any]:
    repo = args.repo_root.resolve()
    protocol_path = args.protocol.resolve()
    protocol_sha, source_hashes = bind_source(repo, args.source_commit, protocol_path)
    result = args.result.resolve()
    summary = read_object(result / "summary.json")
    expected_inputs = {
        "cards_sha256": independent_base.EXPECTED["cards"][0],
        "dev_sha256": independent_base.EXPECTED["dev"][0],
        "protocol_sha256": protocol_sha,
        "train_sha256": independent_base.EXPECTED["train"][0],
    }
    check(
        summary.get("protocol") == PRODUCER_PROTOCOL
        and summary.get("status") == PRODUCER_STATUS
        and summary.get("source_commit") == args.source_commit
        and summary.get("source_file_sha256") == source_hashes
        and summary.get("inputs") == expected_inputs,
        "producer summary source/input contract differs",
    )
    scope = summary.get("scope", {})
    check(
        scope.get("effect_metrics_computed") == []
        and scope.get("prospective_outcomes_read") is False
        and scope.get("prospective_state_read") is False
        and scope.get("test_split_read") is False,
        "producer scope differs",
    )
    outputs = summary.get("outputs", {})
    model_spec_path = result / str(outputs.get("model_spec"))
    reference_path = result / str(outputs.get("train_reference"))
    check(
        sha256_file(model_spec_path) == outputs.get("model_spec_sha256")
        and sha256_file(reference_path) == outputs.get("train_reference_sha256"),
        "producer output hash differs",
    )
    rows, matrices, training_receipt = load_training(
        args.training_cards, args.train_pairs, args.dev_pairs
    )
    margins, fit_receipts = refit(matrices)
    expected_model_spec = {
        "arms": list(ARMS),
        "estimator": {
            "class": "sklearn.ensemble.HistGradientBoostingClassifier",
            **MODEL_PARAMETERS,
        },
        "feature_receipt": training_receipt["feature_receipt"],
        "fit_receipts": fit_receipts,
        "format": "deterministic-full-refit-spec-and-reference-v1",
        "orientation": "canonical left-right; positive margin favors left",
        "protocol": PRODUCER_PROTOCOL,
    }
    check(read_object(model_spec_path) == expected_model_spec, "model specification differs")
    maximum = compare_reference(reference_path, expected_reference(rows, margins))
    check(
        summary.get("inventory")
        == {
            "pairs": len(rows),
            "tasks": len({row["task"] for row in rows}),
            "training_needed_cards": training_receipt["needed_cards"],
        }
        and summary.get("training_integrity")
        == {
            "card_inventory": training_receipt["card_inventory"],
            "component_integrity": training_receipt["component_integrity"],
        },
        "producer training inventory/integrity differs",
    )
    return {
        "all_model_spec_fields_exact": True,
        "inputs": expected_inputs,
        "maximum_reference_margin_difference": maximum,
        "model_spec_sha256": outputs["model_spec_sha256"],
        "producer_imported": False,
        "producer_summary_sha256": sha256_file(result / "summary.json"),
        "protocol": VERIFY_PROTOCOL,
        "reference_rows": len(rows),
        "source_commit": args.source_commit,
        "status": STATUS,
        "train_reference_sha256": outputs["train_reference_sha256"],
        "scope": {
            "api_calls": 0,
            "effect_metrics_computed": [],
            "gpu": 0,
            "prospective_outcomes_read": False,
            "prospective_state_read": False,
            "test_split_read": False,
        },
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--repo-root", required=True, type=Path)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--protocol", required=True, type=Path)
    value.add_argument("--training-cards", required=True, type=Path)
    value.add_argument("--train-pairs", required=True, type=Path)
    value.add_argument("--dev-pairs", required=True, type=Path)
    value.add_argument("--result", required=True, type=Path)
    value.add_argument("--output", required=True, type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    if args.output.exists():
        print("TRANSITION_FUTURE_FULLFIT_VERIFY_ERROR: output exists", file=sys.stderr)
        return 2
    try:
        receipt = verify(args)
        args.output.write_text(
            json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except (
        VerifyError,
        independent_base.VerificationError,
        independent_transition.TransitionVerificationError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"TRANSITION_FUTURE_FULLFIT_VERIFY_ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"status": receipt["status"], "rows": receipt["reference_rows"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
