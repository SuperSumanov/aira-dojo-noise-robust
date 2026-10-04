"""One conditional information trial, not an autonomous correction method.

No old experiment is resumed. The only arm change is an auxiliary public-CV
observation packet. Acquisition/correction are historical human-assisted costs.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import secrets
import shutil
import subprocess
import sys

B = Path('/research/d7/spc/yzyang4')
P = B/'opportunity-information-20261003-v2'
R = B/'diagnostic-information-20261004-v1'
S = B/'diagnostic-scope-20261004-v1'
T = B/'diagnostic-text-scope-20261004-v1'
COMMIT = '3d655b1c68f956414a7e3f21d819820431104019'
DONOR_SHA = 'c8d67b9cce9109425324f5877797ad0448ec5f97beb89572383dce3fa1697448'
PLAN_P = '6b91aba97ee53f6da2335064f1dbe4277020b8744fd95a3575e4c99329936d2f'
SUMMARIES = {
    S: '21a870197f192f32dac7d398f2bbfc18b3740303efe6252ec6d9d3f2be07bdfd',
    T: '364c63f0bc5214c54c50ace4dcb2324bd4d0eb0b26a4d3f1d13f098c43a5c507'}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8*1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


assert sha(P/'task_feedback_real_20261001.py') == DONOR_SHA
spec = importlib.util.spec_from_file_location('frozen_information_base', P/'task_feedback_real_20261001.py')
x = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = x
spec.loader.exec_module(x)
d, m = x.d, x.m
d.ROOT = R
m.ROOT = R
m.PORT, m.CAP, m.SECONDS, m.COMMIT = 19463, 5400, 600, COMMIT
m.infra.ROOT, m.infra.SERVICE_PORT = R, m.PORT
m.sha = sha
TASKS = x.TASKS
decode = x.decode


def schedule():
    order = list('ABC')
    random.Random(107000).shuffle(order)
    rows = []
    for block in range(2):
        for arm in order if block == 0 else order[::-1]:
            for k, task in enumerate(TASKS):
                rows.append(dict(index=len(rows), start=k, source_state=(4, 0)[k],
                                 task=task, arm=arm, seed=107101+10*block+k,
                                 wave=len(rows)//2, retained=True, visible=True))
    return rows


m.schedule = schedule
d.schedule = schedule
COMMON = '''Improve this working natural ML program in a persistent coding workspace.
Every condition has the same parent, public data, tools, model and task image.
Choose useful next work freely: inspect, test, modify, reuse or fit. No required
diagnostic phase or particular modification. Ordinary references available to
all include compatible schema, word/character TFIDF, regularized linear models,
numerical boosting, public-CV selection, early stopping and blending. None is a
guaranteed improvement. Verify relevance rather than treating a high CV as proof.
FOUR model calls and 600 TOTAL seconds include initial execution, generation,
checks, fitting, errors, reconstruction and grading. Each code execution is at
most 300 seconds within the remaining budget. One RTX3090 and six CPU cores.
Write one standalone CHECK or SOLUTION line, a short rationale and exactly one
fenced python block. No PLAN or native tool-call XML. CHECK executes without
grading. SOLUTION writes a new submission.csv. The final call must be SOLUTION.
Successful cells and their variables remain live. submission.csv is deliberately
cleared before each cell; this does NOT mean successful fitted objects vanished.
The external evaluator separately retains the best valid submission. A failed
cell rolls back to the successful code ledger; reconstruction consumes budget.
The parent is /workspace/parent.py. Use only /workspace/data and the workspace;
no downloads or hidden labels. External scores are reused DEVELOPMENT scores,
not final test. Lower log-loss and higher AUC are better. Public-CV diagnostic
numbers are not external scores. Auxiliary reports, when supplied, were executed
in an isolated workspace: their variables/models are NOT live objects here.
No report prescribes a modification or proves final predictive benefit.
'''


def advice(s):
    if s['arm'] == 'A':
        return 'No auxiliary diagnostic report supplied. Parent code, live successful state, public data and all tools remain available.'
    return (R/'advice'/f"{s['start']}.{s['arm']}.private.txt").read_text()


def prompt(task, s, step, ledger, history, remaining):
    return (COMMON+f'\nCURRENT MODEL CALL: {step} of 4.\n'+advice(s)+'\n'
            + ('Final call: SOLUTION.' if step == 4 else 'Choose the useful next CHECK or SOLUTION.')
            + '\nTASK:\n'+task+'\nSUCCESSFUL CODE LEDGER:\n'
            + '\n\n'.join(f'CELL {i}:\n{c}' for i, c in enumerate(ledger))
            + '\nOBSERVED HISTORY:\n'+history+f'\nTOTAL SECONDS REMAINING: {int(remaining)}\n')


d.prompt = prompt


def wrapper(code, seed, remove_submission=True):
    return ('import random as _r, numpy as _n\n_r.seed(42)\n_n.random.seed(42)\n'
            + ("from pathlib import Path as _P\n_P('submission.csv').unlink(missing_ok=True)\n" if remove_submission else '')
            + f'globals()["__name__"]="__main__"\nexec(compile({code!r},"cell.py","exec"))\n')


d.wrapper = wrapper


def adapt(source, name, changes):
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    code = ast.get_source_segment(source, node)
    for before, after in changes:
        assert code.count(before) == 1, (name, before)
        code = code.replace(before, after)
    ast.parse(code)
    exec(compile(code, 'diagnostic_information_'+name, 'exec'), m.__dict__)


runtime_source = Path(m.__file__).read_text()
adapt(runtime_source, 'worker', [("TIME_LIMIT='30 minutes'", "TIME_LIMIT='10 minutes'")])
adapt(runtime_source, 'service', [("!='gpu28'", "!='gpu3'")])
adapt(runtime_source, 'controller', [
    ("!='gpu28'", "!='gpu3'"), ('03:39:00', '01:29:00'),
    ('00:33:00', '00:13:00'), ('max_workers=3', 'max_workers=2'),
    ('dict(attempts=18,', 'dict(attempts=12,'),
    ('        try:\n            while time.monotonic()-began<900:',
     "        try:\n            subprocess.run(base+['--cpus-per-task=6','--gres=gpu:1','--time=00:02:00',str(PY),'-B',str(ROOT/'task_feedback_real_20261001.py'),'compat'],env=env,check=True,timeout=120)\n            while time.monotonic()-began<900:")])


def compatibility():
    path = B/'automatic_specification_v6_20261003.py'
    assert sha(path) == '1c5c7551d43392ab5d8c442d56e0dbc6fadbadababb463b35e0ca0dd795813f0'
    tree = ast.parse(path.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'compatibility')
    namespace = dict(globals())
    exec(compile(ast.get_source_segment(path.read_text(), node), 'compat', 'exec'), namespace)
    namespace['compatibility']()


def make_reports():
    records = []
    for root, expected in SUMMARIES.items():
        assert sha(root/'readout-v1/summary.json') == expected
        assert m.read(root/'readout-v1/summary.json')['complete'] == (10 if root == S else 6)
    for start, root in enumerate((S, T)):
        plan = m.read(root/'plan.json')
        summary = m.read(root/'readout-v1/summary.json')
        pair = next(p for p in summary['pairs'] if p['seed'] == 42 and (start == 1 or p['case'] == 'underfit_check'))
        for arm, scope in zip('BC', ('all_numeric', 'deployment_scope') if start == 0 else ('all_public', 'fold_train')):
            slot = next(p for p in plan['schedule'] if p['seed'] == 42 and p['arm'] == scope and p['case'] == ('underfit_check' if start == 0 else 'diagnostic'))
            code_path = root/'programs'/f"{slot['index']}.private.py"
            assert sha(code_path) == plan['files'][str(code_path.relative_to(root))]
            ep = root/f"episode-{slot['index']}/action-0"
            meta_path = ep/'diagnostic_meta.json'
            result_path = ep/'result.json'
            result = m.read(result_path)
            assert sha(meta_path) == result['artifacts']['diagnostic_meta.json']
            meta = m.read(meta_path)
            assert meta['seed'] == 42 and meta['arm'] == scope
            code = code_path.read_text()
            assert not m.SECRET.search(code.encode())
            nodes = ast.parse(code).body
            alias = '_scope_hashlib' if start == 0 else '_h'
            boundaries = [i for i, n in enumerate(nodes) if isinstance(n, ast.Import) and any(a.name == 'hashlib' and a.asname == alias for a in n.names)]
            assert len(boundaries) == 1
            shown = ast.unparse(ast.Module(body=nodes[:boundaries[0]], type_ignores=[]))
            if start == 0:
                numbers = dict(metric='public five-fold OOF AUC', diagnostic_scores=meta['scores'],
                               original_numeric_component_auc=pair['reference_auc'],
                               numeric_features=len(meta['columns']), numeric_columns=meta['columns'],
                               scope=scope, cv_and_model_seed=42)
                assert abs(meta['scores']['numeric']-pair['all_auc' if arm == 'B' else 'deployment_auc']) < 1e-12
                limitation = 'The reference is only the original numeric component, NOT its full stacked pipeline. Text-vectorizer fitting follows the shown source; this report is not guaranteed unbiased validation.'
            else:
                numbers = dict(metric='public first-fold logloss', diagnostic_lgb_loss=meta['log_loss'],
                               original_combined_lr_loss=pair['reference_loss'], features=meta['features'],
                               vocabulary_fit=scope, split_seed=42)
                assert abs(meta['log_loss']-pair['all_loss' if arm == 'B' else 'fold_loss']) < 1e-12
                limitation = 'Only the first public fold was measured. The reference is combined-representation LR, NOT the full three-member parent blend.'
            packet = ('AUXILIARY PUBLIC-CV OBSERVATION\n'+limitation+'\n'
                      + json.dumps(numbers, sort_keys=True)+'\n'
                      + 'Executed diagnostic computation (output serialization omitted; read-only evidence, not live state):\n'
                      + shown+'\nEND AUXILIARY OBSERVATION\n')
            assert not m.SECRET.search(packet.encode())
            dest = R/'advice'/f'{start}.{arm}.private.txt'
            with dest.open('x') as f:
                f.write(packet)
            records.append(dict(start=start, arm=arm, scope=scope, seed=42, source_plan_sha256=sha(root/'plan.json'),
                                source_summary_sha256=SUMMARIES[root], executed_source_sha256=sha(code_path),
                                source_meta_sha256=sha(meta_path), shown_computation_sha256=hashlib.sha256(shown.encode()).hexdigest(),
                                packet_sha256=sha(dest), packet_characters=len(packet)))
    return records


def prepare():
    assert not R.exists() and sha(P/'plan.json') == PLAN_P
    R.mkdir(mode=0o700)
    old = m.read(P/'plan.json')
    for rel, expected in old['files'].items():
        if not (rel.startswith(('source/', 'forets_', 'opencl-vendors/')) or rel in ('v6_runtime.py', 'root_trial_step_supervisor_20260927.py', 'factorial_engine.py')):
            continue
        assert sha(P/rel) == expected
        dest = R/rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(P/rel, dest)
    identity = R/'forets_native_cuda_identity_20260911.py'
    raw = identity.read_text()
    assert raw.count("!='gpu28'") == 1
    identity.write_text(raw.replace("!='gpu28'", "!='gpu3'"))
    shutil.copyfile(__file__, R/'task_feedback_real_20261001.py')
    for name in ('configs', 'starts', 'advice', 'bin', 'service-cache/tmp'):
        (R/name).mkdir(parents=True, exist_ok=True)
    for k in (0, 1):
        shutil.copyfile(P/'starts'/f'{k}.private.json', R/'starts'/f'{k}.private.json')
        assert hashlib.sha256(m.read(R/'starts'/f'{k}.private.json')['code'].encode()).hexdigest() == old['starts'][k]['code_sha256']
    reports = make_reports()
    entry = (P/'service_entry.py').read_text()
    assert entry.count("'19453'") == 1
    (R/'service_entry.py').write_text(entry.replace("'19453'", "'19463'"))
    with (R/'.service.env').open('x') as f:
        f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    os.chmod(R/'.service.env', 0o600)
    (R/'bin/singularity').write_text(f'#!{m.PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom task_feedback_real_20261001 import m\nm.task_runtime()\n')
    os.chmod(R/'bin/singularity', 0o700)
    for s in schedule():
        cfg = m.read(P/'configs'/f"{s['start']}.json")
        assert cfg['task']['name'] == s['task']
        ep = R/f"episode-{s['index']}"
        ep.mkdir()
        cfg['id'] = f"diagnostic-information-{s['index']}"
        cfg['logger'].update(output_dir=str(ep/'native-log'), write_env_vars=False, use_wandb=False, print_config=False, use_console=False)
        cfg['metadata'].update(seed=s['seed'], script_id='diagnostic-information-20261004', base_path=str(R/'source'), git_commit_id=COMMIT)
        cfg['solver'].update(time_limit_secs=600, step_limit=5, checkpoint_path=str(ep/'unused-checkpoint'))
        cfg['interpreter'].update(timeout=300, working_dir=str(ep/'unused-work'))
        cfg['task']['cache_dir'] = str(R/'no-official-data')
        for op in cfg['solver']['operators'].values():
            op['llm']['client']['base_url'] = 'http://127.0.0.1:19463/v1'
            op['llm']['generation_kwargs']['seed'] = s['seed']
        m.write(R/'configs'/f"{s['index']}.json", cfg)
    batch = (P/'run.sbatch').read_text().replace(str(P), str(R)).replace('opportunity-information', 'diagnostic-information').replace('--nodelist=gpu28', '--nodelist=gpu3')
    (R/'run.sbatch').write_text(batch)
    m.write(R/'plan.json', dict(protocol='diagnostic-information-intervention-v1', base_commit=COMMIT, utc=m.utc(),
        schedule=schedule(), starts=old['starts'], reports=reports, donor_sha256=DONOR_SHA,
        files={str(p.relative_to(R)): sha(p) for p in R.rglob('*') if p.is_file() and p.name != '.service.env'},
        runs=12, run_seconds=600, max_calls=4, max_tokens=4096, code_seconds=300, allocation_seconds=5400, gpus=4, gpu_hours_cap=6,
        primary='C-A primary; C-B and B-A secondary, all12 trajectories and all failures. Task-specific paired differences, median and sample variance. Same initial prediction bytes within each triple required.',
        gate='Each of two tasks: two comparable triples, median C-A and C-B >=0.002, no negative paired differences for these contrasts, and at least one improved valid C candidate. Exploratory only; no automatic expansion.',
        information='A no auxiliary report; B actual unaligned-scope public-CV report; C scope-aligned public-CV report. Same neutral packet format and diagnostic recipe within B/C, differing scope/source computation and measured numbers. Reports are human-constructed from independently verified replays, not an automatic method. A-versus-report contrasts include information amount and attention.',
        selection='Same reused development parents Pizza4/Spooky0; reports fixed to previous seed42 underfit/text diagnosis after their outcomes were known. Two generation seeds per task, not independent tasks or new physical sources. No untouched confirmation or original-agent counterfactual-state claim.',
        cost='New initial execution, generation, checks, fits, failures, reconstruction, grading, service startup and idle allocation counted. Prior parent qualification and human diagnostic discovery/correction are disclosed sunk costs, not free deployed information. Only equal continuation budget, not complete automatic-method cost parity.',
        fairness='Only auxiliary observation changes. Same parent live state, model, task image, tools, worker hardware, initial RNG42 wrapper, parser, deadline, retention and public/search data. All arms receive current-call and submission-lifecycle clarification. No comparisons with historic batches as causal controls.',
        stopping='One12-run batch; no replacement parents, seeds, prompt rescue or API substitution. Outcome values read only after allocation/episodes close. Failure remains in denominator. No new task/policy/critic training.',
        protected_opened=False, paid_api=0, base_updates=0))
    cpu()
    print(json.dumps(dict(status='PREPARED_NOT_SUBMITTED', plan_sha256=sha(R/'plan.json'), runs=12, gpu_hours_cap=6, report_count=len(reports))))


def cpu():
    m.check()
    m.setup()
    os.environ['PRIMARY_KEY_QWEN3_8_27B'] = 'synthetic-test-only'
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    for s in schedule():
        cfg = RunConfig.load_from_json(R/'configs'/f"{s['index']}.json")
        cfg.validate()
        task = MLEBenchTask(cfg.task)
        assert task._search_only_score and not task.private_dir.exists()
        for step in range(1, 5):
            msg = prompt(task.task_description, s, step, ['x=1'], 'observed', 500)
            assert advice(s) in msg and f'CURRENT MODEL CALL: {step} of 4.' in msg
            assert ('AUXILIARY PUBLIC-CV OBSERVATION' in msg) == (s['arm'] != 'A')
    subprocess.run(['bash', '-n', str(R/'run.sbatch')], check=True)
    m.write(R/'cpu.json', dict(status='PASS', configs=12, prompt_checks=48, report_source_checks=4, plan_sha256=sha(R/'plan.json')))


def submit():
    m.check()
    plan = sha(R/'plan.json')
    for name in ('transport-loop-cpu.json', 'analysis-freeze.json'):
        assert m.read(R/name)['plan_sha256'] == plan
    assert m.read(R/'budget-approval.json')['gpu_hours_cap'] == 6
    assert sha(m.infra.TASK_IMAGE) == m.infra.IMAGE_SHA and sha(m.ASSETS/'vllm.sif') == m.infra.VLLM_SHA
    for item in m.read(m.ASSETS/'complete.json')['files']:
        if item['path'].endswith('.safetensors'):
            assert sha(m.ASSETS/item['path']) == item['digest']
    env = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    jobs = subprocess.check_output(['squeue', '-u', 'yzyang4', '-h', '-o', '%i'], env=env, text=True, timeout=25).split()
    assert not set(jobs)-{'12535'}
    assert not (R/'submit-intent.json').exists() and not (R/'launch.json').exists()
    m.write(R/'submit-intent.json', dict(utc=m.utc(), plan_sha256=plan))
    result = subprocess.run(['sbatch', '--parsable', '--chdir='+str(R), '--output='+str(R/'allocation-%j.out'),
                             '--error='+str(R/'allocation-%j.err'), str(R/'run.sbatch')], env=env, capture_output=True, text=True, timeout=25)
    job = result.stdout.strip().split(';')[0]
    assert result.returncode == 0 and job.isdigit(), 'ambiguous submission: do not retry'
    m.write(R/'launch.json', dict(job=job, utc=m.utc(), plan_sha256=plan))
    print(json.dumps(dict(status='SUBMITTED', job=job, plan_sha256=plan, gpu_hours_cap=6)))


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare', 'cpu', 'submit', 'worker', 'controller', 'service', 'compat'])
    parser.add_argument('--index', type=int)
    args = parser.parse_args()
    if args.mode in ('prepare', 'cpu', 'submit'):
        globals()[args.mode]()
    elif args.mode == 'compat':
        compatibility()
    elif args.mode == 'worker':
        m.worker(args.index)
    else:
        getattr(m, args.mode)()
