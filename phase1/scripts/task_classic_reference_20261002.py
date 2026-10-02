"""Fixed cheap task-model qualification; not an agent/repair method.

Only public train labels during fitting. Freeze all outputs before readout.
No follow-up grid, no GPU, no candidate program execution, no protected data.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path

B = Path('/research/d7/spc/yzyang4')
OLD = B/'task-feedback-real-20261001-v6'
ROOT = B/'task-classic-reference-20261002-v1'
OPP = B/'repair-opportunity-20261002-v1'
TASK = 'random-acts-of-pizza'
SEEDS = [102601, 102602, 102603]
MODEL_NAMES = ['metadata_histgbm', 'text_metadata_logistic']


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_bytes())
def save(p, obj):
    with p.open('x') as f:
        json.dump(obj, f, sort_keys=True, indent=2, allow_nan=False); f.write('\n')
def readcsv(p):
    with p.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))


def task_object():
    sys.path.insert(0, str(OLD))
    import task_feedback_real_20261001 as runtime
    runtime.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    assert sha(OLD/'plan.json') == '15751d3b52bdc42617df02006ce724635f4bf49df6e477686769fd1979d53403'
    index = next(r['index'] for r in read(OLD/'plan.json')['schedule'] if r['task'] == TASK)
    return MLEBenchTask(RunConfig.load_from_json(OLD/'configs'/f'{index}.json').task)


def allowed_numeric(name):
    return (name.endswith('_at_request') or name in ('unix_timestamp_of_request', 'unix_timestamp_of_request_utc')) and not any(s in name for s in ('retrieval','received','flair','giver'))


def numeric_columns(train, query):
    common = set.intersection(*(set(r) for r in train+query))
    # Schema inspection only: no query distributions or labels used for selection.
    return sorted(k for k in common if allowed_numeric(k) and all(isinstance(r[k], (int,float,bool)) or r[k] is None for r in train))


def text(row):
    return str(row.get('request_title') or '')+'\n'+str(row.get('request_text_edit_aware') or '')


def numeric(rows, columns):
    import numpy as np
    out = []
    for r in rows:
        vals = [float(r[k]) if isinstance(r.get(k),(int,float,bool)) and math.isfinite(float(r[k])) else float('nan') for k in columns]
        # Fixed generic text lengths, not task-outcome heuristics.
        vals += [len(str(r.get(k) or '')) for k in ('request_title','request_text_edit_aware')]
        vals += [len(str(r.get(k) or '').split()) for k in ('request_title','request_text_edit_aware')]
        out.append(vals)
    return np.asarray(out, dtype=float)


def build(name, rows, y, columns, seed):
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from scipy.sparse import csr_matrix, hstack
    imp = SimpleImputer(strategy='median', keep_empty_features=True)
    X = imp.fit_transform(numeric(rows, columns))
    obj = dict(name=name, columns=columns, imputer=imp, fit_rows=len(rows), seed=seed)
    if name == 'metadata_histgbm':
        model = HistGradientBoostingClassifier(max_iter=200,max_leaf_nodes=15,min_samples_leaf=20,learning_rate=.1,l2_regularization=1.,early_stopping=False,random_state=seed)
    elif name == 'text_metadata_logistic':
        tf = TfidfVectorizer(ngram_range=(1,2),min_df=2,max_features=20000,sublinear_tf=True,strip_accents='unicode')
        tx = tf.fit_transform([text(r) for r in rows])
        scaler = StandardScaler().fit(X)
        X = hstack([tx, csr_matrix(scaler.transform(X))]).tocsr()
        obj.update(tfidf=tf, scaler=scaler)
        model = LogisticRegression(C=1.,solver='liblinear',max_iter=300,random_state=seed)
    else: raise ValueError(name)
    model.fit(X,y); obj['model'] = model
    return obj


def predict(obj, rows):
    from scipy.sparse import csr_matrix, hstack
    X = obj['imputer'].transform(numeric(rows,obj['columns']))
    if obj['name']=='text_metadata_logistic':
        X = hstack([obj['tfidf'].transform([text(r) for r in rows]),csr_matrix(obj['scaler'].transform(X))]).tocsr()
    assert list(obj['model'].classes_) == [0,1]
    return obj['model'].predict_proba(X)[:,1]


def inspect():
    import importlib.metadata as metadata
    task = task_object(); train=read(task.public_dir/'train.json'); query=read(task.public_dir/'test.json')
    print(json.dumps(dict(train_rows=len(train),query_rows=len(query),all_train_keys=sorted(train[0]),all_query_keys=sorted(query[0]),
        selected_numeric=numeric_columns(train,query),public_dir=str(task.public_dir),
        query_has_label=any('requester_received_pizza' in r for r in query),
        versions={n:metadata.version(n) for n in ['scikit-learn','numpy','scipy']},root_exists=ROOT.exists())))


def smoke():
    from sklearn.metrics import roc_auc_score
    rows=[dict(request_id=str(i),request_title='positive help' if i%2 else 'other words',request_text_edit_aware='need support '+str(i),count_at_request=i%2,evil_at_retrieval=i%2,requester_received_pizza=bool(i%2)) for i in range(80)]
    cols=numeric_columns(rows,rows); assert cols==['count_at_request']
    y=[int(r['requester_received_pizza']) for r in rows]
    for n in MODEL_NAMES:
        m=build(n,rows[:60],y[:60],cols,1); p=predict(m,rows[60:]); assert len(p)==20 and roc_auc_score(y[60:],p)>.9
        assert len(m['imputer'].statistics_)==5
    assert not allowed_numeric('number_of_upvotes_of_request_at_retrieval')
    assert not allowed_numeric('requester_received_pizza')
    assert not allowed_numeric('requester_user_flair')
    print(json.dumps(dict(synthetic_smoke='PASS',source_sha256=sha(Path(__file__)),root_exists=ROOT.exists())))


def fit():
    os.umask(0o077); began=time.monotonic()
    import numpy as np
    import scipy
    import sklearn
    import joblib
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import roc_auc_score
    task=task_object(); public=task.public_dir
    train=read(public/'train.json'); query=read(public/'test.json')
    assert not any('requester_received_pizza' in r for r in query)
    ids=[r['request_id'] for r in train]; qids=[r['request_id'] for r in query]
    assert len(ids)==len(set(ids)) and len(qids)==len(set(qids)) and not set(ids)&set(qids)
    cols=numeric_columns(train,query); assert cols
    y=np.asarray([int(r['requester_received_pizza']) for r in train]); assert set(y)=={0,1}
    assert sha(OPP/'summary.json')=='c714d7daf46ed431f87a7d0428a60a188613b7452541b932b9e7ad20dfb37139'
    ref=read(OPP/'summary.json')['references'][TASK]['utility']
    ROOT.mkdir()
    plan=dict(role='CLASSICAL_TASK_REFERENCE_NOT_AGENT_METHOD_OR_AUTOMATIC_REPAIR',source_sha256=sha(Path(__file__)),
        public_source_commit='79cf7c6c02afc261e600cc1f88093d4f6ffb2bae',seeds=SEEDS,models=MODEL_NAMES,
        numeric_columns=cols,extra_numeric='character and word count of title and edit-aware text',
        text='title + edit-aware request, TF-IDF word1-2,min_df2,max_features20000,train-fit only',
        excluded='identifiers, usernames, outcome/giver/flair, all at_retrieval, all fields not available at request; no external competition solutions',
        selection='stratified public train80/20; highest validation AUC, model order breaks ties; refit ONLY chosen model on full public train',
        model_parameters=dict(histgbm=dict(max_iter=200,max_leaf_nodes=15,min_samples_leaf=20,learning_rate=.1,l2_regularization=1.,early_stopping=False),
                              logistic=dict(C=1.,solver='liblinear',max_iter=300)),
        total_task_model_fits=9,gpu=0,api_calls=0,cpu_threads=1,hard_fit_seconds=240,
        baseline_context=ref,baseline_note='historical best developer-selected program, not a matched-cost prospective arm',
        train_rows=len(train),query_rows=len(query),shared_ids=0,
        exact_shared_texts=len(set(text(r) for r in train)&set(text(r) for r in query)),
        normalized_shared_texts=len(set(' '.join(text(r).lower().split()) for r in train)&set(' '.join(text(r).lower().split()) for r in query)),
        public_dir=str(public),input_hashes={n:sha(public/n) for n in ['train.json','test.json']},
        versions=dict(python=sys.version.split()[0],numpy=np.__version__,scipy=scipy.__version__,sklearn=sklearn.__version__),
        limitation='known development task, exploratory reference only; no new held-out or same-budget agent effect',invocation=sys.argv)
    save(ROOT/'plan.json',plan); receipts=[]
    for seed in SEEDS:
        start=time.monotonic(); ti,vi=train_test_split(np.arange(len(train)),test_size=.2,stratify=y,random_state=seed)
        mining=[train[int(i)] for i in ti]; valid=[train[int(i)] for i in vi]
        scores=[]
        for name in MODEL_NAMES:
            model=build(name,mining,y[ti],cols,seed); scores.append(float(roc_auc_score(y[vi],predict(model,valid))))
        choice=max(range(len(scores)),key=lambda i:scores[i]); name=MODEL_NAMES[choice]
        model=build(name,train,y,cols,seed); modelpath=ROOT/f'model-{seed}.private.joblib'; joblib.dump(model,modelpath)
        pred=predict(model,query); assert len(pred)==len(query) and np.isfinite(pred).all() and ((pred>=0)&(pred<=1)).all()
        dest=ROOT/f'prediction-{seed}.private.csv'
        with dest.open('x',newline='') as f:
            w=csv.writer(f);w.writerow(['request_id','requester_received_pizza']);w.writerows(zip(qids,map(float,pred)))
        split=ROOT/f'split-{seed}.private.json';save(split,dict(train=ti.tolist(),valid=vi.tolist()))
        rec=dict(seed=seed,chosen_model=name,public_validation_scores=scores,train_rows=len(ti),valid_rows=len(vi),
                 model_sha256=sha(modelpath),prediction_sha256=sha(dest),split_sha256=sha(split),elapsed_seconds=time.monotonic()-start)
        save(ROOT/f'fit-{seed}.json',rec);receipts.append(rec)
    assert all(sha(public/n)==h for n,h in plan['input_hashes'].items())
    out=dict(status='PREDICTIONS_FROZEN_BEFORE_DEVELOPMENT_READOUT',plan_sha256=sha(ROOT/'plan.json'),rows=receipts,elapsed_seconds=time.monotonic()-began,
             protected_opened=False,development_labels_opened=False)
    save(ROOT/'fit-complete.json',out); print(json.dumps(out,sort_keys=True))


def score():
    plan=read(ROOT/'plan.json'); complete=read(ROOT/'fit-complete.json')
    assert sha(ROOT/'plan.json')==complete['plan_sha256'] and sha(Path(__file__))==plan['source_sha256']
    assert len(complete['rows'])==3 and complete['status']=='PREDICTIONS_FROZEN_BEFORE_DEVELOPMENT_READOUT'
    task=task_object();spec=task._search_only_module.SPEC[TASK]
    truth={r['request_id']:int(r['requester_received_pizza']) for r in readcsv(B/spec.get('source',spec.get('view'))/'private/dsearch.csv')}
    outrows=[]
    for r in complete['rows']:
        p=ROOT/f'prediction-{r["seed"]}.private.csv'; assert sha(p)==r['prediction_sha256']
        preds=readcsv(p); d={r['request_id']:float(r['requester_received_pizza']) for r in preds}
        assert len(d)==len(preds)==len(truth) and d.keys()==truth.keys()
        positives=[v for k,v in d.items() if truth[k]];negatives=[v for k,v in d.items() if not truth[k]]
        value=sum((a>b)+.5*(a==b) for a in positives for b in negatives)/(len(positives)*len(negatives))
        native=task._search_only_score(TASK,p)
        assert native['split']=='D_search_development_only'
        # The native metric key is pinned by the public scorer, not guessed.
        values=[float(v) for k,v in native.items() if k in ('roc_auc','auc')]
        assert len(values)==1 and math.isclose(value,values[0],abs_tol=1e-12),native.keys()
        outrows.append(dict(seed=r['seed'],model=r['chosen_model'],auc=value,delta_historical_reference=value-plan['baseline_context'],
            public_source_commit=plan['public_source_commit'],plan_sha256=complete['plan_sha256'],prediction_sha256=r['prediction_sha256'],fit_seconds=r['elapsed_seconds']))
    out=dict(status='COMPLETE_EXPLORATORY_CLASSICAL_REFERENCE',rows=outrows,auc_median=statistics.median(r['auc'] for r in outrows),
             auc_sample_variance=statistics.variance(r['auc'] for r in outrows),seeds_above_historical_reference=sum(r['delta_historical_reference']>0 for r in outrows),
             fit_complete_sha256=sha(ROOT/'fit-complete.json'),baseline=plan['baseline_context'],
             boundary='No new repair rule or agent method. Developer-viewed D_search, not independent generalization or equal-budget E2E.')
    save(ROOT/'summary.json',out)
    with (ROOT/'rows.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(outrows[0]));w.writeheader();w.writerows(outrows)
    print(json.dumps(out,sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['inspect','smoke','fit','score']);args=parser.parse_args()
    dict(inspect=inspect,smoke=smoke,fit=fit,score=score)[args.mode]()
