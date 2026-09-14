"""No refit: independent features, folds, weights, pairwise AUC and saved models."""
import os
for n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='1'
from collections import Counter,defaultdict
import ast,json,statistics,warnings
from pathlib import Path
import numpy as np,joblib
from analyze_cheap_recent_transfer_20260914 import BASE,read,checked,sha
from verify_task_validity_20260914 import vector
ROOT=BASE/'forets-leave-task-out-20260914-3bppxdqh'
SHA='43573a5c8dcf96b72fa60a3dfbd195c1c966a5fe12746c977ef8df95c2cdaeba'

def auc(y,s,w=None):
    if len(set(y))!=2:return None
    w=np.ones(len(y)) if w is None else np.asarray(w)
    positive=[i for i,t in enumerate(y) if t==1];negative=[i for i,t in enumerate(y) if t==0]
    denominator=sum(w[i] for i in positive)*sum(w[j] for j in negative)
    return sum(w[i]*w[j]*(int(s[i]>s[j])+.5*int(s[i]==s[j])) for i in positive for j in negative)/denominator

def main():
    s=read(ROOT/'summary.json',SHA);rows=[]
    for src in s['sources']:
        p=Path(src['inventory_path']);inv=read(p,src['sha256'])
        rows.extend(map(json.loads,checked(p.parent/'nodes.private.jsonl',inv['private_nodes_sha256']).splitlines()))
    x=np.array([vector(r['code']) for r in rows]);y=np.array([r['label'] for r in rows])
    if sha(x.tobytes())!=s['feature_matrix_sha256']:raise ValueError('independent feature mismatch')
    keys=[]
    for r in rows:
        code=r['code']
        try:
            with warnings.catch_warnings():warnings.simplefilter('ignore',SyntaxWarning);tree=ast.parse(code)
            normalized=sha(ast.dump(tree,include_attributes=False).encode())
        except SyntaxError:normalized='invalid:'+sha(code.encode())
        keys.append((sha(code.encode()),normalized,sha(code[:30000].encode())))
    pred={r['index']:r for r in s['predictions']}
    if len(pred)!=2482 or len(s['folds'])!=14:raise ValueError('complete source matrix')
    maximum=0.;evaluated=0;metrics_checked=0
    for fold in s['folds']:
        task=fold['task'];ti=[i for i,r in enumerate(rows) if r['task']==task]
        held=[{keys[i][j] for i in ti} for j in range(3)]
        tr=[i for i,r in enumerate(rows) if r['task']!=task and all(keys[i][j] not in held[j] for j in range(3))]
        if ti!=fold['held_indices'] or tr!=fold['train_indices']:raise ValueError('independent purge')
        counts=Counter(rows[i]['run'] for i in tr);w=np.array([1/counts[rows[i]['run']] for i in tr]);w=w*len(w)/w.sum()
        for v,k in ((x[tr],'train_feature_sha256'),(y[tr],'train_labels_sha256'),(w,'train_weights_sha256')):
            if sha(v.tobytes())!=fold[k]:raise ValueError('train hashes')
        predictions={'short_code':[-len(rows[i]['code'][:30000]) for i in ti]}
        for receipt in fold['models']:
            p=ROOT/receipt['model']
            if sha(p.read_bytes())!=receipt['model_sha256']:raise ValueError('model hash')
            artifact=joblib.load(p);model=artifact['model'];condition=receipt['condition'];cols=receipt['feature_columns']
            if (artifact['task'],artifact['condition'])!=(task,condition) or model.get_params()!=s['parameters']:raise ValueError('model binding/parameters')
            predictions[condition]=model.predict_proba(x[ti,:cols])[:,1].tolist();evaluated+=1
        runs=defaultdict(list)
        for pos,i in enumerate(ti):
            if pred[i]['run']!=rows[i]['run'] or pred[i]['task']!=task or pred[i]['label']!=int(y[i]) or pred[i]['code_sha256']!=keys[i][0]:raise ValueError('prediction identity')
            runs[rows[i]['run']].append(pos)
            for name,values in predictions.items():maximum=max(maximum,abs(values[pos]-pred[i]['scores'][name]))
        target_y=y[ti].tolist();target_w=[1/len(runs[rows[i]['run']]) for i in ti]
        for name,values in predictions.items():
            expected=fold['metrics'][name]
            within={run:auc([target_y[j] for j in jj],[values[j] for j in jj]) for run,jj in runs.items()}
            defined=[v for v in within.values() if v is not None]
            actual={'node_auc':auc(target_y,values),'run_weighted_task_auc':auc(target_y,values,target_w),
                'within_run_mean_auc':statistics.mean(defined) if defined else None}
            if len(defined)!=expected['defined_runs'] or len(within)!=expected['total_runs']:raise ValueError('undefined denominator')
            for field,value in actual.items():
                target=expected[field]
                if (target is None)!=(value is None) or (value is not None and abs(value-target)>1e-10):raise ValueError('independent AUC')
                metrics_checked+=1
            for run in expected['per_run']:
                value=within[run['run']]
                if (value is None)!=(run['auc'] is None) or (value is not None and abs(value-run['auc'])>1e-10):raise ValueError('run AUC')
    for metric,summary in s['aggregates'].items():
        ff=[f for f in s['folds'] if f['metrics']['full'][metric] is not None]
        if len(ff)!=summary['defined_tasks']:raise ValueError('macro denominator')
        for c,value in summary['macro'].items():
            if abs(sum(f['metrics'][c][metric] for f in ff)/len(ff)-value)>1e-12:raise ValueError('macro')
        for c,stats in summary['full_vs_baseline'].items():
            differences=[f['metrics']['full'][metric]-f['metrics'][c][metric] for f in ff]
            if stats!=dict(wins=sum(d>0 for d in differences),losses=sum(d<0 for d in differences),ties=sum(d==0 for d in differences)):raise ValueError('task signs')
    if maximum!=0 or evaluated!=28:raise ValueError('prediction delivery')
    if sha((BASE/'forets-task-validity-20260914-n8q3h72y/code_only.private.joblib').read_bytes())!=s['full_deployed_model_sha256']:raise ValueError('deployed model changed')
    output=dict(status='independent_features_fold_purge_weights_saved_predictions_and_pairwise_auc_verified',summary_sha256=SHA,
        held_nodes=len(pred),folds=len(s['folds']),saved_models_verified=evaluated,metric_cells_checked=metrics_checked,
        prediction_max_abs_difference=maximum,models_refit=0,deployed_model_unchanged=True,script_sha256=sha(Path(__file__).read_bytes()),
        primary_aggregates=s['aggregates']['within_run_mean_auc'])
    raw=(json.dumps(output,sort_keys=True)+'\n').encode()
    with (ROOT/'independent.json').open('xb') as f:f.write(raw)
    print(json.dumps(dict(sha256=sha(raw),**output)))
if __name__=='__main__':main()
