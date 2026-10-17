"""One fixed closed48 cohort: do not rescue/reopen the failed weight recipe.

Compare actual lineage by the original arm/pool. Post-treatment parent quality
differs across arms, so conditional revision yield is not a model causal effect.
"""
import json
from pathlib import Path
import closed_adaptation_lineage_20261017 as m
from closed_parent_delta_20261017 import evaluate

ROOT=Path('/research/d7/spc/yzyang4/scheduling-metric-deployment-20261015-v2')
PLAN='e3baf5d2fa704cdd0c3fc458549aa21449fdbf3209bac87337b370e2a416e154'
SUMMARY='c68e4c4caafb3b63ad22443c5e7e2f330a0f22a3ddd47887dc06b10820e366e9'

def main():
    dst=ROOT/'adaptation-lineage-20261017.safe.json';pd=ROOT/'parent-delta-20261017.safe.json'
    assert not dst.exists() and not pd.exists()
    out=m.extract(ROOT,PLAN,SUMMARY,'readout-20261015-v1',expected=48)
    out.update(job=18412,driver_sha256=m.sha(__file__))
    with dst.open('x') as f:json.dump(out,f,indent=2,sort_keys=True,allow_nan=False)
    print(json.dumps(dict(kind='lineage',sha256=m.sha(dst),returned=len(out['candidates']),groups=out['groups'])),flush=True)
    result=evaluate(ROOT,dst.name,m.sha(dst))
    result.update(job=18412,reader_sha256=m.sha(__file__),parent_reader_sha256=m.sha(Path(__file__).with_name('closed_parent_delta_20261017.py')),
        limits=['Original48-run quality gate remains false. No rescue training, replacement checkpoint, new GPU or new score.',
                'Conditioning on observed parent is post-treatment; differences do not identify specialization or justify a router.',
                'Two fixed reverse-order repeats, different30minute budget from other lineage cohorts; keep separate.'])
    with pd.open('x') as f:json.dump(result,f,indent=2,sort_keys=True,allow_nan=False)
    print(json.dumps(dict(kind='parent',sha256=m.sha(pd),returned=len(result['rows']),unresolved=result['unresolved'])),flush=True)

if __name__=='__main__':main()
