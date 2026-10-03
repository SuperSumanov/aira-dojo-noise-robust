"""Verify the common-host move did not alter the research intervention or data."""
import ast,hashlib,json
from pathlib import Path
B=Path('/research/d7/spc/yzyang4');old=B/'automatic-specification-20261003-v1';new=B/'automatic-specification-20261003-gpu1-v2'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
p,q=read(old/'plan.json'),read(new/'plan.json')
assert sha(old/'plan.json')=='2d898d1cdf9751cd505a3b11af91cf0032be8af2f81a73cc1ae1e9a125259a15'
assert sha(new/'plan.json')=='b4e3583ea7f999e80c8a15ec2fea1989ffe4dd66736cb173f94e4b46d90a08eb'
for key in ('schedule','base_commit','run_seconds','allocation_seconds','gpus','gpu_hours_cap','root_runs','comparison_runs','max_calls','max_tokens','code_seconds','paid_api','base_updates','treatment','selection','primary','gate','cost','limitations','protected_opened'):
    assert p[key]==q[key],key
assert p['files'].keys()==q['files'].keys()
changes=[]
for name in p['files']:
    assert sha(old/name)==p['files'][name] and sha(new/name)==q['files'][name]
    a,b=(old/name).read_bytes(),(new/name).read_bytes()
    if a==b:continue
    normalized=a.replace(str(old).encode(),str(new).encode())
    if name=='run.sbatch':normalized=normalized.replace(b'--nodelist=gpu28',b'--nodelist=gpu1')
    if name!='task_feedback_real_20261001.py':assert normalized==b,name
    changes.append(name)
def functions(path):
    t=ast.parse(path.read_text());return {n.name:ast.dump(n,include_attributes=False) for n in t.body if isinstance(n,ast.FunctionDef)}
a,b=functions(old/'task_feedback_real_20261001.py'),functions(new/'task_feedback_real_20261001.py')
for name in ('schedule','prompt','decode','wrapper','freeze_roots'):assert a[name]==b[name],name
assert read(old/'cancelled-pending.json')['gpu_hours']==0
receipt=dict(status='PASS',old_plan_sha256=sha(old/'plan.json'),new_plan_sha256=sha(new/'plan.json'),files_checked=len(p['files']),changed_paths=changes,common_treatment_functions_unchanged=True,old_allocation_gpu_hours=0,scope='Whole allocation node gpu28 to gpu1 and one common task-image CUDA warmup within the same allocation budget; no semantic/task/prompt/seed/control changes. Host kernel/driver may differ and must be recorded; no comparison against historical effects.')
with (new/'migration-check.json').open('x') as f:json.dump(receipt,f,sort_keys=True,indent=2)
print(json.dumps(receipt))
