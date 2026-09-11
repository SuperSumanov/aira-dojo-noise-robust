"""All three saved DEVELOPMENT candidates, twice; no search/API/model fitting.

Remote-only candidate extraction and exact-code Jupyter execution. The separate
native wrapper uses the already verified pure GPU binding, not an old pool.
"""
from __future__ import annotations
import argparse
import csv
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import re
import sqlite3
import sys
import time

BASE=Path('/research/d7/spc/yzyang4')
SOURCE=BASE/'forets-next-config-20260911-4h_0y6b4/source'
TREE='3aae90ae26b5ae7b65e6efed14fb49f2907c9c42'
POOL=BASE/'forets-resilience-20260910-4LGN21/package/runs/01-leaf-classification-s6-critic_topk_random/checkpoint/forets-candidates-private/batch-1.sqlite'
SNAPSHOT='1d0f2e417947d195a34354e436c687f1f495da0de247cd7ada00ea8d14dfee89'
POOL_SHA='557f6233667328b4d662774f229da19a721f165137b644d69d3aedabc3eceb2e'
CODES=('7b15dedfd18395414f4118151d67ff16840ae3fb76940aaae376988fd702b5ce',
       '395bcd44075e060691629c8542f8d2a5fa56d98e5d4566e569da644f6e1521cc',
       'ff02ab9a5276cb2b0e565b9988520ad27ca20e20465d465c4dd27ad059e0cbd8')
ORDER=((0,0),(1,0),(2,0),(2,1),(1,1),(0,1))
SECRET=re.compile(r'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9a-z_-]{30,}|Bearer\s+[a-z0-9_.-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')

def digest(data):return hashlib.sha256(data).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def write(path, obj):
    with path.open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2,allow_nan=False)

def snapshot(payload, sha):
    if digest(payload.encode())!=sha or sha!=SNAPSHOT:raise ValueError('snapshot drift')
    d=json.loads(payload)
    if d['phase']!='complete' or d['pool_sha256']!=POOL_SHA:raise ValueError('incomplete pool')
    if d['binding']['task']!='leaf-classification' or d['binding']['step']!=1:raise ValueError('wrong development pool')
    cs=d['candidates']
    if len(cs)!=3:raise ValueError('candidate subset not permitted')
    for slot,c in enumerate(cs):
        code=c['node']['code']
        if digest(code.encode())!=CODES[slot] or SECRET.search(code):raise ValueError('code drift or credential shape')
        if type(c['score']) not in (float,int) or not math.isfinite(c['score']):raise ValueError('missing fixed score')
    return cs

def checked_root(root):
    root=root.resolve(strict=True)
    if root.parent!=BASE or not re.fullmatch(r'forets-closed-pool-20260911-[A-Za-z0-9]+',root.name):
        raise ValueError('new closed-pool diagnostic root required')
    return root

def prepare(root):
    if POOL.is_symlink() or POOL.with_suffix('.sqlite.lock').exists():raise ValueError('pool not read-only stable')
    with closing(sqlite3.connect(POOL.as_uri()+'?mode=ro',uri=True)) as con:
        rows=con.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchall()
    if len(rows)!=1:raise ValueError('missing pool')
    cs=snapshot(*rows[0]);codes=root/'codes';codes.mkdir(mode=0o700)
    for i,c in enumerate(cs):
        with (codes/f'{i}.py').open('xb') as f:f.write(c['node']['code'].encode())
    write(root/'plan.json',dict(role='closed_development_pool_immediate_quality_not_e2e',
        snapshot_sha256=SNAPSHOT,pool_sha256=POOL_SHA,code_sha256=CODES,order=ORDER,
        scores=[c['score'] for c in cs],top_k=2,execution_seconds=300,startup_seconds=90,
        source_tree=TREE,api_calls=0,critic_calls=0,created_utc=now()))
    print(json.dumps({'status':'prepared','programs':3,'executions':6,'api_calls':0,'snapshot_sha256':SNAPSHOT}))

def plan(root):
    p=json.loads((root/'plan.json').read_text())
    if (p['snapshot_sha256']!=SNAPSHOT or p['pool_sha256']!=POOL_SHA or tuple(p['code_sha256'])!=CODES
        or tuple(map(tuple,p['order']))!=ORDER or p['top_k']!=2 or p['execution_seconds']!=300
        or p['startup_seconds']!=90 or p['source_tree']!=TREE):raise ValueError('fixed diagnostic plan drift')
    for i,sha in enumerate(CODES):
        if digest((root/'codes'/f'{i}.py').read_bytes())!=sha:raise ValueError('code drift')
    return p

