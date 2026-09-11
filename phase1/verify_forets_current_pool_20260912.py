"""Numerical regrade after the complete eight-slot development diagnostic.

Truth stays host-only. This is not a Decision-Corpus read or search evaluation.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import os

import pandas as pd
import numpy as np

from forets_current_pool_20260912 import BASE, TASKS, checked_root, plan, summarize


def boolean_values(series):
    table={'true':True,'false':False,'1':True,'0':False,'1.0':True,'0.0':False}
    values=[]
    for value in series:
        if pd.isna(value):raise ValueError('missing boolean label')
        text=str(value).lower()
        if text not in table:raise ValueError('not a boolean label')
        values.append(table[text])
    return values


def independent_accuracy(pred,truth):
    columns={'PassengerId','Transported'}
    if not columns<=set(pred.columns) or not columns<=set(truth.columns):raise ValueError('column mismatch')
    if (pred.PassengerId.duplicated().any() or truth.PassengerId.duplicated().any()
        or pred.PassengerId.isna().any() or truth.PassengerId.isna().any()
        or set(pred.PassengerId)!=set(truth.PassengerId) or len(truth)==0):
        raise ValueError('row ID mismatch')
    p=boolean_values(pred.set_index('PassengerId').sort_index().Transported)
    y=boolean_values(truth.set_index('PassengerId').sort_index().Transported)
    return sum(a==b for a,b in zip(p,y))/len(y)


def independent_leaf_loss(pred,truth):
    # Inspected original Leaf validator (rtol=1e-5, atol=1e-6) and installed
    # sklearn 1.6.1: clip at float64 epsilon, but do NOT renormalize rows.
    if 'id' not in pred or set(pred.columns)!=set(truth.columns):raise ValueError('column mismatch')
    if (pred.id.duplicated().any() or truth.id.duplicated().any() or pred.id.isna().any()
        or truth.id.isna().any() or set(pred.id)!=set(truth.id) or len(truth)==0):
        raise ValueError('row ID mismatch')
    cols=sorted(set(truth.columns)-{'id'})
    p=pred.set_index('id').sort_index()[cols].to_numpy(dtype=float)
    y=truth.set_index('id').sort_index()[cols].to_numpy(dtype=float)
    if not np.isfinite(p).all() or not ((p>=0)&(p<=1)).all():raise ValueError('invalid probabilities')
    if not np.allclose(p.sum(axis=1),1,rtol=1e-5,atol=1e-6):raise ValueError('probability row sums')
    if not ((y==0)|(y==1)).all() or not (y.sum(axis=1)==1).all():raise ValueError('answers not one-hot')
    p=np.clip(p,np.finfo(float).eps,1-np.finfo(float).eps)
    return float(-np.mean(np.sum(y*np.log(p),axis=1)))


def verify(root):
    os.environ['SLURM_CONF']='/opt1/slurm/gpu-slurm.conf'
    root=checked_root(root);p=plan(root)
    launch=json.loads((root/'launch.json').read_text());public=json.loads((root/'summary.json').read_text())
    text=subprocess.check_output(['sacct','-X','-j',launch['job'],'-nP','--format=JobIDRaw,State'],text=True,timeout=25)
    if text.strip()!=launch['job']+'|COMPLETED':raise ValueError('not terminal completed')
    from mlebench.registry import registry
    registry=registry.set_data_dir(BASE/'mle-bench-data')
    truth={task:pd.read_csv(registry.get_competition(task).answers) for task in TASKS}
    rows=[];numeric=[];uuids=set()
    for index,item in enumerate(p['programs']):
        row=json.loads((root/f'result-{index}.json').read_text())
        if (row['index']!=index or row['job']!=launch['job'] or row['task']!=item['task']
            or row['code_sha256']!=item['code_sha256']):raise ValueError('result binding')
        binding=json.loads((root/f'identity-{index}.native-binding.json').read_text())
        if binding['native_identity']['job']!=launch['job'] or binding['namespace']['exact_device_namespace'] is not True:
            raise ValueError('device binding')
        uuids.add(binding['native_identity']['selected_uuid'])
        value=None
        if row['valid']:
            submission=root/f'work-{index}/submission.csv'
            if submission.is_symlink() or hashlib.sha256(submission.read_bytes()).hexdigest()!=row['submission_sha256']:
                raise ValueError('submission changed')
            function=independent_leaf_loss if item['task']==TASKS[0] else independent_accuracy
            value=function(pd.read_csv(submission),truth[item['task']])
            official=json.loads((root/f'grade-{index}/grading_report.json').read_text())
            if (not math.isfinite(value) or round(value,5)!=row['score'] or official['score']!=row['score']
                or official['valid_submission'] is not True or official['is_lower_better']!=(item['task']==TASKS[0])):
                raise ValueError('independent numerical mismatch')
        numeric.append(dict(index=index,task=item['task'],status=row['status'],official_score=row['score'],
                            independent_score=value))
        rows.append(row)
    if len(uuids)!=1:raise ValueError('not same sequential physical GPU')
    rebuilt=summarize(rows,p['programs'])
    if rebuilt['tasks']!=public['tasks']:raise ValueError('summary reconstruction mismatch')
    receipt=dict(job=launch['job'],verification='passed',independent_numerical_regrade=True,
        same_native_gpu=True,rows=numeric,tasks=rebuilt['tasks'],protected_cohort_read=False,
        no_e2e_or_generality_claim=True,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with (root/'independent-verification.json').open('x') as stream:json.dump(receipt,stream,indent=2,allow_nan=False)
    print(json.dumps(receipt))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);args=parser.parse_args();verify(args.root)
