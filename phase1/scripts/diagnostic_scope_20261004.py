"""Paired diagnostic-object intervention; no agent benefit or hidden-score claim.

Two previously observed developer checks, two feature scopes, two RNG settings,
plus two same-seed incumbent numeric-component references. Classical fits only.
The source programs, including their non-nested text CV, remain unchanged except
for symmetric instrumentation/RNG and the one declared numeric feature scope.
"""
import argparse
import ast
import copy
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import time

B = Path('/research/d7/spc/yzyang4')
DONOR = B/'executable-evidence-20261004-v1'
ROOT = B/'diagnostic-scope-20261004-v1'
PY = B/'venvs/aira/bin/python'
PUBLIC = B/'search-only-dev-pizza-20260927-v1/public'
BASE_COMMIT = '18c2f58352046c2569e765fb1c8fe1f2db27e4a0'
DONOR_PLAN = 'f5aba6d06b20a1c4037abc52c373842bae70f6672d3a2ac7b20c8bb3fc82dd3c'
RUNTIME_SHA = '4b155d927c12f063e0838b5708085fe1bc55c4983197a3d8d2453696d73c55ad'
INFRA = B/'repair-replace-dev-20260927-v1/tests/fresh_first_slot_gpu27_20260927.py'
INFRA_SHA = 'daf6b0e80db3577aa5f3219a47e166171958672cae00249248251bf78fd51857'
SOURCES = {
    'component_check': (0, 1, '3cc81fc7232144bdd910920f26ff0de1f346c95c021de9792d260f50e4c65a58'),
    'underfit_check': (14, 2, 'ed0f17639163e820eb8522935457b141afb529689c2224193ca49ce239517de3'),
    'reference': (0, 0, '6e349a6c509145cb25be96f33324f762c51d553051378ac512c3ec0f91648d1c'),
}
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+\S{15,})')


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def safe_read(p):
    raw = Path(p).read_bytes()
    assert not SECRET.search(raw), 'credential shape: output withheld'
    return json.loads(raw)


def write(p, value):
    with Path(p).open('x') as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def schedule():
    rng = random.Random(106501)
    pairs = [(case, seed) for seed in (42, 173) for case in ('component_check', 'underfit_check')]
    rng.shuffle(pairs)
    rows = []
    for case, seed in pairs:
        arms = ['all_numeric', 'deployment_scope']
        rng.shuffle(arms)
        for arm in arms:
            rows.append(dict(index=len(rows), case=case, seed=seed, arm=arm))
    for seed in (42, 173):
        rows.append(dict(index=len(rows), case='reference', seed=seed, arm='deployment_scope'))
    return rows


class SeedSetter(ast.NodeTransformer):
    def __init__(self, seed):
        self.seed = seed

    def visit_keyword(self, node):
        if node.arg == 'random_state' and isinstance(node.value, ast.Constant) and node.value.value == 42:
            node.value = ast.Constant(self.seed)
        return self.generic_visit(node)

    def visit_Dict(self, node):
        for i, key in enumerate(node.keys):
            if isinstance(key, ast.Constant) and key.value == 'random_state':
                assert isinstance(node.values[i], ast.Constant) and node.values[i].value == 42
                node.values[i] = ast.Constant(self.seed)
        return self.generic_visit(node)

    def visit_Call(self, node):
        if ast.unparse(node.func) in ('random.seed', 'np.random.seed') and len(node.args) == 1:
            assert isinstance(node.args[0], ast.Constant) and node.args[0].value == 42
            node.args[0] = ast.Constant(self.seed)
        return self.generic_visit(node)


def target_name(node):
    return node.targets[0].id if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) else None


