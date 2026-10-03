"""One-shot launch of the eight-GPU-hour matrix accepted after its budget request."""
import hashlib,json,os,sys
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/automatic-specification-20261003-v1')
PLAN='2d898d1cdf9751cd505a3b11af91cf0032be8af2f81a73cc1ae1e9a125259a15'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
os.umask(0o077)
assert sha(R/'plan.json')==PLAN
assert not any((R/n).exists() for n in ('launch.json','submit-intent.json','claim.json'))
for receipt,source in [('transport-loop-cpu.json','automatic_specification_cpu_20261003.py'),('readout-freeze.json','automatic_specification_readout_20261003.py'),('verifier-freeze.json','automatic_specification_verify_20261003.py')]:
    rr=read(R/receipt);assert rr['plan_sha256']==PLAN and rr['script_sha256']==sha(R.parent/source)
assert read(R/'transport-loop-cpu.json')['status']=='PASS'
approval=dict(approved=True,gpu_hours_cap=8,plan_sha256=PLAN,observed_utc='2026-10-03T04:09:56Z',scope='2 fresh roots then at most 12 comparisons; four RTX3090 on gpu28 for at most two hours; no paid API or base updates',basis='User replied 好的根据这个新的方向进行新的实验吧，三个小时之后给我有价值的结果 after the immediately preceding response explicitly stated this eight-GPU-hour matrix was awaiting approval.')
with (R/'budget-approval.json').open('x') as f:json.dump(approval,f,sort_keys=True,ensure_ascii=False,indent=2)
sys.path.insert(0,str(R))
import task_feedback_real_20261001 as experiment
experiment.submit()
