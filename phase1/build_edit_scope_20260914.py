"""Frozen 16-run edit-scope study, building does not call models or dispatch GPUs."""
import argparse
from contextlib import closing, redirect_stdout
import inspect
import io
import json
import os
from pathlib import Path
import sqlite3
import build_forets_common_start_20260913 as artifacts_builder
import build_forets_wallclock_20260912 as common
from build_forets_action_prospective_20260913 import replace_function
from forets_environment_build_20260912 import read, write, encode, sha, git, PREFIX
from forets_paid_patch_20260911 import once
from forets_edit_scope_20260914 import apply_config, HEADER, INSTRUCTION

BASE = '746d97a67922896b7d1581c4689f8b5f85204d30'
PARENT = Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-103zf3nb')
BILLING = PARENT.parent/'forets-repair-transfer-20260913-d151en61'
PREPARED = 'b676bfa46afae3c6e83b1d98855e77a368994fe7fdc22263f6693d581a4a57fd'
AUTH_PARENT = 'a3a4561fb81d538d797e32997cf75deff8131784d8fa12da5b329a76f023743e'
COUNTS = (1779, 6366536198, 4966536198, 2)
PLAN = 'FORETS_EDIT_SCOPE_PLAN_20260914.md'
SEEDS = (42, 43, 44, 45)
ARMS = ('whole_program', 'model_module')
NEW_CAP = 10**10 - COUNTS[1]


def order():
    rows = []
    for block, seeds in enumerate(((42, 43), (44, 45)), 1):
        for seed in seeds:
            for i, task in enumerate(('leaf-classification', 'spaceship-titanic')):
                arms = ARMS if (seed+i) % 2 == 0 else ARMS[::-1]
                rows.extend((block, task, seed, arm) for arm in arms)
    return rows


def parent_calls():
    if read(BILLING/'readout-finished.json', '344915af2c014f029bb1c098aea6909ab466c1496e479de6af1a41a1585707ea')['summary_sha256'] != '4157031453885d61f8129ba116cbb7d8d8a5307dddd388df9b7efa714d14cb17':
        raise ValueError('T1 must be closed')
    with closing(sqlite3.connect((BILLING/'paid.sqlite').as_uri()+'?mode=ro', uri=True)) as db:
        if db.execute('SELECT digest,stopped FROM auth').fetchall() != [(AUTH_PARENT, 0)]:
            raise ValueError('active predecessor required')
        rows = db.execute('SELECT * FROM calls ORDER BY id').fetchall()
    actual = (len(rows), sum(r[2] for r in rows), sum(r[3] or 0 for r in rows), sum(r[4]=='unresolved' for r in rows))
    if actual != COUNTS:
        raise ValueError('prior cost drift')
    return rows


def config_transform(cfg, arm):
    s = cfg['solver']
    if (s['num_children'], s['num_children_to_choose'], s['execution_timeout'], s['selection_policy'], s['use_test_score']) != (2, 2, 300, 'uniform_random', False):
        raise ValueError('same native search contract')
    s['time_limit_secs'] = 1200
    # Copy the no-memory parent only. Never strip an unknown prompt suffix.
    if any('Historical execution-error observations' in s['operators'][n]['system_message_prompt_template']['template'] for n in ('draft','improve','debug')):
        raise ValueError('old memory present')
    return apply_config(cfg, arm)


def normalized_template(cfg, rid, root, normalize):
    clone = json.loads(json.dumps(cfg))
    mode = clone['solver'].pop('edit_scope')
    if mode not in ARMS:
        raise ValueError('arm identity')
    for name in ('draft', 'improve', 'debug'):
        field = clone['solver']['operators'][name]['system_message_prompt_template']
        suffix = '\n\n'+HEADER+'\n'+INSTRUCTION
        if mode == 'model_module':
            if not field['template'].endswith(suffix): raise ValueError('module instruction drift')
            field['template'] = field['template'][:-len(suffix)]
    return normalize(clone, run_id=rid, run_dir=root/'runs'/rid)


