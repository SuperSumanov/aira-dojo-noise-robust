"""One-proposal continuation versus an open representation grid, not full MCTS."""
import argparse,ast,copy,csv,hashlib,inspect,json,os,re,secrets,shutil,signal,socket,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import structural_agent_contract_20261005 as c
B=Path('/research/d7/spc/yzyang4');R=B/'structural-agent-20261005-v1';OLD=B/'policy9b-paired-20261005-gpu27-v1'
PREV=B/'matched-representation-20261005-v1';PY=B/'venvs/aira/bin/python';NAME=Path(__file__).name
DONOR_SHA='b422a17094a6971218731054b53b56888505150b82f5309990b0b629577da4c9';CAP=2400
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def write(p,x):
    raw=(json.dumps(x,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();assert not SECRET.search(raw)
    with Path(p).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
def load(name,p):
    import importlib.util
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def host():
    assert sha(R/'runtime.py')==DONOR_SHA;m=load('structural_host',R/'runtime.py');m.R=R;m.CAP=CAP;m.__file__=str(R/NAME);m.check=check;m.setup()
    code=inspect.getsource(m.task_runtime);assert code.count('episode-[0-7]')==1
    exec(compile(code.replace('episode-[0-7]','episode-[0-9]+'),NAME+':runtime','exec'),m.__dict__);return m
def check():
    p=read(R/'plan.json');assert p['schedule']==c.schedule()
    for n,h in p['files'].items():assert sha(R/n)==h,n
    return p
def prepare(commit):
    import numpy as np,pandas as pd
    from sklearn.model_selection import train_test_split
    assert re.fullmatch('[0-9a-f]{40}',commit) and not R.exists()
    assert sha(PREV/'plan.json')=='fed6f8c812fc49db8acc459b460a10bbe962cbe10b8a2172f5dff06c7686a624'
    old=read(OLD/'plan.json');prior=read(PREV/'plan.json');R.mkdir(mode=0o700)
    names=('service_entry.py','root_trial_step_supervisor_20260927.py')
    for n,h in old['files'].items():
        if n.startswith(('source/','forets_','opencl-vendors/')) or n in names:
            assert sha(OLD/n)==h;dst=R/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(OLD/n,dst)
    assert sha(OLD/'policy9b_paired_20261005.py')==DONOR_SHA;shutil.copyfile(OLD/'policy9b_paired_20261005.py',R/'runtime.py')
    for n in (NAME,'structural_agent_contract_20261005.py','analyze_structural_agent_20261005.py'):shutil.copyfile(Path(__file__).parent/n,R/n)
    for n in ('configs','starts','views','bin','service-cache/tmp'):(R/n).mkdir(parents=True,exist_ok=True)
    (R/'bin/singularity').write_text(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom structural_agent_20261005 import host\nhost().task_runtime()\n');os.chmod(R/'bin/singularity',0o700)
    with (R/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    os.chmod(R/'.service.env',0o600);views=[]
    for j,seed in enumerate(c.SEEDS):
        for t,task in enumerate(c.TASKS):
            matches=[s for s in prior['schedule'] if s['task']==task and s['seed']==seed and s['arm']=='word'];assert len(matches)==1
            i=matches[0]['index'];rec=read(PREV/f'episode-{i}/action-0/receipt.json');pcfg=read(PREV/'configs'/f'{i}.json')
            public=Path(pcfg['task']['data_dir']);scorer=Path(pcfg['task']['search_only_dev_scorer_path'])
            assert sha(scorer)==pcfg['task']['search_only_dev_scorer_sha256'];spec=load('view_scorer',scorer).SPEC[task]
            manifest=B/spec['view']/'manifest.json';assert sha(manifest)==spec['view_sha']
            for n,h in read(manifest)['public_sha256'].items():assert sha(public/n)==h
            is_json=t==0;train_path=public/('train.json' if is_json else 'train.csv')
            df=pd.DataFrame(read(train_path)) if is_json else pd.read_csv(train_path)
            target='requester_received_pizza' if is_json else 'author';key='request_id' if is_json else 'id'
            y=df[target].astype(int).to_numpy() if is_json else df[target].to_numpy()
            a,b=train_test_split(np.arange(len(df)),test_size=.2,stratify=y,random_state=seed)
            assert hashlib.sha256(np.asarray(a,dtype='<i8').tobytes()+np.asarray(b,dtype='<i8').tobytes()).hexdigest()==rec['inner_split_sha256']
            root=R/'views'/f'{t}-{seed}';v=root/'public';v.mkdir(parents=True)
            train=df.iloc[a].reset_index(drop=True);query=df.iloc[b].drop(columns=[target]).reset_index(drop=True)
            if is_json:
                train.to_json(v/'train.json',orient='records');query.to_json(v/'test.json',orient='records')
            else:train.to_csv(v/'train.csv',index=False);query.to_csv(v/'test.csv',index=False)
            write(root/'truth.private.json',dict(task=task,ids=df.iloc[b][key].astype(str).tolist(),labels=y[b].tolist()))
            selected={**rec['selected']['params'],'arm':'word'};parent=c.source(task,selected)
            profile=[dict(params=r['params'],internal_metric=r['inner_oriented_score']*(1 if t==0 else -1)) for r in rec['rows']]
            write(R/'starts'/f'{t}-{seed}.private.json',dict(task=task,seed=seed,params=selected,code=parent,profile=profile,
                prior_receipt_sha256=sha(PREV/f'episode-{i}/action-0/receipt.json')))
            views.append(dict(task=task,seed=seed,train_rows=len(a),validation_rows=len(b),source_train_sha256=sha(train_path),split_sha256=rec['inner_split_sha256']))
    for s in c.schedule():
        ep=R/f"episode-{s['index']}";ep.mkdir();cfg=read(PREV/'configs'/f"{0 if s['task_index']==0 else 2}.json")
        cfg['id']='structural-agent-'+str(s['index']);cfg['logger'].update(output_dir=str(ep/'native-log'),write_env_vars=False,use_wandb=False,print_config=False,use_console=False)
        cfg['metadata'].update(seed=s['seed'],git_commit_id=commit,base_path=str(R/'source'),script_id='structural-agent-20261005')
        cfg['task']['data_dir']=cfg['task']['public_dir']=str(R/'views'/f"{s['task_index']}-{s['seed']}"/'public')
        cfg['task']['cache_dir']=str(R/'no-official-data');cfg['task']['private_dir']=str(R/'private-unavailable')
        cfg['interpreter'].update(timeout=120,working_dir=str(ep/'work'));cfg['interpreter']['env']['PYTHONHASHSEED']='42'
        write(R/'configs'/f"{s['index']}.json",cfg)
    batch=f'''#!/bin/bash
#SBATCH --job-name=structural-agent-three-arm
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:4
#SBATCH --cpus-per-task=24
#SBATCH --time=00:40:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 2320s {PY} -B {R}/{NAME} controller
''';(R/'run.sbatch').write_text(batch)
    write(R/'plan.json',dict(protocol='post-hpo-one-proposal-structural-capability-v1',source_commit=commit,schedule=c.schedule(),views=views,
        files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and p.name!='.service.env'},
        task_image_sha256=old['task_image_sha256'],service_image_sha256=old['service_image_sha256'],
        base=str(B/'models/Qwen3.5-9B-c202236'),base_revision='c202236235762e1c871ad0ccb60c8ee5ba337b9a',model_id='qwen3.5-9b',
        generation=dict(temperature=.7,top_p=.95,max_tokens=4096,timeout_seconds=120,enable_thinking=False),
        worker_seconds=360,search_seconds=240,final_refit_cap=90,allocation_seconds=2400,gpus=4,gpu_hours_cap=9600/3600,
        treatments='ordinary full-code modification vs same prompt plus current-word-family 28-row tuning profile vs fixed 56-point word/word+char grid; both agent arms unconstrained within allowed task data/libraries',
        initialization='shared prior training-only word-HPO selected source; NOT end-to-end from scratch. Common warmstart costs reported separately, excluded identically in all arms.',
        selection='execute parent on exact inner split; accept only strict inner improvement, retain incumbent otherwise; rerun selected code on full allowed train and external query. Refitting failure remains missing, not zero.',
        external_visibility='external development labels only after all12 close and prediction hashes frozen; not used by prompt, selection or HPO',
        primary='all four paired profile-minus-ordinary and profile-minus-open_hpo oriented external dev deltas; full denominator',
        gate='all12 complete and all four paired differences positive against BOTH controls; no automatic expansion',
        limitation='Two reused text development tasks and two overlapping internal splits, not clean test confirmation. One proposal only, not native full MCTS. Fixed open_hpo is a word/char grid, not all possible AutoML structures. Human-created positive structure not given to agent. Same caps, report actual total costs incl local LLM service. Shared warmstart was conditioned on earlier dev research, not pristine selection.',
        protected_opened=False,base_updated=False,paid_api=0))
    m=host();from dojo.config_dataclasses.run import RunConfig
    for s in c.schedule():
        cfg=RunConfig.load_from_json(R/'configs'/f"{s['index']}.json");cfg.validate();assert not Path(cfg.task.private_dir).exists() and not cfg.interpreter.read_only_binds
        start=read(R/'starts'/f"{s['task_index']}-{s['seed']}.private.json")
        if s['arm']!='open_hpo':
            msgs=c.messages(s['task'],s['arm'],start['code'],.5,start['profile']);assert not SECRET.search(json.dumps(msgs).encode())
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True);test=c.tests()
    write(R/'preflight.json',dict(**test,typed_configs=12,views=4,plan_sha256=sha(R/'plan.json')));print(json.dumps(dict(status='PREPARED',plan_sha256=sha(R/'plan.json'),test=test)))

def inner_score(task,prediction,truth):
    import numpy as np
    from sklearn.metrics import roc_auc_score
    with Path(prediction).open(newline='',encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    key='request_id' if task==c.TASKS[0] else 'id';rr={r[key]:r for r in rows};assert len(rr)==len(rows)==len(truth['ids']) and set(rr)==set(truth['ids'])
    if task==c.TASKS[0]:
        p=np.array([float(rr[i]['requester_received_pizza']) for i in truth['ids']]);assert np.isfinite(p).all()
        return float(roc_auc_score(truth['labels'],p))
    probs=np.array([[float(rr[i][k]) for k in ('EAP','HPL','MWS')] for i in truth['ids']]);assert np.isfinite(probs).all() and (probs>=0).all() and np.allclose(probs.sum(1),1,atol=1e-6)
    y=np.array([('EAP','HPL','MWS').index(t) for t in truth['labels']]);return float(-np.log(np.maximum(probs[np.arange(len(y)),y],1e-15)).mean())

def worker(i):
    p=check();m=host();x=m.infra();s=c.schedule()[i];ep=R/f'episode-{i}';own=x.native_uuids(1)
    assert not set(own)&set(read(R/'service-native.json')['gpu_uuids'])
    os.environ.update(DOJO_GPU_UUIDS=own[0],POLICY9B_EPISODE=str(ep),DOJO_WORKER_IDENTITY_PATH=str(ep/'identity.json'),
        DOJO_EXECUTION_ID=f'{os.environ["SLURM_JOB_ID"]}.{os.environ["SLURM_STEP_ID"]}:{i}',PATH=str(R/'bin')+':'+os.environ['PATH'])
    from dojo.main_local_worker import _process_start_ticks,_host_boot_id
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    from dojo.utils.logger import config_logger
    from dojo.utils.experiment_deadline import ExperimentDeadline
    from dojo.utils.code_parsing import extract_code
    write(ep/'identity.json',dict(pid=os.getpid(),pgid=os.getpgid(0),process_start_ticks=_process_start_ticks(os.getpid()),host_boot_id=_host_boot_id(),gpu_uuids=own,container_pid=None,container_process_start_ticks=None))
    write(ep/'native.json',dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],gpu_uuids=own))
    cfg=RunConfig.load_from_json(R/'configs'/f'{i}.json');Path(cfg.logger.output_dir).mkdir();config_logger(cfg)
    deadline=ExperimentDeadline(360);write(ep/'deadline.json',deadline.receipt());started=time.monotonic()
    start=read(R/'starts'/f"{s['task_index']}-{s['seed']}.private.json");truth=read(R/'views'/f"{s['task_index']}-{s['seed']}"/'truth.private.json')
    state=dict(**s,valid=False,source_commit=p['source_commit'],initial_inner=None,selected_inner=None,selected='incumbent',proposal_valid=False,
        proposal_inner=None,generation_seconds=0,search_seconds=None,refit_seconds=None,inner_trials=0,grid_complete=None,error_type=None)
    def execute(name,code,data,timeout,files):
        action=ep/name;(action/'work').mkdir(parents=True);write(action/'code.private.json',dict(code=code))
        icfg=copy.deepcopy(cfg.interpreter);icfg.working_dir=str(action/'work');icfg.timeout=max(1,int(min(timeout,deadline.remaining()-10)))
        interp=build(icfg,INTERPRETER_MAP,data_dir=str(data));begin=time.monotonic()
        try:
            output=interp.run(f'import random,numpy as np\nrandom.seed(42)\nnp.random.seed(42)\nexec(compile({code!r},"solution.py","exec"))',reset_session=False)
            write(action/'terminal.private.json',dict(terminal='\n'.join(output.term_out or [])))
            ok=output.exit_code==0 and not output.timed_out
            if ok:
                for n in files:
                    path=action/'work'/n;interp.fetch_file(path);assert path.is_file() and not path.is_symlink();shutil.copyfile(path,action/n)
            write(action/'result.json',dict(valid=ok,exit_code=output.exit_code,timed_out=output.timed_out,seconds=time.monotonic()-begin))
            return ok,action
        finally:interp.close()
    try:
        with deadline.activate():
            ok,ap=execute('parent',start['code'],cfg.task.data_dir,35,['submission.csv']);assert ok,'parent failed'
            best=inner_score(s['task'],ap/'submission.csv',truth);state['initial_inner']=best;chosen=start['code'];state['selected_inner']=best
            sign=1 if s['task_index']==0 else -1
            if s['arm']=='open_hpo':
                names=[f'candidate-{k}.csv' for k in range(56)]+['grid-receipt.json']
                ok,ap=execute('search',c.baseline(s['task']),cfg.task.data_dir,max(1,240-deadline.elapsed()),names)
                if ok:
                    rec=read(ap/'grid-receipt.json');assert len(rec['rows'])==56;state['grid_complete']=True
                    trials=[]
                    for k,row in enumerate(rec['rows']):
                        assert row['params']==c.GRID[k];v=inner_score(s['task'],ap/f'candidate-{k}.csv',truth)
                        trials.append(dict(index=k,params=row['params'],metric=v,converged=row['converged']))
                        if sign*(v-best)>0:best=v;chosen=c.source(s['task'],row['params']);state['selected']='grid-'+str(k)
                    state['inner_trials']=56;state['selected_inner']=best;write(ap/'inner-scores.private.json',trials)
                else:state['grid_complete']=False
            else:
                msgs=c.messages(s['task'],s['arm'],start['code'],best,start['profile']);write(ep/'prompt.private.json',dict(messages=msgs))
                begin=time.monotonic();response=None
                try:
                    response=m.api('/v1/chat/completions',dict(model='qwen3.5-9b',messages=msgs,temperature=.7,top_p=.95,max_tokens=4096,
                        seed=s['generation_seed'],chat_template_kwargs={'enable_thinking':False}),timeout=min(120,max(1,240-deadline.elapsed())))
                except Exception as exc:state['generation_error']=type(exc).__name__
                state['generation_seconds']=time.monotonic()-begin
                if response is not None:
                    assert response['model']=='qwen3.5-9b';write(ep/'generation.private.json',response)
                    try:
                        text=response['choices'][0]['message']['content'];code=extract_code(text)
                        ast.parse(code);assert code.strip()
                        assert not any(bad in code for bad in ('/research/','/etc/','urllib','requests.','socket.','from_pretrained','private/','dsearch.csv'))
                        ok,ap=execute('search',code,cfg.task.data_dir,max(1,min(120,240-deadline.elapsed())),['submission.csv'])
                        state['inner_trials']=1
                        if ok:
                            v=inner_score(s['task'],ap/'submission.csv',truth);state['proposal_valid']=True;state['proposal_inner']=v
                            if sign*(v-best)>0:chosen=code;best=v;state['selected']='proposal';state['selected_inner']=v
                    except (SyntaxError,AssertionError,ValueError,TypeError) as exc:state['proposal_error']=type(exc).__name__
            state['search_seconds']=deadline.elapsed();assert state['search_seconds']<=250
            write(ep/'selection.private.json',dict(code=chosen,inner_score=best,selected=state['selected'],code_sha256=hashlib.sha256(chosen.encode()).hexdigest(),elapsed=deadline.elapsed()))
            # Restore original allowed public train/query. No external labels read here.
            prior_cfg=read(PREV/'configs'/f"{0 if s['task_index']==0 else 2}.json")
            begin=time.monotonic();ok,ap=execute('final',chosen,prior_cfg['task']['data_dir'],90,['submission.csv']);state['refit_seconds']=time.monotonic()-begin
            if ok:state.update(valid=True,prediction_sha256=sha(ap/'submission.csv'))
    except Exception as exc:state['error_type']=type(exc).__name__
    state['elapsed_seconds']=time.monotonic()-started;write(ep/'completed.json',state)

def controller():
    check();m=host();job=os.environ['SLURM_JOB_ID'];assert socket.gethostname().split('.')[0]=='gpu27'
    for _ in range(20):
        if (R/'launch.json').exists():break
        time.sleep(.5)
    assert read(R/'launch.json')['job']==job;env=m.infra().clean_env();base=['srun','--exclusive','--nodes=1','--ntasks=1'];began=time.monotonic()
    with (R/'service.private.log').open('xb') as f:
        server=subprocess.Popen(base+['--cpus-per-task=12','--gres=gpu:2','--time=00:39:00',str(PY),'-B',str(R/NAME),'service'],env=env,stdout=f,stderr=f,start_new_session=True)
        try:
            while time.monotonic()-began<600:
                if server.poll() is not None:raise RuntimeError('service exited')
                try:
                    if m.health():break
                except Exception:pass
                time.sleep(3)
            else:raise TimeoutError('service readiness')
            write(R/'service-ready.json',dict(startup_seconds=time.monotonic()-began))
            def run(s):
                i=s['index'];ep=R/f'episode-{i}';write(ep/'launch.json',s)
                cmd=base+['--cpus-per-task=6','--gres=gpu:1','--time=00:07:00',str(PY),'-B',str(R/NAME),'worker','--index',str(i)]
                with (ep/'worker.private.log').open('xb') as log:q=subprocess.run(cmd,env=env,stdout=log,stderr=log)
                identity=read(ep/'identity.json')
                def gone(pid,ticks):
                    if pid is None:return True
                    try:
                        v=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split();return v[0]=='Z' or int(v[19])!=ticks
                    except FileNotFoundError:return True
                assert gone(identity['pid'],identity['process_start_ticks']) and gone(identity.get('container_pid'),identity.get('container_process_start_ticks')),'cleanup uncertain'
                own=read(ep/'native.json')['gpu_uuids'];apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True,timeout=10)
                assert not any(line.split(',')[0].strip() in own for line in apps.splitlines()),'worker GPU occupied'
                write(ep/'closed.json',dict(returncode=q.returncode,cleanup_certified=True));return i
            for wave in range(6):
                if CAP-(time.monotonic()-began)<440:raise TimeoutError('no whole next wave budget')
                if server.poll() is not None:raise RuntimeError('service lost')
                with ThreadPoolExecutor(max_workers=2) as pool:done=list(pool.map(run,[s for s in c.schedule() if s['wave']==wave]))
                write(R/f'wave-{wave}.json',dict(indices=done))
            write(R/'all-closed.json',dict(assigned=12))
        except Exception as exc:write(R/'controller-error.json',dict(error_type=type(exc).__name__));raise
        finally:
            if server.poll() is None:
                server.send_signal(signal.SIGTERM)
                try:server.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    step=read(R/'service-native.json')['step'];assert step.isdigit();subprocess.run(['scancel','--signal=KILL',job+'.'+step],check=True,timeout=30);server.wait(timeout=30)
            write(R/'closed.json',dict(service_closed=server.poll() is not None,elapsed=time.monotonic()-began))

