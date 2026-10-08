"""Startup-only versus full overlap: 12 fixed neural executions, <=.75GPUh.

No changes to candidate/Adam instrumentation/input/worker deadlines. A trusted
boundary waits after prelude and before candidate start, through previous close.
Both policies retain two worker slots and the same six-CPU/one-GPU allocation.
Run only after full-input trial closes and actual window +2700s <=10800s.
"""
import os
from pathlib import Path
import subprocess
import sys
import time

import neural_node_replication as r
import neural_pool_trial as n
from lifecycle_pilot import read, write, sha
from neural_full_input_trial import accounted_costs

R=Path('/research/d7/spc/yzyang4/scheduling-neural-overlap-20261008-v1')
BASE_SCHEDULE=n.schedule


def schedule():
    return [dict(row, arm='pipeline' if row['arm']=='serial' else row['arm'],
                 position=row['index']%2) for row in BASE_SCHEDULE()]


def predecessor(row):
    return row['index']-1 if row['arm']=='pipeline' and row['position']==1 else None


def wait_turn(row,ep):
    previous=predecessor(row)
    ready=time.time()
    write(ep/'prelude_ready.json',dict(time=ready,predecessor=previous))
    if previous is not None:
        path=R/f'episode-{previous}/closed.json'
        while not path.with_name('closed.ready').exists():
            if time.time()-ready>450:raise TimeoutError('pipeline predecessor wait')
            time.sleep(.02)
        if read(path)['returncode']!=0:raise ValueError('failed pipeline predecessor')
    write(ep/'execution_admitted.json',dict(time=time.time()))


def boundary_write(path,value):
    """Keep timestamps after admission; never expose partial close JSON."""
    is_episode=path.parent.parent==R and path.parent.name.startswith('episode-')
    if is_episode and path.name=='candidate_started.json':
        index=int(path.parent.name.removeprefix('episode-'))
        if index!=36:
            wait_turn(schedule()[index],path.parent)
            value=dict(value,time=time.time())
    result=write(path,value)
    if is_episode and path.name=='closed.json':
        path.with_name('closed.ready').touch(exist_ok=False)
    return result


def mutate_plan(plan):
    plan.update(schedule=schedule(),reference_policy='pipeline',
        first_serial_gate='first startup-parallel/candidate-serial pair must both complete, otherwise stop',
        single_change='Both policies initialize two sandboxes concurrently. Pipeline admits candidate two only after candidate one closes; share2 admits immediately.',
        writer_hook='boundary_write adds trusted admission barrier and correct post-wait start timestamp; original worker and supervisor AST unchanged, not claim of identical runtime semantics',
        barrier_wait_cap_seconds=450,interpreter_deadline_seconds=525,worker_hard_seconds=550,
        no_candidate_or_training_changes=True,
        decision='12 complete, three paired blocks, identical steps and original numerical tolerance; median pipeline/share2>=1.05 exploratory only; keep all failures, no retries',
        queue_wait_is_inside_unchanged_worker_deadline=True)


def set_scope():
    r.R=R;r.NAME='neural_overlap_control.py';r.NODE='gpu27';r.CAP=2700
    r.JOBNAME='r14-neural-overlap';r.FIXTURE_BUILDER=None;r.PLAN_MUTATOR=mutate_plan
    r.EXTRA_FILES=('neural_full_input_trial.py',)
    r.QUESTION='Does overlapping candidate execution beat startup-only overlap on the SAME fixed neural programs and inputs?'
    n.schedule=schedule;n.write=boundary_write


def configure():
    set_scope()
    return r.configure()


def budget_gate():
    base=R.parent
    jobs=['16987','16989','16992','16994','16996','16997','16999','17004',
          read(base/'scheduling-neural-full-input-20261008-v2/launch.json')['job']]
    raw=subprocess.check_output(['sacct','-j',','.join(jobs),'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES'],
         env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=20)
    costs=accounted_costs(raw,jobs,'17004')
    if sum(costs.values())+2700>10800:raise ValueError('3GPUh window budget')
    write(R/'window-budget-before-submit.json',dict(prior_gpu_seconds=costs,
         prior_total_gpu_seconds=sum(costs.values()),new_gpu_seconds_cap=2700,window_seconds_cap=10800))


def audit(plan_sha):
    import audit_neural_result as a
    if sha(R/'plan.json')!=plan_sha:raise ValueError('independent plan pin')
    rows=read(R/'runs.json');allocation=read(R/'allocation.json');checks=[]
    for row in rows:
        ep=R/f'episode-{row["index"]}'
        if (ep/'started.json').exists() and read(ep/'started.json')['affinity']!=allocation['affinity']:
            raise ValueError('CPU identity')
        if (ep/'native.json').exists() and read(ep/'native.json')['gpu_uuids']!=[allocation['gpu_uuid']]:
            raise ValueError('GPU identity')
        if row['status']!='complete':continue
        ready=read(ep/'prelude_ready.json')['time'];admit=read(ep/'execution_admitted.json')['time']
        start=read(ep/'candidate_started.json')['time'];end=read(ep/'candidate_ended.json')['time']
        done=read(ep/'completed.json');previous=predecessor(row)
        if not done['start']<=ready<=admit<=start<=end<=done['end']:raise ValueError('stage order')
        if previous is not None and read(R/f'episode-{previous}/closed.json')['end']>admit:
            raise ValueError('pipeline candidate overlap')
        checks.append(dict(index=row['index'],arm=row['arm'],program=row['program'],
                           initialization=ready-done['start'],queue=admit-ready,
                           candidate=end-start,after_candidate=done['end']-end))
    a.ROOT=R;a.PLAN_SHA=plan_sha;a.REFERENCE_ARM='pipeline';a.main()
    write(R/'audit-v1/pipeline-contract.json',dict(plan_sha256=plan_sha,
          full_denominator=12,stages=checks,same_CPU_GPU=True,pipeline_barriers_verified=True))


if __name__=='__main__':
    set_scope()
    if len(sys.argv)>1 and sys.argv[1]=='submit':budget_gate()
    if len(sys.argv)>1 and sys.argv[1]=='readout':
        import neural_pool_readout as report
        report.REFERENCE_ARM='pipeline'
    if len(sys.argv)>1 and sys.argv[1]=='audit':
        import argparse
        ap=argparse.ArgumentParser();ap.add_argument('mode');ap.add_argument('--plan-sha',required=True)
        audit(ap.parse_args().plan_sha)
    else:sys.exit(r.main())
