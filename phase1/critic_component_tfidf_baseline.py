"""Train-only char-TFIDF baseline for the fixed pair-component critic split."""

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


PROTOCOL = "critic-component-char-tfidf-baseline-v1"
TASK_SEED = 20260821
PARENT_SEED = 20260822
BOOTSTRAP_REPS = 20_000
EXPECTED = {
    "cards": ("5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb", 604190866),
    "train": ("0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e", 3208089),
    "dev": ("3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4", 376635),
    "test": ("cb84d78d578e6a3f5378b3396a355fa83880739b4f9af8459d2b960c7ae005da", 381803),
    "draft": ("3ca77a18e224cacbb7f52121d6e8c2b66f17298c68dd06fbc42a14a238ad05b9", 1465008),
    "improve": ("7aca481afda5317fe78a0ad52fc7488fceff7fde6531c74ebb718df9e3b6926e", 1087821),
}
SUBSETS = ("merged", "Draft", "Improve")


class BaselineError(RuntimeError):
    """Raised when an input, model, or output invariant fails."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def compact(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def verify_identity(path: Path, role: str) -> None:
    expected_hash, expected_bytes = EXPECTED[role]
    if path.stat().st_size != expected_bytes or sha256_file(path) != expected_hash:
        raise BaselineError(f"{role} input identity mismatch")


def pair_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    try:
        left, right = sorted((row["better"], row["worse"]))
        values = row["task"], row["parent"], left, right
    except (KeyError, TypeError, ValueError) as error:
        raise BaselineError("invalid pair identity") from error
    if not all(isinstance(value, str) and value for value in values) or left == right:
        raise BaselineError("invalid pair identity")
    return values


def read_rows(path: Path, expected_split: str | None = None) -> list[dict[str, Any]]:
    rows = []
    keys = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise BaselineError(f"blank row at {path.name}:{line_number}")
            row = json.loads(line)
            if not isinstance(row, dict):
                raise BaselineError("pair row is not an object")
            key = pair_key(row)
            if key in keys:
                raise BaselineError(f"duplicate unordered pair in {path.name}")
            keys.add(key)
            if expected_split is not None and row.get("intask_split") != expected_split:
                raise BaselineError(f"unexpected split in {path.name}")
            rows.append(row)
    return rows


def load_cards(
    path: Path, needed: set[str]
) -> tuple[dict[str, str], dict[str, str], dict[str, tuple[Any, ...]], dict[str, int]]:
    grouped = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(grouped, dict):
        raise BaselineError("cards root is not grouped")
    codes: dict[str, str] = {}
    runs: dict[str, str] = {}
    configs: dict[str, tuple[Any, ...]] = {}
    seen: set[str] = set()
    total = 0
    for run_id, cards in grouped.items():
        if not isinstance(run_id, str) or not isinstance(cards, list):
            raise BaselineError("invalid card group")
        for card in cards:
            total += 1
            if not isinstance(card, dict) or not isinstance(card.get("id"), str) or card["id"] in seen:
                raise BaselineError("invalid or duplicate card")
            card_id = card["id"]
            seen.add(card_id)
            if card_id not in needed:
                continue
            task_object = card.get("task")
            task = task_object.get("name") if isinstance(task_object, dict) else None
            config = (task, card.get("client"), card.get("hardware"), card.get("time_limit"), card.get("execution_timeout"))
            if (
                not isinstance(card.get("code"), str)
                or not all(isinstance(value, str) and value for value in config[:3])
                or not all(isinstance(value, int) for value in config[3:])
            ):
                raise BaselineError("needed card lacks code or provenance")
            codes[card_id] = card["code"]
            runs[card_id] = run_id
            configs[card_id] = config
    if set(codes) != needed:
        raise BaselineError("pair endpoint missing from cards")
    return codes, runs, configs, {"cards": total, "run_groups": len(grouped), "needed_cards": len(needed)}


def semantics_map(draft_rows: list[dict[str, Any]], improve_rows: list[dict[str, Any]]) -> dict[tuple[str, str, str, str], str]:
    draft = {pair_key(row) for row in draft_rows}
    improve = {pair_key(row) for row in improve_rows}
    if draft & improve:
        raise BaselineError("Draft/Improve identities overlap")
    return {key: "Draft" for key in draft} | {key: "Improve" for key in improve}


def validate_splits(
    pools: dict[str, list[dict[str, Any]]],
    runs: dict[str, str],
    configs: dict[str, tuple[Any, ...]],
    semantics: dict[tuple[str, str, str, str], str],
) -> dict[str, Any]:
    keys = {name: {pair_key(row) for row in rows} for name, rows in pools.items()}
    endpoints = {name: {endpoint for key in values for endpoint in key[2:]} for name, values in keys.items()}
    run_sets = {name: {runs[endpoint] for endpoint in values} for name, values in endpoints.items()}
    overlap = {}
    for left, right in (("train", "dev"), ("train", "test"), ("dev", "test")):
        overlap[f"{left}_{right}_pairs"] = len(keys[left] & keys[right])
        overlap[f"{left}_{right}_endpoints"] = len(endpoints[left] & endpoints[right])
        overlap[f"{left}_{right}_runs"] = len(run_sets[left] & run_sets[right])
    if any(overlap.values()):
        raise BaselineError("split overlap")
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
                raise BaselineError("component split receipt mismatch")
            component = row["pair_component_id"]
            if component in component_split and component_split[component] != split:
                raise BaselineError("component crosses train/dev")
            component_split[component] = split
    for split, rows in pools.items():
        for row in rows:
            key = pair_key(row)
            if key not in semantics:
                raise BaselineError("pair lacks fixed semantics")
            if configs[row["better"]] != configs[row["worse"]] or configs[row["better"]][0] != row["task"]:
                raise BaselineError("pair violates exact config")
    return {
        "overlap": overlap,
        "pairs": {name: len(rows) for name, rows in pools.items()},
        "endpoints": {name: len(values) for name, values in endpoints.items()},
        "runs": {name: len(values) for name, values in run_sets.items()},
        "components": len(component_split),
    }


def matrix_indices(rows: list[dict[str, Any]], positions: dict[str, int]) -> tuple[np.ndarray, np.ndarray]:
    better = np.fromiter((positions[row["better"]] for row in rows), dtype=np.int64)
    worse = np.fromiter((positions[row["worse"]] for row in rows), dtype=np.int64)
    return better, worse


def quantiles(values: np.ndarray) -> dict[str, float | None]:
    if not len(values):
        return {name: None for name in ("q00", "q10", "q25", "q50", "q75", "q90", "q100")}
    points = np.quantile(values, [0, 0.1, 0.25, 0.5, 0.75, 0.9, 1], method="linear")
    return {name: float(value) for name, value in zip(("q00", "q10", "q25", "q50", "q75", "q90", "q100"), points)}


def task_ci(rows: list[dict[str, Any]], correct: np.ndarray) -> dict[str, Any]:
    task_values = []
    for task in sorted({row["task"] for row in rows}):
        task_values.append(float(np.mean([flag for row, flag in zip(rows, correct) if row["task"] == task])))
    values = np.asarray(task_values, dtype=np.float64)
    rng = np.random.default_rng(TASK_SEED)
    sampled = rng.integers(0, len(values), size=(BOOTSTRAP_REPS, len(values)))
    estimates = np.mean(values[sampled], axis=1)
    low, high = np.quantile(estimates, [0.025, 0.975], method="linear")
    return {
        "estimand": "task_macro_accuracy",
        "point": float(np.mean(values)),
        "ci95": [float(low), float(high)],
        "clusters": len(values),
        "replicates": BOOTSTRAP_REPS,
        "seed": TASK_SEED,
    }


def parent_ci(rows: list[dict[str, Any]], correct: np.ndarray) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row, flag in zip(rows, correct):
        grouped[(row["task"], row["parent"])].append(float(flag))
    clusters = sorted(grouped)
    values = [np.asarray(grouped[key], dtype=np.float64) for key in clusters]
    rng = np.random.default_rng(PARENT_SEED)
    estimates = np.empty(BOOTSTRAP_REPS, dtype=np.float64)
    for index in range(BOOTSTRAP_REPS):
        sampled = rng.integers(0, len(values), size=len(values))
        numerator = sum(float(np.sum(values[item])) for item in sampled)
        denominator = sum(len(values[item]) for item in sampled)
        estimates[index] = numerator / denominator
    low, high = np.quantile(estimates, [0.025, 0.975], method="linear")
    return {
        "estimand": "pair_micro_accuracy_parent_clustered",
        "point": float(np.mean(correct)),
        "ci95": [float(low), float(high)],
        "clusters": len(values),
        "replicates": BOOTSTRAP_REPS,
        "seed": PARENT_SEED,
    }


def metrics_for_pool(
    rows: list[dict[str, Any]], margins: np.ndarray, pair_semantics: list[str]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    output = {}
    task_rows = []
    for subset in SUBSETS:
        mask = np.asarray([subset == "merged" or semantic == subset for semantic in pair_semantics], dtype=bool)
        selected_rows = [row for row, keep in zip(rows, mask) if keep]
        selected_margins = margins[mask]
        correct = selected_margins > 0
        task_accuracy = {
            task: float(np.mean([flag for row, flag in zip(selected_rows, correct) if row["task"] == task]))
            for task in sorted({row["task"] for row in selected_rows})
        }
        output[subset] = {
            "pairs": len(selected_rows),
            "tasks": len(task_accuracy),
            "parents": len({(row["task"], row["parent"]) for row in selected_rows}),
            "micro_accuracy": float(np.mean(correct)),
            "task_macro_accuracy": float(np.mean(list(task_accuracy.values()))),
            "ties": int(np.sum(selected_margins == 0)),
            "margin_quantiles": quantiles(selected_margins),
            "task_clustered": task_ci(selected_rows, correct),
            "parent_clustered": parent_ci(selected_rows, correct),
        }
        task_rows.extend(
            {"subset": subset, "task": task, "pairs": sum(row["task"] == task for row in selected_rows), "accuracy": accuracy}
            for task, accuracy in task_accuracy.items()
        )
    return output, task_rows


def analyze(
    cards_path: Path,
    train_path: Path,
    dev_path: Path,
    test_path: Path,
    draft_path: Path,
    improve_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    paths = {"cards": cards_path, "train": train_path, "dev": dev_path, "test": test_path, "draft": draft_path, "improve": improve_path}
    for role, path in paths.items():
        verify_identity(path, role)
    pools = {
        "train": read_rows(train_path, "train"),
        "dev": read_rows(dev_path, "dev"),
        "test": read_rows(test_path, "test"),
    }
    draft_rows, improve_rows = read_rows(draft_path), read_rows(improve_path)
    semantics = semantics_map(draft_rows, improve_rows)
    needed = {endpoint for rows in pools.values() for row in rows for endpoint in pair_key(row)[2:]}
    codes, runs, configs, card_inventory = load_cards(cards_path, needed)
    integrity = validate_splits(pools, runs, configs, semantics)

    card_ids = sorted(needed)
    positions = {card_id: index for index, card_id in enumerate(card_ids)}
    train_ids = sorted({endpoint for row in pools["train"] for endpoint in pair_key(row)[2:]})
    vectorizer = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(3, 5), max_features=30000,
        min_df=3, sublinear_tf=True, dtype=np.float64,
    )
    vectorizer.fit([codes[card_id][:20000] for card_id in train_ids])
    matrix = vectorizer.transform([codes[card_id][:20000] for card_id in card_ids]).tocsr()
    train_better, train_worse = matrix_indices(pools["train"], positions)
    train_difference = matrix[train_better] - matrix[train_worse]
    fit_x = sparse.vstack((train_difference, -train_difference), format="csr")
    fit_y = np.concatenate((
        np.ones(train_difference.shape[0], dtype=np.int8),
        np.zeros(train_difference.shape[0], dtype=np.int8),
    ))
    model = LogisticRegression(C=0.5, max_iter=1500, solver="lbfgs", random_state=0).fit(fit_x, fit_y)
    if int(model.n_iter_[0]) >= 1500 or not np.isfinite(model.coef_).all() or not np.isfinite(model.intercept_).all():
        raise BaselineError("logistic regression convergence/finite gate failed")

    all_pair_rows = []
    all_task_rows = []
    all_metrics = {}
    anti_symmetry = 0.0
    for split in ("dev", "test"):
        rows = pools[split]
        better, worse = matrix_indices(rows, positions)
        difference = matrix[better] - matrix[worse]
        margins = np.asarray(model.decision_function(difference), dtype=np.float64)
        reverse = np.asarray(model.decision_function(-difference), dtype=np.float64)
        anti_symmetry = max(anti_symmetry, float(np.max(np.abs(margins + reverse))))
        if margins.shape != (len(rows),) or not np.isfinite(margins).all():
            raise BaselineError("invalid margins")
        pair_semantics = [semantics[pair_key(row)] for row in rows]
        all_metrics[split], task_rows = metrics_for_pool(rows, margins, pair_semantics)
        all_task_rows.extend({"split": split, **row} for row in task_rows)
        for index, (row, semantic, margin) in enumerate(zip(rows, pair_semantics, margins)):
            all_pair_rows.append({
                "split": split,
                "index": index,
                "task": row["task"],
                "parent": row["parent"],
                "better": row["better"],
                "worse": row["worse"],
                "better_run": runs[row["better"]],
                "worse_run": runs[row["worse"]],
                "semantics": semantic,
                "margin": float(margin),
                "correct": bool(margin > 0),
                "tie": bool(margin == 0),
            })
    if anti_symmetry > 1e-8:
        raise BaselineError("pair prediction is not antisymmetric")

    vocabulary = sorted((term, int(index)) for term, index in vectorizer.vocabulary_.items())
    summary = {
        "protocol": PROTOCOL,
        "status": "BASELINE_VALID",
        "evidence_level": "retrospective_same_pool_baseline",
        "inputs": {
            role: {"sha256": EXPECTED[role][0], "bytes": EXPECTED[role][1]}
            for role in ("cards", "train", "dev", "test", "draft", "improve")
        },
        "card_inventory": card_inventory,
        "integrity": integrity,
        "model": {
            "code_prefix_chars": 20000,
            "vectorizer": {"analyzer": "char_wb", "ngram_range": [3, 5], "max_features": 30000, "min_df": 3, "sublinear_tf": True, "dtype": "float64"},
            "logistic_regression": {"C": 0.5, "max_iter": 1500, "solver": "lbfgs", "random_state": 0, "n_iter": int(model.n_iter_[0])},
            "train_endpoints": len(train_ids),
            "all_endpoints": len(card_ids),
            "vocabulary_size": len(vocabulary),
            "vocabulary_sha256": hashlib.sha256(compact(vocabulary).encode()).hexdigest(),
            "idf_sha256": hashlib.sha256(np.asarray(vectorizer.idf_, dtype="<f8").tobytes()).hexdigest(),
            "coefficient_sha256": hashlib.sha256(np.asarray(model.coef_, dtype="<f8").tobytes()).hexdigest(),
            "intercept": float(model.intercept_[0]),
            "intercept_sha256": hashlib.sha256(np.asarray(model.intercept_, dtype="<f8").tobytes()).hexdigest(),
            "anti_symmetry_max_abs": anti_symmetry,
        },
        "bootstrap": {"replicates": BOOTSTRAP_REPS, "task_seed": TASK_SEED, "parent_seed": PARENT_SEED},
        "metrics": all_metrics,
    }
    return summary, all_pair_rows, all_task_rows


def write_outputs(output: Path, summary: dict[str, Any], pair_rows: list[dict[str, Any]], task_rows: list[dict[str, Any]]) -> None:
    if output.exists():
        raise BaselineError("output directory already exists")
    output.mkdir(parents=True)
    (output / "summary.json").write_bytes(canonical(summary))
    with (output / "per_pair.jsonl").open("x", encoding="utf-8", newline="\n") as handle:
        for row in pair_rows:
            handle.write(compact(row) + "\n")
    with (output / "per_task.csv").open("x", encoding="utf-8", newline="") as handle:
        fields = ("split", "subset", "task", "pairs", "accuracy")
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(task_rows)
    manifest = {
        name: sha256_file(output / name)
        for name in ("summary.json", "per_pair.jsonl", "per_task.csv")
    }
    (output / "artifact_manifest.json").write_bytes(canonical(manifest))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cards", type=Path)
    parser.add_argument("train", type=Path)
    parser.add_argument("dev", type=Path)
    parser.add_argument("test", type=Path)
    parser.add_argument("draft", type=Path)
    parser.add_argument("improve", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    summary, pair_rows, task_rows = analyze(
        arguments.cards, arguments.train, arguments.dev, arguments.test,
        arguments.draft, arguments.improve,
    )
    write_outputs(arguments.output, summary, pair_rows, task_rows)
    print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
