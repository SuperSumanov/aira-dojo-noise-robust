"""Build the deterministic full-fit receipt for the frozen transition escrow."""

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

from phase1 import critic_static_source_component_oof as base
from phase1 import critic_transition_static_component_oof as transition


PROTOCOL = "transition-future-fullfit-v1"
ESCROW_PROTOCOL = "transition-future-escrow-v1"
STATUS = "TRANSITION_FUTURE_FULLFIT_COMPLETE_PENDING_INDEPENDENT_VERIFICATION"
ARMS = transition.ARMS
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


class FullFitError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FullFitError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def bind_source(repo: Path, commit: str, protocol_path: Path) -> tuple[str, dict[str, str]]:
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    require(head == commit, "source commit mismatch")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    require(protocol.get("protocol") == ESCROW_PROTOCOL, "escrow protocol identity mismatch")
    paths = protocol.get("source_paths")
    require(isinstance(paths, list) and paths, "escrow source path list missing")
    hashes = {}
    for relative in paths:
        require(isinstance(relative, str), "non-string source path")
        path = repo / relative
        require(path.is_file(), f"bound source missing: {relative}")
        actual_blob = subprocess.check_output(
            ["git", "-C", str(repo), "hash-object", str(path)], text=True
        ).strip()
        expected_blob = subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", f"{commit}:{relative}"], text=True
        ).strip()
        require(actual_blob == expected_blob, f"bound source differs from commit: {relative}")
        hashes[relative] = sha256_file(path)
    return sha256_file(protocol_path), dict(sorted(hashes.items()))


def load_training(cards_path: Path, train_path: Path, dev_path: Path):
    for role, path in (("cards", cards_path), ("train", train_path), ("dev", dev_path)):
        base.verify_identity(path, role)
    rows = base.read_rows(train_path, "train") + base.read_rows(dev_path, "dev")
    rows.sort(key=base.pair_key)
    require(len(rows) == base.EXPECTED_COUNTS["pairs"], "training pair count changed")
    needed = {
        identifier
        for row in rows
        for identifier in (row["better"], row["worse"], row["parent"])
    }
    vectors, sources, runs, tasks, configs, inventory = transition.load_card_projection(
        cards_path, needed
    )
    require(
        all(tasks[row["parent"]] == row["task"] for row in rows),
        "training parent task differs from pair task",
    )
    _units, integrity = base.validate_and_close_components(rows, runs, tasks, configs)
    matrices, feature_receipt = transition.feature_matrices(rows, vectors, sources)
    return rows, matrices, {
        "card_inventory": inventory,
        "component_integrity": integrity,
        "feature_receipt": feature_receipt,
        "needed_cards": len(needed),
        "support_code_sha256": {
            hashlib.sha256(sources[identifier].encode()).hexdigest() for identifier in needed
        },
        "support_ids": needed,
        "support_runs": {runs[identifier] for identifier in needed},
    }


def fit_full(matrices: dict[str, np.ndarray]):
    models: dict[str, HistGradientBoostingClassifier] = {}
    margins: dict[str, np.ndarray] = {}
    receipts = {}
    for arm in ARMS:
        values = matrices[arm]
        design = np.concatenate((values, -values), axis=0)
        labels = np.concatenate(
            (np.ones(len(values), dtype=np.int8), np.zeros(len(values), dtype=np.int8))
        )
        estimator = HistGradientBoostingClassifier(**MODEL_PARAMETERS).fit(design, labels)
        require(estimator.n_iter_ == 300, f"{arm} iteration count changed")
        direct = estimator.decision_function(values)
        reverse_direct = estimator.decision_function(-values)
        forward = 0.5 * (direct - reverse_direct)
        reverse = 0.5 * (reverse_direct - direct)
        error = float(np.max(np.abs(forward + reverse)))
        require(np.isfinite(forward).all() and error <= 1e-12, f"{arm} antisymmetry failed")
        models[arm] = estimator
        margins[arm] = np.asarray(forward, dtype=np.float64)
        receipts[arm] = {
            "anti_symmetry_max_abs": error,
            "features": int(values.shape[1]),
            "fit_matrix_sha256": base.array_sha(values),
            "n_iter": int(estimator.n_iter_),
            "training_pairs": len(values),
            "training_rows_symmetric": len(design),
        }
    return models, margins, receipts


