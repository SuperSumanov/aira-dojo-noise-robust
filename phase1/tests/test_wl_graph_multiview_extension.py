from pathlib import Path

import numpy as np

from phase1.wl_graph_multiview_extension import (
    ARMS,
    fit_bundle,
    load_bundle,
    score_cards,
)


def _cards() -> dict:
    values = {}
    for index in range(6):
        identifier = f"c{index}"
        values[identifier] = {
            "id": identifier,
            "task": "task",
            "run": "run",
            "code": f"import numpy as np\ndef model_{index}(x):\n    return np.mean(x) + {index}\n",
            "lineage": {
                "depth": 2,
                "step": index + 1,
                "n_siblings": 6,
                "op": "Improve",
            },
        }
    return values


def _pairs() -> list[dict]:
    return [
        {"better": "c1", "worse": "c0"},
        {"better": "c3", "worse": "c2"},
        {"better": "c5", "worse": "c4"},
    ]


def test_bundle_roundtrip_preserves_all_arm_scores(tmp_path: Path) -> None:
    cards = _cards()
    arrays, diagnostics, fitted = fit_bundle(cards, _pairs())
    path = tmp_path / "bundle.npz"
    np.savez_compressed(path, **arrays)
    restored = load_bundle(path)
    scored, graph = score_cards(cards, restored)
    assert set(diagnostics["fits"]) == set(ARMS)
    assert diagnostics["outcome_metrics_computed"] == []
    assert graph["endpoints"] == 6
    assert max(
        abs(fitted[identifier][arm] - scored[identifier][arm])
        for identifier in cards
        for arm in ARMS
    ) < 1e-12


def test_step_only_arm_orders_the_synthetic_positive_differences() -> None:
    cards = _cards()
    _arrays, _diagnostics, fitted = fit_bundle(cards, _pairs())
    assert all(fitted[better]["step_only_lr"] > fitted[worse]["step_only_lr"] for better, worse in (("c1", "c0"), ("c3", "c2"), ("c5", "c4")))
