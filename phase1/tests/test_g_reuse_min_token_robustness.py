import pytest

from phase1.g_reuse_min_token_robustness import cost_stats, read_raw_lengths


def test_raw_lengths_are_identity_bound_and_validate_16k_column():
    rows = [{'ordinal': str(i), 'raw_tokens': str(raw), 'valid_tokens': str(min(raw, 16384)),
             'encoding_sha256': 'a'*64} for i, raw in enumerate([20, 17000])]
    assert read_raw_lengths({'a', 'b'}, rows) == {'a': 20, 'b': 17000}


def test_raw_lengths_reject_inconsistent_existing_valid_column():
    rows = [{'ordinal': '0', 'raw_tokens': '17000', 'valid_tokens': '17000',
             'encoding_sha256': 'a'*64}]
    with pytest.raises(ValueError, match='length_value'):
        read_raw_lengths({'a'}, rows)


def test_anonymous_cost_stats_reports_leave_one_and_breadth():
    full = [('a', 'b'), ('a', 'c'), ('d', 'e'), ('d', 'f')]
    basis = [('a', 'b'), ('d', 'e')]
    task_of = {node: ('x' if node in 'abc' else 'y') for node in 'abcdef'}
    stats, qualifying = cost_stats(full, basis, task_of, {node: 1 for node in 'abcdef'})
    assert stats['reduction_fraction'] == pytest.approx(0.5)
    assert stats['leave_one_task_min_reduction'] == pytest.approx(0.5)
    assert stats['max_task_saved_share'] == pytest.approx(0.5)
    assert stats['tasks_reduction_at_least_0_50'] == 2
    assert qualifying == {'x', 'y'}
