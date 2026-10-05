"""Bounded continuation after shared word-HPO initialization. No answer hints."""
import ast,itertools,json
TASKS=('random-acts-of-pizza','spooky-author-identification')
SEEDS=(115001,115002)
ARMS=('ordinary','profile','open_hpo')
GRID=[dict(arm=a,C=c,ngram=n,min_df=d) for a,n,d,c in itertools.product(('word','word_char'),(1,2),(1,2),(.1,.3,1.,3.,10.,30.,100.))]
def schedule():
    rows=[]
    for j,seed in enumerate(SEEDS):
        for arm in (ARMS if j==0 else tuple(reversed(ARMS))):
            for t,task in enumerate(TASKS):rows.append(dict(index=len(rows),wave=len(rows)//2,task=task,task_index=t,seed=seed,arm=arm,generation_seed=116001+10*j+t))
    return rows
def source(task,p):
    feature_cap=50000 if p['arm']=='word' else 25000
    extra='' if p['arm']=='word' else "\nvectors.append(TfidfVectorizer(analyzer='char',ngram_range=(3,5),min_df=params['min_df'],max_features=25000,sublinear_tf=True,dtype=np.float64))"
    return f'''import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.sparse import hstack
from sklearn.preprocessing import normalize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
task={task!r};params={p!r};root=Path('data')
if task=='random-acts-of-pizza':
    train=pd.DataFrame(json.loads((root/'train.json').read_text()))
    query=pd.DataFrame(json.loads((root/'test.json').read_text()))
    key,text,target='request_id','request_text_edit_aware','requester_received_pizza'
    y=train[target].astype(int).to_numpy()
else:
    train=pd.read_csv(root/'train.csv');query=pd.read_csv(root/'test.csv')
    key,text,target='id','text','author';y=train[target].to_numpy()
vectors=[TfidfVectorizer(ngram_range=(1,params['ngram']),min_df=params['min_df'],max_features={feature_cap},sublinear_tf=True,dtype=np.float64)]{extra}
x=normalize(hstack([v.fit_transform(train[text].fillna('').astype(str)) for v in vectors],format='csr'))
z=normalize(hstack([v.transform(query[text].fillna('').astype(str)) for v in vectors],format='csr'))
m=OneVsRestClassifier(LogisticRegression(C=params['C'],solver='liblinear',max_iter=1000,tol=1e-4,random_state=42),n_jobs=1).fit(x,y)
pred=m.predict_proba(z);assert np.isfinite(pred).all() and np.allclose(pred.sum(1),1)
out=pd.DataFrame({{key:query[key]}})
if task=='random-acts-of-pizza':out[target]=pred[:,list(m.classes_).index(1)]
else:
    for c in ('EAP','HPL','MWS'):out[c]=pred[:,list(m.classes_).index(c)]
out.to_csv('submission.csv',index=False)
'''

def baseline(task):
    # Execute all fixed configurations in one task process; score outside container.
    # Reuse vectorizers only within one representation/ngram/min_df combination.
    return f'''import json,time,warnings
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.sparse import hstack
from sklearn.preprocessing import normalize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.exceptions import ConvergenceWarning
task={task!r};grid={GRID!r};root=Path('data')
if task=='random-acts-of-pizza':
    train=pd.DataFrame(json.loads((root/'train.json').read_text()));query=pd.DataFrame(json.loads((root/'test.json').read_text()))
    key,text,target='request_id','request_text_edit_aware','requester_received_pizza';y=train[target].astype(int).to_numpy()
else:
    train=pd.read_csv(root/'train.csv');query=pd.read_csv(root/'test.csv');key,text,target='id','text','author';y=train[target].to_numpy()
assert target not in query.columns
begin=time.monotonic();signature=None;receipt=[]
for i,params in enumerate(grid):
    sig=(params['arm'],params['ngram'],params['min_df'])
    if signature!=sig:
        vectors=[TfidfVectorizer(ngram_range=(1,params['ngram']),min_df=params['min_df'],max_features=50000 if params['arm']=='word' else 25000,sublinear_tf=True,dtype=np.float64)]
        if params['arm']=='word_char':vectors.append(TfidfVectorizer(analyzer='char',ngram_range=(3,5),min_df=params['min_df'],max_features=25000,sublinear_tf=True,dtype=np.float64))
        x=normalize(hstack([v.fit_transform(train[text].fillna('').astype(str)) for v in vectors],format='csr'))
        z=normalize(hstack([v.transform(query[text].fillna('').astype(str)) for v in vectors],format='csr'));signature=sig
    with warnings.catch_warnings(record=True) as ws:
        warnings.simplefilter('always',ConvergenceWarning)
        m=OneVsRestClassifier(LogisticRegression(C=params['C'],solver='liblinear',max_iter=1000,tol=1e-4,random_state=42),n_jobs=1).fit(x,y)
    pred=m.predict_proba(z);out=pd.DataFrame({{key:query[key]}})
    if task=='random-acts-of-pizza':out[target]=pred[:,list(m.classes_).index(1)]
    else:
        for c in ('EAP','HPL','MWS'):out[c]=pred[:,list(m.classes_).index(c)]
    out.to_csv(f'candidate-{{i}}.csv',index=False)
    receipt.append(dict(index=i,params=params,converged=not any(issubclass(w.category,ConvergenceWarning) for w in ws)))
Path('grid-receipt.json').write_text(json.dumps(dict(rows=receipt,elapsed=time.monotonic()-begin)))
'''

def messages(task,arm,code,score,profile):
    assert arm in ('ordinary','profile')
    metric='AUC (higher is better)' if task==TASKS[0] else 'multiclass logloss (lower is better)'
    schema=('Read data/train.json and data/test.json as record lists. ID request_id; text request_text_edit_aware; binary target requester_received_pizza. Output columns request_id,requester_received_pizza.' if task==TASKS[0] else 'Read data/train.csv and data/test.csv. ID id, text text, target author. Output columns id,EAP,HPL,MWS.')
    system='''You are improving a working machine-learning program in a bounded development experiment.
Return at most two sentences then ONE complete Python code block saving submission.csv.
Use only the supplied training labels and unlabeled query rows in ./data. Fit all transformations on training rows only.
No downloads, network, external/pretrained models, service calls or evaluator files.
You may change representation, features, classifier or hyperparameters; no word-only restriction.
Keep the loader and output schema correct. Available: numpy,pandas,scipy,sklearn,xgboost,lightgbm.
Six CPU cores and one RTX3090, original task image. Single execution at most 120 seconds.
Code will be run on this training/validation view, and if selected rerun on the larger training view and different unlabeled query rows.
Do not hardcode row counts, query identities or prediction values. No mandatory CV, PLAN-only output or diagnostic-only script.
One code proposal only; no debugging retry in this experiment.'''
    user=f'Task: {task}\nMetric: {metric}\n{schema}\nCurrent internal-validation score: {score}\nWorking source:\n```python\n{code}\n```\nImprove this solution.'
    if arm=='profile':
        user+='\nTraining-only tuning evidence for the CURRENT representation (not external evaluation):\n'+json.dumps(profile,sort_keys=True)
        user+='\nUse this response surface to decide whether further numeric tuning or a change to the modeling structure is more promising. Do not merely describe a change: implement your chosen change.'
    return [dict(role='system',content=system),dict(role='user',content=user)]

def tests():
    assert len(schedule())==12 and len(GRID)==56
    for task in TASKS:
        parent=source(task,dict(arm='word',C=30,ngram=2,min_df=1));ast.parse(parent);ast.parse(baseline(task))
        a=messages(task,'ordinary',parent,.5,[]);b=messages(task,'profile',parent,.5,[])
        assert a[0]==b[0] and b[1]['content'].startswith(a[1]['content'])
        assert 'character' not in b[1]['content'].lower() and 'char' not in b[1]['content'].lower()
    return dict(status='PASS',schedule=12,grid=56,rendered_pairs=2,common_system=True,no_answer_hint=True)
