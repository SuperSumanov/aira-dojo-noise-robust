"""Prepare-only successor utilities. Parent facts must come from full closure.

No invocation while the paid predecessor is live, no source mutation in place.
The future source differs only in the authorization namespace: interface behavior
is inherited unchanged from the current EScope source.
"""
import argparse
from contextlib import closing,redirect_stdout
import inspect
import io
import json
import os
from pathlib import Path
import sqlite3
import build_forets_wallclock_20260912 as common
import build_forets_common_start_20260913 as artifact_builder
from build_forets_action_prospective_20260913 import replace_function
from forets_environment_build_20260912 import read,write,encode,sha,git,PREFIX
from forets_paid_patch_20260911 import once
from forets_scope_preservation_20260914 import order,transform,strip_intervention,ARMS,SEEDS

BASE='8bb325fa167a9db54656dd6535ce1f3d69859c22'
PARENT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-88v5m9dr')
PREPARED='731001dfa4c054ec16823bbfb685de1f2ad14314e5d5ad4597d12097b713b979'
AUTH_PARENT='643792f11da84620df02fe88ada4759272ff2915dbdf3c8466c5730cb16a3318'
PLAN='ESCOPE_DISCRIMINATING_CONTROLS_20260914.md'
FACTS=None


def load_facts(path):
    facts=read(path)
    if (facts['parent'],facts['authorization'])!=(str(PARENT),AUTH_PARENT):raise ValueError('closed parent identity')
    counts=facts['counts']
    if len(counts)!=4 or counts[3]!=2 or counts[1]>=10**10:raise ValueError('remaining original budget')
    if facts.get('dispatch_allowed') is not True:raise ValueError('development gates not passed')
    return facts


