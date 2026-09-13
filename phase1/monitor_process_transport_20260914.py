"""Small credential-free state projection for the isolated transport diagnostic."""
import json,os,subprocess
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/forets-process-transport-20260914-83zx3mg1')
env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
queue=subprocess.check_output(['squeue','-j','13286','-h','-o','%i|%T|%N|%M'],env=env,text=True,timeout=20)
rows=[json.loads(p.read_bytes()) for p in sorted(ROOT.glob('case-*.json'))]
state=dict(job='13286',queue=queue.strip(),cases=[{k:v for k,v in r.items() if k not in ('values',)} for r in rows])
p=ROOT/'result.json'
if p.exists():
    r=json.loads(p.read_bytes());state['result']={k:v for k,v in r.items() if k!='rows'}
    state['case_outcomes']=[{k:v for k,v in row.items() if k!='values'} for row in r['rows']]
if not queue.strip():
    state['accounting']=subprocess.check_output(['sacct','-j','13286','-P','-n','-o','JobIDRaw,State,ExitCode,ElapsedRaw,NodeList'],env=env,text=True,timeout=20).strip()
print(json.dumps(state,sort_keys=True))
