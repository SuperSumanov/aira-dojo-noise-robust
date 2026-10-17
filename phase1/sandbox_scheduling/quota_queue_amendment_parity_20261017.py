"""No execution: prove administrative v2->v3 replacement preserved science."""
import hashlib
import json
from pathlib import Path

BASE=Path('/research/d7/spc/yzyang4')
OLD=BASE/'scheduling-generation-quota-20261017-v2'
NEW=BASE/'scheduling-generation-quota-20261017-v3'
PINS=('8d4d402365257376ba3634d21929624031f349f971c314e2aa26786c42ea147b',
      '2736fb9326f62f3c83bc0cebc4854ba629991e5b5e4bb69e708aa91e24b74e7e')


def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def normalize(x,root):
    if isinstance(x,str):return x.replace(str(root),'<ROOT>')
    if isinstance(x,list):return [normalize(v,root) for v in x]
    if isinstance(x,dict):return {normalize(k,root):normalize(v,root) for k,v in x.items()}
    return x

def changed_paths(x,y,path=''):
    if isinstance(x,dict) and isinstance(y,dict):
        return [q for k in sorted(set(x)|set(y)) for q in changed_paths(x.get(k),y.get(k),path+'/'+k)]
    if isinstance(x,list) and isinstance(y,list) and len(x)==len(y):
        return [q for i,(u,v) in enumerate(zip(x,y)) for q in changed_paths(u,v,path+'/'+str(i))]
    return [] if x==y else [path]


assert tuple(sha(r/'plan.json') for r in (OLD,NEW))==PINS
a,b=read(OLD/'plan.json'),read(NEW/'plan.json')
fields=('planned','allocation_seconds','gpu_hours_cap','node','model_files','task_image_sha256',
        'service_image_sha256','common_start_receipt_sha256','schedule','primary','single_change',
        'common_execution_change','advance','stop','rationale','limitation',
        'new_window_gpu_seconds_cap','combined_gpu_seconds_cap')
for key in fields:assert a[key]==b[key],key
assert a['planned']==32 and a['allocation_seconds']==6000 and a['gpu_hours_cap']==10
scorers=[r/'image_scorer.py' for r in (OLD,NEW)]
assert normalize(scorers[0].read_text(),OLD)==normalize(scorers[1].read_text(),NEW), 'scorer algorithm differs'
for i in range(32):
    configs=[read(r/f'configs/{i}.json') for r in (OLD,NEW)]
    for config,scorer in zip(configs,scorers):
        assert config['task']['search_only_dev_scorer_path']==str(scorer)
        assert config['task']['search_only_dev_scorer_sha256']==sha(scorer)
        config['task']['search_only_dev_scorer_sha256']='<SAME_SCORER_AFTER_ROOT_NORMALIZATION>'
    left,right=normalize(configs[0],OLD),normalize(configs[1],NEW)
    if left!=right:print(json.dumps(dict(config=i,changed_field_paths_only=changed_paths(left,right))),flush=True)
    assert left==right,f'config{i}'
source_count=0
old_sources={p.name:p for p in OLD.glob('*.py')}
new_sources={p.name:p for p in NEW.glob('*.py')}
assert set(old_sources)==set(new_sources)
source_hashes={}
for name,path in old_sources.items():
    if name=='generation_quota_trial_20261017.py':continue
    other=new_sources[name]
    assert normalize(path.read_text(),OLD)==normalize(other.read_text(),NEW),name
    source_hashes[name]=[sha(path),sha(other)]
    source_count+=1
assert source_count>20
assert sha(NEW/'generation_quota_trial_20261017.py')=='722d9e1516221a2f054607228443444f73c27e0b6dab765303514ba19d2cb6a6'
receipt=dict(passed=True,old_plan_sha256=PINS[0],new_plan_sha256=PINS[1],configs_identical_except_root_and_derived_scorer_hash=32,
             scorer_source_identical_after_root_normalization=True,scorer_sha256s=[sha(p) for p in scorers],
             matched_plan_fields=fields,unchanged_nonentry_python_files_after_root_normalization=source_count,
             source_hashes=source_hashes,
             old_workers=0,new_workers=0,no_outcomes_read=True,
             scope='Pre-start administrative expiry/root/source change only; full configs, original matrix/budget/node/quality gate and all top-level nonentry Python source identical after root normalization.',
             supersedes='v1 config checks passed but input_files contained no Python sources; its all-source scope was overstated. v2 explicitly enumerates both source directories and verifies nonentry code. No experiment or outcomes were read.')
assert not list(OLD.glob('episode-*/deadline.json')) and not list(NEW.glob('episode-*/deadline.json'))
out=Path(__file__).with_name('quota-queue-amendment-parity-v2.safe.json')
with out.open('x') as f:json.dump(receipt,f,indent=2,sort_keys=True)
print(json.dumps({k:v for k,v in receipt.items() if k!='source_hashes'},sort_keys=True))
