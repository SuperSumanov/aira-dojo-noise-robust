"""Independent readout and saved-model replay; no refit or configuration search."""
import csv
import hashlib
import json
import math
import re
import statistics
import sys
from pathlib import Path

B=Path('/research/d7/spc/yzyang4')
R=B/'task-span-reference-20261002-v1'
P=B/'tweet-search-only-20260927-a4d1/public'
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_bytes())
def table(p):
    with p.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def jaccard(a,b):
    left=set(a.lower().split());right=set(b.lower().split())
    return len(left.intersection(right))/len(left.union(right)) if left or right else 0.

def replay(model,rows,bias):
    import numpy as np
    from sklearn.feature_extraction import FeatureHasher
    encoded=[]; tokens=[]
    for row in rows:
        ts=list(re.finditer(r'\S+',row['text']));tokens.append(ts)
        words=[t.group().lower() for t in ts];s=row['sentiment'];n=len(ts)
        for i,w in enumerate(words):
            encoded.append({'bias':1.,'sentiment':s,'word':w,'sentiment_word':s+'|'+w,
                            'previous':words[i-1] if i>0 else '<B>',
                            'next':words[i+1] if i+1<n else '<E>',
                            'position':i/max(n-1,1),'length':min(len(w),30)/30,
                            'sentiment_position':s+'|'+str(min(4,i*5//max(n,1)))})
    matrix=FeatureHasher(n_features=262144,alternate_sign=False,dtype=np.float32).transform(encoded)
    margins=model.decision_function(matrix);offset=0;predictions={}
    for row,ts in zip(rows,tokens):
        values=[float(v)-bias for v in margins[offset:offset+len(ts)]];offset+=len(ts)
        if row['sentiment']=='neutral' or not ts: pred=row['text']
        else:
            # Exhaustive spans, independent of the production linear decoder.
            best=None;chosen=None
            for end in range(1,len(ts)+1):
                for start in range(end):
                    value=sum(values[start:end])
                    if best is None or value>best: best=value;chosen=(start,end)
            start,end=chosen;pred=row['text'][ts[start].start():ts[end-1].end()]
        predictions[row['textID']]=pred
    return predictions

def main():
    import joblib
    plan=read(R/'plan.json');complete=read(R/'fit-complete.json');summary=read(R/'summary.json')
    assert digest(R/'plan.json')==complete['plan_sha256']
    assert digest(R/'fit-complete.json')==summary['fit_complete_sha256']
    assert digest(P/'train.csv')==plan['train_sha256'] and digest(P/'test.csv')==plan['input_sha256']
    train=table(P/'train.csv');query=table(P/'test.csv');q={r['textID']:r for r in query}
    assert len(q)==len(query) and not set(q)&{r['textID'] for r in train}
    sys.path.insert(0,str(B/'task-feedback-real-20261001-v6'))
    import task_feedback_real_20261001 as runner
    runner.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    task=MLEBenchTask(RunConfig.load_from_json(B/'task-feedback-real-20261001-v6/configs/11.json').task)
    spec=task._search_only_module.SPEC['tweet-sentiment-extraction']
    truthrows=table(B/spec.get('source',spec.get('view'))/'private/dsearch.csv')
    truth={r['textID']:r['selected_text'] for r in truthrows}
    assert len(truthrows)==len(truth)==len(q) and truth.keys()==q.keys()
    checked=[]
    assert [r['seed'] for r in summary['rows']]==plan['seeds']==[r['seed'] for r in complete['rows']]
    for fit,row in zip(complete['rows'],summary['rows']):
        seed=row['seed'];modelpath=R/f'model-{seed}.private.joblib';predpath=R/f'prediction-{seed}.private.csv'
        assert digest(modelpath)==fit['model_sha256']
        assert digest(predpath)==fit['prediction_sha256']==row['prediction_sha256']
        model=joblib.load(modelpath)
        assert model.random_state==seed and model.max_iter==8 and model.alpha==1e-5 and model.average
        predrows=table(predpath);pred={r['textID']:r['selected_text'] for r in predrows}
        assert len(predrows)==len(pred)==len(q) and pred.keys()==q.keys()
        assert pred==replay(model,query,fit['chosen_bias'])
        assert fit['chosen_bias']==plan['biases'][max(range(len(plan['biases'])),key=lambda j:fit['public_validation_scores'][j])]
        value=statistics.fmean(jaccard(pred[k],truth[k]) for k in q)
        assert math.isclose(value,row['score'],abs_tol=1e-12)
        for sentiment in ('neutral','positive','negative'):
            keys=[k for k in q if q[k]['sentiment']==sentiment]
            assert len(keys)==row[sentiment+'_rows']
            assert math.isclose(statistics.fmean(jaccard(pred[k],truth[k]) for k in keys),row[sentiment+'_score'],abs_tol=1e-12)
        for key,col in [('original_plus_rule','difference_original'),('historical_strong_F_plus_rule','difference_strong')]:
            assert math.isclose(value-summary['baselines'][key],row[col],abs_tol=1e-12)
        checked.append(value)
    assert math.isclose(statistics.median(checked),summary['seed_score_median'],abs_tol=1e-12)
    assert math.isclose(statistics.variance(checked),summary['seed_score_sample_variance'],abs_tol=1e-15)
    assert summary['full_denominator']==len(checked)==3
    exact={r['text'] for r in train};normalized={' '.join(r['text'].lower().split()) for r in train}
    out=dict(status='PASS',seeds=plan['seeds'],models_replayed=3,prediction_rows_per_seed=len(q),
             exact_text_query_overlap=sum(r['text'] in exact for r in query),
             normalized_text_query_overlap=sum(' '.join(r['text'].lower().split()) in normalized for r in query),
             summary_sha256=digest(R/'summary.json'),verifier_sha256=digest(Path(__file__)),
             scope='saved model, exhaustive decoder and independent metric; no new fit/selection/test')
    with (R/'verification.json').open('x') as f: json.dump(out,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps(out,sort_keys=True))

if __name__=='__main__': main()
