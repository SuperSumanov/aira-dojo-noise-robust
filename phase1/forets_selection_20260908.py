"""Common batch selector; pure function, no model calls or result-label reads."""
import hashlib
import json
import math
import random

POLICIES = ('uniform_random', 'critic_topk_random')


def choose_slots(count, top_k, choose, policy, seed, task, step, scores=None):
    if policy not in POLICIES:
        raise ValueError('explicit supported selection policy required')
    if any(type(v) is not int or v <= 0 for v in (count, top_k, choose)) or choose > top_k:
        raise ValueError('invalid candidate/top-k/choose contract')
    if type(seed) is not int or type(step) is not int or step < 0 or not isinstance(task, str) or not task:
        raise ValueError('invalid independent selector identity')
    if policy == 'uniform_random':
        if scores is not None:
            raise ValueError('random baseline must not receive critic scores')
        eligible = list(range(count))
    else:
        if (not isinstance(scores, (list, tuple)) or len(scores) != count or
                any(type(s) not in (int, float) or not math.isfinite(s) for s in scores)):
            raise ValueError('complete finite score vector required')
        # Preserve stable slot-order ties. Sort the eligible set back into slot
        # order before drawing, so top-k==pool exactly couples to the random arm.
        ranked = sorted(range(count), key=lambda i: scores[i], reverse=True)
        eligible = sorted(ranked[:min(top_k, count)])
    identity = dict(domain='forets-selector-v2', seed=seed, task=task, step=step)
    key = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return random.Random(key).sample(eligible, min(choose, len(eligible)))
