"""Independent reverse-order replication of the completed new-program study.

Same two programs, inputs, source/harness seeds and three restart pairs. Only
the within-pair arm order is reversed relative to 17366; never pool the two
studies as independent tasks. No new source selection or runtime repair.
Prepare only AFTER the current live trial closes and is structurally audited.
"""
import datetime
import inspect
import os
from pathlib import Path
import subprocess
import sys

import neural_extension_20261010 as e
from lifecycle_pilot import read, sha, write

PREVIOUS = e.R
PREVIOUS_PLAN = 'bf0e2b24c267880ade8da3457ca5674b1a545c234485b3479ac0df41be2caa85'
PREVIOUS_RESULT = 'cfa91a7a48774fc10315423ab5547c6b3d65e60644fb4940647f387103094907'
LIVE = PREVIOUS.parent/'scheduling-live-twochild-20261010-v1'
LIVE_PLAN = '082645089d69e711f55057312d49e13d0fa99bf53942e91851791c12eb1525a6'
WINDOW_END = datetime.datetime(2026, 10, 10, 2, 56, 13, tzinfo=datetime.timezone.utc)
CAP = 4500
ORIGINAL_SCOPE = e.scope
ORIGINAL_MUTATE = e.mutate
ORIGINAL_BATCH = e.batch_script
ORIGINAL_SCHEDULE = e.c.schedule
ORIGINAL_BASE_SCHEDULE = e.c.BASE_SCHEDULE

e.R = PREVIOUS.parent/'scheduling-neural-reverse-order-20261010-v1'
e.NAME = 'neural_reverse_order_20261010.py'
e.CAP = CAP


def reverse_schedule():
    # The base function is captured before mutation. Program order, source RNG,
    # harness RNG and all 12 slots remain identical, only arm labels swap.
    return [dict(row, arm='share2' if row['arm']=='serial' else 'pipeline',
                 position=row['index'] % 2) for row in ORIGINAL_BASE_SCHEDULE()]


def mutate(plan):
    ORIGINAL_MUTATE(plan)
    plan.update(
        question='Does the fixed-program benefit persist when all three pair orders are reversed after observed chronological drift?',
        source_selection='Exact same two pre-existing extension pins; no new candidate choice or result-based replacement.',
        first_serial_gate='The first block is now share2: both original programs must complete; otherwise stop and retain all12.',
        independent_reverse_order_followup=True,
        previous_plan_sha256=PREVIOUS_PLAN, previous_primary_sha256=PREVIOUS_RESULT,
        inference='Three original-seed restarts of the same two sources. Report all three ratios and time trends separately from the earlier trial. Inversion reduces one order concern but does not isolate host co-tenancy or prove a stable causal effect.',
        original_frozen_gate_unchanged=True, same_readout_and_independent_audit=True,
        new_window_cost_cap_gpu_hours=10.25,
        reverse_order_batch_cap_gpu_hours=1.25,
        deadline_utc=WINDOW_END.isoformat())
    plan['preflight_items'].update(
        fixed_sample='same two extension program pins; all12 retained, no retries or replacement',
        distribution='same tasks/programs/source-seed restarts, not new workload diversity',
        balance='same within-study source/input/6physical CPU/one3090; reversed arm order in all three pairs',
        walltime='one3090/6physical CPU/75min all-in; existing450s candidates and1120s workers; stop on whole-block admission gate',
        power='3 pairs only; median>=1.05 exploratory gate retained, no population claim or pooled confirmation')


def batch_script(original):
    script = ORIGINAL_BATCH(original)
    if script.count('--time=01:30:00') != 1 or script.count('5350s srun') != 1:
        raise ValueError('original extension allocation interface')
    return script.replace('--time=01:30:00', '--time=01:15:00').replace(
        '5350s srun', '4450s srun').replace('r14-neural-extension', 'r14-neural-reverse')


def scope():
    ORIGINAL_SCOPE()
    e.c.r.EXTRA_FILES += ('neural_extension_20261010.py', 'test_neural_reverse_order.py')


e.c.schedule = reverse_schedule
e.mutate = mutate
e.batch_script = batch_script
e.scope = scope
# Correct only the inherited console budget label. The plan and batch script
# already derive their actual bounds from CAP; do not emit the old 1.5h label.
_prepare_source = inspect.getsource(e.prepare)
if _prepare_source.count('cap_gpu_hours=1.5') != 1:
    raise ValueError('preparation receipt interface')
exec(compile(_prepare_source.replace('cap_gpu_hours=1.5','cap_gpu_hours=1.25'),
             'reverse-prepare-label','exec'), e.__dict__)


def configure():
    return e.configure()


def prerequisites(now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if (WINDOW_END-now).total_seconds() < CAP+90:
        raise ValueError('insufficient remaining user window')
    if sha(PREVIOUS/'plan.json') != PREVIOUS_PLAN or sha(PREVIOUS/'readout-v1/summary.json') != PREVIOUS_RESULT:
        raise ValueError('previous exact scope')
    if sha(LIVE/'plan.json') != LIVE_PLAN or not (LIVE/'closed.json').exists():
        raise ValueError('live trial not closed; no concurrent preparation')
    result = read(LIVE/'readout-v1/summary.json')
    if result['plan_sha256'] != LIVE_PLAN or result['complete'] != 16 or not result['structural_audit']:
        raise ValueError('live structural closeout must be complete first')
    # This prerequisite does NOT use quality scores, feedback counts, or go.
    return result


def accounted_costs(raw):
    expected = {'17364':1, '17366':1, '17368':3}
    found = {}
    for line in raw.splitlines():
        fields = line.split('|')
        if fields[0] not in expected:
            continue
        job, state, seconds, allocation = fields[:4]
        if job in found or state.split()[0] not in ('COMPLETED','FAILED','CANCELLED','TIMEOUT','NODE_FAIL','OUT_OF_MEMORY','PREEMPTED'):
            raise ValueError('nonterminal/duplicate resource accounting')
        tres = dict(v.split('=',1) for v in allocation.split(',') if '=' in v)
        if int(tres.get('gres/gpu',0)) != expected[job]:
            raise ValueError('unexpected allocation scope')
        found[job] = int(seconds)*expected[job]
    if set(found) != set(expected) or any(v < 0 for v in found.values()):
        raise ValueError('incomplete accounting')
    if sum(found.values())+CAP > 10.25*3600:
        raise ValueError('whole-window cap')
    return found


def budget_gate():
    prerequisites()
    env = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    raw = subprocess.check_output(['sacct','-X','-j','17364,17366,17368','-n','-P',
        '-o','JobIDRaw,State,ElapsedRaw,AllocTRES'], env=env, text=True, timeout=20)
    costs = accounted_costs(raw)
    write(e.R/'reverse-window-budget-before-submit.json',dict(
        prior_actual_gpu_seconds=costs,new_batch_gpu_seconds_cap=CAP,
        total_actual_plus_new_cap=sum(costs.values())+CAP,window_cap=36900,
        no_reuse_or_reopen_of_old_roots=True))


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv)>1 else None
    if mode=='prepare':
        prerequisites()
    if mode=='submit':
        budget_gate()
    if mode=='controller':
        prerequisites() # Recheck the full remaining allowance after queueing.
    sys.exit(e.main())
