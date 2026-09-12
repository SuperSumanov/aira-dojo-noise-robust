"""Fresh eight-run development package; artifact/build do not dispatch work.

The compatible source and native container adapter are reused, not requalified.
Only explicit predecessor code/config paths are copied. Ledger activation is
separate and preserves every previous charge and unresolved reservation.
"""
import argparse
from contextlib import closing
from decimal import Decimal
import json
import os
from pathlib import Path
import sqlite3
import sys
import tarfile
import tempfile

from forets_environment_build_20260912 import git, sha, encode, write, read, replace, PREFIX
from forets_paid_patch_20260911 import once
import forets_wallclock_patch_20260912 as hooks

BASE = '900fa3bdf6971381c37a9792723dba42c63e5ac6'
PARENT = Path('/research/d7/spc/yzyang4/forets-repeat-20260912-3no2iopd')
BILLING = PARENT.parent/'forets-generation-capacity-20260912-thgk111r'
AUTH_PARENT = '4d66bef41f5ad23d64a8e6f26350a25486eb65bbde5c416a531879d6b48925ca'
PREPARED = '883062309b6edeee43ac93be26042c9376279ab712948e034bceb39dc67dae1e'
PLAN = 'FORETS_WALLCLOCK_E2E_PLAN_20260912.md'
NEW_CAP = 3500000000


def order():
    rows = []
    for seed in (22, 23):
        for i, task in enumerate(('leaf-classification', 'spaceship-titanic')):
            arms = ['uniform_random', 'critic_topk_random']
            if (seed+i) % 2: arms.reverse()
            rows.extend((1, task, seed, arm) for arm in arms)
    return rows


def artifacts(output):
    output.mkdir(exist_ok=False)
    changed = {}
    methods = {'src/dojo/solvers/mcts/mcts.py': hooks.patch_mcts,
        'src/dojo/tasks/mlebench/task.py': hooks.patch_task,
        'src/dojo/tasks/mlebench/submission_archive.py': hooks.patch_archive,
        'src/dojo/core/runners/slurm/bounded_process.py': hooks.patch_supervisor,
        PREFIX+'paid_budget.py': hooks.patch_budget}
    for name, fn in methods.items():
        changed[name] = fn(git('show', BASE+':'+name).decode()).encode()
    auth = dict(version=10, total=2727324583+NEW_CAP, incremental_cap=NEW_CAP,
        predecessor_authorization=AUTH_PARENT, predecessor_accounted=2727324583,
        predecessor_settled=1327324583, predecessor_calls=402, predecessor_unresolved=2,
        experiment='wallclock-development-seeds22-23', run_limit=4000000000, route_limit=4000000000,
        accounted_cny_ceiling=str(Decimal(2727324583+NEW_CAP)/10**9*Decimal('8.8')))
    changed[PREFIX+'paid_budget.py'] = once(changed[PREFIX+'paid_budget.py'].decode(),
        'AUTH_RAW = json.dumps(AUTH,', 'AUTH.update('+repr(auth)+')\nAUTH_RAW = json.dumps(AUTH,').encode()
    changed['src/dojo/solvers/fore_ts/wallclock.py'] = Path(__file__).with_name('forets_wallclock_20260912.py').read_bytes().replace(b'\r\n',b'\n')
    for raw in changed.values(): compile(raw, '<cutoff source>', 'exec')
    with tempfile.TemporaryDirectory(prefix='forets-cutoff-index-') as temp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(temp)/'index')); git('read-tree', BASE, env=env)
        for name, raw in changed.items():
            blob = git('hash-object','-w','--stdin',data=raw).decode().strip()
            git('update-index','--add','--cacheinfo','100644,'+blob+','+name,env=env)
        tree = git('write-tree',env=env).decode().strip()
    files = {}
    for line in git('ls-tree','-r',tree,'--','src/aira_core','src/dojo').decode().splitlines():
        head,name=line.split('\t'); _,kind,blob=head.split()
        if kind!='blob': raise ValueError('source kind')
        files[name]=sha(git('cat-file','blob',blob))
    archive=git('-c','core.autocrlf=false','archive','--format=tar',tree,'src/aira_core','src/dojo',
        env=dict(os.environ,GIT_LFS_SKIP_SMUDGE='1'))
    write(output/'source.tar',archive)
    info=dict(base_tree=BASE,source_tree=tree,source_files=files,archive_sha256=sha(archive),
        modified_files=sorted(changed),commit=git('rev-parse','HEAD').decode().strip(),
        plan_sha256=sha(Path(__file__).with_name(PLAN).read_bytes()),matrix=order())
    write(output/'artifact.json',encode(info)); print(json.dumps({k:v for k,v in info.items() if k!='source_files'}))


