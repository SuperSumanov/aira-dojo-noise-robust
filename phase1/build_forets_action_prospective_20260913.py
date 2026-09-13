"""Eight uniform trajectories, paired delivery policies; no dispatch in build."""
import argparse
import ast
from contextlib import closing, redirect_stdout
import inspect
import io
import json
import os
from pathlib import Path
import sqlite3
import build_forets_common_start_20260913 as parent_builder
import build_forets_wallclock_20260912 as common
from forets_environment_build_20260912 import git, read, write, encode, sha, PREFIX
from forets_paid_patch_20260911 import once
from forets_action_delivery_20260913 import patch_sources, PROTOCOL

BASE='f1cdee3a9e553e8efeedaa1a66a2c6bd778f9798'
PARENT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-5_czzimk')
PREPARED='82a85e630b4d58830cd382d2b7af549c454aed3645a2b3ca3c1f7d36e74fd571'
AUTH_PARENT='96191b7393556fc5c978d82d2f3f2789ffb5f8c8c0243605b425df6843c07540'
PLAN='FORETS_ACTION_PROSPECTIVE_PLAN_20260913.md'
SEEDS=(34,35,36,37)
FACTS=None

def order():
    return [(b,t,s,'uniform_random') for b,ss in enumerate(((34,35),(36,37)),1)
        for t in ('leaf-classification','spaceship-titanic') for s in ss]

def replace_function(text,name,replacement):
    funcs=[n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name]
    if len(funcs)!=1:raise ValueError('one exact function required')
    n=funcs[0];lines=text.splitlines(keepends=True)
    return ''.join(lines[:n.lineno-1])+replacement.rstrip()+'\n'+''.join(lines[n.end_lineno:])

