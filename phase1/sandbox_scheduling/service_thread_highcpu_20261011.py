"""Scheduler-only correction before allocation; unchanged resource matrix."""
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys

import service_thread_diag_20261011 as s

OLD=s.ROOT
OLD_SHA='38ac9154a978b86654c1f2378c2d7404e05c724dd42a5dec68f074a1038135e5'
ROOT=s.d.BASE/'resource-service-diag-20261011-v2'
NAME=Path(__file__).name
s.ROOT=ROOT;s.NAME=NAME;s.d.ROOT=ROOT;s.d.NAME=NAME


def prepare():
    assert s.d.sha(OLD/'plan.json')==OLD_SHA
    assert not (OLD/'launch.json').exists() and not (OLD/'submit-intent.json').exists()
    old=json.loads((OLD/'plan.json').read_text())
    ROOT.mkdir(mode=0o700)
    for name,digest in old['files'].items():
        assert s.d.sha(OLD/name)==digest
        target=ROOT/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(OLD/name,target)
    shutil.copyfile(__file__,ROOT/NAME)
    batch=(ROOT/'run.sbatch').read_text().replace(str(OLD),str(ROOT)).replace(
        'service_thread_diag_20261011.py',NAME).replace('#SBATCH --nodelist=gpu27\n',
        '#SBATCH --nodelist=gpu27\n#SBATCH --constraint=highcpucount\n')
    (ROOT/'run.sbatch').write_text(batch)
    subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    for row in s.d.schedule():(ROOT/f"block-{row['block']}-worker-{row['index']}").mkdir()
    (ROOT/'service-cache/tmp').mkdir(parents=True)
    with (ROOT/'.service.env').open('x') as f:f.write('VLLM_API_KEY='+secrets.token_hex(32)+'\n')
    os.chmod(ROOT/'.service.env',0o600)
    plan=dict(old,unsubmitted_v1=dict(plan_sha256=OLD_SHA,
        scheduler_failure='18CPU/2GPU requires highcpucount; gpu27 verified to have this feature; no job submitted'),
        model_reuse='Exact assets fully rehashed immediately before this scheduler-only correction; no asset writes.',
        files={str(p.relative_to(ROOT)):s.d.sha(p) for p in ROOT.rglob('*')
               if p.is_file() and p.name!='.service.env' and '__pycache__' not in p.parts})
    s.d.write(ROOT/'plan.json',plan)
    print(json.dumps(dict(prepared=True,root=str(ROOT),plan_sha256=s.d.sha(ROOT/'plan.json'))))


if __name__=='__main__':
    os.umask(0o077);mode=sys.argv[1]
    if mode=='prepare':sys.exit(prepare())
    if mode=='worker':sys.exit(s.d.worker(*map(int,sys.argv[2:])))
    if mode not in ('service','controller','allocation'):raise ValueError('mode')
    sys.exit(getattr(s,mode)())
