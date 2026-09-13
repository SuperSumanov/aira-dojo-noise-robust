import collections,json,os,re,subprocess
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/forets-fresh-integration-20260914-ih6u0mpw')
env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
queue=subprocess.check_output(['squeue','-j','13287','-h','-o','%i|%T|%N|%M'],env=env,text=True,timeout=20)
rows=[json.loads(p.read_bytes()) for p in sorted(ROOT.glob('case-*.json'))]
state=dict(job='13287',queue=queue.strip(),closed=len(rows),counts=dict(collections.Counter((r['backend']+':'+r['status']) for r in rows)),
    noncompleted=[r for r in rows if r['status']!='completed'])
p=ROOT/'result.json'
if p.exists():
    r=json.loads(p.read_bytes());state['result']={k:v for k,v in r.items() if k not in ('rows','parallel')}
if not queue.strip():
    state['accounting']=subprocess.check_output(['sacct','-j','13287','-P','-n','-o','JobIDRaw,State,ExitCode,ElapsedRaw,NodeList'],env=env,text=True,timeout=20).strip()
    if not p.exists():
        err=ROOT/'allocation-13287.err';raw=err.read_bytes()[-20000:] if err.exists() else b''
        state['exception_classes']=[x.decode() for x in re.findall(rb'(?:^|\n)(?:[A-Za-z_][A-Za-z0-9_]*\.)*([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception)):',raw)]
print(json.dumps(state,sort_keys=True))
