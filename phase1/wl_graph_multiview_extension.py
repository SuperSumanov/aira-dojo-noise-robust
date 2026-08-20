#!/usr/bin/env python3
"""Build and apply the frozen WL graph/multi-view prospective extension."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
import warnings
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from phase1.fixed_decision_scorer import (
    atomic_npz,
    code_view,
    git_commit,
    load_manifest,
    load_pairs,
    load_run_map,
    load_train_cards,
    pair_differences,
    reject_forbidden_path,
    sha256,
    static_feature_dict,
    symmetric_design,
    utc_now,
)
from phase1.wl_code_graph_features import (
    HASHED_DIMENSIONS,
    MAXIMUM_NODES,
    WL_ITERATIONS,
    GraphDiagnostics,
    aggregate_diagnostics,
    hashed_l2_matrix,
    wl_feature_dict,
)


PROTOCOL = "wl-graph-multiview-extension-v1"
MODEL_FORMAT = "wl_graph_multiview_npz_v1"
SEED = 20260820
ARMS = (
    "step_only_lr",
    "wl_graph_lr",
    "wl_graph_static_lr",
    "wl_graph_static_tfidf_lr",
)
GRAPH_BATCH = 32
TFIDF_MAX_FEATURES = 30_000
TFIDF_MIN_DF = 3
LR_C = 1.0


class ExtensionError(RuntimeError):
    pass


def protocol_sha(path: Path) -> str:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("protocol") != PROTOCOL:
        raise ExtensionError("protocol identity mismatch")
    graph = value.get("graph", {})
    linear = value.get("linear_models", {})
    if (
        graph.get("wl_iterations") != WL_ITERATIONS
        or graph.get("maximum_nodes") != MAXIMUM_NODES
        or graph.get("feature_hasher", {}).get("n_features") != HASHED_DIMENSIONS
        or linear.get("random_state") != SEED
        or float(linear.get("C", -1)) != LR_C
        or tuple(value.get("arms", {})) != ARMS
    ):
        raise ExtensionError("protocol configuration drift")
    return sha256(path)


def bind_source(repo: Path, source_commit: str, protocol: Path) -> str:
    actual = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(
        ["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all"], text=True
    ).strip()
    if actual != source_commit or dirty:
        raise ExtensionError("source commit/clean worktree binding failed")
    return protocol_sha(protocol)


def graph_matrix(cards: dict[str, dict[str, Any]], identifiers: Sequence[str]):
    from scipy import sparse

    batches = []
    diagnostics: list[GraphDiagnostics] = []
    for start in range(0, len(identifiers), GRAPH_BATCH):
        rows = []
        for identifier in identifiers[start : start + GRAPH_BATCH]:
            features, receipt = wl_feature_dict(cards[identifier]["code"])
            rows.append(features)
            diagnostics.append(receipt)
        batches.append(hashed_l2_matrix(rows))
    matrix = sparse.vstack(batches, format="csr")
    if matrix.shape != (len(identifiers), HASHED_DIMENSIONS) or not np.isfinite(matrix.data).all():
        raise ExtensionError("graph matrix shape/numerics mismatch")
    return matrix, diagnostics


def _fit_lr(design, labels: np.ndarray, name: str):
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.linear_model import LogisticRegression

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model = LogisticRegression(
            C=LR_C,
            fit_intercept=False,
            max_iter=2_000,
            random_state=SEED,
            solver="liblinear",
            tol=1e-6,
        ).fit(design, labels)
    convergence = [str(item.message) for item in caught if issubclass(item.category, ConvergenceWarning)]
    if convergence:
        raise ExtensionError(f"{name} convergence warning: {convergence}")
    coefficient = np.asarray(model.coef_.reshape(-1), dtype="<f8")
    if not np.isfinite(coefficient).all():
        raise ExtensionError(f"{name} non-finite coefficient")
    return coefficient, {
        "iterations": int(model.n_iter_[0]),
        "coefficient_norm": float(np.linalg.norm(coefficient)),
        "features": int(design.shape[1]),
        "training_rows_symmetric": int(design.shape[0]),
        "training_matrix_nnz": int(design.nnz) if hasattr(design, "nnz") else int(np.count_nonzero(design)),
    }


def _tfidf_matrix(cards: dict[str, dict[str, Any]], identifiers: Sequence[str]):
    from sklearn.feature_extraction.text import TfidfVectorizer

    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        dtype=np.float64,
        max_features=TFIDF_MAX_FEATURES,
        min_df=TFIDF_MIN_DF,
        ngram_range=(3, 5),
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform([code_view(str(cards[identifier]["code"])) for identifier in identifiers])
    terms = np.empty(len(vectorizer.vocabulary_), dtype=f"<U{max(map(len, vectorizer.vocabulary_))}")
    for term, index in vectorizer.vocabulary_.items():
        terms[int(index)] = term
    return matrix.tocsr(), terms, np.asarray(vectorizer.idf_, dtype="<f8")


def fit_bundle(cards: dict[str, dict[str, Any]], pairs: Sequence[dict[str, Any]]):
    from scipy import sparse
    from sklearn.preprocessing import StandardScaler

    started = time.perf_counter()
    identifiers = sorted(cards)
    position = {identifier: index for index, identifier in enumerate(identifiers)}

    graph, graph_receipts = graph_matrix(cards, identifiers)
    graph_diff = pair_differences(graph, position, pairs).tocsr()
    graph_design, labels = symmetric_design(graph_diff)
    graph_coef, graph_fit = _fit_lr(graph_design, labels, "wl_graph_lr")
    del graph_design

    static_names = sorted(static_feature_dict(cards[identifiers[0]]))
    static = np.asarray(
        [[static_feature_dict(cards[identifier])[name] for name in static_names] for identifier in identifiers],
        dtype=np.float64,
    )
    static_diff = pair_differences(static, position, pairs)
    static_design, static_labels = symmetric_design(static_diff)
    if not np.array_equal(labels, static_labels):
        raise ExtensionError("symmetric labels differ")
    scaler = StandardScaler(with_mean=False).fit(static_design)
    static_scale = np.asarray(scaler.scale_, dtype="<f8")
    if not np.isfinite(static_scale).all() or np.any(static_scale <= 0):
        raise ExtensionError("invalid static scales")
    static_scaled = sparse.csr_matrix(static / static_scale)
    static_diff_scaled = sparse.csr_matrix(static_diff / static_scale)

    step_index = static_names.index("step")
    step_diff = static_diff[:, [step_index]]
    step_design, step_labels = symmetric_design(step_diff)
    step_scaler = StandardScaler(with_mean=False).fit(step_design)
    step_scale = np.asarray(step_scaler.scale_, dtype="<f8")
    step_coef, step_fit = _fit_lr(step_scaler.transform(step_design), step_labels, "step_only_lr")

    graph_static_diff = sparse.hstack([graph_diff, static_diff_scaled], format="csr")
    graph_static_design, graph_static_labels = symmetric_design(graph_static_diff)
    if not np.array_equal(labels, graph_static_labels):
        raise ExtensionError("graph-static symmetric labels differ")
    graph_static_coef, graph_static_fit = _fit_lr(
        graph_static_design, graph_static_labels, "wl_graph_static_lr"
    )
    del graph_static_design

    tfidf, tfidf_terms, tfidf_idf = _tfidf_matrix(cards, identifiers)
    tfidf_diff = pair_differences(tfidf, position, pairs).tocsr()
    multiview_diff = sparse.hstack([graph_diff, static_diff_scaled, tfidf_diff], format="csr")
    multiview_design, multiview_labels = symmetric_design(multiview_diff)
    if not np.array_equal(labels, multiview_labels):
        raise ExtensionError("multiview symmetric labels differ")
    multiview_coef, multiview_fit = _fit_lr(
        multiview_design, multiview_labels, "wl_graph_static_tfidf_lr"
    )
    del multiview_design

    endpoint_graph_static = sparse.hstack([graph, static_scaled], format="csr")
    endpoint_multiview = sparse.hstack([graph, static_scaled, tfidf], format="csr")
    step_values = static[:, step_index] / step_scale[0]
    score_arrays = {
        "step_only_lr": np.asarray(step_values * step_coef[0], dtype=np.float64),
        "wl_graph_lr": np.asarray(graph @ graph_coef, dtype=np.float64).reshape(-1),
        "wl_graph_static_lr": np.asarray(endpoint_graph_static @ graph_static_coef, dtype=np.float64).reshape(-1),
        "wl_graph_static_tfidf_lr": np.asarray(endpoint_multiview @ multiview_coef, dtype=np.float64).reshape(-1),
    }
    if not all(np.isfinite(values).all() for values in score_arrays.values()):
        raise ExtensionError("non-finite fitted endpoint scores")
    scores = {
        identifier: {arm: float(score_arrays[arm][index]) for arm in ARMS}
        for index, identifier in enumerate(identifiers)
    }
    arrays = {
        "format": np.asarray([MODEL_FORMAT]),
        "protocol": np.asarray([PROTOCOL]),
        "seed": np.asarray([SEED], dtype="<i8"),
        "wl_iterations": np.asarray([WL_ITERATIONS], dtype="<i8"),
        "maximum_nodes": np.asarray([MAXIMUM_NODES], dtype="<i8"),
        "hashed_dimensions": np.asarray([HASHED_DIMENSIONS], dtype="<i8"),
        "step_scale": step_scale,
        "step_coef": step_coef,
        "graph_coef": graph_coef,
        "static_feature_names": np.asarray(static_names),
        "static_scale": static_scale,
        "graph_static_coef": graph_static_coef,
        "tfidf_terms": tfidf_terms,
        "tfidf_idf": tfidf_idf,
        "multiview_coef": multiview_coef,
    }
    diagnostics = {
        "elapsed_seconds": time.perf_counter() - started,
        "graph": {
            **aggregate_diagnostics(graph_receipts),
            "matrix_shape": list(graph.shape),
            "matrix_nnz": int(graph.nnz),
            "hashed_dimensions": HASHED_DIMENSIONS,
        },
        "tfidf": {
            "vocabulary": len(tfidf_terms),
            "matrix_nnz": int(tfidf.nnz),
            "truncated_codes": sum(len(str(cards[identifier]["code"])) > 20_000 for identifier in identifiers),
        },
        "fits": {
            "step_only_lr": step_fit,
            "wl_graph_lr": graph_fit,
            "wl_graph_static_lr": graph_static_fit,
            "wl_graph_static_tfidf_lr": multiview_fit,
        },
        "outcome_metrics_computed": [],
    }
    return arrays, diagnostics, scores


def load_bundle(path: Path) -> dict[str, np.ndarray]:
    required = {
        "format", "protocol", "seed", "wl_iterations", "maximum_nodes", "hashed_dimensions",
        "step_scale", "step_coef", "graph_coef", "static_feature_names", "static_scale",
        "graph_static_coef", "tfidf_terms", "tfidf_idf", "multiview_coef",
    }
    with np.load(path, allow_pickle=False) as data:
        if set(data.files) != required:
            raise ExtensionError(f"bundle keys mismatch: {sorted(data.files)}")
        arrays = {key: np.asarray(data[key]).copy() for key in data.files}
    if (
        str(arrays["format"][0]) != MODEL_FORMAT
        or str(arrays["protocol"][0]) != PROTOCOL
        or int(arrays["seed"][0]) != SEED
        or int(arrays["wl_iterations"][0]) != WL_ITERATIONS
        or int(arrays["maximum_nodes"][0]) != MAXIMUM_NODES
        or int(arrays["hashed_dimensions"][0]) != HASHED_DIMENSIONS
    ):
        raise ExtensionError("bundle configuration mismatch")
    static_count = len(arrays["static_feature_names"])
    tfidf_count = len(arrays["tfidf_terms"])
    expected_shapes = {
        "step_scale": (1,), "step_coef": (1,), "graph_coef": (HASHED_DIMENSIONS,),
        "static_scale": (static_count,),
        "graph_static_coef": (HASHED_DIMENSIONS + static_count,),
        "tfidf_idf": (tfidf_count,),
        "multiview_coef": (HASHED_DIMENSIONS + static_count + tfidf_count,),
    }
    for name, shape in expected_shapes.items():
        if arrays[name].shape != shape or not np.isfinite(arrays[name]).all():
            raise ExtensionError(f"bundle array mismatch: {name}")
    if np.any(arrays["step_scale"] <= 0) or np.any(arrays["static_scale"] <= 0) or np.any(arrays["tfidf_idf"] <= 0):
        raise ExtensionError("bundle positive scale/IDF mismatch")
    return arrays


def score_cards(cards: dict[str, dict[str, Any]], arrays: dict[str, np.ndarray]):
    from scipy import sparse
    from sklearn.feature_extraction.text import TfidfVectorizer

    identifiers = sorted(cards)
    graph, graph_receipts = graph_matrix(cards, identifiers)
    names = [str(value) for value in arrays["static_feature_names"].tolist()]
    static = np.asarray(
        [[static_feature_dict(cards[identifier])[name] for name in names] for identifier in identifiers],
        dtype=np.float64,
    )
    static_scaled = sparse.csr_matrix(static / arrays["static_scale"])
    terms = [str(value) for value in arrays["tfidf_terms"].tolist()]
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        dtype=np.float64,
        ngram_range=(3, 5),
        sublinear_tf=True,
        vocabulary={term: index for index, term in enumerate(terms)},
    )
    vectorizer.idf_ = np.asarray(arrays["tfidf_idf"], dtype=np.float64)
    tfidf = vectorizer.transform([code_view(str(cards[identifier]["code"])) for identifier in identifiers])
    graph_static = sparse.hstack([graph, static_scaled], format="csr")
    multiview = sparse.hstack([graph, static_scaled, tfidf], format="csr")
    step_index = names.index("step")
    score_arrays = {
        "step_only_lr": static[:, step_index] / arrays["step_scale"][0] * arrays["step_coef"][0],
        "wl_graph_lr": np.asarray(graph @ arrays["graph_coef"]).reshape(-1),
        "wl_graph_static_lr": np.asarray(graph_static @ arrays["graph_static_coef"]).reshape(-1),
        "wl_graph_static_tfidf_lr": np.asarray(multiview @ arrays["multiview_coef"]).reshape(-1),
    }
    if not all(np.isfinite(values).all() for values in score_arrays.values()):
        raise ExtensionError("non-finite inference score")
    return {
        identifier: {arm: float(score_arrays[arm][index]) for arm in ARMS}
        for index, identifier in enumerate(identifiers)
    }, aggregate_diagnostics(graph_receipts)


def write_reference(path: Path, cards: dict[str, dict[str, Any]], scores: dict[str, dict[str, float]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("card_id", "task", "run_id", *ARMS),
            lineterminator="\n",
        )
        writer.writeheader()
        for identifier in sorted(cards):
            writer.writerow(
                {
                    "card_id": identifier,
                    "task": cards[identifier]["task"],
                    "run_id": cards[identifier]["run"],
                    **{arm: format(scores[identifier][arm], ".17g") for arm in ARMS},
                }
            )


def build(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    repo = Path(args.repo_root).resolve()
    protocol = Path(args.protocol).resolve()
    protocol_digest = bind_source(repo, args.source_commit, protocol)
    for path, label in (
        (args.pairs, "training pairs"), (args.run_map, "run map"), (args.cards, "source cards"),
        (args.manifest, "train manifest"), (args.manifest_summary, "train manifest summary"),
    ):
        reject_forbidden_path(Path(path), label)
    output = Path(args.output).resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite output: {output}")
    output.mkdir(parents=True)
    manifest, _manifest_summary = load_manifest(
        Path(args.manifest), Path(args.manifest_summary), args.expect_manifest_sha256,
        args.expect_manifest_summary_sha256,
    )
    run_map, _runs = load_run_map(Path(args.run_map), args.expect_run_map_sha256)
    pairs = load_pairs(Path(args.pairs), manifest, run_map, args.expect_pairs_sha256)
    cards, card_audit = load_train_cards(Path(args.cards), manifest, args.expect_cards_sha256)
    arrays, diagnostics, fitted_scores = fit_bundle(cards, pairs)
    bundle = output / "wl_graph_multiview_scorer.npz"
    reference = output / "train_reference_scores.csv"
    atomic_npz(bundle, **arrays)
    write_reference(reference, cards, fitted_scores)
    restored = load_bundle(bundle)
    restored_scores, restored_graph = score_cards(cards, restored)
    max_roundtrip = max(
        abs(restored_scores[identifier][arm] - fitted_scores[identifier][arm])
        for identifier in cards for arm in ARMS
    )
    if max_roundtrip > 1e-12:
        raise ExtensionError(f"bundle roundtrip mismatch: {max_roundtrip}")
    input_hashes = {
        "pairs_sha256": sha256(Path(args.pairs)), "run_map_sha256": sha256(Path(args.run_map)),
        "cards_sha256": sha256(Path(args.cards)), "manifest_sha256": sha256(Path(args.manifest)),
        "manifest_summary_sha256": sha256(Path(args.manifest_summary)),
    }
    elapsed = time.perf_counter() - started
    if elapsed > args.wall_cap_seconds:
        raise ExtensionError("build exceeded wall cap")
    summary = {
        "status": "WL_GRAPH_MULTIVIEW_BUILD_COMPLETE_NOT_YET_INDEPENDENTLY_VERIFIED",
        "protocol": PROTOCOL,
        "model_format": MODEL_FORMAT,
        "source_commit": args.source_commit,
        "protocol_sha256": protocol_digest,
        "built_at_utc": utc_now(),
        "inputs": input_hashes,
        "inventory": {"endpoints": len(cards), "pairs": len(pairs)},
        "configuration": {
            "arms": list(ARMS), "seed": SEED, "wl_iterations": WL_ITERATIONS,
            "maximum_nodes": MAXIMUM_NODES, "hashed_dimensions": HASHED_DIMENSIONS,
            "graph_batch": GRAPH_BATCH, "lr_c": LR_C, "fit_intercept": False,
            "tfidf_max_features": TFIDF_MAX_FEATURES, "tfidf_min_df": TFIDF_MIN_DF,
        },
        "diagnostics": diagnostics,
        "roundtrip": {"maximum_absolute_score_difference": max_roundtrip, "restored_graph": restored_graph},
        "card_audit": card_audit,
        "runtime_seconds": elapsed,
        "outputs": {
            "bundle": bundle.name, "bundle_sha256": sha256(bundle),
            "train_reference": reference.name, "train_reference_sha256": sha256(reference),
        },
        "scope": {
            "v11_frozen_or_extension_read": False, "outcome_metrics_computed": [],
            "prospective_outcomes_read": False, "gpu": 0, "api_calls": 0, "base_llm_updates": 0,
        },
        "reproducibility": {"python": platform.python_version(), "numpy": np.__version__},
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        "WL_GRAPH_MULTIVIEW_BUILD_COMPLETE",
        f"endpoints={len(cards)}",
        f"pairs={len(pairs)}",
        f"runtime_s={elapsed}",
        "outcome_metrics=0",
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--pairs", required=True)
    parser.add_argument("--run-map", required=True)
    parser.add_argument("--cards", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--manifest-summary", required=True)
    parser.add_argument("--expect-pairs-sha256", required=True)
    parser.add_argument("--expect-run-map-sha256", required=True)
    parser.add_argument("--expect-cards-sha256", required=True)
    parser.add_argument("--expect-manifest-sha256", required=True)
    parser.add_argument("--expect-manifest-summary-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--wall-cap-seconds", type=float, default=7200.0)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    try:
        return build(parse_args())
    except (
        ExtensionError, OSError, ValueError, KeyError, json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"WL_GRAPH_MULTIVIEW_ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
