"""One-shot launch of the eight-GPU-hour matrix accepted after its budget request."""
import hashlib,json,os,sys
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/automatic-specification-20261003-gpu1-v2')
PLAN='b4e3583ea7f999e80c8a15ec2fea1989ffe4dd66736cb173f94e4b46d90a08eb'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
os.umask(0o077)
assert sha(R/'plan.json')==PLAN
cancel=read(R.parent/'automatic-specification-20261003-v1/cancelled-pending.json')
assert cancel['job']=='15336' and cancel['gpu_hours']==0 and cancel['elapsed_seconds']==0
assert cancel['planned_successor']==R.name
assert not any((R/n).exists() for n in ('launch.json','submit-intent.json','claim.json'))
for receipt,source in [('transport-loop-cpu.json','automatic_specification_gpu1_cpu_20261003.py'),('readout-freeze.json','automatic_specification_gpu1_readout_20261003.py'),('verifier-freeze.json','automatic_specification_gpu1_verify_20261003.py')]:
    rr=read(R/receipt);assert rr['plan_sha256']==PLAN and rr['script_sha256']==sha(R.parent/source)
assert read(R/'transport-loop-cpu.json')['status']=='PASS'
approval=dict(approved=True,gpu_hours_cap=8,plan_sha256=PLAN,observed_utc='2026-10-03T04:09:56Z',scope='2 fresh roots then at most 12 comparisons; four RTX3090 on gpu1 for at most two hours; no paid API or base updates',basis='User replied 好的根据这个新的方向进行新的实验吧，三个小时之后给我有价值的结果 after the immediately preceding response explicitly stated this eight-GPU-hour matrix was awaiting approval.')
approval['migration']='Common node gpu28 to gpu1, same four RTX3090 and task image, all arms together; pending predecessor cancelled at zero cost. Disclosed before migration, no budget expansion.'
with (R/'budget-approval.json').open('x') as f:json.dump(approval,f,sort_keys=True,ensure_ascii=False,indent=2)
sys.path.insert(0,str(R))
import task_feedback_real_20261001 as experiment
experiment.submit()
