"""Fixed old-development code-only validity learning; no GPU/API or new cohort."""
import os
for _name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_name]='1'
import ast
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import tempfile
import time
import warnings

BASE=Path('/research/d7/spc/yzyang4')
SUMMARY=BASE/'forets-wallclock-20260912-5_czzimk/closed-error-families.json'
SUMMARY_SHA='fbea5f58486ea518255e6227f5d26014a5e5b0d138c78ce335b66086e3c1ef2b'
TASKS=('leaf-classification','spaceship-titanic')
SECRET=re.compile(r'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def encode(value):return (json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode()
def dump(path,value):
    raw=encode(value)
    with path.open('xb') as f:f.write(raw)
    return sha(raw)
def ast_key(code):
    try:return 'ast:'+sha(ast.dump(ast.parse(code),include_attributes=False).encode())
    except SyntaxError:return 'syntax:'+sha(code.encode())
def validity(node):
    if node.get('step')==0 or node.get('exec_time') is None:return None
    exit_code=node.get('exit_code')
    if exit_code is None:return None
    if type(exit_code) is not int:raise ValueError('integer exit status required')
    info=node.get('metric_info')
    vals=[]
    if isinstance(info,dict) and 'valid_submission' in info:vals.append(info['valid_submission'])
    if 'metric_info/valid_submission' in node:vals.append(node['metric_info/valid_submission'])
    if any(v not in (None,False,True,0,1) for v in vals) or (vals and any(v!=vals[0] for v in vals)):
        raise ValueError('conflicting validity schema')
    value=vals[0] if vals else None
    if exit_code!=0:return 0
    if value is None:return None
    return int(value==1)
def load_rows():
    raw=SUMMARY.read_bytes()
    if sha(raw)!=SUMMARY_SHA:raise ValueError('fixed development index drift')
    summary=json.loads(raw);metadata={(r['root'],r['run_id']):r for r in summary['rows']}
    rows=[];excluded=Counter();proofs=[];seen=set()
    for p in summary['proof']:
        root=BASE/p['root'];path=root/'runs'/p['run_id']/'checkpoint/journal.jsonl'
        if not root.resolve().is_relative_to(BASE) or path.is_symlink():raise ValueError('source path')
        b=path.read_bytes()
        if sha(b)!=p['journal_sha256'] or SECRET.search(b.decode()):raise ValueError('journal drift or credential shape')
        for line in b.splitlines():
            node=json.loads(line);label=validity(node)
            if label is None:excluded['not_observed_validity']+=1;continue
            code=node.get('code')
            if not isinstance(code,str) or not code.strip():excluded['no_code']+=1;continue
            key=(p['root'],p['run_id'],node['step'])
            if key in seen:raise ValueError('duplicate node identity')
            seen.add(key);task=metadata[key[:2]]['task']
            if task not in TASKS:raise ValueError('old task scope')
            rows.append(dict(root=p['root'],run=p['root']+'/'+p['run_id'],run_id=p['run_id'],step=node['step'],
                task=task,code=code,label=label,ast_key=ast_key(code),code_sha256=sha(code.encode())))
        if sha(path.read_bytes())!=p['journal_sha256']:raise ValueError('journal changed')
        artifact=json.loads((root/'artifact.json').read_bytes())
        proofs.append(dict(root=p['root'],run_id=p['run_id'],journal_sha256=p['journal_sha256'],source_tree=artifact['source_tree']))
    return rows,dict(excluded),proofs
def folds(rows,mode):
    if mode=='protocol':
        roots=sorted({r['root'] for r in rows})
        if len(roots)!=4:raise ValueError('exact four historical roots')
        assignment={r['run']:roots.index(r['root']) for r in rows}
    elif mode=='run':
        assignment={}
        for task in TASKS:
            runs=sorted({r['run'] for r in rows if r['task']==task},key=lambda x:sha(x.encode()))
            assignment.update({run:i%4 for i,run in enumerate(runs)})
    else:raise ValueError('fixed split mode')
    for fold in range(4):
        test=[r for r in rows if assignment[r['run']]==fold]
        keys={r['ast_key'] for r in test}
        before=[r for r in rows if assignment[r['run']]!=fold]
        train=[r for r in before if r['ast_key'] not in keys]
        if {r['run'] for r in train}&{r['run'] for r in test}:raise ValueError('run overlap')
        if {r['ast_key'] for r in train}&keys:raise ValueError('exact AST overlap')
        yield fold,train,test,len(before)-len(train)
def fit_predict(train,test):
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.exceptions import ConvergenceWarning
    if not train or not test:raise ValueError('empty fold')
    counts=Counter(r['run'] for r in train)
    weights=np.array([1/counts[r['run']] for r in train]);weights*=len(train)/weights.sum()
    y=np.array([r['label'] for r in train]);prior=float(np.average(y,weights=weights))
    start=time.perf_counter();vectorizer=None;model=None;converged=True
    if len(set(y))==2:
        vectorizer=TfidfVectorizer(analyzer='char',ngram_range=(3,5),min_df=2,max_features=20000)
        matrix=vectorizer.fit_transform([r['code'][:30000] for r in train])
        model=LogisticRegression(C=1.,class_weight='balanced',max_iter=1000,random_state=20260914)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always',ConvergenceWarning);model.fit(matrix,y,sample_weight=weights)
        converged=not any(issubclass(w.category,ConvergenceWarning) for w in caught)
    fit_seconds=time.perf_counter()-start;start=time.perf_counter()
    predictions=model.predict_proba(vectorizer.transform([r['code'][:30000] for r in test]))[:,1] if model else np.full(len(test),prior)
    query_seconds=time.perf_counter()-start
    return predictions,prior,dict(fitted=model is not None,converged=converged,train=len(train),test=len(test),
        fit_seconds=fit_seconds,query_total_seconds=query_seconds,query_seconds_per_code=query_seconds/len(test)),(vectorizer,model)
def task_metrics(rows,field='predicted_validity'):
    from sklearn.metrics import roc_auc_score
    out=[]
    for task in TASKS:
        subset=[r for r in rows if r['task']==task];labels=[r['label'] for r in subset]
        out.append(dict(task=task,n=len(subset),valid=sum(labels),invalid=len(labels)-sum(labels),runs=len({r['run'] for r in subset}),
            auc=float(roc_auc_score(labels,[r[field] for r in subset])) if len(set(labels))==2 else None,
            brier=sum((r[field]-r['label'])**2 for r in subset)/len(subset) if subset and field!='short_code_score' else None))
    aucs=[r['auc'] for r in out]
    return out,sum(aucs)/len(aucs) if all(v is not None for v in aucs) else None
def bootstrap(rows):
    import numpy as np
    rng=np.random.default_rng(20260914);groups={run:[r for r in rows if r['run']==run] for run in sorted({r['run'] for r in rows})}
    bytask={t:sorted(run for run,rs in groups.items() if rs[0]['task']==t) for t in TASKS};values=[]
    for _ in range(2000):
        sample=[]
        for task,runs in bytask.items():
            for index in rng.integers(len(runs),size=len(runs)):sample.extend(groups[runs[index]])
        _,value=task_metrics(sample)
        if value is not None:values.append(value)
    return dict(lower=float(np.quantile(values,.025)),upper=float(np.quantile(values,.975)),replicates=len(values),
        target='within-task pooled AUC, macro over two tasks; stratified run resampling, not task generalization')
def main(commit):
    import sklearn,joblib
    if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('exact worker commit required')
    os.umask(0o077);rows,excluded,proof=load_rows();root=Path(tempfile.mkdtemp(prefix='forets-validity-cpu-20260914-',dir=BASE))
    predictions=[];results=[]
    for mode in ('protocol','run'):
        mode_rows=[];reports=[]
        for fold,train,test,purged in folds(rows,mode):
            scores,prior,report,_=fit_predict(train,test);reports.append(dict(fold=fold,purged_exact_ast_training_rows=purged,**report))
            for row,score in zip(test,scores):
                mode_rows.append({k:row[k] for k in ('root','run','run_id','step','task','label','code_sha256','ast_key')}|dict(
                    mode=mode,fold=fold,predicted_validity=float(score),prior_validity=prior,short_code_score=-math.log1p(len(row['code']))))
        metrics,macro=task_metrics(mode_rows);interval=bootstrap(mode_rows)
        priors,prior_macro=task_metrics(mode_rows,'prior_validity');short,short_macro=task_metrics(mode_rows,'short_code_score')
        gate=all(r['fitted'] and r['converged'] for r in reports) and all(r['valid']>=10 and r['invalid']>=10 and r['runs']>=5 and r['auc'] is not None and r['auc']>=.65 for r in metrics) and interval['lower']>.50
        results.append(dict(mode=mode,folds=reports,tasks=metrics,macro_auc=macro,interval=interval,
            constant_baseline_tasks=priors,constant_baseline_macro_auc=prior_macro,
            short_code_tasks=short,short_code_macro_auc=short_macro,fixed_gate_pass=gate))
        predictions.extend(mode_rows)
    # Fit once with the same fixed parameters. Not deployed or selected by outcomes.
    _,_,full_fit,model=fit_predict(rows,rows[:1]);joblib.dump(model,root/'candidate-model.private.joblib')
    with (root/'oof-predictions.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(predictions[0]));writer.writeheader();writer.writerows(predictions)
    report=dict(role='retrospective_development_validity_predictor_not_e2e',source_summary_sha256=SUMMARY_SHA,
        script_sha256=sha(Path(__file__).read_bytes()),worker_commit=commit,sklearn_version=sklearn.__version__,total_nodes=len(rows),
        physical_runs=len({r['run'] for r in rows}),exclusions=excluded,source_proofs=proof,results=results,full_fit=full_fit,
        primary_gate_pass=results[0]['fixed_gate_pass'],api_calls=0,gpu_jobs=0,protected_cohorts_opened=False,
        limitation='Old repeatedly analyzed, heterogeneous development runs only; saved-node survivorship. Validity is not quality or leakage freedom. OOF AUC does not establish live search utility. Timings are one diagnostic fit/batch call, not warmed deployment-latency benchmarks.',
        prediction_sha256=sha((root/'oof-predictions.csv').read_bytes()),model_sha256=sha((root/'candidate-model.private.joblib').read_bytes()))
    digest=dump(root/'summary.json',report)
    print(json.dumps(dict(root=str(root),summary_sha256=digest,**{k:report[k] for k in ('total_nodes','physical_runs','exclusions','results','primary_gate_pass','full_fit')})),flush=True)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--commit',required=True);main(parser.parse_args().commit)
