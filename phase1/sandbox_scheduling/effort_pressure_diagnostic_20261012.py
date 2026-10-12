"""Secondary closed-batch queue accounting, frozen before any new quality read.

Measures host permits, NOT GPU busy time or a counterfactual speedup. It does not
inspect candidate contents, labels, predictions or metric fields. No fitting,
new job, parameter choice, or change to the primary experiment's quality gate.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path


def read(p):
    return json.loads(Path(p).read_text())


def structural_events(path, generation):
    out=[]
    for line in Path(path).read_text().splitlines():
        e=json.loads(line)
        # Deliberately discard all archive, score and candidate identity fields.
        if e['event'] not in ('queued','admitted','released','cancelled','queue_cancelled'):
            continue
        kind='cancelled' if e['event']=='queue_cancelled' else e['event']
        key=e['request']['key'] if generation and kind=='queued' else e['key']
        out.append(dict(time=float(e['time']),kind=kind,key=key))
    return out


def state_changes(events, limit):
    queue=set();active=set();done=set();changes=[];wait={};held={};counts=collections.Counter()
    previous=float('-inf');waiting_seconds=holding_seconds=0.0
    for e in events:
        t,k,kind=e['time'],e['key'],e['kind']
        if t<previous:raise ValueError('nonmonotonic event clock')
        previous=t
        if kind=='queued':
            if k in queue|active|done:raise ValueError('duplicate key')
            queue.add(k);wait[k]=t
        elif kind=='admitted':
            if k not in queue or len(active)>=limit:raise ValueError('invalid admission')
            queue.remove(k);active.add(k);held[k]=t;waiting_seconds+=t-wait.pop(k)
        elif kind=='released':
            if k not in active:raise ValueError('unknown release')
            active.remove(k);done.add(k);holding_seconds+=t-held.pop(k)
        elif kind=='cancelled':
            if k not in queue:raise ValueError('unknown cancellation')
            queue.remove(k);done.add(k);waiting_seconds+=t-wait.pop(k)
        else:raise ValueError('unknown event')
        counts[kind]+=1;changes.append((t,len(queue),len(active)))
    if queue or active:raise ValueError('unclosed permits')
    return changes,dict(counts=counts,waiting_seconds=waiting_seconds,holding_seconds=holding_seconds)


def integrate(streams,start,end):
    if end<=start:raise ValueError('invalid interval')
    points=[]
    for i,stream in enumerate(streams):
        for t,q,a in stream:
            if t<start-0.01 or t>end+0.01:raise ValueError('event outside reserved pool')
            points.append((max(start,min(end,t)),i,q,a))
    # Zero-duration simultaneous transitions contribute no artificial overlap.
    # Preserve the original order within a stream when timestamps coincide.
    # Sorting q/a values would invent a different state after a zero-time step.
    points.sort(key=lambda p:(p[0],p[1]));state=[(0,0)]*len(streams);last=start;totals=collections.Counter()
    def account(dt):
        gq,ga=state[0];eq=sum(v[0] for v in state[1:]);ea=sum(v[1] for v in state[1:])
        totals['generation_queued_seconds']+=gq*dt
        totals['generation_held_seconds']+=ga*dt
        totals['execution_queued_seconds']+=eq*dt
        totals['execution_held_seconds']+=ea*dt
        totals['generation_full_seconds']+=(ga==4)*dt
        totals['execution_full_seconds']+=(ea==4)*dt
        label='both' if ga and ea else 'generation_only' if ga else 'execution_only' if ea else 'neither'
        totals[label+'_seconds']+=dt
    for t,i,q,a in points:
        account(t-last);state[i]=(q,a);last=t
    account(end-last)
    assert abs(sum(totals[k+'_seconds'] for k in ('both','generation_only','execution_only','neither'))-(end-start))<1e-6
    return dict(totals)


def analyze(root,out):
    root=Path(root);plan=read(root/'plan.json');closed=read(root/'closed.json');pools=[]
    assert plan['source_commit'] in ('3f119700a84d5975acef8bcff9949e188c60aefc','1cd338f86dac1381795c0295abcefefc8391df8d')
    # Closed-only secondary output. Incomplete/unattempted pools are not imputed.
    for b in range(6):
        bd=root/f'block-{b}';budget=bd/'budget-slot.json'
        if not budget.exists():
            pools.append(dict(block=b,complete=False));continue
        window=read(budget);streams=[];audits=[]
        paths=[(root/f'generation-{b}/events.jsonl',True,4)]+[(root/f'queue-{b}-{lane}/events.jsonl',False,1) for lane in range(4)]
        for file,generation,limit in paths:
            changes,audit=state_changes(structural_events(file,generation),limit)
            streams.append(changes);audits.append(audit)
        numbers=integrate(streams,window['start'],window['start']+window['actual_seconds'])
        for prefix,selection in [('generation',audits[:1]),('execution',audits[1:])]:
            for name,target in [('waiting','queued'),('holding','held')]:
                assert abs(sum(a[name+'_seconds'] for a in selection)-numbers[prefix+'_'+target+'_seconds'])<1e-4
        roles=collections.defaultdict(lambda:dict(calls=0,returned=0,seconds=0.0,thinking_calls=0))
        for row in plan['schedule']:
            if row['block']!=b:continue
            file=root/f"episode-{row['index']}/effort.jsonl"
            if not file.exists():continue
            for line in file.read_text().splitlines():
                e=json.loads(line);r=roles[e['role']];r['calls']+=1;r['returned']+=int(e['success']);r['seconds']+=e['seconds'];r['thinking_calls']+=int(e['enable_thinking'])
        pools.append(dict(block=b,arm=next(r['arm'] for r in plan['schedule'] if r['block']==b),complete=True,
                          reserved_seconds=window['actual_seconds'],timing=numbers,roles=dict(roles),event_audits=audits))
    result=dict(source_commit=plan['source_commit'],plan_sha256=hashlib.sha256((root/'plan.json').read_bytes()).hexdigest(),
                script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),pools=pools,
                closed_runs=closed['complete'],secondary=True,
                limitations=['Host permits include non-kernel work; these are not GPU utilization or saved compute.',
                             'Role latencies overlap; their sum is not wall-clock cost.',
                             'Finite closed-loop workload, not stationary throughput; no new quality gate or automatic expansion.',
                             'Queue changes do not establish a causal mechanism without an additional intervention.'])
    with Path(out).open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(result,allow_nan=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root');ap.add_argument('out');a=ap.parse_args();analyze(a.root,a.out)
