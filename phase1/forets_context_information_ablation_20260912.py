"""Frozen two-pool, same-model information-package contrast; no task execution."""
import argparse
from contextlib import closing
from decimal import Decimal
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import sqlite3
import subprocess
import tempfile

from forets_context_judge_20260912 import (
    BASE, MODEL, PROVIDER, RESERVE, INCREMENT, SECRET, SYSTEM, TASKS,
    checked_catalog, digest, now, remap, write)

POOL=BASE/'forets-current-pool-20260912-0hz06xtj'
POOL_SHA='6bbe805e1113bbd7d899914178da79ef773ae8ae5f1306ba645066c397c0f02c'
PARENT=BASE/'forets-repeat-20260912-3no2iopd'
PARENT_AUTH='c623a0236a59df74f9dac1f3641ea724c9f2fdece7266c23aa604e6aaab1bb5e'
DEPS=('forets_context_judge_20260912.py','forets_paid_budget_20260911.py','forets_environment_context_20260912.py')


def payloads(task,description,codes):
    from forets_environment_context_20260912 import CONTEXT
    if task not in TASKS or len(codes)!=4:raise ValueError('exact task/full pool required')
    conditions=('full','omitted') if task==TASKS[0] else ('omitted','full')
    result=[]
    for condition in conditions:
        for order in ((0,1,2,3),(3,2,1,0)):
            context=dict(task=task,public_task_description=description,
                candidates=[dict(displayed_index=i,code=codes[s]) for i,s in enumerate(order)])
            if condition=='full':
                context.update(verified_shared_environment=CONTEXT,
                    resources=dict(cpu_cores=6,gpu='one RTX3090',program_wall_limit_seconds=300,
                        time_limit_includes='preprocessing, model fitting, validation and writing submission.csv',
                        image='unchanged MLE-bench 2026-07-macos-v1'))
            messages=[dict(role='system',content=SYSTEM),dict(role='user',content=json.dumps(context))]
            if len(json.dumps(messages).encode())>500000:raise ValueError('fixed input envelope exceeded')
            payload=dict(model=MODEL,messages=messages,provider=PROVIDER,temperature=0,top_p=1,max_tokens=8192,
                stream=False,response_format=dict(type='json_schema',json_schema=dict(name='candidate_ranking',strict=True,
                    schema=dict(type='object',properties=dict(ranking=dict(type='array',items=dict(type='integer'))),
                        required=['ranking'],additionalProperties=False))))
            result.append((dict(task=task,condition=condition,display_order=order),payload))
    return result


def top2(ranks):
    if len(ranks)!=2 or any(sorted(r)!=[0,1,2,3] for r in ranks):raise ValueError('two full rankings required')
    return sorted(range(4),key=lambda slot:(sum(r.index(slot) for r in ranks),slot))[:2]


def prepare(commit):
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('exact commit required')
    raw=(POOL/'plan.private.json').read_bytes()
    if digest(raw)!=POOL_SHA:raise ValueError('pool drift')
    plan=json.loads(raw)
    if [(p['task'],p['pool_slot']) for p in plan['programs']]!=[(t,s) for t in TASKS for s in range(4)]:
        raise ValueError('pool subset/order differs')
    if (POOL/'summary.json').exists():raise ValueError('new complete-pool outcomes already opened')
    root=Path(tempfile.mkdtemp(prefix='forets-information-ablation-20260912-',dir=BASE));os.chmod(root,0o700)
    items=[]
    for task in TASKS:
        desc=(BASE/'mle-bench-data'/task/'prepared/public/description.md').read_bytes();codes=[]
        if SECRET.search(desc):raise ValueError('unsafe public task document')
        for row in plan['programs']:
            if row['task']!=task:continue
            code=(POOL/'codes'/f"{row['index']}.py").read_bytes()
            if digest(code)!=row['code_sha256'] or SECRET.search(code):raise ValueError('unsafe or changed code')
            codes.append(code.decode())
        for item,payload in payloads(task,desc.decode(),codes):
            index=len(items);write(root/f'request-{index}.private.json',payload)
            items.append(item|dict(index=index,request_sha256=digest((root/f'request-{index}.private.json').read_bytes()),
                description_sha256=digest(desc)))
    prepared=dict(root=str(root),utc=now(),controller_commit=commit,script_sha256=digest(Path(__file__).read_bytes()),
        dependencies={n:digest(Path(__file__).with_name(n).read_bytes()) for n in DEPS},requests=items,
        pool_plan_sha256=POOL_SHA,api_calls=0,gpu_jobs=0,task_executions=0,
        new_pool_outcomes_read=False,incremental_cap_nano=INCREMENT)
    write(root/'prepared.json',prepared);print(json.dumps(prepared))


