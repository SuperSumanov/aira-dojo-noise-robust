"""Fresh reference-conditioned selector; no activation before exact parent closure."""
import argparse
from contextlib import closing, redirect_stdout
import io
import json
import os
from pathlib import Path
import sqlite3
import build_forets_common_start_20260913 as parent_builder
import build_forets_wallclock_20260912 as common
from forets_environment_build_20260912 import git, read, write, encode, sha, PREFIX
from forets_paid_patch_20260911 import once
from forets_reference_context_20260913 import patch_sources

BASE='35321718fef54f1907b469ab44334a30fe66b6cd'
PARENT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-y_p2tlmi')
PREPARED='56efc43be970f45b328e3ce29daceca31350d2966ce8929aa7f34f400a2e15e8'
AUTH_PARENT='ee05b65d5870a607144bed13bdcd474337cd5b46228552fdf36d0ca6df74c9a5'
PLAN='FORETS_REFERENCE_CONTEXT_PLAN_20260913.md'
SEEDS=(32,33)
FACTS=None


def order():
    return [(b,t,s,a) for b,s in enumerate(SEEDS,1)
        for i,t in enumerate(('leaf-classification','spaceship-titanic'))
        for a in (['critic_topk_random','uniform_random'] if (s+i)%2 else ['uniform_random','critic_topk_random'])]


def parent_calls():
    finish=read(PARENT/'readout-finished.json',FACTS['finish_sha256'])
    if finish['status']!='verified':raise ValueError('parent closure')
    with closing(sqlite3.connect((PARENT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('SELECT digest,stopped FROM auth').fetchall()!=[(AUTH_PARENT,0)]:raise ValueError('parent not active')
        rows=db.execute('SELECT * FROM calls ORDER BY id').fetchall()
    if sha(encode(rows))!=FACTS['calls_sha256']:raise ValueError('parent calls drift')
    if (len(rows),sum(r[2] for r in rows),sum(r[3] or 0 for r in rows),sum(r[4]=='unresolved' for r in rows))!=tuple(FACTS['billing_counts']):
        raise ValueError('parent billing counts')
    return rows


def derive(name,text):
    if name=='forets_block_controller_20260911.py':text=once(text,'enumerate((30, 31), 1)','enumerate((32, 33), 1)')
    if name=='forets_paid_route_20260911.py':text=once(text,"FORETS_PAID_SCOPE='route_branching_async'","FORETS_PAID_SCOPE='route_reference'")
    return text


def config_transform(cfg):
    s=cfg['solver']
    if (s['num_children'],s['num_children_to_choose'],s['time_limit_secs'],s['execution_timeout'],s['use_test_score'])!=(4,2,600,300,False):
        raise ValueError('exact same-budget execute-two parent required')
    return cfg


def changed_sources():
    count,held,settled,unknown=FACTS['billing_counts']
    auth=dict(version=16,total=10**10,incremental_cap=10**10-held,predecessor_authorization=AUTH_PARENT,
        predecessor_accounted=held,predecessor_settled=settled,predecessor_calls=count,
        predecessor_unresolved=unknown,experiment='executed-reference-e2e-seeds32-33')
    budget=once(git('show',BASE+':'+PREFIX+'paid_budget.py').decode(),'AUTH_RAW = json.dumps(AUTH,',
        'AUTH.update('+repr(auth)+')\nAUTH_RAW = json.dumps(AUTH,')
    prefix='src/dojo/solvers/fore_ts/'
    batch,rank=patch_sources(*[git('show',BASE+':'+prefix+n).decode() for n in ('batch_runtime.py','contextual_rank.py')])
    return {PREFIX+'paid_budget.py':budget.encode(),prefix+'batch_runtime.py':batch.encode(),prefix+'contextual_rank.py':rank.encode(),
        prefix+'reference_context.py':Path(__file__).with_name('forets_reference_context_20260913.py').read_bytes().replace(b'\r\n',b'\n')}


def configure(facts):
    global FACTS
    FACTS=read(facts)
    if (FACTS['root'],FACTS['source_tree'],FACTS['prepared_sha256'],FACTS['authorization'])!=(PARENT.as_posix(),BASE,PREPARED,AUTH_PARENT):
        raise ValueError('exact parent')
    count,held,settled,unknown=FACTS['billing_counts']
    if unknown!=2 or not 0<=settled<=held<10**10 or count<989:raise ValueError('billing facts')
    values=dict(BASE=BASE,PARENT=PARENT,PREPARED=PREPARED,AUTH_PARENT=AUTH_PARENT,PLAN=PLAN,SEEDS=SEEDS,
        NEW_CAP=10**10-held,order=order,parent_calls=parent_calls,derive=derive,config_transform=config_transform,
        changed_sources=changed_sources)
    for k,v in values.items():setattr(parent_builder,k,v)
    parent_builder.configure();common.ROUTE_SCOPE='route_reference'


def build(stage):
    buf=io.StringIO()
    with redirect_stdout(buf):common.build(stage,block_minutes=90,block_ids=(1,2),config_transform=config_transform)
    info=json.loads(buf.getvalue());root=Path(info['package'])
    template=(root/'launchers/forets_wallclock.sbatch').read_text()
    for b in (1,2):
        script=once(template,'execute --block 1',f'execute --block {b}')
        script=once(script,'#SBATCH --job-name=forets-branching-b1',f'#SBATCH --job-name=forets-reference-b{b}')
        write(root/f'launchers/singlevote-b{b}.sbatch',script.encode())
    print(json.dumps(info))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('artifacts','build','activate'));p.add_argument('path',type=Path)
    p.add_argument('--facts',type=Path,required=True);a=p.parse_args();os.umask(0o077);configure(a.facts)
    (parent_builder.artifacts if a.mode=='artifacts' else common.activate if a.mode=='activate' else build)(a.path)
