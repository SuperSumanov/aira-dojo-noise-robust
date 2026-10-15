"""Fixed observed non-execution gaps, endogenous ready times; CPU sensitivity.

This is NOT a closed-loop model simulation. Code, durations, and generation/
coordination gaps are frozen from completed historical requests. No new work or
quality is invented; censored cancellations remain explicitly unidentified.
"""
import argparse
import collections
import hashlib
import heapq
import json
from pathlib import Path
import statistics

def chains(jobs):
    grouped=collections.defaultdict(list)
    for i,j in enumerate(jobs):grouped[j['session']].append(dict(j,index=i))
    for rows in grouped.values():
        rows.sort(key=lambda x:x['arrival'])
        for k,j in enumerate(rows):
            assert j['duration']>=0 and j['original_start']>=j['arrival']-1e-8
            j['gap']=j['arrival'] if not k else j['arrival']-rows[k-1]['original_start']-rows[k-1]['duration']
            assert j['gap']>=0, 'Concurrent work within a session cannot use this serial model'
    return dict(grouped)

def simulate(jobs,mode,overhead=0):
    assert mode in ('fixed','shared','unlimited') and overhead>=0
    groups=chains(jobs);future=[];running=[];waiting=[];out=[];busy={}
    for sid,rows in groups.items():heapq.heappush(future,(rows[0]['gap'],sid,0))
    t=0.
    while future or running or waiting:
        nxt=min(future[0][0] if future else float('inf'),running[0][0] if running else float('inf'))
        if nxt==float('inf'):raise AssertionError('Undispatchable waiting requests')
        t=max(t,nxt)
        while running and running[0][0]<=t:
            end,sid,k,device=heapq.heappop(running);del busy[device]
            if k+1<len(groups[sid]):heapq.heappush(future,(end+groups[sid][k+1]['gap'],sid,k+1))
        while future and future[0][0]<=t:waiting.append(heapq.heappop(future))
        waiting.sort()
        while waiting:
            chosen=None
            for at,(arrival,sid,k) in enumerate(waiting):
                j=groups[sid][k]
                eligible=[sid] if mode=='unlimited' else ([j['lane']] if mode=='fixed' else range(4))
                free=[d for d in eligible if d not in busy]
                if free:chosen=(at,min(free));break
                if mode=='shared':break
            if chosen is None:break
            at,device=chosen;arrival,sid,k=waiting.pop(at);j=groups[sid][k]
            end=t+j['duration']+overhead;busy[device]=j['index']
            heapq.heappush(running,(end,sid,k,device))
            out.append(dict(index=j['index'],session=sid,task=j['task'],ready=arrival,
                start=t,end=end,wait=t-arrival,by_deadline=end<=j['deadline']))
    assert len(out)==len(jobs)
    return sorted(out,key=lambda x:x['index'])

def summary(rows):
    return dict(known_requests=len(rows),released_by_deadline=sum(r['by_deadline'] for r in rows),
        wait_seconds=sum(r['wait'] for r in rows),
        task_counts={str(task):sum(r['by_deadline'] for r in rows if r['task']==task) for task in (0,1)})

def main(files,out):
    result=dict(kind='fixed_observed_gap_dependency_sensitivity',quality_claim=False,new_gpu_jobs=0,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),sources=[],
        limitations=['Only known historical requests; cancelled durations unknown and never imputed.',
            'Conditional model: fixed non-execution gaps include historical model queue/analysis delays. Changed service load and prompts are not simulated.',
            'Unlimited execution is an optimistic envelope only conditional on the frozen jobs/gaps, not a real-world quality or throughput bound.',
            'Release includes cleanup and may include interrupted execution. An on-time release is NOT valid feedback, a completed training run, or improvement.',
            'No extra unobserved tail requests, scores, or candidates invented. This does not change the current GPU protocol or quality gate.'])
    for file in files:
        raw=Path(file).read_bytes();d=json.loads(raw);pools=[]
        assert d['quality_claim'] is False
        for p in d['pools']:
            jobs=p['jobs'];groups=chains(jobs)
            observed=sum(j['original_start']+j['duration']<=j['deadline'] for j in jobs)
            modes={m:simulate(jobs,m) for m in ('fixed','shared','unlimited')}
            # Unlimited conditional timings have an independent analytic formula.
            for rows in groups.values():
                end=0.
                for j in rows:
                    end+=j['gap']+j['duration']
                    assert abs(modes['unlimited'][j['index']]['end']-end)<1e-7
            delays=[j['gap'] for rows in groups.values() for j in rows[1:]]
            pools.append(dict(block=p['block'],arm=p['arm'],known_requests=len(jobs),
                unknown_cancelled=len(p['cancelled']),observed_released_by_deadline=observed,
                median_nonexecution_gap=statistics.median(delays) if delays else None,
                baseline_max_end_deviation=max(abs(modes['fixed'][i]['end']-j['original_start']-j['duration']) for i,j in enumerate(jobs)),
                scenarios={m:summary(r) for m,r in modes.items()},
                shared_overhead=[dict(seconds=x,**summary(simulate(jobs,'shared',x))) for x in (5,15,30)]))
        result['sources'].append(dict(file=Path(file).name,sha256=hashlib.sha256(raw).hexdigest(),pools=pools))
    with Path(out).open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(result,allow_nan=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('files',nargs=2);p.add_argument('out');a=p.parse_args();main(a.files,a.out)
