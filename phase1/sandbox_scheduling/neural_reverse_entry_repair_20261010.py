"""One independent entry-interface repair after job17376, zero formal starts.

Only restore the configure export required by the unchanged container wrapper.
Retain the failed root and all its cost; same programs/order/limits/effect gate.
"""
import os
from pathlib import Path
import subprocess
import sys
import neural_reverse_independent_20261010 as predecessor
from lifecycle_pilot import read,sha,write

old=predecessor.old
FAILED=Path('/research/d7/spc/yzyang4/scheduling-neural-reverse-independent-20261010-v1')
FAILED_PLAN='88fd90528961d58e49ff79518d186b79048be5a8f9729f3a85aa80ce9f78b7cd'
BASE_SCOPE=old.e.scope
BASE_MUTATE=old.e.mutate
old.e.R=FAILED.with_name('scheduling-neural-reverse-entry-repair-20261010-v1')
old.e.NAME='neural_reverse_entry_repair_20261010.py'


def configure():
    # The frozen bin/singularity imports this exact public entry point.
    return old.e.configure()


def scope():
    BASE_SCOPE()
    old.e.c.r.EXTRA_FILES += ('neural_reverse_independent_20261010.py','test_neural_reverse_entry_repair.py')


def mutate(plan):
    BASE_MUTATE(plan)
    plan.update(entry_interface_repair=True,failed_root=str(FAILED),failed_plan_sha256=FAILED_PLAN,
        failure='17376: container wrapper could not import configure from the prior thin entry; warmup failed, all12 formal executions unstarted. 63 allocated GPU seconds retained.',
        repair='Delegate the required configure export to the existing unchanged extension configure. No candidate/image/input/seed/order/timeout/effect-gate change.',
        additional_failed_job_in_window_accounting='17376',single_repair_batch=True)


def prerequisites(now=None):
    predecessor.prerequisites(now)
    if sha(FAILED/'plan.json')!=FAILED_PLAN or str(read(FAILED/'launch.json')['job'])!='17376':
        raise ValueError('exact failed predecessor')
    closed=read(FAILED/'closed.json')
    if closed['planned']!=12 or closed['attempted']!=0 or closed['completed']!=0:
        raise ValueError('no formal source result may be replaced')
    if any((FAILED/f'episode-{i}/started.json').exists() for i in range(12)):
        raise ValueError('formal execution unexpectedly started')


def accounted_costs(raw):
    costs=old.accounted_costs(raw)
    rows=[s.split('|') for s in raw.splitlines() if s.split('|')[0]=='17376']
    if len(rows)!=1 or rows[0][1].split()[0]!='FAILED': raise ValueError('failed-job accounting')
    tres=dict(s.split('=',1) for s in rows[0][3].split(',') if '=' in s)
    seconds=int(rows[0][2])
    if int(tres.get('gres/gpu',0))!=1 or seconds<0: raise ValueError('failed allocation scope')
    costs['17376']=seconds
    if sum(costs.values())+old.CAP>36900: raise ValueError('whole-window cap includes failure')
    return costs


def budget_gate():
    prerequisites()
    raw=subprocess.check_output(['sacct','-X','-j','17364,17366,17368,17376','-n','-P',
        '-o','JobIDRaw,State,ElapsedRaw,AllocTRES'],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=20)
    costs=accounted_costs(raw)
    write(old.e.R/'repair-window-budget-before-submit.json',dict(prior_actual_gpu_seconds=costs,
        new_batch_gpu_seconds_cap=old.CAP,total_actual_plus_new_cap=sum(costs.values())+old.CAP,
        window_cap=36900,closed_failed_batch_not_reopened=True))


old.e.scope=scope
old.e.mutate=mutate
if __name__=='__main__':
    mode=sys.argv[1] if len(sys.argv)>1 else None
    if mode in ('prepare','controller'): prerequisites()
    if mode=='submit': budget_gate()
    sys.exit(old.e.main())
