"""Independent feature reconstruction, public split replay and AUC check."""
import csv, hashlib, json, math, statistics
from pathlib import Path
import numpy as np
import joblib
from scipy.sparse import csr_matrix,hstack
from scipy.special import expit
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score

B=Path('/research/d7/spc/yzyang4')
ROOT=B/'task-classic-reference-20261002-v1'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def main():
    p=read(ROOT/'plan.json');c=read(ROOT/'fit-complete.json');s=read(ROOT/'summary.json')
    assert sha(ROOT/'plan.json')==c['plan_sha256']
    assert sha(ROOT/'fit-complete.json')==s['fit_complete_sha256']
    public=Path(p['public_dir'])
    for n,h in p['input_hashes'].items():assert sha(public/n)==h
    train=read(public/'train.json');query=read(public/'test.json')
    assert not set(r['request_id'] for r in train)&set(r['request_id'] for r in query)
    assert all('requester_received_pizza' not in r for r in query)
    fields=p['numeric_columns']
    assert len(fields)==11 and all((f.endswith('_at_request') or f in ('unix_timestamp_of_request','unix_timestamp_of_request_utc')) for f in fields)
    assert not any(any(b in f for b in ('flair','giver','received','retrieval','username')) for f in fields)
    y=np.array([int(r['requester_received_pizza']) for r in train])
    # Resolve the scorer's registered source. The public view is not the label source.
    from task_classic_reference_20261002 import task_object
    task=task_object(); spec=task._search_only_module.SPEC['random-acts-of-pizza']
    labelpath=B/spec.get('source',spec.get('view'))/'private/dsearch.csv'
    # Same previously approved development labels, not official test.
    truth={r['request_id']:int(r['requester_received_pizza']) for r in rows(labelpath)}
    checked=[]
    for receipt,result in zip(c['rows'],s['rows'],strict=True):
        seed=receipt['seed'];assert seed==result['seed']
        mp=ROOT/f'model-{seed}.private.joblib';predpath=ROOT/f'prediction-{seed}.private.csv';sp=ROOT/f'split-{seed}.private.json'
        assert sha(mp)==receipt['model_sha256'] and sha(predpath)==receipt['prediction_sha256'] and sha(sp)==receipt['split_sha256']
        ti,vi=train_test_split(np.arange(len(train)),test_size=.2,stratify=y,random_state=seed)
        split=read(sp);assert ti.tolist()==split['train'] and vi.tolist()==split['valid']
        assert not set(ti)&set(vi) and set(ti)|set(vi)==set(range(len(train)))
        # Ties select the earlier fixed model, never a development-score choice.
        scores=receipt['public_validation_scores']; chosen=max(enumerate(scores),key=lambda z:(z[1],-z[0]))[0]
        assert p['models'][chosen]==receipt['chosen_model']==result['model']
        model=joblib.load(mp);assert model['fit_rows']==len(train) and model['columns']==fields
        records=[]
        for record in query:
            vals=[]
            for f in fields:
                v=record[f];vals.append(float(v) if isinstance(v,(int,float,bool)) and math.isfinite(float(v)) else np.nan)
            texts=[str(record.get(f) or '') for f in ('request_title','request_text_edit_aware')]
            records.append(vals+list(map(len,texts))+[len(t.split()) for t in texts])
        X=np.array(records)
        imputer=model['imputer'];stats=imputer.statistics_
        for j in range(X.shape[1]):X[np.isnan(X[:,j]),j]=stats[j]
        if result['model']=='text_metadata_logistic':
            z=(X-model['scaler'].mean_)/model['scaler'].scale_
            tx=model['tfidf'].transform([str(r.get('request_title') or '')+'\n'+str(r.get('request_text_edit_aware') or '') for r in query])
            matrix=hstack([tx,csr_matrix(z)]).tocsr();m=model['model']
            pred=expit(np.asarray(matrix@m.coef_.T).ravel()+m.intercept_[0])
        else:pred=model['model'].predict_proba(X)[:,1]
        recorded=rows(predpath);assert [r['request_id'] for r in query]==[r['request_id'] for r in recorded]
        assert np.allclose(pred,[float(r['requester_received_pizza']) for r in recorded],rtol=0,atol=1e-12)
        yy=[truth[r['request_id']] for r in query];auc=float(roc_auc_score(yy,pred))
        assert math.isclose(auc,result['auc'],abs_tol=1e-12)
        assert math.isclose(auc-p['baseline_context'],result['delta_historical_reference'],abs_tol=1e-12)
        checked.append(auc)
    assert math.isclose(statistics.median(checked),s['auc_median'],abs_tol=1e-12)
    assert math.isclose(statistics.variance(checked),s['auc_sample_variance'],abs_tol=1e-12)
    out=dict(status='PASS',rows=3,distinct_prediction_files=len(set(r['prediction_sha256'] for r in c['rows'])),
        scope='Independent numeric matrix/imputation/scaling/logistic algebra and sklearn AUC; shared library HistGBM inference; no full model refit',
        limitation='Two histgbm full fits give identical predictions; three public selection seeds are not three independent tasks or data draws.',
        source_sha256=sha(Path(__file__)),summary_sha256=sha(ROOT/'summary.json'),plan_sha256=sha(ROOT/'plan.json'))
    with (ROOT/'verification.json').open('x') as f:json.dump(out,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps(out,sort_keys=True))

if __name__=='__main__':main()
