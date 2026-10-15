"""Closed18510 diagnostics: structure/stack locations only, no log bodies."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
from safe_senior_reader import redact

R=Path('/research/d7/spc/yzyang4/scheduling-pooling-20261015-v2')
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def trace(path):
    safe,counts=redact(path.read_text(errors='replace'))
    frames=[dict(file=Path(f).name,line=int(n),function=fn)
            for f,n,fn in re.findall(r'File "([^"\n]+)", line (\d+), in ([^\n]+)',safe)]
    errors=[]
    for typ,msg in re.findall(r'^([A-Za-z_][\w.]*(?:Error|Exception)|AssertionError|SystemExit|KeyboardInterrupt)(?::[^\S\n]*(.*))?$',safe,re.M):
        errors.append(dict(type=typ,message_sha256=hashlib.sha256(msg.encode()).hexdigest(),
            known_markers=[x for x in ('execution/queue timing inconsistency','unsafe release','unknown waiting request',
                'duplicate request','runtime input drift','expected16 physical execution cores','container requires one live device lease',
                'exact one-device mount gate failed','no complete slot left','executor failed','Timed out','deadline') if x in msg]))
    return dict(sha256=sha(path),redaction_counts=counts,frames=frames[-30:],errors=errors[-12:])

p,c=read(R/'plan.json'),read(R/'closed.json')
assert read(R/'launch.json')['job']=='18510' and c['planned']==32
raw=subprocess.check_output(['sacct','-j','18510','-X','-n','-P','-o','JobID,State,Start,End,ElapsedRaw,AllocGRES'],text=True)
entries=[x.split('|') for x in raw.strip().splitlines() if x]
assert len(entries)==1
j,state,start,end,elapsed,gres,*_=entries[0]
assert j=='18510' and state=='FAILED' and gres=='gpu:6'
rows=[];diagnostics=[]
for s in p['schedule']:
    ep=R/f"episode-{s['index']}"
    cl=read(ep/'closed.json') if (ep/'closed.json').exists() else {}
    f=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
    row=dict(index=s['index'],block=s['block'],started=(ep/'deadline.json').exists(),
        returncode=cl.get('returncode'),cleanup_verified=cl.get('cleanup_verified'),
        status=f.get('status'),finished_keys=sorted(f))
    assert row['status'] in (None,'completed','budget_exhausted','failed','error','incomplete')
    rows.append(row)
    if row['started'] and (cl.get('returncode')!=0 or row['status'] not in ('completed','budget_exhausted')):
        diagnostics.append(dict(index=s['index'],worker=trace(ep/'worker.private.log')))
executors=[dict(block=b,trace=trace(R/f'block-{b}/executor.private.log')) for b in c['attempted_blocks']]
cost=int(elapsed)*6
out=dict(job=j,state=state,start_hk=start,end_hk=end,elapsed_seconds=int(elapsed),gpu_seconds=cost,gpu_hours=cost/3600,
    assigned=32,started=sum(x['started'] for x in rows),complete=c['complete'],
    source_commit=p['source_commit'],plan_sha256=sha(R/'plan.json'),error=c['error'],
    service_cleanup=read(R/'block-0/service-cleanup.json'),dispatch_qualification_passed=read(R/'dispatch-qualification.json')['passed'],
    rows=rows,failed_worker_diagnostics=diagnostics,executors=executors,quality_claim=False,automatic_retry=False)
with (R/'failure-18510.safe.json').open('x') as f:json.dump(out,f,sort_keys=True,indent=2)
print(json.dumps(out,sort_keys=True))
