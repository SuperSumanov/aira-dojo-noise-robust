"""Bounded qualification of reachable improvements, not an agent method result.

Five available first-valid programs from six prelisted development physical runs.
One manually specified change per available state; paired RNG settings; no LLM.
Original results, invalid starts and all failures remain in the denominator.
"""
import argparse,ast,copy,datetime,hashlib,importlib.util,json,os,random,re,shutil,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
B=Path('/research/d7/spc/yzyang4');ROOT=B/'natural-opportunity-20261003-v1'
PARENT=B/'state-feedback-factorial-20261002-v1';PY=B/'venvs/aira/bin/python'
COMMIT='a284f3df7e8239a042765a329c81282643a4d5a1'
INTAKE_SHA='c57d6005d274a47d0361edb6326e793e8a6da7dad467b7225c6fcc460d480b30'
SEEDS=(42,173);CAP=5400;EXEC_CAP=300
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
CHANGES={
 0:dict(name='cv_selected_member',rationale='Parent measures three CV losses but ignores them for a fixed unvalidated 0.4/0.3/0.3 blend; select minimum mean public CV loss instead. Hypothesis, not proven bug.'),
 1:dict(name='binary_auc_alignment',rationale='LightGBM params omit objective and metric, so defaults optimize regression/L2 despite an AUC task. Joint binary objective and AUC early-stopping correction; component effects are not separated.'),
 3:dict(name='complementary_word_view',rationale='Three character-only views lack explicit word bigrams. Add identical word(1,2) TFIDF to each view. Known ML reference; hypothesis, not diagnosis established by outcomes.'),
 4:dict(name='xgb_early_stopping',rationale='XGBoost fits 1000 rounds despite passing a validation set. Add constructor early_stopping_rounds=50; keep all other models and stacking unchanged.'),
 5:dict(name='span_order_mask',rationale='Score matrix rows are starts, columns ends, but np.tril permits end<=start. Replace with np.triu to enforce start<=end. Structural bug is verifiable without labels; quality gain is unknown.'),
}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def write(p,x):
    with Path(p).open('x') as f:json.dump(x,f,indent=2,sort_keys=True,allow_nan=False)
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def replace_once(code,old,new):
    if code.count(old)!=1:raise ValueError('nonunique patch anchor')
    return code.replace(old,new)
def candidate(i,code):
    if i==0:
        code=replace_once(code,'test_prob_final = 0.4 * test_prob_combined + 0.3 * test_prob_word + 0.3 * test_prob_char',
            'test_prob_final = [test_prob_word, test_prob_char, test_prob_combined][int(np.argmin([np.mean(cv_scores_word), np.mean(cv_scores_char), np.mean(cv_scores_combined)]))]')
    elif i==1:
        code=replace_once(code,'for p in params_grid:\n','for p in params_grid:\n    p.update(objective="binary", metric="auc")\n')
    elif i==3:
        old='    X_train_tfidf = tfidf.fit_transform(train_texts)'
        new='    from sklearn.pipeline import FeatureUnion\n    tfidf = FeatureUnion([("char", tfidf), ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=100000, sublinear_tf=True))])\n'+old
        code=replace_once(code,old,new)
    elif i==4:
        code=replace_once(code,'    xgb_model = xgb.XGBClassifier(**xgb_params)','    xgb_model = xgb.XGBClassifier(**xgb_params, early_stopping_rounds=50)')
    elif i==5:
        code=replace_once(code,'mask = np.tril(np.ones((tl, tl), dtype=bool))','mask = np.triu(np.ones((tl, tl), dtype=bool))')
    else:raise ValueError(i)
    ast.parse(code);return code
