#!/usr/bin/env python3
"""Independent numeric refit verifier for the WL graph extension.

The verifier does not import the producer.  It deliberately uses a different
graph batching path while sharing the frozen pure graph feature specification.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
import warnings
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from phase1.fixed_decision_scorer import (
    code_view,
    load_manifest,
    load_pairs,
    load_run_map,
    load_train_cards,
    pair_differences,
    sha256,
    static_feature_dict,
    symmetric_design,
)
from phase1.wl_code_graph_features import (
    HASHED_DIMENSIONS,
    MAXIMUM_NODES,
    WL_ITERATIONS,
    wl_feature_dict,
)


PROTOCOL = "wl-graph-multiview-extension-v1"
MODEL_FORMAT = "wl_graph_multiview_npz_v1"
SEED = 20260820
LR_C = 1.0
ARMS = (
    "step_only_lr",
    "wl_graph_lr",
    "wl_graph_static_lr",
    "wl_graph_static_tfidf_lr",
)
VERIFY_GRAPH_BATCH = 17


class VerifyError(RuntimeError):
    pass


def bind_source(repo: Path, source_commit: str) -> None:
    actual = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(
        ["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all"], text=True
    ).strip()
    if actual != source_commit or dirty:
        raise VerifyError("verifier source binding failed")


def _graph_matrix(cards: dict[str, dict[str, Any]], identifiers: Sequence[str]):
    from scipy import sparse
    from sklearn.feature_extraction import FeatureHasher
    from sklearn.preprocessing import normalize

    hasher = FeatureHasher(
        n_features=HASHED_DIMENSIONS,
        input_type="dict",
        dtype=np.float64,
        alternate_sign=True,
    )
    matrices = []
    mode_counts: dict[str, int] = {}
    truncated = 0
    for start in range(0, len(identifiers), VERIFY_GRAPH_BATCH):
        features = []
        for identifier in identifiers[start : start + VERIFY_GRAPH_BATCH]:
            row, diagnostic = wl_feature_dict(cards[identifier]["code"])
            features.append(row)
            mode_counts[diagnostic.mode] = mode_counts.get(diagnostic.mode, 0) + 1
            truncated += diagnostic.truncated
        batch = hasher.transform(features).tocsr()
        matrices.append(normalize(batch, norm="l2", axis=1, copy=False))
    matrix = sparse.vstack(matrices, format="csr")
    if matrix.shape != (len(identifiers), HASHED_DIMENSIONS) or not np.isfinite(matrix.data).all():
        raise VerifyError("independent graph matrix invalid")
    return matrix, {"mode_counts": dict(sorted(mode_counts.items())), "truncated_endpoints": truncated}


def _fit(design, labels: np.ndarray):
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
    if any(issubclass(item.category, ConvergenceWarning) for item in caught):
        raise VerifyError("independent fit convergence warning")
    value = np.asarray(model.coef_.reshape(-1), dtype="<f8")
    if not np.isfinite(value).all():
        raise VerifyError("independent fit non-finite")
    return value


def refit(cards: dict[str, dict[str, Any]], pairs: Sequence[dict[str, Any]]):
    from scipy import sparse
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import StandardScaler

    identifiers = sorted(cards)
    position = {identifier: index for index, identifier in enumerate(identifiers)}
    graph, graph_diag = _graph_matrix(cards, identifiers)
    graph_diff = pair_differences(graph, position, pairs).tocsr()
    graph_design, labels = symmetric_design(graph_diff)
    graph_coef = _fit(graph_design, labels)
    del graph_design

    names = sorted(static_feature_dict(cards[identifiers[0]]))
    static = np.asarray(
        [[static_feature_dict(cards[identifier])[name] for name in names] for identifier in identifiers],
        dtype=np.float64,
    )
    static_diff = pair_differences(static, position, pairs)
    static_design, labels_static = symmetric_design(static_diff)
    if not np.array_equal(labels, labels_static):
        raise VerifyError("independent static labels differ")
    scaler = StandardScaler(with_mean=False).fit(static_design)
    static_scale = np.asarray(scaler.scale_, dtype="<f8")
    static_scaled = sparse.csr_matrix(static / static_scale)
    static_diff_scaled = sparse.csr_matrix(static_diff / static_scale)

    step_index = names.index("step")
    step_design, step_labels = symmetric_design(static_diff[:, [step_index]])
    step_scaler = StandardScaler(with_mean=False).fit(step_design)
    step_scale = np.asarray(step_scaler.scale_, dtype="<f8")
    step_coef = _fit(step_scaler.transform(step_design), step_labels)

    graph_static_diff = sparse.hstack([graph_diff, static_diff_scaled], format="csr")
    graph_static_design, graph_static_labels = symmetric_design(graph_static_diff)
    if not np.array_equal(labels, graph_static_labels):
        raise VerifyError("independent graph-static labels differ")
    graph_static_coef = _fit(graph_static_design, graph_static_labels)
    del graph_static_design

    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        dtype=np.float64,
        max_features=30_000,
        min_df=3,
        ngram_range=(3, 5),
        sublinear_tf=True,
    )
    tfidf = vectorizer.fit_transform([code_view(str(cards[identifier]["code"])) for identifier in identifiers]).tocsr()
    terms = np.empty(len(vectorizer.vocabulary_), dtype=f"<U{max(map(len, vectorizer.vocabulary_))}")
    for term, index in vectorizer.vocabulary_.items():
        terms[int(index)] = term
    tfidf_idf = np.asarray(vectorizer.idf_, dtype="<f8")
    tfidf_diff = pair_differences(tfidf, position, pairs).tocsr()
    multiview_diff = sparse.hstack([graph_diff, static_diff_scaled, tfidf_diff], format="csr")
    multiview_design, multiview_labels = symmetric_design(multiview_diff)
    if not np.array_equal(labels, multiview_labels):
        raise VerifyError("independent multiview labels differ")
    multiview_coef = _fit(multiview_design, multiview_labels)

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
        "static_feature_names": np.asarray(names),
        "static_scale": static_scale,
        "graph_static_coef": graph_static_coef,
        "tfidf_terms": terms,
        "tfidf_idf": tfidf_idf,
        "multiview_coef": multiview_coef,
    }
    graph_static = sparse.hstack([graph, static_scaled], format="csr")
    multiview = sparse.hstack([graph, static_scaled, tfidf], format="csr")
    scores_raw = {
        "step_only_lr": static[:, step_index] / step_scale[0] * step_coef[0],
        "wl_graph_lr": np.asarray(graph @ graph_coef).reshape(-1),
        "wl_graph_static_lr": np.asarray(graph_static @ graph_static_coef).reshape(-1),
        "wl_graph_static_tfidf_lr": np.asarray(multiview @ multiview_coef).reshape(-1),
    }
    scores = {
        identifier: {arm: float(scores_raw[arm][index]) for arm in ARMS}
        for index, identifier in enumerate(identifiers)
    }
    return arrays, scores, graph_diag


def _load_bundle(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as data:
        return {key: np.asarray(data[key]).copy() for key in data.files}


def _reference_differences(path: Path, scores: dict[str, dict[str, float]]) -> tuple[int, float]:
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    identifiers = [row["card_id"] for row in rows]
    if identifiers != sorted(scores) or len(identifiers) != len(set(identifiers)):
        raise VerifyError("reference identity inventory mismatch")
    maximum = 0.0
    for row in rows:
        for arm in ARMS:
            maximum = max(maximum, abs(float(row[arm]) - scores[row["card_id"]][arm]))
    return len(rows), maximum


def verify(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    repo = Path(__file__).resolve().parent.parent
    bind_source(repo, args.source_commit)
    result = Path(args.result).resolve()
    summary = json.loads((result / "summary.json").read_text(encoding="utf-8"))
    protocol_path = repo / "phase1" / "wl_graph_multiview_protocol_v1.json"
    protocol_value = json.loads(protocol_path.read_text(encoding="utf-8"))
    if (
        summary.get("status") != "WL_GRAPH_MULTIVIEW_BUILD_COMPLETE_NOT_YET_INDEPENDENTLY_VERIFIED"
        or summary.get("source_commit") != args.source_commit
        or protocol_value.get("protocol") != PROTOCOL
        or summary.get("protocol_sha256") != sha256(protocol_path)
        or summary.get("scope", {}).get("v11_frozen_or_extension_read") is not False
        or summary.get("scope", {}).get("outcome_metrics_computed") != []
    ):
        raise VerifyError("producer summary scope mismatch")
    expected_inputs = {
        "pairs_sha256": args.expect_pairs_sha256,
        "run_map_sha256": args.expect_run_map_sha256,
        "cards_sha256": args.expect_cards_sha256,
        "manifest_sha256": args.expect_manifest_sha256,
        "manifest_summary_sha256": args.expect_manifest_summary_sha256,
    }
    if summary.get("inputs") != expected_inputs:
        raise VerifyError("producer input binding mismatch")
    bundle_path = result / summary["outputs"]["bundle"]
    reference_path = result / summary["outputs"]["train_reference"]
    if sha256(bundle_path) != summary["outputs"]["bundle_sha256"] or sha256(reference_path) != summary["outputs"]["train_reference_sha256"]:
        raise VerifyError("producer output hash mismatch")
    manifest, _ = load_manifest(
        Path(args.manifest), Path(args.manifest_summary), args.expect_manifest_sha256,
        args.expect_manifest_summary_sha256,
    )
    run_map, _ = load_run_map(Path(args.run_map), args.expect_run_map_sha256)
    pairs = load_pairs(Path(args.pairs), manifest, run_map, args.expect_pairs_sha256)
    cards, card_audit = load_train_cards(Path(args.cards), manifest, args.expect_cards_sha256)
    expected, scores, graph_diag = refit(cards, pairs)
    actual = _load_bundle(bundle_path)
    if set(actual) != set(expected):
        raise VerifyError("bundle key set mismatch")
    array_checks: dict[str, dict[str, Any]] = {}
    maximum_numeric = 0.0
    for name in sorted(expected):
        if actual[name].shape != expected[name].shape or actual[name].dtype.kind != expected[name].dtype.kind:
            raise VerifyError(f"bundle shape/type mismatch: {name}")
        if actual[name].dtype.kind in "fiu":
            difference = float(np.max(np.abs(actual[name].astype(float) - expected[name].astype(float)))) if actual[name].size else 0.0
            maximum_numeric = max(maximum_numeric, difference)
            passed = difference <= 1e-12
        else:
            difference = None
            passed = np.array_equal(actual[name], expected[name])
        array_checks[name] = {"passed": bool(passed), "maximum_absolute_difference": difference}
        if not passed:
            raise VerifyError(f"bundle array differs: {name}")
    reference_rows, reference_max = _reference_differences(reference_path, scores)
    if reference_max > 1e-12:
        raise VerifyError("reference scores differ")
    return {
        "status": "INDEPENDENT_WL_GRAPH_MULTIVIEW_REFIT_VERIFIED",
        "protocol": PROTOCOL,
        "source_commit": args.source_commit,
        "producer_imported": False,
        "shared_pure_feature_spec_only": "phase1.wl_code_graph_features",
        "bundle_sha256": sha256(bundle_path),
        "reference_sha256": sha256(reference_path),
        "array_checks": array_checks,
        "maximum_numeric_array_difference": maximum_numeric,
        "reference_rows": reference_rows,
        "maximum_reference_score_difference": reference_max,
        "independent_graph_diagnostics": graph_diag,
        "card_audit": card_audit,
        "runtime_seconds": time.perf_counter() - started,
        "scope": {
            "v11_frozen_or_extension_read": False,
            "outcome_metrics_computed": [],
            "prospective_outcomes_read": False,
            "gpu": 0,
            "api_calls": 0,
            "base_llm_updates": 0,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", required=True)
    parser.add_argument("--run-map", required=True)
    parser.add_argument("--cards", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--manifest-summary", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--expect-pairs-sha256", required=True)
    parser.add_argument("--expect-run-map-sha256", required=True)
    parser.add_argument("--expect-cards-sha256", required=True)
    parser.add_argument("--expect-manifest-sha256", required=True)
    parser.add_argument("--expect-manifest-summary-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite verifier output: {output}")
    try:
        receipt = verify(args)
    except (VerifyError, OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"WL_GRAPH_MULTIVIEW_VERIFY_ERROR: {error}", file=sys.stderr)
        return 2
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(
        receipt["status"],
        f"max_array_diff={receipt['maximum_numeric_array_difference']}",
        f"max_score_diff={receipt['maximum_reference_score_difference']}",
        "outcome_metrics=0",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
