"""Closed old development trajectories; descriptive headroom, no new scoring."""
import hashlib,json,math,statistics
from pathlib import Path
B=Path('/research/d7/spc/yzyang4')
ROOTS={
 'task-feedback-real-20261001-v6':'15751d3b52bdc42617df02006ce724635f4bf49df6e477686769fd1979d53403',
 'task-feedback-upper-20261002-v1':'9fe231e1b9e2da8cb51fadb7ff9844b074c10e8e3dc64d1d1f3be170fb0703a0',
 'task-feedback-local-edit-20261002-v1':'7bd84ff0e867043b2787d5c07af867eff50370f4e7b6bafa811ef215196c4139'}
REF=B/'repair-opportunity-20261002-v1/summary.json'
REF_SHA='c714d7daf46ed431f87a7d0428a60a188613b7452541b932b9e7ad20dfb37139'
HASHES={}
def read(p):
    raw=p.read_bytes();HASHES[str(p.relative_to(B))]=hashlib.sha256(raw).hexdigest()
    return json.loads(raw)
def stats(v):return dict(n=len(v),median=statistics.median(v) if v else None,sample_variance=statistics.variance(v) if len(v)>1 else None)
def census():
    refs=read(REF)['references'];assert HASHES[str(REF.relative_to(B))]==REF_SHA
    rows=[]
    for name,h in ROOTS.items():
        r=B/name;p=read(r/'plan.json');assert HASHES[str((r/'plan.json').relative_to(B))]==h
        assert (r/'all-closed.json').is_file()
        for s in p['schedule']:
            ep=r/f'episode-{s["index"]}';assert (ep/'closed.json').is_file()
            task=s['task'];sign=-1 if task=='spooky-author-identification' else 1
            all_results=[read(a/'result.json') for a in sorted(ep.glob('action-*'),key=lambda x:int(x.name.split('-')[-1])) if (a/'result.json').is_file()]
            initial=next((x for x in all_results if x['step']==0 and x['valid']),None)
            valid=[x for x in all_results if x['valid']]
            assert all(math.isfinite(x['metric']) and x['exit_code']==0 and not x['timed_out'] for x in valid)
            # Independent max-utility accumulation vs declared metric direction.
            maximum=None
            for a in all_results:
                if a['valid']:maximum=sign*a['metric'] if maximum is None else max(maximum,sign*a['metric'])
            best=(min if sign==-1 else max)([a['metric'] for a in valid]) if valid else None
            assert maximum==(sign*best if best is not None else None)
            gain=sign*(best-initial['metric']) if initial else None
            better=[a for a in valid if initial and a['step']>0 and sign*(a['metric']-initial['metric'])>1e-12]
            # Tweet has a later neutral rule; do not mix that reference with raw scores.
            comparable_reference=task!='tweet-sentiment-extraction'
            ref=refs[task]['utility'] if comparable_reference else None
            rows.append(dict(batch=name,index=s['index'],task=task,arm=s['arm'],seed=s['seed'],
                automatic=(name.endswith('20261001-v6') or ('upper' in name and s['arm'] in ('A','B'))),
                initial_metric=initial['metric'] if initial else None,selected_metric=best,gain_from_own_initial=gain,
                improved_actions=len(better),valid_new_actions=sum(a['step']>0 for a in valid),
                initial_code_sha256=initial.get('executed_code_sha256') if initial else None,
                strong_reference_utility=ref,
                own_initial_gap_to_strong=ref-sign*initial['metric'] if ref is not None and initial else None,
                selected_gap_to_strong=ref-sign*best if ref is not None and best is not None else None))
    assert len(rows)==48
    groups={}
    for task in sorted({x['task'] for x in rows}):
        for auto in (True,False):
            rr=[x for x in rows if x['task']==task and x['automatic']==auto]
            vv=[x for x in rr if x['gain_from_own_initial'] is not None]
            groups[f'{task}:{"automatic" if auto else "manual"}']=dict(assigned=len(rr),valid_initial=len(vv),
                improved_trajectories=sum(x['gain_from_own_initial']>1e-12 for x in vv),
                improved_actions=sum(x['improved_actions'] for x in rr),valid_new_actions=sum(x['valid_new_actions'] for x in rr),
                distinct_initial_code_hashes=len({x['initial_code_sha256'] for x in vv if x['initial_code_sha256']}),
                gains=stats([x['gain_from_own_initial'] for x in vv]),
                initial_gap_to_strong=stats([x['own_initial_gap_to_strong'] for x in vv if x['own_initial_gap_to_strong'] is not None]),
                selected_gap_to_strong=stats([x['selected_gap_to_strong'] for x in rr if x['selected_gap_to_strong'] is not None]))
    print(json.dumps(dict(status='DESCRIPTIVE_NOT_COUNTERFACTUAL',rows=rows,groups=groups,input_hashes=HASHES,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        limitations='Old adaptive development scores; strong reference is historically selected. No matching of program, prompt, budget, generator seed or timestamp across batches. Cannot infer causal headroom effect. Tweet global comparator omitted because of later neutral rule. No new labels, prediction values, training or GPU.'),sort_keys=True))
if __name__=='__main__':census()
