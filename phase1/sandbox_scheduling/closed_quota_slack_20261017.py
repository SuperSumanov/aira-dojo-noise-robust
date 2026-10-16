"""Closed18807 observed borrowable queue intervals, stratified by deadline slack.

No changed histories, additional completions, speedup or quality are inferred.
The thresholds describe remaining wall time, not a fitted latency predictor.
"""
from datetime import datetime
import hashlib,json,math
from pathlib import Path
from closed_quota_borrowing_20261017 import ROOT,PIN,TASKS

HORIZONS=(0,60,300,600)
ROLES=('draft','improve','debug','analyze')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())

def measure(segment,horizon):
    dt=segment['seconds'];spare=segment['spare']
    assert dt>=0 and 1<=spare<=4 and horizon>=0
    lengths=[max(0,min(dt,r['slack_at_start']-horizon)) for r in segment['blocked']]
    points=sorted(set([0]+lengths));permits=0.
    for a,b in zip(points,points[1:]):
        permits+=(b-a)*min(spare,sum(x>a for x in lengths))
    return dict(wall=max(lengths,default=0),permits=permits,requests=sum(lengths))

def segments(events,deadlines,start,end):
    waiting={};active={};seen=set();out=[];last=start
    for e in events+[dict(event='end',time=end)]:
        t=e['time'];assert math.isfinite(t) and start<=last<=t<=end
        counts=[sum(r['task']==i for r in active.values()) for i in (0,1)]
        assert all(n<=2 for n in counts)
        spare=4-len(active)
        blocked=[r for r in waiting.values() if counts[r['task']]==2]
        if spare and blocked and t>last:
            out.append(dict(seconds=t-last,spare=spare,blocked=[dict(task=r['task'],role=r['role'],
                slack_at_start=deadlines[r['run']]-last) for r in blocked]))
        last=t;kind=e['event']
        if kind=='end':break
        if kind=='queued':
            r=e['request'];k=r['key'];assert k not in seen and r['run'] in deadlines and r['role'] in ROLES
            seen.add(k);waiting[k]=r
        elif kind=='admitted':k=e['key'];assert k in waiting;active[k]=waiting.pop(k)
        elif kind=='released':assert e['key'] in active;active.pop(e['key'])
        elif kind=='cancelled':assert e['key'] in waiting;waiting.pop(e['key'])
        else:raise ValueError('unexpected structural event')
    assert not waiting and not active
    return out

def summarize(parts):
    by=[]
    for h in HORIZONS:
        values=[measure(s,h) for s in parts]
        roles={}
        for role in ROLES:
            roles[role]=sum(measure(dict(s,blocked=[r for r in s['blocked'] if r['role']==role]),h)['requests'] for s in parts)
        by.append(dict(minimum_remaining_seconds=h,**{k:sum(r[k] for r in values) for k in ('wall','permits','requests')},request_seconds_by_role=roles))
    return by

def main():
    assert sha(ROOT/'plan.json')==PIN
    assert read(ROOT/'readout-20261016-v1/summary.json')['complete']==32
    prior=read(ROOT/'quota-borrowing-20261017-v1.safe.json');sources={};rows=[]
    def tracked(p):
        before=sha(p);value=read(p);assert sha(p)==before;sources[str(p.relative_to(ROOT))]=before;return value
    for b in range(4):
        slot=tracked(ROOT/f'block-{b}/budget-slot.json');deadlines={}
        for i in range(8*b,8*b+8):
            d=tracked(ROOT/f'episode-{i}/deadline.json');assert d['budget_seconds']==1020 and not d['cleanup_is_score_time']
            deadlines[i]=datetime.fromisoformat(d['started_utc']).timestamp()+1020
        f=ROOT/f'generation-{b}/events.jsonl';before=sha(f);events=[]
        for line in f.read_text().splitlines():
            e=json.loads(line);kind=e['event']
            if kind not in ('queued','admitted','released','cancelled'):continue
            r={k:e[k] for k in ('event','time','key') if k in e}
            if kind=='queued':
                q=e['request'];r['request']={k:q[k] for k in ('key','role','run')};r['request']['task']=TASKS.index(q['task'])
            events.append(r)
        assert sha(f)==before==prior['pools'][b]['events_sha256'];sources[str(f.relative_to(ROOT))]=before
        parts=segments(events,deadlines,slot['start'],slot['start']+slot['actual_seconds'])
        observed=sum(s['seconds'] for s in parts)
        assert abs(observed-prior['pools'][b]['borrowable_wall_seconds'])<1e-5
        rows.append(dict(block=b,observed_borrowable_wall_seconds=observed,by_slack=summarize(parts),segments=parts))
    result=dict(plan_sha256=PIN,reader_sha256=sha(Path(__file__)),source_hashes=sources,pools=rows,
        boundary='Closed observed queue metadata only. Remaining time is not time needed, useful progress, saved GPU cost or a counterfactual completion. Horizons0/60/300/600 are descriptive; no threshold chosen or primary gate changed. Role request-seconds may exceed wall seconds. No candidate, score, prediction or raw log export.')
    out=ROOT/'quota-slack-20261017-v1.safe.json'
    with out.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(dict(sha256=sha(out),pools=[{k:v for k,v in p.items() if k!='segments'} for p in rows])))

if __name__=='__main__':main()
