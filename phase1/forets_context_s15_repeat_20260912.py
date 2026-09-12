"""Conditional seed15 replication. Import/check never reads experimental values.

Reuse the hash-pinned builder, bind the actual seed14 package, and freeze every
scientific setting. Only run facts after whole-block independent verification.
"""
import argparse
from contextlib import closing
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess

from forets_paid_patch_20260911 import once
from forets_environment_build_20260912 import encode

PARENT=Path('/research/d7/spc/yzyang4/forets-repeat-20260912-x3pkniqp')
BASE='f70eb4859c48c61bba37b298fbf8e32e367644ae'
PREPARED='111a28c1c12174c00451c737435028cf8528b386fea1f723392a34e648d6f40e'
INVENTORY='b43020dd30309147d97a9aad24c074a03d193a10b10b05cf547eb7f6a1529154'
RELEASE='b3e0237ce1d32367d9b93e8a444738d7a890ba6ada59e366902d7487cf870b6c'
AUTH='d42e129a04210bd56c981c393d2890e0b50b1d98755027893ad3fa6c3127e93a'
LEGACY_SHA='659e2825c26bddd95175431ec058dea4844fbfb5d3a816f8a967c638f412204c'
PLAN='FORETS_SMALLPOOL_S14_LAUNCH_20260912.md'


def order():
    return [('leaf-classification','critic_topk_random'),('leaf-classification','uniform_random'),
            ('spaceship-titanic','uniform_random'),('spaceship-titanic','critic_topk_random')]


def check_gate(verified,diagnostics):
    """Gate technical closure and comparability, never a positive score sign."""
    if (verified['job']!='13124' or verified['source_tree']!=BASE or verified['seed']!=14
        or verified['verification']!='passed' or diagnostics['comparable_pairs']<1
        or verified['valid_finals']!=diagnostics['valid_final_solutions']
        or verified['numerical_final_regrades']!=verified['valid_finals']):
        raise ValueError('replication evidence gate not met')
    pools=verified['pools']
    if not pools or not all(p['completed'] for p in pools) or not any(p['context_ranked'] for p in pools):
        raise ValueError('incomplete or unused contextual selector')


