"""Small prospective implementation-reset qualification, not full MCTS or a selector.

Reuses the accepted Dojo operators, dev scorer, container binding and supervisor.
No previous candidates, quality rankings, protected cohorts or model training.
"""
from __future__ import annotations
import argparse, ast, asyncio, copy, hashlib, inspect, json, logging, math, os
import random, re, secrets, shutil, subprocess, sys, time
from pathlib import Path

B = Path('/research/d7/spc/yzyang4')
OLD = B/'policy9b-paired-20261005-gpu27-v1'
R = B/'implementation-reset-20261005-v1'
PY = B/'venvs/aira/bin/python'
NAME = 'implementation_reset_20261005.py'
DONOR_SHA = 'b422a17094a6971218731054b53b56888505150b82f5309990b0b629577da4c9'
TASKS = ('random-acts-of-pizza', 'spooky-author-identification')
SECONDS, CAP = 600, 7200
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
IDEA = '''Fixed modeling idea, specified before any outcome: sparse word TF-IDF
features from the task's main text field, followed by ONE regularized logistic
regression classifier with probability output. Spooky has three author classes;
Pizza is binary request success. Fit vectorizer only on the supplied training
rows, then transform the supplied prediction rows. No additional character
vectorizer, extra numeric features, model ensemble, external data or pretrained
model. Within this idea, tokenization, vocabulary limits, regularization strength,
solver, public validation and implementation details are free. This is a broad
family, not identical hyperparameters or a claim of semantic equivalence.
'''
COMMON = '''This is a bounded code-start DEVELOPMENT experiment, not final test.
Use only /workspace/data and the current workspace; no downloads or hidden labels.
Return a brief rationale and a complete Python solution using the ordinary code
format. Do not return a separate PLAN-only response. Each program starts in a
fresh workspace. A previously valid starting submission is retained externally
in ALL continuation conditions, so an unsuccessful change cannot erase it.
Generation, execution, public checks, failures and external scoring all consume
the same 600-second continuation budget; each execution is at most 240 seconds.
Do not attempt to access other episodes, model services or evaluator internals.
'''

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda: f.read(8*1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def read(p): return json.loads(Path(p).read_bytes())

def write(p, value):
    data = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
    if SECRET.search(data): raise ValueError('credential-shaped output withheld')
    with Path(p).open('xb') as f: f.write(data); f.flush(); os.fsync(f.fileno())

def schedule():
    rows = [dict(index=len(TASKS)*b+t, wave=b, start=len(TASKS)*b+t,
                 task=task, seed=110501+10*b+t, arm='ROOT')
            for b in range(2) for t, task in enumerate(TASKS)]
    for b in range(2):
        order = ('continue', 'reimplement', 'new_idea') if b == 0 else ('new_idea', 'reimplement', 'continue')
        for j, arm in enumerate(order):
            for t, task in enumerate(TASKS):
                rows.append(dict(index=len(rows), wave=2+3*b+j, start=2*b+t,
                                 task=task, seed=110601+10*b+t, arm=arm))
    return rows

def instructions(s, parent_score=None):
    if s['arm'] == 'ROOT':
        note = 'Implement the fixed modeling idea below. Stop is handled externally at the FIRST valid submission; no best-of-source selection.\n'+IDEA
    elif s['arm'] == 'continue':
        note = 'Continue improving the supplied implementation. Retain its modeling idea and use the existing code as your starting implementation.\n'+IDEA
    elif s['arm'] == 'reimplement':
        note = 'Independently implement the SAME modeling idea from a blank implementation. The old code and its execution logs are deliberately not provided. Do not change model family.\n'+IDEA
    else:
        note = 'Independently implement a DIFFERENT modeling idea from a blank implementation. The old code and its execution logs are deliberately not provided. Change the representation or classifier family, not merely a seed, solver or hyperparameter. The previous idea (for contrast, not a requirement) was:\n'+IDEA
    return COMMON+note+('' if parent_score is None else f'\nCommon incumbent development score: {parent_score}.')

def structural_idea_check(code):
    """Only a transparent syntactic screen; NOT a semantic equivalence certificate."""
    tree = ast.parse(code)
    calls = sorted({getattr(n.func, 'id', getattr(n.func, 'attr', ''))
                    for n in ast.walk(tree) if isinstance(n, ast.Call)})
    other = [n for n in calls if n.endswith(('Classifier', 'Regressor')) or n in ('SVC', 'LinearSVC', 'MultinomialNB', 'BernoulliNB')]
    vecs = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, 'id', getattr(n.func, 'attr', '')) == 'TfidfVectorizer']
    char = any(k.arg == 'analyzer' and isinstance(k.value, ast.Constant) and k.value.value != 'word' for n in vecs for k in n.keywords)
    return dict(screen_pass='TfidfVectorizer' in calls and 'LogisticRegression' in calls and not other and not char,
                classifier_calls=other, tfidf_constructor_sites=len(vecs), nonword_analyzer=char,
                limitation='Syntactic screen only; aliases and dataflow require blinded code review.')

