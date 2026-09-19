"""Fixed depth-two job: only structure and scheduler state while running."""
import json, os, re, subprocess
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/comparison-depth2-debug-20260919-ffunn8gg')
if ROOT.resolve(strict=True)!=ROOT:raise ValueError('scope')
job=json.loads((ROOT/'launch.json').read_bytes())['job']
if job!='14134':raise ValueError('job identity')
env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
acc=subprocess.check_output(['sacct','-X','-j',job,'-nP','-o','JobIDRaw,State%24,ElapsedRaw,NodeList,AllocTRES%120'],env=env,text=True,timeout=25)
rows=[line.split('|') for line in acc.splitlines() if line.split('|')[0]==job]
if len(rows)!=1:raise ValueError('accounting')
out=dict(job=job,allocation=rows[0],ready=(ROOT/'ready.json').exists(),
    generation_records=sum((ROOT/f'generation-{i}.json').exists() for i in (1,2)),closed=(ROOT/'closed.json').exists())
if out['closed']:out['closed_status']=json.loads((ROOT/'closed.json').read_bytes())['status']
print(json.dumps(out))
