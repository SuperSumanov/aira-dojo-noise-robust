"""Reconstruct frozen text-model probabilities algebraically; no refit."""
import csv,hashlib,json,math,statistics
from pathlib import Path
import numpy as np,joblib
from scipy.sparse import hstack
from scipy.special import softmax
from sklearn.model_selection import train_test_split
B=Path('/research/d7/spc/yzyang4');OUT=B/'spooky-classic-reference-20261002-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
    from spooky_classic_reference_20261002 import task_object,TASK
    p=read(OUT/'plan.json');c=read(OUT/'fit-complete.json');s=read(OUT/'summary.json')
    assert sha(OUT/'plan.json')==c['plan_sha256'] and sha(OUT/'fit-complete.json')==s['fit_complete_sha256']
    public=Path(p['public_dir'])
    for name,h in p['input_hashes'].items():assert sha(public/name)==h
    train=rows(public/'train.csv');query=rows(public/'test.csv');y=np.array([r['author'] for r in train])
    assert not {r['id'] for r in train}&{r['id'] for r in query}
    assert set(query[0])=={'id','text'}
    task=task_object();spec=task._search_only_module.SPEC[TASK]
    truth={r['id']:r['author'] for r in rows(B/spec.get('source',spec.get('view'))/'private/dsearch.csv')}
    scores=[]
    for r,res in zip(c['rows'],s['rows'],strict=True):
        seed=r['seed'];assert seed==res['seed']
        mp=OUT/f'model-{seed}.private.joblib';sp=OUT/f'split-{seed}.private.json';pp=OUT/f'prediction-{seed}.private.csv'
        assert sha(mp)==r['model_sha256'] and sha(sp)==r['split_sha256'] and sha(pp)==r['prediction_sha256']
        ti,vi=train_test_split(np.arange(len(train)),test_size=.2,stratify=y,random_state=seed)
        split=read(sp);assert ti.tolist()==split['train'] and vi.tolist()==split['valid']
        choice=min(enumerate(r['validation_logloss']),key=lambda item:(item[1],item[0]))[0]
        assert p['models'][choice]==r['chosen_model']==res['model']
        obj=joblib.load(mp);model=obj['model'];assert obj['fit_rows']==len(train) and list(model.classes_)==p['classes']
        x=obj['word'].transform([row['text'] for row in query])
        if obj['name']=='word_char_logistic':
            x=hstack([x,obj['char'].transform([row['text'] for row in query])]).tocsr()
            logits=np.asarray(x@model.coef_.T)+model.intercept_
        else:logits=np.asarray(x@model.feature_log_prob_.T)+model.class_log_prior_
        pred=softmax(logits,axis=1);recorded=rows(pp)
        assert [r['id'] for r in query]==[r['id'] for r in recorded]
        assert set(truth)=={r['id'] for r in query}
        raw=np.array([[float(r[k]) for k in p['classes']] for r in recorded])
        assert np.allclose(pred,raw,rtol=0,atol=1e-12)
        loss=-math.fsum(math.log(max(np.finfo(float).eps,float(prob[p['classes'].index(truth[row['id']])]))) for row,prob in zip(query,pred,strict=True))/len(query)
        assert math.isclose(loss,res['logloss'],abs_tol=1e-12)
        assert math.isclose(p['historical_reference_logloss']-loss,res['improvement_over_historical'],abs_tol=1e-12)
        scores.append(loss)
    assert math.isclose(statistics.median(scores),s['median_logloss'],abs_tol=1e-12)
    assert math.isclose(statistics.variance(scores),s['sample_variance'],abs_tol=1e-12)
    out=dict(status='PASS',seeds=len(scores),distinct_predictions=len({r['prediction_sha256'] for r in c['rows']}),
        scope='Independent saved split replay, model-selection check, linear logits/softmax and per-row log loss; shared TFIDF transform, no full fitting rerun.',
        limitation='Three selection seeds yield identical final predictions; not three independent outcomes. This is a classical task reference, not a new method.',
        source_sha256=sha(Path(__file__)),plan_sha256=sha(OUT/'plan.json'),summary_sha256=sha(OUT/'summary.json'))
    with (OUT/'verification.json').open('x') as f:json.dump(out,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps(out,sort_keys=True))
if __name__=='__main__':main()