def binding_context(env):
    root=checked_root(Path(env['FORETS_CLOSED_POOL_ROOT']));plan(root)
    if env.get('FORETS_NATIVE_RELEASE') or env.get('FORETS_NATIVE_INTEGRATION_ROOT'):
        raise ValueError('ambiguous diagnostic/production mode')
    receipt=Path(env['DOJO_WORKER_IDENTITY_PATH'])
    if receipt.parent!=root or receipt.is_symlink() or not re.fullmatch(r'identity-[0-5]\.json',receipt.name):
        raise ValueError('identity outside closed diagnostic')
    claim=json.loads((root/'execution.claim.json').read_text())
    if claim['job']!=env['SLURM_JOB_ID'] or not receipt.is_file():raise ValueError('wrong allocation')
    return receipt.with_suffix('.native-binding.json')

def setup(root):
    logging.disable(logging.CRITICAL)
    # Never source .env or inject keys. Original two task env entries retained.
    os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',LOGGING_DIR=str(root),
        SUPERIMAGE_DIR=str(BASE/'aira-dojo/build/superimage'),MLE_BENCH_DATA_DIR=str(BASE/'mle-bench-data'),
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu',
        FORETS_CLOSED_POOL_ROOT=str(root),PATH=str(root/'bin')+':'+os.environ['PATH'],
        NO_PROXY='localhost,127.0.0.1,0.0.0.0')
    sys.path[:0]=[str(root),str(SOURCE/'src')]

def execute_one(root,index):
    from dojo.core.interpreters.jupyter.singularity_jupyter_server import SingularityJupyterServer
    from dojo.tasks.mlebench.evaluate import evaluate_submission
    from mlebench.grade import validate_submission
    from mlebench.registry import registry
    from forets_opencl_allowlist_20260911 import IMAGE
    slot,repeat=ORDER[index];work=root/f'work-{index}';work.mkdir()
    identity=root/f'identity-{index}.json';write(identity,{})
    os.environ['DOJO_WORKER_IDENTITY_PATH']=str(identity)
    result=dict(index=index,slot=slot,repeat=repeat,code_sha256=CODES[slot],started_utc=now(),
        source_commit=os.environ['FORETS_SOURCE_COMMIT'],source_tree=TREE,job=os.environ['SLURM_JOB_ID'],
        task='leaf-classification',original_search_seed=6,node='gpu28',allocated_gpu_count=1,allocated_cpus=6,
        code_time_limit=300,image=str(IMAGE),image_version='2026-07-macos-v1',
        status='infrastructure_error',valid=False,score=None,execution_seconds=None,
        program_device='gpu' if slot==0 else 'original_default_cpu')
    started=time.monotonic();srv=None
    try:
        code=(root/'codes'/f'{slot}.py').read_bytes()
        if digest(code)!=CODES[slot]:raise ValueError('code changed')
        srv=SingularityJupyterServer(working_dir=work,bind_inputs_dir=BASE/'mle-bench-data/leaf-classification/prepared/public',
            superimage_directory=IMAGE.parent,superimage_version='2026-07-macos-v1',startup_timeout=90,
            env={'HF_HUB_OFFLINE':'0','NLTK_DATA':'/root/.nltk_data'})
        client=srv.get_client();kernel=client.start_kernel('python3')
        with client.get_kernel_client(kernel) as k:
            if not k.wait_for_ready(timeout_seconds=10):raise TimeoutError('kernel startup')
            ts=time.monotonic();answer=k.execute(code.decode(),timeout_seconds=300)
            result['execution_seconds']=time.monotonic()-ts
            result.update(kernel_ok=bool(answer.is_ok),timed_out=bool(answer.timed_out))
            # Keep raw candidate stdout remote only; never include it in reports.
            raw='\n'.join(answer.output)
            if SECRET.search(raw):raise ValueError('credential-shaped output quarantined')
            (root/f'program-{index}.txt').write_text(raw,encoding='utf-8')
            result['output_sha256']=digest(raw.encode())
            submission=work/'submission.csv'
            if answer.timed_out:result['status']='program_timeout'
            elif not answer.is_ok:result['status']='program_error'
            elif not submission.is_file():result['status']='missing_submission'
            else:
                if submission.is_symlink():raise ValueError('submission symlink')
                result['submission_sha256']=digest(submission.read_bytes())
                competition=registry.set_data_dir(BASE/'mle-bench-data').get_competition('leaf-classification')
                valid,_=validate_submission(submission,competition)
                if valid:
                    score,report=evaluate_submission(submission,BASE/'mle-bench-data','leaf-classification',root/f'grade-{index}')
                    if score is not None and math.isfinite(float(score)):
                        result.update(status='valid',valid=True,score=float(score))
                    else:result['status']='invalid_submission'
                else:result['status']='invalid_submission'
    except Exception as exc:result['error_type']=type(exc).__name__
    finally:
        if srv is not None:
            try:srv.stop()
            except Exception as exc:result.update(status='infrastructure_error',cleanup_error=type(exc).__name__)
        result.update(wall_seconds=time.monotonic()-started,finished_utc=now())
        write(root/f'result-{index}.json',result)
        print(json.dumps({'index':index,'slot':slot,'status':result['status'],'wall_seconds':result['wall_seconds']}),flush=True)
    return result

