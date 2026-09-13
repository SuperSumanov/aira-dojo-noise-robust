"""Read only operational markers, never new scores or candidate programs."""
from contextlib import closing
import collections
import datetime as dt
import json
from pathlib import Path
import sqlite3
import subprocess
import os

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-88v5m9dr')


def read(p):return json.loads(p.read_bytes())


def run():
    blocks=[];channels=[]
    for block in (1,2):
        start=ROOT/f'block-{block}.runtime/started.json'
        if not start.exists():blocks.append(dict(block=block,status='not_started'));continue
        pool=read(ROOT/read(start)['pool_manifest'])
        blocks.append(dict(block=block,job=pool['allocation_id'],runs=[dict(run_id=k,status=v['status'],attempt=v['attempt']) for k,v in pool['tasks'].items()]))
    for p in (ROOT/'runs/srun_pool').glob('*/identities/*.bounded/execution/stderr.private.log'):
        events=collections.Counter();handshakes=collections.Counter()
        with p.open(errors='replace') as stream:
            for line in stream:
                if '] KERNEL_WIRE ' in line:
                    try:events[json.loads(line.split('] KERNEL_WIRE ',1)[1])['event']]+=1
                    except (ValueError,KeyError):pass
                elif '] kernel_handshake {' in line:
                    try:handshakes[str(json.loads(line.split('kernel_handshake ',1)[1])['success'])]+=1
                    except (ValueError,KeyError):pass
        channels.append(dict(identity=p.parents[1].name,events=dict(events),handshakes=dict(handshakes)))
    with closing(sqlite3.connect((ROOT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        total=db.execute('SELECT COUNT(*),SUM(held),SUM(COALESCE(cost,0)),SUM(state="unresolved") FROM calls').fetchone()
        stopped=db.execute('SELECT stopped FROM auth').fetchone()[0]
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    queue=subprocess.check_output(['squeue','-j','13282,13283','-h','-o','%i|%T|%M|%N'],env=env,text=True,timeout=25)
    acct=subprocess.check_output(['sacct','-X','-j','13282,13283','-nP','-o','JobIDRaw,State%32,ElapsedRaw,NodeList'],env=env,text=True,timeout=25)
    print(json.dumps(dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),blocks=blocks,channels=channels,
        billing=dict(calls=total[0],held_nusd=total[1],settled_nusd=total[2],unresolved=total[3],stopped=bool(stopped)),
        queue=queue.strip().splitlines(),accounting=acct.strip().splitlines())))


if __name__=='__main__':run()
