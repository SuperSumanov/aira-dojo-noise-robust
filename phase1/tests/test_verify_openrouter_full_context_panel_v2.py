from phase1 import verify_openrouter_full_context_panel_v2 as verifier


def test_gap_bins_use_frozen_half_open_boundaries() -> None:
    bins = [
        {"name": "one", "lower_inclusive": 1, "upper_exclusive": 2},
        {"name": "two", "lower_inclusive": 2, "upper_exclusive": None},
    ]
    assert verifier.assign_gap_bin(1.0, bins) == "one"
    assert verifier.assign_gap_bin(1.999, bins) == "one"
    assert verifier.assign_gap_bin(2.0, bins) == "two"
    assert verifier.assign_gap_bin(0.999, bins) is None
