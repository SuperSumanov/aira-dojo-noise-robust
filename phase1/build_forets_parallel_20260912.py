"""Exact closed-parent successor, reusing the bounded eight-run package builder."""
import argparse
from contextlib import closing
from decimal import Decimal
import json
import os
from pathlib import Path
import sqlite3
import tempfile

import build_forets_wallclock_20260912 as common
from forets_environment_build_20260912 import git, sha, encode, write, read, PREFIX
from forets_paid_patch_20260911 import once
from forets_parallel_patch_20260912 import patch_transport, patch_readiness

BASE = '6780e383d20d6051ba53cace793f0db910027315'
PARENT = Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-0t4odqpn')
AUTH_PARENT = '2129c34aa8758e9b5e2e07e98f6b2e9864fd9e896853c07c6b6333e98d716039'
PREPARED = '9194eb00bcff646bad70e8422f8af50aae59b549a3d707d96b93f8e77aed1e00'
PLAN = 'FORETS_PARALLEL_E2E_PLAN_20260912.md'
PRIOR_HELD, PRIOR_COST, NEW_CAP = 3053182076, 1653182076, 4500000000
SEEDS = (24, 25)


def parent_calls():
    finish = read(PARENT/'closeout-finished.json')
    if (finish['job'], finish['status'], finish['summary_sha256']) != (
            '13152', 'verified', 'da78d63c89c401b2bd7c3b8263496eb4d15a48b0a3a3bf84aa04240263dfd150'):
        raise ValueError('closed parent experiment required')
    read(PARENT/'wallclock-summary.json', finish['summary_sha256'])
    with closing(sqlite3.connect((PARENT/'paid.sqlite').as_uri()+'?mode=ro', uri=True)) as db:
        if db.execute('SELECT digest,stopped FROM auth').fetchall() != [(AUTH_PARENT, 0)]:
            raise ValueError('parent ledger not exclusively active')
        rows = db.execute('SELECT * FROM calls ORDER BY id').fetchall()
    if (len(rows), sum(r[2] for r in rows), sum(r[3] or 0 for r in rows), sum(r[4]=='unresolved' for r in rows)) != (
            504, PRIOR_HELD, PRIOR_COST, 2):
        raise ValueError('observed cumulative ledger changed')
    return rows


def derive(name, text):
    if name == 'forets_block_controller_20260911.py':
        text = once(text, '    for seed in (22, 23):', '    for seed in (24, 25):')
    if name == 'forets_paid_route_20260911.py':
        text = once(text, "FORETS_PAID_SCOPE='route_wallclock'", "FORETS_PAID_SCOPE='route_parallel'")
    return text


def configure():
    common.BASE, common.PARENT, common.BILLING = BASE, PARENT, PARENT
    common.AUTH_PARENT, common.PREPARED, common.PLAN = AUTH_PARENT, PREPARED, PLAN
    common.SEEDS, common.ROUTE_SCOPE, common.SBATCH_TEMPLATE = SEEDS, 'route_parallel', 'forets_wallclock.sbatch'
    common.NEW_CAP = NEW_CAP
    common.parent_calls, common.derive = parent_calls, derive


def budget_source(source):
    auth = dict(version=11, total=PRIOR_HELD+NEW_CAP, incremental_cap=NEW_CAP,
                predecessor_authorization=AUTH_PARENT, predecessor_accounted=PRIOR_HELD,
                predecessor_settled=PRIOR_COST, predecessor_calls=504, predecessor_unresolved=2,
                experiment='parallel-wallclock-development-seeds24-25', serial_transport_per_worker=False,
                max_concurrent_generator_requests=4, run_limit=4000000000, route_limit=4000000000,
                accounted_cny_ceiling=str(Decimal(PRIOR_HELD+NEW_CAP)/10**9*Decimal('8.8')))
    assert auth['total'] <= 10*10**9
    return once(source, 'AUTH_RAW = json.dumps(AUTH,', 'AUTH.update('+repr(auth)+')\nAUTH_RAW = json.dumps(AUTH,')


def artifacts(output):
    configure()
    output.mkdir(exist_ok=False)
    changed = {
        PREFIX+'paid_transport.py': patch_transport(git('show', BASE+':'+PREFIX+'paid_transport.py').decode()).encode(),
        'src/dojo/core/interpreters/jupyter/kernel_readiness.py': patch_readiness(
            git('show', BASE+':src/dojo/core/interpreters/jupyter/kernel_readiness.py').decode()).encode(),
        PREFIX+'paid_budget.py': budget_source(git('show', BASE+':'+PREFIX+'paid_budget.py').decode()).encode(),
    }
    for raw in changed.values():
        compile(raw, '<parallel source>', 'exec')
    with tempfile.TemporaryDirectory(prefix='forets-parallel-index-') as temp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(temp)/'index'))
        git('read-tree', BASE, env=env)
        for name, raw in changed.items():
            blob = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
            git('update-index', '--add', '--cacheinfo', '100644,'+blob+','+name, env=env)
        tree = git('write-tree', env=env).decode().strip()
    files = {}
    for line in git('ls-tree','-r',tree,'--','src/aira_core','src/dojo').decode().splitlines():
        head, name = line.split('\t')
        _, kind, blob = head.split()
        if kind != 'blob':
            raise ValueError('source kind')
        files[name] = sha(git('cat-file','blob',blob))
    archive = git('-c','core.autocrlf=false','archive','--format=tar',tree,'src/aira_core','src/dojo',
                  env=dict(os.environ, GIT_LFS_SKIP_SMUDGE='1'))
    write(output/'source.tar', archive)
    info = dict(base_tree=BASE, source_tree=tree, source_files=files, archive_sha256=sha(archive),
                modified_files=sorted(changed), commit=git('rev-parse','HEAD').decode().strip(),
                plan_sha256=sha(Path(__file__).with_name(PLAN).read_bytes()), matrix=common.order())
    write(output/'artifact.json', encode(info))
    print(json.dumps({k:v for k,v in info.items() if k!='source_files'}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=('artifacts','build','activate'))
    p.add_argument('path', type=Path)
    a = p.parse_args()
    os.umask(0o077)
    configure()
    (artifacts if a.mode=='artifacts' else getattr(common,a.mode))(a.path)
