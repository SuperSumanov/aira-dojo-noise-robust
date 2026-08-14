#!/usr/bin/env python3
"""Freeze and apply label-blind decision scorers for prospective runs.

The ``build`` command fits the preregistered static and character-TFIDF
Bradley--Terry scorers on the hash-locked v11 train split.  The ``score``
command accepts only a strict code-only manifest and refuses every pre-cutoff
physical run.  No LLM weights are updated.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from .endpoint_denylist import load_endpoint_denylist


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
    "lightgbm",
    "xgboost",
    "catboost",
    "randomforest",
    "logisticregression",
    "ridge",
    "svc",
    "torch",
    "transformers",
    "bert",
    "resnet",
    "efficientnet",
    "timm",
    "keras",
    "sklearn",
)
CV_WORDS = ("kfold", "stratifiedkfold", "groupkfold", "cross_val", "train_test_split")
RISK_WORDS = (
    "fit_transform(test",
    "fit(test",
    ".append(test",
    "concat([train, test",
    "pd.concat([train,test",
)
BLIND_TOP_LEVEL_KEYS = {
    "card_id",
    "task",
    "run_id",
    "code",
    "code_sha256",
    "lineage",
    "generation_started_at_utc",
    "source_sha256",
}
BLIND_LINEAGE_KEYS = {"depth", "step", "n_siblings", "op", "parent"}


class IntegrityError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise IntegrityError(f"invalid UTC timestamp: {value!r}") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise IntegrityError(f"timestamp is not explicit UTC: {value!r}")
    return parsed.astimezone(timezone.utc)


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def atomic_npz(path: Path, **arrays: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.npz")
    np.savez_compressed(temporary, **arrays)
    os.replace(temporary, path)


def git_commit(repo_root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()


def reject_forbidden_path(path: Path, label: str) -> None:
    found = [token for token in ("frozen", "test", "held") if token in path.name.lower()]
    if found:
        raise IntegrityError(f"{label} path contains forbidden token(s): {found}")


def task_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("desc") or "")
    return str(value or "")


def code_view(code: str) -> str:
    if len(code) <= 20_000:
        return code
    return code[:5_000] + "\n# <FIXED_HEAD_TAIL_TRUNCATION>\n" + code[-15_000:]


def normalized_op(value: Any) -> str:
    op = str(value or "").strip().lower()
    return op if op in OP_NAMES[:-1] else "other"


def static_feature_dict(card: dict[str, Any]) -> dict[str, float]:
    code = str(card["code"])
    low = code.lower()
    lineage = card["lineage"]
    imports = set(IMPORT_RX.findall(code))
    values = {
        "code_len": float(len(code)),
        "n_lines": float(code.count("\n")),
        "n_imports": float(len(imports)),
        "depth": float(lineage.get("depth") or 0),
        "step": float(lineage.get("step") or 0),
        "n_sibs": float(lineage.get("n_siblings") or 0),
        "n_cv": float(sum(low.count(word) for word in CV_WORDS)),
        "n_seed": float(low.count("seed") + low.count("random_state")),
        "n_ensemble": float(
            low.count("ensemble")
            + low.count("blend")
            + low.count("stack")
            + low.count("mean(")
        ),
        "n_earlystop": float(low.count("early_stop")),
        "n_hpsearch": float(
            low.count("optuna")
            + low.count("gridsearch")
            + low.count("param_grid")
            + low.count("hyperopt")
        ),
        "n_augment": float(low.count("augment") + low.count("transform")),
        "n_try": float(low.count("try:")),
        "n_print": float(code.count("print(")),
        "n_comment": float(code.count("#")),
        "n_fold_int": float(
            max([int(item) for item in re.findall(r"n_splits\s*=\s*(\d+)", code)] or [0])
        ),
        "n_epoch_int": float(
            max([int(item) for item in re.findall(r"epochs?\s*=\s*(\d+)", code)] or [0])
        ),
        "risk_leak": float(sum(low.count(word) for word in RISK_WORDS)),
        "has_gpu": float("cuda" in low),
    }
    for word in MODEL_WORDS:
        values[f"m_{word}"] = float(word in low)
    op = normalized_op(lineage.get("op"))
    for name in OP_NAMES:
        values[f"op_{name}"] = float(op == name)
    return values


def load_manifest(
    path: Path,
    summary_path: Path,
    expected_sha: str,
    expected_summary_sha: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reject_forbidden_path(path, "train endpoint manifest")
    reject_forbidden_path(summary_path, "train endpoint manifest summary")
    if sha256(path) != expected_sha.lower() or sha256(summary_path) != expected_summary_sha.lower():
        raise IntegrityError("manifest or manifest-summary SHA mismatch")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    ids = [str(row["card_id"]) for row in rows]
    if ids != sorted(ids) or len(ids) != len(set(ids)) or len(ids) != EXPECTED["endpoints"]:
        raise IntegrityError("manifest inventory mismatch")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("status") != "MANIFEST_COMPLETE" or summary.get("expected_split") != "train":
        raise IntegrityError("manifest summary is not complete train-only data")
    if summary.get("outputs", {}).get("manifest_sha256") != sha256(path):
        raise IntegrityError("manifest summary output SHA mismatch")
    return rows, summary


def load_run_map(path: Path, expected_sha: str) -> tuple[dict[str, str], list[str]]:
    reject_forbidden_path(path, "run map")
    if sha256(path) != expected_sha.lower():
        raise IntegrityError("run-map SHA mismatch")
    raw = json.loads(path.read_text(encoding="utf-8"))
    run_map = {str(key): str(value) for key, value in raw.items()}
    runs = sorted(set(run_map.values()))
    if len(runs) != EXPECTED["precutoff_runs"]:
        raise IntegrityError(f"pre-cutoff run count mismatch: {len(runs)}")
    return run_map, runs


def load_pairs(
    path: Path,
    manifest: Sequence[dict[str, Any]],
    run_map: dict[str, str],
    expected_sha: str,
) -> list[dict[str, Any]]:
    reject_forbidden_path(path, "training pairs")
    if sha256(path) != expected_sha.lower():
        raise IntegrityError("pair SHA mismatch")
    metadata = {str(row["card_id"]): row for row in manifest}
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line:
            continue
        raw = json.loads(line)
        if str(raw.get("intask_split")) != "train" or int(raw.get("budget", -1)) != 0:
            raise IntegrityError(f"non-train pair at line {line_number}")
        better, worse = str(raw["better"]), str(raw["worse"])
        canonical = tuple(sorted((better, worse)))
        if better == worse or canonical in seen:
            raise IntegrityError(f"duplicate/degenerate pair at line {line_number}")
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
                raise IntegrityError(f"pair context mismatch at line {line_number}")
        gap = float(raw["gap_raw"])
        if not math.isfinite(gap) or gap <= 0:
            raise IntegrityError(f"invalid gap at line {line_number}")
        rows.append(
            {
                "task": task,
                "run": run,
                "parent": str(raw["parent"]),
                "better": better,
                "worse": worse,
                "gap_raw": gap,
            }
        )
    endpoints = {str(row[key]) for row in rows for key in ("better", "worse")}
    if len(rows) != EXPECTED["pairs"] or endpoints != set(metadata):
        raise IntegrityError("pair inventory mismatch")
    counts = {
        "train_runs": len({row["run"] for row in rows}),
        "tasks": len({row["task"] for row in rows}),
        "parents": len({row["parent"] for row in rows}),
    }
    for key, value in counts.items():
        if value != EXPECTED[key]:
            raise IntegrityError(f"pair {key} mismatch: {value}")
    return rows


def load_train_cards(
    cards_path: Path,
    manifest: Sequence[dict[str, Any]],
    expected_sha: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    reject_forbidden_path(cards_path, "source cards")
    expected = {str(row["card_id"]): row for row in manifest}
    found: dict[str, dict[str, Any]] = {}
    digest = hashlib.sha256()
    corpus_rows = 0
    with cards_path.open("rb") as handle:
        for raw_line in handle:
            digest.update(raw_line)
            corpus_rows += 1
            raw = json.loads(raw_line)
            card_id = str(raw["id"])
            if card_id not in expected:
                continue
            if card_id in found:
                raise IntegrityError(f"duplicate selected card: {card_id}")
            meta = expected[card_id]
            code = str(raw.get("code") or "")
            lineage = dict(raw.get("lineage") or {})
            if not code or hashlib.sha256(code.encode("utf-8")).hexdigest() != str(meta["code_sha256"]):
                raise IntegrityError(f"selected code mismatch: {card_id}")
            if len(code) != int(meta["code_chars"]):
                raise IntegrityError(f"selected code length mismatch: {card_id}")
            if task_name(raw.get("task")) != str(meta["task"]):
                raise IntegrityError(f"selected task mismatch: {card_id}")
            if str(raw.get("run_id")) != str(meta["run_id"]):
                raise IntegrityError(f"selected run mismatch: {card_id}")
            found[card_id] = {
                "id": card_id,
                "task": str(meta["task"]),
                "run": str(meta["run_id"]),
                "code": code,
                "lineage": {
                    "depth": lineage.get("depth"),
                    "step": lineage.get("step"),
                    "n_siblings": lineage.get("n_siblings"),
                    "op": lineage.get("op"),
                },
            }
    if digest.hexdigest() != expected_sha.lower() or set(found) != set(expected):
        raise IntegrityError("cards SHA or selected coverage mismatch")
    retained = sorted({key for card in found.values() for key in card})
    if retained != ["code", "id", "lineage", "run", "task"]:
        raise IntegrityError(f"unexpected retained card keys: {retained}")
    return found, {
        "cards_sha256": digest.hexdigest(),
        "corpus_rows_scanned": corpus_rows,
        "selected_endpoints": len(found),
        "retained_keys": retained,
        "label_fields_retained": 0,
        "post_execution_fields_retained": 0,
    }


def pair_differences(
    matrix: Any,
    position: dict[str, int],
    rows: Sequence[dict[str, Any]],
) -> Any:
    better = np.asarray([position[str(row["better"])] for row in rows], dtype=np.int64)
    worse = np.asarray([position[str(row["worse"])] for row in rows], dtype=np.int64)
    return matrix[better] - matrix[worse]


def symmetric_design(differences: Any) -> tuple[Any, np.ndarray]:
    if hasattr(differences, "tocsr"):
        from scipy import sparse

        design = sparse.vstack([differences, -differences], format="csr")
    else:
        design = np.vstack([differences, -differences])
    labels = np.concatenate(
        [np.ones(differences.shape[0], dtype=np.int8), np.zeros(differences.shape[0], dtype=np.int8)]
    )
    return design, labels


def fit_bundle(
    cards: dict[str, dict[str, Any]], rows: Sequence[dict[str, Any]]
) -> tuple[dict[str, np.ndarray], dict[str, Any], dict[str, dict[str, float]]]:
    from scipy import sparse
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    started = time.perf_counter()
    ids = sorted(cards)
    position = {card_id: index for index, card_id in enumerate(ids)}
    names = sorted(static_feature_dict(cards[ids[0]]))
    static_matrix = np.asarray(
        [[static_feature_dict(cards[card_id])[name] for name in names] for card_id in ids],
        dtype=np.float64,
    )
    static_diff = pair_differences(static_matrix, position, rows)
    static_design, labels = symmetric_design(static_diff)
    scaler = StandardScaler(with_mean=False).fit(static_design)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        static_model = LogisticRegression(
            C=1.0,
            fit_intercept=False,
            max_iter=2_000,
            random_state=SEED,
            solver="liblinear",
            tol=1e-6,
        ).fit(scaler.transform(static_design), labels)
    convergence = [str(item.message) for item in caught if issubclass(item.category, ConvergenceWarning)]
    if convergence:
        raise IntegrityError(f"static LR convergence warning: {convergence}")

    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        dtype=np.float64,
        max_features=30_000,
        min_df=3,
        ngram_range=(3, 5),
        sublinear_tf=True,
    )
    tfidf_matrix = vectorizer.fit_transform([code_view(str(cards[card_id]["code"])) for card_id in ids])
    tfidf_diff = pair_differences(tfidf_matrix, position, rows)
    tfidf_design, tfidf_labels = symmetric_design(tfidf_diff)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        tfidf_model = LogisticRegression(
            C=0.5,
            fit_intercept=False,
            max_iter=2_000,
            random_state=SEED,
            solver="liblinear",
            tol=1e-6,
        ).fit(tfidf_design, tfidf_labels)
    convergence = [str(item.message) for item in caught if issubclass(item.category, ConvergenceWarning)]
    if convergence:
        raise IntegrityError(f"TF-IDF LR convergence warning: {convergence}")

    terms = np.empty(len(vectorizer.vocabulary_), dtype=f"<U{max(map(len, vectorizer.vocabulary_))}")
    for term, index in vectorizer.vocabulary_.items():
        terms[int(index)] = term
    static_scores = np.asarray(
        static_model.decision_function(scaler.transform(static_matrix)), dtype=np.float64
    ).reshape(-1)
    tfidf_scores = np.asarray(
        tfidf_matrix @ tfidf_model.coef_.reshape(-1), dtype=np.float64
    ).reshape(-1)
    if not all(
        np.isfinite(value).all()
        for value in (
            static_matrix,
            scaler.scale_,
            static_model.coef_,
            vectorizer.idf_,
            tfidf_model.coef_,
            static_scores,
            tfidf_scores,
        )
    ):
        raise IntegrityError("non-finite fitted scorer array")
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
    diagnostics = {
        "elapsed_s": time.perf_counter() - started,
        "static": {
            "features": len(names),
            "iterations": int(static_model.n_iter_[0]),
            "scale_min": float(np.min(scaler.scale_)),
            "scale_max": float(np.max(scaler.scale_)),
            "coefficient_norm": float(np.linalg.norm(static_model.coef_)),
            "training_rows_symmetric": int(static_design.shape[0]),
        },
        "tfidf": {
            "vocabulary": len(vectorizer.vocabulary_),
            "iterations": int(tfidf_model.n_iter_[0]),
            "coefficient_norm": float(np.linalg.norm(tfidf_model.coef_)),
            "training_rows_symmetric": int(tfidf_design.shape[0]),
            "training_matrix_nnz": int(sparse.csr_matrix(tfidf_design).nnz),
            "truncated_codes": sum(len(str(cards[card_id]["code"])) > 20_000 for card_id in ids),
            "vocabulary_sha256": json_digest(
                [(str(term), index) for index, term in enumerate(terms.tolist())]
            ),
            "idf_sha256": hashlib.sha256(arrays["tfidf_idf"].tobytes()).hexdigest(),
        },
    }
    return arrays, diagnostics, scores


def load_bundle(path: Path) -> dict[str, np.ndarray]:
    required = {
        "format",
        "protocol",
        "seed",
        "static_feature_names",
        "static_scale",
        "static_coef",
        "tfidf_terms",
        "tfidf_idf",
        "tfidf_coef",
    }
    with np.load(path, allow_pickle=False) as data:
        if set(data.files) != required:
            raise IntegrityError(f"scorer bundle keys differ: {sorted(data.files)}")
        arrays = {key: np.asarray(data[key]).copy() for key in data.files}
    if str(arrays["format"][0]) != MODEL_FORMAT or str(arrays["protocol"][0]) != PROTOCOL:
        raise IntegrityError("scorer bundle protocol/format mismatch")
    if int(arrays["seed"][0]) != SEED:
        raise IntegrityError("scorer seed mismatch")
    if len(set(map(str, arrays["static_feature_names"]))) != len(arrays["static_feature_names"]):
        raise IntegrityError("duplicate static feature name")
    if len(set(map(str, arrays["tfidf_terms"]))) != len(arrays["tfidf_terms"]):
        raise IntegrityError("duplicate TF-IDF term")
    for name in ("static_scale", "static_coef", "tfidf_idf", "tfidf_coef"):
        if not np.isfinite(arrays[name]).all():
            raise IntegrityError(f"non-finite bundle array: {name}")
    if np.any(arrays["static_scale"] <= 0) or np.any(arrays["tfidf_idf"] <= 0):
        raise IntegrityError("invalid scaler/IDF values")
    if len(arrays["static_scale"]) != len(arrays["static_coef"]) or len(
        arrays["static_scale"]
    ) != len(arrays["static_feature_names"]):
        raise IntegrityError("static bundle shape mismatch")
    if len(arrays["tfidf_terms"]) != len(arrays["tfidf_idf"]) or len(
        arrays["tfidf_terms"]
    ) != len(arrays["tfidf_coef"]):
        raise IntegrityError("TF-IDF bundle shape mismatch")
    return arrays


def score_cards(
    cards: dict[str, dict[str, Any]], arrays: dict[str, np.ndarray]
) -> dict[str, dict[str, float]]:
    from sklearn.feature_extraction.text import TfidfVectorizer

    ids = sorted(cards)
    names = [str(item) for item in arrays["static_feature_names"].tolist()]
    matrix = np.asarray(
        [[static_feature_dict(cards[card_id])[name] for name in names] for card_id in ids],
        dtype=np.float64,
    )
    static_scores = (matrix / arrays["static_scale"]) @ arrays["static_coef"]
    terms = [str(item) for item in arrays["tfidf_terms"].tolist()]
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        dtype=np.float64,
        ngram_range=(3, 5),
        sublinear_tf=True,
        vocabulary={term: index for index, term in enumerate(terms)},
    )
    vectorizer.idf_ = np.asarray(arrays["tfidf_idf"], dtype=np.float64)
    tfidf_matrix = vectorizer.transform([code_view(str(cards[card_id]["code"])) for card_id in ids])
    tfidf_scores = np.asarray(tfidf_matrix @ arrays["tfidf_coef"], dtype=np.float64).reshape(-1)
    if not np.isfinite(static_scores).all() or not np.isfinite(tfidf_scores).all():
        raise IntegrityError("non-finite inference score")
    return {
        card_id: {
            "static_lr": float(static_scores[index]),
            "char_tfidf_lr": float(tfidf_scores[index]),
        }
        for index, card_id in enumerate(ids)
    }


def write_reference(path: Path, cards: dict[str, dict[str, Any]], scores: dict[str, dict[str, float]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("card_id", "task", "run_id", "static_lr", "char_tfidf_lr"),
            lineterminator="\n",
        )
        writer.writeheader()
        for card_id in sorted(cards):
            writer.writerow(
                {
                    "card_id": card_id,
                    "task": cards[card_id]["task"],
                    "run_id": cards[card_id]["run"],
                    "static_lr": format(scores[card_id]["static_lr"], ".17g"),
                    "char_tfidf_lr": format(scores[card_id]["char_tfidf_lr"], ".17g"),
                }
            )
    os.replace(temporary, path)


def build(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    for path, label in (
        (args.pairs, "training pairs"),
        (args.run_map, "run map"),
        (args.cards, "source cards"),
        (args.manifest, "train manifest"),
        (args.manifest_summary, "train manifest summary"),
    ):
        reject_forbidden_path(path, label)
    if args.out_dir.exists():
        raise FileExistsError(f"refusing to overwrite output root: {args.out_dir}")
    args.out_dir.mkdir(parents=True)
    manifest, manifest_summary = load_manifest(
        args.manifest,
        args.manifest_summary,
        args.expect_manifest_sha256,
        args.expect_manifest_summary_sha256,
    )
    run_map, precutoff_runs = load_run_map(args.run_map, args.expect_run_map_sha256)
    rows = load_pairs(args.pairs, manifest, run_map, args.expect_pairs_sha256)
    cards, card_audit = load_train_cards(args.cards, manifest, args.expect_cards_sha256)
    arrays, diagnostics, fitted_scores = fit_bundle(cards, rows)
    bundle_path = args.out_dir / "fixed_scorer.npz"
    reference_path = args.out_dir / "train_reference_scores.csv"
    denylist_path = args.out_dir / "precutoff_runs.txt"
    atomic_npz(bundle_path, **arrays)
    write_reference(reference_path, cards, fitted_scores)
    atomic_text(denylist_path, "".join(f"{run}\n" for run in precutoff_runs))

    restored = load_bundle(bundle_path)
    restored_scores = score_cards(cards, restored)
    max_roundtrip = max(
        abs(restored_scores[card_id][arm] - fitted_scores[card_id][arm])
        for card_id in cards
        for arm in ("static_lr", "char_tfidf_lr")
    )
    if max_roundtrip > 1e-12:
        raise IntegrityError(f"bundle round-trip mismatch: {max_roundtrip}")
    input_hashes = {
        "pairs_sha256": sha256(args.pairs),
        "run_map_sha256": sha256(args.run_map),
        "cards_sha256": sha256(args.cards),
        "manifest_sha256": sha256(args.manifest),
        "manifest_summary_sha256": sha256(args.manifest_summary),
    }
    model_key = json_digest(
        {
            "protocol": PROTOCOL,
            "seed": SEED,
            "inputs": input_hashes,
            "arms": ["static_lr", "char_tfidf_lr"],
            "static_c": 1.0,
            "tfidf_c": 0.5,
        }
    )
    runtime = time.perf_counter() - started
    summary = {
        "status": "SCORER_FREEZE_COMPLETE",
        "protocol": PROTOCOL,
        "model_format": MODEL_FORMAT,
        "model_key": model_key,
        "git_commit": git_commit(args.repo_root),
        "built_at_utc": utc_now(),
        "frozen_read": False,
        "configuration": {
            "seed": SEED,
            "arms": ["static_lr", "char_tfidf_lr"],
            "static_lr": {"c": 1.0, "fit_intercept": False, "solver": "liblinear"},
            "char_tfidf_lr": {
                "analyzer": "char_wb",
                "ngram_range": [3, 5],
                "max_features": 30_000,
                "min_df": 3,
                "sublinear_tf": True,
                "code_view": "all_if_le_20000_else_head5000_tail15000",
                "c": 0.5,
                "fit_intercept": False,
                "solver": "liblinear",
            },
        },
        "inputs": input_hashes,
        "inventory": {
            "pairs": len(rows),
            "train_runs": len({row["run"] for row in rows}),
            "tasks": len({row["task"] for row in rows}),
            "parents": len({row["parent"] for row in rows}),
            "endpoints": len(cards),
            "precutoff_runs": len(precutoff_runs),
        },
        "card_audit": card_audit,
        "manifest_summary": manifest_summary,
        "diagnostics": diagnostics,
        "integrity": {
            "expected_inventory_exact": True,
            "frozen_read_false": True,
            "label_fields_retained_zero": card_audit["label_fields_retained"] == 0,
            "post_execution_fields_retained_zero": card_audit["post_execution_fields_retained"] == 0,
            "precutoff_runs_eq_667": len(precutoff_runs) == EXPECTED["precutoff_runs"],
            "roundtrip_max_abs_le_1e_12": max_roundtrip <= 1e-12,
            "wall_cap_pass": runtime <= args.wall_cap_s,
        },
        "outputs": {
            "fixed_scorer": str(bundle_path),
            "fixed_scorer_sha256": sha256(bundle_path),
            "train_reference_scores": str(reference_path),
            "train_reference_scores_sha256": sha256(reference_path),
            "precutoff_runs": str(denylist_path),
            "precutoff_runs_sha256": sha256(denylist_path),
        },
        "runtime_s": runtime,
        "wall_cap_s": args.wall_cap_s,
        "software": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
        "source_sha256": sha256(Path(__file__)),
    }
    if not all(summary["integrity"].values()):
        raise IntegrityError(f"freeze integrity failed: {summary['integrity']}")
    atomic_json(args.out_dir / "summary.json", summary)
    print(
        "SCORER_FREEZE_COMPLETE",
        f"endpoints={len(cards)}",
        f"precutoff_runs={len(precutoff_runs)}",
        f"vocabulary={diagnostics['tfidf']['vocabulary']}",
        f"roundtrip_max_abs={max_roundtrip:.3g}",
        flush=True,
    )
    return 0


def activate(args: argparse.Namespace) -> int:
    output = args.result_dir / "freeze_receipt.json"
    if output.exists():
        raise FileExistsError(f"refusing to overwrite freeze receipt: {output}")
    summary_path = args.result_dir / "summary.json"
    verifier_path = args.result_dir / "independent_verify.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    verifier = json.loads(verifier_path.read_text(encoding="utf-8"))
    if summary.get("status") != "SCORER_FREEZE_COMPLETE":
        raise IntegrityError("producer freeze is incomplete")
    if verifier.get("status") != "VERIFIED_SCORER_FREEZE_COMPLETE":
        raise IntegrityError("independent freeze verification is incomplete")
    bundle_path = args.result_dir / "fixed_scorer.npz"
    denylist_path = args.result_dir / "precutoff_runs.txt"
    if sha256(bundle_path) != summary["outputs"]["fixed_scorer_sha256"]:
        raise IntegrityError("bundle changed after verification")
    if sha256(denylist_path) != summary["outputs"]["precutoff_runs_sha256"]:
        raise IntegrityError("denylist changed after verification")
    receipt = {
        "status": "PROSPECTIVE_SCORER_ACTIVE",
        "protocol": PROTOCOL,
        "activated_at_utc": utc_now(),
        "eligible_generation_start": "strictly_after_activated_at_utc",
        "git_commit": git_commit(args.repo_root),
        "producer_summary_sha256": sha256(summary_path),
        "independent_verify_sha256": sha256(verifier_path),
        "fixed_scorer_sha256": sha256(bundle_path),
        "precutoff_runs_sha256": sha256(denylist_path),
        "precutoff_runs": EXPECTED["precutoff_runs"],
        "frozen_pair_files_read": False,
    }
    atomic_json(output, receipt)
    print(
        "PROSPECTIVE_SCORER_ACTIVE",
        receipt["activated_at_utc"],
        receipt["fixed_scorer_sha256"],
        flush=True,
    )
    return 0


def load_blind_manifest(
    path: Path,
    expected_sha: str,
    denylist: set[str],
    activated_at: datetime,
    precutoff_card_ids: set[str] | None = None,
    precutoff_code_shas: set[str] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if sha256(path) != expected_sha.lower():
        raise IntegrityError("blind-manifest SHA mismatch")
    cards: dict[str, dict[str, Any]] = {}
    runs: set[str] = set()
    sources: set[str] = set()
    previous_id: str | None = None
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line:
            continue
        raw = json.loads(line)
        if set(raw) != BLIND_TOP_LEVEL_KEYS:
            raise IntegrityError(f"blind top-level schema mismatch at line {line_number}")
        lineage = raw["lineage"]
        if not isinstance(lineage, dict) or set(lineage) != BLIND_LINEAGE_KEYS:
            raise IntegrityError(f"blind lineage schema mismatch at line {line_number}")
        if not isinstance(raw["card_id"], str) or not isinstance(raw["run_id"], str):
            raise IntegrityError(f"blind endpoint/run ID type mismatch at line {line_number}")
        card_id, run = raw["card_id"], raw["run_id"]
        if not card_id or (previous_id is not None and card_id <= previous_id):
            raise IntegrityError("blind manifest IDs must be unique and strictly sorted")
        if any(character in card_id for character in "\r\n\t"):
            raise IntegrityError(f"blind endpoint ID contains control whitespace at line {line_number}")
        previous_id = card_id
        if run in denylist:
            raise IntegrityError(f"pre-cutoff run in blind manifest: {run}")
        if precutoff_card_ids is not None and card_id in precutoff_card_ids:
            raise IntegrityError(f"pre-cutoff endpoint ID in blind manifest at line {line_number}")
        generation_started = parse_utc(str(raw["generation_started_at_utc"]))
        if generation_started <= activated_at:
            raise IntegrityError(f"non-prospective generation time at line {line_number}")
        if not isinstance(raw["code"], str):
            raise IntegrityError(f"blind code must be a string at line {line_number}")
        code = raw["code"]
        code_sha = hashlib.sha256(code.encode("utf-8")).hexdigest()
        if not code or code_sha != str(raw["code_sha256"]):
            raise IntegrityError(f"blind code SHA mismatch at line {line_number}")
        if precutoff_code_shas is not None and code_sha in precutoff_code_shas:
            raise IntegrityError(f"pre-cutoff exact code in blind manifest at line {line_number}")
        source_sha = str(raw["source_sha256"]).lower()
        if not re.fullmatch(r"[0-9a-f]{64}", source_sha):
            raise IntegrityError(f"invalid source SHA at line {line_number}")
        if run != f"journal:{source_sha}":
            raise IntegrityError(f"physical run/source identity mismatch at line {line_number}")
        if not isinstance(raw["task"], str) or not raw["task"] or any(
            character in raw["task"] for character in "\r\n\t"
        ):
            raise IntegrityError(f"invalid task at line {line_number}")
        for key in ("depth", "step", "n_siblings"):
            value = lineage[key]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise IntegrityError(f"invalid blind lineage {key} at line {line_number}")
        if lineage["depth"] < 1 or lineage["step"] < 1:
            raise IntegrityError(f"blind endpoint lineage must be non-root at line {line_number}")
        if not isinstance(lineage["parent"], str) or not lineage["parent"]:
            raise IntegrityError(f"blind endpoint parent must be non-empty at line {line_number}")
        if not isinstance(lineage["op"], str) or any(
            character in lineage["op"] for character in "\r\n\t"
        ):
            raise IntegrityError(f"invalid blind lineage op at line {line_number}")
        cards[card_id] = {
            "id": card_id,
            "task": raw["task"],
            "run": run,
            "code": code,
            "lineage": {key: lineage[key] for key in ("depth", "step", "n_siblings", "op")},
            "parent": lineage["parent"],
            "generation_started_at_utc": str(raw["generation_started_at_utc"]),
            "source_sha256": source_sha,
        }
        runs.add(run)
        sources.add(source_sha)
    if not cards:
        raise IntegrityError("empty blind manifest")
    return cards, {
        "endpoints": len(cards),
        "runs": len(runs),
        "tasks": len({card["task"] for card in cards.values()}),
        "sources": len(sources),
        "retained_keys": sorted({key for card in cards.values() for key in card}),
        "labels_read": False,
        "post_execution_fields_read": False,
        "precutoff_endpoint_id_overlap": 0,
        "precutoff_code_sha256_overlap": 0,
    }


def score(args: argparse.Namespace) -> int:
    if args.out_dir.exists():
        raise FileExistsError(f"refusing to overwrite score output: {args.out_dir}")
    summary_path = args.scorer_dir / "summary.json"
    receipt_path = args.scorer_dir / "freeze_receipt.json"
    bundle_path = args.scorer_dir / "fixed_scorer.npz"
    denylist_path = args.scorer_dir / "precutoff_runs.txt"
    if sha256(receipt_path) != args.expect_receipt_sha256.lower():
        raise IntegrityError("freeze-receipt SHA mismatch")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("status") != "PROSPECTIVE_SCORER_ACTIVE":
        raise IntegrityError("scorer is not active")
    if sha256(bundle_path) != receipt["fixed_scorer_sha256"] or sha256(
        denylist_path
    ) != receipt["precutoff_runs_sha256"]:
        raise IntegrityError("active scorer artifact mismatch")
    if sha256(summary_path) != receipt["producer_summary_sha256"]:
        raise IntegrityError("active summary artifact mismatch")
    denylist_lines = denylist_path.read_text(encoding="utf-8").splitlines()
    denylist = set(denylist_lines)
    if len(denylist_lines) != EXPECTED["precutoff_runs"] or len(denylist) != len(denylist_lines):
        raise IntegrityError("active pre-cutoff denylist inventory mismatch")
    precutoff_card_ids, precutoff_code_shas, endpoint_denylist_audit = load_endpoint_denylist(
        args.precutoff_endpoint_denylist,
        args.expect_precutoff_endpoint_denylist_sha256,
        args.expect_precutoff_endpoints,
    )
    cards, audit = load_blind_manifest(
        args.blind_manifest,
        args.expect_blind_manifest_sha256,
        denylist,
        parse_utc(str(receipt["activated_at_utc"])),
        precutoff_card_ids,
        precutoff_code_shas,
    )
    audit["precutoff_endpoint_ids_checked"] = endpoint_denylist_audit["endpoint_ids"]
    audit["precutoff_code_sha256_checked"] = endpoint_denylist_audit["unique_code_sha256"]
    arrays = load_bundle(bundle_path)
    scores = score_cards(cards, arrays)
    temporary_dir = args.out_dir.with_name(f"{args.out_dir.name}.tmp.{os.getpid()}")
    if temporary_dir.exists():
        raise FileExistsError(f"temporary score output already exists: {temporary_dir}")
    temporary_dir.mkdir(parents=True)
    score_path = temporary_dir / "blind_scores.csv"
    temporary = score_path.with_suffix(".tmp.csv")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        fields = (
            "card_id",
            "task",
            "run_id",
            "parent",
            "generation_started_at_utc",
            "source_sha256",
            "static_lr",
            "char_tfidf_lr",
        )
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for card_id in sorted(cards):
            card = cards[card_id]
            writer.writerow(
                {
                    "card_id": card_id,
                    "task": card["task"],
                    "run_id": card["run"],
                    "parent": card["parent"],
                    "generation_started_at_utc": card["generation_started_at_utc"],
                    "source_sha256": card["source_sha256"],
                    "static_lr": format(scores[card_id]["static_lr"], ".17g"),
                    "char_tfidf_lr": format(scores[card_id]["char_tfidf_lr"], ".17g"),
                }
            )
    os.replace(temporary, score_path)
    output = {
        "status": "BLIND_SCORING_COMPLETE",
        "protocol": PROTOCOL,
        "labels_read": False,
        "post_execution_fields_read": False,
        "inputs": {
            "blind_manifest_sha256": sha256(args.blind_manifest),
            "freeze_receipt_sha256": sha256(receipt_path),
            "fixed_scorer_sha256": sha256(bundle_path),
            "precutoff_runs_sha256": sha256(denylist_path),
            "precutoff_endpoint_denylist_sha256": sha256(args.precutoff_endpoint_denylist),
        },
        "audit": audit,
        "outputs": {
            "blind_scores": str(args.out_dir / "blind_scores.csv"),
            "blind_scores_sha256": sha256(score_path),
        },
    }
    atomic_json(temporary_dir / "summary.json", output)
    os.replace(temporary_dir, args.out_dir)
    print(
        "BLIND_SCORING_COMPLETE",
        f"endpoints={audit['endpoints']}",
        f"runs={audit['runs']}",
        f"tasks={audit['tasks']}",
        "labels_read=false",
        flush=True,
    )
    return 0


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--repo-root", required=True, type=Path)
    build_parser.add_argument("--pairs", required=True, type=Path)
    build_parser.add_argument("--run-map", required=True, type=Path)
    build_parser.add_argument("--cards", required=True, type=Path)
    build_parser.add_argument("--manifest", required=True, type=Path)
    build_parser.add_argument("--manifest-summary", required=True, type=Path)
    build_parser.add_argument("--out-dir", required=True, type=Path)
    build_parser.add_argument("--expect-pairs-sha256", required=True)
    build_parser.add_argument("--expect-run-map-sha256", required=True)
    build_parser.add_argument("--expect-cards-sha256", required=True)
    build_parser.add_argument("--expect-manifest-sha256", required=True)
    build_parser.add_argument("--expect-manifest-summary-sha256", required=True)
    build_parser.add_argument("--wall-cap-s", type=float, default=3_600.0)
    build_parser.set_defaults(function=build)

    activate_parser = subparsers.add_parser("activate")
    activate_parser.add_argument("--repo-root", required=True, type=Path)
    activate_parser.add_argument("--result-dir", required=True, type=Path)
    activate_parser.set_defaults(function=activate)

    score_parser = subparsers.add_parser("score")
    score_parser.add_argument("--scorer-dir", required=True, type=Path)
    score_parser.add_argument("--blind-manifest", required=True, type=Path)
    score_parser.add_argument("--precutoff-endpoint-denylist", required=True, type=Path)
    score_parser.add_argument("--out-dir", required=True, type=Path)
    score_parser.add_argument("--expect-receipt-sha256", required=True)
    score_parser.add_argument("--expect-blind-manifest-sha256", required=True)
    score_parser.add_argument("--expect-precutoff-endpoint-denylist-sha256", required=True)
    score_parser.add_argument("--expect-precutoff-endpoints", required=True, type=int)
    score_parser.set_defaults(function=score)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    return int(args.function(args))


if __name__ == "__main__":
    raise SystemExit(main())
