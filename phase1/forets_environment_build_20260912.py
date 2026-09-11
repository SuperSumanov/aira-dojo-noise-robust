"""Fresh four-run development repair; reuse qualified execution, not old runs.

Local artifact mode constructs an exact Git tree. Remote build copies only
fixed code/configs. Budget activation seals the closed predecessor and carries
its settled cost into the successor; it never resets its calls or old scopes.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tarfile
import tempfile

from forets_environment_context_20260912 import apply_context, CONTEXT_SHA
from forets_paid_patch_20260911 import once

PARENT = Path('/research/d7/spc/yzyang4/forets-paid-20260911-oh3np7b8')
BASE = 'f9087ae47470f7f1868c61405c3b827327f31c2c'
PARENT_PREPARED = '58558eed5abe1f793c77049572549c66de8c104255f8a13fa3c48e0a8b4d3593'
PARENT_INVENTORY = '6857f18c60fecaa745710960c0f2f9dfd50d485717ca8a7e86faa47dedc10c1b'
PARENT_RELEASE = '819621d75c9c95efe1e337866884b8701ad5f3f71cf5ea7e849f2b6ab0dd8798'
PARENT_AUTH = 'c274cfc456296b85a8cb2b85ba9f66d28f738132462119e6fbb7f58d6c2e5c1e'
PRIOR_COST = 318775548  # integer nano-USD, all 124 predecessor calls settled
NEW_CAP = 1500000000
PREFIX = 'src/dojo/core/solvers/llm_helpers/backends/'


def sha(raw): return hashlib.sha256(raw).hexdigest()
def encode(value): return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
def read(path, digest=None):
    raw = path.read_bytes()
    if digest and sha(raw) != digest: raise ValueError('fixed artifact drift')
    return json.loads(raw)
def write(path, raw):
    with path.open('xb') as stream: stream.write(raw)
    return sha(raw)
def git(*args, data=None, env=None):
    return subprocess.run(['git', *args], input=data, capture_output=True, check=True, env=env).stdout


def budget_source(original):
    """Same reservation/settlement code, smaller cap plus explicit carried cost."""
    text = once(original, 'AUTH_RAW = json.dumps(AUTH,',
        "AUTH.update(version=2, total=1818775548, predecessor_cost=318775548,\n"
        "    incremental_cap=1500000000, predecessor_authorization='" + PARENT_AUTH + "',\n"
        "    accounted_cny_ceiling='16.0052248224', experiment='environment-context-seed10')\n"
        'AUTH_RAW = json.dumps(AUTH,')
    text = once(text, "len(run_ids) != 8 or len(set(run_ids)) != 8 or 'route' in run_ids",
        "len(run_ids) != 4 or len(set(run_ids)) != 4 or any(x in run_ids for x in ('route', 'closed_predecessor'))")
    text = once(text, 'exact eight unique scopes required', 'exact four fresh scopes required')
    text = once(text, "        db.execute('INSERT INTO auth VALUES (?,?,0)', (AUTH_SHA, AUTH_RAW.decode()))",
        "        db.execute('INSERT INTO auth VALUES (?,?,0)', (AUTH_SHA, AUTH_RAW.decode()))\n"
        "        db.execute('INSERT INTO scopes VALUES (?,?)', ('closed_predecessor', 0))\n"
        "        db.execute('INSERT INTO calls VALUES (?,?,?,?,?,?)',\n"
        "            ('carried-124-settled-calls', 'closed_predecessor', 318775548, 318775548, 'settled', time.time()))")
    return text


def artifact(output):
    output.mkdir(exist_ok=False)
    commit = git('rev-parse', 'HEAD').decode().strip()
    modified = {PREFIX+'paid_budget.py': budget_source(git('show', BASE+':'+PREFIX+'paid_budget.py').decode()).encode()}
    with tempfile.TemporaryDirectory(prefix='forets-env-index-') as directory:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(directory)/'index'))
        git('read-tree', BASE, env=env)
        for name, raw in modified.items():
            blob = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
            git('update-index', '--add', '--cacheinfo', '100644,'+blob+','+name, env=env)
        tree = git('write-tree', env=env).decode().strip()
    archive = git('-c', 'core.autocrlf=false', 'archive', '--format=tar', tree, 'src/aira_core', 'src/dojo',
                  env=dict(os.environ, GIT_LFS_SKIP_SMUDGE='1'))
    write(output/'source.tar', archive)
    files = {}
    for line in git('ls-tree', '-r', tree, '--', 'src/aira_core', 'src/dojo').decode().splitlines():
        head, name = line.split('\t'); _, kind, blob = head.split()
        if kind != 'blob': raise ValueError('unexpected source entry')
        files[name] = sha(git('cat-file', 'blob', blob))
    info = dict(base_tree=BASE, source_tree=tree, commit=commit, source_files=files,
                archive_sha256=sha(archive), context_sha256=CONTEXT_SHA)
    write(output/'artifact.json', encode(info))
    print(json.dumps({k:v for k,v in info.items() if k != 'source_files'}))


def replace(value, mapping):
    if isinstance(value, dict): return {k:replace(v, mapping) for k,v in value.items()}
    if isinstance(value, list): return [replace(v, mapping) for v in value]
    if isinstance(value, str):
        for old, new in mapping.items(): value = value.replace(old, new)
    return value


def derive_controller(name, text):
    """Explicit versioned matrix reduction; unchanged evaluator formulas."""
    if name == 'forets_block_controller_20260911.py':
        text = once(text, 'enumerate((8, 9), 1)', 'enumerate((10,), 1)')
        text = once(text, 'block not in (1, 2)', 'block not in (1,)')
    if name == 'forets_native_run_20260911.py':
        text = once(text, 'choices=(1,2)', 'choices=(1,)')
    if name == 'forets_block_collect_20260911.py':
        text = once(text, 'for block in (1,2):', 'for block in (1,):')
        text = once(text, "    if starts[0]['controller_commit']!=starts[1]['controller_commit']:\n        raise ValueError('blocks used different controller code')",
            "    if len(starts)!=1: raise ValueError('exactly one development block required')")
    if name == 'forets_block_readout_20260911.py':
        for old, new in [
            ('!= [1, 2]', '!= [1]'),
            ('block_spec(prepared, 1); block_spec(prepared, 2)', 'block_spec(prepared, 1)'),
            ('len(actual) != 8', 'len(actual) != 4'),
            ('for seed in (8, 9):', 'for seed in (10,):'),
            ('planned_pairs=2,', 'planned_pairs=1,'),
            ('planned_runs_per_arm=2,', 'planned_runs_per_arm=1,'),
            ('planned_runs=8, planned_pairs=4,', 'planned_runs=4, planned_pairs=2,'),
            ('Exploratory two-task/two-seed matrix;', 'Exploratory two-task/single-seed environment repair;'),
        ]: text = once(text, old, new)
    return text


def build(stage):
    info = read(stage/'artifact.json')
    if info['base_tree'] != BASE or info['context_sha256'] != CONTEXT_SHA:
        raise ValueError('wrong source/context base')
    if sha((stage/'source.tar').read_bytes()) != info['archive_sha256']: raise ValueError('archive drift')
    old = read(PARENT/'prepared.json', PARENT_PREPARED)
    code_manifest = read(PARENT/'code/code-manifest.json')
    root = Path(tempfile.mkdtemp(prefix='forets-env-20260912-', dir=PARENT.parent)); os.chmod(root, 0o700)
    for name in ('source','code','configs','launchers','runs'): (root/name).mkdir(mode=0o700)
    with tarfile.open(stage/'source.tar') as archive:
        seen = set()
        for member in archive:
            if member.isdir(): continue
            if not member.isfile() or member.name not in info['source_files'] or member.name in seen:
                raise ValueError('unexpected archive entry')
            target = root/'source'/member.name
            if not target.resolve().is_relative_to(root/'source'): raise ValueError('unsafe archive')
            raw = archive.extractfile(member).read()
            if sha(raw) != info['source_files'][member.name]: raise ValueError('source digest differs')
            target.parent.mkdir(parents=True, exist_ok=True); write(target, raw); seen.add(member.name)
        if seen != set(info['source_files']): raise ValueError('incomplete archive')
    inventory_sha = write(root/'source-files.json', encode(info['source_files']))
    os.environ.update(PYTHON_DOTENV_DISABLED='1', LITELLM_LOCAL_MODEL_COST_MAP='True', LOGGING_DIR=str(root),
        MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',
        SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
        DEFAULT_SLURM_PARTITION='gpu_24h', DEFAULT_SLURM_ACCOUNT='gpu', DEFAULT_SLURM_QOS='gpu')
    sys.path.insert(0, str(root/'source/src')); sys.path.append(str(PARENT/'code'))
    from dojo.config_dataclasses.run import RunConfig
    from forets_e2e_package import common_config
    rows, normal = [], []
    for original in old['run_configs'][:4]:
        run_id = original['run_id'].replace('-s8-', '-s10-')
        cfg = read(PARENT/'configs'/(original['run_id']+'.json'), original['config_sha256'])
        cfg = replace(cfg, {str(PARENT):str(root), original['run_id']:run_id})
        cfg['metadata']['seed'] = cfg['solver']['selector_seed'] = 10
        cfg['metadata']['git_commit_id'] = info['commit']
        cfg['metadata']['description'] = 'environment-context-development-source-tree-'+info['source_tree']
        cfg = apply_context(cfg)
        typed = RunConfig.from_dict(cfg); typed.validate()
        if typed.to_typed_dict() != cfg: raise ValueError('typed roundtrip differs')
        digest = write(root/'configs'/(run_id+'.json'), encode(cfg))
        rows.append(dict(original, run_id=run_id, seed=10, config_sha256=digest))
        normal.append(common_config(cfg, run_id=run_id, run_dir=root/'runs'/run_id))
    if normal[0] != normal[1] or normal[2] != normal[3]: raise ValueError('arms differ beyond selector')
    prepared = replace(old, {str(PARENT):str(root)})
    prepared.update(source_tree=info['source_tree'], base_source_tree=BASE, run_configs=rows, run_count=4,
        blocks=1, paired_configs=2, nominal_gpu_hours=280*2/60, source_archive_sha256=info['archive_sha256'],
        source_files=len(info['source_files']), preparation_commit=info['commit'],
        remaining=['activate cumulative budget', 'bounded route', 'real development viability'],
        preparation_files_sha256={}, paired_config_sha256=[sha(encode(normal[i])) for i in (0,2)],
        environment_context_sha256=CONTEXT_SHA, plan_sha256=sha((stage/'FORETS_ENVIRONMENT_REPAIR_PLAN_20260912.md').read_bytes()))
    prepared_sha = write(root/'prepared.json', encode(prepared))
    manifest = read(PARENT/'manifest.json'); manifest.update(source_tree=info['source_tree'], runs=rows)
    write(root/'manifest.json', encode(manifest)); write(root/'launchers/block-1.json', encode(old['launcher']))
    write(root/'allocation-budget-correction.json', (PARENT/'allocation-budget-correction.json').read_bytes())
    write(root/'PACKAGE_STATE.json', encode(dict(execution_allowed=False, readiness=False, package=str(root))))
    namespace = {}; budget_raw = (root/'source'/PREFIX/'paid_budget.py').read_bytes()
    exec(compile(budget_raw, '<new-budget>', 'exec'), namespace)
    spec = read(PARENT/'code/forets_native_e2e_release_20260911.json', PARENT_RELEASE)
    spec.update(package=str(root), source_tree=info['source_tree'], blocks=[1], seeds=[10], runs=4,
        maximum_gpu_hours_including_observed_killwait=10, paid_authorization_sha256=namespace['AUTH_SHA'],
        environment_context_sha256=CONTEXT_SHA, development_purpose='valid_final_solution_viability')
    release_raw = encode(spec); release_sha = sha(release_raw)
    mapping = {str(PARENT):str(root), BASE:info['source_tree'], PARENT_PREPARED:prepared_sha,
               PARENT_INVENTORY:inventory_sha, PARENT_RELEASE:release_sha}
    derivation = {}
    for name, digest in code_manifest['files'].items():
        raw = (PARENT/'code'/name).read_bytes()
        if sha(raw) != digest: raise ValueError('parent controller changed')
        if name == 'forets_native_e2e_release_20260911.json': new = release_raw
        elif name == 'forets_paid_budget_20260911.py': new = budget_raw
        else: new = derive_controller(name, replace(raw.decode(), mapping)).encode()
        target = root/'code'/name; target.parent.mkdir(parents=True, exist_ok=True); write(target, new)
        derivation[name] = dict(base_sha256=sha(raw), derived_sha256=sha(new))
    os.chmod(root/'code/bin/singularity', 0o700)
    for name in ('forets_environment_build_20260912.py','forets_environment_context_20260912.py'):
        write(root/'code'/name, (stage/name).read_bytes())
    write(root/'plan.md', (stage/'FORETS_ENVIRONMENT_REPAIR_PLAN_20260912.md').read_bytes())
    files = {str(p.relative_to(root/'code')):sha(p.read_bytes()) for p in (root/'code').rglob('*') if p.is_file()}
    write(root/'code/code-manifest.json', encode(dict(commit=info['commit'], files=files, derivation=derivation)))
    # No requests can run before activate(): the new database does not exist.
    report = dict(status='BUILT_NO_GPU_NO_API_BUDGET_NOT_ACTIVATED', package=str(root), source_tree=info['source_tree'],
        commit=info['commit'], prepared_sha256=prepared_sha, inventory_sha256=inventory_sha,
        release_sha256=release_sha, context_sha256=CONTEXT_SHA, new_runs=4, predecessor_cost_nano_usd=PRIOR_COST,
        new_cap_nano_usd=NEW_CAP, cumulative_cap_nano_usd=PRIOR_COST+NEW_CAP)
    write(root/'build.json', encode(report)); print(json.dumps(report))


def activate(root):
    """Stop closed predecessor BEFORE enabling successor; no calls removed."""
    root = root.resolve(strict=True)
    if root.parent != PARENT.parent or not root.name.startswith('forets-env-20260912-'):
        raise ValueError('not the explicit fresh development root')
    if (root/'paid.sqlite').exists(): raise ValueError('successor budget already activated')
    env = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    q = subprocess.run(['sacct','-X','-j','13088,13112','-nP','--format=JobIDRaw,State,ExitCode'],
        capture_output=True, text=True, env=env, timeout=15, check=True).stdout
    records = [line.split('|') for line in q.splitlines() if line.strip()]
    if {(r[0],r[1],r[2]) for r in records} != {('13088','COMPLETED','0:0'),('13112','COMPLETED','0:0')}:
        raise ValueError('predecessor not independently terminal')
    with sqlite3.connect((PARENT/'paid.sqlite').as_uri()+'?mode=rw', uri=True) as db:
        db.execute('BEGIN IMMEDIATE')
        auth = db.execute('SELECT digest,stopped FROM auth').fetchall()
        counts = db.execute('SELECT COUNT(*),SUM(held),SUM(cost),SUM(state="unresolved") FROM calls').fetchone()
        if auth != [(PARENT_AUTH,0)] or counts != (124,PRIOR_COST,PRIOR_COST,0):
            raise ValueError('predecessor billing changed; no automatic handover')
        write(root/'parent-ledger-seal.json', encode(dict(parent=str(PARENT), authorization_sha256=PARENT_AUTH,
            closed_calls=124, carried_cost_nano_usd=PRIOR_COST, successor=str(root))))
        db.execute('UPDATE auth SET stopped=1')
    namespace = {}; exec(compile((root/'code/forets_paid_budget_20260911.py').read_bytes(), '<successor>', 'exec'), namespace)
    prepared = read(root/'prepared.json', read(root/'build.json')['prepared_sha256'])
    namespace['initialize'](root/'paid.sqlite', [r['run_id'] for r in prepared['run_configs']])
    write(root/'paid-authorization.json', encode(namespace['AUTH']))
    print(json.dumps(dict(status='CUMULATIVE_BUDGET_ACTIVE_OLD_LEDGER_SEALED', billing=namespace['snapshot'](root/'paid.sqlite'))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('mode', choices=('artifact','build','activate')); p.add_argument('path', type=Path)
    a = p.parse_args(); {'artifact':artifact, 'build':build, 'activate':activate}[a.mode](a.path)
