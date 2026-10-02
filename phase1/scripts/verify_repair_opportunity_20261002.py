"""Second-implementation score check plus preread-frozen blending baseline.

The producer's oracle is not used to select which pairs receive the baseline.
No new model/program execution. All results remain retrospective development.
"""
import csv
import hashlib
import json
import math
import os
import statistics
from pathlib import Path

B = Path('/research/d7/spc/yzyang4')
ROOT = B / 'repair-opportunity-20261002-v1'
OUT = ROOT / 'review-v1'
EXPECTED = 'c714d7daf46ed431f87a7d0428a60a188613b7452541b932b9e7ad20dfb37139'
PIZZA = 'random-acts-of-pizza'
SPOOKY = 'spooky-author-identification'
TWEET = 'tweet-sentiment-extraction'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p): return json.loads(p.read_bytes())
def csvread(p):
    with p.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
def save(p, value):
    with p.open('x') as f: json.dump(value,f,sort_keys=True,indent=2,allow_nan=False); f.write('\n')
def close(a, b): assert math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-11), (a,b)


def pair_score(y, p):
    # All positive-negative comparisons, independent of sklearn rank AUC.
    import numpy as np
    a = np.asarray(p)[np.asarray(y) == 1]
    b = np.asarray(p)[np.asarray(y) == 0]
    if not len(a) or not len(b): return None
    return float(((a[:,None]>b[None,:])+.5*(a[:,None]==b[None,:])).mean())


def score(task, labels, pred):
    if task == PIZZA: return pair_score(labels,pred)
    if task == SPOOKY: return sum(math.log(max(float(p[y]),1e-15)) for y,p in zip(labels,pred))/len(labels)
    values=[]
    for y,p in zip(labels,pred):
        a=set(y.lower().split()); b=set(p.lower().split());values.append(len(a&b)/len(a|b) if a|b else 0.)
    return sum(values)/len(values)


