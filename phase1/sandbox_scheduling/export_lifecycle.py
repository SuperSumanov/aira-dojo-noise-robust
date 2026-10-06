"""Export only the completed authorized no-data lifecycle diagnostics, never logs."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

R=Path('/research/d7/spc/yzyang4/scheduling-lifecycle-20261006-v1')
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
PLAN_SHA='cbece7bc34c10a99e9d65e39ccbb3623d20d047894b94616fa35052e434cda86'


def main():
    os.umask(0o077)
    hashes={}
    def read(name):
        raw=(R/name).read_bytes()
        if SECRET.search(raw):raise ValueError('credential-shaped receipt withheld')
        hashes[name]=hashlib.sha256(raw).hexdigest()
        return json.loads(raw)
    plan=read('plan.json')
    if hashes['plan.json']!=PLAN_SHA:raise ValueError('plan drift')
    closed=read('closed.json')
    if closed!={'attempted':6,'complete':True,'planned':6,'returncodes':[0]*6}:
        raise ValueError('batch incomplete')
    launch=read('launch.json')
    if launch['job']!='16624' or launch['plan_sha256']!=PLAN_SHA:
        raise ValueError('launch mismatch')
    preflight=read('preflight.json')
    episodes=[]
    for i in range(6):
        c=read(f'episode-{i}/completed.json')
        if not c['complete'] or c['error_type'] is not None:raise ValueError('trial failed')
        episodes.append(dict(completed=c,samples=read(f'episode-{i}/samples.json')))
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    raw=subprocess.check_output(['sacct','-j','16624','-X','-n','-P',
        '--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode,NodeList'],env=env,text=True,timeout=15)
    fields=raw.strip().split('|')
    if fields[:2]!=['16624','COMPLETED'] or fields[4]!='0:0' or fields[5]!='gpu27':
        raise ValueError('allocation not completed cleanly')
    tres=dict(item.split('=') for item in fields[3].split(','))
    if int(tres['gres/gpu'])!=1 or int(fields[2])>900:raise ValueError('budget mismatch')
    out=dict(job='16624',plan_sha256=PLAN_SHA,plan=plan,closed=closed,preflight=preflight,
        episodes=episodes,source_hashes=hashes,allocation=dict(state=fields[1],exit_code=fields[4],
            node=fields[5],allocated_gpus=1,elapsed_seconds=int(fields[2]),
            gpu_hours=int(fields[2])/3600,allocated_tres=tres),
        scope='Approved lifecycle fixture only; no datasets, labels, models, tokens or execution logs.')
    encoded=(json.dumps(out,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    if SECRET.search(encoded):raise ValueError('credential-shaped export refused')
    path=R/'resource-readout-v1.json'
    with path.open('xb') as f:f.write(encoded)
    print(json.dumps(dict(path=str(path),sha256=hashlib.sha256(encoded).hexdigest(),
                          completed=6,gpu_hours=out['allocation']['gpu_hours'])))


if __name__=='__main__':main()
