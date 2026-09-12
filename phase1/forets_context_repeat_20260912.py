"""Seed14 small-pool repair binding of the existing package builder.

The inherited builder is hash-pinned. Exact substitutions change seed/path and
billing plus an explicit true small-pool bypass in both configs/validator.
The failed seed13 block is not a valid same-version effect comparison.
Loading this module does not open runs, charge APIs, or submit jobs.
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
import sys

from forets_paid_patch_20260911 import once

PARENT=Path('/research/d7/spc/yzyang4/forets-context-e2e-20260912-5xz0w6iy')
BASE='5950c7d3acf1e03173ba2ea7081d8ba6593279d9'
PREPARED='aa8fcffdfefe12e7bd93ce0c1925b28bc03f296b593ee6f321f1c4a7130566a1'
INVENTORY='46d580776b1ed13be74a89f859693381bb1862091a511a47afcb5bd80d7ceaac'
RELEASE='ba663cf6e7354131957c690950570e37c0e1ff1fc258db43690ae8305c3631b6'
AUTH='f38b37f695e122d8f5df7a26fe781b80952708d8701dec22ab9dbca17ad70613'
LEGACY_SHA='659e2825c26bddd95175431ec058dea4844fbfb5d3a816f8a967c638f412204c'
PLAN='FORETS_CONTEXT_SMALLPOOL_REPAIR_20260912.md'


def order():
    return [('leaf-classification','uniform_random'),('leaf-classification','critic_topk_random'),
            ('spaceship-titanic','critic_topk_random'),('spaceship-titanic','uniform_random')]


def patch_budget(source,model,*,accounted,settled,calls,unknown,authorization,seed):
    if model!='qwen/qwen3-coder-flash' or seed!=14 or authorization!=AUTH:raise ValueError('unplanned replication')
    if any(type(v) is not int for v in (accounted,settled,calls,unknown)) or not 0<=settled<=accounted or calls<214 or unknown!=2:
        raise ValueError('invalid or unresolved predecessor')
    total=min(10000000000,accounted+3500000000)
    if total-accounted<2600000000:raise ValueError('cannot safely reserve a Plus request')
    auth=dict(version=8,total=total,incremental_cap=total-accounted,run_limit=4000000000,route_limit=4000000000,
        predecessor_authorization=AUTH,predecessor_accounted=accounted,predecessor_settled=settled,
        predecessor_calls=calls,predecessor_unresolved=unknown,experiment='contextual-smallpool-repair-seed14',
        accounted_cny_ceiling=str(Decimal(total)/10**9*Decimal('8.8')))
    if 'def reserve(path, scope, attempt_id, amount=None):' not in source or 'cost > row[0]' not in source:
        raise ValueError('variable-reservation parent required')
    source=once(source,'AUTH_RAW = json.dumps(AUTH,','AUTH.update('+repr(auth)+')\nAUTH_RAW = json.dumps(AUTH,')
    return source,auth


def derive(name,text):
    if name=='forets_e2e_package.py':
        return once(text,'if config.solver.use_test_score or config.solver.skip_redundant_critic:',
            'if config.solver.use_test_score or not config.solver.skip_redundant_critic:')
    changes={'forets_block_controller_20260911.py':('enumerate((13,), 1)','enumerate((14,), 1)'),
        'forets_block_readout_20260911.py':('for seed in (13,):','for seed in (14,):'),
        'forets_paid_route_20260911.py':("FORETS_PAID_SCOPE='route_s13'","FORETS_PAID_SCOPE='route_s14'")}
    return once(text,*changes[name]) if name in changes else text


def parent_facts():
    os.environ['SLURM_CONF']='/opt1/slurm/gpu-slurm.conf';sys.path.insert(0,str(PARENT/'code'))
    raw=(PARENT/'prepared.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PREPARED:raise ValueError('parent preparation changed')
    line=subprocess.check_output(['sacct','-X','-j','13123','-nP','--format=JobIDRaw,State%32,NodeList,ElapsedRaw'],text=True,timeout=25).strip()
    if line!='13123|CANCELLED by 7542|gpu28|1494':raise ValueError('cancelled parent differs')
    closed=json.loads((PARENT/'cancellation-closeout.json').read_bytes())
    if (closed['job']!='13123' or closed['effect_comparison_valid'] is not False or closed['outcomes_read'] is not False
        or closed['reason']!='contextual_rank rejects width1 while actual skip_redundant_critic=false'):
        raise ValueError('different cancellation reason')
    # No final scores/journals are read for this infrastructure repair handover.
    with closing(sqlite3.connect((PARENT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('SELECT digest,stopped FROM auth').fetchall()!=[(AUTH,0)]:raise ValueError('parent budget stopped or changed')
        rows=db.execute('SELECT * FROM calls ORDER BY id').fetchall()
    facts=dict(accounted=sum(r[2] for r in rows),settled=sum(r[3] or 0 for r in rows),
        calls=len(rows),unknown=sum(r[4]=='unresolved' for r in rows),authorization=AUTH,seed=14)
    if (facts['unknown'],facts['calls'],facts['accounted'],facts['settled'])!=(2,214,2214760245,814760245):
        raise ValueError('cancellation ledger drift')
    from forets_environment_build_20260912 import encode as canonical
    return dict(facts=facts,ledger_rows_sha256=hashlib.sha256(canonical(rows)).hexdigest(),
        verification_sha256=hashlib.sha256((PARENT/'cancellation-closeout.json').read_bytes()).hexdigest(),
        diagnostics_sha256=hashlib.sha256((PARENT/'cancellation-intent.json').read_bytes()).hexdigest(),
        parent_allocation_gpu_hours=closed['allocation_gpu_hours'])


def load_builder():
    path=Path(__file__).with_name('forets_repeat_build_20260912.py');raw=path.read_bytes().replace(b'\r\n',b'\n')
    if hashlib.sha256(raw).hexdigest()!=LEGACY_SHA:raise ValueError('base builder hash changed')
    text=raw.decode().replace('\r\n','\n')
    # The checked functions below override the old gate/order/budget/derive.
    # The remaining reusable functions are artifact, build, activate and facts.
    edits=[("rid=f'{index:02d}-{task}-s12-{arm}'","rid=f'{index:02d}-{task}-s14-{arm}'"),
        ('rows.append(dict(prior,run_id=rid,seed=12,config_sha256=digest))','rows.append(dict(prior,run_id=rid,seed=14,config_sha256=digest))'),
        ("cfg['metadata']['seed']=cfg['solver']['selector_seed']=12","cfg['metadata']['seed']=cfg['solver']['selector_seed']=14\n        cfg['solver']['skip_redundant_critic']=True"),
        ('seeds=[12]','seeds=[14]'),
        ("'launchers/forets_review_20260912.sbatch'","'launchers/forets_context_20260912.sbatch'"),
        ("'forets-review-s11'","'forets-context-s13'"),
        ("'forets-repeat-s12'","'forets-repeat-s14'"),
        ("'seed11','seed12'","'seed13','seed14'"),
        ("'forets_review_20260912.sbatch'","'forets_context_20260912.sbatch'"),
        ("'seed=11','seed=12'","'seed=13','seed=14'"),
        ("new_api_calls=state['calls']-55,","new_api_calls=state['calls']-185,"),
        ('Decimal(422344104)/10**9','Decimal(742593566)/10**9'),
        ('maximum_new_gpu_hours=10','maximum_new_gpu_hours=5'),
        ('maximum_incremental_usd=2','maximum_incremental_usd=3.5'),
        ("[('route_s12',ns['AUTH']['route_limit'])]","[('route_s14',ns['AUTH']['route_limit'])]")]
    for old,new in edits:
        count=text.count(old)
        if count not in (1,2):raise ValueError('unexpected builder derivation anchor')
        text=text.replace(old,new)
    ns={'__name__':'seed14_bound_builder','__file__':str(path)};exec(compile(text,str(path),'exec'),ns)
    ns.update(PARENT=PARENT,BASE=BASE,PREPARED=PREPARED,INVENTORY=INVENTORY,RELEASE=RELEASE,AUTH_PARENT=AUTH,
        PLAN=PLAN,parent_facts=parent_facts,patch_budget=patch_budget,order=order,derive=derive)
    return ns


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('facts','artifact','build','activate','check'));p.add_argument('path',type=Path,nargs='?');a=p.parse_args()
    ns=load_builder()
    if a.mode=='check':print(json.dumps(dict(status='BUILDER_LOADED_NOT_RUN',seed=14,api_calls=0,gpu_jobs=0)))
    else:
        if a.path is None:raise ValueError('explicit output required')
        ns[a.mode](a.path)
