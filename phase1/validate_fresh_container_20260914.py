"""Real public-task parity and two-process integration; no model or grade calls."""
import argparse,datetime as dt,hashlib,json,logging,os,re,shutil,socket,subprocess,sys,tempfile,time
from pathlib import Path
BASE=Path('/research/d7/spc/yzyang4')
SOURCE=BASE/'forets-wallclock-20260912-88v5m9dr/source'
DONOR=BASE/'forets-process-transport-20260914-83zx3mg1'
TREE='8bb325fa167a9db54656dd6535ce1f3d69859c22'
HELPERS=('forets_closed_pool_native_20260911.py','forets_current_pool_native_20260912.py',
    'forets_gpu_binding_20260911.py','forets_native_cuda_identity_20260911.py','forets_native_gpu_binding_20260911.py',
    'forets_opencl_allowlist_20260911.py','forets_opencl_readonly_ab.py','forets_closed_pool_20260911.py','bin/singularity')
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_bytes())
def utc():return dt.datetime.now(dt.timezone.utc).isoformat()
def write(p,v):
    raw=(json.dumps(v,sort_keys=True,allow_nan=False)+'\n').encode()
    if SECRET.search(raw):raise ValueError('credential-shaped receipt')
    with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return sha(raw)
def root_check(p):
    p=p.resolve(strict=True)
    if p.parent!=BASE or not re.fullmatch(r'forets-fresh-integration-20260914-[a-z0-9_]+',p.name):raise ValueError('root scope')
    return p
def binding_context(env):
    r=root_check(Path(env['FORETS_CURRENT_POOL_ROOT']));p=Path(env['DOJO_WORKER_IDENTITY_PATH'])
    if p.parent!=r or not re.fullmatch(r'identity-[0-9]+\.json',p.name):raise ValueError('identity scope')
    if read(r/'execution.claim.json')['job']!=env['SLURM_JOB_ID']:raise ValueError('allocation mismatch')
    return p.with_suffix('.native-binding.json')
def checked(root):
    root_check(root);p=read(root/'prepared.json')
    for n,h in p['files'].items():
        if sha((root/n).read_bytes())!=h:raise ValueError('code drift')
    a=read(SOURCE.parent/'artifact.json')
    if a['source_tree']!=TREE:raise ValueError('source identity')
    for n,h in a['source_files'].items():
        if sha((SOURCE/n).read_bytes())!=h:raise ValueError('active source drift')
    return p