def reference_component(code):
    """Actual parent prefix/params/first component loop; no regenerated recipe."""
    tree = ast.parse(code)
    cutoff = next(i for i, n in enumerate(tree.body) if target_name(n) == 'tfidf')
    prefix = tree.body[:cutoff]
    names = {'n_splits', 'skf', 'oof_lgb', 'test_lgb', 'lgb_params'}
    selected = [n for n in tree.body if target_name(n) in names]
    assert {target_name(n) for n in selected} == names
    loop = next(n for n in tree.body if isinstance(n, ast.For) and 'skf.split(X_train, y_train)' in ast.unparse(n.iter))
    stop = next(i for i, n in enumerate(loop.body) if target_name(n) == 'xgb_model')
    loop = copy.deepcopy(loop)
    loop.body = loop.body[:stop]
    return ast.unparse(ast.Module(body=prefix + selected + [loop], type_ignores=[]))


def program(case, seed, scope):
    episode, step, expected = SOURCES[case]
    source = DONOR/f'episode-{episode}/action-{step}/node.private.json'
    assert digest(source) == expected
    code = safe_read(source)['code']
    if case == 'reference':
        code = reference_component(code)
    tree = SeedSetter(seed).visit(ast.parse(code))
    ast.fix_missing_locations(tree)
    code = ast.unparse(tree)
    prefix = f'import random, numpy as np\nrandom.seed({seed})\nnp.random.seed({seed})\n'
    prefix += '_scope_text_oof = {}\n_scope_folds = []\n'
    if case != 'reference':
        parsed = ast.parse(code)
        assignments = [n for n in parsed.body if target_name(n) == 'num_cols']
        assert len(assignments) == 1
        anchor = ast.get_source_segment(code, assignments[0])
        engineer = 'eng' if case == 'component_check' else 'engineer_features'
        injection = "\nwith open('./data/test.json') as _scope_handle:\n    _scope_query = pd.DataFrame(json.load(_scope_handle))\n"
        injection += f'_scope_query = {engineer}(_scope_query)\n'
        injection += '_scope_query_numeric = list(_scope_query.select_dtypes(include=[np.number]).columns)\n'
        injection += '_scope_original_columns = list(num_cols)\n'
        # Same work in both arms; only this literal changes the selected columns.
        injection += f'_scope_filter = {scope == "deployment_scope"!r}\n'
        injection += 'if _scope_filter:\n    num_cols = [c for c in num_cols if c in _scope_query_numeric]\n'
        assert code.count(anchor) == 1
        code = code.replace(anchor, anchor + injection)
        if case == 'underfit_check':
            needle = 'return roc_auc_score(y, oof)'
            assert code.count(needle) == 1
            code = code.replace(needle, "_scope_text_oof[str((maxf, ngram))] = oof.copy()\n    " + needle)
    # All programs save public-training OOF only. No D_search labels or scores.
    if case == 'component_check':
        arrays = "dict(y=y_train, numeric=oof_lgb, text_lr=oof_lr, text_lgb=oof_lgb_txt)"
        cols, yname, xname = 'num_cols', 'y_train', 'X_train'
    elif case == 'underfit_check':
        arrays = "dict(y=y, numeric=oof_lgb, **{'text_'+str(i): v for i,v in enumerate(_scope_text_oof.values())})"
        cols, yname, xname = 'num_cols', 'y', 'X'
    else:
        arrays = 'dict(y=y_train, numeric=oof_lgb)'
        cols, yname, xname = 'all_numeric_cols', 'y_train', 'X_train'
    footer = f'''
import hashlib as _scope_hashlib, platform as _scope_platform, sklearn as _scope_sklearn
_scope_arrays = {arrays}
_scope_fold_rows = [(tr, va) for tr, va in skf.split({xname}, {yname})]
np.savez_compressed('diagnostic_oof.npz', **_scope_arrays)
_scope_meta = dict(case={case!r}, seed={seed}, arm={scope!r},
    columns=list({cols}), rows=len({yname}),
    scores={{k:float(roc_auc_score({yname}, v)) for k,v in _scope_arrays.items() if k!='y'}},
    array_hashes={{k:_scope_hashlib.sha256(np.ascontiguousarray(v).tobytes()).hexdigest() for k,v in _scope_arrays.items()}},
    fold_hashes=[_scope_hashlib.sha256(np.asarray(va,dtype=np.int64).tobytes()).hexdigest() for tr,va in _scope_fold_rows],
    versions=dict(python=_scope_platform.python_version(), numpy=np.__version__, pandas=pd.__version__, lightgbm=lgb.__version__, sklearn=_scope_sklearn.__version__))
with open('diagnostic_meta.json','x') as _scope_f:
    json.dump(_scope_meta,_scope_f,sort_keys=True)
print('DIAGNOSTIC_SCOPE_EXECUTION_DONE')
'''
    result = prefix + code + '\n' + footer
    ast.parse(result)
    assert not SECRET.search(result.encode())
    return result


