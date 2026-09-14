"""New three-arm selector study, not the blocked scope-preservation extension."""
import argparse,inspect,io,json,os,sqlite3
from contextlib import closing,redirect_stdout
from pathlib import Path
import build_forets_wallclock_20260912 as common
import build_forets_common_start_20260913 as artifact_builder
from build_forets_action_prospective_20260913 import replace_function
from forets_environment_build_20260912 import read,write,encode,sha,git,PREFIX
from forets_paid_patch_20260911 import once

BASE='8bb325fa167a9db54656dd6535ce1f3d69859c22'
PARENT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-88v5m9dr')
PREPARED='731001dfa4c054ec16823bbfb685de1f2ad14314e5d5ad4597d12097b713b979'
AUTH_PARENT='643792f11da84620df02fe88ada4759272ff2915dbdf3c8466c5730cb16a3318'
COUNTS=(2619,7666052390,6266052390,2)
CAP=10**10-COUNTS[1]
PLAN='FORETS_CHEAP_SELECTOR_PLAN_20260914.md'
SEEDS=(46,47);ARMS=('uniform','short_code','learned_validity')
def order():
    rows=[]
    for block,seed in enumerate(SEEDS,1):
        for i,task in enumerate(('leaf-classification','spaceship-titanic')):
            offset=(block-1+i)%3;arms=ARMS[offset:]+ARMS[:offset]
            rows.extend((block,task,seed,arm) for arm in arms)
    return rows
