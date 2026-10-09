"""Independent program-order replication; explicit prospective entry amendment.

The unsubmitted predecessor unnecessarily required all 16 unrelated live agent
trajectories to succeed. One live model-call timeout was observed before this
amendment; no live quality values or reverse-order outcomes were inspected.
Require full live resource/identity closure, not agent success. Keep exactly
the same 12 neural executions, seeds, inputs, limits and original effect gate.
"""
import datetime
import sys

import neural_reverse_order_20261010 as old
from lifecycle_pilot import read, sha

ABANDONED_ROOT = old.e.R
OLD_SCOPE = old.e.scope
OLD_MUTATE = old.e.mutate
old.e.R = ABANDONED_ROOT.parent/'scheduling-neural-reverse-independent-20261010-v1'
old.e.NAME = 'neural_reverse_independent_20261010.py'


def scope():
    OLD_SCOPE()
    old.e.c.r.EXTRA_FILES += ('neural_reverse_order_20261010.py',
                              'test_neural_reverse_independent.py')


def mutate(plan):
    OLD_MUTATE(plan)
    plan.update(
        independent_entry_amendment=True,
        abandoned_unsubmitted_root=str(ABANDONED_ROOT),
        observed_before_amendment='Live17368 second block index6 terminated with bounded model-call TimeoutError; cleanup passed. No live quality values or reverse-order results inspected.',
        amendment_reason='Unrelated generator success is not a prerequisite for fixed programs with no generator. Both studies still require separate immutable roots; live failure remains in its original denominator/gates.',
        entry_rule='After live all-four-slot identity/queue/resource closeout and primary readout, regardless of agent success or score. No concurrent heavy preparation. Same whole-window time/cost gates.',
        unchanged='12 executions, same sources/inputs/RNG, reversed arm order, candidate450s, worker1120s, one3090/6physical CPU/75min, all12/three-pair/output/step/median>=1.05 effect gate.',
        no_claim_of_original_conditional_protocol_pass=True)


def prerequisites(now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if (old.WINDOW_END-now).total_seconds() < old.CAP+90:
        raise ValueError('insufficient remaining user window')
    if (ABANDONED_ROOT/'launch.json').exists() or (ABANDONED_ROOT/'submit-intent.json').exists():
        raise ValueError('predecessor submitted: no duplicate study')
    if sha(old.PREVIOUS/'plan.json') != old.PREVIOUS_PLAN or sha(old.PREVIOUS/'readout-v1/summary.json') != old.PREVIOUS_RESULT:
        raise ValueError('previous exact fixed-program scope')
    if sha(old.LIVE/'plan.json') != old.LIVE_PLAN or not (old.LIVE/'closed.json').exists():
        raise ValueError('live resource use not closed')
    result = read(old.LIVE/'readout-v1/summary.json')
    if (result['plan_sha256'] != old.LIVE_PLAN or result['assigned'] != 16
            or result['observed_pool_pairs'] != 2 or result['structural_audit'] is not True
            or result['controller_error'] is not None):
        raise ValueError('complete four-slot structural closeout required')
    # Deliberately no complete-run count, endpoint value, feedback or go check.
    return result


old.e.scope = scope
old.e.mutate = mutate
old.prerequisites = prerequisites


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv)>1 else None
    if mode in ('prepare','controller'):
        prerequisites()
    if mode == 'submit':
        old.budget_gate()
    sys.exit(old.e.main())
