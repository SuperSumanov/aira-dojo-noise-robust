"""Fixed independent full-input confirmation with no own concurrent heavy IO.

Same 12-slot source-seed schedule, original candidate/worker/input/image/CPUs.
Only a new allocation and tighter <=45min total cap; original per-worker limits.
Prepare only after donor closes 12/12. Submit after overlap-control closes and
all prior actual GPU seconds +2700 <=10800. No new samples or rescue retries.
"""
import os
from pathlib import Path
import subprocess
import sys

import neural_node_replication as r
from neural_full_input_trial import accounted_costs
from lifecycle_pilot import read,write

R=Path('/research/d7/spc/yzyang4/scheduling-neural-full-confirmation-20261008-v1')
D=Path('/research/d7/spc/yzyang4/scheduling-neural-full-input-20261008-v2')
PIN='e836f8c49b13ce52ef02c138b873bc1464cdb147dc06254f656b707ff93afade'


def batch_script(original):
    for token in ('--time=01:00:00','3560s srun','neural_full_input_trial.py controller',str(D)):
        if token not in original:raise ValueError('actual donor template')
    return original.replace(str(D),str(R)).replace('r14-neural-full-input','r14-neural-confirm').replace(
        '01:00:00','00:45:00').replace('3560s srun','2660s srun').replace(
        'neural_full_input_trial.py controller','neural_full_confirmation.py controller')


def mutate_plan(plan):
    plan.update(independent_confirmation_not_replacement=True,
        qualification='donor 12/12 execution completion only, not speedup/sign; no outcome-based replacement',
        known_interference_control='all own image hashing/data construction must finish before submission and remain inactive during allocation; shared-host isolation is not claimed',
        original_per_candidate_and_worker_limits_unchanged=True,
        input_scale='exact donor full public inputs and same query; no re-extraction or new sample')


def set_scope():
    r.R=R;r.D=D;r.DONOR=PIN;r.NAME='neural_full_confirmation.py'
    r.NODE='gpu27';r.CAP=2700;r.JOBNAME='r14-neural-confirm'
    r.FIXTURE_BUILDER=None;r.PLAN_MUTATOR=mutate_plan
    r.EXTRA_FILES=('neural_full_input_trial.py',)
    r.batch_script=batch_script
    r.QUESTION='Does the same fixed full-input serial/share2 timing contrast repeat without our own concurrent heavy preparation?'


def configure():
    set_scope()
    return r.configure()


def budget_gate():
    base=R.parent
    jobs=['16987','16989','16992','16994','16996','16997','16999','17004',
          read(D/'launch.json')['job'],
          read(base/'scheduling-neural-overlap-20261008-v1/launch.json')['job']]
    raw=subprocess.check_output(['sacct','-j',','.join(jobs),'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES'],
          env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=20)
    costs=accounted_costs(raw,jobs,'17004')
    if sum(costs.values())+2700>10800:raise ValueError('3GPUh window budget')
    write(R/'window-budget-before-submit.json',dict(prior_gpu_seconds=costs,
          prior_total_gpu_seconds=sum(costs.values()),new_gpu_seconds_cap=2700,window_seconds_cap=10800))


if __name__=='__main__':
    set_scope()
    if len(sys.argv)>1 and sys.argv[1]=='submit':budget_gate()
    sys.exit(r.main())
