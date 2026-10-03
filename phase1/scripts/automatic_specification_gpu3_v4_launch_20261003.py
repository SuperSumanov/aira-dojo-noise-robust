"""One-shot launch of the eight-GPU-hour matrix accepted after its budget request."""
import hashlib,json,os,sys,subprocess
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/automatic-specification-20261003-gpu3-v4')
PLAN='a638e6be539955577950714bcf700c8104babca940e1478a41941ff0e8a098dd'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
os.umask(0o077)
assert sha(R/'plan.json')==PLAN
cancel=read(R.parent/'automatic-specification-20261003-v1/cancelled-pending.json')
assert cancel['job']=='15336' and cancel['gpu_hours']==0 and cancel['elapsed_seconds']==0
assert cancel['planned_successor']=='automatic-specification-20261003-gpu1-v2'
assert read(R.parent/'automatic-specification-20261003-gpu1-v2/closed.json')['service_closed']
assert not list((R.parent/'automatic-specification-20261003-gpu1-v2').glob('episode-*/action-*/request.private.json'))
assert read(R.parent/'automatic-specification-20261003-gpu1-v3/closed.json')['service_closed']
assert not list((R.parent/'automatic-specification-20261003-gpu1-v3').glob('episode-*/action-*/request.private.json'))
device=read(R.parent/'automatic-specification-device-probe-gpu3-20261003/result.json')
assert all(r['cuda_count']==2 and len({v['uuid'] for v in r['uuids']})==2 for r in device['records'])
raw=subprocess.check_output(['sacct','-X','-j','15336,15344,15351,15355,15357','-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES'],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=25)
prior=[]
for job,gpus in [('15336',4),('15344',4),('15351',4),('15355',2),('15357',2)]:
    f=next(row.split('|') for row in raw.splitlines() if row.split('|')[0]==job)
    assert f[1].startswith(('FAILED','CANCELLED','COMPLETED')) and (int(f[2])==0 if job=='15336' else 'gres/gpu='+str(gpus) in f[3])
    prior.append(dict(job=job,state=f[1],elapsed_seconds=int(f[2]),gpus=gpus,gpu_hours=int(f[2])*gpus/3600))
cost=sum(j['gpu_hours'] for j in prior)
assert cost+read(R/'plan.json')['allocation_seconds']*4/3600<=8
with (R/'prior-accounting.json').open('x') as f:json.dump(dict(jobs=prior,gpu_hours=cost,combined_max_gpu_hours=cost+read(R/'plan.json')['allocation_seconds']*4/3600),f,sort_keys=True,indent=2)
assert not any((R/n).exists() for n in ('launch.json','submit-intent.json','claim.json'))
for receipt,source in [('transport-loop-cpu.json','automatic_specification_gpu3_v4_cpu_20261003.py'),('readout-freeze.json','automatic_specification_gpu3_v4_readout_20261003.py'),('verifier-freeze.json','automatic_specification_gpu3_v4_verify_20261003.py')]:
    rr=read(R/receipt);assert rr['plan_sha256']==PLAN and rr['script_sha256']==sha(R.parent/source)
assert read(R/'transport-loop-cpu.json')['status']=='PASS'
approval=dict(approved=True,gpu_hours_cap=8,plan_sha256=PLAN,observed_utc='2026-10-03T04:09:56Z',scope='2 fresh roots then at most 12 comparisons; four RTX3090 on gpu3 for at most118 minutes, including predecessor cost within eight GPU hours; no paid API or base updates',basis='User replied 好的根据这个新的方向进行新的实验吧，三个小时之后给我有价值的结果 after the immediately preceding response explicitly stated this eight-GPU-hour matrix was awaiting approval.')
approval['migration']='Common node gpu3 after gpu1 native two-card mismatch reproduced independently; original task image and fixed treatments, all arms together. All five prior costs included, no budget expansion or previous candidate execution.'
with (R/'budget-approval.json').open('x') as f:json.dump(approval,f,sort_keys=True,ensure_ascii=False,indent=2)
sys.path.insert(0,str(R))
import task_feedback_real_20261001 as experiment
experiment.submit()
