"""Structural-only progress of this approved batch, not interim quality."""
import datetime
import json
from pathlib import Path

R=Path('/research/d7/spc/yzyang4/scheduling-pooling-20261015-v1')
def read(p):return json.loads(p.read_text())
out=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),root=str(R),
    prepared=(R/'plan.json').exists(),preflight=(R/'preflight.json').exists(),
    submit_intent=(R/'submit-intent.json').exists(),submitted=(R/'launch.json').exists())
if out['submitted']:
    r=read(R/'launch.json');out.update(job=r['job'],plan_sha256=r['plan_sha256'])
out['service_ready']=(R/'service-ready.json').exists()
q=R/'dispatch-qualification.json'
out['dispatch_qualified']=q.exists() and read(q).get('passed') is True
out['pool_slots_finished']=sum((R/f'block-{i}/budget-slot.json').exists() for i in range(4))
out['started']=sum((R/f'episode-{i}/deadline.json').exists() for i in range(32))
out['finished_receipts']=sum((R/f'episode-{i}/finished.json').exists() for i in range(32))
gates=[]
for i in range(32):
    p=R/f'episode-{i}/input-gate.jsonl'
    if not p.exists():continue
    raw=p.read_text();parts=raw.splitlines()
    for j,line in enumerate(parts):
        try:e=json.loads(line)
        except json.JSONDecodeError:
            if j==len(parts)-1 and not raw.endswith('\n'):continue
            raise
        if e.get('event')=='first_request_input_gate':gates.append(e.get('passed') is True)
out.update(first_inputs_checked=len(gates),first_inputs_passed=sum(gates))
out['closed']=(R/'closed.json').exists()
if out['closed']:
    c=read(R/'closed.json');out.update(complete=c['complete'],attempted_blocks=c['attempted_blocks'],error=c['error'])
print(json.dumps(out,sort_keys=True))