def changed_sources():
    auth = dict(version=21, total=10**10, incremental_cap=NEW_CAP, predecessor_authorization=AUTH_PARENT,
        predecessor_accounted=COUNTS[1], predecessor_settled=COUNTS[2], predecessor_calls=COUNTS[0],
        predecessor_unresolved=2, experiment='edit_scope_1200_seconds_seeds42_45',
        run_limit=NEW_CAP, route_limit=NEW_CAP)
    budget = once(git('show', BASE+':'+PREFIX+'paid_budget.py').decode(), 'AUTH_RAW = json.dumps(AUTH,',
        'AUTH.update('+repr(auth)+')\nAUTH_RAW = json.dumps(AUTH,')
    config = git('show', BASE+':src/dojo/config_dataclasses/solver/fore_ts.py').decode()
    config = once(config, '    action_delivery_protocol: str = "none"', '    action_delivery_protocol: str = "none"\n    edit_scope: str = "whole_program"')
    config = once(config, '        super().validate()', '        super().validate()\n        if self.edit_scope not in ("whole_program", "model_module"):\n            raise ValueError("edit scope")')
    start = git('show', BASE+':src/dojo/solvers/fore_ts/common_start.py').decode()
    start = once(start, 'def code_for(task):', 'def original_code_for(task):')
    start += '\n\ndef code_for(task):\n    from dojo.solvers.fore_ts.edit_scope import code_for as scoped\n    return scoped(task)\n'
    forets = git('show', BASE+':src/dojo/solvers/fore_ts/fore_ts.py').decode()
    forets = once(forets, '        node = MCTSNode(plan=plan, code=code, parents=[], operators_used=["draft"], operators_metrics=[metrics])',
        '        from dojo.solvers.fore_ts.edit_scope import process\n        code, metrics = process(self, code, metrics)\n        node = MCTSNode(plan=plan, code=code, parents=[], operators_used=["draft"], operators_metrics=[metrics])')
    forets = once(forets, '        node = MCTSNode(\n            plan=plan, code=code, parents=[], operators_used=["improve"]',
        '        from dojo.solvers.fore_ts.edit_scope import process\n        code, metrics = process(self, code, metrics)\n        node = MCTSNode(\n            plan=plan, code=code, parents=[], operators_used=["improve"]')
    mcts = git('show', BASE+':src/dojo/solvers/mcts/mcts.py').decode()
    mcts = once(mcts, '        node = MCTSNode(\n            plan=plan, code=code, parents=[parent_node], operators_used=["debug"]',
        '        from dojo.solvers.fore_ts.edit_scope import process\n        code, metrics = process(self, code, metrics)\n        node = MCTSNode(\n            plan=plan, code=code, parents=[parent_node], operators_used=["debug"]')
    return {PREFIX+'paid_budget.py': budget.encode(), 'src/dojo/config_dataclasses/solver/fore_ts.py': config.encode(),
        'src/dojo/solvers/fore_ts/common_start.py': start.encode(), 'src/dojo/solvers/fore_ts/fore_ts.py': forets.encode(),
        'src/dojo/solvers/mcts/mcts.py': mcts.encode(),
        'src/dojo/solvers/fore_ts/edit_scope.py': Path(__file__).with_name('forets_edit_scope_20260914.py').read_bytes().replace(b'\r\n', b'\n')}


def derive(name, text):
    if name == 'forets_block_controller_20260911.py':
        text = replace_function(text, 'expected_order', 'def expected_order():\n    return '+repr(tuple(order())))
        for a,b in [('ALLOCATION_SECONDS = 90 * 60','ALLOCATION_SECONDS = 240 * 60'),
                    ('STEP_WITH_TERMINATION_SECONDS = 1020','STEP_WITH_TERMINATION_SECONDS = 1620'),
                    ("correction['proposed_block_minutes'] != 90","correction['proposed_block_minutes'] != 240"),
                    ('len(spec.run_ids) != 4','len(spec.run_ids) != 8'),('allocation_minutes=280','allocation_minutes=240')]:
            text = once(text,a,b)
    elif name == 'forets_native_run_20260911.py':
        text = once(text,'len(configs) != 4','len(configs) != 8')
    elif name == 'forets_native_context_20260911.py':
        text = once(text,'FORETS_SEARCH_SECONDS="600"','FORETS_SEARCH_SECONDS="1200"')
    elif name == 'forets_paid_route_20260911.py':
        text = once(text,"FORETS_PAID_SCOPE='route_memory_control'","FORETS_PAID_SCOPE='route_edit_scope'")
    return text


def configure():
    for k,v in dict(BASE=BASE,PARENT=PARENT,BILLING=BILLING,PREPARED=PREPARED,AUTH_PARENT=AUTH_PARENT,
        PLAN=PLAN,SEEDS=SEEDS,NEW_CAP=NEW_CAP,ROUTE_SCOPE='route_edit_scope',SBATCH_TEMPLATE='singlevote-b1.sbatch',
        order=order,parent_calls=parent_calls,derive=derive).items(): setattr(common,k,v)
    artifacts_builder.BASE = BASE
    artifacts_builder.PLAN = PLAN
    artifacts_builder.order = order
    artifacts_builder.changed_sources = changed_sources


