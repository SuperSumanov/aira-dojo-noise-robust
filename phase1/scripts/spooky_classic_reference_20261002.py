"""Frozen task-only text baselines; not an automatic agent repair method."""
import argparse,csv,hashlib,json,math,os,statistics,sys,time,warnings
from pathlib import Path
B=Path('/research/d7/spc/yzyang4')
OUT=B/'spooky-classic-reference-20261002-v1'
TASK='spooky-author-identification'
SEEDS=[102701,102702,102703]
MODELS=['word_nb','word_char_logistic']
CLASSES=['EAP','HPL','MWS']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def save(p,v):
    with p.open('x') as f:json.dump(v,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
def task_object():
    import task_classic_reference_20261002 as prior
    assert sha(Path(prior.__file__))=='12e23489e4be56518935bfa14480ef2dc7500ab336e7d4e6d72c66c2d82345a6'
    prior.TASK=TASK
    return prior.task_object()
def build(name,texts,y,seed):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.linear_model import LogisticRegression
    from scipy.sparse import hstack
    from sklearn.exceptions import ConvergenceWarning
    word=TfidfVectorizer(ngram_range=(1,2),min_df=2,max_features=30000,sublinear_tf=True)
    x=word.fit_transform(texts); obj=dict(name=name,word=word,seed=seed,fit_rows=len(texts))
    if name=='word_nb':model=MultinomialNB(alpha=.5)
    else:
        assert name=='word_char_logistic'
        char=TfidfVectorizer(analyzer='char',ngram_range=(3,5),min_df=2,max_features=50000,sublinear_tf=True)
        x=hstack([x,char.fit_transform(texts)]).tocsr();obj['char']=char
        model=LogisticRegression(C=4.,solver='lbfgs',max_iter=300,random_state=seed)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always',ConvergenceWarning);model.fit(x,y)
    obj['convergence_warnings']=sum(issubclass(w.category,ConvergenceWarning) for w in caught)
    obj['model']=model
    assert list(model.classes_)==CLASSES
    return obj
def predict(obj,texts):
    from scipy.sparse import hstack
    x=obj['word'].transform(texts)
    if obj['name']=='word_char_logistic':x=hstack([x,obj['char'].transform(texts)]).tocsr()
    return obj['model'].predict_proba(x)
def inspect():
    task=task_object();train=rows(task.public_dir/'train.csv');query=rows(task.public_dir/'test.csv')
    print(json.dumps(dict(public_dir=str(task.public_dir),train_rows=len(train),query_rows=len(query),
        train_columns=list(train[0]),query_columns=list(query[0]),root_exists=OUT.exists())))
def smoke():
    import numpy as np
    texts=[('dark midnight thunder ' if c=='EAP' else 'ancient cosmic deep ' if c=='HPL' else 'life friend heart ')+str(i) for i in range(90) for c in CLASSES]
    labels=CLASSES*90
    for name in MODELS:
        m=build(name,texts,labels,1);p=predict(m,texts)
        assert (p.argmax(axis=1)==np.tile(np.arange(3),90)).all()
        assert np.allclose(p.sum(axis=1),1) and not m['convergence_warnings']
        assert 'private_only_token' not in m['word'].vocabulary_
    print(json.dumps(dict(status='SYNTHETIC_PASS',models=MODELS,source_sha256=sha(Path(__file__)))))
def fit():
    os.umask(0o077);start=time.monotonic()
    import numpy as np,scipy,sklearn,joblib
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import log_loss
    task=task_object();public=task.public_dir;train=rows(public/'train.csv');query=rows(public/'test.csv')
    assert set(train[0])=={'id','text','author'} and set(query[0])=={'id','text'}
    assert len({r['id'] for r in train})==len(train) and len({r['id'] for r in query})==len(query)
    assert not {r['id'] for r in train}&{r['id'] for r in query}
    y=np.array([r['author'] for r in train]);texts=[r['text'] for r in train];qtexts=[r['text'] for r in query]
    refp=B/'repair-opportunity-20261002-v1/summary.json'
    assert sha(refp)=='c714d7daf46ed431f87a7d0428a60a188613b7452541b932b9e7ad20dfb37139'
    ref=-read(refp)['references'][TASK]['utility'];assert 0<ref<2
    OUT.mkdir()
    plan=dict(role='CLASSICAL_TEXT_REFERENCE_NOT_NOVEL_AGENT_METHOD',source_sha256=sha(Path(__file__)),public_source_commit='79cf7c6c02afc261e600cc1f88093d4f6ffb2bae',
        task=TASK,seeds=SEEDS,models=MODELS,classes=CLASSES,total_classifier_fits=9,
        parameters=dict(word=dict(ngram_range=[1,2],min_df=2,max_features=30000,sublinear_tf=True),char=dict(analyzer='char',ngram_range=[3,5],min_df=2,max_features=50000,sublinear_tf=True),nb=dict(alpha=.5),logistic=dict(C=4.,solver='lbfgs',max_iter=300)),
        selection='public stratified80/20 lowest logloss, fixed model-order ties; refit only winner; no later grid or calibration',
        feature_scope='text only, train-fitted vocabulary and IDF; no IDs or query distributions or external task solutions',
        train_rows=len(train),query_rows=len(query),shared_ids=0,exact_text_overlap=len(set(texts)&set(qtexts)),normalized_text_overlap=len({' '.join(t.casefold().split()) for t in texts}&{' '.join(t.casefold().split()) for t in qtexts}),
        public_dir=str(public),input_hashes={n:sha(public/n) for n in ['train.csv','test.csv']},historical_reference_logloss=ref,
        historical_reference_note='Already development-selected best, not equal-budget prospective comparison',
        versions=dict(python=sys.version.split()[0],numpy=np.__version__,scipy=scipy.__version__,sklearn=sklearn.__version__),
        resources=dict(cpu_threads=1,hard_fit_seconds=240,gpu=0,paid_api=0),command=sys.argv)
    save(OUT/'plan.json',plan);recs=[]
    for seed in SEEDS:
        began=time.monotonic();ti,vi=train_test_split(np.arange(len(train)),test_size=.2,stratify=y,random_state=seed)
        scores=[];convergence=[]
        for name in MODELS:
            m=build(name,[texts[i] for i in ti],y[ti],seed)
            scores.append(float(log_loss(y[vi],predict(m,[texts[i] for i in vi]),labels=CLASSES)));convergence.append(m['convergence_warnings'])
        choice=min(range(2),key=lambda i:scores[i]);m=build(MODELS[choice],texts,y,seed)
        p=predict(m,qtexts);assert p.shape==(len(query),3) and np.isfinite(p).all() and (p>=0).all() and np.allclose(p.sum(axis=1),1)
        mp=OUT/f'model-{seed}.private.joblib';joblib.dump(m,mp)
        pp=OUT/f'prediction-{seed}.private.csv'
        with pp.open('x',newline='') as f:
            w=csv.writer(f);w.writerow(['id']+CLASSES);w.writerows([[r['id']]+list(map(float,pr)) for r,pr in zip(query,p,strict=True)])
        sp=OUT/f'split-{seed}.private.json';save(sp,dict(train=ti.tolist(),valid=vi.tolist()))
        rec=dict(seed=seed,chosen_model=MODELS[choice],validation_logloss=scores,convergence_warnings=convergence+[m['convergence_warnings']],
            model_sha256=sha(mp),prediction_sha256=sha(pp),split_sha256=sha(sp),seconds=time.monotonic()-began)
        save(OUT/f'fit-{seed}.json',rec);recs.append(rec)
    assert all(sha(public/n)==h for n,h in plan['input_hashes'].items())
    done=dict(status='ALL_PREDICTIONS_FROZEN',plan_sha256=sha(OUT/'plan.json'),rows=recs,elapsed_seconds=time.monotonic()-start,development_labels_opened=False,protected_opened=False)
    save(OUT/'fit-complete.json',done);print(json.dumps(done,sort_keys=True))
def score():
    p=read(OUT/'plan.json');c=read(OUT/'fit-complete.json');assert c['status']=='ALL_PREDICTIONS_FROZEN' and len(c['rows'])==3
    assert sha(OUT/'plan.json')==c['plan_sha256'] and sha(Path(__file__))==p['source_sha256']
    task=task_object();result=[]
    for r in c['rows']:
        pp=OUT/f'prediction-{r["seed"]}.private.csv';assert sha(pp)==r['prediction_sha256']
        native=task._search_only_score(TASK,pp);assert native['split']=='D_search_development_only'
        value=float(native['log_loss'])
        result.append(dict(seed=r['seed'],model=r['chosen_model'],logloss=value,improvement_over_historical=p['historical_reference_logloss']-value,
            prediction_sha256=r['prediction_sha256'],fit_seconds=r['seconds'],public_source_commit=p['public_source_commit'],plan_sha256=c['plan_sha256']))
    out=dict(status='COMPLETE_EXPLORATORY_REFERENCE',rows=result,median_logloss=statistics.median(r['logloss'] for r in result),sample_variance=statistics.variance(r['logloss'] for r in result),
        distinct_predictions=len({r['prediction_sha256'] for r in result}),above_historical=sum(r['improvement_over_historical']>0 for r in result),baseline=p['historical_reference_logloss'],
        fit_complete_sha256=sha(OUT/'fit-complete.json'),boundary='Task-model reference only. No new automatic correction, agent effect, independent generalization or same-budget E2E claim.')
    save(OUT/'summary.json',out)
    with (OUT/'rows.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(result[0]));w.writeheader();w.writerows(result)
    print(json.dumps(out,sort_keys=True))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['inspect','smoke','fit','score']);x=a.parse_args();globals()[x.mode]()
