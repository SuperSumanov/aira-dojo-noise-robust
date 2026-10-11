"""Structural-only status; no provisional outcome-guided intervention."""
import json
import os
from pathlib import Path
import subprocess
import sys

root=Path(sys.argv[1]);sys.path.insert(0,str(root))
from lifecycle_pilot import read

out=dict(root=str(root),launch=read(root/'launch.json') if (root/'launch.json').exists() else None,
    service_ready=(root/'service-ready.json').exists(),closed=(root/'closed.json').exists(),pools=[])
for b in range(6):
    es=[];path=root/f'generation-{b}/events.jsonl'
    if path.exists():
        for s in path.read_text().splitlines():
            try:es.append(json.loads(s))
            except json.JSONDecodeError:pass  # concurrent trailing append, status only
    out['pools'].append(dict(block=b,started=sum((root/f'episode-{i}/deadline.json').exists() for i in range(8*b,8*b+8)),
        finished=sum((root/f'episode-{i}/finished.json').exists() for i in range(8*b,8*b+8)),
        warm_loaded=sum(e['event']=='warm_start' for e in es),
        admitted=sum(e['event']=='admitted' for e in es),
        round_complete=sum(e['event']=='round_complete' for e in es),
        slot_closed=(root/f'block-{b}/budget-slot.json').exists()))
if out['closed']:out['closure']=read(root/'closed.json')
if out['launch']:
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    p=subprocess.run(['squeue','-j',out['launch']['job'],'-h','-o','%i|%T|%M|%R'],env=env,capture_output=True,text=True,timeout=20)
    out['queue']=p.stdout.strip();out['queue_rc']=p.returncode
    for s in read(root/'plan.json')['schedule']:
        f=root/f"episode-{s['index']}/failure.json"
        if f.exists():out.setdefault('failures',[]).append(dict(index=s['index'],**read(f)))
print(json.dumps(out,allow_nan=False))