def runtime():
    assert digest(ROOT/'v6_runtime.py') == RUNTIME_SHA and digest(INFRA) == INFRA_SHA
    spec = importlib.util.spec_from_file_location('scope_runtime', ROOT/'v6_runtime.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    mod.ROOT = ROOT
    mod.infra.ROOT = ROOT
    mod.setup()
    return mod


def check():
    p = safe_read(ROOT/'plan.json')
    assert p['schedule'] == schedule()
    for name, expected in p['files'].items():
        assert digest(ROOT/name) == expected, name
    for name, expected in p['public_data'].items():
        assert digest(PUBLIC/name) == expected, name
    return p


def prepare():
    assert not ROOT.exists() and digest(DONOR/'plan.json') == DONOR_PLAN
    assert safe_read(DONOR/'closed.json')['service_closed'] is True
    ROOT.mkdir(mode=0o700)
    for rel, expected in safe_read(DONOR/'plan.json')['files'].items():
        if not (rel.startswith(('source/', 'forets_', 'opencl-vendors/')) or rel == 'v6_runtime.py'):
            continue
        assert digest(DONOR/rel) == expected
        dest = ROOT/rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DONOR/rel, dest)
    shutil.copyfile(__file__, ROOT/Path(__file__).name)
    for name in ('programs', 'configs', 'bin'):
        (ROOT/name).mkdir()
    launcher = f'#!{PY}\nimport sys\nsys.path.insert(0,{str(ROOT)!r})\nfrom diagnostic_scope_20261004 import runtime\nruntime().task_runtime()\n'
    (ROOT/'bin/singularity').write_text(launcher)
    os.chmod(ROOT/'bin/singularity', 0o700)
    for row in schedule():
        i = row['index']
        (ROOT/f'episode-{i}').mkdir()
        (ROOT/'programs'/f'{i}.private.py').write_text(program(row['case'], row['seed'], row['arm']))
        cfg = safe_read(DONOR/'configs/0.json')
        cfg['id'] = f'diagnostic-scope-{i}'
        cfg['logger'].update(output_dir=str(ROOT/f'episode-{i}/native-log'), write_env_vars=False, use_wandb=False, use_console=False, print_config=False)
        cfg['metadata'].update(seed=row['seed'], base_path=str(ROOT/'source'), git_commit_id=BASE_COMMIT, script_id='diagnostic-scope-20261004')
        cfg['interpreter'].update(timeout=300, working_dir=str(ROOT/f'episode-{i}/unused-work'))
        cfg['interpreter']['env'].update(PYTHONHASHSEED=str(row['seed']), OMP_NUM_THREADS='6', OPENBLAS_NUM_THREADS='6', MKL_NUM_THREADS='6', NUMEXPR_NUM_THREADS='6')
        cfg['task']['cache_dir'] = str(ROOT/'no-official-data')
        write(ROOT/'configs'/f'{i}.json', cfg)
    batch = f'''#!/bin/bash
#SBATCH --job-name=diagnostic-scope
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu3
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --time=01:30:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 5340s {PY} -B {ROOT}/diagnostic_scope_20261004.py controller
'''
    (ROOT/'run.sbatch').write_text(batch)
    write(ROOT/'plan.json', dict(protocol='diagnostic-scope-counterfactual-v1', utc=utc(), base_commit=BASE_COMMIT,
        source_sha256=digest(ROOT/Path(__file__).name), donor_plan_sha256=DONOR_PLAN, sources=SOURCES,
        schedule=schedule(), executions=10, gpu_hours_cap=1.5, allocation_seconds=5400, gpus=1, code_seconds=300,
        public_data={n:digest(PUBLIC/n) for n in ('train.json', 'test.json')},
        files={str(p.relative_to(ROOT)):digest(p) for p in ROOT.rglob('*') if p.is_file()},
        primary='Within source-check and seed, numeric OOF AUC all_numeric minus deployment_scope. Verify identical folds, labels, text predictions, dependencies, and source code except declared scope. Report all4 paired contrasts and failures.',
        secondary='Both checks versus same-seed actual parent numeric component; numeric-versus-text ranking. Underfit-check sign relative to actual same-seed reference. Do not infer a changed LLM decision without a new continuation intervention.',
        reference='Exact AST prefix, params, CV and numeric-component loop from observed incumbent. Remove unrelated XGB/text/stack fits. Public OOF seed42 rounded reference 0.677345 is a predeclared descriptive reproduction check, not grounds to replace failed data.',
        gate='No agent expansion authorized by this check. Material distortion candidate: all4 pairs complete, every numeric AUC inflation >=0.01, non-target controls exact; report whether either recommendation sign reverses. Failure or no reversal remains informative; no new seeds or threshold changes.',
        limits='Two post-outcome selected checks on one previously reused developer task; same physical source, not independent tasks. Text vocabulary fitted before CV is retained symmetrically and not called unbiased validation. CV outcomes are diagnostic, not deployment utility or novel method gains. Reference extracted component, not full pipeline rerun.',
        fairness='One numeric-field scope switch within each paired check; all other code identical after symmetric instrumentation and explicit RNG changes. Reference is not a third experimental method. Same task image/native isolation/CPU allocation. All classical models use original CPU algorithms; no GPU-to-CPU fallback.',
        stopping='One10-execution batch; no post-outcome resubmission or prompt/seed sweep. Missing outputs null. Save all failures; frozen raw receipts immutable. Classical-fit checkpoint is per completed execution. Resume only same source/seed/code and no repeat completed slots.',
        budget_basis='10 sequential worker slots <=480s plus <=540s overhead inside90min, one allocated3090. Includes interpreter startup, idle GPU allocation and failures. No service, generator, paid API or base-model update.',
        preflight='13-item checklist adapted: actual AST scope diff, CPU path tests, public-only input binding, all4 pairs/task denominator, randomized fixed pair order, OOF artifacts saved, input hashes/isolation, explicit seeds, secret scan, wall cap, small mechanism not powered generalization, returncodes preserved, frozen roster.',
        paid_api=0, generator_calls=0, base_updates=0, dsearch_read=False, protected_opened=False))
    cpu()


