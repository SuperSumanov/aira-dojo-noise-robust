"""Locate time in actual admitted proposal families, not a scheduling replay.

All requests included; returned-only timing is explicitly conditional. A parent
is chosen at admission, so deleting its wait need not preserve that parent.
No old outcomes are recomputed and no policy threshold is fitted here.
"""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import statistics
from independent_admission_timing_20261017 import SPECS, read


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def stats(xs):
    return dict(n=len(xs), median=statistics.median(xs) if xs else None,
                sample_sd=statistics.stdev(xs) if len(xs)>1 else None)


def extract(root, lineage_file, proposal_pin):
    p=read(root/'proposal-opportunities-20261017.safe.json',proposal_pin)
    l=read(root/lineage_file,p['lineage_sha256'])
    def source(rel,lines=False):
        return read(root/rel,l['source_hashes'][rel],lines)
    candidates={(c['index'],c['candidate']):c for c in l['candidates']}
    rows=[]
    for block in sorted({r['block'] for r in p['rows']}):
        events=source(f'generation-{block}/events.jsonl',True)
        queued={};admitted={};generated={};released={}
        for e in events:
            kind=e['event']
            if kind=='queued':
                key=e['request']['key'];assert key not in queued
                queued[key]=e['request']['requested']
            elif kind in ('admitted','parent_used','released'):
                target={'admitted':admitted,'parent_used':generated,'released':released}[kind]
                assert e['key'] not in target
                target[e['key']]=e['time']
        slot=source(f'block-{block}/budget-slot.json')['start']
        for r in (x for x in p['rows'] if x['block']==block):
            key=r['request_key'];a=admitted[key]
            start=datetime.fromisoformat(source(f'episode-{r["index"]}/deadline.json')['started_utc']).timestamp()
            assert abs(a-start-r['admitted_run_elapsed'])<1e-6
            assert key in queued and key in released
            assert queued[key]<=a<=released[key]
            assert (key in generated)==r['generated']
            g=generated.get(key)
            if g is not None:assert a<=g<=released[key]
            returns=[candidates[r['index'],c['candidate']]['pool_elapsed']+slot for c in r['returns']]
            if returns:assert g is not None and min(returns)>=g
            rows.append(dict(index=r['index'],block=block,request_key=key,task=r['task'],arm=r['arm'],
                new_parent=r['new_parent'],generated=r['generated'],returned_family=bool(returns),
                remaining_seconds=r['remaining_seconds'],wait_seconds=a-queued[key],
                admitted_to_release_seconds=released[key]-a,
                admitted_to_code_seconds=g-a if g is not None else None,
                code_to_first_return_seconds=min(returns)-g if returns else None,
                admitted_to_first_return_seconds=min(returns)-a if returns else None))
    assert len(rows)==p['all_admitted_improve']
    return dict(proposal_sha256=proposal_pin,lineage_sha256=p['lineage_sha256'],rows=rows)


def summarize(rows):
    keys=('wait_seconds','remaining_seconds','admitted_to_release_seconds','admitted_to_code_seconds',
          'code_to_first_return_seconds','admitted_to_first_return_seconds')
    return dict(admitted=len(rows),generated=sum(r['generated'] for r in rows),
                returned_families=sum(r['returned_family'] for r in rows),
                timings={k:stats([r[k] for r in rows if r[k] is not None]) for k in keys})


def main():
    cohorts=[];allrows=[]
    for job,name,file,pin in SPECS[:3]:
        result=extract(Path('/research/d7/spc/yzyang4')/name,file,pin)
        cohorts.append(dict(job=job,**result));allrows.extend(result['rows'])
    out=dict(reader_sha256=sha(__file__),timing_helper_sha256=sha(Path(__file__).with_name('independent_admission_timing_20261017.py')),
        cohorts=cohorts,summary=[dict(new_parent=new,**summarize([r for r in allrows if r['new_parent']==new])) for new in (False,True)],
        by_task=[dict(task=task,**summarize([r for r in allrows if r['new_parent'] and r['task']==task])) for task in sorted({r['task'] for r in allrows})],
        limits=['Observed admitted requests only. Queue cancellations never admitted are outside this denominator.',
                'Code completion is the parent_used client event, not exact server latency; release may follow generation failure/cancellation.',
                'Return-time distributions condition on linked returns and include execution, waiting, and possible Debug descendants.',
                'Parent is selected at admission. Deleting wait can change parent and later trajectory; no saved-time/quality counterfactual.',
                'Warm/new parent comparisons also differ in quality and remaining time. No fitted threshold or original gate changes.'])
    dest=Path(__file__).with_name('opportunity-latency-20261017.safe.json')
    with dest.open('x') as f:json.dump(out,f,indent=2,sort_keys=True,allow_nan=False)
    print(json.dumps(dict(sha256=sha(dest),summary=out['summary'],by_task=out['by_task']),sort_keys=True))


if __name__=='__main__':main()
