from phase1.verify_score_channel_prospective_analysis import expected_credit, sign_test


def test_independent_credit_and_sign_do_not_import_producer():
    assert expected_credit({"a": 1.0, "b": 1.0}, {"a": 2.0, "b": 1.0}) == 0.5
    rows = [
        {"run_id": "r1", "delta": 1.0},
        {"run_id": "r2", "delta": 1.0},
        {"run_id": "r3", "delta": 1.0},
        {"run_id": "r4", "delta": 1.0},
        {"run_id": "r5", "delta": 1.0},
        {"run_id": "r6", "delta": 1.0},
    ]
    assert sign_test(rows)["exact_p_two_sided"] == 0.03125
