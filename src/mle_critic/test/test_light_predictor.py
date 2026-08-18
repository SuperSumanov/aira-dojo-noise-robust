import json

import numpy as np
from scipy import sparse

from src.mle_critic.src.train.light_predictor.data import (
    read_cards,
    read_pair_splits,
    required_card_ids,
)
from src.mle_critic.src.train.light_predictor.features import (
    FEATURE_NAMES,
    extract_static_features,
)
from src.mle_critic.src.train.light_predictor.train import antisymmetric_training_data


def test_static_feature_set_matches_student_suite():
    features = extract_static_features(
        {
            "code": "import sklearn\n# blend\nmodel = LogisticRegression(random_state=7)",
            "lineage": {"depth": 2, "step": 3, "n_siblings": 4},
        }
    )

    assert len(FEATURE_NAMES) == 34
    assert features["depth"] == 2
    assert features["step"] == 3
    assert features["n_sibs"] == 4
    assert features["n_seed"] == 1
    assert features["m_sklearn"] == 1
    assert "runtime" not in features


def test_pair_loading_and_flat_jsonl_cards(tmp_path):
    pairs_path = tmp_path / "pairs.jsonl"
    cards_path = tmp_path / "cards.jsonl"
    pairs_path.write_text(
        "\n".join(
            [
                json.dumps({"better": "a", "worse": "b", "intask_split": "train"}),
                json.dumps({"better": "b", "worse": "c", "intask_split": "test"}),
            ]
        )
    )
    cards_path.write_text(
        "\n".join(
            json.dumps({"id": card_id, "code": f"code-{card_id}", "lineage": {}})
            for card_id in ("a", "b", "c", "unused")
        )
    )

    train, test = read_pair_splits(pairs_path)
    needed = required_card_ids(train, test)
    cards = read_cards(cards_path, needed)

    assert needed == {"a", "b", "c"}
    assert set(cards) == needed


def test_sparse_antisymmetric_training_data():
    matrix = sparse.csr_matrix([[2.0, 0.0], [0.0, 1.0]])
    features, labels = antisymmetric_training_data(
        matrix, np.asarray([0]), np.asarray([1])
    )

    assert sparse.isspmatrix_csr(features)
    assert features.toarray().tolist() == [[2.0, -1.0], [-2.0, 1.0]]
    assert labels.tolist() == [1, 0]
