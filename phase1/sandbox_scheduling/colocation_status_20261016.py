"""Read only structural status; never interim candidate or quality values."""
import datetime
import json
from pathlib import Path

R=Path('/research/d7/spc/yzyang4/scheduling-colocation-20261016-v1')
def read(p):return json.loads(p.read_text())
out=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),root=str(R))
for name,path in dict(prepared='plan.json',preflight='preflight.json',
                     submit_intent='submit-intent.json',submitted='launch.json',
                     service_ready='service-ready.json',closed='closed.json').items():
    out[name]=(R/path).exists()
if out['submitted']:
    r=read(R/'launch.json');out.update(job=r['job'],plan_sha256=r['plan_sha256'])
for name,path in (('dispatch_qualified','dispatch-qualification.json'),
                  ('coexistence_qualified','coexistence-qualification.json')):
    p=R/path;out[name]=p.exists() and read(p).get('passed') is True
out['pools_finished']=sum((R/f'block-{b}/budget-slot.json').exists() for b in range(4))
out['started']=sum((R/f'episode-{i}/deadline.json').exists() for i in range(32))
out['finished']=sum((R/f'episode-{i}/finished.json').exists() for i in range(32))
gates=[]
for i in range(32):
    p=R/f'episode-{i}/input-gate.jsonl'
    if not p.exists():continue
    raw=p.read_text();lines=raw.splitlines()
    for j,line in enumerate(lines):
        try:e=json.loads(line)
        except json.JSONDecodeError:
            if j==len(lines)-1 and not raw.endswith('\n'):continue
            raise
        if e.get('event')=='first_request_input_gate':gates.append(e.get('passed') is True)
out.update(first_inputs_checked=len(gates),first_inputs_passed=sum(gates))
if out['closed']:
    c=read(R/'closed.json');out.update(complete=c['complete'],attempted=c['attempted_blocks'],error=c['error'])
print(json.dumps(out,sort_keys=True))
