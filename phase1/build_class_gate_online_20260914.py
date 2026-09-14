"""Single-worker four-selector mechanism pilot; exact inherited billing."""
import argparse,inspect,io,json,os,sqlite3
from contextlib import closing,redirect_stdout
from pathlib import Path
import build_forets_wallclock_20260912 as common
import build_forets_common_start_20260913 as artifact_builder
from build_forets_action_prospective_20260913 import replace_function
from forets_environment_build_20260912 import read,write,encode,sha,git,PREFIX
from forets_paid_patch_20260911 import once

BASE='61b48862532d048f5f04a517e3f89b211c59bd3d'
PARENT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-km65uuej')
BILLING=PARENT
PREPARED='b2f53da2f6c9cde40c3a6b066a2670a13073f08547bb5d7f301ae4ba8293720b'
AUTH_PARENT='42c7dff9a962500c91bc40b7e5928d688a525638b8afb66c0bcd20e4206031b7'
COUNTS=(2837,8139684380,6739684380,2)
CAP=10**10-COUNTS[1]
PLAN='FORETS_CLASS_GATE_ONLINE_PLAN_20260914.md'
SEEDS=(48,);ARMS=('uniform','short_code','learned_validity','class_gate')
ROUTE='route_class_gate_s48'

def order():
    return [(1,t,48,a) for t,arms in (('leaf-classification',('learned_validity','class_gate','uniform','short_code')),
        ('spaceship-titanic',('uniform','short_code','learned_validity','class_gate'))) for a in arms]

