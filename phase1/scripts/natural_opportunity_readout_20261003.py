"""Frozen developer readout. All executions close before any score is read."""
import argparse,csv,hashlib,json,math,statistics,sys
from pathlib import Path
import natural_opportunity_20261003 as m
R=m.ROOT
METRIC={'spooky-author-identification':'log_loss','random-acts-of-pizza':'auc','tweet-sentiment-extraction':'mean_word_jaccard'}
KEY={'spooky-author-identification':'id','random-acts-of-pizza':'request_id','tweet-sentiment-extraction':'textID'}

def rows(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def metric(task,truth,pred):
    key=KEY[task];lookup={r[key]:r for r in pred}
    assert len(lookup)==len(pred)==len(truth) and set(lookup)=={r[key] for r in truth}
    ordered=[lookup[r[key]] for r in truth]
    if task=='spooky-author-identification':
        return statistics.mean(-math.log(max(float(p[y['author']]),1e-15)) for y,p in zip(truth,ordered,strict=True))
    if task=='random-acts-of-pizza':
        pos=[float(p['requester_received_pizza']) for y,p in zip(truth,ordered,strict=True) if int(y['requester_received_pizza'])==1]
        neg=[float(p['requester_received_pizza']) for y,p in zip(truth,ordered,strict=True) if int(y['requester_received_pizza'])==0]
        assert pos and neg and len(pos)+len(neg)==len(truth)
        return sum((a>b)+.5*(a==b) for a in pos for b in neg)/(len(pos)*len(neg))
    scores=[]
    for y,p in zip(truth,ordered,strict=True):
        a=set(y['selected_text'].lower().split());b=set(p['selected_text'].lower().split());assert a
        scores.append(len(a&b)/len(a|b))
    return statistics.mean(scores)

def gain(task,a,b):return a-b if task=='spooky-author-identification' else b-a

def qualifies(task,values):
    threshold={'spooky-author-identification':.005,'random-acts-of-pizza':.005,'tweet-sentiment-extraction':.01}[task]
    return len(values)==2 and all(v is not None and v>=threshold for v in values)

def tests():
    assert gain('spooky-author-identification',.5,.4)>0
    assert gain('random-acts-of-pizza',.5,.4)<0
    assert not qualifies('random-acts-of-pizza',[.01,None])
    assert not qualifies('random-acts-of-pizza',[.01,.001])
    assert qualifies('random-acts-of-pizza',[.006,.007])
    t=[{'request_id':str(i),'requester_received_pizza':str(i%2)} for i in range(4)]
    p=[{'request_id':str(i),'requester_received_pizza':str(i%2)} for i in range(4)]
    assert metric('random-acts-of-pizza',t,list(reversed(p)))==1
    p=[{'request_id':str(i),'requester_received_pizza':'.3'} for i in range(4)]
    assert metric('random-acts-of-pizza',t,p)==.5
    assert metric('tweet-sentiment-extraction',[{'textID':'a','selected_text':'Good DAY'}],[{'textID':'a','selected_text':'good'}])==.5
    assert math.isclose(metric('spooky-author-identification',[{'id':'a','author':'EAP'}],[{'id':'a','EAP':'.5','HPL':'.3','MWS':'.2'}]),math.log(2))
    return 9

def freeze():
    m.check();assert not (R/'readout.json').exists()
    m.write(R/'readout-freeze.json',dict(utc=m.utc(),plan_sha256=m.sha(R/'plan.json'),script_sha256=m.sha(__file__),fixtures=tests(),closure_at_freeze=(R/'closed.json').exists()))
    print(json.dumps({'status':'READOUT_FROZEN','fixtures':9,'script_sha256':m.sha(__file__)}))

def savecsv(p,data):
    with p.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)