def submit():
    p=check();m=host();assert read(R/'preflight.json')['plan_sha256']==sha(R/'plan.json')
    assert sha(m.TASK_IMAGE)==p['task_image_sha256'] and sha(m.VLLM)==p['service_image_sha256']
    env=m.infra().clean_env();jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=25).split();assert not set(jobs)-{'12535'}
    with (R/'capacity.tmp').open('xb') as f:os.posix_fallocate(f.fileno(),0,128*1024**2)
    (R/'capacity.tmp').unlink();write(R/'submit-intent.json',dict(plan_sha256=sha(R/'plan.json')))
    q=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),'--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=q.stdout.strip().split(';')[0];assert q.returncode==0 and job.isdigit(),'ambiguous submit; no retry'
    write(R/'launch.json',dict(job=job,plan_sha256=sha(R/'plan.json')));print(json.dumps(dict(status='SUBMITTED',job=job,gpu_hours_cap=p['gpu_hours_cap'])))
def status():
    check();print(json.dumps(dict(launch=read(R/'launch.json') if (R/'launch.json').exists() else None,service_ready=(R/'service-ready.json').exists(),closed=(R/'closed.json').exists(),
        controller_error=read(R/'controller-error.json') if (R/'controller-error.json').exists() else None,
        episodes=[dict(index=i,started=(R/f'episode-{i}/native.json').exists(),completed=(R/f'episode-{i}/completed.json').exists()) for i in range(12)])))
if __name__=='__main__':
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','submit','worker','service','controller','status']);p.add_argument('--commit');p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='worker':worker(a.index)
    elif a.mode=='service':host().service()
    else:globals()[a.mode]()
