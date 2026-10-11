"""Exact senior factory entry + narrow exported fixes, isolated from production.

Three unchanged public UNet executions alternating three known exit17 injections.
Reused workspace, no model/API/hidden data; first unexpected result closes all6.
"""
import hashlib,io,json,os,re,shutil,subprocess,sys,tarfile,time
from pathlib import Path

BASE=Path('/research/d7/spc/yzyang4')
ROOT=BASE/'resource-factory-integration-20261011-v1'
DONOR=BASE/'resource-execution-guarded-six-20261011-v1'
PIN='d96fba91f303325714b8a7320571776cbec66a87ccaa45f12d01afd5a2b418a5'
SOURCE='f7ccd79323112b10ccc82d8e9ec9d6cf089df607'
PY=BASE/'venvs/aira/bin/python'
IMAGE=BASE/'aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif'
NAME=Path(__file__).name
PREFIX='src/dojo/core/interpreters/jupyter/'
FLAGS=('resource temporarily unavailable','pthread_create',"can't start new thread",'out of memory')

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()

def read(path):return json.loads(Path(path).read_text())

def write(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,sort_keys=True,allow_nan=False)

def schedule():return [dict(index=i,condition='normal' if i%2==0 else 'exit17',repeat=i//2) for i in range(6)]

def configure():
    os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',
        HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',SUPERIMAGE_DIR=str(IMAGE.parent),
        LOGGING_DIR=str(ROOT),MLE_BENCH_DATA_DIR=str(ROOT/'no-task-data'))
    sys.path.insert(0,str(ROOT/'source/src'))

def prepare(bundle):
    assert sha(DONOR/'plan.json')==PIN and read(DONOR/'audit-v1.json')['execution_gate']
    p=read(DONOR/'plan.json');pr=read(bundle/'patch-receipt.json')
    assert pr['base_commit']==SOURCE and pr['isolated_index_apply_check']
    assert all(sha(bundle/n)==h for n,h in pr['files'].items())
    assert sha(IMAGE)==p['task_image_sha256']
    assert sha(DONOR/'programs/1.py')==p['files']['programs/1.py']
    assert all(sha(n)==h for n,h in p['input_files'].items())
    raw=subprocess.check_output(['git','-C',str(BASE/'aira-dojo'),'archive',SOURCE,'src/dojo'])
    secret=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,})')
    sources={}
    with tarfile.open(fileobj=io.BytesIO(raw)) as ar:
        for item in ar:
            if item.isdir():continue
            path=Path(item.name)
            assert item.isfile() and '..' not in path.parts and path.is_relative_to('src/dojo')
            data=ar.extractfile(item).read();assert not secret.search(data)
            sources[path]=data
    ROOT.mkdir(mode=0o700)
    for path,data in sources.items():
        dest=ROOT/'source'/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    for n in ('A-readiness-cleanup.patch','B-lost-kernel-reporting.patch'):
        subprocess.run(['git','apply','--check',str(bundle/n)],cwd=ROOT/'source',check=True)
        subprocess.run(['git','apply',str(bundle/n)],cwd=ROOT/'source',check=True)
    for n,h in pr['source_sha256'].items():assert sha(ROOT/'source'/PREFIX/n)==h['after']
    shutil.copytree(bundle/'gateway',ROOT/'gateway')
    assert sha(ROOT/'gateway/kernel_shutdown_guard.py')=='ac890ba1a61d371e04f8c1b8faec87b20d64b10a10c95b027656745baa36313e'
    for n in (NAME,'factory_integration_readout_20261011.py','resource_pressure.py','owned_process_pressure.py','resource_gpu_identity.py','live_identity.py','neural_instrument.py','verify_six_gpu_capacity.py'):
        shutil.copyfile(Path(__file__).with_name(n),ROOT/n)
    shutil.copyfile(DONOR/'programs/1.py',ROOT/'program.py')
    (ROOT/'workspace/input_cache').mkdir(parents=True)
    (ROOT/'results').mkdir()
    batch=f'''#!/bin/bash
#SBATCH --job-name=factory-integration
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu3
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --hint=nomultithread
#SBATCH --time=00:15:00
#SBATCH --no-requeue
#SBATCH --output={ROOT}/job.private.log
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 840s srun --exclusive --ntasks=1 --gres=gpu:1 --cpus-per-task=4 --hint=nomultithread {PY} -B {ROOT}/{NAME} run
'''
    (ROOT/'run.sbatch').write_text(batch);subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    configure()
    from dojo.config_dataclasses.interpreter.jupyter import JupyterInterpreterConfig
    from dojo.core.interpreters.jupyter.jupyter_interpreter import JupyterInterpreterFactory
    assert callable(JupyterInterpreterFactory.run)
    JupyterInterpreterConfig(working_dir=str(ROOT/'workspace'),timeout=450,container_runtime='singularity')
    write(ROOT/'plan.json',dict(schedule=schedule(),planned=6,normal=3,known_exit=3,source_commit=SOURCE,
        donor_plan_sha256=PIN,source_seed=42,training_steps=588,program=p['programs'][1],input_files=p['input_files'],
        candidate_seconds=450,gpus=1,cpus=4,gpu_seconds_cap=900,allocation_seconds_cap=900,
        numerical_tolerance=1e-5,
        task_image_sha256=p['task_image_sha256'],expected_output_sha256=sha(DONOR/'episode-0/output.private.csv'),
        question='Do exact factory entry, workspace reuse and cleanup work with the exported narrow fixes?',
        acceptance='All6 slots,3 unchanged normal executions588CUDAsteps+matching outputs,3 known exits reported<20s without timeout,fresh gateway receipt per launch,clean close;first unexpected result stops.',
        no_model=True,no_api=True,no_base_training=True,
        boundary='Integration/known-fault test,not historical EAGAIN reproduction,production deployment,6-way service capacity,speedup or quality.',
        files={str(f.relative_to(ROOT)):sha(f) for f in ROOT.rglob('*') if f.is_file() and '__pycache__' not in f.parts}))
    print(json.dumps(dict(prepared=True,plan_sha256=sha(ROOT/'plan.json'),planned=6,gpu_seconds_cap=900)))

