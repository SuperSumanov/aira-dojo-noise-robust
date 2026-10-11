"""Read-only sampled service-queue check; no candidate or outcome access.

This supplements, never replaces or changes, the frozen quality gate. A zero
queue sample after all pool workers exit is evidence against inter-pool spill;
absence of a sample is unknown, not proof of quiescence.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re

COUNTS=re.compile(r'Running:\s*(\d+)\s+reqs,\s*Waiting:\s*(\d+)\s+reqs')
STAMP=re.compile(r'\b(\d{2}-\d{2} \d{2}:\d{2}:\d{2})\b')


def parse(raw):
    rows=[];missing=0
    for line in raw.splitlines():
        q=COUNTS.search(line)
        if not q:continue
        s=STAMP.search(line)
        if s is None:missing+=1;continue
        rows.append(dict(stamp=s[1],running=int(q[1]),waiting=int(q[2])))
    return rows,missing


def epoch(stamp, offset):
    local=dt.datetime.strptime('2026-'+stamp,'%Y-%m-%d %H:%M:%S')
    return local.replace(tzinfo=dt.timezone(dt.timedelta(hours=offset))).timestamp()


def boundary(samples, worker_end, pool_end):
    tail=[r for r in samples if worker_end<=r['time']<=pool_end]
    if not tail:return dict(observed=False,zero_after_workers=None,samples=0)
    # In the idle padding there are no new agent requests from this pool.
    last=tail[-1]
    zero=last['running']==last['waiting']==0
    return dict(observed=True,zero_after_workers=zero,samples=len(tail),
        last_running=last['running'],last_waiting=last['waiting'],
        last_sample_to_boundary_seconds=pool_end-last['time'])


def analyze(root):
    root=Path(root)
    # Only fixed structural records and numeric logger fields are inspected.
    slots={b:json.loads((root/f'block-{b}/budget-slot.json').read_text())
           for b in range(6) if (root/f'block-{b}/budget-slot.json').exists()}
    rows,missing=parse((root/'block-0/service.private.log').read_text(errors='replace'))
    result=dict(samples=len(rows),missing_timestamp=missing,closed=(root/'closed.json').exists(),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        boundary='Sampled queue counters only, not a continuous per-request trace or quality evidence.')
    if not rows or 0 not in slots:
        return dict(result,status='waiting_for_structural_slot_or_logger_samples')
    # The logger can follow the container timezone rather than the host.
    # Infer only from its FIRST telemetry sample and first pool start; do not
    # choose an offset to make later idle checks pass. Unknown is fail-closed.
    start=slots[0]['start']
    offsets=[o/4 for o in range(-48,57) if start-600<=epoch(rows[0]['stamp'],o/4)<=start+120]
    if len(offsets)!=1:return dict(result,status='unknown_logger_clock',offset_candidates=len(offsets))
    offset=offsets[0]
    samples=[dict(r,time=epoch(r['stamp'],offset)) for r in rows]
    if any(a['time']>b['time'] for a,b in zip(samples,samples[1:])):
        return dict(result,status='nonmonotonic_logger_clock')
    checks=[]
    for b,s in sorted(slots.items()):
        checks.append(dict(block=b,**boundary(samples,s['start']+s['active_seconds'],s['start']+s['actual_seconds'])))
    return dict(result,status='checked',logger_utc_offset_hours=offset,pools=checks,
        all_six_sampled_quiescent=len(checks)==6 and all(r['zero_after_workers'] is True for r in checks))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');a=p.parse_args()
    print(json.dumps(analyze(a.root),allow_nan=False))
