"""Fixed, train-only HPO. Known representations, not an invented agent method."""
import hashlib
import itertools
import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import sklearn
from scipy.sparse import hstack
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import normalize

CS = (.1, .3, 1., 3., 10., 30., 100.)
GRID = [dict(ngram=n, min_df=d, C=c) for n, d, c in itertools.product((1, 2), (1, 2), CS)]

def vectors(arm, p):
    word = TfidfVectorizer(ngram_range=(1, p['ngram']), min_df=p['min_df'],
        max_features=50000 if arm == 'word' else 25000, sublinear_tf=True, dtype=np.float64)
    if arm == 'word': return [word]
    assert arm == 'word_char'
    return [word, TfidfVectorizer(analyzer='char', ngram_range=(3, 5),
        min_df=p['min_df'], max_features=25000, sublinear_tf=True, dtype=np.float64)]

def design(vs, train, query):
    # Fit vocabularies and IDF on inner-training rows only; no query fit.
    a = [v.fit_transform(train) for v in vs]
    b = [v.transform(query) for v in vs]
    return normalize(hstack(a, format='csr')), normalize(hstack(b, format='csr'))

def classifier(c, seed):
    return OneVsRestClassifier(LogisticRegression(C=c, solver='liblinear',
        max_iter=1000, tol=1e-4, random_state=seed), n_jobs=1)

def value(y, p, classes, binary):
    if binary: return float(roc_auc_score(y, p[:, list(classes).index(1)]))
    return -float(log_loss(y, p, labels=classes))

def choose(rows):
    # Fixed grid order breaks ties. Never reads external scores.
    return max(rows, key=lambda r: r['inner_oriented_score'])

def save(path, obj):
    path=Path(path);tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj, sort_keys=True, allow_nan=False));tmp.replace(path)

def main(task, arm, seed):
    started=time.monotonic();np.random.seed(seed);root=Path('data')
    binary=task == 'random-acts-of-pizza'
    if binary:
        train=pd.DataFrame(json.loads((root/'train.json').read_text()))
        query=pd.DataFrame(json.loads((root/'test.json').read_text()))
        key,text,target='request_id','request_text_edit_aware','requester_received_pizza'
        y=train[target].astype(int).to_numpy()
    else:
        assert task == 'spooky-author-identification'
        train=pd.read_csv(root/'train.csv');query=pd.read_csv(root/'test.csv')
        key,text,target='id','text','author';y=train[target].to_numpy()
    assert target not in query.columns
    t=train[text].fillna('').astype(str).to_numpy();q=query[text].fillna('').astype(str).to_numpy()
    a,b=train_test_split(np.arange(len(y)),test_size=.2,stratify=y,random_state=seed)
    assert not set(a)&set(b) and len(a)+len(b)==len(y)
    rows=[];fit_count=0;binary_fits=0;cache=None;signature=None
    for k,p in enumerate(GRID):
        if time.monotonic()-started>330: raise TimeoutError('grid_budget_incomplete')
        sig=(p['ngram'],p['min_df'])
        begin=time.monotonic()
        if signature!=sig:
            vs=vectors(arm,p);cache=design(vs,t[a],t[b]);signature=sig
        x,z=cache;model=classifier(p['C'],seed)
        with warnings.catch_warnings(record=True) as ws:
            warnings.simplefilter('always',ConvergenceWarning);model.fit(x,y[a])
        prob=model.predict_proba(z);assert np.isfinite(prob).all() and np.allclose(prob.sum(1),1)
        fit_count+=1;binary_fits+=len(model.estimators_)
        rows.append(dict(grid_index=k,params=p,inner_oriented_score=value(y[b],prob,model.classes_,binary),
            converged=not any(issubclass(w.category,ConvergenceWarning) for w in ws),
            features=x.shape[1],seconds=time.monotonic()-begin))
        save('progress.json',dict(task=task,arm=arm,seed=seed,rows=rows,classifier_fits=fit_count,
            binary_fits=binary_fits,elapsed=time.monotonic()-started,grid_complete=False))
    selected=choose(rows);p=selected['params'];vs=vectors(arm,p)
    x,z=design(vs,t,q);model=classifier(p['C'],seed)
    with warnings.catch_warnings(record=True) as ws:
        warnings.simplefilter('always',ConvergenceWarning);model.fit(x,y)
    prob=model.predict_proba(z);assert np.isfinite(prob).all() and np.allclose(prob.sum(1),1)
    if binary: out=pd.DataFrame({key:query[key],target:prob[:,list(model.classes_).index(1)]})
    else:
        out=pd.DataFrame({key:query[key]})
        for c in ('EAP','HPL','MWS'):out[c]=prob[:,list(model.classes_).index(c)]
    out.to_csv('submission.csv',index=False)
    receipt=dict(task=task,arm=arm,seed=seed,grid=GRID,rows=rows,selected=selected,
        classifier_fits=fit_count+1,binary_fits=binary_fits+len(model.estimators_),
        grid_complete=True,final_converged=not any(issubclass(w.category,ConvergenceWarning) for w in ws),
        inner_split_sha256=hashlib.sha256(np.asarray(a,dtype='<i8').tobytes()+np.asarray(b,dtype='<i8').tobytes()).hexdigest(),
        train_rows=len(y),query_rows=len(q),features=x.shape[1],classes=model.classes_.tolist(),
        submission_sha256=hashlib.sha256(Path('submission.csv').read_bytes()).hexdigest(),
        versions=dict(numpy=np.__version__,scipy=scipy.__version__,sklearn=sklearn.__version__,pandas=pd.__version__),
        elapsed_seconds=time.monotonic()-started,fit_visibility='public train only; inner validation for selection; query transform only')
    save('receipt.json',receipt);print('MATCHED_REPRESENTATION_DONE')

def synthetic():
    texts=['alpha beta','beta gamma','alpha gamma','beta delta']*3
    y=np.array([0,1,0,1]*3)
    for arm in ('word','word_char'):
        vs=vectors(arm,dict(ngram=2,min_df=1));x,z=design(vs,texts,['unseentokenxyz alpha'])
        assert all('unseentokenxyz' not in v.vocabulary_ for v in vs)
        assert x.shape[1]<=50000 and np.allclose(np.asarray(x.multiply(x).sum(1)).ravel(),1)
        m=classifier(1,42).fit(x,y);p=m.predict_proba(x)
        assert np.isfinite(value(y,p,m.classes_,True)) and np.allclose(p.sum(1),1)
    assert len(GRID)==28 and len({tuple(p.values()) for p in GRID})==28
    assert choose([{'inner_oriented_score':1,'id':0},{'inner_oriented_score':1,'id':1}])['id']==0
    return dict(status='PASS',arms=2,grid_size=28,unseen_token_excluded=True,tie_order_fixed=True)