def checked(root,commit):
    root=Path(root).resolve(strict=True)
    if root.parent!=BASE or not re.fullmatch('forets-information-ablation-20260912-[a-z0-9_]+',root.name):raise ValueError('root scope')
    p=json.loads((root/'prepared.json').read_text())
    if p['root']!=str(root) or p['controller_commit']!=commit or p['script_sha256']!=digest(Path(__file__).read_bytes()):
        raise ValueError('controller/root drift')
    if digest((POOL/'plan.private.json').read_bytes())!=POOL_SHA:raise ValueError('pool drift')
    for name,sha in p['dependencies'].items():
        if digest(Path(__file__).with_name(name).read_bytes())!=sha:raise ValueError('dependency drift')
    expected=[(t,c,list(o)) for t in TASKS for c in (('full','omitted') if t==TASKS[0] else ('omitted','full'))
              for o in ((0,1,2,3),(3,2,1,0))]
    if [(i['task'],i['condition'],i['display_order']) for i in p['requests']]!=expected:raise ValueError('request matrix drift')
    for index,item in enumerate(p['requests']):
        if item['index']!=index or digest((root/f'request-{index}.private.json').read_bytes())!=item['request_sha256']:
            raise ValueError('request drift')
    return root,p


def transfer_budget(root):
    spec=importlib.util.spec_from_file_location('information_budget',Path(__file__).with_name('forets_paid_budget_20260911.py'))
    budget=importlib.util.module_from_spec(spec);spec.loader.exec_module(budget)
    proof=json.loads((PARENT/'independent-context-verification.json').read_text())
    if (proof['verification'],proof['job'],proof['seed'])!=('passed','13128',15):raise ValueError('parent unverified')
    with closing(sqlite3.connect((PARENT/'paid.sqlite').as_uri()+'?mode=rw',uri=True)) as old:
        old.execute('BEGIN IMMEDIATE')
        if old.execute('SELECT digest,stopped FROM auth').fetchall()!=[(PARENT_AUTH,0)]:raise ValueError('parent already sealed or drifted')
        rows=old.execute('SELECT * FROM calls ORDER BY id').fetchall()
        held=sum(r[2] for r in rows);settled=sum(r[3] or 0 for r in rows);unknown=sum(r[4]=='unresolved' for r in rows)
        if (Decimal(str(proof['cumulative_settled_usd']))*10**9!=settled or
            Decimal(str(proof['cumulative_accounted_usd']))*10**9!=held or unknown!=2):raise ValueError('verified liabilities differ')
        if held+INCREMENT>10_000_000_000:raise ValueError('original campaign cap insufficient')
        if (root/'paid.sqlite').exists():raise ValueError('new ledger exists; no repeat')
        old.execute('UPDATE auth SET stopped=1');old.commit()
        with closing(sqlite3.connect(root/'paid.sqlite')) as new:old.backup(new)
    budget.MODEL=MODEL;budget.RESERVE=RESERVE;budget.PROVIDER=PROVIDER
    budget.AUTH=dict(budget.AUTH,version=10,total=held+INCREMENT,model=MODEL,provider=PROVIDER,reservation=RESERVE,
        incremental_cap=INCREMENT,predecessor_authorization=PARENT_AUTH,predecessor_accounted=held,
        predecessor_settled=settled,predecessor_calls=len(rows),predecessor_unresolved=unknown,
        experiment='fixed-full-pool-information-ablation',logical_request_cap=8,run_limit=INCREMENT,
        accounted_cny_ceiling=str(Decimal(held+INCREMENT)/10**9*Decimal('8.8')))
    budget.AUTH_RAW=json.dumps(budget.AUTH,sort_keys=True,separators=(',',':')).encode();budget.AUTH_SHA=digest(budget.AUTH_RAW)
    with closing(sqlite3.connect(root/'paid.sqlite')) as new:
        new.execute('UPDATE auth SET digest=?,body=?,stopped=0',(budget.AUTH_SHA,budget.AUTH_RAW.decode()))
        new.execute('UPDATE scopes SET cap=COALESCE((SELECT SUM(held) FROM calls WHERE calls.scope=scopes.scope),0)')
        new.executemany('INSERT INTO scopes VALUES (?,?)',[(f'information-{i}',INCREMENT) for i in range(8)])
        new.commit()
        if new.execute('SELECT * FROM calls ORDER BY id').fetchall()!=rows:raise ValueError('carried history differs')
    write(root/'authorization.json',budget.AUTH)
    write(root/'parent-seal.json',dict(parent=str(PARENT),authorization=PARENT_AUTH,calls=len(rows),
        settled_nano=settled,accounted_nano=held,unresolved=unknown,calls_sha256=digest(json.dumps(rows).encode())))
    return budget