def score_differences(
    models: dict[str, HistGradientBoostingClassifier], matrices: dict[str, np.ndarray]
) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    margins = {}
    antisymmetry = {}
    for arm in ARMS:
        direct = models[arm].decision_function(matrices[arm])
        reverse_direct = models[arm].decision_function(-matrices[arm])
        forward = np.asarray(0.5 * (direct - reverse_direct), dtype=np.float64)
        reverse = np.asarray(0.5 * (reverse_direct - direct), dtype=np.float64)
        error = float(np.max(np.abs(forward + reverse))) if len(forward) else 0.0
        require(np.isfinite(forward).all() and error <= 1e-12, f"{arm} scoring failed")
        margins[arm] = forward
        antisymmetry[arm] = error
    return margins, antisymmetry


def reference_rows(rows: list[dict[str, Any]], margins: dict[str, np.ndarray]):
    output = []
    for index, row in enumerate(rows):
        task, parent, left, right = base.pair_key(row)
        orientation = 1.0 if row["better"] == left else -1.0
        identity = "\0".join((task, parent, left, right))
        output.append(
            {
                "pair_id": hashlib.sha256(identity.encode()).hexdigest(),
                "task": task,
                "parent": parent,
                "left": left,
                "right": right,
                "split": row["intask_split"],
                **{arm: float(orientation * margins[arm][index]) for arm in ARMS},
            }
        )
    return output


def write_reference(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = ("pair_id", "task", "parent", "left", "right", "split", *ARMS)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **{field: row[field] for field in fields[:6]},
                    **{arm: format(row[arm], ".17g") for arm in ARMS},
                }
            )


def build(args: argparse.Namespace) -> dict[str, Any]:
    repo = args.repo_root.resolve()
    protocol_path = args.protocol.resolve()
    protocol_sha, source_hashes = bind_source(repo, args.source_commit, protocol_path)
    output = args.output.resolve()
    require(not output.exists(), "refusing to overwrite output")
    output.mkdir(parents=True)
    rows, matrices, training_receipt = load_training(
        args.training_cards, args.train_pairs, args.dev_pairs
    )
    _models, margins, fit_receipts = fit_full(matrices)
    references = reference_rows(rows, margins)
    model_spec = {
        "arms": list(ARMS),
        "estimator": {
            "class": "sklearn.ensemble.HistGradientBoostingClassifier",
            **MODEL_PARAMETERS,
        },
        "feature_receipt": training_receipt["feature_receipt"],
        "fit_receipts": fit_receipts,
        "format": "deterministic-full-refit-spec-and-reference-v1",
        "orientation": "canonical left-right; positive margin favors left",
        "protocol": PROTOCOL,
    }
    model_spec_path = output / "model_spec.json"
    model_spec_path.write_bytes(canonical_json(model_spec))
    reference_path = output / "train_reference.csv"
    write_reference(reference_path, references)
    summary = {
        "inputs": {
            "cards_sha256": base.EXPECTED["cards"][0],
            "dev_sha256": base.EXPECTED["dev"][0],
            "protocol_sha256": protocol_sha,
            "train_sha256": base.EXPECTED["train"][0],
        },
        "inventory": {
            "pairs": len(rows),
            "tasks": len({row["task"] for row in rows}),
            "training_needed_cards": training_receipt["needed_cards"],
        },
        "outputs": {
            "model_spec": model_spec_path.name,
            "model_spec_sha256": sha256_file(model_spec_path),
            "train_reference": reference_path.name,
            "train_reference_sha256": sha256_file(reference_path),
        },
        "protocol": PROTOCOL,
        "scope": {
            "api_calls": 0,
            "base_llm_updates": 0,
            "effect_metrics_computed": [],
            "gpu": 0,
            "prospective_outcomes_read": False,
            "prospective_state_read": False,
            "test_split_read": False,
        },
        "source_commit": args.source_commit,
        "source_file_sha256": source_hashes,
        "status": STATUS,
        "training_integrity": {
            "card_inventory": training_receipt["card_inventory"],
            "component_integrity": training_receipt["component_integrity"],
        },
    }
    summary_path = output / "summary.json"
    summary_path.write_bytes(canonical_json(summary))
    return summary


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--repo-root", required=True, type=Path)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--protocol", required=True, type=Path)
    value.add_argument("--training-cards", required=True, type=Path)
    value.add_argument("--train-pairs", required=True, type=Path)
    value.add_argument("--dev-pairs", required=True, type=Path)
    value.add_argument("--output", required=True, type=Path)
    return value


def main() -> int:
    try:
        summary = build(parser().parse_args())
    except (
        FullFitError,
        base.AuditError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"TRANSITION_FUTURE_FULLFIT_ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"status": summary["status"], "pairs": summary["inventory"]["pairs"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
