"""Fresh seed11 package with shared review-type repair and carried liabilities."""
import argparse
from contextlib import closing
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tarfile
import tempfile

from forets_environment_build_20260912 import git, sha, encode, write, read, replace, PREFIX
from forets_paid_patch_20260911 import once
from forets_review_metric_20260912 import patch_parser

PARENT=Path('/research/d7/spc/yzyang4/forets-env-20260912-edcpizid')
LEDGER_PARENT=Path('/research/d7/spc/yzyang4/forets-analyzer-live-dgzmkcqh')
BASE='0a587f6b220b1aa0bd154f537f36594bc0690cb3'
PREPARED='1e0f29be3f48fb376a2ce4a2740da583d5c39fcdefa9c5f6d2bceac7b100eda9'
INVENTORY='0342f6feb8ff7c6fd94b3a04e18d151422ce7738a3fda255d61f030b7f6714c7'
RELEASE='0ddfbdd870d005d9123b8fbcb58c6bb614501db830d373ac3683662517f39e45'
AUTH_PARENT='581f1c378636728df93c6502a4e45513847eed29b86de5a577309d72967f21b5'
ACCOUNTED=1122344104
SETTLED=422344104
ROWS=55
INCREMENT=2000000000
PLAN='FORETS_REVIEW_REPAIR_PLAN_20260912.md'


def order():
    rows=[]
    for index,task in enumerate(('leaf-classification','spaceship-titanic')):
        arms=['uniform_random','critic_topk_random']
        if (11+index)%2:arms.reverse()
        for arm in arms:rows.append((task,arm))
    return rows


def budget_source(source):
    update=dict(version=4,total=ACCOUNTED+INCREMENT,incremental_cap=INCREMENT,
        predecessor_authorization=AUTH_PARENT,predecessor_accounted=ACCOUNTED,
        predecessor_settled=SETTLED,predecessor_calls=ROWS,predecessor_unresolved=1,
        run_limit=1500000000,experiment='review-type-repair-seed11',
        accounted_cny_ceiling=str(Decimal(ACCOUNTED+INCREMENT)/10**9*Decimal('8.8')))
    source=once(source,'AUTH_RAW = json.dumps(AUTH,','AUTH.update('+repr(update)+')\nAUTH_RAW = json.dumps(AUTH,')
    # Initializing only the historical synthetic row would lose unknown liabilities.
    return once(source,'def initialize(path, run_ids):',
        'def initialize(path, run_ids):\n    raise RuntimeError("use exact cumulative ledger handover")')


def artifact(output):
    output.mkdir(exist_ok=False)
    modified={PREFIX+'paid_budget.py':budget_source(git('show',BASE+':'+PREFIX+'paid_budget.py').decode()).encode(),
        PREFIX+'lite_llm.py':patch_parser(git('show',BASE+':'+PREFIX+'lite_llm.py').decode()).encode(),
        PREFIX+'review_metric.py':Path(__file__).with_name('forets_review_metric_20260912.py').read_bytes()}
    with tempfile.TemporaryDirectory(prefix='forets-review-index-') as temp:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(temp)/'index'));git('read-tree',BASE,env=env)
        for name,raw in modified.items():
            blob=git('hash-object','-w','--stdin',data=raw).decode().strip()
            git('update-index','--add','--cacheinfo','100644,'+blob+','+name,env=env)
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
        commit=git('rev-parse','HEAD').decode().strip(),modified_files=sorted(modified))
    write(output/'artifact.json',encode(info));print(json.dumps({k:v for k,v in info.items() if k!='source_files'}))


def derive(name,text):
    if name=='forets_block_controller_20260911.py':
        text=once(text,'enumerate((10,), 1)','enumerate((11,), 1)')
        text=once(text,'(block - 1 + task_index) % 2','(seed + task_index) % 2')
    if name=='forets_block_readout_20260911.py':text=once(text,'for seed in (10,):','for seed in (11,):')
    if name=='forets_paid_route_20260911.py':
        text=once(text,"FORETS_PAID_SCOPE='route'","FORETS_PAID_SCOPE='route_s11'")
        text=once(text,"    if state['stopped']: raise RuntimeError('campaign billing stopped')",
            "    if state['stopped']: raise RuntimeError('campaign billing stopped')\n"
            "    import sqlite3\n    from contextlib import closing\n"
            "    def unknown_ids():\n"
            "        with closing(sqlite3.connect((ROOT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:\n"
            "            return set(x[0] for x in db.execute(\"SELECT id FROM calls WHERE state='unresolved'\"))\n"
            "    prior_unknown=unknown_ids()")
        text=once(text,"or state['unresolved']):","or unknown_ids()!=prior_unknown):")
    return text