def build(stage):
    source = inspect.getsource(common.build)
    replacements = [
        ("((180,(1,)), (90,(1,2)))", "((240,(1,2)),)"),
        ("prior=prior_rows[(task,arm)]", "prior=prior_rows[(task,'no_memory')]"),
        ('cfg = config_transform(cfg)', 'cfg = config_transform(cfg,arm)'),
        ('rows.append(dict(prior,run_id=rid,block=block,seed=seed,config_sha256=digest))',
         'rows.append(dict(prior,run_id=rid,block=block,seed=seed,arm=arm,config_sha256=digest))'),
        ("normalized.append(common_config(cfg,run_id=rid,run_dir=root/'runs'/rid))",'normalized.append(normalized_template(cfg,rid,root,common_config))'),
        ('range(0,8,2)', 'range(0,16,2)'),
        ('worker_wall_seconds=600,step_time_limit_minutes=11','worker_wall_seconds=1200,step_time_limit_minutes=21'),
        ('min_remaining_seconds_to_launch=1020','min_remaining_seconds_to_launch=1620'),
        ('run_count=8','run_count=16'),('paired_configs=4','paired_configs=8'),('nominal_gpu_hours=3','nominal_gpu_hours=8'),
        ('runs=8','runs=16'),('nominal_allocation_gpu_hours=3','nominal_allocation_gpu_hours=8'),
        ("development_purpose='wallclock_600_complete_iteration_incumbent'", "development_purpose='edit_scope_1200_e2e'"),
        ('scientific_search_seconds=600','scientific_search_seconds=1200'),
        ("'8-run dispatch'", "'16-run dispatch'")]
    for a,b in replacements:
        if a not in source: raise ValueError('builder anchor absent: '+a)
        source = source.replace(a,b)
    ns = {**vars(common), 'normalized_template': normalized_template}
    exec(compile(source,'<edit-scope-builder>','exec'),ns)
    capture = io.StringIO()
    with redirect_stdout(capture): ns['build'](stage,block_minutes=240,block_ids=(1,2),config_transform=config_transform)
    info = json.loads(capture.getvalue());root=Path(info['package'])
    template = (root/'launchers/forets_wallclock.sbatch').read_text()
    template = once(template,'#SBATCH --time=01:30:00','#SBATCH --time=04:00:00')
    template = once(template,'#SBATCH --job-name=forets-memory-b1','#SBATCH --job-name=forets-edit-scope-b1')
    for block in (1,2):
        script=template if block==1 else once(once(template,'execute --block 1','execute --block 2'),
            '#SBATCH --job-name=forets-edit-scope-b1','#SBATCH --job-name=forets-edit-scope-b2')
        write(root/f'launchers/edit-scope-b{block}.sbatch',script.encode())
    print(json.dumps(info))


def activate(root):
    calls = parent_calls(); facts=read(root/'parent-facts.json')
    if facts['calls_sha256']!=sha(encode(calls)): raise ValueError('handover facts drift')
    write(root/'activation-intent.json',encode(facts))
    fd=os.open(root/'paid.sqlite',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    ns={};exec(compile((root/'code/forets_paid_budget_20260911.py').read_bytes(),'<budget>','exec'),ns)
    with closing(sqlite3.connect(root/'paid.sqlite')) as db:
        db.execute('ATTACH DATABASE ? AS predecessor',(str(BILLING/'paid.sqlite'),))
        db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA predecessor.journal_mode=DELETE');db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT digest,stopped FROM predecessor.auth').fetchall()!=[(AUTH_PARENT,0)] or db.execute('SELECT * FROM predecessor.calls ORDER BY id').fetchall()!=calls:
            raise ValueError('concurrent prior mutation')
        db.execute('CREATE TABLE auth(digest TEXT NOT NULL,body TEXT NOT NULL,stopped INTEGER NOT NULL)')
        db.execute('CREATE TABLE scopes(scope TEXT PRIMARY KEY,cap INTEGER NOT NULL)')
        db.execute('CREATE TABLE calls(id TEXT PRIMARY KEY,scope TEXT NOT NULL,held INTEGER NOT NULL,cost INTEGER,state TEXT NOT NULL,created REAL NOT NULL)')
        db.execute('INSERT INTO auth VALUES(?,?,0)',(ns['AUTH_SHA'],ns['AUTH_RAW'].decode()))
        db.executemany('INSERT INTO calls VALUES(?,?,?,?,?,?)',calls)
        db.executemany('INSERT INTO scopes VALUES(?,0)',[(x,) for x in sorted({r[1] for r in calls})])
        scopes=[r['run_id'] for r in read(root/'prepared.json')['run_configs']]+['route_edit_scope']
        db.executemany('INSERT INTO scopes VALUES(?,?)',[(s,NEW_CAP) for s in scopes])
        db.execute('UPDATE predecessor.auth SET stopped=1');db.commit()
    write(root/'paid-authorization.json',encode(ns['AUTH']));write(root/'activation-complete.json',encode(facts))
    print(json.dumps(dict(status='ACTIVE_PREDECESSOR_SEALED',billing={k:v for k,v in ns['snapshot'](root/'paid.sqlite').items() if k!='scopes'})))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('artifacts','build','activate'));p.add_argument('path',type=Path)
    a=p.parse_args();os.umask(0o077);configure()
    (artifacts_builder.artifacts if a.mode=='artifacts' else globals()[a.mode])(a.path)
