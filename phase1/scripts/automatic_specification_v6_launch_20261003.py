"""One-shot launch after the 2026-10-03 renewed user approval; total cap8GPUh."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/automatic-specification-20261003-gpu3-v6')
OLD=R.parent/'automatic-specification-20261003-gpu3-v5'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj):
    with p.open('x') as f:json.dump(obj,f,sort_keys=True,indent=2,allow_nan=False)
os.umask(0o077)
assert read(OLD/'closed.json')['service_closed'] and sha(OLD/'readout-v1/summary.json')=='41767d4d72bc8f396c5f53632769f0c52a6943addbef17bd55265e3444cb0f40'
assert not any((R/n).exists() for n in ('launch.json','submit-intent.json','claim.json'))
plan=sha(R/'plan.json');cpu=read(R/'transport-loop-cpu.json');freeze=read(R/'analysis-freeze.json')
assert cpu['status']=='PASS' and cpu['plan_sha256']==plan and cpu['script_sha256']==sha(R.parent/'automatic_specification_v6_cpu_20261003.py')
assert freeze['plan_sha256']==plan and freeze['script_sha256']==sha(R.parent/'automatic_specification_v6_analysis_20261003.py')
for name,h in freeze['files'].items():assert sha(R/'analysis_templates'/f'{name}.py')==h
jobs=[('15336',4),('15344',4),('15351',4),('15355',2),('15357',2),('15365',4),('15389',4)]
raw=subprocess.check_output(['sacct','-X','-j',','.join(j for j,_ in jobs),'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES'],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=25)
prior=[]
for job,gpus in jobs:
    f=next(row.split('|') for row in raw.splitlines() if row.split('|')[0]==job)
    assert f[1].startswith(('FAILED','CANCELLED','COMPLETED')) and (int(f[2])==0 if job=='15336' else 'gres/gpu='+str(gpus) in f[3])
    prior.append(dict(job=job,state=f[1],elapsed_seconds=int(f[2]),gpus=gpus,gpu_hours=int(f[2])*gpus/3600))
cost=sum(r['gpu_hours'] for r in prior);maximum=cost+read(R/'plan.json')['allocation_seconds']*4/3600
assert maximum<=8;write(R/'prior-accounting.json',dict(jobs=prior,gpu_hours=cost,combined_max_gpu_hours=maximum))
write(R/'budget-approval.json',dict(approved=True,plan_sha256=plan,gpu_hours_cap=8,observed_utc='2026-10-03T05:37:40Z',
    basis='User explicitly approves all proposed ideas and asks for a complete approximately four-hour experimental work window, including reasonable decisions during the complete working window. The single bounded phase-clarity follow-up was previewed before implementation; all previous costs remain within the same cap.',
    scope='Two new first-valid roots, then at most twelve unchanged comparisons;80min fourRTX3090. Previous cohorts remain closed, no replacement or pooling; cumulative all seven previous jobs plus new allocation<=8GPUh. Exactly one stage-clarity follow-up, not an unlimited prompt sweep; no paid API or base-model training.'))
sys.path.insert(0,str(R));import task_feedback_real_20261001 as experiment
print(json.dumps(dict(status='PRE_SUBMIT_COST_GATE',prior_gpu_hours=cost,combined_max_gpu_hours=maximum)),flush=True)
experiment.submit()
