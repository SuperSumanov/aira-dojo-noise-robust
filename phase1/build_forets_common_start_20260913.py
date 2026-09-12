"""Successor wrapper: fixed baseline execution then the existing search policy."""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import build_forets_wallclock_20260912 as common
from forets_environment_build_20260912 import git, sha, write, encode, read, PREFIX
from forets_paid_patch_20260911 import once

BASE = 'fb2c041c8ec8e352847881ee6fe2fb56d9561aec'
PARENT = Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-bll4ghfa')
PREPARED = '29349e0d78ce57701db2d5eae8bc35648f1fa50165df5eaff17a6502b3e402fe'
AUTH_PARENT = '81c286978ff9ff58f79d7e9f8029aab335686a2d15158c6f2462efc035ea3279'
PLAN = 'FORETS_COMMON_START_PLAN_20260913.md'
SEEDS = (28, 29)
NEW_CAP = 5902422065


def order():
    return [(b,t,s,a) for b,s in enumerate(SEEDS,1)
        for i,t in enumerate(('leaf-classification','spaceship-titanic'))
        for a in (['critic_topk_random','uniform_random'] if (s+i)%2 else ['uniform_random','critic_topk_random'])]


def parent_calls():
    finish = read(PARENT/'readout-finished.json')
    if finish['status'] != 'verified' or finish['summary_sha256'] != 'e1722e9277dda73a9c73471f2cb2c53703e260d107e8bdaa31311fe48259cdab':
        raise ValueError('parent closure')
    with sqlite3.connect((PARENT/'paid.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        if db.execute('select digest,stopped from auth').fetchall() != [(AUTH_PARENT,0)]:raise ValueError('inactive parent')
        rows=db.execute('select * from calls order by id').fetchall()
    if (len(rows),sum(r[2] for r in rows),sum(r[3] or 0 for r in rows),sum(r[4]=='unresolved' for r in rows)) != (815,4097577935,2697577935,2):
        raise ValueError('parent cost drift')
    return rows


def derive(name,text):
    if name == 'forets_block_controller_20260911.py':
        text=once(text,'enumerate((26, 27), 1)','enumerate((28, 29), 1)')
    if name == 'forets_paid_route_20260911.py':
        text=once(text,"FORETS_PAID_SCOPE='route_singlevote'","FORETS_PAID_SCOPE='route_commonstart'")
    return text


def config_transform(cfg):
    cfg['solver']['common_start_protocol']='rf_common_v1'
    return cfg


def configure():
    for name,value in dict(BASE=BASE,PARENT=PARENT,BILLING=PARENT,PREPARED=PREPARED,AUTH_PARENT=AUTH_PARENT,
        PLAN=PLAN,SEEDS=SEEDS,NEW_CAP=NEW_CAP,ROUTE_SCOPE='route_commonstart',SBATCH_TEMPLATE='singlevote-b1.sbatch',
        order=order,parent_calls=parent_calls,derive=derive).items():setattr(common,name,value)


def changed_sources():
    auth=dict(version=13,total=10**10,incremental_cap=NEW_CAP,predecessor_authorization=AUTH_PARENT,
        predecessor_accounted=4097577935,predecessor_settled=2697577935,predecessor_calls=815,
        predecessor_unresolved=2,experiment='common-start-e2e-seeds28-29',accounted_cny_ceiling='88.00',
        run_limit=4000000000,route_limit=4000000000,concurrent_search_workers=2)
    budget=once(git('show',BASE+':'+PREFIX+'paid_budget.py').decode(),'AUTH_RAW = json.dumps(AUTH,',
        'AUTH.update('+repr(auth)+')\nAUTH_RAW = json.dumps(AUTH,')
    cfg=git('show',BASE+':src/dojo/config_dataclasses/solver/fore_ts.py').decode()
    cfg=once(cfg,'    skip_redundant_critic: bool = False','    skip_redundant_critic: bool = False\n    common_start_protocol: str = "none"')
    cfg=once(cfg,'        for name in ("num_children",',
        '        if self.common_start_protocol not in ("none", "rf_common_v1"):\n            raise ValueError("common start protocol")\n        for name in ("num_children",')
    batch=git('show',BASE+':src/dojo/solvers/fore_ts/batch_runtime.py').decode()
    batch=once(batch,'    count = min(solver.cfg.num_children, solver.remaining_steps)',
        '    from dojo.solvers.fore_ts.common_start import initial, make_node, digest as start_digest\n    bootstrap = initial(solver, path)\n    count = 1 if bootstrap else min(solver.cfg.num_children, solver.remaining_steps)')
    batch=once(batch,"    binding.update(selection_coupling=coupling)",
        "    binding.update(selection_coupling=coupling)\n    if bootstrap:\n        binding['common_start'] = dict(protocol=solver.cfg.common_start_protocol, code_sha256=start_digest(solver.task_name))")
    batch=once(batch,'                    node = await (solver._draft(parent) if not parent.parents else solver._improve(parent))',
        '                    node = make_node(solver.task_name, node_type) if bootstrap else await (solver._draft(parent) if not parent.parents else solver._improve(parent))')
    return {PREFIX+'paid_budget.py':budget.encode(), 'src/dojo/config_dataclasses/solver/fore_ts.py':cfg.encode(),
        'src/dojo/solvers/fore_ts/batch_runtime.py':batch.encode(),
        'src/dojo/solvers/fore_ts/common_start.py':Path(__file__).with_name('forets_common_start_20260913.py').read_bytes().replace(b'\r\n',b'\n')}


def artifacts(output):
    output.mkdir(exist_ok=False);changed=changed_sources()
    for name,raw in changed.items():compile(raw,name,'exec')
    with tempfile.TemporaryDirectory(prefix='forets-common-index-') as tmp:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(tmp)/'index'));git('read-tree',BASE,env=env)
        for name,raw in changed.items():
            blob=git('hash-object','-w','--stdin',data=raw).decode().strip()
            git('update-index','--add','--cacheinfo','100644,'+blob+','+name,env=env)
        tree=git('write-tree',env=env).decode().strip()
    files={}
    for line in git('ls-tree','-r',tree,'--','src/aira_core','src/dojo').decode().splitlines():
        head,name=line.split('\t');_,kind,blob=head.split()
        if kind!='blob':raise ValueError('source kind')
        files[name]=sha(git('cat-file','blob',blob))
    archive=git('-c','core.autocrlf=false','archive','--format=tar',tree,'src/aira_core','src/dojo',env=dict(os.environ,GIT_LFS_SKIP_SMUDGE='1'))
    write(output/'source.tar',archive)
    info=dict(base_tree=BASE,source_tree=tree,source_files=files,archive_sha256=sha(archive),modified_files=sorted(changed),
        commit=git('rev-parse','HEAD').decode().strip(),plan_sha256=sha(Path(__file__).with_name(PLAN).read_bytes()),matrix=order())
    write(output/'artifact.json',encode(info));print(json.dumps({k:v for k,v in info.items() if k!='source_files'}))


def build(stage):
    buf=io.StringIO()
    with contextlib.redirect_stdout(buf):common.build(stage,block_minutes=90,block_ids=(1,2),config_transform=config_transform)
    info=json.loads(buf.getvalue());root=Path(info['package'])
    template=(root/'launchers/forets_wallclock.sbatch').read_text()
    for b in (1,2):
        script=once(template,'execute --block 1',f'execute --block {b}')
        script=once(script,'#SBATCH --job-name=forets-singlevote-b1',f'#SBATCH --job-name=forets-common-b{b}')
        write(root/f'launchers/singlevote-b{b}.sbatch',script.encode())
    print(json.dumps(info))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('artifacts','build','activate'));p.add_argument('path',type=Path)
    a=p.parse_args();os.umask(0o077);configure()
    (common.activate if a.mode=='activate' else globals()[a.mode])(a.path)