def parent_calls():
    with closing(sqlite3.connect((BILLING/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('SELECT digest,stopped FROM auth').fetchall()!=[(AUTH_PARENT,0)]:
            raise ValueError('billing predecessor no longer active')
        rows=db.execute('SELECT * FROM calls ORDER BY id').fetchall()
    if (len(rows),sum(r[2] for r in rows),sum(r[3] or 0 for r in rows),sum(r[4]=='unresolved' for r in rows)) != (402,2727324583,1327324583,2):
        raise ValueError('billing facts changed')
    return rows


def derive(name, text):
    if name=='forets_block_controller_20260911.py':
        text=once(text,'ALLOCATION_SECONDS = 280 * 60','ALLOCATION_SECONDS = 180 * 60')
        text=once(text,'STEP_WITH_TERMINATION_SECONDS = 3930','STEP_WITH_TERMINATION_SECONDS = 1020')
        text=once(text,'    for block, seed in enumerate((15,), 1):','    for seed in (22, 23):\n        block = 1')
        text=once(text,'len(spec.run_ids) != 4','len(spec.run_ids) != 8')
        text=once(text,"correction['proposed_block_minutes'] != 280","correction['proposed_block_minutes'] != 180")
    if name=='forets_native_run_20260911.py':
        text=once(text,'len(configs) != 4','len(configs) != 8')
    if name=='forets_paid_route_20260911.py':
        text=once(text,"FORETS_PAID_SCOPE='route_s15'","FORETS_PAID_SCOPE='route_wallclock'")
    if name=='forets_native_context_20260911.py':
        text=once(text,'        additions = dict(FORETS_PAID_LEDGER=',
            '        additions = dict(FORETS_SEARCH_SECONDS="600",\n'
            '            FORETS_INCUMBENT_DIR=str(ROOT/"incumbents"/run_id), FORETS_PAID_LEDGER=')
    if name=='forets_block_runtime_20260911.py':
        anchor='    def _remaining_seconds(self): return self.runtime_budget.end-self.runtime_budget.now()\n'
        new='''    def _launch(self, run_id):
        from forets_paid_budget_20260911 import snapshot
        state=snapshot(ROOT_FOR_API_CATALOG/'paid.sqlite')
        if state['stopped'] or state['unresolved'] != 2:
            raise RuntimeError('new unresolved charge or stopped billing')
        names={a['job_name'] for t in self.manifest['tasks'].values() for a in t['attempts']}
        scheduler=Scheduler(self.runtime_budget,self.manifest['allocation_id'])
        deadline=min(self.runtime_budget.work,time.monotonic()+20)
        while names and scheduler.active_owned(names,deadline):
            time.sleep(min(.5,self.runtime_budget.left(deadline)))
        return super()._launch(run_id)

'''
        text=once(text,anchor,new+anchor)
    return text


def build(stage):
    info=read(stage/'artifact.json'); old=read(PARENT/'prepared.json',PREPARED); calls=parent_calls()
    if info['base_tree']!=BASE or info['matrix']!=[list(r) for r in order()]: raise ValueError('wrong frozen matrix/source')
    if sha((stage/PLAN).read_bytes())!=info['plan_sha256'] or sha((stage/'source.tar').read_bytes())!=info['archive_sha256']:
        raise ValueError('plan/source artifact drift')
    root=Path(tempfile.mkdtemp(prefix='forets-wallclock-20260912-',dir=PARENT.parent)); os.chmod(root,0o700)
    for n in ('source','code','configs','launchers','runs','incumbents'): (root/n).mkdir(mode=0o700)
    seen=set()
    with tarfile.open(stage/'source.tar') as archive:
        for item in archive:
            if item.isdir(): continue
            if not item.isfile() or item.name in seen or item.name not in info['source_files']: raise ValueError('archive member')
            dest=root/'source'/item.name
            if not dest.resolve().is_relative_to(root/'source'): raise ValueError('archive path')
            raw=archive.extractfile(item).read()
            if sha(raw)!=info['source_files'][item.name]: raise ValueError('archive hash')
            dest.parent.mkdir(parents=True,exist_ok=True); write(dest,raw); seen.add(item.name)
    if seen!=set(info['source_files']): raise ValueError('source coverage')
    inv_sha=write(root/'source-files.json',encode(info['source_files']))
    os.environ.update(PYTHON_DOTENV_DISABLED='1',LITELLM_LOCAL_MODEL_COST_MAP='True',LOGGING_DIR=str(root),
        MLE_BENCH_DATA_DIR=str(PARENT.parent/'mle-bench-data'),SUPERIMAGE_DIR=str(PARENT.parent/'aira-dojo/build/superimage'),
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu')
    sys.path[:0]=[str(root/'source/src'),str(PARENT/'code')]
    from dojo.config_dataclasses.run import RunConfig
    from forets_e2e_package import common_config
    prior_rows={(r['task'],r['arm']):r for r in old['run_configs']}; rows=[]; normalized=[]
    for i,(block,task,seed,arm) in enumerate(order()):
        prior=prior_rows[(task,arm)]; rid=f'{i:02d}-{task}-s{seed}-{arm}'
        cfg=replace(read(PARENT/'configs'/(prior['run_id']+'.json'),prior['config_sha256']),{str(PARENT):str(root),prior['run_id']:rid})
        cfg['metadata'].update(seed=seed,git_commit_id=info['commit'],description='wallclock-source-'+info['source_tree'])
        cfg['solver'].update(selector_seed=seed,step_limit=64,time_limit_secs=600)
        typed=RunConfig.from_dict(cfg); typed.validate()
        if typed.to_typed_dict()!=cfg: raise ValueError('typed config roundtrip')
        digest=write(root/'configs'/(rid+'.json'),encode(cfg))
        rows.append(dict(prior,run_id=rid,block=block,seed=seed,config_sha256=digest))
        normalized.append(common_config(cfg,run_id=rid,run_dir=root/'runs'/rid))
    if any(normalized[i]!=normalized[i+1] for i in range(0,8,2)): raise ValueError('two arms differ beyond policy')
    launcher=dict(old['launcher'],worker_wall_seconds=600,step_time_limit_minutes=11,
        min_remaining_seconds_to_launch=1020,step_termination_allowance_seconds=330,fail_fast=False)
    prepared=replace(old,{str(PARENT):str(root)})
    prepared.update(source_tree=info['source_tree'],base_source_tree=BASE,run_configs=rows,run_count=8,step_limit=64,
        launcher=launcher,nominal_gpu_hours=3,preparation_commit=info['commit'],source_archive_sha256=info['archive_sha256'],
        source_files=len(seen),paired_config_sha256=[sha(encode(normalized[i])) for i in range(0,8,2)],
        plan_sha256=info['plan_sha256'],remaining=['integration check','ledger activation','route/catalog','8-run dispatch'])
    prep_sha=write(root/'prepared.json',encode(prepared))
    manifest=read(PARENT/'manifest.json'); manifest.update(source_tree=info['source_tree'],runs=rows)
    write(root/'manifest.json',encode(manifest));write(root/'launchers/block-1.json',encode(launcher))
    correction=read(PARENT/'allocation-budget-correction.json');correction['proposed_block_minutes']=180
    correction_sha=write(root/'allocation-budget-correction.json',encode(correction))
    write(root/'PACKAGE_STATE.json',encode(read(PARENT/'PACKAGE_STATE.json')))
    budget=(root/'source'/PREFIX/'paid_budget.py').read_bytes(); ns={};exec(compile(budget,'<budget>','exec'),ns)
    release=read(PARENT/'code/forets_native_e2e_release_20260911.json'); old_release_sha=sha(encode(release))
    if old_release_sha!=sha((PARENT/'code/forets_native_e2e_release_20260911.json').read_bytes()): raise ValueError('release encoding')
    release.update(package=str(root),source_tree=info['source_tree'],seeds=[22,23],runs=8,block_minutes=180,
        gpus_per_block=1,cpus_per_block=6,maximum_gpu_hours_including_observed_killwait=None,
        nominal_allocation_gpu_hours=3,paid_authorization_sha256=ns['AUTH_SHA'],
        development_purpose='wallclock_600_complete_iteration_incumbent',scientific_search_seconds=600,
        physical_cleanup_included_in_actual_cost=True,checkpoint_historical_template='not_applicable_api')
    release_raw=encode(release); release_sha=sha(release_raw)
    mapping={str(PARENT):str(root),old['source_tree']:info['source_tree'],PREPARED:prep_sha,
        sha((PARENT/'source-files.json').read_bytes()):inv_sha,old_release_sha:release_sha,
        sha((PARENT/'allocation-budget-correction.json').read_bytes()):correction_sha}
    derivation={}
    for name,digest in read(PARENT/'code/code-manifest.json')['files'].items():
        raw=(PARENT/'code'/name).read_bytes()
        if sha(raw)!=digest: raise ValueError('parent code drift')
        new=release_raw if name=='forets_native_e2e_release_20260911.json' else budget if name=='forets_paid_budget_20260911.py' else derive(name,replace(raw.decode(),mapping)).encode()
        if name.endswith('.py'): compile(new,name,'exec')
        dest=root/'code'/name;dest.parent.mkdir(parents=True,exist_ok=True);write(dest,new)
        derivation[name]=dict(base_sha256=sha(raw),derived_sha256=sha(new))
    os.chmod(root/'code/bin/singularity',0o700)
    files={str(p.relative_to(root/'code')):sha(p.read_bytes()) for p in (root/'code').rglob('*') if p.is_file()}
    write(root/'code/code-manifest.json',encode(dict(commit=info['commit'],files=files,derivation=derivation)))
    script=(PARENT/'launchers/forets_repeat_20260912.sbatch').read_text().replace(str(PARENT),str(root)).replace('forets-repeat-s15','forets-wallclock').replace('04:40:00','03:00:00')
    write(root/'launchers/forets_wallclock.sbatch',script.encode())
    write(root/'plan.md',(stage/PLAN).read_bytes());write(root/'artifact.json',encode(info))
    write(root/'parent-facts.json',encode(dict(parent=str(BILLING),authorization=AUTH_PARENT,calls_sha256=sha(encode(calls)))))
    result=dict(package=str(root),source_tree=info['source_tree'],commit=info['commit'],prepared_sha256=prep_sha,
        authorization_sha256=ns['AUTH_SHA'],status='BUILT_NOT_ACTIVE',runs=8,nominal_gpu_hours=3,
        maximum_new_api_liability_usd=3.5,api_calls=0,gpu_dispatches=0)
    write(root/'build.json',encode(result));print(json.dumps(result))


def activate(root):
    if root.resolve().parent!=PARENT.parent or not root.name.startswith('forets-wallclock-20260912-'): raise ValueError('explicit fresh root')
    facts=read(root/'parent-facts.json'); calls=parent_calls()
    if facts['calls_sha256']!=sha(encode(calls)) or (root/'paid.sqlite').exists(): raise ValueError('handover already attempted/drift')
    # One exclusive durable intent before sealing; crashes are reviewed, never retried automatically.
    write(root/'activation-intent.json',encode(facts))
    with closing(sqlite3.connect((BILLING/'paid.sqlite').as_uri()+'?mode=rw',uri=True)) as prior:
        prior.execute('BEGIN IMMEDIATE')
        if prior.execute('SELECT digest,stopped FROM auth').fetchall()!=[(AUTH_PARENT,0)] or prior.execute('SELECT * FROM calls ORDER BY id').fetchall()!=calls: raise ValueError('concurrent ledger mutation')
        prior.execute('UPDATE auth SET stopped=1');prior.commit()
        with closing(sqlite3.connect(root/'paid.sqlite')) as new: prior.backup(new)
    ns={};exec(compile((root/'code/forets_paid_budget_20260911.py').read_bytes(),'<budget>','exec'),ns)
    scopes=[r['run_id'] for r in read(root/'prepared.json')['run_configs']]+['route_wallclock']
    with closing(sqlite3.connect(root/'paid.sqlite')) as db:
        db.execute('UPDATE auth SET digest=?,body=?,stopped=0',(ns['AUTH_SHA'],ns['AUTH_RAW'].decode()))
        db.execute('UPDATE scopes SET cap=COALESCE((SELECT SUM(held) FROM calls WHERE calls.scope=scopes.scope),0)')
        db.executemany('INSERT INTO scopes VALUES (?,?)',[(s,4000000000) for s in scopes]);db.commit()
        if db.execute('SELECT * FROM calls ORDER BY id').fetchall()!=calls: raise ValueError('old calls altered')
    write(root/'paid-authorization.json',encode(ns['AUTH']));write(root/'activation-complete.json',encode(facts))
    print(json.dumps(dict(status='ACTIVE_PREDECESSOR_SEALED',billing=ns['snapshot'](root/'paid.sqlite'))))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('artifacts','build','activate'));p.add_argument('path',type=Path);a=p.parse_args()
    os.umask(0o077);globals()[a.mode](a.path)
