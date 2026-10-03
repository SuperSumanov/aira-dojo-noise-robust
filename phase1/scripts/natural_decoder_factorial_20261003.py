"""Pre-score supplement: joint natural decoder defects, preserving original gate."""
import argparse,ast,copy,csv,hashlib,importlib.util,json,os,shutil,subprocess,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
B=Path('/research/d7/spc/yzyang4');OLD=B/'natural-opportunity-20261003-v1';R=B/'natural-decoder-factorial-20261003-v1';PY=B/'venvs/aira/bin/python'
sys.path.insert(0,str(OLD))
import natural_opportunity_20261003 as m
m.ROOT=R
def schedule():return [dict(index=i,state=5,seed=seed,arm=arm,pair=i//2) for i,(seed,arm) in enumerate([(42,'axis_only'),(42,'joint'),(173,'joint'),(173,'axis_only')])]
m.schedule=schedule

def prepare():
    assert not R.exists() and not (OLD/'readout.json').exists()
    assert m.sha(OLD/'plan.json')=='39948b4a517cdb609105f099231bb9c3d1c19214754d585a6365245635b903df'
    contract=m.read(OLD/'decoder-contract-pre-score.json');assert contract['status']=='PASS'
    R.mkdir(mode=0o700)
    for f,h in m.read(OLD/'plan.json')['files'].items():
        if not (f.startswith(('source/','forets_','opencl-vendors/')) or f in ('v6_runtime.py','natural_opportunity_20261003.py','starts/5.py')):continue
        assert m.sha(OLD/f)==h;p=R/f;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(OLD/f,p)
    shutil.copyfile(__file__,R/Path(__file__).name)
    for name in ('configs','programs','bin'):(R/name).mkdir()
    wrapper=f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom natural_decoder_factorial_20261003 import m\nm.runtime().task_runtime()\n'
    (R/'bin/singularity').write_text(wrapper);os.chmod(R/'bin/singularity',0o700)
    raw=(OLD/'starts/5.py').read_text();assert raw.count('e = e_logit[:tl, None]')==1
    programs=[]
    for s in schedule():
        code=raw.replace('e = e_logit[:tl, None]','e = e_logit[None, :tl]')
        if s['arm']=='joint':code=code.replace('np.tril(np.ones((tl, tl), dtype=bool))','np.triu(np.ones((tl, tl), dtype=bool))')
        code,count=m.seeded(code,s['seed']);ast.parse(code);p=R/'programs'/f'{s["index"]}.private.py';p.write_text(code)
        ep=R/f'episode-{s["index"]}';ep.mkdir();cfg=m.read(OLD/'starts/5.config.private.json')
        cfg['id']=f'natural-decoder-{s["index"]}';cfg['logger'].update(output_dir=str(ep/'native-log'),write_env_vars=False,use_wandb=False,use_console=False,print_config=False)
        cfg['metadata'].update(seed=s['seed'],base_path=str(R/'source'),git_commit_id=m.COMMIT,script_id='natural-decoder-20261003')
        cfg['interpreter']['env'].update(PYTHONHASHSEED=str(s['seed']),OMP_NUM_THREADS='6',OPENBLAS_NUM_THREADS='6',MKL_NUM_THREADS='6',NUMEXPR_NUM_THREADS='6')
        cfg['task']['cache_dir']=str(R/'no-official-data');m.write(R/'configs'/f'{s["index"]}.json',cfg)
        programs.append(dict(**s,task=cfg['task']['name'],code_sha256=m.sha(p),rng_sites=count))
    batch=(OLD/'run.sbatch').read_text().replace(str(OLD),str(R)).replace('natural-opportunity','natural-decoder').replace('01:30:00','00:20:00').replace('5340s','1140s').replace('natural_opportunity_20261003.py controller','natural_decoder_factorial_20261003.py controller')
    (R/'run.sbatch').write_text(batch)
    m.write(R/'plan.json',dict(protocol='natural-decoder-joint-defect-development-v1',utc=m.utc(),commit=m.COMMIT,schedule=schedule(),programs=programs,
        files={str(p.relative_to(R)):m.sha(p) for p in R.rglob('*') if p.is_file()},task_execution_seconds=300,worker_seconds=450,allocation_seconds=1200,gpus=2,gpu_hours_cap=2/3,
        total_window_gpu_hours_cap=3,original_plan_sha256=m.sha(OLD/'plan.json'),contract_sha256=m.sha(OLD/'decoder-contract-pre-score.json'),
        pre_score=not (OLD/'readout.json').exists(),paid_api=0,generator_calls=0,base_updates=0,
        analysis='Retain original 20-run gate unchanged. Add 4 runs to complete same-state 2x2 axis x mask. Joint improvement must exceed both original and full-text reference by >=.01 for both RNG settings. Report interaction, all cells, seed spread, and neutral-copy postprocessing of original/joint. New supplemental pilot, not original cross-task gate.',
        limitations='One previously inspected natural development state; not a new method. Late pre-outcome amendment motivated by pure code mathematics. No scores read before freeze. Same budget per execution; extra discovery/training cost fully retained.'))
    m.runtime()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    for s in schedule():
        c=RunConfig.load_from_json(R/'configs'/f'{s["index"]}.json');c.validate();t=MLEBenchTask(c.task);assert t._search_only_score and not t.private_dir.exists()
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    m.write(R/'cpu.json',dict(status='PASS',configs=4,plan_sha256=m.sha(R/'plan.json')))
    print(json.dumps(dict(status='PREPARED_PRE_SCORE',runs=4,plan_sha256=m.sha(R/'plan.json'))))

def submit():
    m.check();assert m.read(R/'cpu.json')['plan_sha256']==m.sha(R/'plan.json')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf');job=m.read(OLD/'launch.json')['job']
    raw=subprocess.check_output(['sacct','-X','-j',job,'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES'],env=env,text=True,timeout=25)
    line=next(x for x in raw.splitlines() if x.split('|')[0]==job);j,state,elapsed,tres,*_=line.split('|')
    assert state=='COMPLETED' and 'gres/gpu=2' in tres and 2*int(elapsed)+2400<=3*3600
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=25).split();assert not set(jobs)-{'12535'}
    m.write(R/'submit-intent.json',dict(utc=m.utc(),prior_elapsed_seconds=int(elapsed),combined_cap_gpu_hours=(2*int(elapsed)+2400)/3600))
    r=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),'--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=r.stdout.strip().split(';')[0];assert r.returncode==0 and job.isdigit(),'ambiguous: do not retry'
    m.write(R/'launch.json',dict(job=job,utc=m.utc(),plan_sha256=m.sha(R/'plan.json')));print(json.dumps(dict(job=job,status='SUBMITTED',combined_gpu_hours_cap=(2*int(elapsed)+2400)/3600)))

