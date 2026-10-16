"""Observed application-level stranded permits, not a policy value replay.

Only numeric request metadata is retained. Histories, generation durations and
scores are not replayed into an invented alternative trajectory.
"""
import collections
import hashlib
import json
from pathlib import Path

ROOT=Path('/research/d7/spc/yzyang4/scheduling-colocation-20261016-v1')
PIN='36ce5852b26de2299755c19a8b9711a1f4161d68abd25a3de6cc7687cdde8560'
TASKS=('aerial-cactus-identification','denoising-dirty-documents')

def numeric_events(path):
    out=[]
    for line in path.read_text().splitlines():
        e=json.loads(line);kind=e['event']
        if kind not in ('queued','admitted','released','cancelled'):continue
        item=e['request'] if kind=='queued' else e
        row=dict(time=e['time'],kind=kind,key=item['key'])
        if kind=='queued':row['task']=TASKS.index(item['task'])
        out.append(row)
    return out

def audit(events,start,end):
    waiting={};active={};seen=set();intervals=collections.defaultdict(float);last=start
    for e in events+[dict(time=end,kind='end')]:
        t=e['time'];assert start<=t<=end and t>=last
        wa=[sum(v==i for v in waiting.values()) for i in (0,1)]
        ac=[sum(v==i for v in active.values()) for i in (0,1)]
        assert all(n<=2 for n in ac)
        intervals[tuple(ac+wa)]+=t-last;last=t
        if e['kind']=='end':break
        k=e['key']
        if e['kind']=='queued':assert k not in seen;seen.add(k);waiting[k]=e['task']
        elif e['kind']=='admitted':assert k in waiting;active[k]=waiting.pop(k)
        elif e['kind']=='released':assert k in active;active.pop(k)
        else:assert e['kind']=='cancelled' and k in waiting;waiting.pop(k)
    assert not waiting and not active
    states=[dict(active=list(k[:2]),waiting=list(k[2:]),seconds=v) for k,v in sorted(intervals.items())]
    wall=slots=wait=0.0
    for r in states:
        a,w,dt=r['active'],r['waiting'],r['seconds'];wait+=sum(w)*dt
        spare=4-sum(a);blocked=sum(w[i] for i in (0,1) if a[i]==2)
        if spare>0 and blocked>0:
            wall+=dt;slots+=min(spare,blocked)*dt
    assert abs(sum(r['seconds'] for r in states)-(end-start))<1e-4
    return dict(reserved_seconds=end-start,waiting_seconds=wait,borrowable_wall_seconds=wall,
        borrowable_permit_seconds=slots,states=states)

def main():
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    assert sha(ROOT/'plan.json')==PIN
    assert json.loads((ROOT/'readout-20261016-v1/summary.json').read_text())['complete']==32
    rows=[]
    for b in range(4):
        p=ROOT/f'generation-{b}/events.jsonl';w=json.loads((ROOT/f'block-{b}/budget-slot.json').read_text())
        rows.append(dict(block=b,events_sha256=sha(p),**audit(numeric_events(p),w['start'],w['start']+w['actual_seconds'])))
    result=dict(plan_sha256=PIN,reader_sha256=sha(Path(__file__)),pools=rows,
        boundary='Observed resource states only; borrowable means a queued task held its2permits while fewer than4total were active. Not saved time, server capacity, causal quality gain or a changed experiment. No code/labels/predictions/model/GPU calls. Binned states omit candidate identities and order.')
    with (ROOT/'quota-borrowing-20261017-v1.safe.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(dict(result,pools=[{k:v for k,v in r.items() if k!='states'} for r in rows])))

if __name__=='__main__':main()
