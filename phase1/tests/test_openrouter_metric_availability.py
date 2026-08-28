from phase1 import audit_openrouter_metric_availability as audit


def test_consensus_status_is_exact_and_fail_closed() -> None:
    assert audit.consensus_status(set()) == "missing"
    assert audit.consensus_status({"accuracy"}) == "unique"
    assert audit.consensus_status({"Accuracy", "accuracy"}) == "ambiguous"


def test_pair_consensus_separates_different_run_task_keys() -> None:
    metrics = {("run-a", "task-a"): {"accuracy"}}
    assert (
        audit.pair_consensus_status(
            ("run-a", "task-a", False), ("run-b", "task-a", False), metrics
        )
        == "different_run_task_key"
    )
    assert (
        audit.pair_consensus_status(
            ("run-a", "task-a", False), ("run-a", "task-a", False), metrics
        )
        == "unique"
    )