def parent_facts():
    raw=(PARENT/'prepared.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PREPARED:raise ValueError('parent preparation drift')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    status=subprocess.check_output(['sacct','-X','-j','13124','-nP','-o','JobIDRaw,State%32,NodeList,ElapsedRaw'],env=env,text=True,timeout=25).strip()
    fields=status.split('|')
    if len(fields)!=4 or fields[:3]!=['13124','COMPLETED','gpu28']:raise ValueError('parent not normally complete')
    vr=PARENT/'independent-context-verification.json';dg=PARENT/'diagnostics.json'
    verified=json.loads(vr.read_bytes());diagnostics=json.loads(dg.read_bytes());check_gate(verified,diagnostics)
    with closing(sqlite3.connect((PARENT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('SELECT digest,stopped FROM auth').fetchall()!=[(AUTH,0)]:raise ValueError('parent authorization drift')
        rows=db.execute('SELECT * FROM calls ORDER BY id').fetchall()
    facts=dict(accounted=sum(r[2] for r in rows),settled=sum(r[3] or 0 for r in rows),calls=len(rows),
        unknown=sum(r[4]=='unresolved' for r in rows),authorization=AUTH,seed=15)
    if facts['unknown']!=2 or any(r[4] not in ('settled','unresolved') for r in rows):
        raise ValueError('new unresolved/unknown request needs review')
    if (Decimal(str(verified['cumulative_accounted_usd']))*10**9!=facts['accounted']
        or Decimal(str(verified['cumulative_settled_usd']))*10**9!=facts['settled']):
        raise ValueError('ledger changed after independent closeout')
    return dict(facts=facts,ledger_rows_sha256=hashlib.sha256(encode(rows)).hexdigest(),
        verification_sha256=hashlib.sha256(vr.read_bytes()).hexdigest(),
        diagnostics_sha256=hashlib.sha256(dg.read_bytes()).hexdigest(),
        parent_allocation_gpu_hours=verified['allocation_gpu_hours'])


def patch_budget(source,model,*,accounted,settled,calls,unknown,authorization,seed):
    if model!='qwen/qwen3-coder-flash' or seed!=15 or authorization!=AUTH:raise ValueError('unplanned replication')
    if any(type(v) is not int for v in (accounted,settled,calls,unknown)) or not 0<=settled<=accounted or calls<216 or unknown!=2:
        raise ValueError('invalid carryover')
    total=min(10000000000,accounted+3500000000)
    if total-accounted<2600000000:raise ValueError('insufficient conservative reservation')
    auth=dict(version=9,total=total,incremental_cap=total-accounted,run_limit=4000000000,route_limit=4000000000,
        predecessor_authorization=AUTH,predecessor_accounted=accounted,predecessor_settled=settled,
        predecessor_calls=calls,predecessor_unresolved=unknown,experiment='contextual-same-version-seed15',
        accounted_cny_ceiling=str(Decimal(total)/10**9*Decimal('8.8')))
    return once(source,'AUTH_RAW = json.dumps(AUTH,','AUTH.update('+repr(auth)+')\nAUTH_RAW = json.dumps(AUTH,'),auth


def derive(name,text):
    edits={'forets_block_controller_20260911.py':('enumerate((14,), 1)','enumerate((15,), 1)'),
        'forets_block_readout_20260911.py':('for seed in (14,):','for seed in (15,):'),
        'forets_paid_route_20260911.py':("FORETS_PAID_SCOPE='route_s14'","FORETS_PAID_SCOPE='route_s15'")}
    return once(text,*edits[name]) if name in edits else text


def load_builder():
    path=Path(__file__).with_name('forets_repeat_build_20260912.py');raw=path.read_bytes().replace(b'\r\n',b'\n')
    if hashlib.sha256(raw).hexdigest()!=LEGACY_SHA:raise ValueError('builder changed')
    text=raw.decode()
    edits=[("rid=f'{index:02d}-{task}-s12-{arm}'","rid=f'{index:02d}-{task}-s15-{arm}'"),
        ('rows.append(dict(prior,run_id=rid,seed=12,config_sha256=digest))','rows.append(dict(prior,run_id=rid,seed=15,config_sha256=digest))'),
        ("cfg['metadata']['seed']=cfg['solver']['selector_seed']=12","cfg['metadata']['seed']=cfg['solver']['selector_seed']=15"),
        ('seeds=[12]','seeds=[15]'),
        ("'launchers/forets_review_20260912.sbatch'","'launchers/forets_repeat_20260912.sbatch'"),
        ("'forets-review-s11'","'forets-repeat-s14'"),
        ("'forets-repeat-s12'","'forets-repeat-s15'"),
        ("'seed11','seed12'","'seed14','seed15'"),
        ("'forets_review_20260912.sbatch'","'forets_repeat_20260912.sbatch'"),
        ("'seed=11','seed=12'","'seed=14','seed=15'"),
        ("new_api_calls=state['calls']-55,","new_api_calls=state['calls']-214,"),
        ('Decimal(422344104)/10**9','Decimal(814760245)/10**9'),
        ('maximum_new_gpu_hours=10','maximum_new_gpu_hours=5'),
        ('maximum_incremental_usd=2','maximum_incremental_usd=3.5'),
        ("[('route_s12',ns['AUTH']['route_limit'])]","[('route_s15',ns['AUTH']['route_limit'])]")]
    for old,new in edits:
        if text.count(old) not in (1,2):raise ValueError('builder anchor drift')
        text=text.replace(old,new)
    ns={'__name__':'seed15_bound_builder','__file__':str(path)};exec(compile(text,str(path),'exec'),ns)
    ns.update(PARENT=PARENT,BASE=BASE,PREPARED=PREPARED,INVENTORY=INVENTORY,RELEASE=RELEASE,AUTH_PARENT=AUTH,
        PLAN=PLAN,parent_facts=parent_facts,patch_budget=patch_budget,order=order,derive=derive)
    return ns


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('check','facts','artifact','build','activate'))
    parser.add_argument('path',type=Path,nargs='?');args=parser.parse_args();ns=load_builder()
    if args.mode=='check':print(json.dumps(dict(status='PREPARED_NOT_RUN',seed=15,api_calls=0,gpu_jobs=0)))
    else:
        if args.path is None:raise ValueError('explicit output path required')
        ns[args.mode](args.path)