def run():
    import owned_process_pressure as pressure
    from resource_gpu_identity import gpu_uuids
    from live_identity import cpu_topology,cores
    from neural_instrument import INSTRUMENT,RECEIPT
    plan=read(ROOT/'plan.json');assert all(sha(ROOT/n)==h for n,h in plan['files'].items())
    configure();device=gpu_uuids(1)[0];top=cpu_topology();assert len(cores(top))==4
    from dojo.config_dataclasses.interpreter.jupyter import JupyterInterpreterConfig
    from dojo.core.interpreters.jupyter.jupyter_interpreter import JupyterInterpreterFactory
    from dojo.core.interpreters.jupyter import singularity_jupyter_server as gateway
    build=gateway._build_singularity_command
    def isolated(**kw):
        args=build(**kw);args[2:2]=['--no-mount','hostfs,bind-paths'];return args
    gateway._build_singularity_command=isolated
    work=ROOT/'workspace';source=(ROOT/'program.py').read_text()
    cfg=JupyterInterpreterConfig(working_dir=str(work),timeout=450,container_runtime='singularity',
        superimage_directory=str(IMAGE.parent),superimage_version='2026-07-macos-v1',
        read_only_binds={plan['program']['data']:'/workspace/workspace_input',str(ROOT/'gateway'):'/r14gateway',str(ROOT/'resource_gpu_identity.py'):'/resource_gpu_identity.py'},
        env=dict(PYTHONPATH='/r14gateway',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='6',OPENBLAS_NUM_THREADS='6',MKL_NUM_THREADS='6',PYTHONHASHSEED='130701',CUDA_VISIBLE_DEVICES=device))
    factory=JupyterInterpreterFactory(cfg,data_dir=Path(plan['program']['data']))
    write(ROOT/'identity.json',dict(gpu_uuids=[device],cpu_topology=top,job=os.environ['SLURM_JOB_ID']))
    write(ROOT/'pressure-before.json',pressure.snapshot(os.getpid()))
    rows=[];close_error=None
    try:
        for item in schedule():
            row=dict(**item,attempted=True,accepted=False,start=time.time());rows.append(row)
            try:
                before={f.name for f in work.glob('kernel-shutdown-guard-installed-*.json')}
                prelude="import sys,json,torch;sys.argv=['candidate.py'];sys.path.insert(0,'/');from resource_gpu_identity import gpu_uuids\n"
                prelude+=f"assert gpu_uuids(1)==[{device!r}]\nassert torch.cuda.is_available() and torch.cuda.device_count()==1\n"
                prelude+=INSTRUMENT
                ready=factory.run(prelude,reset_session=True)
                assert ready.exit_code==0 and not ready.timed_out
                fresh={f.name for f in work.glob('kernel-shutdown-guard-installed-*.json')}-before
                assert len(fresh)==1
                installed=read(work/next(iter(fresh)));assert installed['transition_timeout']==15 and installed['no_candidate_retry']
                row['fresh_gateway_receipt']=True
                code=source if item['condition']=='normal' else f"import os,json\nwith open('fault-start-{item['index']}.json','w') as f:json.dump({{'exit_requested':17}},f)\nos._exit(17)"
                result=factory.run(code,reset_session=False)
                text='\n'.join(map(str,result.term_out)).lower()
                row.update(exit_code=result.exit_code,timed_out=result.timed_out,execution_seconds=result.exec_time,
                           resource_flags={x:x in text for x in FLAGS},lost_state='kernel state lost during execution' in text)
                write(ROOT/f"results/pressure-{item['index']}.json",pressure.snapshot(os.getpid()))
                assert not any(row['resource_flags'].values())
                if item['condition']=='normal':
                    assert result.exit_code==0 and not result.timed_out
                    assert factory.fetch_file(str(work/'submission.csv'))
                    shutil.copyfile(work/'submission.csv',ROOT/f"results/output-{item['index']}.private.csv")
                    receipt=factory.run(RECEIPT,reset_session=False);assert receipt.exit_code==0 and not receipt.timed_out
                    assert factory.fetch_file(str(work/'gpu_training.json'))
                    training=read(work/'gpu_training.json');assert training['steps']==588
                    assert all(x['devices']==['cuda:0'] and x['gradient_parameters']>0 for x in training['host_step_intervals'])
                    shutil.copyfile(work/'gpu_training.json',ROOT/f"results/training-{item['index']}.json")
                    row.update(training_steps=588,output_sha256=sha(ROOT/f"results/output-{item['index']}.private.csv"))
                else:
                    assert read(work/f"fault-start-{item['index']}.json")==dict(exit_requested=17)
                    assert result.exit_code!=0 and not result.timed_out and result.exec_time<20 and row['lost_state']
                row['accepted']=True
            except Exception as exc:row['error_type']=type(exc).__name__
            finally:
                row['end']=time.time();write(ROOT/f"results/row-{item['index']}.json",row)
                print(json.dumps({k:v for k,v in row.items() if k not in ('resource_flags',)}),flush=True)
            if not row['accepted']:break
    finally:
        try:factory.close()
        except Exception as exc:close_error=type(exc).__name__
        write(ROOT/'pressure-after.json',pressure.snapshot(os.getpid()))
        write(ROOT/'closed.json',dict(planned=6,attempted=len(rows),accepted=sum(r['accepted'] for r in rows),close_error=close_error))
    return int(len(rows)!=6 or not all(r['accepted'] for r in rows) or close_error is not None)

if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1]=='prepare':prepare(Path(sys.argv[2]))
    elif sys.argv[1]=='run':sys.exit(run())
    else:raise ValueError('mode')
