"""Independent entry repair: Slurm19 has no --exact; keep matrix and caps."""
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys

import service_thread_highcpu_20261011 as h

s=h.s
OLD=h.ROOT
OLD_SHA='0e945b1381e3ccdf3a899ca31b361ff32e4dc2c005d6a75aff7e99b99c461ae2'
ROOT=s.d.BASE/'resource-service-diag-20261011-v3'
NAME=Path(__file__).name
s.ROOT=ROOT;s.NAME=NAME;s.d.ROOT=ROOT;s.d.NAME=NAME


def prepare():
    assert s.d.sha(OLD/'plan.json')==OLD_SHA
    old=json.loads((OLD/'plan.json').read_text())
    failed=json.loads((OLD/'allocation-closed.json').read_text())
    assert failed['returncode']==1 and failed['service_stopped'] and failed['controller_stopped']
    assert not (OLD/'service-identity.json').exists() and not (OLD/'closed.json').exists()
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    helptext=subprocess.check_output(['srun','--help'],env=env,text=True)
    assert '--exact' not in helptext
    assert all(flag in helptext for flag in ('--exclusive','--gres','--cpu-bind','--cpus-per-task'))
    ROOT.mkdir(mode=0o700)
    for name,digest in old['files'].items():
        assert s.d.sha(OLD/name)==digest
        target=ROOT/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(OLD/name,target)
    shutil.copyfile(__file__,ROOT/NAME)
    driver=ROOT/'service_thread_diag_20261011.py';source=driver.read_text()
    assert source.count("'--exact',")==2
    source=source.replace("'--exact',",'');compile(source,str(driver),'exec');driver.write_text(source)
    batch=(ROOT/'run.sbatch').read_text().replace(str(OLD),str(ROOT)).replace('service_thread_highcpu_20261011.py',NAME)
    (ROOT/'run.sbatch').write_text(batch)
    subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    for row in s.d.schedule():(ROOT/f"block-{row['block']}-worker-{row['index']}").mkdir()
    (ROOT/'service-cache/tmp').mkdir(parents=True)
    with (ROOT/'.service.env').open('x') as f:f.write('VLLM_API_KEY='+secrets.token_hex(32)+'\n')
    os.chmod(ROOT/'.service.env',0o600)
    plan=dict(old,failed_v2=dict(job='17545',plan_sha256=OLD_SHA,gpu_seconds=10,attempted_kernels=0,
        reason='srun19.05.4 rejects --exact before service/candidate starts'),
        entry_repair='Remove unsupported --exact only; explicit exclusive steps with unchanged12+6 CPUs and2+0 GPUs.',
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