def main():
    os.umask(0o077); assert sha(ROOT/'summary.json')==EXPECTED; OUT.mkdir()
    save(OUT/'plan.json',dict(source_sha256=sha(Path(__file__)), original_summary_sha256=EXPECTED,
         scope='verify all85 parents and all valid pair/group counterfactual scores; blending all valid Pizza pairs',
         fixed_baseline='probability arithmetic mean alpha0.5, not selected by results',
         additional_oracle='best global alpha in [0,.25,.5,.75,1], optimistic comparator not deployable selection',
         selection='ALL valid Pizza pairs, including manual; automatic subset separate',
         no_fit=True,gpu=0,api_calls=0,protected_opened=False))
    result=load(ROOT/'summary.json'); bindings=load(ROOT/'bindings.private.json')
    for p,h in bindings.items(): assert sha(Path(p))==h
    for name,h in result['outputs'].items(): assert sha(ROOT/name)==h
    pairs=csvread(ROOT/'pairs.csv'); groups=csvread(ROOT/'groups.csv'); assert len(pairs)==85
    imported={}; dataset={}; blend=[]; checked=0
    # Bind input tables through config and the saved hash allowlist. No new data
    # sources, metrics or partitions are searched for by outcome.
    import sys
    old=B/'task-feedback-real-20261001-v6';sys.path.insert(0,str(old))
    import task_feedback_real_20261001 as runtime
    runtime.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    from task_feedback_facts_20261001 import groups as original_groups
    for task,key in ((PIZZA,'request_id'),(SPOOKY,'id'),(TWEET,'textID')):
        idx=next(r['index'] for r in load(old/'plan.json')['schedule'] if r['task']==task)
        obj=MLEBenchTask(RunConfig.load_from_json(old/'configs'/f'{idx}.json').task)
        spec=obj._search_only_module.SPEC[task]; labelp=B/spec.get('source',spec.get('view'))/'private/dsearch.csv'
        assert str(labelp) in bindings
        label_rows=csvread(labelp);ids=[r[key] for r in label_rows]
        if task==PIZZA:
            train=load(obj.public_dir/'train.json'); public=load(obj.public_dir/'test.json');textcol='request_text_edit_aware'
            labels=[int(r['requester_received_pizza']) for r in label_rows]
        else:
            train=csvread(obj.public_dir/'train.csv');public=csvread(obj.public_dir/'test.csv');textcol='text'
            labels=[r['author' if task==SPOOKY else 'selected_text'] for r in label_rows]
        sizes=sorted(len((r.get(textcol) or '').split()) for r in train)
        cuts=[sizes[(len(sizes)-1)//3],sizes[2*(len(sizes)-1)//3]]
        bins={r[key]:sum(len((r.get(textcol) or '').split())>c for c in cuts) for r in public}
        assert (cuts,bins)==original_groups(task,obj.public_dir)
        dataset[task]=(key,ids,labels,[bins[i] for i in ids],{r[key]:r for r in public})
    def prediction(task, action):
        if str(action) in imported:return imported[str(action)]
        key,ids,labels,bins,public=dataset[task];meta=load(action/'result.json')
        if not meta['valid']:return None
        p=action/'submission.private.csv';assert str(p) in bindings
        data=csvread(p);lookup={r[key]:r for r in data};assert len(data)==len(lookup)==len(ids) and set(lookup)==set(ids)
        if task==PIZZA:values=[float(lookup[i]['requester_received_pizza']) for i in ids]
        elif task==SPOOKY:values=[{c:float(lookup[i][c]) for c in ('EAP','HPL','MWS')} for i in ids]
        else:values=[public[i]['text'] if public[i]['sentiment']=='neutral' else lookup[i]['selected_text'] for i in ids]
        imported[str(action)]=values;return values
    for pair in pairs:
        task=pair['task'];ep=B/pair['batch']/f'episode-{pair["episode"]}'
        p=prediction(task,ep/f'action-{pair["parent_step"]}');c=prediction(task,ep/f'action-{pair["step"]}')
        key,ids,y,bins,public=dataset[task];u0=score(task,y,p);close(u0,pair['parent_utility'])
        assert (c is not None)==(pair['child_valid']=='True')
        if c is None:continue
        u1=score(task,y,c);close(u1,pair['child_utility'])
        subrows=[r for r in groups if r['index']==pair['index']];assert len(subrows)==3
        swaps=[]
        for row in subrows:
            g=int(row['group']); mask=[b==g for b in bins]; mixed=[a if m else b for a,b,m in zip(c,p,mask)]
            us=score(task,y,mixed);close(us,row['swap_utility']);close(us-u0,row['swap_global_gain'])
            gy=[a for a,m in zip(y,mask) if m];gp=[a for a,m in zip(p,mask) if m];gc=[a for a,m in zip(c,mask) if m]
            l0=score(task,gy,gp);l1=score(task,gy,gc)
            if l0 is not None and l1 is not None:close(l1-l0,row['local_delta'])
            if task==PIZZA:
                # Direct cross-boundary edge changes, without subtracting the
                # producer's local term from its global term.
                import numpy as np
                ya=np.asarray(y);pa=np.asarray(p);ma=np.asarray(mixed);gm=np.asarray(mask)
                pos=np.flatnonzero(ya==1);neg=np.flatnonzero(ya==0)
                crossing=gm[pos,None] != gm[None,neg]
                before=(pa[pos,None]>pa[None,neg])+.5*(pa[pos,None]==pa[None,neg])
                after=(ma[pos,None]>ma[None,neg])+.5*(ma[pos,None]==ma[None,neg])
                external=float(((after-before)*crossing).sum()/(len(pos)*len(neg)))
                close(external,row['cross_boundary_contribution'])
            swaps.append(us);checked+=1
        close(max(swaps)-max(u0,u1),pair['oracle_beyond_both_endpoints'])
        if task==PIZZA:
            values=[score(task,y,[(1-a)*v+a*w for v,w in zip(p,c)]) for a in (0,.25,.5,.75,1)]
            ref=float(pair['strongest_historical_utility'])
            blend.append(dict(index=int(pair['index']),automatic_guidance=pair['automatic_guidance']=='True',
                              batch=pair['batch'],episode=int(pair['episode']),step=int(pair['step']),
                              parent=u0,child=u1,reference=ref,group_oracle=max(swaps),
                              fixed_half=values[2],global_grid_oracle=max(values),
                              fixed_half_vs_parent=values[2]-u0,fixed_half_vs_reference=values[2]-ref,
                              group_oracle_vs_half=max(swaps)-values[2],group_oracle_vs_grid=max(swaps)-max(values)))
    summaries={}
    for scope in ('all','automatic'):
        sub=[r for r in blend if scope=='all' or r['automatic_guidance']]
        summaries[scope]=dict(n=len(sub), half_beats_parent=sum(r['fixed_half_vs_parent']>1e-12 for r in sub),
             half_beats_reference=sum(r['fixed_half_vs_reference']>1e-12 for r in sub),
             group_oracle_beats_half=sum(r['group_oracle_vs_half']>1e-12 for r in sub),
             group_oracle_beats_grid=sum(r['group_oracle_vs_grid']>1e-12 for r in sub),
             median_half_vs_parent=statistics.median(r['fixed_half_vs_parent'] for r in sub),
             variance_half_vs_parent=statistics.variance(r['fixed_half_vs_parent'] for r in sub),
             median_group_vs_grid=statistics.median(r['group_oracle_vs_grid'] for r in sub))
    save(OUT/'verification.json',dict(status='PASS',parent_scores=len(pairs),valid_pair_scores=sum(r['child_valid']=='True' for r in pairs),
             counterfactual_groups=checked,input_bindings=len(bindings),producer_summary_sha256=EXPECTED,plan_sha256=sha(OUT/'plan.json')))
    save(OUT/'baseline.json',dict(status='RETROSPECTIVE_BASELINE_NOT_NEW_METHOD',summaries=summaries,rows=blend))
    print(json.dumps(dict(verification=load(OUT/'verification.json'),summaries=summaries,
             strong_reference_exceptions=[r for r in blend if r['automatic_guidance'] and r['group_oracle']>r['reference']+1e-12]),sort_keys=True))


if __name__=='__main__':main()
