"""Complete-matrix readout + independent numeric regrade, no extra executions."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys

TASKS=('leaf-classification','spaceship-titanic')
MODELS=('qwen/qwen3-coder-flash','qwen/qwen3-coder-plus')
MATRIX=((0,16,0),(0,16,1),(1,16,1),(1,16,0),(0,17,1),(0,17,0),(1,17,0),(1,17,1))
ALLOWED={'valid','program_error','program_timeout','missing_submission','invalid_submission'}


def summarize(rows,matrix=MATRIX):
    expected={(TASKS[t],s,MODELS[m]) for t,s,m in matrix}
    if len(rows)!=8 or {(r['task'],r['replicate'],r['model']) for r in rows}!=expected:
        raise ValueError('complete unique matrix required')
    for r in rows:
        if r['status'] not in ALLOWED or r['valid']!=(r['status']=='valid'):
            raise ValueError('infrastructure/misclassified result')
        if r['valid']:
            if type(r['score']) not in (int,float) or not math.isfinite(r['score']):raise ValueError('score missing')
        elif r['score'] is not None:raise ValueError('invalid imputation')
    groups=[];pairs=[]
    for task in TASKS:
        for model in MODELS:
            rs=[r for r in rows if (r['task'],r['model'])==(task,model)]
            values=[r['score'] for r in rs if r['valid']]
            times=[r['execution_seconds'] for r in rs]
            groups.append(dict(task=task,model=model,n=len(rs),valid=len(values),
                valid_probability=len(values)/len(rs),conditional_median_score=statistics.median(values) if values else None,
                conditional_sample_std_score=statistics.stdev(values) if len(values)>1 else None,
                median_execution_seconds=statistics.median(times),sample_std_execution_seconds=statistics.stdev(times),
                api_cost_usd=sum(r['api_cost_usd'] for r in rs)))
        for seed in sorted({s for _,s,_ in matrix}):
            a,b=[next(r for r in rows if (r['task'],r['replicate'],r['model'])==(task,seed,m)) for m in MODELS]
            comparable=a['valid'] and b['valid']
            gain=((a['score']-b['score']) if task==TASKS[0] else (b['score']-a['score'])) if comparable else None
            pairs.append(dict(task=task,replicate=seed,flash_valid=a['valid'],plus_valid=b['valid'],
                comparable=comparable,plus_oriented_score_gain=gain))
    totals=[dict(model=m,valid=sum(r['valid'] for r in rows if r['model']==m),programs=4,
                 api_cost_usd=sum(r['api_cost_usd'] for r in rows if r['model']==m)) for m in MODELS]
    return dict(groups=groups,pairs=pairs,totals=totals,
        limitation='Two requested program seeds per task; API sampling not guaranteed deterministic. Not critic/e2e or equal-dollar advantage.')


def numerical(task,pred,truth):
    import numpy as np
    idcol='id' if task==TASKS[0] else 'PassengerId'
    if task==TASKS[0]:
        if set(pred.columns)!=set(truth.columns) or idcol not in pred:raise ValueError('columns')
        columns=sorted(set(truth.columns)-{idcol})
    else:
        # Official Spaceship answers retain input features alongside the target.
        # Only PassengerId + Transported participate in accuracy.
        if not {idcol,'Transported'}<=set(pred.columns) or not {idcol,'Transported'}<=set(truth.columns):raise ValueError('columns')
        columns=['Transported']
    if (pred[idcol].duplicated().any() or truth[idcol].duplicated().any() or pred[idcol].isna().any()
        or truth[idcol].isna().any() or set(pred[idcol])!=set(truth[idcol]) or len(truth)==0):raise ValueError('ids')
    p=pred.set_index(idcol).sort_index()[columns];y=truth.set_index(idcol).sort_index()[columns]
    if task==TASKS[0]:
        p,y=p.to_numpy(dtype=float),y.to_numpy(dtype=float)
        if not np.isfinite(p).all() or not ((p>=0)&(p<=1)).all() or not np.allclose(p.sum(axis=1),1,rtol=1e-5,atol=1e-6):raise ValueError('probabilities')
        if not ((y==0)|(y==1)).all() or not (y.sum(axis=1)==1).all():raise ValueError('onehot')
        p=np.clip(p,np.finfo(float).eps,1-np.finfo(float).eps)
        return float(-np.mean(np.sum(y*np.log(p),axis=1)))
    lookup={'true':True,'false':False,'1':True,'0':False,'1.0':True,'0.0':False}
    if columns!=['Transported']:raise ValueError('prediction columns')
    a=[lookup[str(v).lower()] for v in p.Transported];b=[lookup[str(v).lower()] for v in y.Transported]
    return sum(x==z for x,z in zip(a,b))/len(a)


def verify(root):
    import pandas as pd
    os.environ['SLURM_CONF']='/opt1/slurm/gpu-slurm.conf'
    root=root.resolve(strict=True);sys.path.insert(0,str(root))
    import forets_generation_capacity_20260912 as worker
    root,prepared=worker.checked(root);_,g=worker.programs(root)
    launch=json.loads((root/'launch.json').read_text());intent=json.loads((root/'submit-intent.json').read_text())
    if intent['generation_sha256']!=hashlib.sha256((root/'generation-finished.json').read_bytes()).hexdigest():raise ValueError('generation changed')
    state=subprocess.check_output(['sacct','-X','-j',launch['job'],'-nP','--format=JobIDRaw,State,ElapsedRaw'],text=True,timeout=25).strip().split('|')
    if len(state)!=3 or state[:2]!=[launch['job'],'COMPLETED']:raise ValueError('not completed allocation')
    done=json.loads((root/'execution-finished.json').read_text())
    if not done['complete'] or done['completed']!=8 or not all((root/f'result-{i}.json').is_file() for i in range(8)):
        raise ValueError('whole matrix not closed')
    from mlebench.registry import registry
    registry=registry.set_data_dir(worker.BASE/'mle-bench-data')
    rows=[];proofs=[];uuids=set();truth={}
    for i,item in enumerate(prepared['requests']):
        row=json.loads((root/f'result-{i}.json').read_text())
        if (row['index'],row['job'],row['task'],row['original_search_seed'],row['source_tree'],row['code_sha256'])!=(
            i,launch['job'],item['task'],item['replicate'],worker.TREE,g['records'][i]['code_sha256']):raise ValueError('row binding')
        if row['status'] not in ALLOWED:raise ValueError('infrastructure failure')
        binding=json.loads((root/f'identity-{i}.native-binding.json').read_text())
        if binding['native_identity']['job']!=launch['job'] or binding['namespace']['exact_device_namespace'] is not True:raise ValueError('native GPU binding')
        uuids.add(binding['native_identity']['selected_uuid']);value=None
        if row['valid']:
            submission=root/f'work-{i}/submission.csv'
            if submission.is_symlink() or hashlib.sha256(submission.read_bytes()).hexdigest()!=row['submission_sha256']:raise ValueError('submission changed')
            task=item['task']
            if task not in truth:truth[task]=pd.read_csv(registry.get_competition(task).answers)
            value=numerical(task,pd.read_csv(submission),truth[task])
            official=json.loads((root/f'grade-{i}/grading_report.json').read_text())
            if round(value,5)!=row['score'] or official['score']!=row['score'] or official['valid_submission'] is not True:
                raise ValueError('independent numerical mismatch')
        proofs.append(dict(index=i,status=row['status'],official_score=row['score'],independent_score=value))
        rows.append(dict(row,model=item['model'],replicate=item['replicate'],api_cost_usd=g['records'][i]['cost_usd']))
    if len(uuids)!=1:raise ValueError('hardware differed within matrix')
    summary=summarize(rows,worker.MATRIX)
    if 'rank_records' in g:
        if len(g['rank_records'])!=4 or any(r['status']!='ranked' for r in g['rank_records']):raise ValueError('incomplete blind ranks')
        selection=[]
        for task in TASKS:
            rs=[r for r in rows if r['task']==task];ranks=[]
            for receipt in [r for r in g['rank_records'] if r['task']==task]:
                i=receipt['index'];raw=(root/f'rank-{i}.private.json').read_bytes()
                if hashlib.sha256(raw).hexdigest()!=receipt['ranking_sha256']:raise ValueError('rank changed')
                saved=json.loads(raw);response=(root/f'rank-response-{i}.private.json').read_bytes()
                if hashlib.sha256(response).hexdigest()!=saved['response_sha256']:raise ValueError('rank response changed')
                request=(root/f'rank-request-{i}.private.json').read_bytes()
                if hashlib.sha256(request).hexdigest()!=receipt['request_sha256']:raise ValueError('rank request changed')
                ranked=worker.remap(json.loads(json.loads(response)['choices'][0]['message']['content']),receipt['display_order'])
                if ranked!=saved['ranking'] or receipt['program_indices']!=[r['index'] for r in rs]:raise ValueError('rank identity/order')
                ranks.append(ranked)
            def stats(slots):
                valid=[rs[s]['score'] for s in slots if rs[s]['valid']]
                return dict(slots=slots,valid=len(valid),total=len(slots),valid_probability=len(valid)/len(slots),
                    conditional_mean_score=sum(valid)/len(valid) if valid else None)
            slots=sorted(range(4),key=lambda s:(sum(rank.index(s) for rank in ranks),s))[:2]
            a,b=stats(list(range(4))),stats(slots)
            flash=stats([i for i,r in enumerate(rs) if r['model']==MODELS[0]])
            selection.append(dict(task=task,uniform4=a,blind_borda_top2=b,
                prior_batch_metadata_flash=flash,
                validity_difference_vs_prior_batch_flash=b['valid_probability']-flash['valid_probability'],
                validity_probability_difference=b['valid_probability']-a['valid_probability'],
                individual_order_top2=[rank[:2] for rank in ranks],
                order_top2_invariant=set(ranks[0][:2])==set(ranks[1][:2])))
        summary['blind_selection']=selection
        summary['ranking_api_cost_usd']=sum(r['cost_usd'] for r in g['rank_records'])
        summary['selection_limitation']='Finite mixed-generator development pools, each code executed once. Not single-generator production/e2e confirmation; ranking fees are additional.'
        summary['metadata_baseline_registration']='Secondary always-Flash rule added at 05:09 UTC after execution closure but before any current outcome/ranking readout; chosen only from prior batch, not an original primary endpoint.'
    summary.update(role='paired_generator_capacity_development_diagnostic',job=launch['job'],utc=worker.now(),
        controller_commit=prepared['controller_commit'],source_tree=worker.TREE,
        prepared_sha256=hashlib.sha256((root/'prepared.json').read_bytes()).hexdigest(),
        same_native_gpu=True,independent_numerical_regrades=sum(p['independent_score'] is not None for p in proofs),
        all_program_slots_included=True,rows=proofs,billing=g['billing'],allocation_gpu_hours=int(state[2])/3600,
        verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),protected_cohort_read=False)
    with (root/'generation-capacity-summary.json').open('x') as f:json.dump(summary,f,indent=2,allow_nan=False)
    with (root/'generation-capacity-runs.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=sorted(set().union(*(r.keys() for r in rows))));writer.writeheader();writer.writerows(rows)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('billing','rows')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);args=parser.parse_args();verify(args.root)