def prepare(commit):
    if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('commit')
    if read(DONOR/'result.json')['status']!='PASS_DIAGNOSTIC_NOT_DEPLOYED':raise ValueError('prior diagnostic failed')
    prior=read(DONOR/'prepared.json');root=Path(tempfile.mkdtemp(prefix='forets-fresh-integration-20260914-',dir=BASE))
    for n in HELPERS:
        raw=(DONOR/n).read_bytes()
        if sha(raw)!=prior['files'][n]:raise ValueError('helper drift')
        out=root/n;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(DONOR/n,out)
    for n in ('validate_fresh_container_20260914.py','forets_process_interpreter_20260914.py','FRESH_CONTAINER_INTEGRATION_PLAN_20260914.md'):
        shutil.copy2(Path(__file__).with_name(n),root/n)
    (root/'forets_current_pool_20260912.py').write_text('from validate_fresh_container_20260914 import binding_context\n')
    (root/'opencl-vendors').mkdir();(root/'opencl-vendors/nvidia.icd').write_text('libnvidia-opencl.so.1\n')
    script='''#!/bin/bash
#SBATCH --job-name=fresh-container-integration
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --time=00:45:00
#SBATCH --no-requeue
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1
export PYTHONDONTWRITEBYTECODE=1
srun --exclusive --ntasks=1 --cpus-per-task=6 --gres=gpu:1 --time=00:44:00 timeout --signal=TERM --kill-after=10s 2500s /research/d7/spc/yzyang4/venvs/aira/bin/python -B ROOT/validate_fresh_container_20260914.py execute --root ROOT
'''.replace('ROOT',str(root));(root/'run.sbatch').write_text(script)
    files={str(p.relative_to(root)):sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
    h=write(root/'prepared.json',dict(commit=commit,source_tree=TREE,utc=utc(),files=files,api_calls=0,
        real_task_executions=8,synthetic_concurrent_calls=24,gpu_hours_cap=.75,code_timeout=90,
        active_source_changed=False,task_labels='public training only',external_grading=False))
    print(json.dumps(dict(root=str(root),prepared_sha256=h)))
def setup(root,p):
    if socket.gethostname().split('.')[0]!='gpu28' or not os.environ.get('SLURM_STEP_ID','').isdigit():raise ValueError('gpu28 allocation')
    for k in ('OPENROUTER_API_KEY','PRIMARY_KEY','FORETS_NATIVE_RELEASE','FORETS_CLOSED_POOL_ROOT'):os.environ.pop(k,None)
    os.environ.update(PYTHON_DOTENV_DISABLED='1',LOGGING_DIR=str(root),MLE_BENCH_DATA_DIR=str(BASE/'mle-bench-data'),
        SUPERIMAGE_DIR=str(BASE/'aira-dojo/build/superimage'),DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',
        DEFAULT_SLURM_QOS='gpu',FORETS_CURRENT_POOL_ROOT=str(root),FORETS_SOURCE_COMMIT=p['commit'],
        PATH=str(root/'bin')+':'+os.environ['PATH'],NO_PROXY='localhost,127.0.0.1,0.0.0.0')
    sys.path[:0]=[str(root),str(SOURCE/'src')];logging.disable(logging.CRITICAL)
    from forets_opencl_allowlist_20260911 import IMAGE
    st=IMAGE.stat()
    if (st.st_size,st.st_mtime_ns)!=(19717783552,1784638286000000000):raise ValueError('image drift')
def cfg_for(root,index):
    from dojo.config_dataclasses.interpreter.jupyter import JupyterInterpreterConfig
    from forets_opencl_allowlist_20260911 import IMAGE
    work=root/f'work-{index}';work.mkdir();identity=root/f'identity-{index}.json';write(identity,{})
    os.environ['DOJO_WORKER_IDENTITY_PATH']=str(identity)
    cfg=JupyterInterpreterConfig(working_dir=str(work),timeout=90,strip_ansi=True,container_runtime='singularity',
        superimage_directory=str(IMAGE.parent),superimage_version='2026-07-macos-v1',
        env={'HF_HUB_OFFLINE':'0','NLTK_DATA':'/root/.nltk_data'})
    cfg.validate();return cfg
def one(root,index,backend,task=None,code=None):
    from dojo.core.interpreters.jupyter.jupyter_interpreter import JupyterInterpreterFactory
    from forets_process_interpreter_20260914 import FreshContainerInterpreter
    cfg=cfg_for(root,index);public=BASE/'mle-bench-data'/task/'prepared/public' if task else None
    factory=FreshContainerInterpreter if backend=='fresh' else JupyterInterpreterFactory
    worker=None;row=dict(index=index,backend=backend,task=task,status='infrastructure_unknown');start=time.monotonic()
    try:
        worker=factory(cfg,data_dir=public)
        if task:
            from dojo.solvers.fore_ts.edit_scope import code_for
            code=code_for(task)
        ans=worker.run(code,file_name='solution.py',include_exec_time=False)
        raw=''.join(ans.term_out).encode()
        if SECRET.search(raw):raise ValueError('credential shape in diagnostic output')
        (root/f'output-{index}.private.log').write_bytes(raw)
        row.update(exit_code=ans.exit_code,timed_out=ans.timed_out,status='completed' if ans.exit_code==0 and not ans.timed_out else 'code_failed')
        if task and row['status']=='completed':
            path=worker.fetch_file(Path(cfg.working_dir)/'submission.csv')
            row['submission_present']=path is not None
            if path:row['submission_sha256']=sha(Path(path).read_bytes())
        if not task:row['marker_count']=raw.count(b'FRESH_INTEGRATION_OK')
    except Exception as exc:row.update(status='infrastructure_unknown',error_type=type(exc).__name__)
    finally:
        if worker is not None:
            try:worker.close()
            except Exception as exc:row.update(status='cleanup_unknown',cleanup_error=type(exc).__name__)
        row['elapsed_seconds']=time.monotonic()-start;write(root/f'case-{index}.json',row)
    return row
def concurrent(root,slot):
    p=checked(root);setup(root,p)
    for j in range(12):
        r=one(root,100*(slot+1)+j,'fresh',code="x=3\nassert x==3\nprint('FRESH_INTEGRATION_OK')")
        if r['status']!='completed' or r['marker_count']!=1:raise RuntimeError('concurrent fresh process failed')
def execute(root):
    p=checked(root);setup(root,p);write(root/'execution.claim.json',dict(job=os.environ['SLURM_JOB_ID'],utc=utc()))
    rows=[];pairs=[];use_jupyter=True;started=time.monotonic()
    for repeat in range(2):
        for ti,task in enumerate(('leaf-classification','spaceship-titanic')):
            pair={}
            for mode in (('fresh','jupyter') if (repeat+ti)%2==0 else ('jupyter','fresh')):
                if time.monotonic()-started>1800:raise RuntimeError('integration time budget')
                if mode=='jupyter' and not use_jupyter:continue
                row=one(root,len(rows),mode,task=task);rows.append(row);pair[mode]=row
                if mode=='jupyter' and row['status']!='completed':use_jupyter=False
            if set(pair)=={'fresh','jupyter'} and all(r.get('submission_present') for r in pair.values()):
                import pandas as pd,numpy as np
                a,b=[pd.read_csv(root/f'work-{pair[k]["index"]}'/'submission.csv') for k in ('fresh','jupyter')]
                same_shape=a.shape==b.shape and list(a.columns)==list(b.columns);equal=same_shape
                if same_shape:
                    for c in a:
                        if pd.api.types.is_numeric_dtype(a[c]) and not pd.api.types.is_bool_dtype(a[c]):
                            equal=equal and bool(np.allclose(a[c],b[c],rtol=0,atol=1e-12,equal_nan=False))
                        else:equal=equal and a[c].equals(b[c])
                pairs.append(dict(task=task,repeat=repeat,equal_predictions=bool(equal),same_shape=bool(same_shape)))
    children=[];logs=[]
    try:
        for slot in range(2):
            log=(root/f'concurrent-{slot}.private.log').open('xb');logs.append(log)
            children.append(subprocess.Popen([sys.executable,'-B',str(root/Path(__file__).name),'concurrent','--root',str(root),'--slot',str(slot)],stdout=log,stderr=log))
        codes=[child.wait(timeout=450) for child in children]
    finally:
        for child in children:
            if child.poll() is None:child.terminate();child.wait(timeout=5)
        for log in logs:log.close()
    parallel=[read(root/f'case-{i}.json') for i in list(range(100,112))+list(range(200,212)) if (root/f'case-{i}.json').exists()]
    magic=one(root,300,'fresh',code="%%capture diagnostic_capture\nprint('captured')\n")
    fresh=[r for r in rows if r['backend']=='fresh']
    conditions=dict(all_real_fresh_complete=len(fresh)==4 and all(r['status']=='completed' and r.get('submission_present') for r in fresh),
        all_real_pairs_equal=len(pairs)==4 and all(r['equal_predictions'] for r in pairs),
        two_process_calls_complete=codes==[0,0] and len(parallel)==24 and all(r['status']=='completed' and r['marker_count']==1 for r in parallel),
        ipython_magic_supported=magic['status']=='completed')
    result=dict(status='PASS_INTEGRATION_NOT_DEPLOYED' if all(conditions.values()) else 'INTEGRATION_INCOMPLETE_OR_FAILED',
        utc=utc(),conditions=conditions,rows=rows,parallel=parallel,paired=pairs,magic=magic,seconds=time.monotonic()-started,
        api_calls=0,external_grading=False,active_source_changed=False,commit=p['commit'],source_tree=TREE,
        limitation='Fixed shared RF outputs and isolated IPython calls only; not e2e efficacy or all possible generated-code semantics.')
    write(root/'result.json',result);print(json.dumps(result),flush=True)
def submit(root):
    p=checked(root);env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    q=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=20)
    if len(q.strip().splitlines())>=4:raise ValueError('job quota')
    write(root/'submit-intent.json',dict(utc=utc(),prepared_sha256=sha((root/'prepared.json').read_bytes()),api_calls=0,gpu_hours_cap=.75))
    r=subprocess.run(['sbatch','--parsable','--chdir='+str(root),'--output='+str(root/'allocation-%j.out'),
        '--error='+str(root/'allocation-%j.err'),str(root/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=r.stdout.strip().split(';')[0]
    if r.returncode or not job.isdigit():raise ValueError('ambiguous submission; no retry')
    write(root/'launch.json',dict(job=job,utc=utc(),commit=p['commit']));print(json.dumps(dict(root=str(root),job=job)))
if __name__=='__main__':
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('mode',choices=('prepare','submit','execute','concurrent'));p.add_argument('--root',type=Path);p.add_argument('--commit');p.add_argument('--slot',type=int);a=p.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='concurrent':concurrent(a.root,a.slot)
    else:globals()[a.mode](a.root)
