"""Bounded fresh continuation-action bank; reuse the proven native executor."""
import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import tarfile
import tempfile
import time
from dataclasses import asdict
from pathlib import Path, PurePosixPath

from run_comparison_spooky_pool_20260919 import (
    BASE, INPUT, SOURCE, SOURCE_ROOT, TREE, NODES, HELPERS, DONOR, SECRET,
    now, read, write, sha, source_check, setup, one,
)

SCRIPT = 'run_comparison_reuse_20260919.py'
PLAN = 'comparison_reuse_plan_20260919.json'
RUNS = {1: '3277c81be72a1c30', 2: '58d3914785a2cfe1'}
PREFIX_ERRORS = {
    1: "TypeError: LogisticRegression.__init__() got an unexpected keyword argument 'multi_class'",
    2: "TypeError: TfidfVectorizer.__init__() got an unexpected keyword argument 'lower_case'",
}


def select_rows(nodes):
    rows = []
    for seed, run in RUNS.items():
        executed = {n['step']: n for n in nodes if n['run'] == run and n['group'] == 'executed'}
        if len(executed) != sum(n['run'] == run and n['group'] == 'executed' for n in nodes):
            raise ValueError('duplicate execution index')
        parent, debug = executed[1], executed[2]
        if parent['parents'] != [0] or 'draft' not in parent['operators_used']:
            raise ValueError('first executed initial draft')
        if debug['parents'] != [1] or 'debug' not in debug['operators_used']:
            raise ValueError('first direct debug, not a later successful retry')
        cached = sorted((n for n in nodes if n['run'] == run and n['group'] == 'unselected'
                         and n['parents'] == [0] and 'draft' in n['operators_used']),
                        key=lambda n: (n['creation_time'], n['id']))
        if len(cached) != 4:
            raise ValueError('four complete initial cache candidates')
        for slot, (role, n) in enumerate([('prefix', parent), ('debug', debug)] + [('cache', n) for n in cached]):
            rows.append(dict(index=len(rows), seed=seed, run=run, slot=slot, role=role,
                             task='spooky-author-identification', node=n['id'],
                             raw_code_sha256=n['code_sha256']))
    if len({r['node'] for r in rows}) != 12:
        raise ValueError('unique source candidates required')
    return rows


def root_check(root):
    root = root.resolve(strict=True)
    if root.parent != BASE or not re.fullmatch(r'comparison-reuse-20260919-[a-z0-9_]+', root.name):
        raise ValueError('root scope')
    return root


def prepared(root):
    root_check(root)
    p = read(root / 'prepared.json')
    if len(p['rows']) != 12 or (p['execution_seconds'], p['allocation_seconds']) != (7200, 9000):
        raise ValueError('protocol drift')
    for seed in (1, 2):
        roles = [r['role'] for r in p['rows'] if r['seed'] == seed]
        if roles != ['prefix', 'debug', 'cache', 'cache', 'cache', 'cache']:
            raise ValueError('action bank drift')
    for name, expected in p['files'].items():
        if sha((root / name).read_bytes()) != expected:
            raise ValueError('prepared file drift')
    return p


def binding_context(env):
    root = root_check(Path(env['FORETS_CURRENT_POOL_ROOT']))
    identity = Path(env['DOJO_WORKER_IDENTITY_PATH'])
    if identity.parent != root or not re.fullmatch(r'identity-(?:[0-9]|1[01])\.json', identity.name):
        raise ValueError('worker identity scope')
    if read(root / 'execution-claim.json')['job'] != env['SLURM_JOB_ID']:
        raise ValueError('allocation identity')
    return identity.with_suffix('.native-binding.json')