def cpu():
    p = check()
    m = runtime()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    for row in schedule():
        cfg = RunConfig.load_from_json(ROOT/'configs'/f'{row["index"]}.json')
        cfg.validate()
        task = MLEBenchTask(cfg.task)
        assert task._search_only_score and not task.private_dir.exists()
        assert Path(cfg.task.data_dir) == PUBLIC and Path(cfg.task.public_dir) == PUBLIC
        interpreter = build(cfg.interpreter, INTERPRETER_MAP, data_dir=cfg.task.data_dir)
        assert interpreter.factory
        code = (ROOT/'programs'/f'{row["index"]}.private.py').read_text()
        ast.parse(code)
        assert 'diagnostic_oof.npz' in code and 'submission.to_csv' not in code
    for case in ('component_check', 'underfit_check'):
        for seed in (42, 173):
            left = program(case, seed, 'all_numeric').replace("arm='all_numeric'", "arm='SCOPE'").replace('_scope_filter = False', '_scope_filter = FLAG')
            right = program(case, seed, 'deployment_scope').replace("arm='deployment_scope'", "arm='SCOPE'").replace('_scope_filter = True', '_scope_filter = FLAG')
            assert left == right, 'undeclared paired difference'
    fixture = {'train': ['a', 'b', 'after_event'], 'query': ['b', 'a']}
    assert [c for c in fixture['train'] if c in fixture['query']] == ['a', 'b']
    assert [c for c in fixture['train'] if c in fixture['train']] == fixture['train']
    subprocess.run(['bash', '-n', str(ROOT/'run.sbatch')], check=True)
    write(ROOT/'cpu.json', dict(status='PASS', configs=10, paired_source_checks=4, schema_fixtures=2, plan_sha256=digest(ROOT/'plan.json')))
    print(json.dumps(dict(status='PREPARED_CPU_PASS', plan_sha256=digest(ROOT/'plan.json'), executions=10, gpu_hours_cap=1.5)))


