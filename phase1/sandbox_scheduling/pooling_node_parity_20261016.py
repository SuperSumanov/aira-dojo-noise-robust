"""Independent structural comparison against sealed18673; no outcome reads."""
import ast
import hashlib
import json
from pathlib import Path

OLD=Path('/research/d7/spc/yzyang4/scheduling-pooling-20261016-v2')
NEW=OLD.with_name('scheduling-pooling-20261016-v3')
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(OLD/'plan.json')=='221a8fc38cffab0c0a08c80c795a38ed98f7a4eb7db5c22c8ecb9e34a948b462'
old,new=read(OLD/'plan.json'),read(NEW/'plan.json')
assert old['node']=='projgpu12' and new['node']=='gpu1'
assert set(old)==set(new)
allowed={'source_commit','approval','files','independent_predecessor','node','staging_note'}
normalized=json.loads((NEW/'plan.json').read_text().replace(str(NEW),str(OLD)))
assert {k:v for k,v in old.items() if k not in allowed}=={k:v for k,v in normalized.items() if k not in allowed}
assert (OLD/'image_scorer.py').read_text()==(NEW/'image_scorer.py').read_text().replace(str(NEW),str(OLD))
for i in range(32):
    a=read(OLD/f'configs/{i}.json')
    b=json.loads((NEW/f'configs/{i}.json').read_text().replace(str(NEW),str(OLD)))
    assert a['task']['search_only_dev_scorer_sha256']==sha(OLD/'image_scorer.py')
    assert b['task']['search_only_dev_scorer_sha256']==sha(NEW/'image_scorer.py')
    b['task']['search_only_dev_scorer_sha256']=a['task']['search_only_dev_scorer_sha256']
    assert a==b
a,b=(read(r/'input-matrix/summary.safe.json') for r in (OLD,NEW))
assert a['rows']==b['rows'] and a['paired_groups']==b['paired_groups']
assert a['exact_input_gate'] and b['exact_input_gate']
trees=[ast.parse((r/'pooling_trial_20261015.py').read_text()) for r in (OLD,NEW)]
functions=[{n.name:ast.dump(n,include_attributes=False) for n in t.body if isinstance(n,ast.FunctionDef)} for t in trees]
assert functions[0].keys()==functions[1].keys()
changed=sorted(k for k in functions[0] if functions[0][k]!=functions[1][k])
assert changed==['prepare'],changed
for name in ('shared_pool_20261015.py','pooling_readout_20261015.py','deferred_alarm_transaction_20261012.py','pooling_production_gate_20261016.py'):
    assert sha(OLD/name)==sha(NEW/name)
for name in ('image_live_2plus4_20261011.py','forets_native_cuda_identity_20260911.py','run.sbatch'):
    assert (OLD/name).read_text()==(NEW/name).read_text().replace(str(NEW),str(OLD)).replace('gpu1','projgpu12')
gate=read(NEW/'production-guard.safe.json')
assert gate['passed'] and len(gate['cases'])==10 and all(x['passed'] and not x['manual_guard'] for x in gate['cases'])
assert gate['production_source_sha256']==sha(NEW/'pooling_trial_20261015.py')
assert all(sha(OLD/n)==h for n,h in old['files'].items())
assert all(sha(NEW/n)==h for n,h in new['files'].items())
print(json.dumps(dict(passed=True,predecessor='18673',source_commit=new['source_commit'],
    plan_sha256=sha(NEW/'plan.json'),configs_equal=32,actual_cpu_inputs_equal=32,
    production_guard_cases=10,changed_functions=changed,dispatch_and_quality_gates_unchanged=True,
    common_node='gpu1',old_batch_unchanged=True,gpu_calls=0,model_calls=0),sort_keys=True))
