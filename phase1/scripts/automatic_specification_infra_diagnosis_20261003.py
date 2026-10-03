"""Read only a closed pre-candidate failure; redact credentials before output."""
import hashlib,json,re,subprocess,os,sys
from pathlib import Path
version=sys.argv[1] if len(sys.argv)>1 else 'v2'
assert version in ('v2','v3')
R=Path('/research/d7/spc/yzyang4')/('automatic-specification-20261003-gpu1-'+version)
job=json.loads((R/'launch.json').read_bytes())['job'];assert job.isdigit()
assert json.loads((R/'closed.json').read_bytes())['service_closed']
assert not list(R.glob('episode-*/action-*/request.private.json'))
secret=re.compile(r'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
for name in ('allocation-'+job+'.err','allocation-'+job+'.out','service.private.log','compatibility-failed.json','compatibility.json'):
    p=R/name
    if not p.exists():continue
    raw=p.read_bytes();text=secret.sub('[REDACTED]',raw.decode(errors='replace'))
    tail=text.splitlines()[-35:]
    print(json.dumps(dict(file=name,sha256=hashlib.sha256(raw).hexdigest(),credential_shape_hits=len(secret.findall(raw.decode(errors='replace'))),tail=tail)))
print(subprocess.check_output(['sacct','-j',job,'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=25))
