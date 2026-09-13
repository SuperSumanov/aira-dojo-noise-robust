"""Compact in-session health read, no candidate data or task outcome values."""
from pathlib import Path
import collections
import datetime as dt
import json
import re
import sqlite3
from contextlib import closing

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-y_p2tlmi')


def read(p):return json.loads(p.read_bytes())


def run():
    blocks=[]
    for b in (1,2):
        start=ROOT/f'block-{b}.runtime/started.json'
        if not start.exists():blocks.append(dict(block=b,status='not_started'));continue
        pool=read(ROOT/read(start)['pool_manifest'])
        blocks.append(dict(block=b,job=pool['allocation_id'],runs=[dict(run_id=k,status=v['status'],attempt=v['attempt']) for k,v in pool['tasks'].items()]))
    counts=collections.Counter();terminal=[]
    for p in (ROOT/'runs/srun_pool').glob('*/identities/*.bounded/execution/stderr.private.log'):
        events=collections.Counter(); handshakes=collections.Counter()
        for line in p.read_text(errors='replace').splitlines():
            marker='] KERNEL_WIRE '
            if marker in line:
                try:event=json.loads(line.split(marker,1)[1]);events[event['event']]+=1
                except (ValueError,KeyError):continue
            if '] kernel_handshake {' in line:
                try:handshakes[str(json.loads(line.split('kernel_handshake ',1)[1])['success'])]+=1
                except (ValueError,KeyError):continue
        counts.update(events)
        terminal.append(dict(identity=p.parents[1].name,wire_events=dict(events),handshakes=dict(handshakes)))
    with closing(sqlite3.connect((ROOT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        calls=db.execute('SELECT held,cost,state FROM calls').fetchall()
        auth=db.execute('SELECT stopped FROM auth').fetchone()[0]
    print(json.dumps(dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),blocks=blocks,channels=terminal,
        billing=dict(calls=len(calls),settled_nusd=sum(c[1] or 0 for c in calls),held_nusd=sum(c[0] for c in calls),
            unresolved=sum(c[2]=='unresolved' for c in calls),stopped=bool(auth))),sort_keys=True))


if __name__=='__main__':run()
