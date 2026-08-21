"""Independent full-refit verifier for the component-split char-TFIDF baseline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression


REPS = 20_000
TASK_SEED = 20260821
PARENT_SEED = 20260822
EXPECTED = {
    "cards": ("5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb", 604190866),
    "train": ("0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e", 3208089),
    "dev": ("3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4", 376635),
    "test": ("cb84d78d578e6a3f5378b3396a355fa83880739b4f9af8459d2b960c7ae005da", 381803),
    "draft": ("3ca77a18e224cacbb7f52121d6e8c2b66f17298c68dd06fbc42a14a238ad05b9", 1465008),
    "improve": ("7aca481afda5317fe78a0ad52fc7488fceff7fde6531c74ebb718df9e3b6926e", 1087821),
}


class VerificationError(RuntimeError):
    """Raised when a producer artifact differs from an independent refit."""


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compact(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def identify(path: Path, role: str) -> None:
    expected_hash, expected_bytes = EXPECTED[role]
    if path.stat().st_size != expected_bytes or file_hash(path) != expected_hash:
        raise VerificationError(f"{role} identity mismatch")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                raise VerificationError(f"blank row {number}")
            row = json.loads(line)
            if not isinstance(row, dict):
                raise VerificationError("row is not object")
            rows.append(row)
    return rows


def identity(row: dict[str, Any]) -> tuple[str, str, str, str]:
    try:
        endpoints = sorted((row["better"], row["worse"]))
        key = row["task"], row["parent"], endpoints[0], endpoints[1]
    except (KeyError, TypeError, ValueError) as error:
        raise VerificationError("bad pair identity") from error
    if not all(isinstance(item, str) and item for item in key) or key[2] == key[3]:
        raise VerificationError("bad pair identity")
    return key


def cards_for(path: Path, endpoints: set[str]) -> tuple[dict[str, str], dict[str, str], dict[str, tuple[Any, ...]], dict[str, int]]:
    grouped = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(grouped, dict):
        raise VerificationError("cards root invalid")
    code: dict[str, str] = {}
    run: dict[str, str] = {}
    config: dict[str, tuple[Any, ...]] = {}
    seen = set()
    total = 0
    for run_id, cards in grouped.items():
        if not isinstance(run_id, str) or not isinstance(cards, list):
            raise VerificationError("cards group invalid")
        for card in cards:
            total += 1
            if not isinstance(card, dict) or not isinstance(card.get("id"), str) or card["id"] in seen:
                raise VerificationError("card identity invalid")
            card_id = card["id"]
            seen.add(card_id)
            if card_id not in endpoints:
                continue
            task_object = card.get("task")
            task = task_object.get("name") if isinstance(task_object, dict) else None
            values = task, card.get("client"), card.get("hardware"), card.get("time_limit"), card.get("execution_timeout")
            if (
                not isinstance(card.get("code"), str)
                or not all(isinstance(value, str) and value for value in values[:3])
                or not all(isinstance(value, int) for value in values[3:])
            ):
                raise VerificationError("needed card incomplete")
            code[card_id] = card["code"]
            run[card_id] = run_id
            config[card_id] = values
    if set(code) != endpoints:
        raise VerificationError("needed card missing")
    return code, run, config, {"cards": total, "run_groups": len(grouped), "needed_cards": len(endpoints)}


def semantics(draft_path: Path, improve_path: Path) -> dict[tuple[str, str, str, str], str]:
    draft_keys = {identity(row) for row in read_jsonl(draft_path)}
    improve_keys = {identity(row) for row in read_jsonl(improve_path)}
    if draft_keys & improve_keys:
        raise VerificationError("semantic key overlap")
    return {key: "Draft" for key in draft_keys} | {key: "Improve" for key in improve_keys}


def pair_positions(rows: list[dict[str, Any]], positions: dict[str, int]) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.fromiter((positions[row["better"]] for row in rows), dtype=np.int64),
        np.fromiter((positions[row["worse"]] for row in rows), dtype=np.int64),
    )


def distribution(values: np.ndarray) -> dict[str, float | None]:
    if values.size == 0:
        return {key: None for key in ("q00", "q10", "q25", "q50", "q75", "q90", "q100")}
    quantile = np.quantile(values, [0, .1, .25, .5, .75, .9, 1], method="linear")
    return {key: float(value) for key, value in zip(("q00", "q10", "q25", "q50", "q75", "q90", "q100"), quantile)}


def clustered_task(rows: list[dict[str, Any]], flags: np.ndarray) -> dict[str, Any]:
    accuracies = []
    for task in sorted({row["task"] for row in rows}):
        accuracies.append(float(np.mean([flag for row, flag in zip(rows, flags) if row["task"] == task])))
    values = np.asarray(accuracies, dtype=np.float64)
    rng = np.random.default_rng(TASK_SEED)
    draws = rng.integers(0, len(values), size=(REPS, len(values)))
    estimates = np.mean(values[draws], axis=1)
    interval = np.quantile(estimates, [.025, .975], method="linear")
    return {
        "estimand": "task_macro_accuracy", "point": float(np.mean(values)),
        "ci95": [float(interval[0]), float(interval[1])], "clusters": len(values),
        "replicates": REPS, "seed": TASK_SEED,
    }


def clustered_parent(rows: list[dict[str, Any]], flags: np.ndarray) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row, flag in zip(rows, flags):
        grouped[(row["task"], row["parent"])].append(float(flag))
    clusters = sorted(grouped)
    arrays = [np.asarray(grouped[key], dtype=np.float64) for key in clusters]
    rng = np.random.default_rng(PARENT_SEED)
    estimates = np.empty(REPS, dtype=np.float64)
    for draw in range(REPS):
        selection = rng.integers(0, len(arrays), size=len(arrays))
        estimates[draw] = sum(float(np.sum(arrays[index])) for index in selection) / sum(
            len(arrays[index]) for index in selection
        )
    interval = np.quantile(estimates, [.025, .975], method="linear")
    return {
        "estimand": "pair_micro_accuracy_parent_clustered", "point": float(np.mean(flags)),
        "ci95": [float(interval[0]), float(interval[1])], "clusters": len(arrays),
        "replicates": REPS, "seed": PARENT_SEED,
    }


def pool_statistics(
    rows: list[dict[str, Any]], margins: np.ndarray, semantic_values: list[str]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metrics = {}
    task_records = []
    for subset in ("merged", "Draft", "Improve"):
        selected = np.asarray([subset == "merged" or value == subset for value in semantic_values], dtype=bool)
        chosen_rows = [row for row, keep in zip(rows, selected) if keep]
        chosen_margins = margins[selected]
        flags = chosen_margins > 0
        tasks = sorted({row["task"] for row in chosen_rows})
        task_accuracy = {
            task: float(np.mean([flag for row, flag in zip(chosen_rows, flags) if row["task"] == task]))
            for task in tasks
        }
        metrics[subset] = {
            "pairs": len(chosen_rows), "tasks": len(tasks),
            "parents": len({(row["task"], row["parent"]) for row in chosen_rows}),
            "micro_accuracy": float(np.mean(flags)),
            "task_macro_accuracy": float(np.mean(list(task_accuracy.values()))),
            "ties": int(np.sum(chosen_margins == 0)),
            "margin_quantiles": distribution(chosen_margins),
            "task_clustered": clustered_task(chosen_rows, flags),
            "parent_clustered": clustered_parent(chosen_rows, flags),
        }
        task_records.extend(
            {"subset": subset, "task": task, "pairs": sum(row["task"] == task for row in chosen_rows), "accuracy": accuracy}
            for task, accuracy in task_accuracy.items()
        )
    return metrics, task_records


def compare_values(expected: Any, observed: Any, path: str = "root") -> float:
    if isinstance(expected, dict):
        if not isinstance(observed, dict) or set(expected) != set(observed):
            raise VerificationError(f"mapping mismatch at {path}")
        return max((compare_values(value, observed[key], f"{path}.{key}") for key, value in expected.items()), default=0.0)
    if isinstance(expected, list):
        if not isinstance(observed, list) or len(expected) != len(observed):
            raise VerificationError(f"list mismatch at {path}")
        return max((compare_values(left, right, f"{path}[{index}]") for index, (left, right) in enumerate(zip(expected, observed))), default=0.0)
    if isinstance(expected, float):
        if not isinstance(observed, (int, float)) or not np.isfinite(observed):
            raise VerificationError(f"float mismatch at {path}")
        difference = abs(expected - float(observed))
        if difference > 1e-12:
            raise VerificationError(f"numeric mismatch at {path}: {difference}")
        return difference
    if expected != observed:
        raise VerificationError(f"value mismatch at {path}")
    return 0.0


def verify(
    cards_path: Path,
    train_path: Path,
    dev_path: Path,
    test_path: Path,
    draft_path: Path,
    improve_path: Path,
    artifact_dir: Path,
) -> dict[str, Any]:
    for role, path in (("cards", cards_path), ("train", train_path), ("dev", dev_path), ("test", test_path), ("draft", draft_path), ("improve", improve_path)):
        identify(path, role)
    pools = {"train": read_jsonl(train_path), "dev": read_jsonl(dev_path), "test": read_jsonl(test_path)}
    if any(row.get("intask_split") != split for split, rows in pools.items() for row in rows):
        raise VerificationError("split row mismatch")
    for name, rows in pools.items():
        keys = [identity(row) for row in rows]
        if len(keys) != len(set(keys)):
            raise VerificationError(f"duplicate pair in {name}")
    key_sets = {name: {identity(row) for row in rows} for name, rows in pools.items()}
    if any(key_sets[left] & key_sets[right] for left, right in (("train", "dev"), ("train", "test"), ("dev", "test"))):
        raise VerificationError("pair overlap")
    endpoints = {endpoint for rows in pools.values() for row in rows for endpoint in identity(row)[2:]}
    code, run, config, card_inventory = cards_for(cards_path, endpoints)
    endpoint_sets = {name: {endpoint for key in keys for endpoint in key[2:]} for name, keys in key_sets.items()}
    run_sets = {name: {run[endpoint] for endpoint in values} for name, values in endpoint_sets.items()}
    if any(endpoint_sets[left] & endpoint_sets[right] or run_sets[left] & run_sets[right] for left, right in (("train", "dev"), ("train", "test"), ("dev", "test"))):
        raise VerificationError("endpoint or run overlap")
    semantic_map = semantics(draft_path, improve_path)
    component_split: dict[str, str] = {}
    for split in ("train", "dev"):
        for row in pools[split]:
            if (
                row.get("outer_intask_split") != "train"
                or row.get("train_dev_protocol") != "pair-graph-component-train-dev-split-v1"
                or row.get("train_dev_seed") != 20260821
                or row.get("train_dev_target_numerator") != 1
                or row.get("train_dev_target_denominator") != 10
                or not isinstance(row.get("pair_component_id"), str)
                or re.fullmatch(r"[0-9a-f]{64}", row["pair_component_id"]) is None
            ):
                raise VerificationError("component split receipt mismatch")
            component = row["pair_component_id"]
            if component in component_split and component_split[component] != split:
                raise VerificationError("component crosses train/dev")
            component_split[component] = split
    for rows in pools.values():
        for row in rows:
            key = identity(row)
            if key not in semantic_map or config[row["better"]] != config[row["worse"]] or config[row["better"]][0] != row["task"]:
                raise VerificationError("semantic/config mismatch")

    ordered_cards = sorted(endpoints)
    positions = {card_id: position for position, card_id in enumerate(ordered_cards)}
    train_endpoints = sorted(endpoint_sets["train"])
    tfidf = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(3, 5), max_features=30000,
        min_df=3, sublinear_tf=True, dtype=np.float64,
    )
    tfidf.fit([code[card_id][:20000] for card_id in train_endpoints])
    feature_matrix = tfidf.transform([code[card_id][:20000] for card_id in ordered_cards]).tocsr()
    better, worse = pair_positions(pools["train"], positions)
    differences = feature_matrix[better] - feature_matrix[worse]
    fit_matrix = sparse.vstack((differences, -differences), format="csr")
    labels = np.concatenate((np.ones(differences.shape[0], dtype=np.int8), np.zeros(differences.shape[0], dtype=np.int8)))
    model = LogisticRegression(C=.5, max_iter=1500, solver="lbfgs", random_state=0).fit(fit_matrix, labels)
    if int(model.n_iter_[0]) >= 1500 or not np.isfinite(model.coef_).all():
        raise VerificationError("refit convergence failure")

    producer_summary = json.loads((artifact_dir / "summary.json").read_text(encoding="utf-8"))
    expected_integrity = {
        "overlap": {
            f"{left}_{right}_{kind}": 0
            for left, right in (("train", "dev"), ("train", "test"), ("dev", "test"))
            for kind in ("pairs", "endpoints", "runs")
        },
        "pairs": {name: len(rows) for name, rows in pools.items()},
        "endpoints": {name: len(values) for name, values in endpoint_sets.items()},
        "runs": {name: len(values) for name, values in run_sets.items()},
        "components": len(component_split),
    }
    static_checks = {
        "protocol": "critic-component-char-tfidf-baseline-v1",
        "status": "BASELINE_VALID",
        "evidence_level": "retrospective_same_pool_baseline",
        "inputs": {
            role: {"sha256": EXPECTED[role][0], "bytes": EXPECTED[role][1]}
            for role in ("cards", "train", "dev", "test", "draft", "improve")
        },
        "integrity": expected_integrity,
        "bootstrap": {"replicates": REPS, "task_seed": TASK_SEED, "parent_seed": PARENT_SEED},
    }
    for field, expected_value in static_checks.items():
        if producer_summary.get(field) != expected_value:
            raise VerificationError(f"producer summary static mismatch: {field}")
    producer_pairs = read_jsonl(artifact_dir / "per_pair.jsonl")
    observed_pair_index = {(row["split"], row["index"]): row for row in producer_pairs}
    recomputed_metrics = {}
    recomputed_task_rows = []
    max_margin_difference = 0.0
    anti_symmetry = 0.0
    pair_weights = np.asarray(model.coef_, dtype=np.float64).reshape(-1)
    for split in ("dev", "test"):
        rows = pools[split]
        better, worse = pair_positions(rows, positions)
        pair_matrix = feature_matrix[better] - feature_matrix[worse]
        margin = np.asarray(pair_matrix.dot(pair_weights), dtype=np.float64).reshape(-1)
        reverse = np.asarray((-pair_matrix).dot(pair_weights), dtype=np.float64).reshape(-1)
        anti_symmetry = max(anti_symmetry, float(np.max(np.abs(margin + reverse))))
        semantic_values = [semantic_map[identity(row)] for row in rows]
        recomputed_metrics[split], task_rows = pool_statistics(rows, margin, semantic_values)
        recomputed_task_rows.extend({"split": split, **row} for row in task_rows)
        for index, (row, semantic, value) in enumerate(zip(rows, semantic_values, margin)):
            observed = observed_pair_index.get((split, index))
            if observed is None:
                raise VerificationError("missing per-pair row")
            expected_identity = {
                "task": row["task"], "parent": row["parent"], "better": row["better"], "worse": row["worse"],
                "better_run": run[row["better"]], "worse_run": run[row["worse"]], "semantics": semantic,
                "correct": bool(value > 0), "tie": bool(value == 0),
            }
            if any(observed.get(key) != expected for key, expected in expected_identity.items()):
                raise VerificationError("per-pair identity/prediction mismatch")
            difference = abs(float(observed.get("margin")) - float(value))
            max_margin_difference = max(max_margin_difference, difference)
            if difference > 1e-12:
                raise VerificationError("per-pair margin mismatch")
    if len(observed_pair_index) != len(pools["dev"]) + len(pools["test"]):
        raise VerificationError("extra per-pair row")

    max_metric_difference = compare_values(recomputed_metrics, producer_summary.get("metrics"), "metrics")
    vocabulary = sorted((term, int(index)) for term, index in tfidf.vocabulary_.items())
    expected_model = {
        "code_prefix_chars": 20000,
        "vectorizer": {"analyzer": "char_wb", "ngram_range": [3, 5], "max_features": 30000, "min_df": 3, "sublinear_tf": True, "dtype": "float64"},
        "logistic_regression": {"C": 0.5, "max_iter": 1500, "solver": "lbfgs", "random_state": 0, "n_iter": int(model.n_iter_[0])},
        "pair_margin_uses_classifier_intercept": False,
        "train_endpoints": len(train_endpoints), "all_endpoints": len(ordered_cards),
        "vocabulary_size": len(vocabulary),
        "vocabulary_sha256": hashlib.sha256(compact(vocabulary).encode()).hexdigest(),
        "idf_sha256": hashlib.sha256(np.asarray(tfidf.idf_, dtype="<f8").tobytes()).hexdigest(),
        "coefficient_sha256": hashlib.sha256(np.asarray(model.coef_, dtype="<f8").tobytes()).hexdigest(),
        "intercept": float(model.intercept_[0]),
        "intercept_sha256": hashlib.sha256(np.asarray(model.intercept_, dtype="<f8").tobytes()).hexdigest(),
        "anti_symmetry_max_abs": anti_symmetry,
    }
    max_model_difference = compare_values(expected_model, producer_summary.get("model"), "model")
    if producer_summary.get("card_inventory") != card_inventory:
        raise VerificationError("card inventory mismatch")

    with (artifact_dir / "per_task.csv").open(encoding="utf-8", newline="") as handle:
        observed_task_rows = list(csv.DictReader(handle))
    if len(observed_task_rows) != len(recomputed_task_rows):
        raise VerificationError("per-task row count mismatch")
    max_task_difference = 0.0
    for expected, observed in zip(recomputed_task_rows, observed_task_rows):
        for key in ("split", "subset", "task"):
            if observed[key] != expected[key]:
                raise VerificationError("per-task identity mismatch")
        if int(observed["pairs"]) != expected["pairs"]:
            raise VerificationError("per-task count mismatch")
        max_task_difference = max(max_task_difference, abs(float(observed["accuracy"]) - expected["accuracy"]))
    if max_task_difference > 1e-12:
        raise VerificationError("per-task accuracy mismatch")

    manifest = json.loads((artifact_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
    expected_manifest = {name: file_hash(artifact_dir / name) for name in ("summary.json", "per_pair.jsonl", "per_task.csv")}
    if manifest != expected_manifest:
        raise VerificationError("artifact manifest mismatch")
    return {
        "protocol": "independent-critic-component-char-tfidf-verifier-v1",
        "status": "BASELINE_INDEPENDENTLY_VERIFIED",
        "full_refit": True,
        "producer_imported": False,
        "pairs": {name: len(rows) for name, rows in pools.items()},
        "max_abs_margin_difference": max_margin_difference,
        "max_abs_metric_difference": max_metric_difference,
        "max_abs_model_receipt_difference": max_model_difference,
        "max_abs_task_accuracy_difference": max_task_difference,
        "producer_summary_sha256": file_hash(artifact_dir / "summary.json"),
        "producer_artifact_manifest_sha256": file_hash(artifact_dir / "artifact_manifest.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cards", type=Path)
    parser.add_argument("train", type=Path)
    parser.add_argument("dev", type=Path)
    parser.add_argument("test", type=Path)
    parser.add_argument("draft", type=Path)
    parser.add_argument("improve", type=Path)
    parser.add_argument("artifact_dir", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(verify(
        arguments.cards, arguments.train, arguments.dev, arguments.test,
        arguments.draft, arguments.improve, arguments.artifact_dir,
    ), indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
