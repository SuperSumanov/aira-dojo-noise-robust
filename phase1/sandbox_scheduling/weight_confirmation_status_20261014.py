"""Outcome-free progress only; no candidate/prediction/score/prompt bodies."""
import json
from pathlib import Path
import sys
R=Path('/research/d7/spc/yzyang4/scheduling-weight-confirmation-20261014-v1')
def read(p):return json.loads(p.read_text())
out=dict(root=str(R),prepared=(R/'plan.json').exists(),submitted=(R/'launch.json').exists())
if out['submitted']:out.update(read(R/'launch.json'))
out['service_ready']=(R/'service-ready.json').exists()
out['pool_slots_finished']=sum((R/f'block-{i}/budget-slot.json').exists() for i in range(4))
out['started']=sum((R/f'episode-{i}/deadline.json').exists() for i in range(32))
out['finished_receipts']=sum((R/f'episode-{i}/finished.json').exists() for i in range(32))
gates=[]
for i in range(32):
    p=R/f'episode-{i}/input-gate.jsonl'
    if not p.exists():continue
    for line in p.read_text().splitlines():
        try:e=json.loads(line)
        except json.JSONDecodeError:continue  # live writer may have an incomplete last line
        if e.get('event')=='first_request_input_gate':gates.append(e.get('passed') is True)
out.update(first_inputs_checked=len(gates),first_inputs_passed=sum(gates))
if (R/'closed.json').exists():
    c=read(R/'closed.json');out.update(closed=True,complete=c['complete'],attempted_blocks=c['attempted_blocks'],error=c['error'])
else:out['closed']=False
print(json.dumps(out,sort_keys=True))
