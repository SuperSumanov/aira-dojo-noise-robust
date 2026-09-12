"""Fixed 12-kernel handshake experiment; no task code, dataset, API or model."""
import argparse
import csv
import datetime as dt
import hashlib
import json
import logging
import os
from pathlib import Path
import socket
import statistics
import sys
import time
import re

BASE=Path('/research/d7/spc/yzyang4')
SOURCE=BASE/'forets-repeat-20260912-3no2iopd/source'
CLIENT_SHA='a6c6abdca37745ce8d5137f48595a3c0e6332c113e8133b0782425b7bbb291bf'
ROOT=BASE/'forets-readiness-live-20260912-i3uww4ec'
ORDER=['old','new','new','old','old','new','new','old','old','new','new','old']


def write(path,data):
    with path.open('x') as f:json.dump(data,f,indent=2,allow_nan=False);f.write('\n')


def context():
    logging.disable(logging.CRITICAL)
    os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',
        NO_PROXY='localhost,127.0.0.1,0.0.0.0',LOGGING_DIR=str(ROOT),
        SUPERIMAGE_DIR=str(BASE/'aira-dojo/build/superimage'),MLE_BENCH_DATA_DIR=str(BASE/'mle-bench-data'),
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu')
    for name in ['DOJO_WORKER_IDENTITY_PATH','FORETS_NATIVE_RELEASE','FORETS_CURRENT_POOL_ROOT','FORETS_CLOSED_POOL_ROOT']:
        os.environ.pop(name,None)
    sys.path[:0]=[str(ROOT),str(SOURCE/'src')]
    from forets_kernel_readiness_20260912 import wait_for_ready
    from dojo.core.interpreters.jupyter.singularity_jupyter_server import SingularityJupyterServer
    return wait_for_ready,SingularityJupyterServer


def run(commit):
    if socket.gethostname().split('.')[0]!='gpu28' or not os.environ.get('SLURM_STEP_ID','').isdigit():
        raise ValueError('dedicated requested node/step required')
    wait_until=time.monotonic()+10
    while not (ROOT/'launch.json').exists() and time.monotonic()<wait_until:time.sleep(.1)
    manifest=json.loads((ROOT/'launch.json').read_text())
    if manifest['commit']!=commit or str(manifest['job'])!=os.environ['SLURM_JOB_ID']:raise ValueError('wrong launch')
    for name,sha in manifest['files'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha:raise ValueError('code drift')
    if hashlib.sha256((SOURCE/'src/dojo/core/interpreters/jupyter/jupyter_client.py').read_bytes()).hexdigest()!=CLIENT_SHA:
        raise ValueError('original client drift')
    write(ROOT/'started.json',dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),job=os.environ['SLURM_JOB_ID'],commit=commit))
    wait_for_ready,SingularityJupyterServer=context()
    image_dir=BASE/'aira-dojo/build/superimage'
    work=ROOT/'workspace';work.mkdir()
    rows=[];server=None;started=time.monotonic()
    try:
        server=SingularityJupyterServer(working_dir=work,bind_inputs_dir=None,
            superimage_directory=image_dir,superimage_version='2026-07-macos-v1',startup_timeout=90)
        client=server.get_client()
        for index,condition in enumerate(ORDER):
            if time.monotonic()-started>1800:raise TimeoutError('block budget exhausted')
            kernel=client.start_kernel('python3');row=dict(index=index,condition=condition,ready=False,marker_ok=False)
            try:
                with client.get_kernel_client(kernel) as k:
                    timer=time.monotonic()
                    row['ready']=bool(k.wait_for_ready(timeout_seconds=120) if condition=='old' else wait_for_ready(k,120))
                    row['readiness_seconds']=time.monotonic()-timer
                    if row['ready']:
                        answer=k.execute("print('FORETS_READINESS_MARKER')",timeout_seconds=10)
                        row['marker_ok']=bool(answer.is_ok and not answer.timed_out and
                            any('FORETS_READINESS_MARKER' in s for s in answer.output))
            except Exception as exc:row['error_type']=type(exc).__name__
            finally:client.delete_kernel(kernel)
            rows.append(row);write(ROOT/f'row-{index}.json',row)
            print(json.dumps(dict(index=index,completed=len(rows),planned=12)),flush=True)
        if len(rows)!=12:raise ValueError('incomplete fixed matrix')
    finally:
        if server is not None:server.stop()
    summaries=[]
    for condition in ('old','new'):
        group=[r for r in rows if r['condition']==condition]
        times=[r['readiness_seconds'] for r in group if 'readiness_seconds' in r]
        summaries.append(dict(condition=condition,kernels=len(group),ready=sum(r['ready'] for r in group),
            marker_ok=sum(r['marker_ok'] for r in group),median_handshake_seconds=statistics.median(times) if times else None,
            sample_std_seconds=statistics.stdev(times) if len(times)>1 else None))
    result=dict(job=os.environ['SLURM_JOB_ID'],commit=commit,completed=True,rows=rows,conditions=summaries,
        source_tree='54e353963a6899965896b2e8ea492207829b3cbd',client_sha256=CLIENT_SHA,
        original_image_unchanged=True,cold_starts_all_included=True,api_calls=0,task_executions=0,model_loads=0,
        candidate_reruns=0,seconds=time.monotonic()-started,utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        limitations=['Kernel startup/marker test only, not GPU compute acceptance or critic/e2e gain.',
                    'No historical failed task retried; twelve new cold kernels in a single new gateway.',
                    'If old does not fail here, this does not show a lower failure rate.'])
    write(ROOT/'result.json',result)
    with (ROOT/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=sorted(set().union(*(r.keys() for r in rows))));w.writeheader();w.writerows(rows)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--commit');p.add_argument('--root',required=True)
    p.add_argument('--check-import',action='store_true');a=p.parse_args()
    ROOT=Path(a.root).resolve(strict=True)
    if ROOT.parent!=BASE or not re.fullmatch('forets-readiness-live-20260912-[A-Za-z0-9_]+',ROOT.name):raise ValueError('root scope')
    if a.check_import:context();print('original_runtime_import_passed_no_kernel_started')
    else:run(a.commit)
