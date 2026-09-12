"""Fixed eight-run two-allocation successor; no old source or results overwritten."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import build_forets_wallclock_20260912 as common
from forets_environment_build_20260912 import git,sha,encode,write,read,PREFIX
from forets_paid_patch_20260911 import once
from forets_rank_budget_variant_20260912 import variant

BASE='e07cb8c61bca347c61bb8253c84eda826b1add6a'
PARENT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-cxb9p0og')
AUTH_PARENT='c5c17a09ef3503be91b0e2ff0fa0873c833cb884f01f5c0f5820e14a40cdb4b4'
PREPARED='96e624e811e8152627e93bcb8976cb2ae9218f5f15361901178f08dd19d6b077'
PLAN='FORETS_SINGLE_VOTE_PLAN_20260913.md'
SEEDS=(26,27)
PRIOR_HELD=3600861988
PRIOR_COST=2200861988
NEW_CAP=10**10-PRIOR_HELD

def order():
    return [(block,task,seed,arm) for block,seed in enumerate(SEEDS,1)
        for i,task in enumerate(('leaf-classification','spaceship-titanic'))
        for arm in (['critic_topk_random','uniform_random'] if (seed+i)%2 else ['uniform_random','critic_topk_random'])]

def parent_calls():
    finish=read(PARENT/'recovery-readout-finished.json')
    if (finish['job'],finish['status'],finish['summary_sha256'])!=('13156','verified','a127831408688b545e3d666b790fe1f75b65e82f9324d21c8c4cfc0243d39e90'):
        raise ValueError('parent readout closure changed')
    with closing(sqlite3.connect((PARENT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('SELECT digest,stopped FROM auth').fetchall()!=[(AUTH_PARENT,0)]:raise ValueError('parent inactive')
        rows=db.execute('SELECT * FROM calls ORDER BY id').fetchall()
    if (len(rows),sum(r[2] for r in rows),sum(r[3] or 0 for r in rows),sum(r[4]=='unresolved' for r in rows))!=(658,PRIOR_HELD,PRIOR_COST,2):
        raise ValueError('parent billing changed')
    return rows

def derive(name,text):
    if name=='forets_block_controller_20260911.py':
        for a,b in [('ALLOCATION_SECONDS = 180 * 60','ALLOCATION_SECONDS = 90 * 60'),
          ('    for seed in (24, 25):\n        block = 1','    for block, seed in enumerate((26, 27), 1):'),
          ('block not in (1,)','block not in (1,2)'),('len(spec.run_ids) != 8','len(spec.run_ids) != 4'),
          ("correction['proposed_block_minutes'] != 180","correction['proposed_block_minutes'] != 90")]:text=once(text,a,b)
    if name=='forets_native_run_20260911.py':
        text=once(text,'len(configs) != 8','len(configs) != 4')
        text=once(text,'choices=(1,)','choices=(1,2)')
    if name=='forets_paid_route_20260911.py':
        text=once(text,"FORETS_PAID_SCOPE='route_parallel'","FORETS_PAID_SCOPE='route_singlevote'")
    if name=='forets_block_runtime_20260911.py':
        text=once(text,"        if state['stopped'] or state['unresolved'] != 2:\n            raise RuntimeError('new unresolved charge or stopped billing')",
            '        from forets_parallel_scope_gate_20260913 import check\n        check(ROOT_FOR_API_CATALOG)')
        text=once(text,"aggregation='two_order_borda_v1'","aggregation='single_order_rank_v1'")
    return text

def configure():
    for name,value in dict(BASE=BASE,PARENT=PARENT,BILLING=PARENT,AUTH_PARENT=AUTH_PARENT,PREPARED=PREPARED,
       PLAN=PLAN,NEW_CAP=NEW_CAP,SEEDS=SEEDS,ROUTE_SCOPE='route_singlevote',SBATCH_TEMPLATE='forets_wallclock.sbatch',
       order=order,parent_calls=parent_calls,derive=derive).items():setattr(common,name,value)

def artifacts(output):
    output.mkdir(exist_ok=False)
    auth=dict(version=12,total=10**10,incremental_cap=NEW_CAP,predecessor_authorization=AUTH_PARENT,
        predecessor_accounted=PRIOR_HELD,predecessor_settled=PRIOR_COST,predecessor_calls=658,
        predecessor_unresolved=2,experiment='single-vote-e2e-seeds26-27',accounted_cny_ceiling='88.00',
        run_limit=4000000000,route_limit=4000000000,concurrent_search_workers=2)
    changed={PREFIX+'paid_budget.py':once(git('show',BASE+':'+PREFIX+'paid_budget.py').decode(),
       'AUTH_RAW = json.dumps(AUTH,','AUTH.update('+repr(auth)+')\nAUTH_RAW = json.dumps(AUTH,').encode(),
       'src/dojo/solvers/fore_ts/contextual_rank.py':variant(git('show',BASE+':src/dojo/solvers/fore_ts/contextual_rank.py').decode(),1).encode()}
    for raw in changed.values():compile(raw,'<single-vote>','exec')
    with tempfile.TemporaryDirectory(prefix='forets-single-index-') as tmp:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(tmp)/'index'));git('read-tree',BASE,env=env)
        for name,raw in changed.items():
            blob=git('hash-object','-w','--stdin',data=raw).decode().strip()
            git('update-index','--add','--cacheinfo','100644,'+blob+','+name,env=env)
        tree=git('write-tree',env=env).decode().strip()
    files={}
    for line in git('ls-tree','-r',tree,'--','src/aira_core','src/dojo').decode().splitlines():
        head,name=line.split('\t');_,kind,blob=head.split()
        if kind!='blob':raise ValueError('source type')
        files[name]=sha(git('cat-file','blob',blob))
    archive=git('-c','core.autocrlf=false','archive','--format=tar',tree,'src/aira_core','src/dojo',env=dict(os.environ,GIT_LFS_SKIP_SMUDGE='1'))
    write(output/'source.tar',archive)
    info=dict(base_tree=BASE,source_tree=tree,source_files=files,archive_sha256=sha(archive),modified_files=sorted(changed),
        commit=git('rev-parse','HEAD').decode().strip(),plan_sha256=sha(Path(__file__).with_name(PLAN).read_bytes()),matrix=order())
    write(output/'artifact.json',encode(info));print(json.dumps({k:v for k,v in info.items() if k!='source_files'}))

def build(stage):
    # Common builder remains single-block by default. Only this successor opts in.
    import contextlib,io
    buf=io.StringIO()
    with contextlib.redirect_stdout(buf):common.build(stage,block_minutes=90,block_ids=(1,2))
    info=json.loads(buf.getvalue());root=Path(info['package'])
    gate=Path(__file__).with_name('forets_parallel_scope_gate_20260913.py').read_bytes().replace(b'\r\n',b'\n')
    write(root/'code/forets_parallel_scope_gate_20260913.py',gate)
    manifest_path=root/'code/code-manifest.json';manifest=read(manifest_path)
    manifest['files']['forets_parallel_scope_gate_20260913.py']=sha(gate)
    # These are new unpublished build artifacts, before activation or dispatch.
    manifest_path.write_bytes(encode(manifest))
    template=(root/'launchers/forets_wallclock.sbatch').read_text()
    template=once(template,'#SBATCH --time=03:00:00','#SBATCH --time=01:30:00')
    for block in (1,2):
        script=once(template,'execute --block 1',f'execute --block {block}')
        script=once(script,'#SBATCH --job-name=forets-wallclock',f'#SBATCH --job-name=forets-singlevote-b{block}')
        write(root/f'launchers/singlevote-b{block}.sbatch',script.encode())
    print(json.dumps(info))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('artifacts','build','activate'));p.add_argument('path',type=Path)
    a=p.parse_args();os.umask(0o077);configure()
    (common.activate if a.mode=='activate' else globals()[a.mode])(a.path)
