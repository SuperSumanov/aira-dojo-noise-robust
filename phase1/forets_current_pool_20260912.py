"""Conditional diagnostic: both seed11 first pools, all slots, unchanged programs.

Preparation is CPU/metadata only. Execution requires seed12 closure and an
explicit launch receipt. No API, critic invocation, fitting, or protected data.
"""
import argparse
from contextlib import closing
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import re
import socket
import sqlite3
import sys
import tempfile
import time

from forets_closed_pool_20260911 import BASE, SECRET, digest, now, write, execute_one

PARENT=BASE/'forets-review-20260912-csh5q4i8'
REPEAT=BASE/'forets-repeat-20260912-zuvnt3oa'
PREPARED='e6ec9d4c6664a98a6c069b13cb85624ece78b864adf036591ed34f4c8df18718'
TREE='6ca01fba9892a350cbb24152054b5296dc7095f1'
TASKS=('leaf-classification','spaceship-titanic')
ROLE='all_seed11_first_pools_immediate_quality_not_e2e'
ORDER=tuple((i,0) for i in range(8))


def checked_root(path):
    root=Path(path).resolve(strict=True)
    if root.parent!=BASE or not re.fullmatch('forets-current-pool-20260912-[A-Za-z0-9_-]+',root.name):
        raise ValueError('only new scoped diagnostic roots permitted')
    return root


def complete_pools():
    os.environ['SLURM_CONF']='/opt1/slurm/gpu-slurm.conf'
    sys.path.insert(0,str(PARENT/'code'))
    from forets_block_collect_20260911 import collect_metadata
    raw=(PARENT/'prepared.json').read_bytes()
    if digest(raw)!=PREPARED:raise ValueError('parent preparation changed')
    prepared=json.loads(raw);collect_metadata(PARENT,prepared)
    verification=json.loads((PARENT/'independent-final-verification.json').read_text())
    if verification['job']!='13115' or verification['source_tree']!=TREE:raise ValueError('wrong closed source')
    pools=[]
    for task in TASKS:
        matches=[r for r in prepared['run_configs'] if r['task']==task and r['arm']=='critic_topk_random']
        if len(matches)!=1:raise ValueError('pool selection ambiguous')
        run=matches[0];cfgraw=(PARENT/'configs'/(run['run_id']+'.json')).read_bytes()
        if digest(cfgraw)!=run['config_sha256']:raise ValueError('configuration changed')
        cfg=json.loads(cfgraw)
        path=PARENT/'runs'/run['run_id']/'checkpoint/forets-candidates-private/batch-1.sqlite'
        if path.is_symlink() or path.with_suffix('.sqlite.lock').exists():raise ValueError('pool not stable')
        before=digest(path.read_bytes())
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
            rows=db.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchall()
        if len(rows)!=1:raise ValueError('snapshot missing')
        raw,sha=rows[0]
        if digest(raw.encode())!=sha:raise ValueError('snapshot drift')
        pool=json.loads(raw);binding=pool['binding'];candidates=pool['candidates']
        if (pool['phase']!='complete' or len(candidates)!=4 or binding['task']!=task
            or binding['step']!=1 or binding['selection_policy']!='critic_topk_random'
            or cfg['solver']['selector_seed']!=11):raise ValueError('wrong fixed first pool')
        for c in candidates:
            if (not isinstance(c['node']['code'],str) or not c['node']['code'] or SECRET.search(c['node']['code'])
                or type(c['score']) not in (float,int) or not math.isfinite(c['score'])):
                raise ValueError('code or fixed score unavailable')
        if digest(path.read_bytes())!=before:raise ValueError('pool changed while reading')
        pools.append(dict(task=task,run_id=run['run_id'],snapshot_sha256=sha,ledger_sha256=before,
                          candidates=candidates,source_config_sha256=digest(cfgraw)))
    return pools


