"""Card schema: JSON round-trip, label-hiding (leak prevention), normalize_graded round-trip."""
import numpy as np

from phase1.cards import Card, features_matrix, normalize_graded, FEATURE_NAMES
from phase1.mock import generate


def test_json_roundtrip():
    c = generate(n_tasks=1, n_per_task=1, seed=0)[0]
    c2 = Card.from_json(c.to_json())
    assert c2.id == c.id and c2.task.name == c.task.name
    assert abs(c2.label.y_norm - c.label.y_norm) < 1e-9


def test_label_hiding():
    c = generate(n_tasks=1, n_per_task=1, seed=0)[0]
    assert c.hidden().label is None            # predict() only ever gets this
    assert "label" not in c.view()             # the critic-visible dict has no label
    assert c.y is not None                      # but the label is still available for fitting/scoring


def test_featurizer_shape_and_finite():
    cards = generate(n_tasks=2, n_per_task=5, seed=1)
    X = features_matrix(cards)
    assert X.shape == (10, len(FEATURE_NAMES))
    assert np.isfinite(X).all()


def test_normalize_graded_roundtrip():
    thr = {"bronze": 0.4, "silver": 0.6, "gold": 0.8}
    # mock uses graded = 0.6*y + 0.2 ; normalize should recover y for the anchored piecewise map
    for y in (0.0, 0.3, 0.7, 1.0):
        graded = 0.6 * y + 0.2
        y_norm, bucket = normalize_graded(graded, thr, True)
        assert abs(y_norm - y) < 1e-6


def test_normalize_missing_thresholds_degrades():
    y_norm, bucket = normalize_graded(0.5, {}, True)
    assert y_norm is None and bucket == "none"
