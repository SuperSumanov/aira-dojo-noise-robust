"""Prior-error memory contrast; actual configuration templates, no model update."""
import argparse
from contextlib import redirect_stdout
import inspect
import io
import json
import os
from pathlib import Path
import build_forets_width_control_20260913 as width
import build_forets_common_start_20260913 as parent_builder
import build_forets_wallclock_20260912 as common
from build_forets_action_prospective_20260913 import replace_function
from forets_environment_build_20260912 import read,write,encode,sha,git,PREFIX
from forets_paid_patch_20260911 import once
from forets_execution_memory_20260913 import frozen_memory,apply_memory,OPERATORS,TEXT_SHA

SEEDS=(40,41)
ARMS=('no_memory','execution_memory')
PLAN='FORETS_EXECUTION_MEMORY_PLAN_20260913.md'
FACTS=None
MEMORY=None
BASE=None
PARENT=None
PREPARED=None
AUTH_PARENT=None

def order():
    return [(block,task,seed,arm) for block,seed in enumerate(SEEDS,1)
        for i,task in enumerate(('leaf-classification','spaceship-titanic'))
        for arm in (ARMS if (seed+i)%2==0 else tuple(reversed(ARMS)))]

def derive(name,text):
    if name=='forets_block_controller_20260911.py':
        text=replace_function(text,'expected_order','def expected_order():\n    return '+repr(tuple(order())))
    if name=='forets_paid_route_20260911.py':
        text=once(text,"FORETS_PAID_SCOPE='route_width_control'","FORETS_PAID_SCOPE='route_memory_control'")
    return text

def config_transform(cfg,arm):
    if arm not in ARMS:raise ValueError('frozen arm')
    if (cfg['solver']['time_limit_secs'],cfg['solver']['action_delivery_protocol'])!=(600,'original_search_visible_action_delivery_v1'):
        raise ValueError('same time/delivery protocol')
    return apply_memory(cfg,MEMORY,arm=='execution_memory')

def normalized_template(cfg,rid,root,common_config):
    clone=json.loads(json.dumps(cfg))
    for k in OPERATORS:
        template=clone['solver']['operators'][k]['system_message_prompt_template']
        suffix='\n\n'+MEMORY['text']
        if template['template'].endswith(suffix):template['template']=template['template'][:-len(suffix)]
    return common_config(clone,run_id=rid,run_dir=root/'runs'/rid)

def changed_sources():
    count,held,settled,unknown=FACTS['billing_counts']
    if unknown!=2 or not 0<=settled<=held<10**10:raise ValueError('cumulative budget')
    auth=dict(version=19,total=10**10,incremental_cap=10**10-held,predecessor_authorization=AUTH_PARENT,
        predecessor_accounted=held,predecessor_settled=settled,predecessor_calls=count,
        predecessor_unresolved=unknown,experiment='frozen-prior-error-memory-seeds40-41')
    text=once(git('show',BASE+':'+PREFIX+'paid_budget.py').decode(),'AUTH_RAW = json.dumps(AUTH,',
        'AUTH.update('+repr(auth)+')\nAUTH_RAW = json.dumps(AUTH,')
    return {PREFIX+'paid_budget.py':text.encode()}

def configure(facts):
    global FACTS,MEMORY,BASE,PARENT,PREPARED,AUTH_PARENT
    FACTS=read(facts)
    if FACTS['protocol']!='closed_uniform_width_seeds38_39':raise ValueError('closed width predecessor only')
    BASE=FACTS['source_tree'];PARENT=Path(FACTS['root']);PREPARED=FACTS['prepared_sha256'];AUTH_PARENT=FACTS['authorization']
    if not PARENT.as_posix().startswith('/research/d7/spc/yzyang4/forets-wallclock-20260912-'):raise ValueError('predecessor location')
    directory=Path(__file__).resolve().parent
    if not (directory/'closed-error-families.json').exists():
        directory=directory/'results/forets_reference_s32_s33_20260913'
    MEMORY=frozen_memory(directory/'closed-error-families.json',directory/'closed-error-recurrence.json')
    vals=dict(BASE=BASE,PARENT=PARENT,PREPARED=PREPARED,AUTH_PARENT=AUTH_PARENT,FACTS=FACTS)
    for k,v in vals.items():setattr(width,k,v)
    # Reuse only the unchanged exact closure/ledger validator, with frozen facts.
    for k,v in dict(**vals,PLAN=PLAN,SEEDS=SEEDS,NEW_CAP=10**10-FACTS['billing_counts'][1],
        order=order,parent_calls=width.parent_calls,derive=derive,config_transform=config_transform,changed_sources=changed_sources).items():
        setattr(parent_builder,k,v)
    parent_builder.configure();common.ROUTE_SCOPE='route_memory_control'

def build(stage):
    text=inspect.getsource(common.build)
    text=once(text,"prior=prior_rows[(task,arm)]","prior=prior_rows[(task,'direct_two')]")
    text=once(text,'cfg = config_transform(cfg)','cfg = config_transform(cfg,arm)')
    text=once(text,'rows.append(dict(prior,run_id=rid,block=block,seed=seed,config_sha256=digest))',
        'rows.append(dict(prior,run_id=rid,block=block,seed=seed,arm=arm,proposal_width=2,memory_enabled=(arm==\'execution_memory\'),config_sha256=digest))')
    text=once(text,"normalized.append(common_config(cfg,run_id=rid,run_dir=root/'runs'/rid))",
        'normalized.append(normalized_template(cfg,rid,root,common_config))')
    text=once(text,"raise ValueError('two arms differ beyond policy')","raise ValueError('two arms differ beyond frozen memory')")
    text=once(text,"development_purpose='wallclock_600_complete_iteration_incumbent'",
        "development_purpose='execution_memory_action_primary_iteration_secondary'")
    ns={**vars(common),'normalized_template':normalized_template};exec(compile(text,'<explicit-memory-builder>','exec'),ns)
    buf=io.StringIO()
    with redirect_stdout(buf):ns['build'](stage,block_minutes=90,block_ids=(1,2),config_transform=config_transform)
    info=json.loads(buf.getvalue());root=Path(info['package']);template=(root/'launchers/forets_wallclock.sbatch').read_text()
    for block in (1,2):
        script=once(template,'execute --block 1',f'execute --block {block}')
        script=once(script,'#SBATCH --job-name=forets-width-b1',f'#SBATCH --job-name=forets-memory-b{block}')
        write(root/f'launchers/singlevote-b{block}.sbatch',script.encode())
    write(root/'frozen-memory.json',encode(MEMORY))
    print(json.dumps(info))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('artifacts','build','activate'));p.add_argument('path',type=Path)
    p.add_argument('--facts',type=Path,required=True);a=p.parse_args();os.umask(0o077);configure(a.facts)
    (parent_builder.artifacts if a.mode=='artifacts' else common.activate if a.mode=='activate' else build)(a.path)
