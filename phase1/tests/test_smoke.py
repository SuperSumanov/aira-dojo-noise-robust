"""Phase-1a acceptance gate: the mock pipeline runs end-to-end and writes its artifacts."""
import os

from phase1 import smoke


def test_smoke_pipeline(tmp_path):
    rows, paths, table, plot_msgs = smoke.run(str(tmp_path), quick=True)
    # all 6 predictors produced runs
    assert {r.predictor for r in rows} == {"one_epoch", "asha", "zeroshot", "scalar", "reasoning", "probe"}
    # per-run CSV + plot-data CSVs exist
    assert os.path.exists(paths["csv"])
    assert any(f.startswith("sample_eff_") and f.endswith(".csv") for f in os.listdir(tmp_path))
    # summary table mentions the headline metric
    assert "spearman" in table
    assert len(plot_msgs) >= 1
