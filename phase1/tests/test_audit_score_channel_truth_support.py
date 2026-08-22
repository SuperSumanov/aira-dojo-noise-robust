from phase1.audit_score_channel_truth_support import summarize_support


def test_truth_support_funnel_separates_ties_and_channel_coverage():
    selected = [
        {
            "task": "task-a",
            "run_id": "run-a",
            "parent_id": "parent-a",
            "candidate_card_ids": ["a", "b"],
        },
        {
            "task": "task-b",
            "run_id": "run-b",
            "parent_id": "parent-b",
            "candidate_card_ids": ["c", "d"],
        },
    ]
    labels = {"a": 0.5, "b": 0.5, "c": 0.0, "d": 1.0}
    results = {
        "a": {
            "sub_exists": True,
            "sub_score": 0.2,
            "val_how": "keyed",
            "stdout_val": 0.3,
        },
        "b": {
            "sub_exists": True,
            "sub_score": 0.4,
            "val_how": "keyed",
            "stdout_val": 0.1,
        },
        "c": {
            "sub_exists": False,
            "sub_score": None,
            "val_how": "keyed",
            "stdout_val": 0.1,
        },
        "d": {
            "sub_exists": False,
            "sub_score": None,
            "val_how": "keyed",
            "stdout_val": 0.2,
        },
    }
    value = summarize_support(selected, labels, results)
    assert value["truth_support"]["all_tied_parents"] == 1
    assert value["truth_support"]["nontied_parents"] == 1
    assert value["identifiability_funnel"] == {
        "structural_parents": 2,
        "truth_informative_parents": 1,
        "external_comparative_and_truth_informative": 0,
        "stdout_comparative_and_truth_informative": 1,
        "paired_channels_comparative_and_truth_informative": 0,
    }
    assert value["primary_common_support"] == {
        "comparative_parents": 1,
        "cards": 2,
        "truth_tied_parents": 1,
        "truth_nontied_parents": 0,
    }
    assert value["interpretation"][
        "evidence_for_channel_equality_or_external_harm_allowed"
    ] is False