def controller():
    m.check();assert m.read(R/'launch.json')['job']==os.environ['SLURM_JOB_ID'];rt=m.runtime()
    def pair(k):
        rc=[]
        for s in [s for s in schedule() if s['pair']==k]:
            ep=R/f'episode-{s["index"]}'
            cmd=['srun','--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=6','--gres=gpu:1','--time=00:07:30',str(PY),'-B',str(R/'natural_decoder_factorial_20261003.py'),'worker','--index',str(s['index'])]
            with (ep/'worker.private.log').open('xb') as f:r=subprocess.run(cmd,env=rt.infra.clean_env(),stdout=f,stderr=f,timeout=480)
            m.write(ep/'closed.json',dict(returncode=r.returncode));rc.append(r.returncode)
        return rc
    with ThreadPoolExecutor(max_workers=2) as pool:rc=list(pool.map(pair,range(2)))
    m.write(R/'closed.json',dict(returncodes=rc,utc=m.utc()));assert all(c==0 for x in rc for c in x)

if __name__=='__main__':
    os.umask(0o077);a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','submit','worker','controller','status']);a.add_argument('--index',type=int);x=a.parse_args()
    if x.mode=='worker':m.worker(x.index)
    elif x.mode=='status':m.status()
    else:globals()[x.mode]()
