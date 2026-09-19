"""Only structural receipts while the fixed third bank is running."""
import json,os,subprocess
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/comparison-third-bank-20260919-7b544kbs')
if ROOT.resolve(strict=True)!=ROOT:raise ValueError('scope')
job=json.loads((ROOT/'launch.json').read_bytes())['job']
if job!='14135':raise ValueError('job identity')
env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
acc=subprocess.check_output(['sacct','-X','-j',job,'-nP','-o','JobIDRaw,State%24,ElapsedRaw,NodeList,AllocTRES%120'],env=env,text=True,timeout=25)
rows=[line.split('|') for line in acc.splitlines() if line.split('|')[0]==job]
if len(rows)!=1:raise ValueError('accounting')
print(json.dumps(dict(job=job,allocation=rows[0],claimed=(ROOT/'execution-claim.json').exists(),
    finished=(ROOT/'finished.json').exists(),result_records=sum((ROOT/f'result-{i}.json').exists() for i in range(6)),
    binding_records=sum((ROOT/f'identity-{i}.native-binding.json').exists() for i in range(6)))))