def parent_calls():
    if FACTS is None:raise ValueError('explicit closure facts required')
    closure=read(PARENT/'readout-finished.json',FACTS['closure_sha256'])
    if closure['status']!='verified':raise ValueError('parent still live')
    with closing(sqlite3.connect((PARENT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('SELECT digest,stopped FROM auth').fetchall()!=[(AUTH_PARENT,0)]:raise ValueError('prior account state')
        rows=db.execute('SELECT * FROM calls ORDER BY id').fetchall()
    counts=[len(rows),sum(r[2] for r in rows),sum(r[3] or 0 for r in rows),sum(r[4]=='unresolved' for r in rows)]
    if counts!=FACTS['counts'] or sha(encode(rows))!=FACTS['calls_sha256']:raise ValueError('closed liability drift')
    return rows


def changed_sources():
    cap=10**10-FACTS['counts'][1]
    auth=dict(version=22,total=10**10,incremental_cap=cap,predecessor_authorization=AUTH_PARENT,
        predecessor_accounted=FACTS['counts'][1],predecessor_settled=FACTS['counts'][2],
        predecessor_calls=FACTS['counts'][0],predecessor_unresolved=2,
        experiment='scope_preservation_three_arm_seeds46_47',run_limit=cap,route_limit=cap)
    raw=once(git('show',BASE+':'+PREFIX+'paid_budget.py').decode(),'AUTH_RAW = json.dumps(AUTH,',
        'AUTH.update('+repr(auth)+')\nAUTH_RAW = json.dumps(AUTH,')
    return {PREFIX+'paid_budget.py':raw.encode()}


def cfg_transform(cfg,arm):
    solver=cfg['solver']
    if (solver['num_children'],solver['num_children_to_choose'],solver['execution_timeout'],solver['selection_policy'],solver['use_test_score'],solver['edit_scope'])!=(2,2,300,'uniform_random',False,'whole_program'):
        raise ValueError('same search and plain whole-program donor')
    solver['time_limit_secs']=1200
    return transform(cfg,arm)


def normalize(cfg,arm,rid,root,common_config):
    clone=strip_intervention(cfg,arm)
    return common_config(clone,run_id=rid,run_dir=root/'runs'/rid)


def derive(name,text):
    if name=='forets_block_controller_20260911.py':
        text=replace_function(text,'expected_order','def expected_order():\n    return '+repr(tuple(order())))
        for a,b in [('ALLOCATION_SECONDS = 240 * 60','ALLOCATION_SECONDS = 180 * 60'),
            ("correction['proposed_block_minutes'] != 240","correction['proposed_block_minutes'] != 180"),
            ('len(spec.run_ids) != 8','len(spec.run_ids) != 6'),
            ('allocation_minutes=240','allocation_minutes=180')]:text=once(text,a,b)
    elif name=='forets_native_run_20260911.py':text=once(text,'len(configs) != 8','len(configs) != 6')
    elif name=='forets_paid_route_20260911.py':text=once(text,"FORETS_PAID_SCOPE='route_edit_scope'","FORETS_PAID_SCOPE='route_scope_preservation'")
    return text


def configure(facts_path):
    global FACTS
    FACTS=load_facts(facts_path);cap=10**10-FACTS['counts'][1]
    for k,v in dict(BASE=BASE,PARENT=PARENT,BILLING=PARENT,PREPARED=PREPARED,AUTH_PARENT=AUTH_PARENT,
        PLAN=PLAN,SEEDS=SEEDS,NEW_CAP=cap,ROUTE_SCOPE='route_scope_preservation',SBATCH_TEMPLATE='edit-scope-b1.sbatch',
        order=order,parent_calls=parent_calls,derive=derive).items():setattr(common,k,v)
    artifact_builder.BASE=BASE;artifact_builder.PLAN=PLAN;artifact_builder.order=order;artifact_builder.changed_sources=changed_sources


def build(stage):
    source=inspect.getsource(common.build)
    replacements=[("((180,(1,)), (90,(1,2)))","((180,(1,2)),)"),
        ("prior=prior_rows[(task,arm)]","prior=prior_rows[(task,'whole_program')]"),
        ('cfg = config_transform(cfg)','cfg = config_transform(cfg,arm)'),
        ('rows.append(dict(prior,run_id=rid,block=block,seed=seed,config_sha256=digest))',
         'rows.append(dict(prior,run_id=rid,block=block,seed=seed,arm=arm,config_sha256=digest))'),
        ("normalized.append(common_config(cfg,run_id=rid,run_dir=root/'runs'/rid))",'normalized.append(normalize(cfg,arm,rid,root,common_config))'),
        ('any(normalized[i]!=normalized[i+1] for i in range(0,8,2))','any(normalized[i]!=normalized[i+j] for i in range(0,12,3) for j in (1,2))'),
        ('range(0,8,2)','range(0,12,3)'),
        ('worker_wall_seconds=600,step_time_limit_minutes=11','worker_wall_seconds=1200,step_time_limit_minutes=21'),
        ('min_remaining_seconds_to_launch=1020','min_remaining_seconds_to_launch=1620'),
        ('run_count=8','run_count=12'),('runs=8','runs=12'),('nominal_gpu_hours=3','nominal_gpu_hours=6'),
        ('nominal_allocation_gpu_hours=3','nominal_allocation_gpu_hours=6'),
        ("development_purpose='wallclock_600_complete_iteration_incumbent'","development_purpose='three_arm_preservation_1200_e2e'"),
        ('scientific_search_seconds=600','scientific_search_seconds=1200'),("'8-run dispatch'","'12-run dispatch'")]
    for a,b in replacements:
        if a not in source:raise ValueError('exact builder anchor absent')
        source=source.replace(a,b)
    ns={**vars(common),'normalize':normalize};exec(compile(source,'<three-arm-preparation>','exec'),ns)
    with redirect_stdout(io.StringIO()) as out:ns['build'](stage,block_minutes=180,block_ids=(1,2),config_transform=cfg_transform)
    info=json.loads(out.getvalue());root=Path(info['package']);template=(root/'launchers/forets_wallclock.sbatch').read_text()
    template=once(template,'#SBATCH --time=04:00:00','#SBATCH --time=03:00:00')
    template=once(template,'#SBATCH --job-name=forets-edit-scope-b1','#SBATCH --job-name=forets-preserve-b1')
    for block in (1,2):
        text=template if block==1 else once(once(template,'execute --block 1','execute --block 2'),
            '#SBATCH --job-name=forets-preserve-b1','#SBATCH --job-name=forets-preserve-b2')
        write(root/f'launchers/preserve-b{block}.sbatch',text.encode())
    write(root/'closed-parent-facts.json',encode(FACTS));print(json.dumps(info))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('artifacts','build'));p.add_argument('path',type=Path);p.add_argument('--facts',required=True,type=Path);a=p.parse_args()
    os.umask(0o077);configure(a.facts)
    (artifact_builder.artifacts if a.mode=='artifacts' else build)(a.path)
