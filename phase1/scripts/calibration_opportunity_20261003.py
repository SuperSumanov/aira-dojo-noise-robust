"""One-dimensional public-OOF calibration opportunity, not a new agent method.

The parent program is unchanged. A task-local scalar is learned only from its
public OOF predictions. Original and calibrated submissions are frozen before
any external development scoring. No generator, paid API or base-model update.
"""
import argparse,ast,copy,hashlib,importlib.util,json,os,shutil,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
B=Path('/research/d7/spc/yzyang4');PARENT=B/'state-feedback-factorial-20261002-v1'
ROOT=B/'calibration-opportunity-20261003-v1';PY=B/'venvs/aira/bin/python'
COMMIT='8ec74c5a4e7eaaa334a7f0f34dbfd220120e6a02';SEEDS=(103801,103802,103803)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def write(p,x):
    with Path(p).open('x') as f:json.dump(x,f,sort_keys=True,indent=2,allow_nan=False)
def runtime():
    p=ROOT/'v6_runtime.py';assert sha(p)=='4b155d927c12f063e0838b5708085fe1bc55c4983197a3d8d2453696d73c55ad'
    s=importlib.util.spec_from_file_location('calibration_runtime',p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
    m.ROOT=ROOT;m.infra.ROOT=ROOT;m.setup();return m
def tail():
    return '''
import json as _j, shutil as _sh, hashlib as _h
from scipy.special import logsumexp as _lse
from scipy.optimize import minimize_scalar as _min
from pathlib import Path as _P
_begin=time.monotonic()
_oof=safe_clip((1-best_w)*oof_tfidf_c+best_w*oof_emb_c)
_log=np.log(np.clip(_oof,1e-15,1))
def _obj(beta):
    z=beta*_log
    return float(np.mean(_lse(z,axis=1)-z[np.arange(len(y_train)),y_train]))
_opt=_min(_obj,bounds=(.25,4.),method='bounded',options={'xatol':1e-9,'maxiter':100})
assert _opt.success and np.isfinite(_opt.fun)
# Identity is in the search class and wins ties. No hidden score enters this choice.
_beta=float(_opt.x) if _obj(float(_opt.x))<_obj(1.) else 1.
_z=_beta*np.log(np.clip(test_prob_final,1e-15,1))
_pred=np.exp(_z-_lse(_z,axis=1)[:,None])
assert np.isfinite(_pred).all() and np.allclose(_pred.sum(1),1)
_sh.copyfile('submission.csv','original.csv')
_cal=submission.copy()
_cal[classes]=_pred
_cal.to_csv('calibrated.csv',index=False)
np.savez('public-calibration.private.npz',oof=_oof,labels=y_train,query_original=test_prob_final,query_calibrated=_pred)
_receipt=dict(beta=_beta,temperature=1/_beta,public_original_loss=_obj(1.),public_calibrated_loss=_obj(_beta),
    public_gradient_at_identity=float(np.mean(np.sum(_oof*_log,axis=1)-_log[np.arange(len(y_train)),y_train])),
    best_embedding_weight=float(best_w),public_rows=len(y_train),query_rows=len(_pred),classes=classes,
    calibration_seconds=time.monotonic()-_begin,
    files={n:_h.sha256(_P(n).read_bytes()).hexdigest() for n in ['original.csv','calibrated.csv','public-calibration.private.npz']})
with open('calibration-receipt.json','x') as _f:_j.dump(_receipt,_f,sort_keys=True)
print('CALIBRATION_OPPORTUNITY_DONE')
'''
def check():
    p=read(ROOT/'plan.json')
    for f,h in p['files'].items():assert sha(ROOT/f)==h,f
    return p
def prepare():
    assert not ROOT.exists()
    assert sha(PARENT/'plan.json')=='2820d6cc64d9d1045179f2290383340c38605b6ba604364d8fd6307be2a0b237'
    p=read(PARENT/'plan.json');ROOT.mkdir(mode=0o700)
    for rel,h in p['files'].items():
        if not(rel.startswith(('source/','forets_','opencl-vendors/')) or rel=='v6_runtime.py'):continue
        assert sha(PARENT/rel)==h
        target=ROOT/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(PARENT/rel,target)
    shutil.copyfile(__file__,ROOT/Path(__file__).name)
    (ROOT/'bin').mkdir();(ROOT/'configs').mkdir();(ROOT/'starts').mkdir()
    raw=(PARENT/'starts/1.private.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='bca4cc6a4df9d7b8e565ec64d7fd2dc09239f2defac1e43b819600528eee74dd'
    (ROOT/'starts/parent.private.json').write_bytes(raw)
    wrapper=f'#!{PY}\nimport sys\nsys.path.insert(0,{str(ROOT)!r})\nfrom calibration_opportunity_20261003 import runtime\nruntime().task_runtime()\n'
    (ROOT/'bin/singularity').write_text(wrapper);os.chmod(ROOT/'bin/singularity',0o700)
    for i,seed in enumerate(SEEDS):
        cfg=read(PARENT/'configs/1.json');(ROOT/f'episode-{i}').mkdir()
        cfg['id']=f'calibration-opportunity-{i}';cfg['logger']['output_dir']=str(ROOT/f'episode-{i}/native-log')
        cfg['metadata'].update(seed=seed,base_path=str(ROOT/'source'),git_commit_id=COMMIT,script_id='calibration-opportunity-20261003')
        cfg['interpreter']['env']['PYTHONHASHSEED']=str(seed);cfg['task']['cache_dir']=str(ROOT/'no-official-data')
        write(ROOT/'configs'/f'{i}.json',cfg)
    batch=f'''#!/bin/bash
#SBATCH --job-name=calibration-opportunity
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=12
#SBATCH --time=00:20:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 1140s {PY} -B {ROOT}/calibration_opportunity_20261003.py controller
'''
    (ROOT/'run.sbatch').write_text(batch)
    write(ROOT/'plan.json',dict(protocol='public-oof-scalar-calibration-opportunity-v1',commit=COMMIT,
        files={str(f.relative_to(ROOT)):sha(f) for f in ROOT.rglob('*') if f.is_file()},seeds=SEEDS,
        task='spooky-author-identification',runs=3,task_program_executions=3,submissions=6,execution_cap=300,
        allocation_seconds=1200,gpus=2,gpu_hours_cap=2*1200/3600,paid_api=0,generator_calls=0,
        parameter='inverse temperature beta in [.25,4], bounded minimization of public OOF logloss; identity fallback',
        endpoint='paired original minus calibrated external development logloss; median and sample variance',
        expansion_gate='all 3 paired valid, median improvement >0 and no negative run; mechanism/novelty and E2E separately required',
        limitations='Known calibration, not novel method or agent benefit. Historical selected parent and reused development set. Internal classifier/CV seed remains42; outer seeds may not create independent predictions. OOF used for parent selection, not independent validation. Embedding may vary. No final test.',
        protected_opened=False,base_model_updated=False))
    cpu()
def cpu():
    import numpy as np
    from scipy.special import logsumexp
    from scipy.optimize import minimize_scalar
    from sklearn.metrics import roc_auc_score
    p=check();m=runtime();from dojo.config_dataclasses.run import RunConfig
    for i in range(3):
        c=RunConfig.load_from_json(ROOT/'configs'/f'{i}.json');c.validate()
        assert not Path(c.task.private_dir).exists() and c.interpreter.env['OMP_NUM_THREADS']=='6'
    code=read(ROOT/'starts/parent.private.json')['code'];assert ast.dump(ast.parse(code+tail()).body[0])==ast.dump(ast.parse(code).body[0])
    assert ast.dump(ast.Module(body=ast.parse(code+tail()).body[:len(ast.parse(code).body)],type_ignores=[]))==ast.dump(ast.parse(code))
    # Calibrator must improve a known over-confident distribution and preserve class argmax.
    logits=np.tile([4.,0.,-1.],(100,1));labels=np.array([0]*60+[1]*30+[2]*10)
    f=lambda b:float(np.mean(logsumexp(b*logits,axis=1)-(b*logits)[np.arange(100),labels]))
    opt=minimize_scalar(f,bounds=(.25,4),method='bounded');assert opt.success and f(opt.x)<f(1)
    pred=np.linspace(.01,.99,100);truth=np.arange(100)%2
    for b in (.25,.5,2,4):
        transformed=1/(1+np.exp(-b*np.log(pred/(1-pred))))
        assert roc_auc_score(truth,pred)==roc_auc_score(truth,transformed)
    subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    out=dict(status='PASS',typed_configs=3,parent_ast_unchanged=True,calibration_fixture=True,auc_invariance_fixtures=4,plan_sha256=sha(ROOT/'plan.json'))
    write(ROOT/'cpu.json',out);print(json.dumps(out))
def submit():
    check();m=runtime();assert not (ROOT/'submit-intent.json').exists()
    assert read(ROOT/'cpu.json')['plan_sha256']==sha(ROOT/'plan.json') and sha(m.infra.TASK_IMAGE)==m.infra.IMAGE_SHA
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=25).split();assert not set(jobs)-{'12535'}
    with (ROOT/'capacity.tmp').open('xb') as f:os.posix_fallocate(f.fileno(),0,256*1024**2)
    (ROOT/'capacity.tmp').unlink();write(ROOT/'submit-intent.json',dict(utc=m.utc(),plan_sha256=sha(ROOT/'plan.json')))
    r=subprocess.run(['sbatch','--parsable','--chdir='+str(ROOT),'--output='+str(ROOT/'allocation-%j.out'),'--error='+str(ROOT/'allocation-%j.err'),str(ROOT/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=r.stdout.strip().split(';')[0]
    if r.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; no retry')
    write(ROOT/'launch.json',dict(job=job,plan_sha256=sha(ROOT/'plan.json')));print(json.dumps(dict(status='SUBMITTED',job=job,gpu_hours_cap=2/3)))
def worker(i):
    check();m=runtime();ep=ROOT/f'episode-{i}';seed=SEEDS[i];own=m.infra.native_uuids(1)
    os.environ.update(DOJO_GPU_UUIDS=own[0],DOJO_WORKER_IDENTITY_PATH=str(ep/'identity.json'),DOJO_EXECUTION_ID=f'{os.environ["SLURM_JOB_ID"]}.{os.environ["SLURM_STEP_ID"]}:{i}',PATH=str(ROOT/'bin')+':'+os.environ['PATH'])
    from dojo.main_local_worker import _process_start_ticks,_host_boot_id
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    from dojo.utils.logger import config_logger
    from dojo.utils.experiment_deadline import ExperimentDeadline
    write(ep/'identity.json',dict(pid=os.getpid(),pgid=os.getpgid(0),process_start_ticks=_process_start_ticks(os.getpid()),host_boot_id=_host_boot_id(),gpu_uuids=own,container_pid=None,container_process_start_ticks=None))
    write(ep/'native.json',dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],gpu_uuids=own))
    cfg=RunConfig.load_from_json(ROOT/'configs'/f'{i}.json');Path(cfg.logger.output_dir).mkdir();config_logger(cfg)
    action=ep/'action-0';(action/'work').mkdir(parents=True);os.environ['FEEDBACK_ACTION_ROOT']=str(action)
    icfg=copy.deepcopy(cfg.interpreter);icfg.working_dir=str(action/'work');icfg.timeout=300
    code=read(ROOT/'starts/parent.private.json')['code'];executable=f'import random, numpy as np\nrandom.seed({seed})\nnp.random.seed({seed})\nexec(compile({(code+tail())!r},"parent_and_calibration.py","exec"))\n'
    began=time.monotonic();valid=False;error_type=None;out=None
    with ExperimentDeadline(500).activate():
        interp=build(icfg,INTERPRETER_MAP,data_dir=cfg.task.data_dir)
        try:
            out=interp.run(executable,reset_session=False);terminal='\n'.join(out.term_out or [])
            if m.SECRET.search(terminal.encode()):raise ValueError('credential-shaped output')
            write(action/'terminal.private.json',dict(terminal=terminal))
            if out.exit_code==0 and not out.timed_out:
                for name in ('original.csv','calibrated.csv','public-calibration.private.npz','calibration-receipt.json'):
                    path=action/'work'/name;interp.fetch_file(path);assert path.is_file() and not path.is_symlink()
                    shutil.copyfile(path,action/name)
                receipt=read(action/'calibration-receipt.json')
                for name,h in receipt['files'].items():assert sha(action/name)==h
                valid=True
        except Exception as e:error_type=type(e).__name__
        finally:interp.close()
    write(action/'result.json',dict(index=i,seed=seed,valid=valid,exit_code=out.exit_code if out else None,timed_out=out.timed_out if out else None,
        error_type=error_type,seconds=time.monotonic()-began,plan_sha256=sha(ROOT/'plan.json'),commit=COMMIT))
    write(ep/'completed.json',dict(status='complete',valid=valid))
def controller():
    check();m=runtime();assert read(ROOT/'launch.json')['job']==os.environ['SLURM_JOB_ID']
    def run(i):
        ep=ROOT/f'episode-{i}';cmd=['srun','--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=6','--gres=gpu:1','--time=00:09:00',str(PY),'-B',str(ROOT/'calibration_opportunity_20261003.py'),'worker','--index',str(i)]
        with (ep/'worker.private.log').open('xb') as f:r=subprocess.run(cmd,env=m.infra.clean_env(),stdout=f,stderr=f,timeout=550)
        write(ep/'closed.json',dict(returncode=r.returncode));return r.returncode
    with ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(run,range(3)))
    write(ROOT/'closed.json',dict(returncodes=codes,utc=m.utc()))
    if any(codes):raise RuntimeError('worker failure')
def status():
    check();print(json.dumps(dict(launched=read(ROOT/'launch.json') if (ROOT/'launch.json').exists() else None,closed=(ROOT/'closed.json').exists(),
        episodes=[dict(index=i,started=(ROOT/f'episode-{i}/native.json').exists(),completed=(ROOT/f'episode-{i}/completed.json').exists()) for i in range(3)])))
if __name__=='__main__':
    os.umask(0o077);a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','submit','controller','worker','check','status']);a.add_argument('--index',type=int);x=a.parse_args()
    if x.mode=='worker':worker(x.index)
    else:globals()[x.mode]()