def native():
    import importlib.util
    p = OLD/'policy9b_paired_20261005.py'
    assert sha(p) == DONOR_SHA, 'accepted infrastructure changed'
    spec = importlib.util.spec_from_file_location('reset_fixed_host', p)
    m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m; spec.loader.exec_module(m)
    m.R, m.CAP, m.SECONDS = R, CAP, SECONDS
    m.schedule, m.check, m.freeze_roots = schedule, check, freeze_roots
    # Existing device binding accepts arbitrary episode IDs; widen only its path
    # validation, not CUDA isolation or task execution. Exact replacement is checked.
    changes = {
        'task_runtime': [('episode-[0-7]', 'episode-[0-9]+')],
        'controller': [('range(4)', 'range(8)'), ('01:29:00', '01:59:00'),
                       ('dict(attempts=8,', 'dict(attempts=16,'),
                       ("write(R/f'wave-{wave}.json',dict(indices=done,utc=utc()))",
                        "write(R/f'wave-{wave}.json',dict(indices=done,utc=utc()))\n                if wave == 1 and not freeze_roots(): return")]
    }
    for function, replacements in changes.items():
        source = inspect.getsource(getattr(m, function))
        for before, after in replacements:
            assert source.count(before) == 1, (function, before)
            source = source.replace(before, after)
        exec(compile(source, NAME+':'+function, 'exec'), m.__dict__)
    m.__file__ = str(R/NAME)
    return m

def check():
    p = read(R/'plan.json'); assert p['schedule'] == schedule()
    for name, h in p['files'].items(): assert sha(R/name) == h, name
    assert sha(OLD/'policy9b_paired_20261005.py') == DONOR_SHA
    return p

