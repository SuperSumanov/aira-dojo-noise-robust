"""Build a fresh single-GPU contextual-selector release from closed seed12.

Only explicit artifacts; no GPU launch, paid request, new branch or old-run edit.
Budget activation separately seals the completed judge ledger, preserving rows.
"""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys
import tarfile
import tempfile

from forets_environment_build_20260912 import git,sha,encode,write,read,replace,PREFIX
from forets_paid_patch_20260911 import once
from forets_context_e2e_patch_20260912 import budget_source,batch_source,derive
from forets_submission_archive_20260912 import patch_evaluator

PARENT=Path('/research/d7/spc/yzyang4/forets-repeat-20260912-zuvnt3oa')
BILLING=PARENT.parent/'forets-context-judge-20260912-42qtmhgi'
BASE='35711518b3b7262bccd3bebfdd2b4a4b7c726715'
PREPARED='963418d10d5645f7401a85da42d6fc3d5b2f7553e76cf44eecbeb342f17d44d5'
INVENTORY='67516a4d01ddb6093ad405da538add47fbe0f9e64016df1b9b35036d306b9545'
RELEASE='a64e8b24afc538a9446060cf847a5310288a3041ffa6a700b132949340b86bc0'
AUTH_PARENT='69e6d156ea7ec0f172edf3f46f432661c1da8ca0c1249301212ac59bac209fbe'
COMPARISON='785df0a492c7b850996915f53132147cde5d12fe257d4a4e8152dc7b39c62f49'
PLAN='FORETS_CONTEXT_E2E_PLAN_20260912.md'
BATCH='src/dojo/solvers/fore_ts/batch_runtime.py'
EVALUATOR='src/dojo/tasks/mlebench/evaluate.py'
ADDED={'src/dojo/solvers/fore_ts/contextual_rank.py':'forets_contextual_rank_20260912.py',
       'src/dojo/solvers/fore_ts/context_environment.py':'forets_environment_context_20260912.py',
       'src/dojo/tasks/mlebench/submission_archive.py':'forets_submission_archive_20260912.py'}


def artifacts(output):
    output.mkdir(exist_ok=False)
    changed={PREFIX+'paid_budget.py':budget_source(git('show',BASE+':'+PREFIX+'paid_budget.py').decode()).encode(),
        BATCH:batch_source(git('show',BASE+':'+BATCH).decode()).encode(),
        EVALUATOR:patch_evaluator(git('show',BASE+':'+EVALUATOR).decode()).encode()}
    for name,local in ADDED.items():changed[name]=Path(__file__).with_name(local).read_bytes()
    for raw in changed.values():compile(raw,'<new source>','exec')
    with tempfile.TemporaryDirectory(prefix='forets-context-index-') as temp:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(temp)/'index'));git('read-tree',BASE,env=env)
        for name,raw in changed.items():
            blob=git('hash-object','-w','--stdin',data=raw).decode().strip()
            git('update-index','--add','--cacheinfo','100644,'+blob+','+name,env=env)
        tree=git('write-tree',env=env).decode().strip()
    files={}
    for line in git('ls-tree','-r',tree,'--','src/aira_core','src/dojo').decode().splitlines():
        head,name=line.split('\t');_,kind,blob=head.split()
        if kind!='blob':raise ValueError('source kind')
        files[name]=sha(git('cat-file','blob',blob))
    archive=git('-c','core.autocrlf=false','archive','--format=tar',tree,'src/aira_core','src/dojo',
        env=dict(os.environ,GIT_LFS_SKIP_SMUDGE='1'))
    write(output/'source.tar',archive)
    info=dict(base_tree=BASE,source_tree=tree,source_files=files,archive_sha256=sha(archive),
        modified_files=sorted(changed),commit=git('rev-parse','HEAD').decode().strip(),plan_sha256=sha(Path(__file__).with_name(PLAN).read_bytes()))
    write(output/'artifact.json',encode(info));print(json.dumps({k:v for k,v in info.items() if k!='source_files'}))


