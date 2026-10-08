"""One infrastructure retry, not independent evidence or repaired old results.

17014 stopped in warmup with zero formal candidates. Preserve its 12 unstarted
slots and cost. Same fixed startup-only/share2 contrast, two programs, 12 slots,
source seeds/input/image/6CPUs and worker/phase deadlines; total cap tightened
to 30min. No candidate-level retries. Submit only after full confirmation closes
and all prior actual GPU costs +1800 seconds fit the 3GPUh window.
"""
import os
from pathlib import Path
import subprocess
import sys
import neural_overlap_control as c
from neural_full_input_trial import accounted_costs
from lifecycle_pilot import read,write

R=Path('/research/d7/spc/yzyang4/scheduling-neural-overlap-retry-20261008-v2')
PRIOR=R.parent/'scheduling-neural-overlap-20261008-v1'
CONFIRM=R.parent/'scheduling-neural-full-confirmation-20261008-v1'

def mutate_plan(plan):
 c.mutate_plan(plan)
 plan.update(infrastructure_retry_of_job='17014',
  prior_failure='warmup kernel readiness deadline; zero formal candidates; prior receipts and cost retained',
  not_independent_training_seed_or_replacement=True,
  no_own_concurrent_heavy_preparation=True,
  total_cap_tightened_seconds=1800)

def set_scope():
 c.R=R;c.set_scope()
 c.r.NAME='neural_overlap_retry.py';c.r.CAP=1800;c.r.JOBNAME='r14-neural-overlap-retry'
 c.r.EXTRA_FILES=('neural_full_input_trial.py','neural_overlap_control.py')
 c.r.PLAN_MUTATOR=mutate_plan

def configure():
 set_scope()
 return c.r.configure()

def budget_gate():
 if read(PRIOR/'launch.json')['job']!='17014' or read(PRIOR/'closed.json')['attempted']!=0:
  raise ValueError('not a zero-candidate infrastructure retry')
 jobs=['16987','16989','16992','16994','16996','16997','16999','17004','17005','17014',read(CONFIRM/'launch.json')['job']]
 raw=subprocess.check_output(['sacct','-j',','.join(jobs),'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES'],
  env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=20)
 costs=accounted_costs(raw,jobs,'17004')
 if sum(costs.values())+1800>10800:raise ValueError('3GPUh window budget')
 write(R/'window-budget-before-submit.json',dict(prior_gpu_seconds=costs,
  prior_total_gpu_seconds=sum(costs.values()),new_gpu_seconds_cap=1800,window_seconds_cap=10800))

if __name__=='__main__':
 set_scope()
 if len(sys.argv)>1 and sys.argv[1]=='submit':budget_gate()
 if len(sys.argv)>1 and sys.argv[1]=='readout':
  import neural_pool_readout as report
  report.REFERENCE_ARM='pipeline'
 if len(sys.argv)>1 and sys.argv[1]=='audit':
  import argparse
  ap=argparse.ArgumentParser();ap.add_argument('mode');ap.add_argument('--plan-sha',required=True)
  c.audit(ap.parse_args().plan_sha)
 else:sys.exit(c.r.main())
