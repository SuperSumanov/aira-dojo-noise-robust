"""Exactly fourteen historical held-task folds, two fixed fits per fold."""
import os
for n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='1'
import importlib.util,json,signal,statistics,tempfile,time
from collections import Counter,defaultdict
from pathlib import Path
import joblib,numpy as np,sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from analyze_cheap_recent_transfer_20260914 import BASE,read,checked,sha,identity
MODEL_ROOT=BASE/'forets-task-validity-20260914-n8q3h72y'
MODEL_SHA='05379469122879c798f1d2c571eb733956a067dac314050feeb06d3e09c641d1'

def run_weights(rows):
    counts=Counter(r['run'] for r in rows);values=np.array([1/counts[r['run']] for r in rows])
    return values*len(values)/values.sum()

def fold_indices(rows,keys,task):
    ti=[i for i,r in enumerate(rows) if r['task']==task];held=[set(keys[i][j] for i in ti) for j in range(3)]
    candidates=[i for i,r in enumerate(rows) if r['task']!=task]
    tr=[i for i in candidates if not any(keys[i][j] in held[j] for j in range(3))]
    if set(rows[i]['run'] for i in tr)&set(rows[i]['run'] for i in ti):raise ValueError('run intersection')
    return tr,ti,len(candidates)-len(tr)

def metrics(rows,scores):
    y=np.array([r['label'] for r in rows]);w=run_weights(rows)
    byrun=defaultdict(list)
    for i,r in enumerate(rows):byrun[r['run']].append(i)
    perrun=[]
    for run,ii in byrun.items():
        yi=y[ii];si=np.array(scores)[ii]
        perrun.append(dict(run=run,nodes=len(ii),positive=int(yi.sum()),auc=float(roc_auc_score(yi,si)) if len(set(yi))==2 else None))
    vals=[r['auc'] for r in perrun if r['auc'] is not None]
    return dict(node_auc=float(roc_auc_score(y,scores)) if len(set(y))==2 else None,
        run_weighted_task_auc=float(roc_auc_score(y,scores,sample_weight=w)) if len(set(y))==2 else None,
        within_run_mean_auc=statistics.mean(vals) if vals else None,defined_runs=len(vals),total_runs=len(perrun),per_run=perrun)

