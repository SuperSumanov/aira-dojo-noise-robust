"""T1: fixed old development cases, one generated repair per arm, full execution.

No protected cohort access. Full code/prompts stay remote. API and execution are
separate so allocations are not occupied during serial generation. This is a
necessary-condition development experiment, not a new e2e search result.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
from string import Template
import subprocess
import sys
import time

from prepare_repair_transfer_20260913 import BASE, ARMS, TASKS, SECRET, read, dump, encode, sha

ROOT = BASE/'forets-repair-transfer-20260913-d151en61'
SELECTION_SHA = '48605345d740b81f50b387cae3368269a6d2449ff8c665e024c2aec7a1ba94ca'
PARENT = BASE/'forets-wallclock-20260912-103zf3nb'
SOURCE = PARENT/'source'
TREE = '746d97a67922896b7d1581c4689f8b5f85204d30'
OLD_AUTH = '0b4e20837991c8ec3f9cb16116170c62b1e0897e732c9b1e62ffb1eaa8db5b4c'
OLD_COUNTS = (1755, 6302127386, 4902127386, 2)
ADAPTER = BASE/'forets-current-pool-20260912-0hz06xtj'
HELPERS = ('forets_closed_pool_native_20260911.py','forets_current_pool_native_20260912.py',
    'forets_gpu_binding_20260911.py','forets_native_cuda_identity_20260911.py',
    'forets_native_gpu_binding_20260911.py','forets_opencl_allowlist_20260911.py',
    'forets_opencl_readonly_ab.py','bin/singularity')
FILES = ('run_repair_transfer_20260913.py','prepare_repair_transfer_20260913.py',
    'forets_paid_budget_20260911.py','forets_paid_route_20260911.py',
    'forets_closed_pool_20260911.py','readout_repair_transfer_20260913.py','FORETS_CLAIM_PROGRAM_20260913.md')


def now(): return datetime.now(timezone.utc).isoformat()
def public_budget(b): return {k:v for k,v in b.items() if k != 'scopes'}


def inputs():
    p = read(ROOT/'selection-public.json', SELECTION_SHA)
    if p['status'] != 'PREPARED' or p['cases'] != 8 or p['planned_calls'] != 24:
        raise ValueError('exact selection required')
    return p, read(ROOT/'inputs.private.json',p['private_sha256'])['rows']


def source_check():
    a = read(PARENT/'artifact.json')
    if a['source_tree'] != TREE: raise ValueError('source identity')
    for n,h in a['source_files'].items():
        if sha((SOURCE/n).read_bytes()) != h: raise ValueError('source file drift')


def counts(db):
    return tuple(db.execute('SELECT COUNT(*),SUM(held),SUM(COALESCE(cost,0)),SUM(state="unresolved") FROM calls').fetchone())


def payload_for(row, cfg, instructions, description):
    from jinja2 import Environment, StrictUndefined
    s=cfg['solver']; op=s['operators']['debug']
    values=dict(task_desc=instructions+'\n'+description, hardware='one NVIDIA RTX 3090, 6 CPU cores',
        prev_buggy_code='```python\n'+row['code']+'\n```',execution_output='```\n'+row['error']+'\n```',
        time_remaining='5 minutes',steps_remaining=1,execution_timeout='5 minutes',other_remarks=None,
        packages=', '.join('`'+x+'`' for x in sorted(s['available_packages'])),
        memory=row['memory'] or None,data_overview='(No data preview available)')
    env=Environment(undefined=StrictUndefined)
    messages=[]
    for role,key in [('system','system_message_prompt_template'),('user','init_user_message_prompt_template')]:
        spec=op[key]
        text=env.from_string(spec['template']).render(**{**(spec.get('partial_variables') or {}),**values})
        messages.append(dict(role=role,content=text))
    # Same frozen original debug wording for all arms, same strict output tool.
    tool=dict(type='function',function=dict(name='emit_repair',description='Return the complete corrected Python implementation.',
        parameters=dict(type='object',additionalProperties=False,required=['code'],properties=dict(code=dict(type='string')))))
    import forets_paid_budget_20260911 as b
    payload=dict(model=b.MODEL,provider=b.PROVIDER,stream=False,messages=messages,tools=[tool],
        tool_choice=dict(type='function',function=dict(name='emit_repair')),max_tokens=8192,
        temperature=0,top_p=1,seed=row['seed'])
    raw=encode(payload)
    # Byte-level conservative input bound + 8192 output tokens fits $0.10 at
    # catalog ceilings; 2000 additional tokenizer/template tokens are allowed.
    if len(raw)>100000 or SECRET.search(raw.decode()): raise ValueError('context cap or credential shape')
    return payload


def prepare(commit):
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('commit required')
    p, rows=inputs();source_check()
    with closing(sqlite3.connect((PARENT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('SELECT digest,stopped FROM auth').fetchall()!=[(OLD_AUTH,0)] or counts(db)!=OLD_COUNTS:
            raise ValueError('closed predecessor ledger changed')
        old_body=json.loads(db.execute('SELECT body FROM auth').fetchone()[0])
        journal_mode=db.execute('PRAGMA journal_mode').fetchone()[0]
    finish=read(PARENT/'readout-finished.json')
    if finish['status']!='verified':raise ValueError('predecessor not closed')
    manifest=read(PARENT/'prepared.json')
    candidates=[r for r in manifest['run_configs'] if r['arm']=='no_memory']
    cfgs={r['task']:read(PARENT/'configs'/(r['run_id']+'.json')) for r in candidates}
    instructions=(SOURCE/'src/dojo/tasks/mlebench/instructions.txt').read_text()
    instructions=Template(instructions).substitute(HARDWARE='one NVIDIA RTX 3090, 6 CPU cores',
        TIME_LIMIT='7 minutes (one repair generation plus one complete program execution)',STEP_LIMIT='1')
    if re.search(r'\$\{?[A-Z_][A-Z_0-9]*',instructions):raise ValueError('unresolved task instruction environment')
    rendered=[]
    (ROOT/'requests').mkdir()
    for index,row in enumerate(rows):
        description=(BASE/'mle-bench-data'/row['task']/'prepared/public/description.md').read_text()
        payload=payload_for(row,cfgs[row['task']],instructions,description)
        digest=dump(ROOT/'requests'/f'{index}.private.json',payload)
        rendered.append(dict(index=index,case=row['case'],task=row['task'],arm=row['arm'],
            seed=row['seed'],request_sha256=digest,request_bytes=len(encode(payload)),
            target_code_sha256=row['code_sha256'],memory_diff_sha256=row['memory_diff_sha256']))
    for name in FILES:shutil.copy2(Path(__file__).with_name(name),ROOT/name)
    auth=dict(old_body,version=20,experiment='run_disjoint_three_arm_repair_transfer_T1',
        predecessor_authorization=OLD_AUTH,predecessor_accounted=OLD_COUNTS[1],predecessor_settled=OLD_COUNTS[2],
        predecessor_calls=OLD_COUNTS[0],predecessor_unresolved=2,total=OLD_COUNTS[1]+2400000000,
        incremental_cap=2400000000,reservation=100000000,logical_request_cap=24,output_tokens=8192,
        input_payload_byte_limit=100000,max_concurrent_generator_requests=1)
    if auth['total']>10**10:raise ValueError('original cumulative cap')
    dump(ROOT/'authorization.json',auth)
    files={n:sha((ROOT/n).read_bytes()) for n in FILES}
    result=dict(commit=commit,utc=now(),source_tree=TREE,selection_sha256=SELECTION_SHA,rows=rendered,
        private_input_sha256=p['private_sha256'],authorization_sha256=sha((ROOT/'authorization.json').read_bytes()),
        files=files,predecessor_journal_mode=journal_mode,predecessor_counts=OLD_COUNTS,
        target_ast_unique=len({r['ast_sha256'] for r in rows}),target_runs=len({(r['root'],r['run_id']) for r in rows}),
        coincident_memory_cases=sum(rows[3*i+next(j for j in range(3) if rows[3*i+j]['arm']=='retrieved_repair')]['memory_diff_sha256']==
                                    rows[3*i+next(j for j in range(3) if rows[3*i+j]['arm']=='random_repair')]['memory_diff_sha256'] for i in range(8)))
    digest=dump(ROOT/'prepared.json',result)
    print(json.dumps(dict(prepared_sha256=digest,commit=commit,rows=len(rendered),target_runs=result['target_runs'],
        target_ast_unique=result['target_ast_unique'],max_request_bytes=max(r['request_bytes'] for r in rendered),
        coincident_memory_cases=result['coincident_memory_cases'],predecessor_journal_mode=journal_mode)))


def checked():
    p=read(ROOT/'prepared.json')
    for n,h in p['files'].items():
        if sha((ROOT/n).read_bytes())!=h:raise ValueError('frozen worker drift')
    if p['selection_sha256']!=SELECTION_SHA or p['source_tree']!=TREE:raise ValueError('frozen input drift')
    read(ROOT/'inputs.private.json',p['private_input_sha256'])
    read(ROOT/'authorization.json',p['authorization_sha256'])
    return p


def budget_module():
    import forets_paid_budget_20260911 as b
    b.AUTH=read(ROOT/'authorization.json');b.RESERVE=b.AUTH['reservation']
    b.AUTH_RAW=json.dumps(b.AUTH,sort_keys=True,separators=(',',':')).encode();b.AUTH_SHA=sha(b.AUTH_RAW)
    return b


def activate():
    checked();b=budget_module()
    dump(ROOT/'handover-intent.json',dict(utc=now(),old_authorization=OLD_AUTH,new_authorization=b.AUTH_SHA))
    fd=os.open(ROOT/'paid.sqlite',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    with closing(sqlite3.connect(ROOT/'paid.sqlite')) as db:
        db.execute('ATTACH DATABASE ? AS predecessor',(str(PARENT/'paid.sqlite'),))
        if db.execute('PRAGMA predecessor.journal_mode').fetchone()[0]!='delete':
            raise ValueError('atomic multi-file handover requires delete journal; no mutation')
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT digest,stopped FROM predecessor.auth').fetchall()!=[(OLD_AUTH,0)]:raise ValueError('prior auth')
        old=db.execute('SELECT * FROM predecessor.calls').fetchall()
        actual=(len(old),sum(x[2] for x in old),sum(x[3] or 0 for x in old),sum(x[4]=='unresolved' for x in old))
        if actual!=OLD_COUNTS:raise ValueError('prior counts')
        db.execute('CREATE TABLE auth(digest TEXT NOT NULL,body TEXT NOT NULL,stopped INTEGER NOT NULL)')
        db.execute('CREATE TABLE scopes(scope TEXT PRIMARY KEY,cap INTEGER NOT NULL)')
        db.execute('CREATE TABLE calls(id TEXT PRIMARY KEY,scope TEXT NOT NULL,held INTEGER NOT NULL,cost INTEGER,state TEXT NOT NULL,created REAL NOT NULL)')
        db.execute('INSERT INTO auth VALUES(?,?,0)',(b.AUTH_SHA,b.AUTH_RAW.decode()))
        db.executemany('INSERT INTO calls VALUES(?,?,?,?,?,?)',old)
        db.executemany('INSERT INTO scopes VALUES(?,0)',[(x,) for x in sorted({r[1] for r in old})])
        db.executemany('INSERT INTO scopes VALUES(?,?)',[(f'transfer_case_{i}',300000000) for i in range(8)])
        db.execute('UPDATE predecessor.auth SET stopped=1');db.commit()
    state=public_budget(b.snapshot(ROOT/'paid.sqlite'))
    dump(ROOT/'activated.json',dict(utc=now(),billing=state));print(json.dumps(state))


def parse_code(raw):
    import ast
    choices=raw.get('choices')
    if not isinstance(choices,list) or len(choices)!=1 or choices[0].get('finish_reason') not in ('tool_calls','stop'):
        raise ValueError('incomplete completion')
    calls=choices[0].get('message',{}).get('tool_calls')
    if not isinstance(calls,list) or len(calls)!=1 or calls[0]['function']['name']!='emit_repair':raise ValueError('tool schema')
    result=json.loads(calls[0]['function']['arguments'])
    if set(result)!={'code'} or not isinstance(result['code'],str) or not result['code'].strip():raise ValueError('code schema')
    if SECRET.search(result['code']):raise ValueError('credential shape')
    ast.parse(result['code'])
    return result['code']


def generate():
    import httpx
    from dotenv import dotenv_values
    from forets_paid_route_20260911 import catalog_valid
    p=checked();b=budget_module();source_check()
    if not (ROOT/'activated.json').exists():raise ValueError('activate first')
    dump(ROOT/'generation.claim.json',dict(utc=now(),pid=os.getpid(),commit=p['commit']))
    credential=dotenv_values(BASE/'aira-dojo/.env',interpolate=False).get('OPENROUTER_API_KEY')
    if not credential:raise ValueError('known remote OpenRouter entry absent')
    (ROOT/'codes').mkdir();completed=[];started=time.monotonic()
    with httpx.Client(timeout=120,follow_redirects=False) as client:
        response=client.get('https://openrouter.ai/api/v1/models/'+b.MODEL+'/endpoints',timeout=30)
        response.raise_for_status();catalog=catalog_valid(response.json())
        dump(ROOT/'catalog.json',dict(catalog,utc=now()))
        for row in p['rows']:
            index=row['index'];payload=read(ROOT/'requests'/f'{index}.private.json',row['request_sha256'])
            if len(encode(payload))>100000:raise ValueError('payload price bound')
            attempt=f'T1-case{row["case"]}-{row["arm"]}-attempt1';t=time.monotonic()
            record=dict(index=index,case=row['case'],task=row['task'],arm=row['arm'],seed=row['seed'],status='not_dispatched',request_sha256=row['request_sha256'])
            try:
                b.reserve(ROOT/'paid.sqlite',f'transfer_case_{row["case"]}',attempt)
                record['status']='unresolved'
                response=client.post('https://openrouter.ai/api/v1/chat/completions',json=payload,headers={'Authorization':'Bearer '+credential})
                response.raise_for_status();raw=response.json()
                record['cost_usd']=b.settle(ROOT/'paid.sqlite',attempt,raw.get('usage'))
                # Never print provider errors, prompts, credentials or raw content.
                if SECRET.search(encode(raw).decode()):
                    record['status']='security_stop';raise ValueError('credential-shaped response')
                record['response_sha256']=dump(ROOT/f'response-{index}.private.json',raw)
                record['status']='format_or_syntax_failure'
                code=parse_code(raw)
                with (ROOT/'codes'/f'{index}.py').open('xb') as stream:stream.write(code.encode())
                record.update(status='generated',code_sha256=sha(code.encode()))
                record['usage']={k:raw.get('usage',{}).get(k) for k in ('prompt_tokens','completion_tokens','total_tokens')}
            except Exception as exc:
                record['error_type']=type(exc).__name__
            record['seconds']=time.monotonic()-t;dump(ROOT/f'generated-{index}.json',record);completed.append(record)
            print(json.dumps(dict(index=index,status=record['status'],completed=len(completed))),flush=True)
            state=public_budget(b.snapshot(ROOT/'paid.sqlite'))
            if state['stopped'] or state['unresolved']!=2 or record['status'] in ('not_dispatched','security_stop'):break
    state=public_budget(b.snapshot(ROOT/'paid.sqlite'))
    result=dict(utc=now(),planned=24,completed=len(completed),generated=sum(r['status']=='generated' for r in completed),
        complete=len(completed)==24 and not state['stopped'] and state['unresolved']==2,
        billing=state,seconds=time.monotonic()-started)
    dump(ROOT/'generation-finished.json',result);print(json.dumps(result),flush=True)


def binding_context(env):
    work=Path(env['FORETS_CURRENT_POOL_ROOT']).resolve(strict=True)
    if work.parent!=ROOT or work.name not in ('block-0','block-1'):raise ValueError('execution root')
    identity=Path(env['DOJO_WORKER_IDENTITY_PATH'])
    if identity.parent!=work or identity.is_symlink() or not re.fullmatch(r'identity-\d+\.json',identity.name):raise ValueError('identity path')
    if read(work/'execution.claim.json')['job']!=env['SLURM_JOB_ID']:raise ValueError('allocation binding')
    return identity.with_suffix('.native-binding.json')


def gpu_prepare():
    p=checked();finished=read(ROOT/'generation-finished.json')
    if not finished['complete']:raise ValueError('generation not cleanly complete')
    donor=read(ADAPTER/'submit-intent.json')
    for block,task in enumerate(TASKS):
        work=ROOT/f'block-{block}';work.mkdir();(work/'codes').mkdir()
        rows=[]
        for row in p['rows']:
            if row['task']!=task:continue
            generated=read(ROOT/f'generated-{row["index"]}.json')
            if generated['status']!='generated':continue
            i=len(rows);code=(ROOT/'codes'/f'{row["index"]}.py').read_bytes()
            if sha(code)!=generated['code_sha256']:raise ValueError('generated code drift')
            with (work/'codes'/f'{i}.py').open('xb') as stream:stream.write(code)
            rows.append(dict(row,local_index=i,code_sha256=sha(code)))
        for name in HELPERS:
            raw=(ADAPTER/name).read_bytes()
            if sha(raw)!=donor['code_sha256'][name]:raise ValueError('native adapter drift')
            dest=work/name;dest.parent.mkdir(exist_ok=True,parents=True);shutil.copy2(ADAPTER/name,dest)
        for name in ('run_repair_transfer_20260913.py','prepare_repair_transfer_20260913.py','forets_closed_pool_20260911.py'):
            shutil.copy2(ROOT/name,work/name)
        with (work/'forets_current_pool_20260912.py').open('x') as stream:stream.write('from run_repair_transfer_20260913 import binding_context\n')
        (work/'opencl-vendors').mkdir()
        with (work/'opencl-vendors/nvidia.icd').open('x') as stream:stream.write('libnvidia-opencl.so.1\n')
        script='''#!/bin/bash
#SBATCH --job-name=repair-transfer-T1
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --time=02:00:00
#SBATCH --no-requeue
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1
srun --exclusive --ntasks=1 --cpus-per-task=6 --gres=gpu:1 --time=01:58:00 timeout --signal=TERM --kill-after=10s 7000s /research/d7/spc/yzyang4/venvs/aira/bin/python -B "$(dirname "$0")/run_repair_transfer_20260913.py" execute --block BLOCK
'''.replace('BLOCK',str(block))
        # sbatch spools $0 elsewhere; bind the frozen explicit workspace instead.
        script=script.replace('"$(dirname "$0")/run_repair_transfer_20260913.py"',str(work/'run_repair_transfer_20260913.py'))
        with (work/'run.sbatch').open('x') as stream:stream.write(script)
        files={str(x.relative_to(work)):sha(x.read_bytes()) for x in work.rglob('*') if x.is_file()}
        dump(work/'prepared.json',dict(commit=p['commit'],source_tree=TREE,task=task,block=block,rows=rows,files=files))
    print(json.dumps(dict(gpu_blocks=2,max_gpu_hours=4,generated=finished['generated'])))


def gpu_checked(block):
    if block not in (0,1):raise ValueError('block')
    work=ROOT/f'block-{block}';p=read(work/'prepared.json')
    for n,h in p['files'].items():
        if sha((work/n).read_bytes())!=h:raise ValueError('execution files drift')
    return work,p


def submit(block):
    checked();work,p=gpu_checked(block);source_check()
    if not p['rows']:raise ValueError('no executable programs; do not request GPU')
    env={**os.environ,'SLURM_CONF':'/opt1/slurm/gpu-slurm.conf'}
    queue=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i %j %T'],env=env,text=True,timeout=25)
    if len(queue.splitlines())>=4:raise ValueError('job quota')
    command=['sbatch','--parsable','--chdir='+str(work),'--output='+str(work/'allocation-%j.out'),'--error='+str(work/'allocation-%j.err'),str(work/'run.sbatch')]
    intent=dict(utc=now(),commit=p['commit'],prepared_sha256=sha((work/'prepared.json').read_bytes()),command=command)
    dump(work/'submit-intent.json',intent)
    result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=25,check=True)
    job=result.stdout.strip().split(';')[0]
    if not job.isdigit():raise ValueError('ambiguous submission; no retry')
    dump(work/'launch.json',dict(intent,job=job));print(json.dumps(dict(block=block,job=job,programs=len(p['rows']))))


def execute(block):
    checked();work,p=gpu_checked(block);source_check()
    if socket.gethostname().split('.')[0]!='gpu28' or not os.environ.get('SLURM_STEP_ID','').isdigit():raise ValueError('dedicated gpu28 step')
    for _ in range(100):
        if (work/'launch.json').exists():break
        time.sleep(.1)
    launch=read(work/'launch.json')
    if launch['job']!=os.environ['SLURM_JOB_ID'] or launch['prepared_sha256']!=sha((work/'prepared.json').read_bytes()):raise ValueError('launch mismatch')
    dump(work/'execution.claim.json',dict(job=launch['job'],utc=now()))
    logging.disable(logging.CRITICAL)
    for name in ('FORETS_NATIVE_RELEASE','FORETS_CLOSED_POOL_ROOT','OPENROUTER_API_KEY','PRIMARY_KEY'):os.environ.pop(name,None)
    os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',LOGGING_DIR=str(work),
        SUPERIMAGE_DIR=str(BASE/'aira-dojo/build/superimage'),MLE_BENCH_DATA_DIR=str(BASE/'mle-bench-data'),
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu',
        FORETS_SOURCE_COMMIT=p['commit'],FORETS_CURRENT_POOL_ROOT=str(work),PATH=str(work/'bin')+':'+os.environ['PATH'],
        NO_PROXY='localhost,127.0.0.1,0.0.0.0')
    sys.path[:0]=[str(work),str(SOURCE/'src')]
    from forets_closed_pool_20260911 import execute_one
    from forets_opencl_allowlist_20260911 import IMAGE
    st=IMAGE.stat()
    if (st.st_size,st.st_mtime_ns)!=(19717783552,1784638286000000000):raise ValueError('original image drift')
    start=time.monotonic();done=[];stop='matrix_complete'
    for row in p['rows']:
        if time.monotonic()-start>6300:stop='bounded_time_stop';break
        result=execute_one(work,row['local_index'],task=row['task'],seed=row['seed'],source_tree=TREE,
            code_hashes=tuple(r['code_sha256'] for r in p['rows']),order=tuple((i,0) for i in range(len(p['rows']))),
            device_label='original_generated_program_device',ready_timeout=120)
        done.append(result)
        if result['status']=='infrastructure_error':stop='infrastructure_stop_no_retry';break
    dump(work/'execution-finished.json',dict(utc=now(),job=launch['job'],planned=len(p['rows']),completed=len(done),
        complete=len(done)==len(p['rows']) and stop=='matrix_complete',stop_reason=stop,seconds=time.monotonic()-start))
    return 0 if stop=='matrix_complete' else 1


if __name__=='__main__':
    os.umask(0o077)
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('prepare','activate','generate','gpu_prepare','submit','execute'))
    parser.add_argument('--commit');parser.add_argument('--block',type=int);args=parser.parse_args()
    if args.mode=='prepare':prepare(args.commit)
    elif args.mode=='submit':submit(args.block)
    elif args.mode=='execute':raise SystemExit(execute(args.block))
    else:globals()[args.mode]()
