"""12 CPU-kernel fault-injection cases, reserved GPU cost counted, no task data."""
import hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
import resource_diag_20261011 as d
from kernel_restart_guard import overlay

ROOT=d.BASE/'resource-restart-guard-trial-20261011-v1'
DONOR=d.BASE/'resource-execution-exit-capture-20261011-v1'
PIN='64d4d03d1b4513bfac11518736671031691f334334195e134eab564ba99931f0'
NAME=Path(__file__).name
CLIENT='src/dojo/core/interpreters/jupyter/jupyter_client.py'
CODES={'normal':"print('R14_NORMAL_OK')",'exit':"import os,time\ntime.sleep(1)\nos._exit(17)"}
SITE="""import os,sys
if os.path.basename(sys.argv[0])=='jupyter-kernelgateway':
    import gateway_counter
    import kernel_lifecycle_observer
"""

def schedule():
    rows=[]
    for rep in range(3):
        for arm in (('old','guard') if rep%2==0 else ('guard','old')):
            for case in (('normal','exit') if rep%2==0 else ('exit','normal')):
                rows.append(dict(index=len(rows),repeat=rep,arm=arm,case=case))
    return rows

def configure(arm):
    d.ROOT=ROOT;d.configure()
    if arm=='guard':sys.path.insert(0,str(ROOT/'source-guard/src'))

def prepare():
    assert d.sha(DONOR/'plan.json')==PIN
    p=json.loads((DONOR/'plan.json').read_text())
    assert all(d.sha(DONOR/n)==h for n,h in p['files'].items())
    ROOT.mkdir(mode=0o700)
    for n in p['files']:
        if not(n.startswith('source/') or n in ('resource_diag_20261011.py','resource_pressure.py')):continue
        path=ROOT/n;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/n,path)
    for n in (NAME,'kernel_restart_guard.py','kernel_lifecycle_observer.py'):
        shutil.copyfile(Path(__file__).with_name(n),ROOT/n)
    # Avoid loading an unrelated experiment driver at runtime: SITE is a fixed string.
    shutil.copytree(ROOT/'source',ROOT/'source-guard')
    (ROOT/'source-guard'/CLIENT).write_text(overlay((ROOT/'source'/CLIENT).read_text()))
    for row in schedule():
        obs=ROOT/f"case-{row['index']}"/'observer';obs.mkdir(parents=True)
        (obs/'sitecustomize.py').write_text(SITE)
        shutil.copyfile(DONOR/'episode-0/observer/gateway_counter.py',obs/'gateway_counter.py')
        shutil.copyfile(ROOT/'kernel_lifecycle_observer.py',obs/'kernel_lifecycle_observer.py')
    batch=f'''#!/bin/bash
#SBATCH --job-name=restart-guard-trial
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu3
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --hint=nomultithread
#SBATCH --time=00:10:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=15s 560s srun --exclusive --ntasks=1 --gres=gpu:1 --cpus-per-task=4 --hint=nomultithread {d.PY} -B {ROOT}/{NAME} controller
'''
    (ROOT/'run.sbatch').write_text(batch);subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    for arm in ('old','guard'):subprocess.run([str(d.PY),'-B',str(ROOT/NAME),'preflight',arm],check=True)
    d.write(ROOT/'plan.json',dict(question='Does honoring parentless gateway lifecycle failure avoid waiting for a dead execution while preserving normal behavior?',
        source_commit=d.SOURCE,task_image_sha256=p['task_image_sha256'],donor_plan_sha256=PIN,
        planned=12,schedule=schedule(),codes=CODES,execution_timeout=12,source_seed=101101,
        gpus=1,cpus=4,gpu_seconds_cap=600,allocation_seconds_cap=600,no_gpu_compute=True,no_task_data=True,no_api=True,no_base_update=True,
        only_change='Insert restarting/dead control-plane guard before request-ID filtering; timeout,original image and all other client logic unchanged.',
        expected='6normal success with identical stdout;3old exits yield timeout;3guard exits yield non-timeout failure within8s,all6exit codes17 recorded by provisioner.',
        stop='Stop first unexpected infrastructure or case outcome,or remaining controller reserve;no replacements. Entire GPU reservation counted.',
        boundary='Controlled os._exit17 diagnostic,not historical EAGAIN root cause,spontaneous crash prevention,MLE throughput or scientific method gain.',
        files={str(f.relative_to(ROOT)):d.sha(f) for f in ROOT.rglob('*') if f.is_file() and '__pycache__' not in f.parts}))
    print(json.dumps(dict(prepared=True,planned=12,gpu_seconds_cap=600,plan_sha256=d.sha(ROOT/'plan.json'))))

