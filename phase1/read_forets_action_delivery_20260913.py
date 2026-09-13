"""Independent passive action reader: latest eligible, never best external grade."""
import hashlib
import json
import math
from pathlib import Path

PROTOCOL='original_search_visible_action_delivery_v1'

def replay(rows):
    if len({r['node_id'] for r in rows})!=len(rows):raise ValueError('duplicate nodes')
    best=None
    for r in rows:
        if type(r['is_buggy']) is not bool:raise ValueError('analysis incomplete')
        v=r['search_value'];direction=r['maximize']
        if v is not None and (type(v) not in (int,float) or not math.isfinite(v)):
            raise ValueError('invalid validation metric')
        if direction is not None and type(direction) is not bool:raise ValueError('direction')
        if r['is_buggy']:continue
        if best is None:best=r;continue
        if v is None:continue
        b=best['search_value']
        if b is None:best=r;continue
        if direction!=best['maximize']:raise ValueError('inconsistent metric directions')
        if (v>b if direction else v<b):best=r
    return best

def read_latest(base,*,start_ns,seconds):
    directory=Path(base)/'action-incumbents'
    if directory.is_symlink():raise ValueError('action path symlink')
    deadline=start_ns+round(seconds*10**9);records=[]
    for path in sorted(directory.glob('action-*.commit.json')):
        if path.is_symlink():raise ValueError('commit symlink')
        try:c=json.loads(path.read_bytes())
        except json.JSONDecodeError:continue
        data=directory/c['data_file']
        if data.parent!=directory or data.is_symlink() or path.name!=data.stem+'.commit.json':raise ValueError('action path')
        raw=data.read_bytes();d=json.loads(raw)
        if (hashlib.sha256(raw).hexdigest()!=c['data_sha256'] or d['protocol']!=PROTOCOL or d['schema']!=1
            or d['start_ns']!=start_ns or d['deadline_ns']!=deadline or c['deadline_ns']!=deadline
            or type(d['observation_ns']) is not int or type(c['durable_ns']) is not int
            or not start_ns<=d['observation_ns']<=c['durable_ns']
            or c['eligible'] is not (c['durable_ns']<deadline)):
            raise ValueError('hash/clock binding')
        if (type(d['action']) is not int or d['action']!=len(d['observed_nodes']) or d['action']<1
            or data.name!=f"action-{d['action']:06d}.json"):
            raise ValueError('action identity')
        best=replay(d['observed_nodes'])
        if best is None:
            if d['node_id'] is not None or d['code'] is not None or d['submission'] is not None:raise ValueError('missing is not zero')
        else:
            h=hashlib.sha256(d['code'].encode()).hexdigest()
            if best['node_id']!=d['node_id'] or best['code_sha256']!=h or d['submission']['code_sha256']!=h:
                raise ValueError('independent original-selection replay differs')
        records.append((d['action'],c['durable_ns'],c['eligible'],d))
    if len({r[0] for r in records})!=len(records):raise ValueError('duplicate action')
    records.sort()
    if any(a[1]>b[1] for a,b in zip(records,records[1:])):raise ValueError('action chronology')
    eligible=[r for r in records if r[2]]
    return eligible[-1][3] if eligible else None
