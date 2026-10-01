"""Retrospective public-training rule baseline; not a novel or held-out discovery.

No candidate code execution, GPU, LLM, optimizer or official-test access. This
rule family was designed AFTER seeing a neutral-copy pattern: do not claim
independent rule discovery or task generalization. Public-only mining tests
whether the known simple baseline can be instantiated without a hand-coded
sentiment value, NOT whether the research process was outcome-naive.
"""
import argparse,csv,hashlib,json,math,os,statistics,sys,time
from pathlib import Path
BASE=Path('/research/d7/spc/yzyang4')
OLD=BASE/'task-feedback-real-20261001-v6'
LOCAL=BASE/'task-feedback-local-edit-20261002-v1'
PUBLIC=BASE/'tweet-search-only-20260927-a4d1/public'
OUT=BASE/'task-feedback-public-rule-20261002-v1'
THRESHOLD=.95
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def jac(a,b):
    x=set(a.lower().split());y=set(b.lower().split());return len(x&y)/len(x|y) if x|y else 0.
def bucket(i):return int(hashlib.sha256(('public-rule-20261002:'+i).encode()).hexdigest(),16)%5
def stats(xs):return dict(n=len(xs),mean=statistics.mean(xs) if xs else None,median=statistics.median(xs) if xs else None,sample_variance=statistics.variance(xs) if len(xs)>1 else None)
def select_rule(data):
    assert len({r['textID'] for r in data})==len(data)
    train=[r for r in data if bucket(r['textID'])!=0];confirm=[r for r in data if bucket(r['textID'])==0]
    features=sorted(k for k in data[0] if k not in ('textID','text','selected_text') and 2<=len({r[k] for r in train})<=16)
    candidates=[]
    for k in features:
        for v in sorted({r[k] for r in train}):
            group=[r for r in train if r[k]==v];ys=[jac(r['text'],r['selected_text']) for r in group]
            candidates.append(dict(column=k,value=v,mining=stats(ys),mining_pass=len(ys)>=200 and statistics.mean(ys)>=THRESHOLD))
    qualified=[c for c in candidates if c['mining_pass']]
    chosen=min(qualified,key=lambda c:(-c['mining']['n'],-c['mining']['mean'],c['column'],c['value'])) if qualified else None
    # Only ONE mining-selected rule is checked. Failure does not try a runner-up.
    confirmed=None
    if chosen:
        vals=[jac(r['text'],r['selected_text']) for r in confirm if r[chosen['column']]==chosen['value']]
        confirmed=stats(vals)
        if len(vals)<100 or confirmed['mean']<THRESHOLD:chosen=None
    return dict(features=features,mining_rows=len(train),confirmation_rows=len(confirm),candidates=candidates,confirmation=confirmed,
        chosen=dict(column=chosen['column'],value=chosen['value'],operation='copy_full_text') if chosen else None,
        threshold=THRESHOLD,scope='empirical public-only screen, not a statistical guarantee or independent discovery')
def mine():
    os.umask(0o077);OUT.mkdir();began=time.monotonic()
    plan=dict(source=str(PUBLIC/'train.csv'),source_sha256=sha(PUBLIC/'train.csv'),script_sha256=sha(Path(__file__)),threshold=THRESHOLD,
        minimum_mining_rows=200,minimum_confirmation_rows=100,categorical_cardinality=[2,16],
        family='copy full public input text conditioned on one non-ID/input/target categorical column value',
        selection='largest qualifying mining group, then highest mining mean, then lexical; confirm once, no fallback',
        split='SHA256(public-rule-20261002:textID) mod5, zero confirmation, others mining',
        retrospective=True,private_labels_opened=False,gpu=0,agent_calls=0,model_optimizer_fits=0)
    with (OUT/'plan.json').open('x') as f:json.dump(plan,f,sort_keys=True,indent=2);f.write('\n')
    result=select_rule(rows(PUBLIC/'train.csv'));result.update(plan_sha256=sha(OUT/'plan.json'),elapsed_seconds=time.monotonic()-began)
    with (OUT/'rule.json').open('x') as f:json.dump(result,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps(result,sort_keys=True));print('rule_sha256='+sha(OUT/'rule.json'))
