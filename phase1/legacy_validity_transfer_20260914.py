"""Four frozen CPU fits: earlier real failures to fixed recent development nodes."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
import argparse
import ast
from collections import Counter,defaultdict
import csv
import json
import math
from pathlib import Path
import statistics
import tempfile
import time
import warnings

from validity_cpu_transfer_20260914 import (BASE,TASKS,SECRET,sha,ast_key,load_rows,
    fit_predict,task_metrics,bootstrap,dump)

SOURCE=BASE/'forets-legacy-validity-20260914-_vngs4p9'
SOURCE_SHA='c4f060ddd0cb1440800320d1c351586b1b7a73680b50b1d21c504c01e70d60c8'
AST_TYPES=('Import','ImportFrom','Call','FunctionDef','ClassDef','For','While','If','Try',
    'With','Assign','Subscript','Attribute','ListComp','DictComp','Lambda','Return','Raise',
    'ExceptHandler','Constant','Name','Compare','BinOp','BoolOp')
FEATURE_NAMES=('log_chars','log_lines','syntax_invalid','max_ast_depth')+tuple('log_'+n for n in AST_TYPES)

def features(code):
    code=code[:30000]; count=Counter(); invalid=0; depth=0
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',SyntaxWarning); tree=ast.parse(code)
        stack=[(tree,0)]
        while stack:
            node,level=stack.pop();count[type(node).__name__]+=1;depth=max(depth,level)
            stack.extend((child,level+1) for child in ast.iter_child_nodes(node))
    except SyntaxError: invalid=1
    return [math.log1p(len(code)),math.log1p(code.count('\n')+1),invalid,depth]+[math.log1p(count[n]) for n in AST_TYPES]

def purge(train,test):
    asts={r['ast_key'] for r in test}; exact={r['code_sha256'] for r in test}
    prefixes={sha(r['code'][:30000].encode()) for r in test}
    if {r['run'] for r in train}&{r['run'] for r in test}: raise ValueError('physical run overlap')
    kept=[r for r in train if r['ast_key'] not in asts and r['code_sha256'] not in exact and sha(r['code'][:30000].encode()) not in prefixes]
    return kept,len(train)-len(kept)

def run_weights(rows):
    counts=Counter(r['run'] for r in rows); w=[1/counts[r['run']] for r in rows]
    factor=len(rows)/sum(w)
    return [v*factor for v in w]

def pair_auc(rows,column):
    pos=[r[column] for r in rows if r['label']==1];neg=[r[column] for r in rows if r['label']==0]
    if not pos or not neg:return None
    return sum(1 if a>b else .5 if a==b else 0 for a in pos for b in neg)/(len(pos)*len(neg))

def within_runs(rows):
    output=[]
    for task in TASKS:
        byrun=defaultdict(list)
        for r in rows:
            if r['task']==task: byrun[r['run']].append(r)
        values=[pair_auc(rr,'predicted_validity') for rr in byrun.values()]
        observed=[v for v in values if v is not None]
        output.append(dict(task=task,total_runs=len(values),mixed_label_runs=len(observed),single_class_runs=values.count(None),
            run_equal_auc=statistics.mean(observed) if observed else None))
    return output

def main(commit):
    import joblib,numpy as np,sklearn
    from sklearn.ensemble import HistGradientBoostingClassifier
    import resource,signal
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));signal.alarm(1200)
    if len(commit)!=40 or any(c not in '0123456789abcdef' for c in commit):raise ValueError('exact commit')
    os.umask(0o077); start_all=time.perf_counter()
    raw=(SOURCE/'inventory.json').read_bytes()
    if sha(raw)!=SOURCE_SHA:raise ValueError('old source inventory drift')
    inventory=json.loads(raw);raw=(SOURCE/'nodes.private.jsonl').read_bytes()
    if sha(raw)!=inventory['private_nodes_sha256'] or SECRET.search(raw.decode()):raise ValueError('private nodes binding/security')
    original=[json.loads(line) for line in raw.splitlines()];test,excluded,proofs=load_rows()
    if len(original)!=2296 or len(test)!=157:raise ValueError('fixed data sizes')
    root=Path(tempfile.mkdtemp(prefix='forets-legacy-transfer-20260914-',dir=BASE));results=[];all_rows=[]
    for scope in ('all_legacy','other_tasks_only'):
        selected=[r for r in original if scope=='all_legacy' or r['task'] not in TASKS]
        train,removed=purge(selected,test);counts=Counter(r['label'] for r in train)
        train_info=dict(nodes_before=len(selected),purged=removed,nodes=len(train),runs=len({r['run'] for r in train}),
            label_counts=dict(counts),tasks=dict(Counter(r['task'] for r in train)))
        for kind in ('tfidf_lr','static_hgb'):
            if len(train)<100 or min(counts.get(0,0),counts.get(1,0))<20:
                results.append(dict(scope=scope,model=kind,status='insufficient_training_data',training=train_info));continue
            if kind=='tfidf_lr':
                scores,prior,timing,model=fit_predict(train,test)
                vector,clf=model
                query=lambda:clf.predict_proba(vector.transform([r['code'][:30000] for r in test]))[:,1]
                parameters={k:clf.get_params()[k] for k in ('C','class_weight','max_iter','random_state','solver')}
            else:
                weights=np.array(run_weights(train));y=np.array([r['label'] for r in train]);prior=float(np.average(y,weights=weights))
                before=time.perf_counter();matrix=np.array([features(r['code']) for r in train])
                clf=HistGradientBoostingClassifier(max_iter=100,max_leaf_nodes=15,min_samples_leaf=20,l2_regularization=1,random_state=20260914)
                clf.fit(matrix,y,sample_weight=weights)
                fit_seconds=time.perf_counter()-before;before=time.perf_counter()
                query=lambda:clf.predict_proba(np.array([features(r['code']) for r in test]))[:,1]
                scores=query();timing=dict(fitted=True,converged=True,train=len(train),test=len(test),fit_seconds=fit_seconds,
                    query_total_seconds=time.perf_counter()-before)
                model=(FEATURE_NAMES,clf);parameters={k:clf.get_params()[k] for k in ('max_iter','max_leaf_nodes','min_samples_leaf','l2_regularization','random_state','early_stopping')}
            # Warm calls are diagnostic latency, not an online cost-saving result.
            warm=query();durations=[]
            for _ in range(5):
                before=time.perf_counter();again=query();durations.append(time.perf_counter()-before)
                if not np.array_equal(again,warm):raise ValueError('deterministic query changed')
            rows=[{k:r[k] for k in ('root','run','run_id','step','task','label','code_sha256','ast_key')}|
                dict(scope=scope,model=kind,predicted_validity=float(v),prior_validity=prior,short_code_score=-math.log1p(len(r['code']))) for r,v in zip(test,scores)]
            tasks,macro=task_metrics(rows);short,short_macro=task_metrics(rows,'short_code_score');priors,_=task_metrics(rows,'prior_validity')
            gate=timing['converged'] and all(r['auc']>=.65 and r['auc']>=b['auc'] for r,b in zip(tasks,short)) and macro>short_macro
            model_path=root/(scope+'-'+kind+'.private.joblib');joblib.dump(model,model_path)
            result=dict(scope=scope,model=kind,status='completed',training=train_info,parameters=parameters,tasks=tasks,macro_auc=macro,
                short_code_tasks=short,short_code_macro_auc=short_macro,constant_tasks=priors,within_run=within_runs(rows),interval=bootstrap(rows),
                timing=timing,warm_query_batch_median_seconds=statistics.median(durations),warm_query_batch_sample_sd_seconds=statistics.stdev(durations),
                warm_query_batch_size=len(test),fixed_development_gate_pass=bool(gate),model_sha256=sha(model_path.read_bytes()))
            results.append(result);all_rows.extend(rows)
            print(json.dumps({k:result[k] for k in ('scope','model','training','macro_auc','tasks','fixed_development_gate_pass')}),flush=True)
    with (root/'predictions.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(all_rows[0]));writer.writeheader();writer.writerows(all_rows)
    summary=dict(role='legacy_corpus_to_recent_development_validity_not_e2e',worker_commit=commit,script_sha256=sha(Path(__file__).read_bytes()),
        inventory_path=str(SOURCE/'inventory.json'),inventory_sha256=SOURCE_SHA,target_source_proofs=proofs,target_exclusions=excluded,
        target_nodes=len(test),target_runs=len({r['run'] for r in test}),results=results,sklearn_version=sklearn.__version__,
        elapsed_seconds=time.perf_counter()-start_all,predictions_sha256=sha((root/'predictions.csv').read_bytes()),api_calls=0,gpu_jobs=0,
        limits='Four fixed models on reused development outcomes, no untouched confirmation, no search utility claim. Source missing all-failed unanchored runs and differs in environment. Fixed-gate selection among four is exploratory. No model deployment or EScope scoring.')
    digest=dump(root/'summary.json',summary);print(json.dumps(dict(root=str(root),summary_sha256=digest,elapsed_seconds=summary['elapsed_seconds'])),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--commit',required=True);main(parser.parse_args().commit)
