"""Compare returned candidates to the parent actually admitted at decision time.

This is a descriptive follow-up of three fixed closed DEV cohorts, NOT an
operator intervention, label-noise estimate, or no-feedback counterfactual.
Only metadata derived from previously hash-pinned lineage sources is exported.
"""
from collections import Counter
import json
from pathlib import Path
import statistics
import closed_adaptation_lineage_20261017 as m

SPECS=(
 (18770,'scheduling-pooling-20261016-v3','adaptation-lineage-extension-20261017.safe.json','ce2df3e9c801da6c1a8e407d542f963d61c47d9fcde807c52b15c2308e14e644'),
 (18807,'scheduling-colocation-20261016-v1','adaptation-lineage-extension-20261017.safe.json','b47201384f5d3c385f471becba37bb2f546747de89a529f55d48f0ff9a264430'),
 (18997,'scheduling-selective-20261017-v1','adaptation-lineage-20261017.safe.json','6ec665d244a8cd54820542b175526975d2a13ed24a0185ddd56a7d8dd2d19698'))

def stats(values):
    return dict(n=len(values),median=statistics.median(values) if values else None,
        sample_sd=statistics.stdev(values) if len(values)>1 else None)

def evaluate(root,filename,pin):
    assert m.sha(root/filename)==pin
    original=m.load(root/filename)
    assert m.sha(root/'plan.json')==original['plan_sha256']
    def source(rel,lines=False):
        path=root/rel;expected=original['source_hashes'][rel]
        assert m.sha(path)==expected
        out=m.load(path,lines)
        assert m.sha(path)==expected
        return out
    blocks=sorted({c['block'] for c in original['candidates']})
    events={b:source(f'generation-{b}/events.jsonl',True) for b in blocks}
    starts={b:source(f'block-{b}/budget-slot.json')['start'] for b in blocks}
    warm={e['run']:e['code_sha256'] for ee in events.values() for e in ee if e['event']=='warm_start'}
    admitted={b:{e['key']:e for e in ee if e['event']=='admitted'} for b,ee in events.items()}
    used={};nodes={};receipts={}
    for b,ee in events.items():
        for e in ee:
            if e['event']=='parent_used':used.setdefault((b,e['run'],e['child']),[]).append(e)
    for c in original['candidates']:
        i,n=c['index'],c['candidate']
        if i not in nodes:nodes[i]=source(f'episode-{i}/checkpoint/journal.jsonl',True)
        receipts[i,n]=source(f'episode-{i}/candidate-{n}.json')
    rows=[]
    for c in original['candidates']:
        i,n,b=c['index'],c['candidate'],c['block'];task=c['task'];sign=-1 if task=='denoising-dirty-documents' else 1
        row={k:c[k] for k in ('index','candidate','block','task','category','valid','score','pool_elapsed')}
        f=m.lineage(nodes[i],receipts[i,n]['code_sha256'],warm[i])
        assert f['category']==c['category']
        if not f['resolved']:rows.append(row|dict(parent_resolved=False,reason='lineage_unresolved'));continue
        uu=[e for e in used.get((b,i,f['proposal']),[]) if e['parent']==f['parent']]
        if len(uu)!=1:rows.append(row|dict(parent_resolved=False,reason='ambiguous_parent_event'));continue
        a=admitted[b][uu[0]['key']];assert a['parent']==f['parent'] and a['role']=='improve'
        arc=a['snapshot']['archive'][task];p=arc[f['parent']]['metric'];assert m.finite(p)
        assert sign*p==max(sign*v['metric'] for v in arc.values()),'selected parent not greedy incumbent'
        group=next(g for g in original['groups'] if g['block']==b and g['task']==task)
        evidence='warm' if f['parent']==warm[i] and p==group['initial'] else None
        if evidence is None:
            matches=[x for x in original['candidates'] if x['block']==b and x['task']==task and x['valid']
                and receipts[x['index'],x['candidate']]['code_sha256']==f['parent']
                and abs(x['score']-p)<1e-12 and starts[b]+x['pool_elapsed']<=a['time']+.01]
            assert matches,'parent not supported by earlier pristineDEV candidate'
            evidence='earlier_pristine_dev_return'
        gain=sign*(c['score']-p) if c['valid'] else None
        relation=('better' if gain>1e-12 else 'worse' if gain < -1e-12 else 'tie') if gain is not None else 'invalid'
        rows.append(row|dict(parent_resolved=True,new_parent=f['parent']!=warm[i],parent_score=p,parent_evidence=evidence,
            parent_admitted_pool_elapsed=a['time']-starts[b],gain_vs_parent=gain,relation=relation))
    summary=[]
    for task in sorted({r['task'] for r in rows}):
        for new in (False,True):
            rr=[r for r in rows if r['task']==task and r['parent_resolved'] and r['new_parent']==new]
            summary.append(dict(task=task,new_parent=new,returned=len(rr),relations=dict(Counter(r['relation'] for r in rr)),
                valid_gain=stats([r['gain_vs_parent'] for r in rr if r['valid']]),
                parent_admission_seconds=stats([r['parent_admitted_pool_elapsed'] for r in rr])))
    return dict(lineage_sha256=pin,source_reader_sha256=m.sha(m.__file__),rows=rows,summary=summary,
        unresolved=sum(not r['parent_resolved'] for r in rows))

def main():
    for job,name,file,pin in SPECS:
        root=Path('/research/d7/spc/yzyang4')/name
        dest=root/'parent-delta-20261017.safe.json'
        if dest.exists():raise FileExistsError('diagnostic already exists')
        result=evaluate(root,file,pin)|dict(job=job,reader_sha256=m.sha(__file__),
            limits=['Post-hoc actual-parent association only. Warm/new parents have different quality and opportunity; no causal comparison.',
                   'Returned candidates only; attempts without a receipt remain censored. No denominator excludes invalid returned candidates.',
                   'Journal and earlier external-score joins checked, not independently re-extracted. No new scoring/model/GPU.'])
        with dest.open('x') as f:json.dump(result,f,indent=2,sort_keys=True,allow_nan=False)
        print(json.dumps(dict(job=job,sha256=m.sha(dest),returned=len(result['rows']),unresolved=result['unresolved'],summary=result['summary'])),flush=True)

if __name__=='__main__':main()