def run(root):
    import socket
    plan(root)
    if socket.gethostname().split('.')[0]!='gpu28' or not os.environ.get('SLURM_STEP_ID','').isdigit():
        raise ValueError('requires new gpu28 step')
    if not re.fullmatch(r'[a-f0-9]{40}',os.environ.get('FORETS_SOURCE_COMMIT','')):raise ValueError('source commit absent')
    write(root/'execution.claim.json',dict(job=os.environ['SLURM_JOB_ID'],utc=now()))
    setup(root);started=time.monotonic();rows=[]
    from forets_opencl_allowlist_20260911 import IMAGE
    image_stat=IMAGE.stat()
    if (image_stat.st_size,image_stat.st_mtime_ns)!=(19717783552,1784638286000000000):
        raise ValueError('original image metadata changed')
    for index in range(6):
        if time.monotonic()-started>2700:break  # leave >=600s before allocation end
        r=execute_one(root,index);rows.append(r)
        if r['status']=='infrastructure_error':break
    write(root/'finished.json',dict(utc=now(),completed_slots=len(rows),planned=6,
        api_calls=0,critic_calls=0,role='closed_development_pool_not_e2e',seconds=time.monotonic()-started))
    return 0 if len(rows)==6 and all(r['status']!='infrastructure_error' for r in rows) else 1

def summarize(rows,scores):
    if len(rows)!=6 or {(r['slot'],r['repeat']) for r in rows}!=set(ORDER):raise ValueError('incomplete diagnostic')
    if any(r['status']=='infrastructure_error' for r in rows):raise ValueError('infrastructure invalidation')
    top=sorted(range(3),key=lambda i:(-scores[i],i))[:2]
    def arm(slots):
        subset=[r for r in rows if r['slot'] in slots];valid=[r for r in subset if r['valid']]
        return dict(slots=slots,valid_probability=len(valid)/len(subset),
            conditional_mean_logloss=sum(r['score'] for r in valid)/len(valid) if valid else None,
            n_executions=len(subset))
    return dict(role='single_development_pool_only',historical_scores=scores,top2=arm(top),uniform3=arm([0,1,2]),
        independent_search_seeds=1,no_generality_or_e2e_claim=True)

def readout(root):
    d=plan(root)
    # Match frozen scores to the original snapshot, not merely the mutable copy.
    with closing(sqlite3.connect(POOL.as_uri()+'?mode=ro',uri=True)) as con:
        original=snapshot(*con.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchone())
    if d['scores']!=[c['score'] for c in original]:raise ValueError('historical score drift')
    rows=[json.loads((root/f'result-{i}.json').read_text()) for i in range(6)]
    for i,r in enumerate(rows):
        if (r['slot'],r['repeat'])!=ORDER[i] or r['code_sha256']!=CODES[r['slot']]:raise ValueError('result binding')
    value=summarize(rows,d['scores'])
    with (root/'runs.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=sorted(set().union(*(r.keys() for r in rows))))
        writer.writeheader();writer.writerows(rows)
    write(root/'summary.json',value);print(json.dumps(value))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('prepare','run','readout'))
    p.add_argument('--root',type=Path,required=True);a=p.parse_args();root=checked_root(a.root)
    if a.mode=='prepare':prepare(root)
    elif a.mode=='run':raise SystemExit(run(root))
    else:readout(root)
