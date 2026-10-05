"""Bounded original-code replay of an already frozen public-source sample.

Not a new method, a comparison of generators, or a replication of published GOME
scores. Only approved, repeatedly used development views are mounted. The source
sample predates this execution; dependencies, not outcomes, define eligibility.
"""
import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

B = Path('/research/d7/spc/yzyang4')
R = B/'external-pair-replay-20261006-v1'
D = B/'matched-representation-20261005-v1'
F = B/'collateral-factorial-20261006-v1'
PY = B/'venvs/aira/bin/python'
NAME = 'external_pair_replay_20261006.py'
SAMPLE = B/'collateral-sample-20261006-v1'
TASKS = ('random-acts-of-pizza', 'spooky-author-identification')
PIN = '82bcbbfcb7f1022b246fce0703e81de4a788c67d5fc5d1b3fc0285f77fc077d5'
RUNTIME_SHA = 'b422a17094a6971218731054b53b56888505150b82f5309990b0b629577da4c9'
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda: f.read(8*1024**2), b''):
            h.update(chunk)
    return h.hexdigest()


def read(p):
    raw = Path(p).read_bytes()
    assert not SECRET.search(raw), 'credential-shaped content withheld'
    return json.loads(raw)


def write(p, value):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
    assert not SECRET.search(raw)
    with Path(p).open('xb') as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def wrap(code):
    # An I/O alias and a script entry point; the entire original code is intact.
    return ('import os as _entry_os, sys as _entry_sys\n'
            'assert _entry_os.path.isdir("data")\n'
            'assert not _entry_os.path.lexists("workspace_input")\n'
            '_entry_os.symlink(_entry_os.path.abspath("data"), "workspace_input")\n'
            '_entry_sys.argv = ["gome_source.py"]\n'
            f'exec(compile({code!r}, "gome_source.py", "exec"), '
            '{"__name__":"__main__", "__file__":"gome_source.py"})\n')


def tests():
    import ast
    source = 'x=7\nif __name__=="__main__": y=x+2\n'
    tree = ast.parse(wrap(source))
    call = tree.body[-1].value
    assert call.args[0].args[0].value == source
    assert call.args[1].keys[0].value == '__name__'
    compile(tree, 'wrapper-test', 'exec')
    assert '__debug__' not in wrap(source) and '--debug' not in wrap(source)
    assert not SECRET.search(b'task-replay fixture')
    io_test = 'not_run_on_windows'
    if os.name != 'nt':
        import tempfile
        old_cwd, old_argv = os.getcwd(), sys.argv[:]
        try:
            with tempfile.TemporaryDirectory(prefix='external-replay-fixture-') as tmp:
                os.chdir(tmp)
                Path('data').mkdir()
                Path('data/input.txt').write_text('fixture-only')
                fixture = ('import pathlib,sys\n'
                           'assert __name__=="__main__"\n'
                           'assert sys.argv==["gome_source.py"]\n'
                           'assert pathlib.Path("workspace_input/input.txt").read_text()=="fixture-only"\n')
                exec(compile(wrap(fixture), 'fixture-wrapper', 'exec'), {})
                assert Path('workspace_input').resolve() == Path('data').resolve()
                io_test = 'PASS'
        finally:
            os.chdir(old_cwd)
            sys.argv = old_argv
    return dict(status='PASS', exact_source_payload=True, script_entry=True,
                no_debug_downsampling=True, credential_false_positive_fixture=True,
                isolated_io_fixture=io_test)


def schedule():
    return read(R/'plan.json')['schedule']


def check():
    p = read(R/'plan.json')
    for name, expected in p['files'].items():
        assert sha(R/name) == expected, name
    assert len(p['schedule']) == 6
    return p


def runtime():
    assert sha(R/'runtime.py') == RUNTIME_SHA
    m = load('external_replay_runtime', R/'runtime.py')
    m.R = R
    m.setup()
    return m


