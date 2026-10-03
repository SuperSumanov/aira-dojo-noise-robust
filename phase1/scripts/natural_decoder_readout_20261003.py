"""Frozen supplement analysis, including the no-training full-text reference."""
import argparse,csv,hashlib,json,math,statistics,sys
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/natural-decoder-factorial-20261003-v1');OLD=R.parent/'natural-opportunity-20261003-v1'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,x):
    with p.open('x') as f:json.dump(x,f,sort_keys=True,indent=2,allow_nan=False)
def csvwrite(p,rr):
    with p.open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def jaccard(a,b):
    x=set(a.lower().split());y=set(b.lower().split());assert x
    return len(x&y)/len(x|y)
def clean(s):
    s=s.strip()
    if len(s)>=2 and s[0] in "\"'" and s[-1]==s[0]:s=s[1:-1]
    return s
def freeze():
    assert not (OLD/'readout.json').exists() and not (R/'readout.json').exists()
    assert jaccard('a b','a')==.5 and jaccard('a','A')==1 and jaccard('a','b')==0
    write(R/'readout-freeze.json',dict(plan_sha256=sha(R/'plan.json'),script_sha256=sha(Path(__file__)),fixtures=3,utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()))
    print('SUPPLEMENT_READOUT_FROZEN')
def analyze():
    frozen=read(R/'readout-freeze.json');assert sha(R/'plan.json')==frozen['plan_sha256'] and sha(Path(__file__))==frozen['script_sha256']
    assert all(x==0 for pair in read(R/'closed.json')['returncodes'] for x in pair)
    assert (OLD/'verification.json').exists() and read(OLD/'verification.json')['status']=='PASS'
    sys.path.insert(0,str(R));import natural_decoder_factorial_20261003 as e
    e.m.check();e.m.runtime()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    cfg=RunConfig.load_from_json(R/'configs/0.json');task=MLEBenchTask(cfg.task);name='tweet-sentiment-extraction'
    assert cfg.task.name==name and task._search_only_score and not task.private_dir.exists()
    spec=task._search_only_module.SPEC[name];label=e.B/spec.get('source',spec.get('view'))/'private/dsearch.csv'
    trows=rows(label);truth={r['textID']:r['selected_text'] for r in trows};assert len(truth)==len(trows)
    public=Path(cfg.task.public_dir)/'test.csv';pr=rows(public);publics={r['textID']:r for r in pr};assert set(publics)==set(truth)
    bindings={str(label):sha(label),str(public):sha(public)};summ=[];per={};cells={}
    def score(path):
        h=sha(path);rr=rows(path);pred={r['textID']:r['selected_text'] for r in rr};assert len(rr)==len(pred)==len(truth) and set(pred)==set(truth)
        receipt=task._search_only_score(name,path);assert receipt['split']=='D_search_development_only'
        vv=[jaccard(truth[k],pred[k]) for k in truth];value=math.fsum(vv)/len(vv)
        assert math.isclose(value,receipt['mean_word_jaccard'],abs_tol=1e-11) and sha(path)==h;bindings[str(path)]=h
        return value,pred,vv
    full=R/'fulltext.private.csv';csvwrite(full,[dict(textID=k,selected_text=clean(publics[k]['text'])) for k in truth]);fullscore,_,_=score(full)
    for seed in (42,173):
        ss=[]
        for s in read(OLD/'plan.json')['schedule']:
            if s['state']==5 and s['seed']==seed:ss.append((OLD,s,'original' if s['arm']=='original' else 'mask_only'))
        for s in read(R/'plan.json')['schedule']:
            if s['seed']==seed:ss.append((R,s,s['arm']))
        for root,s,arm in ss:
            a=root/f'episode-{s["index"]}/action-0';r=read(a/'result.json');value=None;neutral=None
            if r['output_present']:
                assert r['submission_sha256']==sha(a/'submission.private.csv');value,pred,vv=score(a/'submission.private.csv');per[(seed,arm)]=vv
                if arm in ('original','joint'):
                    dest=R/f'neutral-{seed}-{arm}.private.csv'
                    csvwrite(dest,[dict(textID=k,selected_text=clean(publics[k]['text']) if publics[k]['sentiment']=='neutral' else pred[k]) for k in truth]);neutral,_,_=score(dest)
            summ.append(dict(seed=seed,arm=arm,valid=value is not None,score=value,neutral_score=neutral,seconds=r['seconds'],code_sha256=r['code_sha256'],submission_sha256=r['submission_sha256']))
            cells[(seed,arm)]=value
    pairs=[]
    for seed in (42,173):
        a,b,c,d=[cells[(seed,n)] for n in ('original','mask_only','axis_only','joint')];valid=all(v is not None for v in (a,b,c,d))
        pairs.append(dict(seed=seed,original=a,mask_only=b,axis_only=c,joint=d,fulltext=fullscore,joint_gain=d-a if valid else None,
            joint_minus_fulltext=d-fullscore if d is not None else None,interaction=d-b-c+a if valid else None,
            qualified=valid and d-a>=.01 and d-fullscore>=.01))
    for path,h in bindings.items():assert sha(Path(path))==h
    gains=[r['joint_gain'] for r in pairs if r['joint_gain'] is not None]
    out=dict(status='SCORED',plan_sha256=sha(R/'plan.json'),original_plan_sha256=sha(OLD/'plan.json'),script_sha256=sha(Path(__file__)),
        rows=summ,pairs=pairs,fulltext_reference=fullscore,qualified=all(p['qualified'] for p in pairs),
        median_joint_gain=statistics.median(gains) if gains else None,sample_variance=statistics.variance(gains) if len(gains)>1 else None,
        limitation='Separate pre-outcome supplement; does not change original qualification gate. One reused development source, two RNG settings; full-text and neutral references are known rules, not novel methods. No significance/generalization claim.')
    write(R/'readout-bindings.private.json',bindings);csvwrite(R/'readout-runs.csv',summ);csvwrite(R/'readout-pairs.csv',pairs);write(R/'readout.json',out)
    print(json.dumps(out,sort_keys=True))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['freeze','analyze']);globals()[a.parse_args().mode]()