def run(root,commit):
    import requests
    from dotenv import dotenv_values
    root,p=checked(root,commit)
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    if subprocess.check_output(['sacct','-X','-j','13128','-nP','--format=JobIDRaw,State'],text=True,env=env,timeout=25).strip()!='13128|COMPLETED':
        raise ValueError('seed15 must be fully closed')
    if (POOL/'summary.json').exists():raise ValueError('diagnostic already unblinded')
    key=dotenv_values(BASE/'aira-dojo/.env',interpolate=False).get('OPENROUTER_API_KEY')
    if not key:raise ValueError('remote credential unavailable')
    with requests.Session() as session:
        r=session.get('https://openrouter.ai/api/v1/models/'+MODEL+'/endpoints',timeout=(10,30),allow_redirects=False)
        r.raise_for_status();write(root/'catalog.json',checked_catalog(r.json()))
        write(PARENT/'information-handover-intent.json',dict(root=str(root),utc=now(),requests=8,incremental_cap_nano=INCREMENT))
        write(root/'run-intent.json',dict(utc=now(),controller_commit=commit))
        budget=transfer_budget(root);records=[]
        for item in p['requests']:
            index=item['index'];scope=f'information-{index}';dispatched=False
            record=item|dict(status='not_sent',utc=now())
            try:
                budget.reserve(root/'paid.sqlite',scope,scope);dispatched=True
                def expired(signum,frame):raise TimeoutError('fixed 120-second request limit')
                handler=signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,120)
                try:
                    response=session.post('https://openrouter.ai/api/v1/chat/completions',
                        json=json.loads((root/f'request-{index}.private.json').read_text()),
                        headers={'Authorization':'Bearer '+key},timeout=(10,120),allow_redirects=False)
                finally:
                    signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,handler)
                response.raise_for_status();data=response.json();raw=response.content
                cost=budget.settle(root/'paid.sqlite',scope,data.get('usage'))
                if SECRET.search(raw):raise ValueError('credential-shaped response quarantined')
                with (root/f'response-{index}.private.json').open('xb') as f:f.write(raw)
                if data.get('model')!=MODEL or str(data.get('provider','')).lower()!='alibaba':raise ValueError('wrong route')
                choices=data.get('choices',[])
                if len(choices)!=1 or choices[0].get('finish_reason')!='stop':raise ValueError('incomplete response')
                rank=remap(json.loads(choices[0]['message']['content']),item['display_order'])
                write(root/f'ranking-{index}.private.json',dict(original_slot_ranking=rank,response_sha256=digest(raw)))
                record.update(status='ranked',settled_usd=cost,provider_confirmed='Alibaba',model=MODEL)
            except Exception as exc:
                record.update(status='failed_after_dispatch' if dispatched else 'not_sent',error_type=type(exc).__name__)
            records.append(record);write(root/f'receipt-{index}.json',record);print(json.dumps(record),flush=True)
            if record['status']!='ranked':break
        finished=dict(utc=now(),root=str(root),requests=records,complete=len(records)==8 and all(r['status']=='ranked' for r in records),
            billing=budget.snapshot(root/'paid.sqlite'),api_calls=len(records),gpu_jobs=0,task_executions=0,
            ranking_values_exported=False,new_pool_outcomes_read=False,protected_cohort_read=False,controller_commit=commit)
        write(root/'finished.json',finished);print(json.dumps(finished))


