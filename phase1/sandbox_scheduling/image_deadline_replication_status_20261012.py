"""Allowlisted current-batch structural status, no raw logs or candidate output."""
import json,os,subprocess,time
from pathlib import Path
from lifecycle_pilot import read,sha
R=Path('/research/d7/spc/yzyang4/scheduling-image-deadline-replication-20261012-v1')


def status():
    p=read(R/'plan.json');launch=read(R/'launch.json') if (R/'launch.json').exists() else None
    assert p['planned']==32
    rows=[]
    for r in p['schedule']:
        ep=R/f"episode-{r['index']}";f=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
        c=read(ep/'closed.json') if (ep/'closed.json').exists() else {}
        rows.append(dict(index=r['index'],block=r['block'],arm=r['arm'],task=r['task'],seed=r['seed'],started=(ep/'deadline.json').exists(),finished=bool(f),status=f.get('status'),worker_returncode=c.get('returncode'),cleanup=c.get('cleanup_verified')))
    pools=[]
    for b in range(4):
        bd=R/f'block-{b}';pools.append(dict(block=b,service_ready=read(bd/'service-ready.json') if (bd/'service-ready.json').exists() else None,budget=read(bd/'budget-slot.json') if (bd/'budget-slot.json').exists() else None))
    closed={name:read(R/name) for name in ('completion-closed.json','completion-error.json','completion-incomplete.json') if (R/name).exists()}
    account=[]
    if launch:
        raw=subprocess.check_output(['sacct','-X','-j',launch['job'],'-n','-P','--format=JobIDRaw,State,ElapsedRaw,AllocTRES'],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=20)
        account=[x.split('|') for x in raw.splitlines() if x.split('|')[0]==launch['job']]
    print(json.dumps(dict(observed=time.time(),plan_sha256=sha(R/'plan.json'),launch=launch,accounting=account,assigned=32,rows=rows,pools=pools,closure=closed),allow_nan=False))


if __name__=='__main__':status()
