"""Frozen proposal-width contrast; only configuration fanout changes scientifically."""
import argparse
from contextlib import closing, redirect_stdout
import inspect
import io
import json
import os
from pathlib import Path
import sqlite3
import build_forets_common_start_20260913 as parent_builder
import build_forets_wallclock_20260912 as common
from build_forets_action_prospective_20260913 import replace_function
from forets_environment_build_20260912 import git, read, write, encode, sha, PREFIX
from forets_paid_patch_20260911 import once

BASE='f7a8b9e3c07b530467573315d55f62203cc67895'
PARENT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-7wzrny21')
PREPARED='ab146978b54b763a4295fc6261a633174e054c1bbd00f1d0602f5c8f3da53cf9'
AUTH_PARENT='b00f6e77b018028a544d2c8c066ca4e239d4f50878436c182c059ccf104b2e04'
PLAN='FORETS_WIDTH_CONTROL_PLAN_20260913.md'
SEEDS=(38,39)
WIDTHS={'batch_four':4,'direct_two':2}
FACTS=None

def order():
    rows=[]
    for block,seed in enumerate(SEEDS,1):
        for i,task in enumerate(('leaf-classification','spaceship-titanic')):
            arms=list(WIDTHS)
            if (seed+i)%2:arms.reverse()
            rows.extend((block,task,seed,arm) for arm in arms)
    return rows

def parent_calls():
    finish=read(PARENT/'readout-finished.json',FACTS['finish_sha256'])
    if finish['status']!='verified':raise ValueError('closed predecessor')
    with closing(sqlite3.connect((PARENT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('SELECT digest,stopped FROM auth').fetchall()!=[(AUTH_PARENT,0)]:raise ValueError('parent not active')
        rows=db.execute('SELECT * FROM calls ORDER BY id').fetchall()
    if sha(encode(rows))!=FACTS['calls_sha256']:raise ValueError('prior calls drift')
    counts=(len(rows),sum(r[2] for r in rows),sum(r[3] or 0 for r in rows),sum(r[4]=='unresolved' for r in rows))
    if counts!=tuple(FACTS['billing_counts']) or counts[3]!=2:raise ValueError('prior counts/unknowns drift')
    return rows

def derive(name,text):
    if name=='forets_block_controller_20260911.py':
        text=replace_function(text,'expected_order','def expected_order():\n    return '+repr(tuple(order())))
    if name=='forets_paid_route_20260911.py':
        text=once(text,"FORETS_PAID_SCOPE='route_action_delivery'","FORETS_PAID_SCOPE='route_width_control'")
    return text

def config_transform(cfg,arm):
    s=cfg['solver']
    if (s['num_children'],s['num_children_to_choose'],s['critic_top_k'],s['time_limit_secs'],
        s['execution_timeout'],s['selection_policy'],s['use_test_score'],s['action_delivery_protocol'])!=(
        4,2,2,600,300,'uniform_random',False,'original_search_visible_action_delivery_v1'):
        raise ValueError('exact uniform reference configuration required')
    s['num_children']=WIDTHS[arm]
    return cfg

def normalized_template(cfg,rid,root,common_config):
    clone=json.loads(json.dumps(cfg))
    if clone['solver']['num_children'] not in WIDTHS.values():raise ValueError('unplanned width')
    clone['solver']['num_children']=0
    return common_config(clone,run_id=rid,run_dir=root/'runs'/rid)

def changed_sources():
    count,held,settled,unknown=FACTS['billing_counts']
    if unknown!=2 or not 0<=settled<=held<10**10:raise ValueError('remaining cumulative budget')
    auth=dict(version=18,total=10**10,incremental_cap=10**10-held,predecessor_authorization=AUTH_PARENT,
        predecessor_accounted=held,predecessor_settled=settled,predecessor_calls=count,
        predecessor_unresolved=unknown,experiment='uniform-proposal-width-two-vs-four-seeds38-39')
    text=once(git('show',BASE+':'+PREFIX+'paid_budget.py').decode(),'AUTH_RAW = json.dumps(AUTH,',
        'AUTH.update('+repr(auth)+')\nAUTH_RAW = json.dumps(AUTH,')
    return {PREFIX+'paid_budget.py':text.encode()}

def configure(facts):
    global FACTS
    FACTS=read(facts)
    if (FACTS['root'],FACTS['source_tree'],FACTS['prepared_sha256'],FACTS['authorization'])!=(PARENT.as_posix(),BASE,PREPARED,AUTH_PARENT):
        raise ValueError('exact predecessor facts')
    vals=dict(BASE=BASE,PARENT=PARENT,PREPARED=PREPARED,AUTH_PARENT=AUTH_PARENT,PLAN=PLAN,SEEDS=SEEDS,
        NEW_CAP=10**10-FACTS['billing_counts'][1],order=order,parent_calls=parent_calls,derive=derive,
        config_transform=config_transform,changed_sources=changed_sources)
    for k,v in vals.items():setattr(parent_builder,k,v)
    parent_builder.configure();common.ROUTE_SCOPE='route_width_control'

def build(stage):
    # Honest experiment arm labels are distinct from the unchanged uniform
    # selector. Both configs come from the parent's uniform template.
    text=inspect.getsource(common.build)
    text=once(text,"prior=prior_rows[(task,arm)]","prior=prior_rows[(task,'uniform_random')]")
    text=once(text,'cfg = config_transform(cfg)','cfg = config_transform(cfg,arm)')
    text=once(text,'rows.append(dict(prior,run_id=rid,block=block,seed=seed,config_sha256=digest))',
        'rows.append(dict(prior,run_id=rid,block=block,seed=seed,arm=arm,proposal_width=WIDTHS[arm],config_sha256=digest))')
    text=once(text,"normalized.append(common_config(cfg,run_id=rid,run_dir=root/'runs'/rid))",
        'normalized.append(normalized_template(cfg,rid,root,common_config))')
    text=once(text,"raise ValueError('two arms differ beyond policy')","raise ValueError('two arms differ beyond fanout')")
    text=once(text,"development_purpose='wallclock_600_complete_iteration_incumbent'",
        "development_purpose='uniform_width_control_action_primary_iteration_secondary'")
    ns={**vars(common),'normalized_template':normalized_template,'WIDTHS':WIDTHS};exec(compile(text,'<explicit-width-builder>','exec'),ns)
    buf=io.StringIO()
    with redirect_stdout(buf):ns['build'](stage,block_minutes=90,block_ids=(1,2),config_transform=config_transform)
    info=json.loads(buf.getvalue());root=Path(info['package'])
    template=(root/'launchers/forets_wallclock.sbatch').read_text()
    for b in (1,2):
        script=once(template,'execute --block 1',f'execute --block {b}')
        script=once(script,'#SBATCH --job-name=forets-action-b1',f'#SBATCH --job-name=forets-width-b{b}')
        write(root/f'launchers/singlevote-b{b}.sbatch',script.encode())
    print(json.dumps(info))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('artifacts','build','activate'));p.add_argument('path',type=Path)
    p.add_argument('--facts',type=Path,required=True);a=p.parse_args();os.umask(0o077);configure(a.facts)
    (parent_builder.artifacts if a.mode=='artifacts' else common.activate if a.mode=='activate' else build)(a.path)