def prepare():
    assert not R.exists(), 'new root only; do not overwrite attempted experiment'
    frozen = read(OLD/'plan.json')
    assert sha(OLD/'plan.json') == '12d1264457158c936e4f1eff8e9c844ce5044365e77056066c4ded2ecfe6cd79'
    R.mkdir(mode=0o700)
    names = ('forets_gpu_binding_20260911.py', 'forets_native_cuda_identity_20260911.py',
             'forets_native_gpu_binding_20260911.py', 'forets_opencl_allowlist_20260911.py',
             'forets_opencl_readonly_ab.py', 'root_trial_step_supervisor_20260927.py', 'service_entry.py')
    for name, h in frozen['files'].items():
        if name.startswith('source/') or name in names:
            assert sha(OLD/name) == h
            target = R/name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(OLD/name, target)
    for folder in ('configs', 'starts', 'bin', 'opencl-vendors', 'service-cache/tmp'):
        (R/folder).mkdir(parents=True, exist_ok=True)
    (R/'opencl-vendors/nvidia.icd').write_text('libnvidia-opencl.so.1\n')
    shutil.copyfile(__file__, R/NAME)
    shutil.copyfile(Path(__file__).with_name('analyze_implementation_reset_20261005.py'), R/'analyze_implementation_reset_20261005.py')
    (R/'bin/singularity').write_text(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom implementation_reset_20261005 import native\nnative().task_runtime()\n')
    os.chmod(R/'bin/singularity', 0o700)
    with (R/'.service.env').open('x') as f: f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    os.chmod(R/'.service.env', 0o600)
    for s in schedule():
        old = 'configs/0.json' if s['task'] == TASKS[0] else 'configs/1.json'
        assert sha(OLD/old) == frozen['files'][old]
        cfg = read(OLD/old); ep = R/f"episode-{s['index']}"; ep.mkdir()
        cfg['id'] = 'implementation-reset-'+str(s['index'])
        cfg['metadata'].update(seed=s['seed'], script_id='implementation-reset-20261005', base_path=str(R/'source'))
        cfg['logger'].update(output_dir=str(ep/'native-log'), write_env_vars=False, use_wandb=False, print_config=False, use_console=False)
        cfg['solver'].update(time_limit_secs=SECONDS, execution_timeout=240, step_limit=10000, checkpoint_path=str(ep/'checkpoint'))
        cfg['interpreter']['working_dir'] = str(ep/'work')
        cfg['interpreter']['env']['PYTHONHASHSEED'] = str(s['seed'])
        cfg['task']['cache_dir'] = str(R/'no-official-data')
        for op in cfg['solver']['operators'].values():
            op['llm']['client']['model_id'] = 'qwen3.5-9b'
            op['llm']['generation_kwargs']['seed'] = s['seed']
        write(R/'configs'/f"{s['index']}.json", cfg)
    batch = f'''#!/bin/bash
#SBATCH --job-name=idea-implementation-ABC
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:4
#SBATCH --cpus-per-task=24
#SBATCH --time=02:00:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 7120s {PY} -B {R/NAME} controller
'''
    (R/'run.sbatch').write_text(batch)
    files = {str(p.relative_to(R)): sha(p) for p in R.rglob('*') if p.is_file() and p.name != '.service.env'}
    write(R/'plan.json', dict(protocol='prospective-fixed-idea-implementation-reset-v1', utc=native().utc(),
        files=files, schedule=schedule(), source_commit=frozen['source_commit'], infra_sha256=DONOR_SHA,
        root_runs=4, comparison_runs=12, run_seconds=SECONDS, allocated_gpus=4, allocation_seconds=CAP,
        gpu_hours_cap=CAP*4/3600, user_approval='2026-10-05: 可以的，你试一试，这对我很重要; bounded matrix announced before implementation',
        task_image_sha256=frozen['task_image_sha256'], service_image_sha256=frozen['service_image_sha256'],
        base=frozen['base'], base_revision=frozen['base_revision'], context_tokens=32768, max_output_tokens=8192,
        temperature='unchanged native role defaults', no_thinking=True, model_training=False, paid_api=0,
        source_selection='first externally valid per predeclared task/seed; STOP all contrasts unless all four qualify; no replacement roots',
        idea=IDEA, syntactic_source_screen='TFIDF plus LR; no alternate classifier or explicit nonword analyzer; not semantic proof',
        primary='Oriented paired final best dev score with COMMON incumbent fallback and <=600s continuation; task-specific median and variance, all 12 assignments.',
        cost='Shared prospective source cost charged in full to every contrasted strategy; generation/execution/scoring inside continuation clock. Whole 4-GPU allocation including service startup reported separately.',
        visibility='continue sees old code and logs; reimplement and new_idea see only fixed idea and common score. No inherited runtime state in ANY arm. This is bundled context/operator-routing intervention, not pure prompt-length or semantic causality.',
        advance='No automatic expansion. Consider only if all four paired reimplement-minus-continue AND reimplement-minus-new_idea are positive, qualifying parent/selected-code adherence is independently checked, and gain not explained solely by ordinary tuning/repair. Incomplete pairs do not pass.',
        limits='Two previously reused development tasks, simple human-specified idea family, two roots per task; no novel selector or full-search E2E claim, no protected or final-test access. Missing results remain missing; no p-value at n=2/task.'))
    cpu()
    print(json.dumps(dict(status='PREPARED', plan_sha256=sha(R/'plan.json'), runs=16, gpu_hours_cap=8)))

def cpu():
    check(); m = native(); m.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.core.solvers.utils.journal import Journal, Node
    from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
    from dojo.core.solvers.operators.draft import draft_op
    from dojo.core.solvers.operators.improve import improve_op
    from dojo.core.solvers.operators.debug import debug_op
    from dojo.utils.logger import config_logger
    from omegaconf import OmegaConf
    os.environ['PRIMARY_KEY_QWEN3_5_9B'] = 'offline-fixture'
    comparisons = []
    for s in schedule():
        cfg = RunConfig.load_from_json(R/'configs'/f"{s['index']}.json"); cfg.validate(); config_logger(cfg)
        task = MLEBenchTask(cfg.task)
        assert task._search_only_score is not None and not task.private_dir.exists() and cfg.solver.use_test_score is False
        assert sha(Path(cfg.task.search_only_dev_scorer_path)) == cfg.task.search_only_dev_scorer_sha256
        for kind, op in (('draft', draft_op), ('improve', improve_op), ('debug', debug_op)):
            llm = GenericLLM(OmegaConf.structured(cfg.solver.operators[kind])); j = Journal()
            n = Node(code='sentinel_parent = 12345', plan='common idea', _term_out=['log'])
            async def mock(**kw):
                q = kw['query_data']; messages = [llm.system_message_prompt_template.format(**q), llm.init_user_message_prompt_template.format(**q)]
                combined = '\n'.join(messages)
                assert ('sentinel_parent' in combined) == (kind != 'draft')
                assert 'Fixed modeling idea' in combined
                return '```python\npass\n```', {}
            args = [mock, OmegaConf.structured(cfg.solver), None, task.task_description+instructions(s, .5), j]
            if kind != 'draft': args.append(n)
            asyncio.run(op(*args, 1, 600, data_preview='public-only'))
        if s['arm'] != 'ROOT': comparisons.append((s, cfg.to_typed_dict()))
    def normalized(x):
        x = copy.deepcopy(x)
        for k in ('id', 'logger', 'metadata'): x.pop(k, None)
        for k in ('checkpoint_path', 'exp_name'): x['solver'].pop(k, None)
        x['interpreter'].pop('working_dir', None); x['task'].pop('results_output_dir', None)
        return x
    for start in range(4):
        group = [normalized(cfg) for s, cfg in comparisons if s['start'] == start]
        assert len(group) == 3 and group[0] == group[1] == group[2]
    assert structural_idea_check('v=TfidfVectorizer(); m=LogisticRegression()')['screen_pass']
    assert not structural_idea_check('v=TfidfVectorizer(analyzer="char"); m=LogisticRegression()')['screen_pass']
    subprocess.run(['bash', '-n', str(R/'run.sbatch')], check=True)
    write(R/'cpu.json', dict(status='PASS', configs=16, native_prompt_renders=48, matched_config_triplets=4,
        no_model_calls=True, plan_sha256=sha(R/'plan.json')))

def freeze_roots():
    rows=[]
    for start in range(4):
        p=R/f'episode-{start}'/'first-valid.private.json'
        if not p.exists():
            write(R/'source-gate.json', dict(passed=False, reason='missing_first_valid', missing_start=start)); return False
        x=read(p); screen=structural_idea_check(x['code'])
        if not screen['screen_pass']:
            write(R/'source-gate.json', dict(passed=False, reason='idea_screen_failed', start=start, screen=screen)); return False
        write(R/'starts'/f'{start}.private.json', x)
        rows.append(dict(start=start, code_sha256=hashlib.sha256(x['code'].encode()).hexdigest(), source_sha256=sha(p), screen=screen))
    write(R/'source-gate.json', dict(passed=True, roots=rows, semantics_verified=False))
    return True

def worker(index):
    check(); m=native(); m.setup(); s=schedule()[index]; ep=R/f'episode-{index}'; x=m.infra()
    own=x.native_uuids(1); assert not set(own)&set(read(R/'service-native.json')['gpu_uuids'])
    os.environ.update(PRIMARY_KEY_QWEN3_5_9B=x.local_key(), PRIMARY_KEY=x.local_key(),
        DOJO_GPU_UUIDS=own[0], POLICY9B_EPISODE=str(ep), DOJO_WORKER_IDENTITY_PATH=str(ep/'identity.json'),
        DOJO_EXECUTION_ID=f'{os.environ["SLURM_JOB_ID"]}.{os.environ["SLURM_STEP_ID"]}:{index}',
        HARDWARE='one NVIDIA RTX3090, six CPU cores', TIME_LIMIT='10 minutes', TIME_LIMIT_SECS='600', STEP_LIMIT='10000',
        PATH=str(R/'bin')+':'+os.environ['PATH'])
    from dojo.main_local_worker import _process_start_ticks, _host_boot_id
    write(ep/'identity.json',dict(pid=os.getpid(),pgid=os.getpgid(0),process_start_ticks=_process_start_ticks(os.getpid()),host_boot_id=_host_boot_id(),gpu_uuids=own,container_pid=None,container_process_start_ticks=None))
    write(ep/'native.json',dict(index=index,job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],config_sha256=sha(R/'configs'/f'{index}.json'),gpu_uuids=own))
    from dojo.utils.experiment_deadline import ExperimentDeadline, ExperimentDeadlineExpired
    deadline=ExperimentDeadline(SECONDS);write(ep/'deadline.json',deadline.receipt());status='failed'
    try:
        with deadline.activate(): episode(s,ep,deadline)
        status='completed'
    except ExperimentDeadlineExpired: status='budget_exhausted'
    except Exception as exc:
        write(ep/'failure.json',dict(error_type=type(exc).__name__));raise
    finally: write(ep/'finished.json',dict(status=status,elapsed_seconds=deadline.elapsed(),utc=m.utc()))

