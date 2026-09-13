"""Same completed legacy data, same HGB; task identity is the sole new feature."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import argparse
from collections import Counter
import csv,json,math
from pathlib import Path
import tempfile,time

from validity_cpu_transfer_20260914 import BASE,TASKS,SECRET,sha,load_rows,task_metrics,bootstrap,dump
from legacy_validity_transfer_20260914 import features,FEATURE_NAMES,purge,run_weights,within_runs

SOURCES=(
    (BASE/'forets-legacy-validity-20260914-_vngs4p9','c4f060ddd0cb1440800320d1c351586b1b7a73680b50b1d21c504c01e70d60c8'),
    (BASE/'forets-early-space-validity-20260914-_kilp7zj','044fc20f5e17964de9ed414c562906562f473bcc3ba7e9e41e6e2af8876f9fe3'))

def task_features(task,categories):
    if len(categories)!=len(set(categories)):raise ValueError('duplicate category')
    return [int(task==name) for name in categories]

def main(commit):
    import resource,signal,joblib,numpy as np,sklearn
    from sklearn.ensemble import HistGradientBoostingClassifier
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));signal.alarm(600);os.umask(0o077)
    if len(commit)!=40 or any(c not in '0123456789abcdef' for c in commit):raise ValueError('commit')
    before=time.perf_counter();original=[];source_proofs=[]
    for source,digest in SOURCES:
        raw=(source/'inventory.json').read_bytes()
        if sha(raw)!=digest:raise ValueError('inventory drift')
        inventory=json.loads(raw);raw=(source/'nodes.private.jsonl').read_bytes()
        if sha(raw)!=inventory['private_nodes_sha256'] or SECRET.search(raw.decode()):raise ValueError('source binding/security')
        original.extend(json.loads(line) for line in raw.splitlines());source_proofs.append(dict(inventory_path=str(source/'inventory.json'),sha256=digest))
    if len({(r['run'],r['step']) for r in original})!=len(original):raise ValueError('source identity duplicate')
    target,excluded,proofs=load_rows();train,removed=purge(original,target)
    if len(target)!=157:raise ValueError('fixed target')
    categories=sorted({r['task'] for r in train});weights=run_weights(train);y=[r['label'] for r in train]
    train_matrix=np.array([features(r['code']) for r in train]);target_matrix=np.array([features(r['code']) for r in target])
    train_identity=np.array([task_features(r['task'],categories) for r in train]);target_identity=np.array([task_features(r['task'],categories) for r in target])
    root=Path(tempfile.mkdtemp(prefix='forets-task-validity-20260914-',dir=BASE));all_rows=[];results=[]
    for condition in ('code_only','code_plus_task'):
        x=train_matrix if condition=='code_only' else np.column_stack((train_matrix,train_identity))
        xt=target_matrix if condition=='code_only' else np.column_stack((target_matrix,target_identity))
        model=HistGradientBoostingClassifier(max_iter=100,max_leaf_nodes=15,min_samples_leaf=20,l2_regularization=1,random_state=20260914)
        start=time.perf_counter();model.fit(x,y,sample_weight=weights);fit_seconds=time.perf_counter()-start
        scores=model.predict_proba(xt)[:,1]
        rows=[{k:r[k] for k in ('root','run','run_id','step','task','label','code_sha256','ast_key')}|dict(condition=condition,
            predicted_validity=float(score),short_code_score=-math.log1p(len(r['code']))) for r,score in zip(target,scores)]
        tasks,macro=task_metrics(rows);short,short_macro=task_metrics(rows,'short_code_score')
        gate=all(r['auc']>=.65 and r['auc']>=b['auc'] for r,b in zip(tasks,short)) and macro>short_macro
        model_path=root/(condition+'.private.joblib');joblib.dump(dict(model=model,features=FEATURE_NAMES,categories=categories,condition=condition),model_path)
        result=dict(condition=condition,tasks=tasks,macro_auc=macro,short_code_tasks=short,short_code_macro_auc=short_macro,
            interval=bootstrap(rows),within_run=within_runs(rows),fit_seconds=fit_seconds,feature_dimensions=x.shape[1],
            parameters=model.get_params(),fixed_development_gate_pass=bool(gate),model_sha256=sha(model_path.read_bytes()))
        results.append(result);all_rows.extend(rows)
    with (root/'predictions.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(all_rows[0]));writer.writeheader();writer.writerows(all_rows)
    report=dict(role='same_legacy_data_task_identity_feature_development',worker_commit=commit,script_sha256=sha(Path(__file__).read_bytes()),
        sources=source_proofs,target_source_proofs=proofs,target_exclusions=excluded,train_nodes=len(train),train_runs=len({r['run'] for r in train}),
        train_label_counts=dict(Counter(y)),training_tasks=dict(Counter(r['task'] for r in train)),purged=removed,categories=categories,
        target_nodes=len(target),results=results,sklearn_version=sklearn.__version__,predictions_sha256=sha((root/'predictions.csv').read_bytes()),
        elapsed_seconds=time.perf_counter()-before,api_calls=0,gpu_jobs=0,limitations='Reused development targets after earlier transfer failures; no untouched confirmation, no search utility, no new EScope scoring or original-gate revision.')
    digest=dump(root/'summary.json',report);print(json.dumps(dict(root=str(root),summary_sha256=digest,**report)),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--commit',required=True);main(parser.parse_args().commit)
