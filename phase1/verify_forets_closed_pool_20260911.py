"""Independent numerical readout of the fixed six DEVELOPMENT executions.

No sklearn/dojo grading call: align IDs/classes and compute cross entropy with
NumPy directly. Task answers remain host-only, never printed or exported.
"""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import numpy as np
import pandas as pd

ROOT=Path('/research/d7/spc/yzyang4/forets-closed-pool-20260911-pDXbiZ93')
ORDER=((0,0),(1,0),(2,0),(2,1),(1,1),(0,1))

def independent_loss(pred, truth):
    if 'id' not in pred or set(pred.columns)!=set(truth.columns):raise ValueError('column mismatch')
    if pred.id.duplicated().any() or truth.id.duplicated().any() or set(pred.id)!=set(truth.id):
        raise ValueError('row ID mismatch')
    cols=sorted(set(truth.columns)-{'id'})
    p=pred.set_index('id').sort_index()[cols].to_numpy(dtype=float)
    y=truth.set_index('id').sort_index()[cols].to_numpy(dtype=float)
    if not np.isfinite(p).all() or not ((p>=0)&(p<=1)).all():raise ValueError('invalid probabilities')
    if not np.allclose(p.sum(axis=1),1,rtol=0,atol=1e-10):raise ValueError('probabilities not normalized')
    if not ((y==0)|(y==1)).all() or not (y.sum(axis=1)==1).all():raise ValueError('answers not one-hot')
    p=np.clip(p,np.finfo(float).eps,1-np.finfo(float).eps)
    p=p/p.sum(axis=1,keepdims=True)
    return float(-np.mean(np.sum(y*np.log(p),axis=1)))

def main():
    from mlebench.registry import registry
    finished=json.loads((ROOT/'finished.json').read_text())
    if finished['completed_slots']!=6:raise ValueError('incomplete diagnostic')
    public=json.loads((ROOT/'summary.json').read_text())
    plan=json.loads((ROOT/'plan.json').read_text());rows=[];uuids=set()
    comp=registry.set_data_dir(Path('/research/d7/spc/yzyang4/mle-bench-data')).get_competition('leaf-classification')
    # This is the allowed MLE-bench development task, not any Decision cohort.
    answers=pd.read_csv(comp.answers)
    for index,(slot,repeat) in enumerate(ORDER):
        row=json.loads((ROOT/f'result-{index}.json').read_text())
        assert (row['slot'],row['repeat'])==(slot,repeat) and row['job']=='13085'
        assert row['code_sha256']==plan['code_sha256'][slot]
        binding=json.loads((ROOT/f'identity-{index}.native-binding.json').read_text())
        assert binding['native_identity']['job']=='13085' and binding['namespace']['exact_device_namespace'] is True
        uuids.add(binding['native_identity']['selected_uuid'])
        rec=dict(index=index,slot=slot,repeat=repeat,status=row['status'],official_logloss=row['score'],
            independent_logloss=None,execution_seconds=row['execution_seconds'])
        if row['valid']:
            submission=ROOT/f'work-{index}/submission.csv'
            assert hashlib.sha256(submission.read_bytes()).hexdigest()==row['submission_sha256']
            value=independent_loss(pd.read_csv(submission),answers)
            official=json.loads((ROOT/f'grade-{index}/grading_report.json').read_text())
            assert official['is_lower_better'] is True and official['valid_submission'] is True
            assert round(value,5)==row['score']==official['score']
            rec['independent_logloss']=value
        else:assert row['score'] is None and row['status'] in ('program_error','program_timeout','missing_submission','invalid_submission')
        rows.append(rec)
    assert len(uuids)==1  # sequential same allocation/hardware
    scores=plan['scores'];top=sorted(range(3),key=lambda i:(-scores[i],i))[:2]
    def mean(slots):
        sub=[r for r in rows if r['slot'] in slots];valid=[r for r in sub if r['official_logloss'] is not None]
        return dict(valid_probability=len(valid)/len(sub),conditional_mean_logloss=statistics.mean(r['official_logloss'] for r in valid) if valid else None)
    arms={'top2':mean(top),'uniform3':mean([0,1,2])}
    for name,values in arms.items():
        for key,value in values.items():
            if value is None:assert public[name][key] is None
            else:assert abs(public[name][key]-value)<1e-12
    output=dict(job='13085',verification='passed',rows=rows,arms=arms,top2_slots=top,
        fixed_historical_scores=scores,same_native_gpu=True,independent_numerical_regrade=True,
        no_e2e_or_generalization_claim=True)
    with (ROOT/'independent-verification.json').open('x') as f:json.dump(output,f,indent=2,allow_nan=False)
    print(json.dumps(output))

if __name__=='__main__':main()