def episode(s,ep,deadline):
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.utils.config import build
    from dojo.utils.logger import config_logger
    from dojo.core.tasks.constants import EXECUTION_OUTPUT,VALID_SOLUTION,VALIDATION_FITNESS,VALID_SOLUTION_FEEDBACK
    from dojo.core.solvers.utils.journal import Journal,Node
    from dojo.core.solvers.utils.metric import MetricValue,WorstMetricValue
    from dojo.utils.code_parsing import extract_code
    from dojo.core.solvers.operators.draft import draft_op
    from dojo.core.solvers.operators.improve import improve_op
    from dojo.core.solvers.operators.debug import debug_op
    from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
    from omegaconf import OmegaConf
    import numpy as np
    cfg=RunConfig.load_from_json(R/'configs'/f"{s['index']}.json");config_logger(cfg)
    for name in ('openai','httpx','httpcore','LiteLLM'):logging.getLogger(name).setLevel(logging.ERROR)
    task_info=MLEBenchTask(cfg.task);desc=task_info.task_description
    score=None;parent=None;best_generated=None;node=None;journal=Journal();lower=s['task']==TASKS[1]
    if s['arm']!='ROOT':
        assert read(R/'source-gate.json')['passed']
        src=read(R/'starts'/f"{s['start']}.private.json");score=src['metric']
        if s['arm']=='continue':
            parent=Node(code=src['code'],plan=IDEA,_term_out=[src['terminal']],is_buggy=False,metric=MetricValue(score,maximize=not lower))
    note=instructions(s,score);write(ep/'condition.json',dict(arm=s['arm'],instructions=note,old_code_visible=s['arm']=='continue',inherited_runtime_state=False))
    best=score
    for step in range(10000):
        deadline.check()
        if deadline.remaining()<10:break
        action=ep/f'action-{step}';action.mkdir()
        selected = node if node is not None and node.is_buggy else (best_generated or parent)
        kind='draft' if selected is None else ('debug' if selected.is_buggy else 'improve')
        opc=copy.deepcopy(cfg.solver.operators[kind]);kw=opc.llm.generation_kwargs
        call_seed=s['seed']*1000+step;kw['seed']=call_seed;kw['bounded_request_timeout_seconds']=max(1,min(180,int(deadline.remaining())))
        random.seed(call_seed);np.random.seed(call_seed)
        llm=GenericLLM(OmegaConf.structured(opc));op={'draft':draft_op,'debug':debug_op,'improve':improve_op}[kind]
        args=[llm,OmegaConf.structured(cfg.solver),None,desc+'\n'+note,journal]
        if selected is not None:args.append(selected)
        start=time.monotonic()
        try:
            response, info=asyncio.run(asyncio.wait_for(op(*args,step,int(deadline.remaining()),data_preview='Use the task-described files in /workspace/data.'),timeout=max(1,min(185,deadline.remaining()))))
        except (asyncio.TimeoutError,TimeoutError):
            write(action/'generation-failure.json',dict(reason='timeout',elapsed_seconds=deadline.elapsed()));break
        raw=str(response);assert not SECRET.search(raw.encode())
        write(action/'generation.private.json',dict(response=raw,info=info,generation_seconds=time.monotonic()-start,call_seed=call_seed,kind=kind))
        try:
            code=extract_code(raw)
            if not code.strip():raise ValueError('empty code')
            ast.parse(code)
        except (SyntaxError,ValueError):
            write(action/'parse-failure.json',dict(elapsed_seconds=deadline.elapsed()));break
        # A complete fresh program on every execution; no treatment gets cached models.
        node=Node(code=code,plan=raw.split('```',1)[0],_term_out=[],is_buggy=True,metric=WorstMetricValue())
        task=MLEBenchTask(cfg.task);original=task._search_only_score
        def capture(name,submission):
            receipt=original(name,submission)
            shutil.copyfile(submission,action/'submission.private.csv')
            write(action/'score.private.json',dict(receipt=receipt,elapsed_seconds=deadline.elapsed()))
            return receipt
        task._search_only_score=capture
        icfg=copy.deepcopy(cfg.interpreter);icfg.working_dir=str(action/'work');icfg.timeout=max(1,min(240,int(deadline.remaining())))
        Path(icfg.working_dir).mkdir();interp=build(icfg,INTERPRETER_MAP,data_dir=cfg.task.data_dir)
        state=None
        write(action/'code.private.json',dict(code=code))
        try:
            state,_=task.prepare(solver_interpreter=interp,eval_interpreter=None)
            executable=f'import random as _r, numpy as _n\n_r.seed({s["seed"]})\n_n.random.seed({s["seed"]})\n'+f'exec(compile({code!r},"solution.py","exec"))\n'
            state,result=task.step_task(state,executable);deadline.check()
        finally:
            interp.close()
            if hasattr(interp,'cleanup_session'):interp.cleanup_session()
        out=result[EXECUTION_OUTPUT];node.absorb_exec_result(out)
        value=result.get(VALIDATION_FITNESS);valid=bool(result.get(VALID_SOLUTION)) and out.exit_code==0 and not out.timed_out and isinstance(value,(int,float)) and math.isfinite(value)
        node.is_buggy=not valid
        if valid:node.metric=MetricValue(value,maximize=not lower)
        node._term_out=list(node._term_out or [])+['\nTrusted DEVELOPMENT feedback: '+str(result.get(VALID_SOLUTION_FEEDBACK,''))]
        journal.append(node)
        if valid and (best_generated is None or node.metric>best_generated.metric):best_generated=node
        improves=valid and (best is None or (value<best if lower else value>best))
        if improves:best=value
        write(action/'result.json',dict(valid=valid,metric=value if valid else None,selected_metric=best,improves=improves,elapsed_seconds=deadline.elapsed(),exec_seconds=out.exec_time,exit_code=out.exit_code,timed_out=out.timed_out,kind=kind,code_sha256=hashlib.sha256(code.encode()).hexdigest(),idea_screen=structural_idea_check(code)))
        if s['arm']=='ROOT' and valid:
            write(ep/'first-valid.private.json',dict(code=code,metric=value,terminal=node.term_out,elapsed_seconds=deadline.elapsed(),step=step,seed=s['seed'],task=s['task']))
            break