def prepare(commit):
    assert re.fullmatch('[a-f0-9]{40}', commit) and not R.exists()
    assert sha(SAMPLE/'structure.json') == PIN
    assert sha(SAMPLE/'sample.json') == read(SAMPLE/'structure.json')['sample_sha256']
    assert sha(D/'plan.json') == 'fed6f8c812fc49db8acc459b460a10bbe962cbe10b8a2172f5dff06c7686a624'
    sys.path.insert(0, str(B))
    import collateral_sample_20261006 as sample
    sampled = read(SAMPLE/'sample.json')['selected']
    population = [r for r in sampled if r['task'] in TASKS]
    assert len(population) == 4
    # The fourth pair needs SentenceTransformer downloads/caches not part of the
    # frozen original task image. Do not fetch weights or rewrite its pipeline.
    excluded = [r for r in population if r['task'] == TASKS[0] and r['file'] == 'Trace_3.json']
    eligible = [r for r in population if r not in excluded]
    assert len(excluded) == 1 and len(eligible) == 3
    eligible.sort(key=lambda r: (r['task'], r['file'], r['loop']))
    R.mkdir(mode=0o700)
    for rel, expected in read(D/'plan.json')['files'].items():
        if not rel.startswith(('source/', 'forets_', 'opencl-vendors/')):
            continue
        assert sha(D/rel) == expected
        dest = R/rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(D/rel, dest)
    assert sha(D/'runtime.py') == RUNTIME_SHA
    shutil.copyfile(D/'runtime.py', R/'runtime.py')
    shutil.copyfile(__file__, R/NAME)
    # Reuse the previously executed worker, with only its outer duration changed.
    old = (F/'run_collateral_factorial_20261006.py').read_text()
    assert sha(F/'run_collateral_factorial_20261006.py') == read(F/'plan.json')['files']['run_collateral_factorial_20261006.py']
    assert old.count('with ExperimentDeadline(390).activate():') == 1
    with (R/'worker_helper.py').open('x') as f:
        f.write(old.replace('with ExperimentDeadline(390).activate():', 'with ExperimentDeadline(1350).activate():'))
    (R/'configs').mkdir()
    (R/'bin').mkdir()
    with (R/'bin/singularity').open('x') as f:
        f.write(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom external_pair_replay_20261006 import runtime\nruntime().task_runtime()\n')
    os.chmod(R/'bin/singularity', 0o700)
    rows = []
    for case, r in enumerate(eligible):
        raw = (sample.ROOT/r['file']).read_bytes()
        assert sample.digest(raw) == sample.PINS[r['file']]
        obj = json.loads(raw)
        folder = R/f'case-{case}.private'
        folder.mkdir()
        hashes = {}
        for arm, key in [('P', 'base_code'), ('C', 'code')]:
            code = obj[r['task']][r['loop']][key]
            expected = r['base_sha256' if arm == 'P' else 'code_sha256']
            assert sample.digest(code) == expected and not SECRET.search(code.encode())
            compile(code, 'original-public-source', 'exec')
            text = wrap(code)
            compile(text, 'wrapped-public-source', 'exec')
            with (folder/f'{arm}.py').open('x') as f:
                f.write(text)
            hashes[arm] = sha(folder/f'{arm}.py')
        for arm in (('P', 'C') if case % 2 == 0 else ('C', 'P')):
            i = len(rows)
            s = dict(index=i, case=case, arm=arm, task=r['task'], seed=116201+case,
                     code_sha256=hashes[arm], original_sha256=r['base_sha256' if arm == 'P' else 'code_sha256'],
                     public_file=r['file'], public_loop=r['loop'])
            rows.append(s)
            ep = R/f'episode-{i}'
            ep.mkdir()
            cfg = read(D/'configs'/('0.json' if r['task'] == TASKS[0] else '2.json'))
            cfg['id'] = f'external-replay-{i}'
            cfg['logger'].update(output_dir=str(ep/'native-log'), write_env_vars=False,
                                 use_wandb=False, print_config=False, use_console=False)
            cfg['metadata'].update(seed=s['seed'], base_path=str(R/'source'), git_commit_id=commit,
                                   script_id='external-pair-replay-20261006')
            cfg['task'].update(cache_dir=str(R/'no-official-data'), results_output_dir=str(ep/'native-log/results'))
            cfg['interpreter'].update(timeout=1200, working_dir=str(ep/'action-0/work'))
            cfg['interpreter']['env'].update(PYTHONHASHSEED=str(s['seed']), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
            write(R/'configs'/f'{i}.json', cfg)
    batch = f'''#!/bin/bash
#SBATCH --job-name=external-pair-replay
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --time=02:30:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 8920s {PY} -B {R}/{NAME} controller
'''
    with (R/'run.sbatch').open('x') as f:
        f.write(batch)
    write(R/'plan.json', dict(protocol='external-original-pair-portability-v1', source_commit=commit,
        source_sample_sha256=sha(SAMPLE/'sample.json'), source_structure_sha256=PIN,
        source_pins=sample.PINS, source_eligible=eligible, source_excluded=[dict(**r, reason='external_sentence_transformer_weights') for r in excluded],
        schedule=rows, files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file()},
        task_image_sha256=read(D/'preflight.json')['task_image_sha256'], tests=tests(),
        program_seconds=1200, worker_seconds=1350, step_seconds=1380, allocation_seconds=9000,
        gpus=1, gpu_hours_cap=2.5, generator_calls=0, paid_api=0, base_training=False,
        primary='Report every original parent/child pair, invalid/missing endpoints, oriented child-minus-parent and actual costs. No automatic expansion or all-wins gate.',
        purpose='Check whether independently sourced natural edits provide an executable opportunity outside our repeatedly reused local parents. Not an isolated model-capacity effect.',
        adapter='Exactly original code via exec; argv contains no debug flag; workspace_input aliases existing read-only data. No algorithm, numeric setting, folds or source-seed edits.',
        budget='Equal cap/hardware per pair, not equal actual compute; source creation costs unknown. Not a same-budget search-method claim.',
        limitation='Two reused development tasks, three source parents, single source-coded training seed each. Fresh code source is not fresh test data or a replication of GOME metrics.',
        protected_opened=False, outcome_timing='Only after all assigned workers close and predictions freeze.',
        resume='Skip already closed programs; refuse to repeat any started but unclosed program. No automatic candidate repair, dependency installation, changed cap or replacement sample.'))
    runtime()
    from dojo.config_dataclasses.run import RunConfig
    signatures = {}
    for s in rows:
        c = RunConfig.load_from_json(R/'configs'/f"{s['index']}.json")
        c.validate()
        assert c.task.data_dir == c.task.public_dir and '/search-only-dev-' in c.task.data_dir
        assert not Path(c.task.private_dir).exists() and not c.interpreter.read_only_binds
        assert sha(c.task.search_only_dev_scorer_path) == c.task.search_only_dev_scorer_sha256
        raw = read(R/'configs'/f"{s['index']}.json")
        t = copy.deepcopy(raw['task']); t.pop('results_output_dir')
        it = copy.deepcopy(raw['interpreter']); it.pop('working_dir')
        sig = json.dumps([t, it], sort_keys=True)
        assert s['case'] not in signatures or signatures[s['case']] == sig
        signatures[s['case']] = sig
    subprocess.run(['bash', '-n', str(R/'run.sbatch')], check=True)
    write(R/'preflight.json', dict(status='PASS', configs=len(rows), matched_pairs=len(signatures),
        source_payload_preserved=True, no_debug_flag=True, plan_sha256=sha(R/'plan.json'),
        helper_deadline_amendment_only=True, no_new_model_acceptance=True,
        checklist='No training/split manipulation; original seeds retained; two-task denominator explicit; no role/order reselection; raw outputs stay remote; 6x1380s<9000s; old tests/dependencies reused; performance not presumed.'))
    print(json.dumps(dict(status='PREPARED', plan_sha256=sha(R/'plan.json'), programs=6, excluded_pairs=1, gpu_hours_cap=2.5)))


def submit():
    p = check()
    m = runtime()
    assert read(R/'preflight.json')['plan_sha256'] == sha(R/'plan.json')
    assert sha(m.TASK_IMAGE) == p['task_image_sha256']
    env = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    jobs = subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'], env=env, text=True, timeout=25).split()
    assert not set(jobs)-{'12535'}, 'Other jobs require resource review; do not alter them'
    with (R/'capacity.tmp').open('xb') as f:
        os.posix_fallocate(f.fileno(), 0, 64*1024**2)
    (R/'capacity.tmp').unlink()
    write(R/'submit-intent.json', dict(plan_sha256=sha(R/'plan.json')))
    q = subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),
                        '--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')], env=env, capture_output=True, text=True, timeout=25)
    job = q.stdout.strip().split(';')[0]
    assert q.returncode == 0 and job.isdigit(), 'Ambiguous submission; no retry'
    write(R/'launch.json', dict(job=job, plan_sha256=sha(R/'plan.json')))
    print(json.dumps(dict(job=job, status='SUBMITTED', gpu_hours_cap=2.5)))