def prepare():
    os.umask(0o077)
    pools=complete_pools()  # do not allocate output before validating scope
    root=Path(tempfile.mkdtemp(prefix='forets-current-pool-20260912-',dir=BASE));os.chmod(root,0o700)
    (root/'codes').mkdir(mode=0o700)
    items=[];bindings=[]
    for pool in pools:
        bindings.append({k:v for k,v in pool.items() if k!='candidates'})
        for slot,candidate in enumerate(pool['candidates']):
            index=len(items);raw=candidate['node']['code'].encode()
            with (root/'codes'/f'{index}.py').open('xb') as f:f.write(raw)
            items.append(dict(index=index,task=pool['task'],pool_slot=slot,code_sha256=digest(raw),fixed_score=candidate['score']))
    value=dict(role=ROLE,created_utc=now(),source_tree=TREE,parent=str(PARENT),seed=11,
        pools=bindings,programs=items,order=ORDER,execution_seconds=300,startup_seconds=90,
        cpus=6,gpus=1,node='gpu28',maximum_gpu_hours=1.5,api_calls=0,critic_calls=0,
        condition='Only after all seed12 runs close and failure/attribution needs this diagnostic; no automatic launch.')
    write(root/'plan.private.json',value)
    receipt=dict(role=ROLE,root=str(root),plan_sha256=digest((root/'plan.private.json').read_bytes()),
        source_tree=TREE,programs=8,tasks=list(TASKS),seed=11,api_calls=0,gpu_jobs=0,
        status='PREPARED_NOT_LAUNCHABLE',created_utc=now())
    write(root/'preparation.json',receipt);print(json.dumps(receipt))


def plan(root):
    root=checked_root(root);receipt=json.loads((root/'preparation.json').read_text())
    raw=(root/'plan.private.json').read_bytes()
    if digest(raw)!=receipt['plan_sha256'] or receipt['root']!=str(root):raise ValueError('plan drift')
    p=json.loads(raw)
    if (p['role']!=ROLE or p['source_tree']!=TREE or p['execution_seconds']!=300
        or p['startup_seconds']!=90 or p['cpus']!=6 or p['gpus']!=1 or len(p['programs'])!=8
        or tuple(map(tuple,p['order']))!=ORDER):raise ValueError('wrong diagnostic')
    expected=[(task,slot) for task in TASKS for slot in range(4)]
    if [(r['task'],r['pool_slot']) for r in p['programs']]!=expected:raise ValueError('pool subset or reorder')
    for i,row in enumerate(p['programs']):
        path=root/'codes'/f'{i}.py'
        if path.is_symlink() or digest(path.read_bytes())!=row['code_sha256']:raise ValueError('program changed')
    return p


def binding_context(env):
    root=checked_root(env['FORETS_CURRENT_POOL_ROOT']);plan(root)
    if env.get('FORETS_NATIVE_RELEASE') or env.get('FORETS_CLOSED_POOL_ROOT'):raise ValueError('ambiguous mode')
    path=Path(env['DOJO_WORKER_IDENTITY_PATH'])
    if path.parent!=root or path.is_symlink() or not re.fullmatch(r'identity-[0-7]\.json',path.name):
        raise ValueError('identity outside new diagnostic')
    if json.loads((root/'execution.claim.json').read_text())['job']!=env['SLURM_JOB_ID']:
        raise ValueError('different allocation')
    return path.with_suffix('.native-binding.json')


def run(root):
    p=plan(root)
    if socket.gethostname().split('.')[0]!='gpu28' or not os.environ.get('SLURM_STEP_ID','').isdigit():
        raise ValueError('requires dedicated gpu28 step')
    launch=json.loads((root/'launch.json').read_text())
    if launch['job']!=os.environ['SLURM_JOB_ID'] or launch['plan_sha256']!=digest((root/'plan.private.json').read_bytes()):
        raise ValueError('no matching approved launch')
    # The launch decision is separate from preparation; both paired outcomes
    # must close first, but this reader never opens those outcomes itself.
    if not (REPEAT/'independent-final-verification.json').is_file():raise ValueError('seed12 not closed')
    write(root/'execution.claim.json',dict(job=os.environ['SLURM_JOB_ID'],utc=now()))
    logging.disable(logging.CRITICAL)
    os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',LOGGING_DIR=str(root),
        SUPERIMAGE_DIR=str(BASE/'aira-dojo/build/superimage'),MLE_BENCH_DATA_DIR=str(BASE/'mle-bench-data'),
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu',
        FORETS_CURRENT_POOL_ROOT=str(root),PATH=str(root/'bin')+':'+os.environ['PATH'],
        NO_PROXY='localhost,127.0.0.1,0.0.0.0')
    sys.path[:0]=[str(root),str(PARENT/'source/src')]
    from forets_opencl_allowlist_20260911 import IMAGE
    stat=IMAGE.stat()
    if (stat.st_size,stat.st_mtime_ns)!=(19717783552,1784638286000000000):raise ValueError('original image changed')
    hashes=tuple(row['code_sha256'] for row in p['programs']);started=time.monotonic();rows=[]
    for index,item in enumerate(p['programs']):
        if time.monotonic()-started>4200:break
        row=execute_one(root,index,task=item['task'],seed=11,source_tree=TREE,code_hashes=hashes,
                        order=ORDER,device_label='original_program_unchanged')
        rows.append(row)
        if row['status']=='infrastructure_error':break
    write(root/'finished.json',dict(utc=now(),role=ROLE,completed_slots=len(rows),planned=8,
        seconds=time.monotonic()-started,api_calls=0,critic_calls=0))
    return 0 if len(rows)==8 and all(r['status']!='infrastructure_error' for r in rows) else 1


