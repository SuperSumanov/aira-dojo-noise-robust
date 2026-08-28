from phase1 import audit_openrouter_metric_availability as audit


def test_consensus_status_is_exact_and_fail_closed() -> None:
    assert audit.consensus_status(set()) == "missing"
    assert audit.consensus_status({"accuracy"}) == "unique"
    assert audit.consensus_status({"Accuracy", "accuracy"}) == "ambiguous"
