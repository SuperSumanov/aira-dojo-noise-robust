"""Train TF-IDF/LR and handcrafted-feature LR/GBM pairwise predictors.

Example from the repository root:

  python -m src.mle_critic.src.train.light_predictor.train \
      --pairs data/mle_critic/value_pairs_runsplit.jsonl \
      --cards data/mle_critic/cards_current.jsonl
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
from scipy import sparse
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from .data import Pair, read_cards, read_pair_splits, required_card_ids
from .features import FEATURE_NAMES, static_feature_matrix


MODEL_NAMES = ("tfidf_lr", "static_lr", "static_gbm")


def pair_indices(
    pairs: list[Pair], position: dict[str, int]
) -> tuple[np.ndarray, np.ndarray]:
    """Map pair card IDs to aligned better/worse row indices."""
    better = np.fromiter((position[pair["better"]] for pair in pairs), dtype=np.int64)
    worse = np.fromiter((position[pair["worse"]] for pair in pairs), dtype=np.int64)
    return better, worse


def antisymmetric_training_data(
    matrix: Any, better: np.ndarray, worse: np.ndarray
) -> tuple[Any, np.ndarray]:
    """Add both pair orders, labelled one and zero respectively."""
    differences = matrix[better] - matrix[worse]
    if sparse.issparse(differences):
        features = sparse.vstack((differences, -differences), format="csr")
    else:
        features = np.vstack((differences, -differences))
    labels = np.concatenate(
        (np.ones(len(better), dtype=np.int8), np.zeros(len(better), dtype=np.int8))
    )
    return features, labels


def accuracy(model: Any, matrix: Any, better: np.ndarray, worse: np.ndarray) -> float:
    """Return the fraction of labelled-better endpoints assigned a positive margin."""
    differences = matrix[better] - matrix[worse]
    return float(np.mean(model.decision_function(differences) > 0))


def train_static_models(
    cards: dict[str, dict[str, Any]],
    card_ids: list[str],
    train_pairs: list[Pair],
    test_pairs: list[Pair],
    selected: set[str],
) -> list[dict[str, Any]]:
    """Fit the two handcrafted-feature models requested by the caller."""
    if not selected.intersection({"static_lr", "static_gbm"}):
        return []
    position = {card_id: index for index, card_id in enumerate(card_ids)}
    train_better, train_worse = pair_indices(train_pairs, position)
    test_better, test_worse = pair_indices(test_pairs, position)
    matrix = static_feature_matrix(cards, card_ids)
    train_x, train_y = antisymmetric_training_data(matrix, train_better, train_worse)
    results = []

    if "static_lr" in selected:
        start = time.perf_counter()
        scaler = StandardScaler(with_mean=False).fit(train_x)
        scaled_train_x = scaler.transform(train_x)
        model = LogisticRegression(max_iter=4_000, C=1.0).fit(scaled_train_x, train_y)
        test_differences = matrix[test_better] - matrix[test_worse]
        test_accuracy = float(
            np.mean(model.decision_function(scaler.transform(test_differences)) > 0)
        )
        results.append(
            {
                "model": "static_lr",
                "accuracy": test_accuracy,
                "train_seconds": time.perf_counter() - start,
                "n_features": len(FEATURE_NAMES),
            }
        )

    if "static_gbm" in selected:
        start = time.perf_counter()
        model = HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.08, random_state=7
        ).fit(train_x, train_y)
        results.append(
            {
                "model": "static_gbm",
                "accuracy": accuracy(model, matrix, test_better, test_worse),
                "train_seconds": time.perf_counter() - start,
                "n_features": len(FEATURE_NAMES),
            }
        )
    return results


def train_tfidf_model(
    cards: dict[str, dict[str, Any]],
    card_ids: list[str],
    train_pairs: list[Pair],
    test_pairs: list[Pair],
) -> dict[str, Any]:
    """Fit the student's train-only char 3-5 gram TF-IDF logistic ranker."""
    start = time.perf_counter()
    position = {card_id: index for index, card_id in enumerate(card_ids)}
    train_better, train_worse = pair_indices(train_pairs, position)
    test_better, test_worse = pair_indices(test_pairs, position)
    train_ids = sorted(required_card_ids(train_pairs))
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        max_features=30_000,
        min_df=3,
        sublinear_tf=True,
    )
    vectorizer.fit([(cards[card_id].get("code") or "")[:20_000] for card_id in train_ids])
    matrix = vectorizer.transform(
        [(cards[card_id].get("code") or "")[:20_000] for card_id in card_ids]
    )
    train_x, train_y = antisymmetric_training_data(matrix, train_better, train_worse)
    model = LogisticRegression(max_iter=1_500, C=0.5).fit(train_x, train_y)
    return {
        "model": "tfidf_lr",
        "accuracy": accuracy(model, matrix, test_better, test_worse),
        "train_seconds": time.perf_counter() - start,
        "n_features": len(vectorizer.vocabulary_),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", default="data/mle_critic/value_pairs_runsplit.jsonl")
    parser.add_argument("--cards", default="data/mle_critic/cards_current.jsonl")
    parser.add_argument("--models", nargs="+", choices=MODEL_NAMES, default=list(MODEL_NAMES))
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--train-cap", type=int, default=24_000)
    parser.add_argument("--test-cap", type=int, default=6_000)
    parser.add_argument("--loto", type=str, default="")
    parser.add_argument("--output", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> list[dict[str, Any]]:
    args = parse_args(argv)
    train_pairs, test_pairs = read_pair_splits(
        args.pairs,
        seed=args.seed,
        train_cap=args.train_cap,
        test_cap=args.test_cap,
        loto=args.loto
    )
    if not train_pairs or not test_pairs:
        raise ValueError("Both train and test pair splits must be non-empty")
    needed = required_card_ids(train_pairs, test_pairs)
    cards = read_cards(args.cards, needed)
    card_ids = sorted(needed)
    selected = set(args.models)
    print(
        f"[light-predictor] cards={len(cards)} train_pairs={len(train_pairs)} "
        f"test_pairs={len(test_pairs)} models={','.join(args.models)}",
        flush=True,
    )

    results = train_static_models(
        cards, card_ids, train_pairs, test_pairs, selected
    )
    if "tfidf_lr" in selected:
        results.append(train_tfidf_model(cards, card_ids, train_pairs, test_pairs))
    results.sort(key=lambda result: args.models.index(result["model"]))
    for result in results:
        print(
            f"{result['model']:12s} accuracy={result['accuracy']:.4f} "
            f"features={result['n_features']} train_s={result['train_seconds']:.2f}",
            flush=True,
        )

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print(f"[light-predictor] wrote {output}", flush=True)
    return results


if __name__ == "__main__":
    main()