class RNG(ast.NodeTransformer):
    def __init__(self,seed):self.seed=seed;self.changes=0
    def visit_keyword(self,node):
        if node.arg=='random_state' and isinstance(node.value,ast.Constant) and node.value.value==42:
            node.value=ast.Constant(self.seed);self.changes+=1
        return self.generic_visit(node)
    def visit_Assign(self,node):
        if any(isinstance(t,ast.Name) and t.id=='SEED' for t in node.targets) and isinstance(node.value,ast.Constant) and node.value.value==42:
            node.value=ast.Constant(self.seed);self.changes+=1
        return self.generic_visit(node)
    def visit_Dict(self,node):
        for j,k in enumerate(node.keys):
            if isinstance(k,ast.Constant) and k.value=='random_state' and isinstance(node.values[j],ast.Constant) and node.values[j].value==42:
                node.values[j]=ast.Constant(self.seed);self.changes+=1
        return self.generic_visit(node)
def seeded(code,seed):
    t=RNG(seed);tree=t.visit(ast.parse(code));ast.fix_missing_locations(tree)
    prefix=f'import random, numpy as np\nrandom.seed({seed})\nnp.random.seed({seed})\n'
    if 'import torch' in code:prefix+='import torch\nassert torch.cuda.is_available(), "GPU required: no CPU fallback"\ntorch.backends.cudnn.deterministic=True\ntorch.backends.cudnn.benchmark=False\n'
    return prefix+ast.unparse(tree)+'\n',t.changes
def runtime():
    p=ROOT/'v6_runtime.py'
    assert sha(p)=='4b155d927c12f063e0838b5708085fe1bc55c4983197a3d8d2453696d73c55ad'
    sp=importlib.util.spec_from_file_location('natural_runtime',p);m=importlib.util.module_from_spec(sp);sys.modules[sp.name]=m;sp.loader.exec_module(m)
    m.ROOT=ROOT;m.infra.ROOT=ROOT;m.setup();return m
def schedule():
    pairs=[(i,seed) for seed in SEEDS for i in sorted(CHANGES)]
    random.Random(104003).shuffle(pairs);out=[]
    for pair,(i,seed) in enumerate(pairs):
        arms=['original','modified'] if pair%2==0 else ['modified','original']
        for arm in arms:out.append(dict(index=len(out),state=i,seed=seed,arm=arm,pair=pair))
    return out
def check():
    p=read(ROOT/'plan.json');assert p['schedule']==schedule()
    for f,h in p['files'].items():assert sha(ROOT/f)==h,f
    return p
