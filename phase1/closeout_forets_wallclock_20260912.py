"""One experiment's CPU-only completion stage, not a recurring automation.

Wait for the exact dispatched allocation to close, then invoke the pinned
independent reader once. Never submit/cancel/retry GPU work, call an API, change
a policy, push Git, or continue another experiment. Hard lifetime four hours.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

TERMINAL={'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE'}


def write(path,value):
    with path.open('x') as stream:
        json.dump(value,stream,sort_keys=True,indent=2,allow_nan=False)
        stream.flush();os.fsync(stream.fileno())


def bound(root, job='13152', seeds=(22,23)):
    root=root.resolve(strict=True)
    if root.parent!=Path('/research/d7/spc/yzyang4') or not root.name.startswith('forets-wallclock-20260912-'):
        raise ValueError('only explicit new experiment')
    launch=json.loads((root/'launch.json').read_bytes())
    if not re.fullmatch('[0-9]+',job) or launch['job']!=job or launch['package']!=str(root):raise ValueError('not the fixed dispatched allocation')
    prepared=json.loads((root/'prepared.json').read_bytes())
    if tuple(seeds) not in ((22,23),(24,25)) or {r['seed'] for r in prepared['run_configs']}!=set(seeds):
        raise ValueError('not the fixed seed matrix')
    return root,launch


def start(root, job='13152', seeds=(22,23)):
    root,launch=bound(root,job,seeds);directory=Path(__file__).resolve().parent
    files={name:hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in
        ('closeout_forets_wallclock_20260912.py','readout_forets_wallclock_20260912.py','readout_forets_generation_capacity_20260912.py',
         'attribute_forets_wallclock_20260912.py')}
    write(root/'closeout-intent.json',dict(job=launch['job'],seeds=list(seeds),directory=str(directory),files=files,
        utc=dt.datetime.now(dt.timezone.utc).isoformat(),maximum_wait_seconds=14400,maximum_readout_seconds=180))
    env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','USER','LOGNAME','LANG','LC_ALL','LD_LIBRARY_PATH')}
    env.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',LITELLM_LOCAL_MODEL_COST_MAP='True',
        SLURM_CONF='/opt1/slurm/gpu-slurm.conf',LOGGING_DIR=str(root),
        MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu')
    with (root/'closeout.private.log').open('xb') as log:
        child=subprocess.Popen([sys.executable,'-B',str(directory/'closeout_forets_wallclock_20260912.py'),'run',str(root),
                                '--job',job,'--seeds',*[str(s) for s in seeds]],
            stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
    write(root/'closeout-started.json',dict(pid=child.pid,job=launch['job'],files=files))
    print(json.dumps(dict(status='SINGLE_COMPLETION_STAGE_STARTED',pid=child.pid,job=launch['job'],gpu_dispatches=0,api_requests=0)))


def run(root, job='13152', seeds=(22,23)):
    root,launch=bound(root,job,seeds);intent=json.loads((root/'closeout-intent.json').read_bytes());directory=Path(intent['directory'])
    if intent.get('seeds',[22,23])!=list(seeds):raise ValueError('completion seeds changed')
    deadline=time.monotonic()+intent['maximum_wait_seconds'];last=None
    result=dict(job=launch['job'],status='failed_closed',readout_called=False)
    try:
        while time.monotonic()<deadline:
            # Allocation-only metadata, no result/label or prediction input.
            text=subprocess.check_output(['sacct','-X','-j',launch['job'],'-nP','-o','JobIDRaw,State%32,NodeList,ElapsedRaw'],
                text=True,timeout=20).strip()
            fields=text.split('|')
            if len(fields)!=4 or fields[0]!=launch['job']:raise ValueError('ambiguous accounting record')
            state=fields[1].split()[0].rstrip('+')
            if state!=last:
                print(json.dumps(dict(job=launch['job'],allocation_state=state,utc=dt.datetime.now(dt.timezone.utc).isoformat())),flush=True)
                last=state
            if state in TERMINAL:
                if fields[2]!='gpu28':raise ValueError('unexpected allocation node')
                break
            if state not in ('PENDING','RUNNING','COMPLETING','CONFIGURING'):raise ValueError('unknown allocation state')
            time.sleep(30)
        else:raise TimeoutError('single completion stage lifetime exhausted')
        for name,digest in intent['files'].items():
            path=directory/name
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('pinned completion code changed')
        write(root/'readout-intent.json',dict(job=launch['job'],files=intent['files'],
            utc=dt.datetime.now(dt.timezone.utc).isoformat(),allocation_state=state))
        result['readout_called']=True
        process=subprocess.run([sys.executable,'-B',str(directory/'readout_forets_wallclock_20260912.py'),str(root),
                                '--seeds',*[str(s) for s in seeds]],
            capture_output=True,text=True,timeout=intent['maximum_readout_seconds'])
        with (root/'readout.private.log').open('x') as stream:stream.write(process.stdout+'\n'+process.stderr)
        result.update(readout_exit_code=process.returncode,status='verified' if process.returncode==0 else 'readout_failed_closed')
        if process.returncode==0:
            result['summary_sha256']=hashlib.sha256((root/'wallclock-summary.json').read_bytes()).hexdigest()
            result['csv_sha256']=hashlib.sha256((root/'wallclock-runs.csv').read_bytes()).hexdigest()
    except Exception as exc:
        result['error_type']=type(exc).__name__
    result['utc']=dt.datetime.now(dt.timezone.utc).isoformat();write(root/'closeout-finished.json',result)
    print(json.dumps(result),flush=True)
    # Supplemental descriptive accounting runs only after the independent
    # verified receipt exists. Failure cannot relabel or overwrite its results.
    attribute='attribute_forets_wallclock_20260912.py'
    if result['status']=='verified' and attribute in intent['files']:
        additional=dict(job=launch['job'],status='failed_closed')
        try:
            script=directory/attribute
            if hashlib.sha256(script.read_bytes()).hexdigest()!=intent['files'][attribute]:
                raise ValueError('attribution code changed')
            process=subprocess.run([sys.executable,'-B',str(script),str(root)],capture_output=True,text=True,timeout=45)
            with (root/'attribution.private.log').open('x') as stream:stream.write(process.stdout+'\n'+process.stderr)
            additional.update(exit_code=process.returncode,status='complete' if process.returncode==0 else 'failed_closed')
            if process.returncode==0:
                additional['sha256']=hashlib.sha256((root/'wallclock-attribution.json').read_bytes()).hexdigest()
        except Exception as exc:additional['error_type']=type(exc).__name__
        write(root/'attribution-finished.json',additional)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('start','run'));p.add_argument('root',type=Path)
    p.add_argument('--job',default='13152');p.add_argument('--seeds',type=int,nargs=2,default=(22,23));a=p.parse_args()
    os.umask(0o077);globals()[a.mode](a.root,job=a.job,seeds=tuple(a.seeds))
