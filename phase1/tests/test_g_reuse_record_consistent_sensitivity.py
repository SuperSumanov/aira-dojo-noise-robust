from phase1.g_reuse_record_consistent_sensitivity import decide, record_consistent
from phase1.verify_g_reuse_record_consistent_sensitivity import decide as independent_decide


def metrics(pairs, gain, positive, maximum):
    return {'reuse_pairs': pairs, 'total_rank_gain': gain, 'tasks': 28,
            'tasks_with_positive_rank_gain': positive, 'max_task_rank_gain': maximum,
            'max_task_gain_share': maximum/gain, 'anonymous_task_rows': []}


def test_record_consistent_exact_union_exclusion():
    cards = {'a': ('r1', 't', 'c1', (True,)*4), 'b': ('r2', 't', 'c1', (True,)*4),
             'c': ('r3', 't', 'c2', (True,)*4), 'd': ('r4', 't', 'c1', (True,)*4)}
    batches = {'r1': ('t', 'unique', 'x'), 'r2': ('t', 'unique', 'x'),
               'r3': ('t', 'unique', 'x'), 'r4': ('t', 'missing', None)}
    assert record_consistent([('a', 'b'), ('a', 'c'), ('a', 'd')], cards, batches) == [('a', 'b')]


def test_three_gate_boundary_and_independent_decision():
    full, filtered = metrics(100, 100, 28, 12), metrics(80, 80, 20, 16)
    result = decide(full, filtered)
    assert result == independent_decide(full, filtered)
    assert result['all_gates_pass'] and result['rank_gain_retention'] == 0.8
    assert result['max_task_gain_share'] == 0.2


def test_each_gate_can_fail_without_rescue():
    full = metrics(100, 100, 28, 10)
    assert not decide(full, metrics(70, 79, 28, 10))['all_gates_pass']
    assert not decide(full, metrics(80, 80, 19, 10))['all_gates_pass']
    assert not decide(full, metrics(80, 80, 28, 17))['all_gates_pass']
