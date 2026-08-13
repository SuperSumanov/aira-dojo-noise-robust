#!/usr/bin/env python3
"""Independent refit verifier for the prospective fixed decision scorer.

This module deliberately does not import ``fixed_decision_scorer``.  It
re-opens the hash-locked train-only inputs, independently rebuilds both feature
families, refits both models, and compares model arrays and reference scores.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import warnings
from pathlib import Path
from typing import Any, Sequence

import numpy as np


SEED = 887
PROTOCOL = "prospective_decision_v1"
MODEL_FORMAT = "fixed_decision_scorer_npz_v1"
EXPECTED = {
    "pairs": 4_263,
    "train_runs": 333,
    "tasks": 23,
    "parents": 2_293,
    "endpoints": 5_499,
    "precutoff_runs": 667,
}
OP_NAMES = ("draft", "debug", "improve", "other")
IMPORT_RX = re.compile(r"^\s*(?:from|import)\s+([\w.]+)", re.M)
MODEL_WORDS = (
    "lightgbm", "xgboost", "catboost", "randomforest", "logisticregression",
    "ridge", "svc", "torch", "transformers", "bert", "resnet",
    "efficientnet", "timm", "keras", "sklearn",
)
CV_WORDS = ("kfold", "stratifiedkfold", "groupkfold", "cross_val", "train_test_split")
RISK_WORDS = (
    "fit_transform(test", "fit(test", ".append(test", "concat([train, test",
    "pd.concat([train,test",
)


class VerificationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def reject_forbidden_path(path: Path) -> None:
    if any(token in path.name.lower() for token in ("frozen", "test", "held")):
        raise VerificationError(f"forbidden train input path: {path}")


def task_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("desc") or "")
    return str(value or "")


def code_view(code: str) -> str:
    return code if len(code) <= 20_000 else code[:5_000] + "\n# <FIXED_HEAD_TAIL_TRUNCATION>\n" + code[-15_000:]


def normalized_op(value: Any) -> str:
    op = str(value or "").strip().lower()
    return op if op in OP_NAMES[:-1] else "other"


def static_feature_dict(card: dict[str, Any]) -> dict[str, float]:
    code = str(card["code"])
    low = code.lower()
    lineage = card["lineage"]
    values = {
        "code_len": float(len(code)),
        "n_lines": float(code.count("\n")),
        "n_imports": float(len(set(IMPORT_RX.findall(code)))),
        "depth": float(lineage.get("depth") or 0),
        "step": float(lineage.get("step") or 0),
        "n_sibs": float(lineage.get("n_siblings") or 0),
        "n_cv": float(sum(low.count(word) for word in CV_WORDS)),
        "n_seed": float(low.count("seed") + low.count("random_state")),
        "n_ensemble": float(low.count("ensemble") + low.count("blend") + low.count("stack") + low.count("mean(")),
        "n_earlystop": float(low.count("early_stop")),
        "n_hpsearch": float(low.count("optuna") + low.count("gridsearch") + low.count("param_grid") + low.count("hyperopt")),
        "n_augment": float(low.count("augment") + low.count("transform")),
        "n_try": float(low.count("try:")),
        "n_print": float(code.count("print(")),
        "n_comment": float(code.count("#")),
        "n_fold_int": float(max([int(item) for item in re.findall(r"n_splits\s*=\s*(\d+)", code)] or [0])),
        "n_epoch_int": float(max([int(item) for item in re.findall(r"epochs?\s*=\s*(\d+)", code)] or [0])),
        "risk_leak": float(sum(low.count(word) for word in RISK_WORDS)),
        "has_gpu": float("cuda" in low),
    }
    for word in MODEL_WORDS:
        values[f"m_{word}"] = float(word in low)
    op = normalized_op(lineage.get("op"))
    for name in OP_NAMES:
        values[f"op_{name}"] = float(op == name)
    return values


def load_inputs(args: argparse.Namespace) -> tuple[
    dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, str], list[str]
]:
    for path in (args.pairs, args.run_map, args.cards, args.manifest, args.manifest_summary):
        reject_forbidden_path(path)
    expected_hashes = (
        (args.pairs, args.expect_pairs_sha256),
        (args.run_map, args.expect_run_map_sha256),
        (args.cards, args.expect_cards_sha256),
        (args.manifest, args.expect_manifest_sha256),
        (args.manifest_summary, args.expect_manifest_summary_sha256),
    )
    if any(sha256(path) != expected.lower() for path, expected in expected_hashes):
        raise VerificationError("input SHA mismatch")
    manifest = [
        json.loads(line) for line in args.manifest.read_text(encoding="utf-8").splitlines() if line
    ]
    ids = [str(row["card_id"]) for row in manifest]
    if ids != sorted(ids) or len(ids) != len(set(ids)) or len(ids) != EXPECTED["endpoints"]:
        raise VerificationError("manifest inventory mismatch")
    manifest_summary = json.loads(args.manifest_summary.read_text(encoding="utf-8"))
    if (
        manifest_summary.get("status") != "MANIFEST_COMPLETE"
        or manifest_summary.get("expected_split") != "train"
        or manifest_summary.get("outputs", {}).get("manifest_sha256") != sha256(args.manifest)
    ):
        raise VerificationError("manifest summary mismatch")
    metadata = {str(row["card_id"]): row for row in manifest}
    run_map = {
        str(key): str(value)
        for key, value in json.loads(args.run_map.read_text(encoding="utf-8")).items()
    }
    precutoff_runs = sorted(set(run_map.values()))
    if len(precutoff_runs) != EXPECTED["precutoff_runs"]:
        raise VerificationError("pre-cutoff run inventory mismatch")

    cards: dict[str, dict[str, Any]] = {}
    cards_digest = hashlib.sha256()
    with args.cards.open("rb") as handle:
        for raw_line in handle:
            cards_digest.update(raw_line)
            raw = json.loads(raw_line)
            card_id = str(raw["id"])
            if card_id not in metadata:
                continue
            if card_id in cards:
                raise VerificationError(f"duplicate selected card: {card_id}")
            meta = metadata[card_id]
            code = str(raw.get("code") or "")
            lineage = dict(raw.get("lineage") or {})
            if (
                not code
                or hashlib.sha256(code.encode("utf-8")).hexdigest() != str(meta["code_sha256"])
                or len(code) != int(meta["code_chars"])
                or task_name(raw.get("task")) != str(meta["task"])
                or str(raw.get("run_id")) != str(meta["run_id"])
            ):
                raise VerificationError(f"selected card mismatch: {card_id}")
            cards[card_id] = {
                "code": code,
                "task": str(meta["task"]),
                "run": str(meta["run_id"]),
                "lineage": {key: lineage.get(key) for key in ("depth", "step", "n_siblings", "op")},
            }
    if cards_digest.hexdigest() != args.expect_cards_sha256.lower() or set(cards) != set(metadata):
        raise VerificationError("card SHA/coverage mismatch")

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for line_number, line in enumerate(args.pairs.read_text(encoding="utf-8").splitlines(), 1):
        if not line:
            continue
        raw = json.loads(line)
        if str(raw.get("intask_split")) != "train" or int(raw.get("budget", -1)) != 0:
            raise VerificationError(f"non-train pair: {line_number}")
        better, worse = str(raw["better"]), str(raw["worse"])
        canonical = tuple(sorted((better, worse)))
        if better == worse or canonical in seen:
            raise VerificationError(f"duplicate/degenerate pair: {line_number}")
        seen.add(canonical)
        task, run = str(raw["task"]), str(raw["run_id"])
        for card_id in (better, worse):
            meta = metadata.get(card_id)
            if (
                meta is None
                or str(meta["task"]) != task
                or str(meta["run_id"]) != run
                or run_map.get(card_id) != run
            ):
                raise VerificationError(f"pair context mismatch: {line_number}")
        gap = float(raw["gap_raw"])
        if not math.isfinite(gap) or gap <= 0:
            raise VerificationError(f"invalid gap: {line_number}")
        rows.append(
            {
                "better": better,
                "worse": worse,
                "task": task,
                "run": run,
                "parent": str(raw["parent"]),
            }
        )
    if len(rows) != EXPECTED["pairs"]:
        raise VerificationError("pair count mismatch")
    inventories = {
        "train_runs": len({row["run"] for row in rows}),
        "tasks": len({row["task"] for row in rows}),
        "parents": len({row["parent"] for row in rows}),
    }
    if any(inventories[key] != EXPECTED[key] for key in inventories):
        raise VerificationError(f"pair inventory mismatch: {inventories}")
    return cards, rows, run_map, precutoff_runs


def symmetric(differences: Any) -> tuple[Any, np.ndarray]:
    if hasattr(differences, "tocsr"):
        from scipy import sparse

        design = sparse.vstack([differences, -differences], format="csr")
    else:
        design = np.vstack([differences, -differences])
    labels = np.concatenate(
        [np.ones(differences.shape[0], dtype=np.int8), np.zeros(differences.shape[0], dtype=np.int8)]
    )
    return design, labels


def independent_refit(
    cards: dict[str, dict[str, Any]], rows: Sequence[dict[str, Any]]
) -> tuple[dict[str, np.ndarray], dict[str, dict[str, float]]]:
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    ids = sorted(cards)
    position = {card_id: index for index, card_id in enumerate(ids)}
    better = np.asarray([position[str(row["better"])] for row in rows], dtype=np.int64)
    worse = np.asarray([position[str(row["worse"])] for row in rows], dtype=np.int64)
    names = sorted(static_feature_dict(cards[ids[0]]))
    matrix = np.asarray(
        [[static_feature_dict(cards[card_id])[name] for name in names] for card_id in ids],
        dtype=np.float64,
    )
    static_design, labels = symmetric(matrix[better] - matrix[worse])
    scaler = StandardScaler(with_mean=False).fit(static_design)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        static_model = LogisticRegression(
            C=1.0, fit_intercept=False, max_iter=2_000, random_state=SEED,
            solver="liblinear", tol=1e-6,
        ).fit(scaler.transform(static_design), labels)
    if any(issubclass(item.category, ConvergenceWarning) for item in caught):
        raise VerificationError("static convergence warning")

    vectorizer = TfidfVectorizer(
        analyzer="char_wb", dtype=np.float64, max_features=30_000, min_df=3,
        ngram_range=(3, 5), sublinear_tf=True,
    )
    tfidf = vectorizer.fit_transform([code_view(cards[card_id]["code"]) for card_id in ids])
    tfidf_design, tfidf_labels = symmetric(tfidf[better] - tfidf[worse])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        tfidf_model = LogisticRegression(
            C=0.5, fit_intercept=False, max_iter=2_000, random_state=SEED,
            solver="liblinear", tol=1e-6,
        ).fit(tfidf_design, tfidf_labels)
    if any(issubclass(item.category, ConvergenceWarning) for item in caught):
        raise VerificationError("TF-IDF convergence warning")
    terms = np.empty(len(vectorizer.vocabulary_), dtype=f"<U{max(map(len, vectorizer.vocabulary_))}")
    for term, index in vectorizer.vocabulary_.items():
        terms[int(index)] = term
    static_scores = np.asarray(
        static_model.decision_function(scaler.transform(matrix)), dtype=np.float64
    ).reshape(-1)
    tfidf_scores = np.asarray(tfidf @ tfidf_model.coef_.reshape(-1), dtype=np.float64).reshape(-1)
    arrays = {
        "format": np.asarray([MODEL_FORMAT]),
        "protocol": np.asarray([PROTOCOL]),
        "seed": np.asarray([SEED], dtype=np.int64),
        "static_feature_names": np.asarray(names),
        "static_scale": np.asarray(scaler.scale_, dtype="<f8"),
        "static_coef": np.asarray(static_model.coef_.reshape(-1), dtype="<f8"),
        "tfidf_terms": terms,
        "tfidf_idf": np.asarray(vectorizer.idf_, dtype="<f8"),
        "tfidf_coef": np.asarray(tfidf_model.coef_.reshape(-1), dtype="<f8"),
    }
    scores = {
        card_id: {
            "static_lr": float(static_scores[index]),
            "char_tfidf_lr": float(tfidf_scores[index]),
        }
        for index, card_id in enumerate(ids)
    }
    return arrays, scores


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", required=True, type=Path)
    parser.add_argument("--run-map", required=True, type=Path)
    parser.add_argument("--cards", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--manifest-summary", required=True, type=Path)
    parser.add_argument("--result-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expect-pairs-sha256", required=True)
    parser.add_argument("--expect-run-map-sha256", required=True)
    parser.add_argument("--expect-cards-sha256", required=True)
    parser.add_argument("--expect-manifest-sha256", required=True)
    parser.add_argument("--expect-manifest-summary-sha256", required=True)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    producer_path = args.result_dir / "summary.json"
    bundle_path = args.result_dir / "fixed_scorer.npz"
    reference_path = args.result_dir / "train_reference_scores.csv"
    denylist_path = args.result_dir / "precutoff_runs.txt"
    producer = json.loads(producer_path.read_text(encoding="utf-8"))
    if producer.get("status") != "SCORER_FREEZE_COMPLETE" or producer.get("protocol") != PROTOCOL:
        raise VerificationError("producer status/protocol mismatch")
    if producer.get("frozen_read") is not False:
        raise VerificationError("producer frozen-read flag mismatch")
    cards, rows, _, precutoff_runs = load_inputs(args)
    expected_arrays, expected_scores = independent_refit(cards, rows)
    with np.load(bundle_path, allow_pickle=False) as data:
        if set(data.files) != set(expected_arrays):
            raise VerificationError("bundle key mismatch")
        stored_arrays = {key: np.asarray(data[key]) for key in data.files}
    array_max_abs: dict[str, float] = {}
    for key, expected in expected_arrays.items():
        stored = stored_arrays[key]
        if stored.dtype.kind in "US" or expected.dtype.kind in "US":
            if not np.array_equal(stored.astype(str), expected.astype(str)):
                raise VerificationError(f"bundle string array mismatch: {key}")
            array_max_abs[key] = 0.0
        else:
            if stored.shape != expected.shape or not np.allclose(stored, expected, atol=1e-10, rtol=1e-10):
                difference = math.inf if stored.shape != expected.shape else float(np.max(np.abs(stored - expected)))
                raise VerificationError(f"bundle numeric array mismatch: {key} max={difference}")
            array_max_abs[key] = float(np.max(np.abs(stored - expected))) if stored.size else 0.0

    with reference_path.open("r", encoding="utf-8", newline="") as handle:
        reference = list(csv.DictReader(handle))
    if len(reference) != len(cards) or [row["card_id"] for row in reference] != sorted(cards):
        raise VerificationError("reference score inventory mismatch")
    score_max_abs = 0.0
    for row in reference:
        card_id = row["card_id"]
        if row["task"] != cards[card_id]["task"] or row["run_id"] != cards[card_id]["run"]:
            raise VerificationError(f"reference context mismatch: {card_id}")
        for arm in ("static_lr", "char_tfidf_lr"):
            difference = abs(float(row[arm]) - expected_scores[card_id][arm])
            score_max_abs = max(score_max_abs, difference)
            if difference > 1e-10:
                raise VerificationError(f"reference score mismatch: {card_id} {arm}")
    denylist = denylist_path.read_text(encoding="utf-8").splitlines()
    if denylist != precutoff_runs or len(denylist) != len(set(denylist)):
        raise VerificationError("pre-cutoff denylist mismatch")
    expected_output_hashes = {
        "fixed_scorer_sha256": sha256(bundle_path),
        "train_reference_scores_sha256": sha256(reference_path),
        "precutoff_runs_sha256": sha256(denylist_path),
    }
    for key, value in expected_output_hashes.items():
        if producer.get("outputs", {}).get(key) != value:
            raise VerificationError(f"producer output SHA mismatch: {key}")
    expected_inventory = {
        "pairs": len(rows),
        "train_runs": len({row["run"] for row in rows}),
        "tasks": len({row["task"] for row in rows}),
        "parents": len({row["parent"] for row in rows}),
        "endpoints": len(cards),
        "precutoff_runs": len(precutoff_runs),
    }
    if producer.get("inventory") != expected_inventory:
        raise VerificationError("producer inventory mismatch")
    integrity = {
        "array_refit_match": True,
        "input_hashes_exact": True,
        "inventory_exact": expected_inventory == EXPECTED,
        "frozen_read_false": True,
        "label_fields_retained_zero": True,
        "post_execution_fields_retained_zero": True,
        "precutoff_denylist_exact": True,
        "reference_scores_match": score_max_abs <= 1e-10,
        "producer_output_hashes_exact": True,
    }
    if not all(integrity.values()):
        raise VerificationError(f"verification integrity failed: {integrity}")
    output = {
        "status": "VERIFIED_SCORER_FREEZE_COMPLETE",
        "protocol": PROTOCOL,
        "producer_summary_sha256": sha256(producer_path),
        "fixed_scorer_sha256": sha256(bundle_path),
        "train_reference_scores_sha256": sha256(reference_path),
        "precutoff_runs_sha256": sha256(denylist_path),
        "inventory": expected_inventory,
        "array_max_abs": array_max_abs,
        "reference_score_max_abs": score_max_abs,
        "integrity": integrity,
        "frozen_read": False,
    }
    atomic_json(args.output, output)
    print(
        "VERIFIED_SCORER_FREEZE_COMPLETE",
        f"endpoints={len(cards)}",
        f"precutoff_runs={len(precutoff_runs)}",
        f"reference_score_max_abs={score_max_abs:.3g}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
