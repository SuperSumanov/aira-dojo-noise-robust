"""Compare new guard-only batch to sealed18510; no outcome/model access."""
import ast
import hashlib
import json
from pathlib import Path

OLD=Path('/research/d7/spc/yzyang4/scheduling-pooling-20261015-v2')
NEW=OLD.with_name('scheduling-pooling-20261016-v1')
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(OLD/'plan.json')=='c31091ff71f19a15ce6cdb12583f1d7a16cbc5f53a96b97d26b03782003bce64'
old,new=read(OLD/'plan.json'),read(NEW/'plan.json')
allowed={'source_commit','approval','files','independent_predecessor'}
assert set(old)==set(new)
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
changed=sorted(k for k in functions[0] if functions[0][k]!=functions[1][k])
assert changed==['install_hooks','preflight','prepare'],changed
# Prove the only install-function change is the first protection statement.
hooks=[next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='install_hooks') for t in trees]
assert ast.dump(hooks[1].body[0])==ast.dump(ast.parse('pool.locked=protect(pool.locked)').body[0])
hooks[1].body.pop(0)
assert ast.dump(hooks[0])==ast.dump(hooks[1])
for name in ('shared_pool_20261015.py','pooling_readout_20261015.py','deferred_alarm_transaction_20261012.py'):
    assert sha(OLD/name)==sha(NEW/name)
gate=read(NEW/'production-guard.safe.json')
assert gate['passed'] and len(gate['cases'])==10 and all(x['passed'] and not x['manual_guard'] for x in gate['cases'])
assert gate['production_source_sha256']==sha(NEW/'pooling_trial_20261015.py')
print(json.dumps(dict(passed=True,predecessor='18510',source_commit=new['source_commit'],
    plan_sha256=sha(NEW/'plan.json'),configs_equal=32,actual_cpu_inputs_equal=32,
    production_guard_cases=10,changed_functions=changed,dispatch_and_quality_gates_unchanged=True,
    old_batch_unchanged=True,gpu_calls=0,model_calls=0),sort_keys=True))