def parent_calls():
    if sha((BILLING/'comparison.json').read_bytes())!=COMPARISON or not read(BILLING/'finished.json')['complete']:
        raise ValueError('completed diagnostic differs')
    with closing(sqlite3.connect((BILLING/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('SELECT digest,stopped FROM auth').fetchall()!=[(AUTH_PARENT,0)]:raise ValueError('parent ledger sealed or changed')
        rows=db.execute('SELECT * FROM calls ORDER BY id').fetchall()
    if (len(rows),sum(r[2] for r in rows),sum(r[3] or 0 for r in rows),sum(r[4]=='unresolved' for r in rows))!=(185,1442593566,742593566,1):
        raise ValueError('parent ledger facts changed')
    return rows


def order():
    rows=[]
    for i,task in enumerate(('leaf-classification','spaceship-titanic')):
        arms=['uniform_random','critic_topk_random']
        if (13+i)%2:arms.reverse()
        rows.extend((task,arm) for arm in arms)
    return rows


def build(stage):
    info=read(stage/'artifact.json');old=read(PARENT/'prepared.json',PREPARED);calls=parent_calls()
    inventory=read(PARENT/'source-files.json',INVENTORY)
    expected={PREFIX+'paid_budget.py',BATCH,EVALUATOR}|set(ADDED)
    changed={name for name in info['source_files'] if info['source_files'][name]!=inventory.get(name)}
    if (info['base_tree']!=BASE or changed!=expected or set(inventory)-set(info['source_files'])
        or sha((stage/'source.tar').read_bytes())!=info['archive_sha256'] or sha((stage/PLAN).read_bytes())!=info['plan_sha256']):
        raise ValueError('source or plan drift')
    root=Path(tempfile.mkdtemp(prefix='forets-context-e2e-20260912-',dir=PARENT.parent));os.chmod(root,0o700)
    for name in ('source','code','configs','launchers','runs'):(root/name).mkdir(mode=0o700)
    seen=set()
    with tarfile.open(stage/'source.tar') as archive:
        for member in archive:
            if member.isdir():continue
            if not member.isfile() or member.name not in info['source_files'] or member.name in seen:raise ValueError('archive member')
            target=root/'source'/member.name
            if not target.resolve().is_relative_to(root/'source'):raise ValueError('archive path')
            raw=archive.extractfile(member).read()
            if sha(raw)!=info['source_files'][member.name]:raise ValueError('source hash')
            target.parent.mkdir(parents=True,exist_ok=True);write(target,raw);seen.add(member.name)
    if seen!=set(info['source_files']):raise ValueError('source incomplete')
    inv_sha=write(root/'source-files.json',encode(info['source_files']))
    os.environ.update(PYTHON_DOTENV_DISABLED='1',LITELLM_LOCAL_MODEL_COST_MAP='True',LOGGING_DIR=str(root),
        MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu')
    sys.path[:0]=[str(root/'source/src'),str(PARENT/'code')]
    from dojo.config_dataclasses.run import RunConfig
    from forets_e2e_package import common_config
    by_key={(r['task'],r['arm']):r for r in old['run_configs']};rows=[];norm=[]
    for i,(task,arm) in enumerate(order()):
        prior=by_key[(task,arm)];rid=f'{i:02d}-{task}-s13-{arm}'
        cfg=replace(read(PARENT/'configs'/(prior['run_id']+'.json'),prior['config_sha256']),{str(PARENT):str(root),prior['run_id']:rid})
        cfg['metadata']['seed']=cfg['solver']['selector_seed']=13
        cfg['metadata']['git_commit_id']=info['commit'];cfg['metadata']['description']='contextual-e2e-source-tree-'+info['source_tree']
        typed=RunConfig.from_dict(cfg);typed.validate()
        if typed.to_typed_dict()!=cfg:raise ValueError('typed roundtrip')
        digest=write(root/'configs'/(rid+'.json'),encode(cfg));rows.append(dict(prior,run_id=rid,seed=13,config_sha256=digest))
        norm.append(common_config(cfg,run_id=rid,run_dir=root/'runs'/rid))
    if norm[0]!=norm[1] or norm[2]!=norm[3]:raise ValueError('unmatched arms')
    prepared=replace(old,{str(PARENT):str(root)});prepared.update(source_tree=info['source_tree'],base_source_tree=BASE,
        run_configs=rows,preparation_commit=info['commit'],source_archive_sha256=info['archive_sha256'],source_files=len(seen),
        paired_config_sha256=[sha(encode(norm[i])) for i in (0,2)],plan_sha256=info['plan_sha256'],
        nominal_gpu_hours=280/60,checkpoint_training_template='not_applicable_contextual_api',
        remaining=['ledger handover','generator route','Plus catalog','new end-to-end allocation'])
    prep_sha=write(root/'prepared.json',encode(prepared))
    manifest=read(PARENT/'manifest.json');manifest.update(source_tree=info['source_tree'],runs=rows)
    write(root/'manifest.json',encode(manifest));write(root/'launchers/block-1.json',encode(old['launcher']))
    for name in ('allocation-budget-correction.json','PACKAGE_STATE.json'):
        write(root/name,encode(replace(read(PARENT/name),{str(PARENT):str(root)})))
    budget=(root/'source'/PREFIX/'paid_budget.py').read_bytes();ns={};exec(compile(budget,'<budget>','exec'),ns)
    release=read(PARENT/'code/forets_native_e2e_release_20260911.json',RELEASE)
    release.update(package=str(root),source_tree=info['source_tree'],seeds=[13],paid_authorization_sha256=ns['AUTH_SHA'],
        critic_kind='in_worker_contextual_api',critic_model='qwen/qwen3-coder-plus',
        development_purpose='contextual_selector_seed13',local_critic_model_loads=0)
    release_raw=encode(release);release_sha=sha(release_raw)
    mapping={str(PARENT):str(root),BASE:info['source_tree'],PREPARED:prep_sha,INVENTORY:inv_sha,RELEASE:release_sha}
    derivation={}
    for name,digest in read(PARENT/'code/code-manifest.json')['files'].items():
        raw=(PARENT/'code'/name).read_bytes()
        if sha(raw)!=digest:raise ValueError('parent controller drift')
        new=release_raw if name=='forets_native_e2e_release_20260911.json' else budget if name=='forets_paid_budget_20260911.py' else derive(name,replace(raw.decode(),mapping),root).encode()
        path=root/'code'/name;path.parent.mkdir(parents=True,exist_ok=True);write(path,new)
        derivation[name]=dict(base_sha256=sha(raw),derived_sha256=sha(new))
    os.chmod(root/'code/bin/singularity',0o700)
    files={str(p.relative_to(root/'code')):sha(p.read_bytes()) for p in (root/'code').rglob('*') if p.is_file()}
    write(root/'code/code-manifest.json',encode(dict(commit=info['commit'],files=files,derivation=derivation)))
    script=(PARENT/'launchers/forets_repeat_20260912.sbatch').read_text().replace(str(PARENT),str(root)).replace('forets-repeat-s12','forets-context-s13').replace('seed12','seed13')
    script=once(script,'#SBATCH --cpus-per-task=12','#SBATCH --cpus-per-task=6')
    script=once(script,'#SBATCH --gres=gpu:2','#SBATCH --gres=gpu:1')
    write(root/'launchers/forets_context_20260912.sbatch',script.encode())
    session=(PARENT/'forets_environment_session_20260912.py').read_text().replace(str(PARENT),str(root)).replace(PREPARED,prep_sha)
    for old_text,new_text in [('forets-repeat-s12','forets-context-s13'),('forets_repeat_20260912.sbatch','forets_context_20260912.sbatch'),
        ('seed=12','seed=13'),("new_api_calls=state['calls']-117,","new_api_calls=state['calls']-185,"),
        ('Decimal(574500927)/10**9','Decimal(742593566)/10**9'),('maximum_new_gpu_hours=10','maximum_new_gpu_hours=5')]:
        if old_text not in session:raise ValueError('session derivation anchor')
        session=session.replace(old_text,new_text)
    write(root/'forets_environment_session_20260912.py',session.encode())
    for name in ('forets_paid_measurements_20260912.py','forets_paid_failure_verify_20260912.py'):write(root/name,(PARENT/name).read_bytes())
    write(root/'plan.md',(stage/PLAN).read_bytes())
    write(root/'parent-facts.json',encode(dict(parent=str(BILLING),authorization=AUTH_PARENT,calls_sha256=sha(encode(calls)),
        calls=185,accounted_nano=1442593566,settled_nano=742593566,unresolved=1)))
    result=dict(package=str(root),source_tree=info['source_tree'],commit=info['commit'],prepared_sha256=prep_sha,
        inventory_sha256=inv_sha,release_sha256=release_sha,authorization_sha256=ns['AUTH_SHA'],status='BUILT_NOT_ACTIVE',
        run_ids=[r['run_id'] for r in rows],modified_source_files=sorted(expected),maximum_new_gpu_hours=5,maximum_incremental_usd=3.5)
    write(root/'build.json',encode(result));print(json.dumps(result))


def activate(root):
    if root.resolve().parent!=PARENT.parent or not root.name.startswith('forets-context-e2e-20260912-'):raise ValueError('new root required')
    facts=read(root/'parent-facts.json');calls=parent_calls()
    if facts['calls_sha256']!=sha(encode(calls)) or (root/'paid.sqlite').exists():raise ValueError('handover drift or already attempted')
    with closing(sqlite3.connect((BILLING/'paid.sqlite').as_uri()+'?mode=rw',uri=True)) as old:
        old.execute('BEGIN IMMEDIATE')
        if old.execute('SELECT digest,stopped FROM auth').fetchall()!=[(AUTH_PARENT,0)] or old.execute('SELECT * FROM calls ORDER BY id').fetchall()!=calls:
            raise ValueError('handover raced')
        old.execute('UPDATE auth SET stopped=1');old.commit()
        with closing(sqlite3.connect(root/'paid.sqlite')) as child:old.backup(child)
    ns={};exec(compile((root/'code/forets_paid_budget_20260911.py').read_bytes(),'<budget>','exec'),ns)
    scopes=[r['run_id'] for r in read(root/'prepared.json')['run_configs']]+['route_s13']
    with closing(sqlite3.connect(root/'paid.sqlite')) as db:
        db.execute('UPDATE auth SET digest=?,body=?,stopped=0',(ns['AUTH_SHA'],ns['AUTH_RAW'].decode()))
        db.execute('UPDATE scopes SET cap=COALESCE((SELECT SUM(held) FROM calls WHERE calls.scope=scopes.scope),0)')
        db.executemany('INSERT INTO scopes VALUES (?,?)',[(s,4000000000) for s in scopes]);db.commit()
        if db.execute('SELECT * FROM calls ORDER BY id').fetchall()!=calls:raise ValueError('carried calls changed')
    write(root/'parent-ledger-seal.json',encode(facts));write(root/'paid-authorization.json',encode(ns['AUTH']))
    print(json.dumps(dict(status='ACTIVE_PREDECESSOR_SEALED',billing=ns['snapshot'](root/'paid.sqlite'))))


def check_plus(root):
    import requests
    from forets_context_judge_20260912 import checked_catalog
    r=requests.get('https://openrouter.ai/api/v1/models/qwen/qwen3-coder-plus/endpoints',timeout=(10,30),allow_redirects=False)
    r.raise_for_status();value=checked_catalog(r.json());write(root/'block-1.plus-catalog.json',encode(value));print(json.dumps(value))


def check_derive(unused):
    import ast
    manifest=read(PARENT/'code/code-manifest.json');edited=[];parsed=0
    for name,digest in manifest['files'].items():
        raw=(PARENT/'code'/name).read_bytes()
        if sha(raw)!=digest:raise ValueError('parent code changed')
        if not name.endswith('.py'):continue
        new=derive(name,raw.decode(),PARENT.parent/'forets-context-e2e-20260912-DRYCHECK')
        ast.parse(new);parsed+=1
        if new!=raw.decode():edited.append(name)
    print(json.dumps(dict(parent_python_files_parsed=parsed,derived_controller_files=edited,api_calls=0,gpu_jobs=0,files_written=0)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('artifact','build','activate','check-plus','check-derive'));p.add_argument('path',type=Path);a=p.parse_args()
    os.umask(0o077)
    {'artifact':artifacts,'build':build,'activate':activate,'check-plus':check_plus,'check-derive':check_derive}[a.mode](a.path)