def prepare():
    assert sha(ROOT/'intake.json')==INTAKE_SHA and not (ROOT/'plan.json').exists()
    assert sha(PARENT/'plan.json')=='2820d6cc64d9d1045179f2290383340c38605b6ba604364d8fd6307be2a0b237'
    for rel,h in read(PARENT/'plan.json')['files'].items():
        if not(rel.startswith(('source/','forets_','opencl-vendors/')) or rel=='v6_runtime.py'):continue
        assert sha(PARENT/rel)==h
        p=ROOT/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(PARENT/rel,p)
    shutil.copyfile(__file__,ROOT/Path(__file__).name)
    for name in ('bin','configs','programs'):(ROOT/name).mkdir()
    wrapper=f'#!{PY}\nimport sys\nsys.path.insert(0,{str(ROOT)!r})\nfrom natural_opportunity_20261003 import runtime\nruntime().task_runtime()\n'
    (ROOT/'bin/singularity').write_text(wrapper);os.chmod(ROOT/'bin/singularity',0o700)
    intake=read(ROOT/'intake.json');states={s['index']:s for s in intake['states']};programs=[]
    for s in schedule():
        i=s['state'];assert states[i]['available']
        raw=(ROOT/'starts'/f'{i}.py').read_text();assert hashlib.sha256(raw.encode()).hexdigest()==states[i]['code_sha256']
        code=raw if s['arm']=='original' else candidate(i,raw)
        executable,count=seeded(code,s['seed']);ast.parse(executable)
        if SECRET.search(executable.encode()):raise ValueError('credential shape')
        pp=ROOT/'programs'/f'{s["index"]}.private.py';pp.write_text(executable)
        cfg=read(ROOT/'starts'/f'{i}.config.private.json');ep=ROOT/f'episode-{s["index"]}';ep.mkdir()
        cfg['id']=f'natural-opportunity-{s["index"]}';cfg['logger'].update(output_dir=str(ep/'native-log'),write_env_vars=False,use_wandb=False,use_console=False,print_config=False)
        cfg['metadata'].update(seed=s['seed'],base_path=str(ROOT/'source'),git_commit_id=COMMIT,script_id='natural-opportunity-20261003')
        cfg['interpreter']['env'].update(PYTHONHASHSEED=str(s['seed']),OMP_NUM_THREADS='6',OPENBLAS_NUM_THREADS='6',MKL_NUM_THREADS='6',NUMEXPR_NUM_THREADS='6')
        cfg['task']['cache_dir']=str(ROOT/'no-official-data')
        write(ROOT/'configs'/f'{s["index"]}.json',cfg)
        programs.append(dict(**s,task=states[i]['task'],code_sha256=sha(pp),rng_sites=count))
    batch=f'''#!/bin/bash
#SBATCH --job-name=natural-opportunity
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=12
#SBATCH --time=01:30:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 5340s {PY} -B {ROOT}/natural_opportunity_20261003.py controller
'''
    (ROOT/'run.sbatch').write_text(batch)
    write(ROOT/'plan.json',dict(protocol='natural-first-valid-opportunity-v1',commit=COMMIT,utc=utc(),
        intake_sha256=INTAKE_SHA,roster=6,available=5,unavailable=[2],schedule=schedule(),programs=programs,changes=CHANGES,
        files={str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*') if p.is_file()},
        task_execution_seconds=EXEC_CAP,worker_seconds=450,allocation_seconds=CAP,gpus=2,gpu_hours_cap=3,
        number_program_executions=20,paid_api=0,generator_calls=0,base_updates=0,
        selection='No ranking by score. Same six previously inspected developer runs, first valid row. Missing run retained.',
        rng='All explicit random_state=42 and SEED=42 rewritten symmetrically; global RNG set. LGB default seed remains unchanged if absent. Two settings NOT independent physical run replication.',
        gate='For a state: all four executions valid; both direction-adjusted improvements >= task minimum (.005 AUC, .005 logloss, .01 Jaccard). At least 2 tasks qualify to propose cross-task diagnostic extension; no significance claim.',
        minimum_gain={'random-acts-of-pizza':.005,'spooky-author-identification':.005,'tweet-sentiment-extraction':.01},
        external='D_search development only, read after all outputs frozen. Independently recompute all metrics. No D_val/test/protected cohort.',
        scope='Cold rebuilt natural code states, no native history/cache continuation. Manual known-reference witnesses, not new methods. Count discovery/rebuild/repeats/invalids; no extra candidates after results.',
        costs='3 allocated GPUh hard cap includes all workers/startup/idling; historical start-generation cost sunk, not free. Assistant-designed candidate discovery is manual, not deployable zero-cost inference. No claim of full-search budget equality.',
        preregistration_tests='13-item checklist: config/patch evidence, CPU fixtures, no train/test fitting, taskwise denominator, paired balanced order, no agent checkpoint training, fixed hashes/isolation, explicit RNG, credential scan, allocation wall cap, exploratory not powered, subprocess rc checked, immutable roster.'))
    cpu()
def cpu():
    p=check();m=runtime()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    import numpy as np
    for s in p['schedule']:
        cfg=RunConfig.load_from_json(ROOT/'configs'/f'{s["index"]}.json');cfg.validate()
        task=MLEBenchTask(cfg.task);assert task._search_only_score and not task.private_dir.exists()
        interp=build(cfg.interpreter,INTERPRETER_MAP,data_dir=cfg.task.data_dir);assert interp.factory
        code=(ROOT/'programs'/f'{s["index"]}.private.py').read_text();ast.parse(code)
        assert cfg.interpreter.env['OMP_NUM_THREADS']=='6'
        assert p['programs'][s['index']]['rng_sites']>0
    # Original versus corrected mask must differ on a valid off-diagonal optimum.
    sl=np.array([4.,0.,0.]);el=np.array([0.,0.,4.]);scores=sl[:,None]+el[None,:]
    good=np.unravel_index(np.argmax(np.where(np.triu(np.ones((3,3),bool)),scores,-1e9)),scores.shape)
    bad=np.unravel_index(np.argmax(np.where(np.tril(np.ones((3,3),bool)),scores,-1e9)),scores.shape)
    assert good==(0,2) and bad!=good
    assert all(a<=b for a,b in zip(*np.where(np.triu(np.ones((5,5),bool)))))
    assert sum(s['arm']=='original' for s in schedule())==10
    assert len({(s['state'],s['seed'],s['arm']) for s in schedule()})==20
    subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    write(ROOT/'cpu.json',dict(status='PASS',configs=20,parsed_programs=20,mask_fixtures=2,independent_runs=5,roster=6,plan_sha256=sha(ROOT/'plan.json')))
    print(json.dumps(dict(status='PREPARED_CPU_PASS',root=str(ROOT),runs=20,gpu_hours_cap=3,plan_sha256=sha(ROOT/'plan.json'))))
def submit():
    p=check();m=runtime();assert not (ROOT/'submit-intent.json').exists()
    assert read(ROOT/'cpu.json')['plan_sha256']==sha(ROOT/'plan.json') and sha(m.infra.TASK_IMAGE)==m.infra.IMAGE_SHA
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=25).split();assert not set(jobs)-{'12535'}
    with (ROOT/'capacity.tmp').open('xb') as f:os.posix_fallocate(f.fileno(),0,512*1024**2)
    (ROOT/'capacity.tmp').unlink();write(ROOT/'submit-intent.json',dict(utc=utc(),plan_sha256=sha(ROOT/'plan.json')))
    r=subprocess.run(['sbatch','--parsable','--chdir='+str(ROOT),'--output='+str(ROOT/'allocation-%j.out'),'--error='+str(ROOT/'allocation-%j.err'),str(ROOT/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=r.stdout.strip().split(';')[0]
    if r.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; inspect, never retry blindly')
    write(ROOT/'launch.json',dict(job=job,utc=utc(),plan_sha256=sha(ROOT/'plan.json')));print(json.dumps(dict(job=job,status='SUBMITTED',gpu_hours_cap=3)))
def worker(index):
    p=check();m=runtime();s=p['schedule'][index];ep=ROOT/f'episode-{index}';own=m.infra.native_uuids(1)
    os.environ.update(DOJO_GPU_UUIDS=own[0],DOJO_WORKER_IDENTITY_PATH=str(ep/'identity.json'),DOJO_EXECUTION_ID=f'{os.environ["SLURM_JOB_ID"]}.{os.environ["SLURM_STEP_ID"]}:{index}',PATH=str(ROOT/'bin')+':'+os.environ['PATH'])
    from dojo.main_local_worker import _process_start_ticks,_host_boot_id
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    from dojo.utils.logger import config_logger
    from dojo.utils.experiment_deadline import ExperimentDeadline
    write(ep/'identity.json',dict(pid=os.getpid(),pgid=os.getpgid(0),process_start_ticks=_process_start_ticks(os.getpid()),host_boot_id=_host_boot_id(),gpu_uuids=own,container_pid=None,container_process_start_ticks=None))
    write(ep/'native.json',dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],gpu_uuids=own,config_sha256=sha(ROOT/'configs'/f'{index}.json')))
    cfg=RunConfig.load_from_json(ROOT/'configs'/f'{index}.json');Path(cfg.logger.output_dir).mkdir();config_logger(cfg)
    action=ep/'action-0';(action/'work').mkdir(parents=True);os.environ['FEEDBACK_ACTION_ROOT']=str(action)
    icfg=copy.deepcopy(cfg.interpreter);icfg.working_dir=str(action/'work');icfg.timeout=EXEC_CAP
    code=(ROOT/'programs'/f'{index}.private.py').read_text()
    # Explicit __main__ makes the original main-guard execute in all cells.
    executable=f'exec(compile({code!r}, "natural_program.py", "exec"), {{"__name__":"__main__"}})\n'
    began=time.monotonic();valid=False;error_type=None;out=None;interp=None
    with ExperimentDeadline(400).activate():
        try:
            interp=build(icfg,INTERPRETER_MAP,data_dir=cfg.task.data_dir)
            out=interp.run(executable,reset_session=False);terminal='\n'.join(out.term_out or [])
            if SECRET.search(terminal.encode()):raise ValueError('credential-shaped output')
            write(action/'terminal.private.json',dict(terminal=terminal))
            if out.exit_code==0 and not out.timed_out:
                path=action/'work/submission.csv';interp.fetch_file(path)
                assert path.is_file() and not path.is_symlink()
                shutil.copyfile(path,action/'submission.private.csv');valid=True
        except Exception as e:
            error_type=type(e).__name__
            message=str(e)
            write(action/'error.private.json',dict(type=error_type,message='withheld' if SECRET.search(message.encode()) else message))
        finally:
            if interp is not None:interp.close()
    write(action/'result.json',dict(**s,task=cfg.task.name,output_present=valid,exit_code=out.exit_code if out else None,timed_out=out.timed_out if out else None,
        error_type=error_type,seconds=time.monotonic()-began,plan_sha256=sha(ROOT/'plan.json'),code_sha256=sha(ROOT/'programs'/f'{index}.private.py'),
        submission_sha256=sha(action/'submission.private.csv') if valid else None))
    write(ep/'completed.json',dict(status='complete',output_present=valid))
def controller():
    check();m=runtime();assert read(ROOT/'launch.json')['job']==os.environ['SLURM_JOB_ID']
    def run_pair(pair):
        rc=[]
        for s in [s for s in schedule() if s['pair']==pair]:
            i=s['index'];ep=ROOT/f'episode-{i}'
            cmd=['srun','--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=6','--gres=gpu:1','--time=00:07:30',str(PY),'-B',str(ROOT/'natural_opportunity_20261003.py'),'worker','--index',str(i)]
            with (ep/'worker.private.log').open('xb') as f:
                result=subprocess.run(cmd,env=m.infra.clean_env(),stdout=f,stderr=f,timeout=480)
            write(ep/'closed.json',dict(returncode=result.returncode));rc.append(result.returncode)
            print(json.dumps(dict(index=i,closed=True,returncode=result.returncode)),flush=True)
        return rc
    with ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(run_pair,range(10)))
    write(ROOT/'closed.json',dict(returncodes=codes,utc=utc()))
    if any(c for row in codes for c in row):raise RuntimeError('worker failure retained')
def status():
    p=check();print(json.dumps(dict(launch=read(ROOT/'launch.json') if (ROOT/'launch.json').exists() else None,
        closed=(ROOT/'closed.json').exists(),episodes=[dict(index=s['index'],state=s['state'],arm=s['arm'],seed=s['seed'],started=(ROOT/f'episode-{s["index"]}/native.json').exists(),completed=(ROOT/f'episode-{s["index"]}/completed.json').exists()) for s in p['schedule']])) )
if __name__=='__main__':
    os.umask(0o077);ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','submit','worker','controller','status','check']);ap.add_argument('--index',type=int);a=ap.parse_args()
    if a.mode=='worker':worker(a.index)
    else:globals()[a.mode]()