def prepare(commit):
    if not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('commit identity')
    source_check()
    root = Path(tempfile.mkdtemp(prefix='comparison-reuse-20260919-', dir=BASE))
    setup(root, commit)
    from dojo.core.solvers.utils.response import extract_code
    from dojo.config_dataclasses.interpreter.fresh_container import FreshContainerInterpreterConfig
    rows = select_rows(read(INPUT / 'qwen-readout-v1/nodes.json', NODES))
    wanted = {r['node']: r for r in rows}
    codes = {}
    with tarfile.open(INPUT / 'archives/spooky-author-identification.tar.gz', 'r|gz') as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if not member.isfile() or path.name not in ('journal.jsonl', 'journal_for_unselected.jsonl'):
                continue
            run = sha(str(path.parent.parent).encode())[:16]
            if run not in RUNS.values():
                continue
            for line in archive.extractfile(member):
                n = json.loads(line)
                if n.get('id') not in wanted:
                    continue
                row = wanted[n['id']]
                raw = (n.get('code') or '').encode()
                if row['run'] != run or sha(raw) != row['raw_code_sha256'] or SECRET.search(raw) or n['id'] in codes:
                    raise ValueError('code identity/security')
                if re.search(rb'/prepared/private|/data/private|/research/[^\s\"\x27]+', raw):
                    raise ValueError('unapproved filesystem reference')
                codes[n['id']] = raw.decode()
    if set(codes) != set(wanted):
        raise ValueError('complete source extraction')
    for name in ('codes', 'configs', 'opencl-vendors'):
        (root / name).mkdir()
    prior = read(DONOR / 'prepared.json')
    for name in HELPERS:
        src = DONOR / name
        if sha(src.read_bytes()) != prior['files'][name]:
            raise ValueError('native adapter changed')
        dst = root / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    for name in (SCRIPT, PLAN, 'run_comparison_spooky_pool_20260919.py',
                 'readout_comparison_spooky_pool_20260919.py', 'readout_comparison_reuse_20260919.py'):
        shutil.copy2(Path(__file__).with_name(name), root / name)
    (root / 'forets_current_pool_20260912.py').write_text('from run_comparison_reuse_20260919 import binding_context\n')
    (root / 'opencl-vendors/nvidia.icd').write_text('libnvidia-opencl.so.1\n')
    for row in rows:
        i = row['index']
        raw = codes[row['node']]
        code = extract_code(raw)
        row['code_sha256'] = sha(code.encode())
        (root / 'codes' / f'{i}.raw.private.py').write_bytes(raw.encode())
        (root / 'codes' / f'{i}.private.py').write_bytes(code.encode())
        cfg = FreshContainerInterpreterConfig(working_dir=str(root / f'work-{i}'), timeout=7200,
            container_runtime='singularity', superimage_directory=str(BASE / 'aira-dojo/build/superimage'),
            superimage_version='2026-07-macos-v1',
            env={n: '6' for n in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')})
        cfg.validate()
        write(root / 'configs' / f'{i}.json', asdict(cfg))
    batch = '''#!/bin/bash
#SBATCH --job-name=comparison-reuse-debug
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:6
#SBATCH --cpus-per-task=36
#SBATCH --time=02:30:00
#SBATCH --no-requeue
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
timeout --signal=TERM --kill-after=10s 8950s /research/d7/spc/yzyang4/venvs/aira/bin/python -B ROOT/run_comparison_reuse_20260919.py coordinate --root ROOT
'''.replace('ROOT', str(root))
    (root / 'run.sbatch').write_text(batch)
    files = {str(p.relative_to(root)): sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
    p = dict(commit=commit, source_tree=TREE, utc=now(), rows=rows, files=files,
             execution_seconds=7200, allocation_seconds=9000, gpu_hours_cap=15, api_calls=0,
             role='exploratory_historical_continuation_actions_not_live_e2e')
    receipt = write(root / 'prepared.json', p)
    print(json.dumps(dict(status='PREPARED_NOT_SUBMITTED', root=str(root), prepared_sha256=receipt,
                          candidates=len(rows), gpu_hours_cap=15)), flush=True)


def coordinate(root):
    p = prepared(root)
    source_check()
    job = os.environ['SLURM_JOB_ID']
    if socket.gethostname().split('.')[0] != 'gpu28' or read(root / 'launch.json')['job'] != job:
        raise ValueError('allocation')
    write(root / 'execution-claim.json', dict(job=job, utc=now()))
    start = time.monotonic()
    completed, deferred = [], []
    for seed in (1, 2):
        if p['allocation_seconds'] - 100 - (time.monotonic() - start) < 7500:
            deferred.append(seed)
            continue
        rows = [r for r in p['rows'] if r['seed'] == seed]
        write(root / f'pool-start-{seed}.json', dict(seed=seed, job=job, utc=now(), indices=[r['index'] for r in rows]))
        processes = []
        for row in rows:
            command = ['srun', '--exclusive', '--ntasks=1', '--cpus-per-task=6', '--gres=gpu:1', '--time=02:04:00',
                       str(BASE / 'venvs/aira/bin/python'), '-B', str(root / SCRIPT), 'execute', '--root', str(root), '--index', str(row['index'])]
            with (root / f'worker-{row["index"]}.private.log').open('xb') as handle:
                processes.append(subprocess.Popen(command, stdout=handle, stderr=handle))
        codes = [p.wait() for p in processes]
        write(root / f'pool-finished-{seed}.json', dict(seed=seed, worker_returncodes=codes, utc=now()))
        completed.append(seed)
        if any(codes):
            deferred.extend(s for s in (1, 2) if s > seed)
            break
    write(root / 'finished.json', dict(job=job, attempted_seeds=completed, unstarted_seeds=deferred, utc=now(), api_calls=0))


def execute(root, index):
    p = prepared(root)
    setup(root, p['commit'])
    if not os.environ.get('SLURM_STEP_ID', '').isdigit() or read(root / 'execution-claim.json')['job'] != os.environ['SLURM_JOB_ID']:
        raise ValueError('native step required')
    one(root, p['rows'][index])


def submit(root):
    p = prepared(root)
    source_check()
    cpu = read(root / 'cpu-preflight.json')
    if cpu['status'] != 'PASS' or cpu['cases'] != 12 or cpu['prepared_sha256'] != sha((root / 'prepared.json').read_bytes()):
        raise ValueError('actual CPU driver preflight required')
    st = (BASE / 'aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif').stat()
    if (st.st_size, st.st_mtime_ns) != (19717783552, 1784638286000000000):
        raise ValueError('original image')
    public = BASE / 'mle-bench-data/spooky-author-identification/prepared/public'
    if not all((public / name).is_file() for name in ('train.csv', 'test.csv', 'sample_submission.csv')):
        raise ValueError('public data missing')
    reserve = root / 'own-capacity-check'
    with reserve.open('xb') as handle:
        os.posix_fallocate(handle.fileno(), 0, 256 * 1024 ** 2)
    reserve.unlink()
    env = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    queue = subprocess.check_output(['squeue', '-u', 'yzyang4', '-h', '-o', '%i'], env=env, text=True, timeout=25)
    if len(queue.strip().splitlines()) >= 4:
        raise ValueError('job count cap')
    write(root / 'submit-intent.json', dict(utc=now(), prepared_sha256=sha((root / 'prepared.json').read_bytes()), gpu_hours_cap=15))
    result = subprocess.run(['sbatch', '--parsable', '--output=' + str(root / 'allocation-%j.out'),
                             '--error=' + str(root / 'allocation-%j.err'), str(root / 'run.sbatch')],
                            env=env, capture_output=True, text=True, timeout=25)
    job = result.stdout.strip().split(';')[0]
    if result.returncode or not job.isdigit():
        raise RuntimeError('ambiguous submit; do not retry')
    write(root / 'launch.json', dict(job=job, utc=now(), prepared_sha256=sha((root / 'prepared.json').read_bytes())))
    print(json.dumps(dict(job=job, root=str(root), gpu_hours_cap=p['gpu_hours_cap'])), flush=True)


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('prepare', 'submit', 'coordinate', 'execute'))
    parser.add_argument('--root', type=Path)
    parser.add_argument('--commit')
    parser.add_argument('--index', type=int)
    args = parser.parse_args()
    if args.mode == 'prepare': prepare(args.commit)
    elif args.mode == 'submit': submit(args.root)
    elif args.mode == 'coordinate': coordinate(args.root)
    else: execute(args.root, args.index)
