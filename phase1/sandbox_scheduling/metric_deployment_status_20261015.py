"""Read only the approved batch's structural progress; never scores/prompts."""
import json
from pathlib import Path

R=Path('/research/d7/spc/yzyang4/scheduling-metric-deployment-20261015-v2')
def read(p):return json.loads(p.read_text())
out=dict(root=str(R),prepared=(R/'plan.json').exists(),preflight=(R/'preflight.json').exists(),submitted=(R/'launch.json').exists())
if out['submitted']:
    launch=read(R/'launch.json');out.update(job=launch['job'],plan_sha256=launch['plan_sha256'])
out['service_ready']=(R/'service-ready.json').exists()
out['cpu_input_receipts']=sum((R/f'input-matrix/{i}.safe.json').exists() for i in range(48))
qualification=R/'adapter-service-qualification.json'
out['adapter_routes_qualified']=False
if qualification.exists():
    q=read(qualification)
    out['adapter_routes_qualified']=(q['synthetic_only'] is True and q['quality_claim'] is False
        and len(q['rows'])==2 and all(r['response_received'] is True for r in q['rows'])
        and {r['model_id'] for r in q['rows']}=={'qwen3.8-27b','qwen3.8-27b-metric-step30'})
out['pool_slots_finished']=sum((R/f'block-{i}/budget-slot.json').exists() for i in range(6))
out['started']=sum((R/f'episode-{i}/deadline.json').exists() for i in range(48))
out['finished_receipts']=sum((R/f'episode-{i}/finished.json').exists() for i in range(48))
gates=[]
for i in range(48):
    p=R/f'episode-{i}/input-gate.jsonl'
    if not p.exists():continue
    raw=p.read_text();lines=raw.splitlines()
    for j,line in enumerate(lines):
        try:event=json.loads(line)
        except json.JSONDecodeError:
            if j==len(lines)-1 and not raw.endswith('\n'):continue
            raise ValueError('malformed complete structural event') from None
        if event.get('event')=='first_request_input_gate':gates.append(event.get('passed') is True)
out.update(first_inputs_checked=len(gates),first_inputs_passed=sum(gates))
out['closed']=(R/'closed.json').exists()
if out['closed']:
    c=read(R/'closed.json');out.update(complete=c['complete'],attempted_blocks=c['attempted_blocks'],error_present=c['error'] is not None)
print(json.dumps(out,sort_keys=True))