def parent_calls():
    finish=read(PARENT/'readout-finished.json',FACTS['finish_sha256'])
    if finish['status']!='verified':raise ValueError('closed predecessor')
    with closing(sqlite3.connect((PARENT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('SELECT digest,stopped FROM auth').fetchall()!=[(AUTH_PARENT,0)]:raise ValueError('parent not active')
        rows=db.execute('SELECT * FROM calls ORDER BY id').fetchall()
    if sha(encode(rows))!=FACTS['calls_sha256']:raise ValueError('prior calls drift')
    if (len(rows),sum(r[2] for r in rows),sum(r[3] or 0 for r in rows),sum(r[4]=='unresolved' for r in rows))!=tuple(FACTS['billing_counts']):
        raise ValueError('prior counts drift')
    return rows

def derive(name,text):
    if name=='forets_block_controller_20260911.py':
        text=replace_function(text,'expected_order','def expected_order():\n    return '+repr(tuple(order())))
    if name=='forets_paid_route_20260911.py':
        text=once(text,"FORETS_PAID_SCOPE='route_reference'","FORETS_PAID_SCOPE='route_action_delivery'")
    return text

def config_transform(cfg):
    s=cfg['solver']
    if (s['num_children'],s['num_children_to_choose'],s['time_limit_secs'],s['execution_timeout'],s['use_test_score'],s['selection_policy'])!=(4,2,600,300,False,'uniform_random'):
        raise ValueError('fixed random-search configuration')
    s['action_delivery_protocol']=PROTOCOL
    return cfg

def normalized_template(cfg,rid,root,common_config):
    # New matrix varies seed, not policy. This check explicitly excludes only
    # documented seed identity in addition to common_config's mechanical paths.
    clone=json.loads(json.dumps(cfg))
    if clone['metadata']['seed'] not in SEEDS or clone['solver']['selector_seed']!=clone['metadata']['seed']:
        raise ValueError('seed binding')
    clone['metadata']['seed']=clone['solver']['selector_seed']=0
    return common_config(clone,run_id=rid,run_dir=root/'runs'/rid)

def changed_sources():
    count,held,settled,unknown=FACTS['billing_counts']
    auth=dict(version=17,total=10**10,incremental_cap=10**10-held,predecessor_authorization=AUTH_PARENT,
        predecessor_accounted=held,predecessor_settled=settled,predecessor_calls=count,
        predecessor_unresolved=unknown,experiment='passive-action-delivery-uniform-seeds34-37')
    budget=once(git('show',BASE+':'+PREFIX+'paid_budget.py').decode(),'AUTH_RAW = json.dumps(AUTH,',
        'AUTH.update('+repr(auth)+')\nAUTH_RAW = json.dumps(AUTH,')
    cfg_path='src/dojo/config_dataclasses/solver/fore_ts.py';solver_path='src/dojo/solvers/fore_ts/fore_ts.py'
    cfg,solver=patch_sources(*[git('show',BASE+':'+p).decode() for p in (cfg_path,solver_path)])
    return {PREFIX+'paid_budget.py':budget.encode(),cfg_path:cfg.encode(),solver_path:solver.encode(),
        'src/dojo/solvers/fore_ts/action_delivery.py':Path(__file__).with_name('forets_action_delivery_20260913.py').read_bytes().replace(b'\r\n',b'\n')}

def configure(facts):
    global FACTS
    FACTS=read(facts)
    if (FACTS['root'],FACTS['source_tree'],FACTS['prepared_sha256'],FACTS['authorization'])!=(PARENT.as_posix(),BASE,PREPARED,AUTH_PARENT):
        raise ValueError('exact predecessor facts')
    if FACTS['billing_counts']!=[1310,5388558392,3988558392,2]:raise ValueError('closed billing counts')
    vals=dict(BASE=BASE,PARENT=PARENT,PREPARED=PREPARED,AUTH_PARENT=AUTH_PARENT,PLAN=PLAN,SEEDS=SEEDS,
        NEW_CAP=10**10-FACTS['billing_counts'][1],order=order,parent_calls=parent_calls,derive=derive,
        config_transform=config_transform,changed_sources=changed_sources)
    for k,v in vals.items():setattr(parent_builder,k,v)
    parent_builder.configure();common.ROUTE_SCOPE='route_action_delivery'

def build(stage):
    # Reuse the unchanged archive, native adapter and ledger code. Only replace
    # the matrix normalizer so different documented seeds aren't called arms.
    text=inspect.getsource(common.build)
    text=once(text,"normalized.append(common_config(cfg,run_id=rid,run_dir=root/'runs'/rid))",
        'normalized.append(normalized_template(cfg,rid,root,common_config))')
    text=once(text,"raise ValueError('two arms differ beyond policy')","raise ValueError('trajectories differ beyond seed')")
    text=once(text,'paired_configs=4,','paired_configs=0,paired_delivery_readouts=8,')
    text=once(text,"development_purpose='wallclock_600_complete_iteration_incumbent'",
        "development_purpose='paired_delivery_same_uniform_trajectory'")
    ns={**vars(common),'normalized_template':normalized_template};exec(compile(text,'<explicit-action-builder>','exec'),ns)
    buf=io.StringIO()
    with redirect_stdout(buf):ns['build'](stage,block_minutes=90,block_ids=(1,2),config_transform=config_transform)
    info=json.loads(buf.getvalue());root=Path(info['package'])
    template=(root/'launchers/forets_wallclock.sbatch').read_text()
    for b in (1,2):
        script=once(template,'execute --block 1',f'execute --block {b}')
        script=once(script,'#SBATCH --job-name=forets-reference-b1',f'#SBATCH --job-name=forets-action-b{b}')
        write(root/f'launchers/singlevote-b{b}.sbatch',script.encode())
    print(json.dumps(info))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('artifacts','build','activate'));p.add_argument('path',type=Path)
    p.add_argument('--facts',type=Path,required=True);a=p.parse_args();os.umask(0o077);configure(a.facts)
    (parent_builder.artifacts if a.mode=='artifacts' else common.activate if a.mode=='activate' else build)(a.path)
