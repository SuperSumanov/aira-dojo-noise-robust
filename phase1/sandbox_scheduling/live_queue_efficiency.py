"""Read-only post-closure admission accounting, not an alternative effect gate.

Permit-slot seconds with waiting work and spare logical capacity diagnose
admission overhead. They are NOT device-idle time or recoverable GPU savings.
No candidate, score, label, reply or private log is read. Run only after closure.
"""
import argparse
import json
import math
from pathlib import Path
from lifecycle_pilot import read, write, sha


def account(events, limit):
    if limit not in (1,2):raise ValueError('frozen live width')
    previous=None;waiting=[];active=set();seen=set()
    total=lost=queue_time=busy=0.;intervals=0;longest=0.
    for e in events:
        t=e['time'];kind=e['event'];key=e['key']
        if not math.isfinite(t) or previous is not None and t<previous:
            raise ValueError('nonmonotonic event clock')
        if previous is not None:
            seconds=t-previous;total+=seconds
            busy+=len(active)*seconds;queue_time+=len(waiting)*seconds
            spare=min(limit-len(active),len(waiting))
            if spare:
                lost+=spare*seconds;intervals+=1;longest=max(longest,seconds)
        if kind=='queued':
            if key in seen:raise ValueError('duplicate operation')
            seen.add(key);waiting.append(key)
        elif kind=='admitted':
            if len(active)>=limit or not waiting or waiting.pop(0)!=key:
                raise ValueError('non-FIFO/overcapacity')
            active.add(key)
        elif kind=='released':
            if key not in active:raise ValueError('unowned release')
            active.remove(key)
        elif kind=='queue_cancelled':
            if key not in waiting:raise ValueError('unowned cancellation')
            waiting.remove(key)
        else:raise ValueError('unknown event')
        if (e['active'],e['queued'],e['limit'])!=(len(active),len(waiting),limit):
            raise ValueError('state count mismatch')
        previous=t
    if active or waiting:raise ValueError('open queue; no complete accounting')
    return dict(event_count=len(events),operations=len(seen),event_span_seconds=total,
        busy_permit_slot_seconds=busy,waiting_task_seconds_including_cancelled=queue_time,
        waiting_with_spare_permit_slot_seconds=lost,spare_with_waiting_intervals=intervals,
        longest_spare_with_waiting_event_interval_seconds=longest,
        accounted_through_final_release_or_cancellation=True)


def main(root, output):
    root=Path(root)
    if root.name!='scheduling-live-search-20261009-v7':raise ValueError('explicit fresh dev root only')
    plan=read(root/'plan.json');closed=read(root/'closed.json')
    rows=[]
    for block in range(4):
        path=root/f'queue-{block}/events.jsonl'
        if not path.exists():
            rows.append(dict(block=block,observed=False));continue
        arm=next(s['arm'] for s in plan['schedule'] if s['block']==block)
        events=[json.loads(s) for s in path.read_text().splitlines() if s.strip()]
        rows.append(dict(block=block,arm=arm,observed=True,events_sha256=sha(path),
            **account(events,1 if arm=='pipeline' else 2)))
    result=dict(plan_sha256=sha(root/'plan.json'),closed_sha256=sha(root/'closed.json'),
        analysis_source_sha256=sha(__file__),rows=rows,
        boundary='Descriptive admission overhead only. Permit-slot seconds are not GPU seconds. Includes cancelled waiting. Event-span coverage excludes time before first/after last queue event; no alternative effect gate, imputation or workload replay.')
    write(output,result)
    print(json.dumps(dict(written=True,observed=sum(r['observed'] for r in rows))))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('output')
    a=p.parse_args();main(a.root,a.output)