def submit():
    p = check()
    assert not (ROOT/'submit-intent.json').exists()
    assert safe_read(ROOT/'cpu.json')['plan_sha256'] == digest(ROOT/'plan.json')
    assert (ROOT/'analysis-freeze.json').is_file()
    m = runtime()
    assert digest(m.infra.TASK_IMAGE) == m.infra.IMAGE_SHA
    env = m.infra.clean_env()
    jobs = subprocess.check_output(['squeue', '-u', 'yzyang4', '-h', '-o', '%i'], env=env, text=True, timeout=25).split()
    assert not set(jobs)-{'12535'}
    write(ROOT/'submit-intent.json', dict(utc=utc(), plan_sha256=digest(ROOT/'plan.json')))
    result = subprocess.run(['sbatch', '--parsable', '--chdir='+str(ROOT), '--output='+str(ROOT/'allocation-%j.out'), '--error='+str(ROOT/'allocation-%j.err'), str(ROOT/'run.sbatch')], env=env, capture_output=True, text=True, timeout=25)
    job = result.stdout.strip().split(';')[0]
    assert result.returncode == 0 and job.isdigit(), 'ambiguous submission: do not retry'
    write(ROOT/'launch.json', dict(job=job, utc=utc(), plan_sha256=digest(ROOT/'plan.json')))
    print(json.dumps(dict(status='SUBMITTED', job=job, gpu_hours_cap=p['gpu_hours_cap'])))


def worker(index):
    p = check()
    row = p['schedule'][index]
    ep = ROOT/f'episode-{index}'
    assert not (ep/'completed.json').exists() and not (ep/'native.json').exists()
    m = runtime()
    own = m.infra.native_uuids(1)
    os.environ.update(DOJO_GPU_UUIDS=own[0], DOJO_WORKER_IDENTITY_PATH=str(ep/'identity.json'),
        DOJO_EXECUTION_ID=f'{os.environ["SLURM_JOB_ID"]}.{os.environ["SLURM_STEP_ID"]}:{index}', PATH=str(ROOT/'bin')+':'+os.environ['PATH'])
    from dojo.main_local_worker import _process_start_ticks, _host_boot_id
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    from dojo.utils.logger import config_logger
    from dojo.utils.experiment_deadline import ExperimentDeadline
    write(ep/'identity.json', dict(pid=os.getpid(), pgid=os.getpgid(0), process_start_ticks=_process_start_ticks(os.getpid()), host_boot_id=_host_boot_id(), gpu_uuids=own, container_pid=None, container_process_start_ticks=None))
    write(ep/'native.json', dict(job=os.environ['SLURM_JOB_ID'], step=os.environ['SLURM_STEP_ID'], gpu_uuids=own, config_sha256=digest(ROOT/'configs'/f'{index}.json')))
    cfg = RunConfig.load_from_json(ROOT/'configs'/f'{index}.json')
    Path(cfg.logger.output_dir).mkdir()
    config_logger(cfg)
    action = ep/'action-0'
    (action/'work').mkdir(parents=True)
    os.environ['FEEDBACK_ACTION_ROOT'] = str(action)
    icfg = copy.deepcopy(cfg.interpreter)
    icfg.working_dir = str(action/'work')
    icfg.timeout = 300
    code = (ROOT/'programs'/f'{index}.private.py').read_text()
    executable = f'exec(compile({code!r},"diagnostic_program.py","exec"),{{"__name__":"__main__"}})\n'
    began = time.monotonic()
    out = None
    interp = None
    complete = False
    error_type = None
    with ExperimentDeadline(420).activate():
        try:
            interp = build(icfg, INTERPRETER_MAP, data_dir=cfg.task.data_dir)
            out = interp.run(executable, reset_session=False)
            terminal = '\n'.join(out.term_out or [])
            assert not SECRET.search(terminal.encode()), 'credential shape'
            write(action/'terminal.private.json', dict(terminal=terminal))
            if out.exit_code == 0 and not out.timed_out:
                for name in ('diagnostic_oof.npz', 'diagnostic_meta.json'):
                    path = action/'work'/name
                    interp.fetch_file(path)
                    assert path.is_file() and not path.is_symlink()
                    shutil.copyfile(path, action/name)
                complete = True
        except Exception as exc:
            error_type = type(exc).__name__
            message = str(exc)
            write(action/'error.private.json', dict(type=error_type, message='withheld' if SECRET.search(message.encode()) else message))
        finally:
            if interp is not None:
                interp.close()
    write(action/'result.json', dict(**row, complete=complete, seconds=time.monotonic()-began,
        exit_code=out.exit_code if out is not None else None, timed_out=out.timed_out if out is not None else None,
        error_type=error_type, plan_sha256=digest(ROOT/'plan.json'), code_sha256=digest(ROOT/'programs'/f'{index}.private.py'),
        artifacts={n:digest(action/n) for n in ('diagnostic_oof.npz', 'diagnostic_meta.json') if (action/n).is_file()}))
    write(ep/'completed.json', dict(status='COMPLETE', diagnostic_complete=complete))