def summarize(rows,programs):
    if len(rows)!=8 or {r['index'] for r in rows}!=set(range(8)):raise ValueError('incomplete diagnostic')
    if any(r['status']=='infrastructure_error' for r in rows):raise ValueError('infrastructure failure')
    for row in rows:
        if type(row['valid']) is not bool or (row['valid']!=(row['status']=='valid')):
            raise ValueError('status validity mismatch')
        if not row['valid'] and row['score'] is not None:raise ValueError('invalid score imputation')
    answer=[]
    for task in TASKS:
        items=[p for p in programs if p['task']==task]
        if len(items)!=4:raise ValueError('task subset')
        top={p['index'] for p in sorted(items,key=lambda p:(-p['fixed_score'],p['pool_slot']))[:2]}
        group=[r for r in rows if r['task']==task]
        if {r['index'] for r in group}!={p['index'] for p in items}:raise ValueError('result task binding')
        def arm(sub):
            valid=[r['score'] for r in sub if r['valid']]
            if any(not math.isfinite(s) for s in valid):raise ValueError('nonfinite score')
            return dict(executions=len(sub),valid=len(valid),valid_probability=len(valid)/len(sub),
                conditional_mean_score=sum(valid)/len(valid) if valid else None)
        answer.append(dict(task=task,metric='logloss' if task==TASKS[0] else 'accuracy',
            lower_is_better=task==TASKS[0],uniform4=arm(group),top2=arm([r for r in group if r['index'] in top])))
    return dict(role=ROLE,tasks=answer,independent_search_seeds=1,
        limitations=['Finite first-pool immediate quality only, not e2e or a free oracle.',
                    'Duplicate program slots retained; one execution each cannot estimate test-retest variation.',
                    'Conditional score means must be read alongside valid probability; no missing-score imputation.'])


def readout(root):
    import csv
    import subprocess
    p=plan(root);launch=json.loads((root/'launch.json').read_text())
    os.environ['SLURM_CONF']='/opt1/slurm/gpu-slurm.conf'
    text=subprocess.check_output(['sacct','-X','-j',launch['job'],'-nP',
        '--format=JobIDRaw,State,ElapsedRaw,AllocTRES%256'],text=True,timeout=25)
    records=[s.split('|') for s in text.splitlines() if s.strip()]
    if len(records)!=1 or records[0][0]!=launch['job'] or records[0][1]!='COMPLETED':
        raise ValueError('allocation not cleanly closed')
    job,state,elapsed,resources=records[0][:4]
    if 'gres/gpu=1' not in resources.split(','):raise ValueError('allocation GPU count')
    finished=json.loads((root/'finished.json').read_text())
    if finished['completed_slots']!=8:raise ValueError('not all diagnostic slots closed')
    rows=[json.loads((root/f'result-{i}.json').read_text()) for i in range(8)]
    for i,(r,program) in enumerate(zip(rows,p['programs'])):
        if (r['index']!=i or r['slot']!=i or r['repeat']!=0 or r['job']!=job
            or r['task']!=program['task'] or r['code_sha256']!=program['code_sha256']):
            raise ValueError('result binding mismatch')
    result=summarize(rows,p['programs']);result.update(job=job,allocation_gpu_hours=int(elapsed)/3600,utc=now())
    with (root/'runs.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=sorted(set().union(*(r.keys() for r in rows))))
        writer.writeheader();writer.writerows(rows)
    write(root/'summary.json',result);print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('prepare','run','readout'));parser.add_argument('--root')
    args=parser.parse_args()
    if args.mode=='prepare':prepare()
    elif args.mode=='run':raise SystemExit(run(checked_root(args.root)))
    else:readout(checked_root(args.root))
