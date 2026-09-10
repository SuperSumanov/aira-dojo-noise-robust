"""UNDEPLOYED experiment helper: common random ordering, then eligibility filter.

This is a standard coupling, not a new learned method or a measured improvement.
It does not replace forets_selection_20260908 or change any recorded campaign.
"""
import hashlib
import json
import math
import random


def _rng(seed, task, step, purpose):
    if type(seed) is not int or type(step) is not int or step < 0 or not isinstance(task, str) or not task:
        raise ValueError('invalid_random_identity')
    key = json.dumps({'version': 'forets-common-priority-v1', 'seed': seed,
                      'task': task, 'step': step, 'purpose': purpose}, sort_keys=True, separators=(',', ':'))
    return random.Random(hashlib.sha256(key.encode()).hexdigest())


def select_from_order(order, eligible, choose=1):
    if (not isinstance(order, (list, tuple)) or not order or any(type(i) is not int for i in order)
            or sorted(order) != list(range(len(order)))):
        raise ValueError('not_a_pool_permutation')
    if (not isinstance(eligible, (list, tuple, set, frozenset)) or not eligible
            or any(type(i) is not int for i in eligible) or len(set(eligible)) != len(eligible)
            or not set(eligible).issubset(order) or type(choose) is not int or choose <= 0):
        raise ValueError('invalid_eligible_set_or_choose')
    return [i for i in order if i in set(eligible)][:choose]


def choose_slots(count, top_k, choose, policy, seed, task, step, scores=None):
    if (any(type(x) is not int or x <= 0 for x in (count, top_k, choose)) or choose > top_k
            or policy not in ('uniform_random', 'critic_topk_random', 'permuted_topk_random')):
        raise ValueError('invalid_contract')
    order = list(range(count))
    _rng(seed, task, step, 'selection_order').shuffle(order)
    if policy == 'uniform_random':
        if scores is not None: raise ValueError('random_arm_must_not_read_scores')
        eligible = list(range(count))
    else:
        if (not isinstance(scores, (list, tuple)) or len(scores) != count
                or any(type(s) not in (int, float) or not math.isfinite(s) for s in scores)):
            raise ValueError('finite_complete_scores_required')
        assigned = list(scores)
        if policy == 'permuted_topk_random':
            _rng(seed, task, step, 'score_permutation').shuffle(assigned)
        # Preserve the old stable slot-order tie rule, explicitly not a tie fix.
        eligible = sorted(range(count), key=lambda i: assigned[i], reverse=True)[:min(top_k, count)]
    return select_from_order(order, eligible, choose)
