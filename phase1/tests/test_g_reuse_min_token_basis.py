import pytest

from phase1.g_reuse_min_token_basis import choose_basis, metrics, read_lengths


def test_minimum_token_edge_is_chosen_and_connectivity_preserved():
    local = [('a', 'b'), ('c', 'd'), ('e', 'f')]
    reuse = [('b', 'c'), ('a', 'd'), ('d', 'e')]
    lengths = dict(a=10, b=1, c=1, d=5, e=1, f=1)
    assert choose_basis(local, reuse, lengths) == [('b', 'c'), ('d', 'e')]


def test_tie_break_is_orientation_and_order_invariant():
    local = [('a', 'b'), ('c', 'd')]
    reuse = [('b', 'c'), ('a', 'd')]
    lengths = dict(a=1, b=1, c=1, d=1)
    assert choose_basis(local, reuse, lengths) == [('a', 'd')]
    assert choose_basis(list(reversed(local)), list(reversed(reuse)), lengths) == [('a', 'd')]


def test_length_rows_are_bound_to_sorted_identity():
    rows = [{'ordinal': str(i), 'raw_tokens': str(raw), 'valid_tokens': str(min(raw, 16384)),
             'encoding_sha256': 'a'*64} for i, raw in enumerate([20, 17000])]
    assert read_lengths({'a', 'b'}, rows) == {'a': 20, 'b': 16384}


def test_metric_gate_passes_for_large_synthetic_reduction():
    local, full = [('a', 'b'), ('c', 'd')], [('b', 'c')]*3
    basis = [('b', 'c')]
    task_of = {node: 't' for node in 'abcd'}
    lengths = {node: 1 for node in 'abcd'}
    result = metrics(local, full, basis, task_of, lengths)
    assert result['full_rank_gain'] == result['basis_rank_gain'] == 1
    assert result['g_token_reduction_fraction'] == pytest.approx(2/3)
    assert not result['all_gates_pass']  # Production's fixed total-gain=790 gate must not be relaxed.
