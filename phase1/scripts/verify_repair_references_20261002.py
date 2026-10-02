"""Independent finalizer reconstruction and ranking-guard verification."""
import csv
import hashlib
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

B=Path('/research/d7/spc/yzyang4')
E=B/'trajectory-ensemble-reference-20261002-v1'
G=B/'rank-locality-screen-20261002-v1'
OLD=B/'task-feedback-real-20261001-v6'
TASKS=('spooky-author-identification','random-acts-of-pizza','tweet-sentiment-extraction')
KEYS=dict(zip(TASKS,('id','request_id','textID')))


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def close(a,b):assert math.isclose(float(a),float(b),abs_tol=1e-11,rel_tol=1e-10)
def j(a,b):
    x,y=set(a.lower().split()),set(b.lower().split())
    return len(x&y)/len(x|y) if x|y else 0.
def save(p,obj):
    with p.open('x') as f:json.dump(obj,f,sort_keys=True,indent=2);f.write('\n')


def main():
    os.umask(0o077)
    assert sha(E/'plan.json')=='81839a83db2297b23b758137411f7956947d78208b67c76b26aeb2d0ed078513'
    assert sha(E/'rows.csv')=='8ac35729bdd29e9f58a23a02feb88f9f3503542ae959482b0777734dfa622b78'
    assert sha(G/'plan.json')=='8c115aa6020dd628242eb5ce8877c9db14f1fb84b2ee2683725ae8f981689fcc'
    assert sha(G/'rows.csv')=='bcae698b05f9af6c45d529cbc7873a13c7e86d9cd8f5710745521cb04c78d5ab'
    binding=read(B/'repair-opportunity-20261002-v1/bindings.private.json')
    for p,h in binding.items():assert sha(Path(p))==h
    sys.path.insert(0,str(OLD));import task_feedback_real_20261001 as runtime
    runtime.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    import numpy as np
    data={}
    for task in TASKS:
        i=next(s['index'] for s in read(OLD/'plan.json')['schedule'] if s['task']==task)
        obj=MLEBenchTask(RunConfig.load_from_json(OLD/'configs'/f'{i}.json').task)
        public=read(obj.public_dir/'test.json') if task==TASKS[1] else rows(obj.public_dir/'test.csv')
        ids=[r[KEYS[task]] for r in public];pub={r[KEYS[task]]:r for r in public}
        spec=obj._search_only_module.SPEC[task];p=B/spec.get('source',spec.get('view'))/'private/dsearch.csv'
        assert sha(p)==binding[str(p)];truth={r[KEYS[task]]:r for r in rows(p)}
        col='author' if task==TASKS[0] else 'requester_received_pizza' if task==TASKS[1] else 'selected_text'
        y=[truth[i][col] for i in ids]
        data[task]=obj,ids,pub,y
    def pred(task,path):
        assert sha(path)==binding[str(path)]
        lookup={r[KEYS[task]]:r for r in rows(path)};_,ids,pub,_=data[task]
        if task==TASKS[0]:return [[float(lookup[i][c]) for c in ('EAP','HPL','MWS')] for i in ids]
        if task==TASKS[1]:return [float(lookup[i]['requester_received_pizza']) for i in ids]
        return [pub[i]['text'] if pub[i]['sentiment']=='neutral' else lookup[i]['selected_text'] for i in ids]
    def score(task,p):
        y=data[task][3]
        if task==TASKS[0]:
            tiny=np.finfo(float).eps;indices={'EAP':0,'HPL':1,'MWS':2}
            clipped=[[min(1.-tiny,max(tiny,v)) for v in row] for row in p]
            return math.fsum(math.log(row[indices[t]]/sum(row)) for t,row in zip(y,clipped))/len(y)
        if task==TASKS[2]:return math.fsum(j(t,v) for t,v in zip(y,p))/len(y)
        v=np.asarray(p);positive=v[np.asarray(y)=='1'];negative=np.sort(v[np.asarray(y)=='0'])
        return float((np.searchsorted(negative,positive,'left')+np.searchsorted(negative,positive,'right')).sum()/(2*len(positive)*len(negative)))
    count=0
    expected=rows(E/'rows.csv')
    for record in read(E/'predictions-frozen.json')['records']:
        path=Path(record['path']);assert sha(path)==record['sha256'];r=read(path);task=r['task']
        sub=[x for x in expected if x['batch']==r['batch'] and int(x['episode'])==r['episode']]
        if not r['methods']:
            assert all(x['coverage']=='False' and x['gain']=='' for x in sub);continue
        ep=B/r['batch']/f'episode-{r["episode"]}'
        source=[pred(task,ep/f'action-{s}/submission.private.csv') for s in r['library_steps']]
        assert pred(task,ep/f'action-{r["selected_step"]}/submission.private.csv')==r['selected']
        assert r['selected_step']==max(int(p.parent.name.split('-')[-1]) for p in ep.glob('action-*/selected.json'))
        for row in sub:
            method=row['method'];v=r['methods'][method]
            if method=='consensus':
                reconstructed=[]
                for candidates in zip(*source):
                    best=max(range(len(candidates)),key=lambda i:math.fsum(j(candidates[i],x) for x in candidates))
                    reconstructed.append(candidates[best])
                assert reconstructed==v
            elif method=='mean':
                if task==TASKS[0]:
                    reconstructed=[[math.fsum(x[c] for x in candidates)/len(source) for c in range(3)] for candidates in zip(*source)]
                else:reconstructed=[math.fsum(x)/len(source) for x in zip(*source)]
                assert np.allclose(reconstructed,v,atol=1e-14,rtol=1e-14)
            else:
                ranks=[]
                for x in source:
                    ordered=sorted(x);rank={value:(np.searchsorted(ordered,value,'left')+np.searchsorted(ordered,value,'right')+1)/(2*len(x)) for value in set(x)}
                    ranks.append([rank[a] for a in x])
                reconstructed=[math.fsum(x)/len(ranks) for x in zip(*ranks)]
                assert np.allclose(reconstructed,v,atol=1e-14,rtol=1e-14)
            close(score(task,v),row['utility']);close(score(task,r['selected']),row['selected_utility'])
            close(float(row['utility'])-float(row['selected_utility']),row['gain']);count+=1
    save(E/'verification.json',dict(status='PASS',trajectories=48,scored_finalizers=count,
         rows_sha256=sha(E/'rows.csv'),summary_sha256=sha(E/'summary.json'),verifier_sha256=sha(Path(__file__)),
         note='independent finalizer and metric reconstruction; not independent evaluation data'))

    obj,ids,pub,y=data[TASKS[1]];train=read(obj.public_dir/'train.json')
    lengths=sorted(len((r.get('request_text_edit_aware') or '').split()) for r in train)
    cuts=[lengths[(len(lengths)-1)//3],lengths[2*(len(lengths)-1)//3]]
    group=[sum(len((pub[i].get('request_text_edit_aware') or '').split())>c for c in cuts) for i in ids]
    expected=rows(G/'rows.csv');checked=0
    for r in expected:
        cell=read(G/f'{r["index"]}.private.json');p,c,out=cell['parent'],cell['child'],cell['guard']
        # Independent equivalence-class construction: two same-group examples
        # may exchange scores iff their comparisons to ALL outsiders agree.
        sets=defaultdict(list)
        for i in range(len(p)):
            outsiders=[k for k in range(len(p)) if group[k]!=group[i]]
            signature=tuple((p[i]>p[k])-(p[i]<p[k]) for k in outsiders)
            if 0 in signature:continue
            sets[group[i],signature].append(i)
        rebuilt=list(p)
        for b in sets.values():
            for i,value in zip(sorted(b,key=lambda i:(c[i],p[i],i)),sorted(p[i] for i in b)):rebuilt[i]=value
        assert rebuilt==out and sorted(out)==sorted(p)
        assert all((p[i]>p[k])-(p[i]<p[k])==(out[i]>out[k])-(out[i]<out[k])
                   for i in range(len(p)) for k in range(i) if group[i]!=group[k])
        for name,value in (('parent',p),('child',c),('guard',out)):close(score(TASKS[1],value),r[name])
        checked+=1
    save(G/'verification.json',dict(status='PASS',guarded_candidates=checked,
         reconstruction='outsider comparison equivalence classes, independent of producer consecutive-level blocks',
         rows_sha256=sha(G/'rows.csv'),summary_sha256=sha(G/'summary.json'),verifier_sha256=sha(Path(__file__))))
    print(json.dumps(dict(ensemble=read(E/'verification.json'),rank_guard=read(G/'verification.json')),sort_keys=True))


if __name__=='__main__':main()
