"""Read-only comparison against sealed18468; no labels, scores or model calls."""
import ast
import hashlib
import json
from pathlib import Path

OLD=Path('/research/d7/spc/yzyang4/scheduling-pooling-20261015-v1')
NEW=OLD.with_name('scheduling-pooling-20261015-v2')
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def normalized(p):return json.loads(p.read_text().replace(str(NEW),str(OLD)))

assert sha(OLD/'plan.json')=='dfd73da4f1661ce1b74076e44c0e6064d93e39621e7cd717da0eaa73af340515'
old,new=read(OLD/'plan.json'),read(NEW/'plan.json')
allowed={'source_commit','approval','files','independent_predecessor'}
assert set(new)-set(old)=={'independent_predecessor'}
assert set(old)-set(new)==set()
assert {k:v for k,v in old.items() if k not in allowed}=={k:v for k,v in normalized(NEW/'plan.json').items() if k not in allowed}
assert old['schedule']==new['schedule'] and len(new['schedule'])==32
assert (OLD/'image_scorer.py').read_text()==(NEW/'image_scorer.py').read_text().replace(str(NEW),str(OLD))
for i in range(32):
    a,b=read(OLD/f'configs/{i}.json'),normalized(NEW/f'configs/{i}.json')
    # Scorer bytes change only because its absolute batch root changes.
    assert a['task']['search_only_dev_scorer_sha256']==sha(OLD/'image_scorer.py')
    assert b['task']['search_only_dev_scorer_sha256']==sha(NEW/'image_scorer.py')
    b['task']['search_only_dev_scorer_sha256']=a['task']['search_only_dev_scorer_sha256']
    assert a==b
a,b=(read(p/'input-matrix/summary.safe.json') for p in (OLD,NEW))
assert a['rows']==b['rows'] and a['paired_groups']==b['paired_groups']
assert a['exact_input_gate'] and b['exact_input_gate']
functions=[]
for p in (OLD,NEW):
    tree=ast.parse((p/'pooling_trial_20261015.py').read_text())
    functions.append({n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,ast.FunctionDef)})
changed=sorted(k for k in functions[0] if functions[0][k]!=functions[1][k])
assert changed==['preflight','prepare','qualification'],changed
for name in ('shared_pool_20261015.py','pooling_readout_20261015.py'):
    assert sha(OLD/name)==sha(NEW/name)
out=dict(passed=True,old_job='18468',old_plan_sha256=sha(OLD/'plan.json'),new_plan_sha256=sha(NEW/'plan.json'),
    source_commit=new['source_commit'],configs_equal_ignoring_root=32,actual_cpu_inputs_equal=32,
    changed_functions=changed,production_dispatch_and_scientific_protocol_unchanged=True,
    qualification_change='Retain all four logical leases before sequential physical-device validation; add complete CPU regression.',
    gpu_or_model_calls=0)
print(json.dumps(out,sort_keys=True))