def controller():
    p = check()
    assert safe_read(ROOT/'launch.json')['job'] == os.environ['SLURM_JOB_ID']
    m = runtime()
    rows = []
    for row in p['schedule']:
        index = row['index']
        ep = ROOT/f'episode-{index}'
        cmd = ['srun', '--exclusive', '--nodes=1', '--ntasks=1', '--cpus-per-task=6', '--gres=gpu:1', '--time=00:08:00', str(PY), '-B', str(ROOT/'diagnostic_scope_20261004.py'), 'worker', '--index', str(index)]
        if (ep/'closed.json').exists():
            old = safe_read(ep/'closed.json')
            assert old['returncode'] == 0 and (ep/'completed.json').is_file(), 'incomplete prior slot: no automatic rerun'
            rows.append(old)
            continue
        with (ep/'worker.private.log').open('xb') as f:
            try:
                result = subprocess.run(cmd, env=m.infra.clean_env(), stdout=f, stderr=f, timeout=500)
                receipt = dict(index=index, returncode=result.returncode, supervisor_timeout=False)
            except subprocess.TimeoutExpired:
                receipt = dict(index=index, returncode=None, supervisor_timeout=True)
        write(ep/'closed.json', receipt)
        rows.append(receipt)
        print(json.dumps(dict(index=index, closed=True, **{k:receipt[k] for k in ('returncode', 'supervisor_timeout')})), flush=True)
        if receipt['returncode'] != 0:
            write(ROOT/'controller-failure.json', dict(utc=utc(), failed_index=index, remaining_unstarted=[s['index'] for s in p['schedule'] if s['index']>index]))
            raise RuntimeError('worker infrastructure failure; preserve unstarted slots')
    write(ROOT/'closed.json', dict(utc=utc(), plan_sha256=digest(ROOT/'plan.json'), slots=rows))


def status():
    p = check()
    print(json.dumps(dict(launch=safe_read(ROOT/'launch.json') if (ROOT/'launch.json').exists() else None,
        closed=(ROOT/'closed.json').exists(), controller_failure=(ROOT/'controller-failure.json').exists(),
        slots=[dict(index=s['index'], started=(ROOT/f'episode-{s["index"]}/native.json').exists(), complete=(ROOT/f'episode-{s["index"]}/completed.json').exists()) for s in p['schedule']])))


if __name__ == '__main__':
    os.umask(0o077)
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['prepare', 'cpu', 'submit', 'controller', 'worker', 'status'])
    ap.add_argument('--index', type=int)
    args = ap.parse_args()
    worker(args.index) if args.mode == 'worker' else globals()[args.mode]()
