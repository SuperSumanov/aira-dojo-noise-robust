from phase1.g_reuse_decision_context_reach import arm_summary, parent_projection


def test_parent_projection_rejects_multi_context_endpoint():
    rows = [
        {"better": "a", "worse": "b", "task": "t", "parent": "p1", "intask_split": "train"},
        {"better": "a", "worse": "c", "task": "t", "parent": "p2", "intask_split": "train"},
    ]
    task_of = {"a": "t", "b": "t", "c": "t"}
    try:
        parent_projection(rows, task_of)
    except ValueError as exc:
        assert str(exc) == "endpoint_multiple_contexts"
    else:
        raise AssertionError("multi-context endpoint was accepted")


def test_arm_summary_counts_parent_reach():
    local = [("a1", "a2"), ("b1", "b2"), ("c1", "c2")]
    edge_parent = {
        ("a1", "a2"): ("t", "p1"),
        ("b1", "b2"): ("t", "p2"),
        ("c1", "c2"): ("t", "p3"),
    }
    parent_of = {
        "a1": ("t", "p1"), "a2": ("t", "p1"),
        "b1": ("t", "p2"), "b2": ("t", "p2"),
        "c1": ("t", "p3"), "c2": ("t", "p3"),
    }
    task_of = {node: "t" for node in parent_of}
    lengths = {node: 10 for node in parent_of}
    result = arm_summary(
        "x", [("a1", "b1"), ("b2", "c1")], local,
        edge_parent, parent_of, task_of, lengths,
    )
    assert result["cross_context_edges"] == 2
    assert result["contexts_touched"] == 3
    assert result["parent_rank_gain"] == 2
    assert result["tasks_with_positive_parent_rank_gain"] == 1
    assert result["local_pairs_any_endpoint_touched"] == 3
    assert result["local_pairs_both_endpoints_touched"] == 1
    assert result["g_tokens"] == 40