def worker(index):
    x = load('external_pair_worker', R/'worker_helper.py')
    x.R = R
    x.check = check
    x.schedule = schedule
    x.runtime = runtime
    x.worker(index)


def controller():
    check()
    m = runtime()
    assert read(R/'launch.json')['job'] == os.environ['SLURM_JOB_ID']
    codes = []
    for s in schedule():
        ep = R/f"episode-{s['index']}"
        if (ep/'closed.json').exists():
            codes.append(read(ep/'closed.json')['returncode'])
            continue
        assert not (ep/'native.json').exists(), 'Started without closure: preserve unknown, do not retry'
        cmd = ['srun','--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=6','--gres=gpu:1',
               '--time=00:23:00',str(PY),'-B',str(R/NAME),'worker','--index',str(s['index'])]
        with (ep/'worker.private.log').open('xb') as f:
            q = subprocess.run(cmd, env=m.infra().clean_env(), stdout=f, stderr=f)
        write(ep/'closed.json', dict(returncode=q.returncode))
        codes.append(q.returncode)
    write(R/'closed.json', dict(returncodes=codes, assigned=len(schedule())))


def status():
    check()
    print(json.dumps(dict(launch=read(R/'launch.json') if (R/'launch.json').exists() else None,
        assigned=6, started=sum((R/f'episode-{i}/native.json').exists() for i in range(6)),
        completed=sum((R/f'episode-{i}/completed.json').exists() for i in range(6)),
        closed_workers=sum((R/f'episode-{i}/closed.json').exists() for i in range(6)),
        batch_closed=(R/'closed.json').exists())))


if __name__ == '__main__':
    os.umask(0o077)
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['tests','prepare','submit','worker','controller','status','check'])
    p.add_argument('--commit')
    p.add_argument('--index', type=int)
    a = p.parse_args()
    if a.mode == 'tests': print(json.dumps(tests()))
    elif a.mode == 'prepare': prepare(a.commit)
    elif a.mode == 'worker': worker(a.index)
    else: globals()[a.mode]()
