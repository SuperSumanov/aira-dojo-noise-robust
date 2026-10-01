"""Separate raw-data verifier for the retrospective rule baseline, no new rule."""
import csv,hashlib,json,math,statistics,sys
from pathlib import Path
BASE=Path('/research/d7/spc/yzyang4');R=BASE/'task-feedback-public-rule-20261002-v1'
OLD=BASE/'task-feedback-real-20261001-v6';PUBLIC=BASE/'tweet-search-only-20260927-a4d1/public'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def similarity(a,b):
    a,b=set(a.lower().split()),set(b.lower().split());u=a.union(b);return len(a.intersection(b))/len(u) if u else 0.
def verify():
    summary=load(R/'summary.json');frozen=load(R/'plan.json');record=load(R/'rule.json')
    assert sha(R/'rule.json')==summary['rule_sha256']=='2beaad25ab591c957f1183de5b17457ff738b25130d13075df500c36bb4fbfc0'
    assert sha(PUBLIC/'train.csv')==frozen['source_sha256'];train=rows(PUBLIC/'train.csv');public=rows(PUBLIC/'test.csv')
    ids=[x['textID'] for x in train];queryids=[x['textID'] for x in public]
    assert len(ids)==len(set(ids)) and len(queryids)==len(set(queryids)) and not set(ids)&set(queryids)
    parts=[[],[]]
    for row in train:
        h=hashlib.sha256(('public-rule-20261002:'+row['textID']).encode()).digest()
        # Independent bytes-to-int equivalent of the mining implementation.
        remainder=0
        for value in h:remainder=(remainder*256+value)%5
        parts[int(remainder==0)].append(row)
    assert list(map(len,parts))==[record['mining_rows'],record['confirmation_rows']]
    features=sorted(k for k in train[0] if k not in ('textID','text','selected_text') and 2<=len({r[k] for r in parts[0]})<=16)
    assert features==record['features']
    candidates=[]
    for k in features:
        for v in sorted({r[k] for r in parts[0]}):
            z=[similarity(r['text'],r['selected_text']) for r in parts[0] if r[k]==v]
            original=next(c for c in record['candidates'] if c['column']==k and c['value']==v)
            assert len(z)==original['mining']['n'] and math.isclose(sum(z)/len(z),original['mining']['mean'],abs_tol=1e-12)
            if len(z)>=200 and sum(z)/len(z)>=.95:candidates.append((len(z),sum(z)/len(z),k,v))
    winner=sorted(candidates,key=lambda q:(-q[0],-q[1],q[2],q[3]))[0]
    rule=summary['rule'];assert (rule['column'],rule['value'])==winner[2:]
    confirmation=[similarity(r['text'],r['selected_text']) for r in parts[1] if r[rule['column']]==rule['value']]
    assert len(confirmation)>=100 and sum(confirmation)/len(confirmation)>=.95
    assert math.isclose(sum(confirmation)/len(confirmation),record['confirmation']['mean'],abs_tol=1e-12)
    sys.path.insert(0,str(OLD));import task_feedback_real_20261001 as engine;engine.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    task=MLEBenchTask(RunConfig.load_from_json(OLD/'configs/11.json').task)
    spec=task._search_only_module.SPEC['tweet-sentiment-extraction']
    truth={r['textID']:r['selected_text'] for r in rows(BASE/spec.get('source',spec.get('view'))/'private/dsearch.csv')}
    inputs={r['textID']:r for r in public};assert set(inputs)==set(truth)
    checked=[];unique={}
    for i,r in enumerate(summary['rows']):
        if r['source'] is None:
            assert r['baseline'] is None and r['difference'] is None;continue
        src=Path(r['source']);assert sha(src)==r['source_sha256']
        original={v['textID']:v['selected_text'] for v in rows(src)}
        amended={v['textID']:v['selected_text'] for v in rows(R/f'prediction-{i}.private.csv')}
        assert set(original)==set(amended)==set(inputs)
        expected={key:(value['text'] if value[rule['column']]==rule['value'] else original[key]) for key,value in inputs.items()}
        assert expected==amended
        a=sum(similarity(truth[k],original[k]) for k in inputs)/len(inputs)
        b=sum(similarity(truth[k],amended[k]) for k in inputs)/len(inputs)
        assert math.isclose(a,r['baseline'],abs_tol=1e-12) and math.isclose(b,r['rule_score'],abs_tol=1e-12)
        assert math.isclose(b-a,r['difference'],abs_tol=1e-12)
        checked.append(i);unique[r['source_sha256']]=r['difference']
    assert len(checked)==7 and len(unique)==6 and len(summary['rows'])==9
    return dict(status='PASS',summary_sha256=sha(R/'summary.json'),rule_sha256=summary['rule_sha256'],
        public_train_rows=len(train),development_input_rows=len(public),shared_ids=0,mining_reproduced=True,confirmation_reproduced=True,
        planned_endpoints=9,scored_endpoints=7,missing_endpoints=2,distinct_prediction_files=6,
        positive_distinct=sum(d>0 for d in unique.values()),unique_difference_median=statistics.median(unique.values()),unique_difference_sample_variance=statistics.variance(unique.values()),
        scope='single task; six different prediction files are NOT six independent datasets, tasks or original starting programs; retrospective feasibility only')
if __name__=='__main__':
    out=verify()
    with (R/'independent-verification.json').open('x') as f:json.dump(out,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps(out,sort_keys=True))