def submit():
    p=check();m=native();assert read(R/'cpu.json')['plan_sha256']==sha(R/'plan.json')
    assert sha(m.TASK_IMAGE)==p['task_image_sha256'] and sha(m.VLLM)==p['service_image_sha256']
    # Keep exact accepted BF16 deployment (the loaded adapter is never requested).
    assert m.MODEL.is_dir() and m.ADAPTER.is_dir()
    env=m.infra().clean_env()
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=20).split()
    assert not set(jobs)-{'12535'}, 'unexpected owned allocation'
    write(R/'submit-intent.json',dict(utc=m.utc(),plan_sha256=sha(R/'plan.json')))
    r=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),'--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=r.stdout.strip().split(';')[0]
    assert r.returncode==0 and job.isdigit(), 'ambiguous submission, inspect scheduler; do not retry'
    write(R/'launch.json',dict(job=job,utc=m.utc(),plan_sha256=sha(R/'plan.json')))
    print(json.dumps(dict(status='SUBMITTED',job=job,runs=16,gpu_hours_cap=8)))

if __name__=='__main__':
    os.umask(0o077)
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('prepare','cpu','submit','worker','controller','service','check'));p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='worker':worker(a.index)
    elif a.mode in ('controller','service'):getattr(native(),a.mode)()
    elif a.mode=='check':check();print('FROZEN_PLAN_VALID')
    else:globals()[a.mode]()
