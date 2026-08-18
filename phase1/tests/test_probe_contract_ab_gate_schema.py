from phase1.validate_probe_contract_ab import classify as primary_classify
from phase1.verify_probe_contract_ab_v2_independent import classify as independent_classify


def test_v2_primary_and_independent_gate_schemas_match() -> None:
    summary = {
        "contract_probe_valid": 4,
        "contract_coverage_120": 4,
        "coverage_gain": 0,
        "contract_full_valid": 4,
        "original_full_valid": 6,
        "paired_full_scores": 4,
        "median_relative_oriented_full_delta": 0.0,
        "catastrophic_harm_count": 0,
    }

    primary_verdict, primary_gates = primary_classify(summary, "v2")
    independent_verdict, independent_gates = independent_classify(summary)

    assert primary_verdict == independent_verdict == "QUALITY_KILL"
    assert primary_gates == independent_gates
    assert "quality_pairs_at_least_4" in primary_gates
    assert "quality_pairs_at_least_3" not in primary_gates
