"""Fresh execute-two successor, cumulative billing and passive channel counters."""
import argparse
import contextlib
import io
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import build_forets_common_start_20260913 as parent_builder
import build_forets_wallclock_20260912 as common
from forets_environment_build_20260912 import git, read, write, PREFIX
from forets_paid_patch_20260911 import once
from forets_reserve_backpressure_20260913 import patch_budget
from forets_gateway_wire_20260913 import patch_server
from forets_branching_control_20260913 import execute_two

BASE='1ec18564f176d58a3a7ac3a46852ad92044777b5'
PARENT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-2o9mw39n')
BILLING=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-nehs1mj2')
PREPARED='2fcde0dd017124ab20c73a7bb505462185525d7b377d890c4e66e08f801986b5'
AUTH_PARENT='e59bbcbff5dc6616bf8771c8172ad0ed4de6354f6a3808112353568e339b6659'
PLAN='FORETS_BRANCHING_EXECUTION_PLAN_20260913.md'
SEEDS=(30,31)
NEW_CAP=5437705319


def order():
    return [(b,t,s,a) for b,s in enumerate(SEEDS,1)
        for i,t in enumerate(('leaf-classification','spaceship-titanic'))
        for a in (['critic_topk_random','uniform_random'] if (s+i)%2 else ['uniform_random','critic_topk_random'])]


def parent_calls():
    finish=read(PARENT/'readout-finished.json')
    if finish['status']!='verified' or finish['files']['common-start-summary.json']!='3b1322cea5406d5e0197694f6b9e9af85a466bd005d590416f6070989a4ce408':raise ValueError('closure')
    if list(BILLING.glob('launch-b*.json')) or list(BILLING.glob('submit-intent-b*.json')):raise ValueError('prelaunch repair already dispatched')
    with closing(sqlite3.connect((BILLING/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('SELECT digest,stopped FROM auth').fetchall()!=[(AUTH_PARENT,0)]:raise ValueError('parent inactive')
        rows=db.execute('SELECT * FROM calls ORDER BY id').fetchall()
    if (len(rows),sum(r[2] for r in rows),sum(r[3] or 0 for r in rows),sum(r[4]=='unresolved' for r in rows))!=(985,4562294681,3162294681,2):raise ValueError('cost drift')
    return rows


def derive(name,text):
    if name=='forets_block_controller_20260911.py':text=once(text,'enumerate((28, 29), 1)','enumerate((30, 31), 1)')
    if name=='forets_paid_route_20260911.py':text=once(text,"FORETS_PAID_SCOPE='route_commonstart'","FORETS_PAID_SCOPE='route_branching_async'")
    return text


def changed_sources():
    auth=dict(version=15,total=10**10,incremental_cap=NEW_CAP,predecessor_authorization=AUTH_PARENT,
        predecessor_accounted=4562294681,predecessor_settled=3162294681,predecessor_calls=985,
        predecessor_unresolved=2,experiment='execute-two-e2e-seeds30-31',pre_dispatch_wait_seconds=90)
    budget=patch_budget(git('show',BASE+':'+PREFIX+'paid_budget.py').decode())
    budget=once(budget,'AUTH_RAW = json.dumps(AUTH,','AUTH.update('+repr(auth)+')\nAUTH_RAW = json.dumps(AUTH,')
    path='src/dojo/core/interpreters/jupyter/'
    server=patch_server(git('show',BASE+':'+path+'singularity_jupyter_server.py').decode())
    transport=git('show',BASE+':'+PREFIX+'paid_transport.py').decode()
    transport=transport.replace('PROVIDER, reserve, settle, BudgetStopped','PROVIDER, reserve_async, settle, BudgetStopped')
    transport=once(transport,'        reserve(path, scope, attempt_id)','        await reserve_async(path, scope, attempt_id)')
    rank_path='src/dojo/solvers/fore_ts/contextual_rank.py'
    rank=once(git('show',BASE+':'+rank_path).decode(),'        paid_budget.reserve(ledger,scope,attempt,amount=2600000000)',
        '        await paid_budget.reserve_async(ledger,scope,attempt,amount=2600000000)')
    return {PREFIX+'paid_budget.py':budget.encode(),path+'singularity_jupyter_server.py':server.encode(),
        PREFIX+'paid_transport.py':transport.encode(),rank_path:rank.encode(),
        path+'gateway_wire.py':Path(__file__).with_name('forets_gateway_wire_20260913.py').read_bytes().replace(b'\r\n',b'\n'),
        'src/dojo/solvers/fore_ts/reserve_backpressure.py':Path(__file__).with_name('forets_reserve_backpressure_20260913.py').read_bytes().replace(b'\r\n',b'\n')}


def configure():
    values=dict(BASE=BASE,PARENT=PARENT,PREPARED=PREPARED,AUTH_PARENT=AUTH_PARENT,PLAN=PLAN,SEEDS=SEEDS,
        NEW_CAP=NEW_CAP,order=order,parent_calls=parent_calls,derive=derive,config_transform=execute_two,
        changed_sources=changed_sources)
    for k,v in values.items():setattr(parent_builder,k,v)
    parent_builder.configure()
    common.ROUTE_SCOPE='route_branching_async';common.BILLING=BILLING


def build(stage):
    # Parent wrapper supplies the exact two-block launcher structure.
    buf=io.StringIO()
    with contextlib.redirect_stdout(buf):common.build(stage,block_minutes=90,block_ids=(1,2),config_transform=execute_two)
    info=json.loads(buf.getvalue());root=Path(info['package'])
    template=(root/'launchers/forets_wallclock.sbatch').read_text()
    for b in (1,2):
        script=once(template,'execute --block 1',f'execute --block {b}')
        script=once(script,'#SBATCH --job-name=forets-common-b1',f'#SBATCH --job-name=forets-branching-b{b}')
        write(root/f'launchers/singlevote-b{b}.sbatch',script.encode())
    print(json.dumps(info))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('artifacts','build','activate'));p.add_argument('path',type=Path)
    a=p.parse_args();os.umask(0o077);configure()
    (parent_builder.artifacts if a.mode=='artifacts' else (lambda root:common.activate(root,reuse_unattempted_scopes=True)) if a.mode=='activate' else build)(a.path)