def evaluate(expected):
    os.umask(0o077);began=time.monotonic();assert sha(OUT/'rule.json')==expected
    frozen=read(OUT/'plan.json');assert sha(PUBLIC/'train.csv')==frozen['source_sha256']
    assert sha(Path(__file__))==frozen['script_sha256']
    rule=read(OUT/'rule.json')['chosen'];assert rule is not None
    assert (OLD/'all-closed.json').exists() and (LOCAL/'all-closed.json').exists()
    assert sha(OLD/'plan.json')=='15751d3b52bdc42617df02006ce724635f4bf49df6e477686769fd1979d53403'
    assert sha(LOCAL/'plan.json')=='7bd84ff0e867043b2787d5c07af867eff50370f4e7b6bafa811ef215196c4139'
    # All original Tweet endpoints, then ALL three manual-guidance full-code
    # endpoints, including invalid/missing ones. No source picked by new gains.
    selected=[]
    for root in (OLD,LOCAL):
        for s in read(root/'plan.json')['schedule']:
            if s['task']!='tweet-sentiment-extraction' or (root==LOCAL and s['arm']!='F'):continue
            ep=root/f'episode-{s["index"]}';assert (ep/'closed.json').exists()
            picks=sorted(ep.glob('action-*/selected.json'),key=lambda p:int(p.parent.name.split('-')[-1]))
            src=picks[-1].parent/'submission.private.csv' if picks else None
            selected.append(dict(batch=root.name,**s,source=str(src) if src else None,source_sha256=sha(src) if src else None))
    assert len(selected)==9
    manifest=dict(rule_sha256=expected,public_input_sha256=sha(PUBLIC/'test.csv'),sources=selected,
        selection='all6 original Tweet endpoints + all3 later F endpoints; no new-gain selection',denominator=9)
    with (OUT/'evaluation-plan.json').open('x') as f:json.dump(manifest,f,sort_keys=True,indent=2);f.write('\n')
    sys.path.insert(0,str(OLD));import task_feedback_real_20261001 as m;m.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    task=MLEBenchTask(RunConfig.load_from_json(OLD/'configs/11.json').task)
    public=rows(PUBLIC/'test.csv');lookup={r['textID']:r for r in public};assert len(lookup)==len(public)
    spec=task._search_only_module.SPEC['tweet-sentiment-extraction']
    truth={r['textID']:r['selected_text'] for r in rows(m.B/spec.get('source',spec.get('view'))/'private/dsearch.csv')}
    assert set(truth)==set(lookup)
    results=[]
    for n,s in enumerate(selected):
        r=dict(**s,baseline=None,rule_score=None,difference=None,changed_rows=None)
        if s['source']:
            src=Path(s['source']);old=rows(src);assert sha(src)==s['source_sha256']
            assert len(old)==len(lookup) and {v['textID'] for v in old}==set(lookup)
            new=[dict(v,selected_text=lookup[v['textID']]['text']) if lookup[v['textID']][rule['column']]==rule['value'] else dict(v) for v in old]
            dest=OUT/f'prediction-{n}.private.csv'
            with dest.open('x',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(old[0]));w.writeheader();w.writerows(new)
            v0=task._search_only_score('tweet-sentiment-extraction',src);v1=task._search_only_score('tweet-sentiment-extraction',dest)
            assert v0['split']==v1['split']=='D_search_development_only'
            a=statistics.mean(jac(truth[v['textID']],v['selected_text']) for v in old)
            b=statistics.mean(jac(truth[v['textID']],v['selected_text']) for v in new)
            assert math.isclose(a,v0['mean_word_jaccard'],abs_tol=1e-12) and math.isclose(b,v1['mean_word_jaccard'],abs_tol=1e-12)
            assert all(x==y for x,y in zip(old,new) if lookup[x['textID']][rule['column']]!=rule['value'])
            assert sha(src)==s['source_sha256']
            r.update(baseline=a,rule_score=b,difference=b-a,changed_rows=sum(x!=y for x,y in zip(old,new)),independent_match=True)
        results.append(r)
    assert sha(OUT/'rule.json')==expected and sha(PUBLIC/'test.csv')==manifest['public_input_sha256']
    out=dict(status='RETROSPECTIVE_BASELINE_CHECK',rule=rule,rule_sha256=expected,rows=results,full_denominator=9,
        valid_sources=sum(r['baseline'] is not None for r in results),unique_prediction_sources=len({r['source_sha256'] for r in results if r['source']}),
        scope='same single-task development set, dependent sources, two old code origins; not independent method efficacy or task generalization',
        empirical_rule_fits=1,model_optimizer_fits=0,agent_calls=0,new_gpu=0,elapsed_seconds=time.monotonic()-began)
    with (OUT/'summary.json').open('x') as f:json.dump(out,f,sort_keys=True,indent=2);f.write('\n')
    with (OUT/'rows.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
    print(json.dumps(out,sort_keys=True))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['mine','evaluate']);p.add_argument('--rule-sha256');a=p.parse_args()
    mine() if a.mode=='mine' else evaluate(a.rule_sha256)