def main(commit):
    signal.alarm(600);os.umask(0o077);start=time.perf_counter()
    if sklearn.__version__!='1.6.1' or len(commit)!=40:raise ValueError('runtime/commit')
    modelpath=MODEL_ROOT/'code_only.private.joblib'
    if sha(modelpath.read_bytes())!=MODEL_SHA:raise ValueError('deployed model drift')
    source=BASE/'forets-wallclock-20260912-km65uuej/source/src/dojo/solvers/fore_ts/cheap_ranker.py'
    inv=read(BASE/'forets-wallclock-20260912-km65uuej/source-files.json')
    if sha(source.read_bytes())!=inv['src/dojo/solvers/fore_ts/cheap_ranker.py']:raise ValueError('feature source')
    spec=importlib.util.spec_from_file_location('production_features',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    ms=read(MODEL_ROOT/'summary.json','66be27cbde084c433df25e95cd803bc7f42df3c71ad7d72af23528205d928a33')
    rows=[]
    for item in ms['sources']:
        p=Path(item['inventory_path']);v=read(p,item['sha256'])
        rows.extend(json.loads(line) for line in checked(p.parent/'nodes.private.jsonl',v['private_nodes_sha256']).splitlines())
    tasks=sorted({r['task'] for r in rows})
    if (len(rows),len({r['run'] for r in rows}),len(tasks))!=(2482,138,14):raise ValueError('source matrix')
    for run in {r['run'] for r in rows}:
        if len({r['task'] for r in rows if r['run']==run})!=1:raise ValueError('run spans tasks')
    keys=[identity(r['code']) for r in rows];x=np.array([module.features(r['code']) for r in rows]);y=np.array([r['label'] for r in rows])
    if x.shape!=(2482,28):raise ValueError('feature dimensions')
    root=Path(tempfile.mkdtemp(prefix='forets-leave-task-out-20260914-',dir=BASE));folds=[];predictions=[]
    for fold,task in enumerate(tasks):
        tr,ti,purged=fold_indices(rows,keys,task)
        if len(set(y[tr]))!=2:raise ValueError('training lacks class; no alternate fit')
        w=run_weights([rows[i] for i in tr]);target=[rows[i] for i in ti]
        scores={'short_code':[-len(r['code'][:30000]) for r in target]};receipts=[]
        for condition,cols in (('full',28),('size_only',2)):
            model=HistGradientBoostingClassifier(max_iter=100,max_leaf_nodes=15,min_samples_leaf=20,l2_regularization=1,random_state=20260914)
            if model.get_params()!=ms['results'][0]['parameters']:raise ValueError('same parameters')
            began=time.perf_counter();model.fit(x[tr,:cols],y[tr],sample_weight=w);elapsed=time.perf_counter()-began
            values=model.predict_proba(x[ti,:cols])[:,1].tolist();scores[condition]=values
            path=root/f'fold-{fold:02d}-{condition}.private.joblib';joblib.dump(dict(model=model,task=task,condition=condition),path)
            receipts.append(dict(condition=condition,model=path.name,model_sha256=sha(path.read_bytes()),feature_columns=cols,fit_seconds=elapsed))
        folds.append(dict(task=task,fold=fold,train_nodes=len(tr),train_runs=len({rows[i]['run'] for i in tr}),held_nodes=len(ti),held_runs=len({rows[i]['run'] for i in ti}),
            held_positive=int(y[ti].sum()),purged_nodes=purged,train_indices=tr,held_indices=ti,
            train_feature_sha256=sha(x[tr].tobytes()),train_labels_sha256=sha(y[tr].tobytes()),train_weights_sha256=sha(w.tobytes()),models=receipts,
            metrics={name:metrics(target,values) for name,values in scores.items()}))
        for pos,i in enumerate(ti):predictions.append(dict(index=i,task=task,run=rows[i]['run'],step=rows[i]['step'],label=int(y[i]),
            code_sha256=keys[i][0],scores={name:float(values[pos]) for name,values in scores.items()}))
    if sha(modelpath.read_bytes())!=MODEL_SHA:raise ValueError('deployed model altered')
    aggregates={}
    for metric in ('within_run_mean_auc','run_weighted_task_auc','node_auc'):
        defined=[f for f in folds if all(f['metrics'][c][metric] is not None for c in ('full','size_only','short_code'))]
        aggregates[metric]=dict(defined_tasks=len(defined),macro={c:statistics.mean(f['metrics'][c][metric] for f in defined) if defined else None for c in ('full','size_only','short_code')},
            full_vs_baseline={c:dict(wins=sum(f['metrics']['full'][metric]>f['metrics'][c][metric] for f in defined),
                losses=sum(f['metrics']['full'][metric]<f['metrics'][c][metric] for f in defined),ties=sum(f['metrics']['full'][metric]==f['metrics'][c][metric] for f in defined)) for c in ('size_only','short_code')})
    output=dict(role='posthoc_historical_leave_task_out_validity',root=str(root),worker_commit=commit,sklearn_version=sklearn.__version__,
        script_sha256=sha(Path(__file__).read_bytes()),plan_sha256=sha(Path(__file__).with_name('CHEAP_LEAVE_TASK_OUT_PLAN_20260914.md').read_bytes()),
        sources=ms['sources'],full_deployed_model_sha256=MODEL_SHA,deployed_model_unchanged=True,parameters=ms['results'][0]['parameters'],
        source_features_sha256=sha(source.read_bytes()),feature_matrix_sha256=sha(x.tobytes()),folds=folds,predictions=predictions,aggregates=aggregates,
        fit_count=28,gpu_jobs=0,api_calls=0,elapsed_seconds=time.perf_counter()-start,
        limitations='Historical selected runs and heterogeneous execution conditions. Feature family previously developed; not untouched confirmation, same-budget E2E or a new model selection gate. Undefined task/run metrics retained. No current46/47 outcomes used.')
    raw=(json.dumps(output,sort_keys=True,allow_nan=False)+'\n').encode()
    with (root/'summary.json').open('xb') as f:f.write(raw)
    print(json.dumps(dict(root=str(root),sha256=sha(raw),aggregates=aggregates,elapsed_seconds=output['elapsed_seconds'],purged_nodes=sum(f['purged_nodes'] for f in folds))))
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--commit',required=True);main(p.parse_args().commit)
