"""Export an existing, closed, frozen readout; never run or repair the reader."""
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
from closed_rng_structure_20261018 import SECRET

R=Path('/research/d7/spc/yzyang4/rng-selection-20261018-v2')
O=R/'readout-20261018-v1'
E=R/'safe-export-20261018-v1'
read=lambda p:json.loads(p.read_text())
URL_CREDENTIAL=re.compile(r'(?i)[?&](?:access_?token|token|api_?key|secret|password|signature|sig)=[^&\s)]+')
assert read(R/'launch.json')['job']=='19249'
assert (R/'closed.json').is_file() and (O/'summary.json').is_file()
assert read(R/'plan.json')['source_commit']=='7632bba196426ae1689e89a1d62671609d1d5296'
env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
q=subprocess.run(['squeue','-j','19249','-h','-o','%i|%T'],env=env,text=True,capture_output=True,timeout=20)
assert q.returncode==0 and not q.stdout.strip(),'job still active or queue unavailable'
a=subprocess.run(['sacct','-j','19249','-n','-P',
    '--format=JobIDRaw,State,ExitCode,ElapsedRaw,Start,End,AllocTRES,NodeList'],
    env=env,text=True,capture_output=True,timeout=20)
assert a.returncode==0
account=[line.split('|') for line in a.stdout.strip().splitlines()]
main=next(x for x in account if x[0]=='19249')
assert main[1] in ('COMPLETED','FAILED','TIMEOUT','CANCELLED')
assert 'gres/gpu=4' in main[6]
assert read(O/'summary.json')['gpu_seconds']==int(main[3])*4
files={n:R/n for n in ('plan.json','native.json','closed.json','launch.json')}
files.update({n:O/n for n in ('summary.json','runs.json','runs.csv','rng-traces.json','selection-sealed.json')})
payload={}
for name,p in files.items():
    raw=p.read_bytes()
    assert not SECRET.search(raw.decode()) and not URL_CREDENTIAL.search(raw.decode()),'credential shape in safe export'
    payload[name]=raw
accounting=json.dumps(dict(job='19249',records=account,allocation_gpu_seconds=int(main[3])*4,
    conservative_gpu_seconds=max(int(x[3]) for x in account)*4,
    note='Slurm elapsed includes allocation startup, idle and cleanup; maximum row adds conservative tail.'),sort_keys=True).encode()
assert not SECRET.search(accounting.decode()) and not URL_CREDENTIAL.search(accounting.decode())
payload['accounting.json']=accounting
E.mkdir(mode=0o700)
for n,b in payload.items():
    with (E/n).open('xb') as f:f.write(b)
manifest={n:hashlib.sha256(b).hexdigest() for n,b in payload.items()}
with (E/'transfer-sha.json').open('x') as f:json.dump(manifest,f,sort_keys=True)
print(json.dumps(dict(export=str(E),files=list(payload),allocation_gpu_seconds=int(main[3])*4)))