def analyze():
    plan=m.check();freeze=m.read(R/'readout-freeze.json')
    assert freeze['script_sha256']==m.sha(__file__) and freeze['plan_sha256']==m.sha(R/'plan.json')
    assert (R/'closed.json').is_file() and not (R/'readout.json').exists()
    # An abnormal worker is not a scored failure: require explicit investigation first.
    assert all(c==0 for row in m.read(R/'closed.json')['returncodes'] for c in row)
    for s in plan['schedule']:
        ep=R/f'episode-{s["index"]}';assert m.read(ep/'closed.json')['returncode']==0
        assert m.read(ep/'completed.json')['status']=='complete'
    m.runtime()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    runs=[];bindings={};unique={};grade_receipts=[]
    for s in plan['schedule']:
        i=s['index'];a=R/f'episode-{i}/action-0';r=m.read(a/'result.json');cfg=RunConfig.load_from_json(R/'configs'/f'{i}.json')
        task=MLEBenchTask(cfg.task);assert task._search_only_score and not task.private_dir.exists()
        name=cfg.task.name;score=None;verified=False;reason='execution_or_output_failure'
        assert all(r[k]==v for k,v in s.items()) and r['plan_sha256']==m.sha(R/'plan.json')
        assert r['code_sha256']==plan['programs'][i]['code_sha256']
        if r['output_present']:
            sub=a/'submission.private.csv';h=m.sha(sub);assert h==r['submission_sha256']
            # Fixed external scorer owns format validity. Unexpected errors stop this readout.
            receipt=task._search_only_score(name,sub);assert receipt['split']=='D_search_development_only'
            score=receipt[METRIC[name]];assert isinstance(score,(int,float)) and math.isfinite(score)
            spec=task._search_only_module.SPEC[name]
            label=m.B/spec.get('source',spec.get('view'))/'private/dsearch.csv'
            assert label.name=='dsearch.csv' and label.parent.name=='private'
            before=m.sha(label);value=metric(name,rows(label),rows(sub))
            assert math.isclose(score,value,rel_tol=1e-11,abs_tol=1e-11),(i,'metric mismatch')
            assert m.sha(label)==before and m.sha(sub)==h
            bindings[str(label)]=before;bindings[str(sub)]=h
            unique.setdefault(name,set()).add(h);verified=True;reason='scored'
            grade_receipts.append(dict(index=i,receipt=receipt))
        runs.append(dict(**s,task=name,metric=METRIC[name],score=score,valid=verified,status=reason,seconds=r['seconds'],
            exit_code=r['exit_code'],timed_out=r['timed_out'],error_type=r['error_type'],code_sha256=r['code_sha256'],submission_sha256=r['submission_sha256'],
            commit=plan['commit'],plan_sha256=m.sha(R/'plan.json'),task_budget_seconds=plan['task_execution_seconds']))
    pairs=[]
    for pair in range(10):
        rr={r['arm']:r for r in runs if r['pair']==pair};a=rr['original'];b=rr['modified'];ok=a['valid'] and b['valid']
        pairs.append(dict(pair=pair,state=a['state'],task=a['task'],seed=a['seed'],both_valid=ok,original=a['score'],modified=b['score'],
            oriented_gain=gain(a['task'],a['score'],b['score']) if ok else None,same_submission=a['submission_sha256']==b['submission_sha256'] if ok else None,
            original_seconds=a['seconds'],modified_seconds=b['seconds']))
    states=[]
    for state in sorted(m.CHANGES):
        pp=[p for p in pairs if p['state']==state];assert len(pp)==2
        values=[p['oriented_gain'] for p in pp];known=[v for v in values if v is not None]
        states.append(dict(state=state,task=pp[0]['task'],change=m.CHANGES[state]['name'],gains=values,valid_pairs=len(known),
            median_gain=statistics.median(known) if known else None,sample_variance=statistics.variance(known) if len(known)>1 else None,
            qualifies=qualifies(pp[0]['task'],values)))
    qualified_tasks=sorted({s['task'] for s in states if s['qualifies']})
    summary=dict(utc=m.utc(),plan_sha256=m.sha(R/'plan.json'),readout_sha256=m.sha(__file__),roster=6,available=5,unavailable=[2],
        executions=20,scored=sum(r['valid'] for r in runs),valid_pairs=sum(p['both_valid'] for p in pairs),states=states,
        qualified_states=sum(s['qualifies'] for s in states),qualified_tasks=qualified_tasks,cross_task_gate=len(qualified_tasks)>=2,
        unique_submission_hashes={k:len(v) for k,v in unique.items()},
        interpretation='Exploratory opportunity qualification on reused development data. Manual reference changes, not automatic agent gains. Two RNG settings per state, not independent physical-run replication. Missing state remains in roster. No heldout, no significance claim.')
    m.write(R/'readout-bindings.private.json',bindings);m.write(R/'grade-receipts.private.json',grade_receipts)
    savecsv(R/'readout-runs.csv',runs);savecsv(R/'readout-pairs.csv',pairs);m.write(R/'readout.json',summary)
    print(json.dumps(summary,sort_keys=True))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['freeze','analyze','tests']);a=ap.parse_args()
    if a.mode=='tests':print(tests())
    else:globals()[a.mode]()
