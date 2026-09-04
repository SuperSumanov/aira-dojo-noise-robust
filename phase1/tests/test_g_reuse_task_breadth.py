import pytest

from phase1.g_reuse_task_breadth import component_count, derive_reuse, summarize
from phase1.verify_g_reuse_task_breadth import count_components, recompute


def fixture():
    local = [('a', 'b'), ('c', 'd'), ('e', 'f'), ('g', 'h')]
    global_all = [('b', 'c'), ('f', 'g'), ('a', 'x'), ('a', 'b')]
    run_of = {v: 'r1' for v in 'abcdefgh'} | {'x': 'r2'}
    task_of = {v: 't1' for v in 'abcd'} | {v: 't2' for v in 'efghx'}
    grouped = {'r1': [{'id': v, 'task': {'name': task_of[v]}} for v in 'abcdefgh'],
               'r2': [{'id': 'x', 'task': {'name': 't2'}}]}
    return local, global_all, run_of, task_of, grouped


def test_exact_reuse_and_independent_bfs():
    local, global_all, run_of, task_of, grouped = fixture()
    reuse = derive_reuse(local, global_all, run_of, task_of)
    assert set(reuse) == {('b', 'c'), ('f', 'g')}
    metrics = summarize(local, reuse, task_of)
    count, independent = recompute(set(local), set(global_all), grouped)
    assert count == 2
    assert metrics == independent
    assert metrics['total_rank_gain'] == 2
    assert metrics['tasks_with_positive_rank_gain'] == 2
    assert not metrics['all_gates_pass']


def test_order_orientation_invariance():
    local, global_all, run_of, task_of, _ = fixture()
    reuse = derive_reuse(local, global_all, run_of, task_of)
    reversed_local = [(b, a) for a, b in reversed(local)]
    reversed_reuse = [(b, a) for a, b in reversed(reuse)]
    assert summarize(local, reuse, task_of) == summarize(reversed_local, reversed_reuse, task_of)


def test_component_implementations_agree():
    nodes = set('abcdef')
    for edges in [[], [('a', 'b')], [('a', 'b'), ('c', 'd')],
                  [('a', 'b'), ('b', 'c'), ('a', 'c')]]:
        assert component_count(nodes, edges) == count_components(nodes, set(edges))


def synthetic_task(task, gain):
    local, reuse = [], []
    for i in range(gain + 1):
        a, b = f'{task}a{i}', f'{task}b{i}'
        local.append((a, b))
        if i:
            reuse.append((f'{task}b{i-1}', a))
    return local, reuse


def test_exact_gate_boundary_twenty_tasks_and_twenty_percent():
    local, reuse, task_of = [], [], {}
    # Five tasks gain four and fifteen gain one: total 35, max share < 0.20.
    for index, gain in enumerate([4] * 5 + [1] * 15):
        l_part, r_part = synthetic_task(f't{index}', gain)
        local.extend(l_part); reuse.extend(r_part)
        for edge in l_part:
            task_of[edge[0]] = task_of[edge[1]] = f't{index}'
    result = summarize(local, reuse, task_of)
    assert result['tasks_with_positive_rank_gain'] == 20
    assert result['all_gates_pass']


def test_single_task_dominance_fails():
    local, reuse, task_of = [], [], {}
    for index, gain in enumerate([21] + [1] * 20):
        l_part, r_part = synthetic_task(f't{index}', gain)
        local.extend(l_part); reuse.extend(r_part)
        for edge in l_part:
            task_of[edge[0]] = task_of[edge[1]] = f't{index}'
    result = summarize(local, reuse, task_of)
    assert result['tasks_with_positive_rank_gain'] == 21
    assert result['max_task_gain_share'] > 0.20
    assert not result['all_gates_pass']


def test_unlisted_or_outside_edges_are_not_rescued():
    local, global_all, run_of, task_of, _ = fixture()
    task_of['q'] = 't1'; run_of['q'] = 'r2'
    task_of['z'] = 'other'; run_of['z'] = 'r1'
    assert set(derive_reuse(local, global_all + [('a', 'q'), ('a', 'z')], run_of, task_of)) == {
        ('b', 'c'), ('f', 'g')}


@pytest.mark.parametrize('nodes,edges', [(set(), []), ({'a'}, [])])
def test_isolated_nodes_count(nodes, edges):
    assert component_count(nodes, edges) == len(nodes)
    assert count_components(nodes, set(edges)) == len(nodes)
