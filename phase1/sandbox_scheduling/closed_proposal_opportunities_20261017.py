"""All admitted Improve decisions, including no-return and Debug descendants.

Fixed diagnostic bins are 300s execution-budget multiples, chosen before output.
This is a census of actual decisions, not restart or scheduling counterfactuals.
"""
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import statistics
import closed_adaptation_lineage_20261017 as m
from closed_prompt_contract_20261017 import ALL

def band(seconds):
    assert seconds>=0
    return 'under300' if seconds<300 else '300to600' if seconds<600 else '600to900' if seconds<900 else 'atleast900'

def stats(xs):
    return dict(n=len(xs),median=statistics.median(xs) if xs else None,
        sample_sd=statistics.stdev(xs) if len(xs)>1 else None)

def summarize(rows):
    return dict(admitted=len(rows),generated=sum(r['generated'] for r in rows),
        any_return=sum(bool(r['returns']) for r in rows),valid_family=sum(r['has_valid_return'] for r in rows),
        improving_family=sum(r['improved_parent'] for r in rows),
        returning_descendants=sum(len(r['returns']) for r in rows),
        remaining_at_admission=stats([r['remaining_seconds'] for r in rows]),
        return_states=dict(Counter('no_return' if not r['returns'] else 'all_invalid' if not r['has_valid_return'] else 'improved' if r['improved_parent'] else 'valid_no_improvement' for r in rows)))

def extract(root,file,pin):
    assert m.sha(root/file)==pin;origin=m.load(root/file)
    assert m.sha(root/'plan.json')==origin['plan_sha256'];plan=m.load(root/'plan.json');duration=plan['run_seconds']
    def source(rel,lines=False):
        p=root/rel;assert m.sha(p)==origin['source_hashes'][rel]
        v=m.load(p,lines);assert m.sha(p)==origin['source_hashes'][rel];return v
    groups={(g['block'],g['task']):g for g in origin['groups']}
    run_task={c['index']:c['task'] for c in origin['candidates']};assert len(run_task)==origin['assigned']
    start={i:datetime.fromisoformat(source(f'episode-{i}/deadline.json')['started_utc']).timestamp() for i in run_task}
    events={b:source(f'generation-{b}/events.jsonl',True) for b in sorted({c['block'] for c in origin['candidates']})}
    slots={b:source(f'block-{b}/budget-slot.json')['start'] for b in events}
    warm={e['run']:e['code_sha256'] for ee in events.values() for e in ee if e['event']=='warm_start'}
    families={};used={};index={}
    for b,ee in events.items():
        for e in ee:
            if e['event']=='admitted' and e['role']=='improve':
                k=(b,e['key']);assert k not in families;i=e['run'];task=run_task[i]
                p=e['snapshot']['archive'][task][e['parent']]['metric'];sign=-1 if task=='denoising-dirty-documents' else 1
                assert sign*p==max(sign*x['metric'] for x in e['snapshot']['archive'][task].values())
                elapsed=e['time']-start[i];assert 0<=elapsed<duration
                ordinal=len(index);index[k]=ordinal
                families[k]=dict(ordinal=ordinal,index=i,block=b,task=task,arm=groups[b,task]['pool_mode'],
                    request_key=e['key'],new_parent=e['parent']!=warm[i],parent_score=p,
                    admitted_run_elapsed=elapsed,remaining_seconds=duration-elapsed,remaining_band=band(duration-elapsed),
                    generated=False,returns=[],parent_hash_private=e['parent'])
            elif e['event']=='parent_used':
                k=(b,e['key']);assert k in families and e['parent']==families[k]['parent_hash_private']
                assert not families[k]['generated'];families[k]['generated']=True
                used.setdefault((b,e['run'],e['child'],e['parent']),[]).append(k)
    nodes={i:source(f'episode-{i}/checkpoint/journal.jsonl',True) for i in run_task};unresolved=[]
    for c in origin['candidates']:
        i,n,b=c['index'],c['candidate'],c['block'];receipt=source(f'episode-{i}/candidate-{n}.json')
        f=m.lineage(nodes[i],receipt['code_sha256'],warm[i]);keys=used.get((b,i,f.get('proposal'),f.get('parent')),[])
        if not f['resolved'] or len(keys)!=1:
            unresolved.append(dict(index=i,candidate=n,reason='unresolved_lineage_or_admission'));continue
        r=families[keys[0]];assert r['new_parent']==c['category'].endswith('_from_new')
        assert c['pool_elapsed']+slots[b]>=start[i]+r['admitted_run_elapsed']
        sign=-1 if c['task']=='denoising-dirty-documents' else 1
        gain=sign*(c['score']-r['parent_score']) if c['valid'] else None
        r['returns'].append(dict(candidate=n,category=c['category'],valid=c['valid'],score=c['score'],gain_vs_parent=gain))
    rows=[]
    for r in families.values():
        del r['parent_hash_private']
        gains=[c['gain_vs_parent'] for c in r['returns'] if c['valid']]
        rows.append(r|dict(has_valid_return=bool(gains),best_gain_vs_parent=max(gains) if gains else None,
            improved_parent=bool(gains and max(gains)>1e-12)))
    assert sum(len(r['returns']) for r in rows)+len(unresolved)==len(origin['candidates'])
    summary=[]
    for task in sorted(set(run_task.values())):
        for new in (False,True):
            rr=[r for r in rows if r['task']==task and r['new_parent']==new]
            summary.append(dict(task=task,new_parent=new,**summarize(rr),
                by_remaining=[dict(band=b,**summarize([r for r in rr if r['remaining_band']==b])) for b in ('under300','300to600','600to900','atleast900')]))
    return dict(lineage_sha256=pin,run_seconds=duration,source_reader_sha256=m.sha(m.__file__),
        assigned=origin['assigned'],all_admitted_improve=len(rows),matched_returns=sum(len(r['returns']) for r in rows),
        unresolved_returns=unresolved,rows=rows,summary=summary)

def main():
    for job,name,file,pin in ALL:
        root=Path('/research/d7/spc/yzyang4')/name;dest=root/'proposal-opportunities-20261017.safe.json'
        assert not dest.exists()
        out=extract(root,file,pin)|dict(job=job,reader_sha256=m.sha(__file__),
            limits=['Actual post-treatment parent states, not causal adaptive/restart comparison.',
                    'All admitted Improve requests included; queued requests never admitted are outside this decision denominator.',
                    'No-return includes generation/continuation/deadline censoring; it is not an invented bad score.',
                    '300s bands are execution-budget multiples, not enough-time certificates for generation plus execution plus analysis.',
                    'Unresolved returned ancestry retained separately; do not silently turn unknown families into known failures.'])
        with dest.open('x') as f:json.dump(out,f,indent=2,sort_keys=True,allow_nan=False)
        print(json.dumps(dict(job=job,sha256=m.sha(dest),admitted=out['all_admitted_improve'],
            matched_returns=out['matched_returns'],unresolved=len(out['unresolved_returns']),summary=out['summary'])),flush=True)

if __name__=='__main__':main()