def parent_calls():
    # Full physical closure is required; no dependence on EScope effect/gate.
    for block in (1,2):
        started=read(PARENT/f'block-{block}.runtime/started.json');pool=read(PARENT/started['pool_manifest'])
        if len(pool['tasks'])!=8 or any(t['status'] in ('pending','launching','running') for t in pool['tasks'].values()):raise ValueError('parent not closed')
    modelroot=PARENT.parent/'forets-task-validity-20260914-n8q3h72y'
    read(modelroot/'summary.json','66be27cbde084c433df25e95cd803bc7f42df3c71ad7d72af23528205d928a33')
    read(modelroot/'independent.json','8fbd1c92e404ffbe585810a174ce78611e6df71ead976ced669019e84b2265cb')
    with closing(sqlite3.connect((PARENT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('SELECT digest,stopped FROM auth').fetchall()!=[(AUTH_PARENT,0)]:raise ValueError('active predecessor')
        rows=db.execute('SELECT * FROM calls ORDER BY id').fetchall()
    if (len(rows),sum(r[2] for r in rows),sum(r[3] or 0 for r in rows),sum(r[4]=='unresolved' for r in rows))!=COUNTS:raise ValueError('prior liability drift')
    return rows
def changed_sources():
    auth=dict(version=23,total=10**10,incremental_cap=CAP,predecessor_authorization=AUTH_PARENT,
        predecessor_accounted=COUNTS[1],predecessor_settled=COUNTS[2],predecessor_calls=COUNTS[0],predecessor_unresolved=2,
        experiment='cheap_selector_600_three_arm_seeds46_47',run_limit=CAP,route_limit=CAP)
    get=lambda p:git('show',BASE+':'+p).decode()
    budget=once(get(PREFIX+'paid_budget.py'),'AUTH_RAW = json.dumps(AUTH,','AUTH.update('+repr(auth)+')\nAUTH_RAW = json.dumps(AUTH,')
    cfg=once(get('src/dojo/config_dataclasses/solver/fore_ts.py'),'    edit_scope: str = "whole_program"','    edit_scope: str = "whole_program"\n    cheap_ranker: str = "none"')
    cfg=once(cfg,'        super().validate()','        super().validate()\n        if self.cheap_ranker not in ("none", "short_code", "learned_validity"):\n            raise ValueError("cheap ranker")\n        if self.cheap_ranker != "none" and self.selection_policy != "critic_topk_random":\n            raise ValueError("ranker requires scored selection")')
    batch=get('src/dojo/solvers/fore_ts/batch_runtime.py')
    old='''                from dojo.solvers.fore_ts.reference_context import reference_context
                from dojo.solvers.fore_ts.wallclock import budget
                references = reference_context(solver, parent, budget_spec=budget())
                scores = await rank_pool(solver.task_name, [node.code for node in nodes],
                                         solver.state.current_step, root, reference_context=references)'''
    new='''                if solver.cfg.cheap_ranker != 'none':
                    from dojo.solvers.fore_ts.cheap_ranker import rank_codes
                    scores = rank_codes(solver, [node.code for node in nodes], root, solver.state.current_step)
                else:
                    from dojo.solvers.fore_ts.reference_context import reference_context
                    from dojo.solvers.fore_ts.wallclock import budget
                    references = reference_context(solver, parent, budget_spec=budget())
                    scores = await rank_pool(solver.task_name, [node.code for node in nodes],
                                             solver.state.current_step, root, reference_context=references)'''
    batch=once(batch,old,new)
    batch=once(batch,'    binding.update(selection_coupling=coupling)','    binding.update(selection_coupling=coupling, cheap_ranker=solver.cfg.cheap_ranker)')
    selection=get('src/dojo/solvers/fore_ts/selection.py')
    selection=once(selection,'        eligible = sorted(ranked[:min(top_k, count)])','        threshold = scores[ranked[min(top_k, count)-1]]\n        eligible = [i for i in range(count) if scores[i] >= threshold]')
    selection=selection.replace('# Preserve stable slot-order ties. Sort the eligible set back into slot\n        # order before drawing, so top-k==pool exactly couples to the random arm.','# Keep all ties at the cutoff; common priority randomizes ties fairly.\n        # This is the frozen new selector protocol, not a change to old runs.')
    registry=get('src/dojo/config_dataclasses/interpreter/__init__.py')
    registry=once(registry,'INTERPRETER_MAP = {','from dojo.core.interpreters.fresh_container import FreshContainerInterpreter\n\nINTERPRETER_MAP = {\n    "FreshContainerInterpreterConfig": FreshContainerInterpreter,')
    here=Path(__file__).parent.parent
    changes={PREFIX+'paid_budget.py':budget.encode(),'src/dojo/config_dataclasses/solver/fore_ts.py':cfg.encode(),
        'src/dojo/solvers/fore_ts/batch_runtime.py':batch.encode(),'src/dojo/solvers/fore_ts/selection.py':selection.encode(),
        'src/dojo/config_dataclasses/interpreter/__init__.py':registry.encode(),
        'src/dojo/solvers/fore_ts/cheap_ranker.py':Path(__file__).with_name('forets_cheap_ranker_20260914.py').read_bytes().replace(b'\r\n',b'\n')}
    for name in ('src/dojo/core/interpreters/fresh_container.py','src/dojo/config_dataclasses/interpreter/fresh_container.py'):
        changes[name]=(here/name).read_bytes().replace(b'\r\n',b'\n')
    return changes
def cfg_transform(cfg,arm):
    s=cfg['solver']
    if (s['num_children'],s['num_children_to_choose'],s['execution_timeout'],s['selection_policy'],s['use_test_score'],s['edit_scope'])!=(2,2,300,'uniform_random',False,'whole_program'):raise ValueError('whole program donor')
    s.update(time_limit_secs=600,num_children_to_choose=1,critic_top_k=1,
        selection_policy='uniform_random' if arm=='uniform' else 'critic_topk_random',cheap_ranker='none' if arm=='uniform' else arm)
    if cfg['interpreter']['_dojo_dataclass_type']!='dojo.config_dataclasses.interpreter.jupyter:JupyterInterpreterConfig':raise ValueError('original interpreter donor')
    cfg['interpreter']['_dojo_dataclass_type']='dojo.config_dataclasses.interpreter.fresh_container:FreshContainerInterpreterConfig'
    return cfg
def normalize(cfg,arm,rid,root,normalizer):
    clone=json.loads(json.dumps(cfg));clone['solver'].pop('cheap_ranker')
    return normalizer(clone,run_id=rid,run_dir=root/'runs'/rid)
def derive(name,text):
    if name=='forets_block_controller_20260911.py':
        text=replace_function(text,'expected_order','def expected_order():\n    return '+repr(tuple(order())))
        for a,b in [('ALLOCATION_SECONDS = 240 * 60','ALLOCATION_SECONDS = 90 * 60'),('STEP_WITH_TERMINATION_SECONDS = 1620','STEP_WITH_TERMINATION_SECONDS = 1020'),("correction['proposed_block_minutes'] != 240","correction['proposed_block_minutes'] != 90"),('len(spec.run_ids) != 8','len(spec.run_ids) != 6'),('allocation_minutes=240','allocation_minutes=90')]:text=once(text,a,b)
    elif name=='forets_native_run_20260911.py':text=once(text,'len(configs) != 8','len(configs) != 6')
    elif name=='forets_native_context_20260911.py':text=once(text,'FORETS_SEARCH_SECONDS="1200"','FORETS_SEARCH_SECONDS="600"')
    elif name=='forets_paid_route_20260911.py':text=once(text,"FORETS_PAID_SCOPE='route_edit_scope'","FORETS_PAID_SCOPE='route_cheap_selector'")
    return text
def configure():
    for k,v in dict(BASE=BASE,PARENT=PARENT,BILLING=PARENT,PREPARED=PREPARED,AUTH_PARENT=AUTH_PARENT,PLAN=PLAN,SEEDS=SEEDS,
        NEW_CAP=CAP,ROUTE_SCOPE='route_cheap_selector',SBATCH_TEMPLATE='edit-scope-b1.sbatch',order=order,parent_calls=parent_calls,derive=derive).items():setattr(common,k,v)
    artifact_builder.BASE=BASE;artifact_builder.PLAN=PLAN;artifact_builder.order=order;artifact_builder.changed_sources=changed_sources
def build(stage):
    source=inspect.getsource(common.build)
    replacements=[("prior=prior_rows[(task,arm)]","prior=prior_rows[(task,'whole_program')]"),
        ('cfg = config_transform(cfg)','cfg = config_transform(cfg,arm)'),
        ('rows.append(dict(prior,run_id=rid,block=block,seed=seed,config_sha256=digest))','rows.append(dict(prior,run_id=rid,block=block,seed=seed,arm=arm,config_sha256=digest))'),
        ("normalized.append(common_config(cfg,run_id=rid,run_dir=root/'runs'/rid))",'normalized.append(normalize(cfg,arm,rid,root,common_config))'),
        ('any(normalized[i]!=normalized[i+1] for i in range(0,8,2))','any(normalized[i]!=normalized[i+j] for i in range(0,12,3) for j in (1,2))'),
        ('range(0,8,2)','range(0,12,3)'),('run_count=8','run_count=12'),('runs=8','runs=12'),
        ("development_purpose='wallclock_600_complete_iteration_incumbent'","development_purpose='cheap_selector_three_arm_600_e2e'"),("'8-run dispatch'","'12-run dispatch'")]
    for a,b in replacements:
        if a not in source:raise ValueError('builder anchor: '+a)
        source=source.replace(a,b)
    ns={**vars(common),'normalize':normalize};exec(compile(source,'<cheap-selector-builder>','exec'),ns)
    with redirect_stdout(io.StringIO()) as out:ns['build'](stage,block_minutes=90,block_ids=(1,2),config_transform=cfg_transform)
    info=json.loads(out.getvalue());root=Path(info['package']);template=(root/'launchers/forets_wallclock.sbatch').read_text()
    template=once(template,'#SBATCH --time=04:00:00','#SBATCH --time=01:30:00')
    template=once(template,'#SBATCH --job-name=forets-edit-scope-b1','#SBATCH --job-name=forets-cheap-b1')
    for block in (1,2):
        text=template if block==1 else once(once(template,'execute --block 1','execute --block 2'),'#SBATCH --job-name=forets-cheap-b1','#SBATCH --job-name=forets-cheap-b2')
        write(root/f'launchers/cheap-b{block}.sbatch',text.encode())
    print(json.dumps(info))
def activate(root):
    import build_edit_scope_20260914 as prior
    text=once(inspect.getsource(prior.activate),"['route_edit_scope']","['route_cheap_selector']")
    ns=dict(vars(prior));ns.update(parent_calls=parent_calls,BILLING=PARENT,AUTH_PARENT=AUTH_PARENT,NEW_CAP=CAP)
    exec(compile(text,'<atomic-cheap-selector-handover>','exec'),ns);ns['activate'](root)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('artifacts','build','activate'));p.add_argument('path',type=Path);a=p.parse_args();os.umask(0o077);configure()
    (artifact_builder.artifacts if a.mode=='artifacts' else globals()[a.mode])(a.path)