def parent_calls():
    finish=read(PARENT/'readout-finished.json')
    if finish['status']!='verified':raise ValueError('current full readout first')
    independent=read(PARENT/'cheap-selector-independent.json')
    if independent['summary_sha256']!=finish['summary_sha256']:raise ValueError('independent predecessor readout')
    if independent['technical_eligible']!=12:raise ValueError('unresolved infrastructure; do not launch')
    with closing(sqlite3.connect((PARENT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('SELECT digest,stopped FROM auth').fetchall()!=[(AUTH_PARENT,0)]:raise ValueError('active closed predecessor')
        rows=db.execute('SELECT * FROM calls ORDER BY id').fetchall()
    if (len(rows),sum(r[2] for r in rows),sum(r[3] or 0 for r in rows),sum(r[4]=='unresolved' for r in rows))!=COUNTS:raise ValueError('frozen liability drift')
    return rows

def changed_sources():
    get=lambda n:git('show',BASE+':'+n).decode()
    auth=dict(version=25,total=10**10,incremental_cap=CAP,predecessor_authorization=AUTH_PARENT,
        predecessor_accounted=COUNTS[1],predecessor_settled=COUNTS[2],predecessor_calls=COUNTS[0],predecessor_unresolved=2,
        experiment='class_gate_single_worker_four_arm_s48_600',run_limit=CAP,route_limit=CAP,concurrent_search_workers=1)
    budget=once(get(PREFIX+'paid_budget.py'),'AUTH_RAW = json.dumps(AUTH,','AUTH.update('+repr(auth)+')\nAUTH_RAW = json.dumps(AUTH,')
    cfg=once(get('src/dojo/config_dataclasses/solver/fore_ts.py'),'("none", "short_code", "learned_validity")','("none", "short_code", "learned_validity", "class_gate")')
    rank=get('src/dojo/solvers/fore_ts/cheap_ranker.py')
    rank=once(rank,"('short_code','learned_validity')","('short_code','learned_validity','class_gate')")
    rank=once(rank,'    if len(scores)!=len(codes)',"    probabilities=list(scores) if kind!='short_code' else None\n    if kind=='class_gate':scores=[float(p>.5) for p in probabilities]\n    if len(scores)!=len(codes)")
    rank=once(rank,"model_sha256=MODEL_SHA if kind=='learned_validity' else None","raw_probabilities=probabilities,model_sha256=MODEL_SHA if kind in ('learned_validity','class_gate') else None")
    return {PREFIX+'paid_budget.py':budget.encode(),'src/dojo/config_dataclasses/solver/fore_ts.py':cfg.encode(),
        'src/dojo/solvers/fore_ts/cheap_ranker.py':rank.encode()}

def cfg_transform(cfg,arm):
    s=cfg['solver']
    if (s['num_children'],s['num_children_to_choose'],s['cheap_ranker'],s['execution_timeout'])!=(2,1,'none',300):raise ValueError('uniform donor')
    s.update(selection_policy='uniform_random' if arm=='uniform' else 'critic_topk_random',cheap_ranker='none' if arm=='uniform' else arm)
    return cfg

def normalize(cfg,arm,rid,root,normalizer):
    clone=json.loads(json.dumps(cfg));clone['solver'].pop('cheap_ranker')
    return normalizer(clone,run_id=rid,run_dir=root/'runs'/rid)

def derive(name,text):
    if name=='forets_block_controller_20260911.py':
        text=replace_function(text,'expected_order','def expected_order():\n    return '+repr(tuple(order())))
        for a,b in [('ALLOCATION_SECONDS = 85 * 60','ALLOCATION_SECONDS = 95 * 60'),("correction['proposed_block_minutes'] != 85","correction['proposed_block_minutes'] != 95"),('len(spec.run_ids) != 6','len(spec.run_ids) != 8'),('allocation_minutes=85','allocation_minutes=95')]:text=once(text,a,b)
    elif name=='forets_native_run_20260911.py':text=once(text,'len(configs) != 6','len(configs) != 8')
    elif name=='forets_paid_route_20260911.py':text=once(text,"FORETS_PAID_SCOPE='route_cheap_selector_v2'","FORETS_PAID_SCOPE='"+ROUTE+"'")
    return text

def configure():
    for k,v in dict(BASE=BASE,PARENT=PARENT,BILLING=BILLING,PREPARED=PREPARED,AUTH_PARENT=AUTH_PARENT,PLAN=PLAN,SEEDS=SEEDS,
        NEW_CAP=CAP,ROUTE_SCOPE=ROUTE,SBATCH_TEMPLATE='cheap-b1.sbatch',order=order,parent_calls=parent_calls,derive=derive).items():setattr(common,k,v)
    artifact_builder.BASE=BASE;artifact_builder.PLAN=PLAN;artifact_builder.order=order;artifact_builder.changed_sources=changed_sources

def build(stage):
    text=inspect.getsource(common.build)
    for a,b in [("((180,(1,)), (90,(1,2)))","((95,(1,)),)"),("prior=prior_rows[(task,arm)]","prior=prior_rows[(task,'uniform')]"),
        ('cfg = config_transform(cfg)','cfg = config_transform(cfg,arm)'),
        ('rows.append(dict(prior,run_id=rid,block=block,seed=seed,config_sha256=digest))','rows.append(dict(prior,run_id=rid,block=block,seed=seed,arm=arm,config_sha256=digest))'),
        ("normalized.append(common_config(cfg,run_id=rid,run_dir=root/'runs'/rid))",'normalized.append(normalize(cfg,arm,rid,root,common_config))'),
        ('any(normalized[i]!=normalized[i+1] for i in range(0,8,2))','any(normalized[i]!=normalized[i+j] for i in (0,4) for j in (1,2,3))'),
        ('range(0,8,2)','(0,4)'),('paired_configs=4','paired_configs=2'),('nominal_gpu_hours=3','nominal_gpu_hours=95/60'),
        ('nominal_allocation_gpu_hours=3','nominal_allocation_gpu_hours=95/60'),
        ("development_purpose='wallclock_600_complete_iteration_incumbent'","development_purpose='class_gate_single_worker_four_arm_s48'")]:
        if a not in text:raise ValueError('builder anchor '+a)
        text=text.replace(a,b)
    ns={**vars(common),'normalize':normalize};exec(compile(text,'<class-gate-builder>','exec'),ns)
    with redirect_stdout(io.StringIO()) as out:ns['build'](stage,block_minutes=95,block_ids=(1,),config_transform=cfg_transform)
    info=json.loads(out.getvalue());root=Path(info['package']);template=(root/'launchers/forets_wallclock.sbatch').read_text()
    template=once(template,'#SBATCH --time=01:25:00','#SBATCH --time=01:35:00')
    template=once(template,'#SBATCH --job-name=forets-cheap-v2-b1','#SBATCH --job-name=forets-class-gate-s48')
    write(root/'launchers/class-gate.sbatch',template.encode());print(json.dumps(info))

def activate(root):
    import build_edit_scope_20260914 as previous
    text=once(inspect.getsource(previous.activate),"['route_edit_scope']","['"+ROUTE+"']")
    ns=dict(vars(previous));ns.update(parent_calls=parent_calls,BILLING=BILLING,AUTH_PARENT=AUTH_PARENT,NEW_CAP=CAP)
    exec(compile(text,'<atomic-class-gate-handover>','exec'),ns);ns['activate'](root)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('artifacts','build','activate'));p.add_argument('path',type=Path);a=p.parse_args();os.umask(0o077);configure()
    (artifact_builder.artifacts if a.mode=='artifacts' else globals()[a.mode])(a.path)