def worker(index):
    row=schedule()[index];ep=ROOT/f'case-{index}';configure(row['arm'])
    from dojo.core.interpreters.jupyter import singularity_jupyter_server as sg
    from dojo.core.interpreters.jupyter.jupyter_code_executor import JupyterCodeExecutor
    from dojo.core.interpreters.jupyter.jupyter_client import JupyterKernelClient
    build=sg._build_singularity_command
    def cpu(**kw):
        env=dict(kw['container_env'],PYTHONPATH='/workspace/observer')
        args=build(**dict(kw,container_env=env));args.remove('--nv');args[2:2]=['--no-mount','hostfs,bind-paths'];return args
    sg._build_singularity_command=cpu
    messages=[];receive=JupyterKernelClient._receive_message
    def observed(self,*args,**kwargs):
        message=receive(self,*args,**kwargs)
        if message is not None:
            kind=message.get('msg_type');content=message.get('content',{})
            if kind in ('status','kernel_info_reply','execute_reply','error'):
                state=content.get('execution_state') if isinstance(content,dict) else None
                messages.append(dict(kind=kind,state=state if state in ('starting','busy','idle','restarting','dead') else None,
                    has_parent=bool(message.get('parent_header',{}).get('msg_id')),time=time.time()))
        return message
    JupyterKernelClient._receive_message=observed
    server=executor=None;result=None;error=None;started=time.time();out=None
    try:
        server=sg.SingularityJupyterServer(working_dir=ep,superimage_directory=str(d.IMAGE.parent),superimage_version='2026-07-macos-v1',startup_timeout=60,
            env=dict(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='3',OPENBLAS_NUM_THREADS='3',MKL_NUM_THREADS='3',PYTHONHASHSEED='101101'))
        executor=JupyterCodeExecutor(server,timeout=12)
        before=time.time();out=executor.execute_code(CODES[row['case']]);after=time.time()
        result=dict(exit_code=out.exit_code,timed_out=out.timed_out,seconds=out.exec_time,start=before,end=after,
            normal_marker='R14_NORMAL_OK' in '\n'.join(out.term_out),
            stdout_sha256=hashlib.sha256(json.dumps(out.term_out,sort_keys=True).encode()).hexdigest() if row['case']=='normal' else None,
            lifecycle_marker='gateway lifecycle event' in '\n'.join(out.term_out))
        expected=(out.exit_code==0 and not out.timed_out and result['normal_marker']) if row['case']=='normal' else (
            out.exit_code==1 and (out.timed_out if row['arm']=='old' else not out.timed_out and result['lifecycle_marker'] and out.exec_time<=8))
        if not expected:raise RuntimeError('case did not meet frozen expectation')
    except Exception as exc:error=type(exc).__name__
    finally:
        if executor is not None:
            try:executor.stop()
            except Exception as exc:error=error or type(exc).__name__
        if server is not None:
            try:server.stop()
            except Exception as exc:error=error or type(exc).__name__
        d.write(ep/'receipt.json',dict(**row,complete=error is None,error_type=error,result=result,messages=messages,start=started,end=time.time()))
    return int(error is not None)

def controller():
    p=json.loads((ROOT/'plan.json').read_text());assert all(d.sha(ROOT/n)==h for n,h in p['files'].items())
    start=time.monotonic();results=[]
    d.write(ROOT/'before.json',d.resource_pressure.snapshot())
    for row in schedule():
        if time.monotonic()-start>410:break
        with (ROOT/f"case-{row['index']}/worker.private.log").open('x') as log:
            proc=subprocess.Popen([str(d.PY),'-B',str(ROOT/NAME),'worker',str(row['index'])],stdout=log,stderr=log,start_new_session=True)
            try:rc=proc.wait(timeout=140)
            except subprocess.TimeoutExpired:
                import signal
                os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=5)
                rc=124
        results.append(dict(index=row['index'],returncode=rc))
        if rc:break
    d.write(ROOT/'after.json',d.resource_pressure.snapshot())
    d.write(ROOT/'closed.json',dict(planned=12,attempted=len(results),complete=sum(x['returncode']==0 for x in results),rows=results))
    return int(len(results)!=12 or any(x['returncode'] for x in results))

if __name__=='__main__':
    os.umask(0o077);d.ROOT=ROOT
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='preflight':
        configure(sys.argv[2])
        import inspect
        from dojo.core.interpreters.jupyter.jupyter_client import JupyterKernelClient
        source=inspect.getsource(JupyterKernelClient.execute)
        assert ('gateway lifecycle event' in source)==(sys.argv[2]=='guard')
        print(json.dumps(dict(preflight=sys.argv[2],imports_pass=True,no_kernel=True)))
    elif sys.argv[1]=='worker':sys.exit(worker(int(sys.argv[2])))
    elif sys.argv[1]=='controller':sys.exit(controller())
