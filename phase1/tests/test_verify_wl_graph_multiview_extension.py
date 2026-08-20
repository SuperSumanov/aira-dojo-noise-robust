import numpy as np

from phase1.tests.test_wl_graph_multiview_extension import _cards, _pairs
from phase1.verify_wl_graph_multiview_extension import refit
from phase1.wl_graph_multiview_extension import fit_bundle


def test_independent_refit_matches_producer_on_synthetic_cards() -> None:
    produced, produced_diagnostics, produced_scores = fit_bundle(_cards(), _pairs())
    verified, verified_scores, _graph = refit(_cards(), _pairs())
    assert produced_diagnostics["outcome_metrics_computed"] == []
    assert set(produced) == set(verified)
    for name in produced:
        if produced[name].dtype.kind in "fiu":
            np.testing.assert_allclose(produced[name], verified[name], rtol=0, atol=1e-12)
        else:
            np.testing.assert_array_equal(produced[name], verified[name])
    for identifier in produced_scores:
        for arm in produced_scores[identifier]:
            assert abs(produced_scores[identifier][arm] - verified_scores[identifier][arm]) < 1e-12
