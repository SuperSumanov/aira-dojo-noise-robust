"""One-shot launch of the eight-GPU-hour matrix accepted after its budget request."""
import hashlib,json,os,sys,subprocess
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/automatic-specification-20261003-gpu1-v3')
PLAN='b4dd6a7a59000b90ee2307b8038b1c013864ab66eef614b6eecb7c64feb0b4c5'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
os.umask(0o077)
assert sha(R/'plan.json')==PLAN
cancel=read(R.parent/'automatic-specification-20261003-v1/cancelled-pending.json')
assert cancel['job']=='15336' and cancel['gpu_hours']==0 and cancel['elapsed_seconds']==0
assert cancel['planned_successor']=='automatic-specification-20261003-gpu1-v2'
assert read(R.parent/'automatic-specification-20261003-gpu1-v2/closed.json')['service_closed']
assert not list((R.parent/'automatic-specification-20261003-gpu1-v2').glob('episode-*/action-*/request.private.json'))
raw=subprocess.check_output(['sacct','-X','-j','15336,15344','-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES'],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=25)
prior=[]
for job in ('15336','15344'):
    f=next(row.split('|') for row in raw.splitlines() if row.split('|')[0]==job)
    assert f[1].startswith(('FAILED','CANCELLED')) and (int(f[2])==0 if job=='15336' else 'gres/gpu=4' in f[3])
    prior.append(dict(job=job,state=f[1],elapsed_seconds=int(f[2]),gpus=4,gpu_hours=int(f[2])*4/3600))
cost=sum(j['gpu_hours'] for j in prior)
assert cost+read(R/'plan.json')['allocation_seconds']*4/3600<=8
with (R/'prior-accounting.json').open('x') as f:json.dump(dict(jobs=prior,gpu_hours=cost,combined_max_gpu_hours=cost+read(R/'plan.json')['allocation_seconds']*4/3600),f,sort_keys=True,indent=2)
assert not any((R/n).exists() for n in ('launch.json','submit-intent.json','claim.json'))
for receipt,source in [('transport-loop-cpu.json','automatic_specification_gpu1_v3_cpu_20261003.py'),('readout-freeze.json','automatic_specification_gpu1_v3_readout_20261003.py'),('verifier-freeze.json','automatic_specification_gpu1_v3_verify_20261003.py')]:
    rr=read(R/receipt);assert rr['plan_sha256']==PLAN and rr['script_sha256']==sha(R.parent/source)
assert read(R/'transport-loop-cpu.json')['status']=='PASS'
approval=dict(approved=True,gpu_hours_cap=8,plan_sha256=PLAN,observed_utc='2026-10-03T04:09:56Z',scope='2 fresh roots then at most 12 comparisons; four RTX3090 on gpu1 for at most119 minutes, including predecessor cost within eight GPU hours; no paid API or base updates',basis='User replied 好的根据这个新的方向进行新的实验吧，三个小时之后给我有价值的结果 after the immediately preceding response explicitly stated this eight-GPU-hour matrix was awaiting approval.')
approval['migration']='Common node gpu28 to gpu1, same four RTX3090 and task image, all arms together; pending predecessor cancelled at zero cost. Disclosed before migration, no budget expansion.'
with (R/'budget-approval.json').open('x') as f:json.dump(approval,f,sort_keys=True,ensure_ascii=False,indent=2)
sys.path.insert(0,str(R))
import task_feedback_real_20261001 as experiment
experiment.submit()
