"""The student's 34 decision-time handcrafted code features."""

from __future__ import annotations

import re
from typing import Any

import numpy as np


IMPORT_RX = re.compile(r"^\s*(?:from|import)\s+([\w.]+)", re.MULTILINE)
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


def extract_static_features(card: dict[str, Any]) -> dict[str, float]:
    """Extract pre-execution string-count and lineage features from one card."""
    code = card.get("code") or ""
    low = code.lower()
    lineage = card.get("lineage") or {}
    imports = set(IMPORT_RX.findall(code))
    features = {
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
        "n_print": float(low.count("print(")),
        "n_comment": float(code.count("#")),
        "n_fold_int": float(
            max([int(value) for value in re.findall(r"n_splits\s*=\s*(\d+)", code)] or [0])
        ),
        "n_epoch_int": float(
            max([int(value) for value in re.findall(r"epochs?\s*=\s*(\d+)", code)] or [0])
        ),
        "risk_leak": float(sum(low.count(word) for word in RISK_WORDS)),
        "has_gpu": float("cuda" in low),
    }
    for model_word in MODEL_WORDS:
        features["m_" + model_word] = float(model_word in low)
    return features


FEATURE_NAMES = tuple(sorted(extract_static_features({"code": "", "lineage": {}})))


def static_feature_matrix(
    cards: dict[str, dict[str, Any]], card_ids: list[str]
) -> np.ndarray:
    """Build a card-aligned dense matrix using the stable alphabetical feature order."""
    return np.asarray(
        [
            [extract_static_features(cards[card_id])[name] for name in FEATURE_NAMES]
            for card_id in card_ids
        ],
        dtype=np.float64,
    )
