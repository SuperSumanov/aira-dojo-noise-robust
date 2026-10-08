"""Fixed input-scale check; not a retry of a failed candidate or changed model.

Same two candidate sources, worker, seed, image, 6 CPUs, serial/share2 x 3.
DnCNN sees all public training pairs except the SAME two noisy-only query images.
One gpu27 <=60min. Submit only after prior jobs close and all-in window <=3GPUh.
"""
import os
from pathlib import Path
import subprocess
import sys

import neural_node_replication as r
from neural_inputs import make_denoising
from lifecycle_pilot import read,write,sha

R=Path('/research/d7/spc/yzyang4/scheduling-neural-full-input-20261008-v1')
SOURCE=Path('/research/d7/spc/yzyang4/mle-bench-data/denoising-dirty-documents/prepared/public')


def fixture(root):
    result=make_denoising(SOURCE,root/'data-1',all_remaining=True)
    if result['public_training_pairs']!=113 or result['source_internal_train_images']!=98:
        raise ValueError('predeclared public input size')
    if sha(root/'data-1/test.csv')!=sha(r.D/'data-1/test.csv'):
        raise ValueError('query identities changed')
    for path in (root/'data-1/test').iterdir():
        if sha(path)!=sha(r.D/'data-1/test'/path.name):raise ValueError('query bytes changed')
    write(root/'full-input-fixture.json',result)
    return result


def set_scope():
    r.R=R;r.NAME='neural_full_input_trial.py';r.NODE='gpu27';r.CAP=3600
    r.JOBNAME='r14-neural-full-input';r.FIXTURE_BUILDER=fixture
    r.QUESTION='Does the simple concurrency benefit survive a larger public-input DnCNN workload, with identical source, steps and outputs across policies?'


def configure():
    set_scope()
    return r.configure()


def budget_gate():
    replication=Path('/research/d7/spc/yzyang4/scheduling-neural-gpu28-20261008-v2')
    jobs=['16987','16989','16992','16994','16996','16997','16999',read(replication/'launch.json')['job']]
    if len(set(jobs))!=len(jobs):raise ValueError('duplicate allocation')
    raw=subprocess.check_output(['sacct','-j',','.join(jobs),'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES'],
                                env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=20)
    rows={}
    for line in raw.splitlines():
        fields=line.split('|')
        if fields[0] in jobs:
            if fields[0] in rows:raise ValueError('duplicate accounting row')
            if fields[1] not in ('COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY'):
                raise ValueError('prior allocation not closed')
            tres=dict(x.split('=',1) for x in fields[3].split(',') if '=' in x)
            if int(tres['gres/gpu'])!=1:raise ValueError('unexpected GPU allocation')
            rows[fields[0]]=int(fields[2])
    if set(rows)!=set(jobs):raise ValueError('missing accounting')
    total=sum(rows.values())
    if total+3600>10800:raise ValueError('3GPUh window cap would be exceeded')
    write(R/'window-budget-before-submit.json',dict(prior_gpu_seconds=rows,
          prior_total_gpu_seconds=total,new_gpu_seconds_cap=3600,window_seconds_cap=10800))


if __name__=='__main__':
    set_scope()
    if len(sys.argv)>1 and sys.argv[1]=='submit':budget_gate()
    sys.exit(r.main())