def build(stage):
    info=read(stage/'artifact.json');old=read(PARENT/'prepared.json',PREPARED)
    read(PARENT/'source-files.json',INVENTORY)
    if info['base_tree']!=BASE or sha((stage/'source.tar').read_bytes())!=info['archive_sha256']:raise ValueError('source drift')
    verified=read(LEDGER_PARENT/'report.json')
    if (len(verified['calls'])!=2 or not all(c['accepted'] and c['is_bug_matches_fixture'] and c['metric_matches_fixture'] for c in verified['calls'])
        or verified['compatibility_helper_sha256']!=info['source_files'][PREFIX+'review_metric.py']
        or verified['compatibility_patch_sha256']!=info['source_files'][PREFIX+'lite_llm.py']):raise ValueError('actual parser check differs')
    root=Path(tempfile.mkdtemp(prefix='forets-review-20260912-',dir=PARENT.parent));os.chmod(root,0o700)
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
        prior=by_key[(task,arm)];rid=f'{index:02d}-{task}-s11-{arm}'
        cfg=read(PARENT/'configs'/(prior['run_id']+'.json'),prior['config_sha256'])
        cfg=replace(cfg,{str(PARENT):str(root),prior['run_id']:rid})
        cfg['metadata']['seed']=cfg['solver']['selector_seed']=11
        cfg['metadata']['git_commit_id']=info['commit'];cfg['metadata']['description']='review-type-repair-source-tree-'+info['source_tree']
        typed=RunConfig.from_dict(cfg);typed.validate()
        if typed.to_typed_dict()!=cfg:raise ValueError('typed roundtrip')
        digest=write(root/'configs'/(rid+'.json'),encode(cfg))
        rows.append(dict(prior,run_id=rid,seed=11,config_sha256=digest))
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
    spec.update(package=str(root),source_tree=info['source_tree'],seeds=[11],paid_authorization_sha256=ns['AUTH_SHA'],
        development_purpose='review_type_repair_same_budget_e2e')
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
    script=(stage/'forets_environment_20260912.sbatch').read_text().replace(str(PARENT),str(root)).replace('forets-env-s10','forets-review-s11').replace('seed10','seed11')
    write(root/'launchers/forets_review_20260912.sbatch',script.encode())
    session=(stage/'forets_environment_session_20260912.py').read_text().replace(str(PARENT),str(root)).replace(PREPARED,prepared_sha)
    session=session.replace('forets-env-s10','forets-review-s11').replace('forets_environment_20260912.sbatch','forets_review_20260912.sbatch').replace('seed=10','seed=11')
    session=once(session,"new_api_calls=state['calls']-1,","new_api_calls=state['calls']-55,")
    session=once(session,'Decimal(PRIOR_NANO)/10**9','Decimal(422344104)/10**9')
    write(root/'forets_environment_session_20260912.py',session.encode())
    for name in ('forets_paid_measurements_20260912.py','forets_paid_failure_verify_20260912.py'):
        write(root/name,(PARENT/name).read_bytes())
    write(root/'plan.md',(stage/PLAN).read_bytes())
    result=dict(package=str(root),source_tree=info['source_tree'],commit=info['commit'],prepared_sha256=prepared_sha,
        inventory_sha256=inventory,release_sha256=release,authorization_sha256=ns['AUTH_SHA'],status='BUILT_NOT_ACTIVE',
        run_ids=[r['run_id'] for r in rows],maximum_new_gpu_hours=10,maximum_incremental_usd=2)
    write(root/'build.json',encode(result));print(json.dumps(result))


def activate(root):
    if root.resolve().parent!=PARENT.parent or not root.name.startswith('forets-review-20260912-'):raise ValueError('explicit new package')
    if (root/'paid.sqlite').exists():raise ValueError('ledger exists')
    os.environ['SLURM_CONF']='/opt1/slurm/gpu-slurm.conf';sys.path.insert(0,str(PARENT/'code'))
    from forets_block_collect_20260911 import collect_metadata
    collect_metadata(PARENT,read(PARENT/'prepared.json',PREPARED))
    with closing(sqlite3.connect((LEDGER_PARENT/'paid.sqlite').as_uri()+'?mode=rw',uri=True)) as parent:
        parent.execute('BEGIN IMMEDIATE')
        if parent.execute('SELECT digest,stopped FROM auth').fetchall()!=[(AUTH_PARENT,0)]:raise ValueError('prior auth changed')
        calls=parent.execute('SELECT * FROM calls ORDER BY id').fetchall()
        if (len(calls),sum(r[2] for r in calls),sum(r[3] or 0 for r in calls),sum(r[4]=='unresolved' for r in calls))!=(ROWS,ACCOUNTED,SETTLED,1):raise ValueError('prior charges changed')
        parent.execute('UPDATE auth SET stopped=1');parent.commit()
        with closing(sqlite3.connect(root/'paid.sqlite')) as child:parent.backup(child)
    ns={};exec(compile((root/'code/forets_paid_budget_20260911.py').read_bytes(),'<new budget>','exec'),ns)
    ids=[r['run_id'] for r in read(root/'prepared.json')['run_configs']]
    with closing(sqlite3.connect(root/'paid.sqlite')) as child:
        child.execute('UPDATE auth SET digest=?,body=?,stopped=0',(ns['AUTH_SHA'],ns['AUTH_RAW'].decode()))
        child.execute('UPDATE scopes SET cap=COALESCE((SELECT SUM(held) FROM calls WHERE calls.scope=scopes.scope),0)')
        child.executemany('INSERT INTO scopes VALUES (?,?)',[(x,1500000000) for x in ids]+[('route_s11',1200000000)])
        child.commit()
        if child.execute('SELECT * FROM calls ORDER BY id').fetchall()!=calls:raise ValueError('copied calls differ')
    receipt=dict(parent=str(LEDGER_PARENT),parent_authorization_sha256=AUTH_PARENT,carried_rows=ROWS,
        carried_actual_api_calls=178,carried_settled_nano=SETTLED,carried_accounted_nano=ACCOUNTED,unknown_preserved=1,
        authorization_sha256=ns['AUTH_SHA'],authorization=ns['AUTH'])
    write(root/'paid-authorization.json',encode(ns['AUTH']));write(root/'parent-ledger-seal.json',encode(receipt))
    print(json.dumps(dict(status='ACTIVE_OLD_LEDGER_SEALED',billing=ns['snapshot'](root/'paid.sqlite'))))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('artifact','build','activate'));p.add_argument('path',type=Path)
    a=p.parse_args();{'artifact':artifact,'build':build,'activate':activate}[a.mode](a.path)