def readout(root,commit):
    root,p=checked(root,commit);finish=json.loads((root/'finished.json').read_text())
    proof=json.loads((POOL/'independent-verification.json').read_text());launch=json.loads((POOL/'launch.json').read_text())
    if not finish['complete'] or proof['verification']!='passed' or proof['job']!=launch['job']:raise ValueError('incomplete verified matrix')
    plan=json.loads((POOL/'plan.private.json').read_text());rows=[]
    for item in p['requests']:
        i=item['index'];raw=(root/f'response-{i}.private.json').read_bytes();data=json.loads(raw)
        if SECRET.search(raw):raise ValueError('unsafe response')
        rank=remap(json.loads(data['choices'][0]['message']['content']),item['display_order'])
        saved=json.loads((root/f'ranking-{i}.private.json').read_text())
        if saved!=dict(original_slot_ranking=rank,response_sha256=digest(raw)):raise ValueError('ranking drift')
        rows.append(item|dict(original_slot_ranking=rank))
    summaries=[]
    for task in TASKS:
        programs=[r for r in plan['programs'] if r['task']==task]
        outcomes={p['pool_slot']:json.loads((POOL/f"result-{p['index']}.json").read_text()) for p in programs}
        for p0 in programs:
            o=outcomes[p0['pool_slot']]
            if (o['code_sha256'],o['task'],o['job'])!=(p0['code_sha256'],task,launch['job']):raise ValueError('outcome binding')
            numeric=next(r for r in proof['rows'] if r['index']==p0['index'])
            if numeric['official_score']!=o['score'] or numeric['status']!=o['status']:raise ValueError('verified result drift')
        def stats(slots):
            valid=[outcomes[s]['score'] for s in slots if outcomes[s]['valid']]
            return dict(slots=slots,valid=len(valid),total=len(slots),valid_probability=len(valid)/len(slots),
                conditional_mean_score=sum(valid)/len(valid) if valid else None)
        entry=dict(task=task,uniform4=stats(list(range(4))))
        for condition in ('full','omitted'):
            ranks=[r['original_slot_ranking'] for r in rows if r['task']==task and r['condition']==condition]
            entry[condition]=stats(top2(ranks))|dict(single_order_top2=[r[:2] for r in ranks],
                single_order_top2_invariant=set(ranks[0][:2])==set(ranks[1][:2]))
        summaries.append(entry)
    result=dict(role='two_development_pool_information_package_ablation',tasks=summaries,rankings=rows,
        billing=finish['billing'],controller_commit=commit,script_sha256=digest(Path(__file__).read_bytes()),
        pool_plan_sha256=POOL_SHA,numerical_verifier_sha256=digest((POOL/'independent-verification.json').read_bytes()),
        e2e_claim=False,protected_cohort_read=False,independent_search_seeds=1,
        limitations=['Only two previously explored development pools; no generality or causal e2e claim.',
            'The information package combines resources, API facts and usage guidance; those components are not separated.',
            'Provider nondeterminism, input length and time can contribute; alternating order is not a cure.',
            'Missing scores remain missing; compare validity and conditional quality jointly.'])
    write(root/'summary.json',result);print(json.dumps(result))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=('prepare','run','readout'));ap.add_argument('--root');ap.add_argument('--commit',required=True)
    a=ap.parse_args();os.umask(0o077)
    try:
        if a.mode=='prepare':prepare(a.commit)
        elif a.mode=='run':run(a.root,a.commit)
        else:readout(a.root,a.commit)
    except Exception as exc:
        print(json.dumps(dict(status='FAILED_CLOSED',error_type=type(exc).__name__)));raise SystemExit(2)
