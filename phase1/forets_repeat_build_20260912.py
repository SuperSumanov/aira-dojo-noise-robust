"""Conditional seed12 replication of the closed seed11 development block.

No old run is resumed. No generator, image, critic, task or search knob changes.
The sole source difference is a cumulative authorization carried without reset.
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

from forets_environment_build_20260912 import git, sha, encode, write, read, replace, PREFIX
from forets_paid_patch_20260911 import once
from forets_successor_budget_20260912 import patch as patch_budget

PARENT=Path('/research/d7/spc/yzyang4/forets-review-20260912-csh5q4i8')
BASE='6ca01fba9892a350cbb24152054b5296dc7095f1'
PREPARED='e6ec9d4c6664a98a6c069b13cb85624ece78b864adf036591ed34f4c8df18718'
INVENTORY='9fbd2e1a336a96c241a03a837649854b38e1fd0d12991d3bac3f94367df28a6a'
RELEASE='cf87a4c186d04c4021d69844c8698de11a80b4c5cf9cc18beaa0c3582f6e4f36'
AUTH_PARENT='4bbac52d02eb1109aded9aeca4d73cd670fb7893afe5988973ace34a7204d98e'
MODEL='qwen/qwen3-coder-flash'
PLAN='FORETS_SEED12_REPLICATION_20260912.md'


def parent_facts():
    os.environ['SLURM_CONF']='/opt1/slurm/gpu-slurm.conf'
    sys.path.insert(0,str(PARENT/'code'))
    from forets_block_collect_20260911 import collect_metadata
    collect_metadata(PARENT,read(PARENT/'prepared.json',PREPARED))
    verified=read(PARENT/'independent-final-verification.json')
    result=read(PARENT/'diagnostics.json')
    if (verified['job']!='13115' or verified['source_tree']!=BASE or
        verified['verification']!='selected-node/external-grade consistency passed' or
        result['comparable_pairs']<1 or verified['valid_finals']!=result['valid_final_solutions']):
        raise ValueError('same-version replication gate not met')
    with closing(sqlite3.connect((PARENT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('SELECT digest,stopped FROM auth').fetchall()!=[(AUTH_PARENT,0)]:
            raise ValueError('closed parent ledger authorization changed')
        calls=db.execute('SELECT * FROM calls ORDER BY id').fetchall()
    facts=dict(accounted=sum(r[2] for r in calls),settled=sum(r[3] or 0 for r in calls),
        calls=len(calls),unknown=sum(r[4]=='unresolved' for r in calls),authorization=AUTH_PARENT,seed=12)
    if facts['calls']<55 or facts['unknown']<1:raise ValueError('historical liabilities lost')
    return dict(facts=facts,ledger_rows_sha256=sha(encode(calls)),
        verification_sha256=sha((PARENT/'independent-final-verification.json').read_bytes()),
        diagnostics_sha256=sha((PARENT/'diagnostics.json').read_bytes()),
        parent_allocation_gpu_hours=verified['allocation_gpu_hours'])


def facts(output):
    item=parent_facts();write(output,encode(item));print(json.dumps(item))


def artifact(output):
    # Parent facts must already have passed the terminal and comparison gates.
    parent=read(output/'parent-facts.json')
    original=git('show',BASE+':'+PREFIX+'paid_budget.py').decode()
    budget,auth=patch_budget(original,MODEL,**parent['facts'])
    with tempfile.TemporaryDirectory(prefix='forets-repeat-index-') as temp:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(temp)/'index'));git('read-tree',BASE,env=env)
        blob=git('hash-object','-w','--stdin',data=budget.encode()).decode().strip()
        git('update-index','--add','--cacheinfo','100644,'+blob+','+PREFIX+'paid_budget.py',env=env)
        tree=git('write-tree',env=env).decode().strip()
    files={}
    for line in git('ls-tree','-r',tree,'--','src/aira_core','src/dojo').decode().splitlines():
        head,name=line.split('\t');_,kind,blob=head.split()
        if kind!='blob':raise ValueError('source kind')
        files[name]=sha(git('cat-file','blob',blob))
    raw=git('-c','core.autocrlf=false','archive','--format=tar',tree,'src/aira_core','src/dojo',
        env=dict(os.environ,GIT_LFS_SKIP_SMUDGE='1'))
    write(output/'source.tar',raw)
    info=dict(base_tree=BASE,source_tree=tree,source_files=files,archive_sha256=sha(raw),
        commit=git('rev-parse','HEAD').decode().strip(),modified_files=[PREFIX+'paid_budget.py'],
        parent=parent,authorization=auth)
    write(output/'artifact.json',encode(info));print(json.dumps({k:v for k,v in info.items() if k!='source_files'}))


def order():
    rows=[]
    for index,task in enumerate(('leaf-classification','spaceship-titanic')):
        arms=['uniform_random','critic_topk_random']
        if (12+index)%2:arms.reverse()
        rows.extend((task,arm) for arm in arms)
    return rows


def derive(name,text):
    if name=='forets_block_controller_20260911.py':text=once(text,'enumerate((11,), 1)','enumerate((12,), 1)')
    if name=='forets_block_readout_20260911.py':text=once(text,'for seed in (11,):','for seed in (12,):')
    if name=='forets_paid_route_20260911.py':text=once(text,"FORETS_PAID_SCOPE='route_s11'","FORETS_PAID_SCOPE='route_s12'")
    return text


def build(stage):
    info=read(stage/'artifact.json');old=read(PARENT/'prepared.json',PREPARED)
    parent_inventory=read(PARENT/'source-files.json',INVENTORY)
    if parent_facts()!=info['parent']:raise ValueError('parent facts changed since freeze')
    if info['base_tree']!=BASE or sha((stage/'source.tar').read_bytes())!=info['archive_sha256']:raise ValueError('source drift')
    if set(info['source_files'])!=set(parent_inventory):raise ValueError('source file set differs')
    changed=[name for name in parent_inventory if parent_inventory[name]!=info['source_files'][name]]
    if changed!=[PREFIX+'paid_budget.py']:raise ValueError('replication changed scientific source')
    root=Path(tempfile.mkdtemp(prefix='forets-repeat-20260912-',dir=PARENT.parent));os.chmod(root,0o700)
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
    inventory=write(root/'source-files.json',encode(info['source_files']))
    os.environ.update(PYTHON_DOTENV_DISABLED='1',LITELLM_LOCAL_MODEL_COST_MAP='True',LOGGING_DIR=str(root),
        MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu')
    sys.path[:0]=[str(root/'source/src'),str(PARENT/'code')]
    from dojo.config_dataclasses.run import RunConfig
    from forets_e2e_package import common_config
    by_key={(r['task'],r['arm']):r for r in old['run_configs']};rows=[];normal=[]
    for index,(task,arm) in enumerate(order()):
        prior=by_key[(task,arm)];rid=f'{index:02d}-{task}-s12-{arm}'
        cfg=replace(read(PARENT/'configs'/(prior['run_id']+'.json'),prior['config_sha256']),
            {str(PARENT):str(root),prior['run_id']:rid})
        cfg['metadata']['seed']=cfg['solver']['selector_seed']=12
        cfg['metadata']['git_commit_id']=info['commit'];cfg['metadata']['description']='same-version-replication-source-tree-'+info['source_tree']
        typed=RunConfig.from_dict(cfg);typed.validate()
        if typed.to_typed_dict()!=cfg:raise ValueError('typed roundtrip')
        digest=write(root/'configs'/(rid+'.json'),encode(cfg))
        rows.append(dict(prior,run_id=rid,seed=12,config_sha256=digest))
        normal.append(common_config(cfg,run_id=rid,run_dir=root/'runs'/rid))
    if normal[0]!=normal[1] or normal[2]!=normal[3]:raise ValueError('unmatched arms')
    prepared=replace(old,{str(PARENT):str(root)});prepared.update(source_tree=info['source_tree'],base_source_tree=BASE,
        run_configs=rows,preparation_commit=info['commit'],source_archive_sha256=info['archive_sha256'],source_files=len(seen),
        paired_config_sha256=[sha(encode(normal[i])) for i in (0,2)],plan_sha256=sha((stage/PLAN).read_bytes()),
        remaining=['exact ledger handover','bounded route','new e2e block'])
    prepared_sha=write(root/'prepared.json',encode(prepared))
    manifest=read(PARENT/'manifest.json');manifest.update(source_tree=info['source_tree'],runs=rows)
    write(root/'manifest.json',encode(manifest));write(root/'launchers/block-1.json',encode(old['launcher']))
    for name in ('allocation-budget-correction.json','PACKAGE_STATE.json'):
        write(root/name,encode(replace(read(PARENT/name),{str(PARENT):str(root)})))
    budget_raw=(root/'source'/PREFIX/'paid_budget.py').read_bytes();ns={};exec(compile(budget_raw,'<budget>','exec'),ns)
    spec=read(PARENT/'code/forets_native_e2e_release_20260911.json',RELEASE)
    spec.update(package=str(root),source_tree=info['source_tree'],seeds=[12],paid_authorization_sha256=ns['AUTH_SHA'],
        development_purpose='same_version_seed_replication')
    release_raw=encode(spec);release=sha(release_raw)
    mapping={str(PARENT):str(root),BASE:info['source_tree'],PREPARED:prepared_sha,INVENTORY:inventory,RELEASE:release}
    derivation={}
    for name,digest in read(PARENT/'code/code-manifest.json')['files'].items():
        raw=(PARENT/'code'/name).read_bytes()
        if sha(raw)!=digest:raise ValueError('old controller drift')
        new=release_raw if name=='forets_native_e2e_release_20260911.json' else budget_raw if name=='forets_paid_budget_20260911.py' else derive(name,replace(raw.decode(),mapping)).encode()
        target=root/'code'/name;target.parent.mkdir(parents=True,exist_ok=True);write(target,new)
        derivation[name]=dict(base_sha256=sha(raw),derived_sha256=sha(new))
    os.chmod(root/'code/bin/singularity',0o700)
    files={str(p.relative_to(root/'code')):sha(p.read_bytes()) for p in (root/'code').rglob('*') if p.is_file()}
    write(root/'code/code-manifest.json',encode(dict(commit=info['commit'],files=files,derivation=derivation)))
    script=(PARENT/'launchers/forets_review_20260912.sbatch').read_text().replace(str(PARENT),str(root)).replace('forets-review-s11','forets-repeat-s12').replace('seed11','seed12')
    write(root/'launchers/forets_repeat_20260912.sbatch',script.encode())
    session=(PARENT/'forets_environment_session_20260912.py').read_text().replace(str(PARENT),str(root)).replace(PREPARED,prepared_sha)
    session=session.replace('forets-review-s11','forets-repeat-s12').replace('forets_review_20260912.sbatch','forets_repeat_20260912.sbatch').replace('seed=11','seed=12')
    session=once(session,"new_api_calls=state['calls']-55,",f"new_api_calls=state['calls']-{info['parent']['facts']['calls']},")
    session=once(session,'Decimal(422344104)/10**9',f"Decimal({info['parent']['facts']['settled']})/10**9")
    write(root/'forets_environment_session_20260912.py',session.encode())
    for name in ('forets_paid_measurements_20260912.py','forets_paid_failure_verify_20260912.py'):
        write(root/name,(PARENT/name).read_bytes())
    write(root/'plan.md',(stage/PLAN).read_bytes());write(root/'parent-facts.json',encode(info['parent']))
    result=dict(package=str(root),source_tree=info['source_tree'],commit=info['commit'],prepared_sha256=prepared_sha,
        inventory_sha256=inventory,release_sha256=release,authorization_sha256=ns['AUTH_SHA'],status='BUILT_NOT_ACTIVE',
        run_ids=[r['run_id'] for r in rows],maximum_new_gpu_hours=10,maximum_incremental_usd=2)
    write(root/'build.json',encode(result));print(json.dumps(result))


def activate(root):
    if root.resolve().parent!=PARENT.parent or not root.name.startswith('forets-repeat-20260912-'):raise ValueError('explicit new package')
    if (root/'paid.sqlite').exists():raise ValueError('ledger exists')
    expected=read(root/'parent-facts.json')
    if parent_facts()!=expected:raise ValueError('parent freeze drift')
    with closing(sqlite3.connect((PARENT/'paid.sqlite').as_uri()+'?mode=rw',uri=True)) as parent:
        parent.execute('BEGIN IMMEDIATE')
        if parent.execute('SELECT digest,stopped FROM auth').fetchall()!=[(AUTH_PARENT,0)]:raise ValueError('parent auth drift')
        calls=parent.execute('SELECT * FROM calls ORDER BY id').fetchall()
        if sha(encode(calls))!=expected['ledger_rows_sha256']:raise ValueError('parent calls changed')
        parent.execute('UPDATE auth SET stopped=1');parent.commit()
        with closing(sqlite3.connect(root/'paid.sqlite')) as child:parent.backup(child)
    ns={};exec(compile((root/'code/forets_paid_budget_20260911.py').read_bytes(),'<budget>','exec'),ns)
    ids=[r['run_id'] for r in read(root/'prepared.json')['run_configs']]
    with closing(sqlite3.connect(root/'paid.sqlite')) as child:
        child.execute('UPDATE auth SET digest=?,body=?,stopped=0',(ns['AUTH_SHA'],ns['AUTH_RAW'].decode()))
        child.execute('UPDATE scopes SET cap=COALESCE((SELECT SUM(held) FROM calls WHERE calls.scope=scopes.scope),0)')
        child.executemany('INSERT INTO scopes VALUES (?,?)',[(x,ns['AUTH']['run_limit']) for x in ids]+[('route_s12',ns['AUTH']['route_limit'])])
        child.commit()
        if child.execute('SELECT * FROM calls ORDER BY id').fetchall()!=calls:raise ValueError('ledger copy differs')
    write(root/'paid-authorization.json',encode(ns['AUTH']))
    write(root/'parent-ledger-seal.json',encode(expected|dict(parent=str(PARENT),authorization_sha256=ns['AUTH_SHA'])))
    print(json.dumps(dict(status='ACTIVE_OLD_LEDGER_SEALED',billing=ns['snapshot'](root/'paid.sqlite'))))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('facts','artifact','build','activate'));parser.add_argument('path',type=Path)
    args=parser.parse_args();{'facts':facts,'artifact':artifact,'build':build,'activate':activate}[args.mode](args.path)
