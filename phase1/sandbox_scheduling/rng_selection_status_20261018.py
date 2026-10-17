"""Read-only metadata/status. Does not read score or prediction files."""
import json,os,subprocess,sys
from pathlib import Path
version=sys.argv[1] if len(sys.argv)>1 else 'v2'
assert version in ('v1','v2')
R=Path('/research/d7/spc/yzyang4/rng-selection-20261018-'+version)
read=lambda p:json.loads(p.read_text())
out={'root_exists':R.exists(),'plan':(R/'plan.json').exists(),'submitted':(R/'launch.json').exists()}
if not out['submitted']:
    out['submit_processes']=[]
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():continue
        try:
            args=(proc/'cmdline').read_bytes().split(b'\0')
            if str(R/'rng_selection_pilot_20261018.py').encode() in args and b'submit' in args:
                io=(proc/'io').read_text()
                out['submit_processes'].append(dict(pid=int(proc.name),io=dict(line.split(': ',1) for line in io.strip().splitlines())))
        except (PermissionError,FileNotFoundError,ProcessLookupError):pass
if out['submitted']:
    job=read(R/'launch.json')['job'];assert str(job).isdigit()
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    for name,cmd in [('queue',['squeue','-j',job,'-h','-o','%i|%T|%M|%R']),
                     ('accounting',['sacct','-j',job,'-n','-P','--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocTRES,NodeList'])]:
        p=subprocess.run(cmd,env=env,text=True,capture_output=True,timeout=20)
        out[name]=p.stdout.strip() if p.returncode==0 else {'returncode':p.returncode}
    out['started']=[i for i in range(32) if (R/f'episode-{i}/started.json').exists()]
    out['finished']=[i for i in range(32) if (R/f'episode-{i}/finished.json').exists()]
    out['errors']={str(i):read(R/f'episode-{i}/finished.json').get('error') for i in out['finished']
                   if read(R/f'episode-{i}/finished.json').get('error')}
    out['rng_receipts']=sum((R/f'episode-{i}/training.safe.json').exists() for i in range(32))
    if (R/'closed.json').exists():out['closed']=read(R/'closed.json')
    if (R/'window-refusal.json').exists():out['window_refusal']=read(R/'window-refusal.json')
print(json.dumps(out))
