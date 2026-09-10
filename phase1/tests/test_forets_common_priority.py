from collections import Counter
from itertools import combinations, permutations
import random
import pytest
from phase1 import forets_common_priority as m


@pytest.mark.parametrize('n', [1, 2, 3, 4, 5])
def test_exhaustive_coupling_and_uniform_marginal(n):
    pool = list(range(n))
    for size in range(1, n+1):
        for eligible in combinations(pool, size):
            counts = Counter()
            for order in permutations(pool):
                chosen = m.select_from_order(order, eligible)[0]; counts[chosen] += 1
                assert (chosen != order[0]) == (order[0] not in eligible)
                assert m.select_from_order(order, pool) == [order[0]]
            assert set(counts) == set(eligible) and len(set(counts.values())) == 1


def test_ordered_multichoice_is_uniform():
    counts = Counter(tuple(m.select_from_order(p, [0, 1, 3], 2)) for p in permutations(range(4)))
    assert len(counts) == 6 and len(set(counts.values())) == 1


def test_rng_isolation_reproducibility_and_full_pool():
    before = random.getstate()
    for seed in range(32):
        args = (3, 3, 1)
        r = m.choose_slots(*args, 'uniform_random', seed, 'artificial-task', 1)
        for policy in ('critic_topk_random', 'permuted_topk_random'):
            assert m.choose_slots(*args, policy, seed, 'artificial-task', 1, [0.3, 0.2, 0.1]) == r
        assert m.choose_slots(*args, 'uniform_random', seed, 'artificial-task', 1) == r
    assert random.getstate() == before


def test_ties_explicitly_keep_stable_slot_rule():
    for seed in range(32):
        c = m.choose_slots(4, 2, 1, 'critic_topk_random', seed, 'artificial', 1, [1.0]*4)
        s = m.choose_slots(4, 2, 1, 'permuted_topk_random', seed, 'artificial', 1, [1.0]*4)
        assert c == s and c[0] in (0, 1)


@pytest.mark.parametrize('scores', [[1.0], [1.0, float('nan')], [True, 1.0], None])
def test_incomplete_or_invalid_scores(scores):
    with pytest.raises(ValueError): m.choose_slots(2, 1, 1, 'critic_topk_random', 0, 'artificial', 1, scores)


@pytest.mark.parametrize('order,eligible', [([0, 0], [0]), ([False, 1], [0]), ([0, 1], []), ([0, 1], [2]), ([0, 1], [1, 1])])
def test_invalid_pool(order, eligible):
    with pytest.raises(ValueError): m.select_from_order(order, eligible)
