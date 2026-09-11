"""Fresh Jupyter integration using native CUDA identity; no old task recovery."""
import argparse
import json
import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

SOURCE=Path('/research/d7/spc/yzyang4/forets-next-config-20260911-4h_0y6b4/source')


def step(root,slot):
    logging.disable(logging.CRITICAL)
    os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',
        LOGGING_DIR=str(root),LITELLM_LOCAL_MODEL_COST_MAP='True',
        SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
        MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu',
        FORETS_NATIVE_INTEGRATION_ROOT=str(root),
        PATH=str(root/'bin')+':'+os.environ['PATH'],NO_PROXY='localhost,127.0.0.1,0.0.0.0')
    sys.path[:0]=[str(root),str(SOURCE/'src')]
    from dojo.core.interpreters.jupyter.singularity_jupyter_server import SingularityJupyterServer
    from forets_opencl_allowlist_20260911 import IMAGE,GATE,CUDA_CHECK,OBSERVABLE_PROBE
    work=root/('work-'+str(slot));work.mkdir()
    receipt=root/('identity-'+str(slot)+'.json')
    with receipt.open('x') as f:json.dump({},f)
    os.environ['DOJO_WORKER_IDENTITY_PATH']=str(receipt)
    result=dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],slot=slot,
        source_commit=os.environ['FORETS_SOURCE_COMMIT'],source_tree='3aae90ae26b5ae7b65e6efed14fb49f2907c9c42',
        role='native_device_actual_jupyter_integration_not_effect',api_calls=0,model_calls=0,task_runs=0)
    def expired(*_):raise TimeoutError('bounded native Jupyter check')
    signal.signal(signal.SIGALRM,expired);signal.alarm(230)
    srv=None;started=time.monotonic()
    try:
        srv=SingularityJupyterServer(working_dir=work,superimage_directory=IMAGE.parent,
            superimage_version='2026-07-macos-v1',startup_timeout=90)
        binding=json.loads(receipt.with_suffix('.native-binding.json').read_text())
        result['binding']=binding
        minor=binding['namespace']['minor']
        prefix=f"import os\nos.environ['EXPECTED_GPU_MINORS']={str(minor)!r}\nos.environ['EXPECTED_GPU_MAJOR']='195'\n"
        client=srv.get_client();kernel=client.start_kernel('python3')
        with client.get_kernel_client(kernel) as k:
            if not k.wait_for_ready(timeout_seconds=10):raise TimeoutError('kernel not ready')
            answer=k.execute(prefix+GATE+'\n'+CUDA_CHECK+'\n'+OBSERVABLE_PROBE,timeout_seconds=90)
            result.update(kernel_ok=answer.is_ok,kernel_timed_out=answer.timed_out,records=[])
            for text in answer.output:
                for line in text.splitlines():
                    for marker in ('ALLOWLIST_GATE ','CUDA_ALLOWLIST ','OPENCL_DIAGNOSTIC '):
                        if line.startswith(marker):result['records'].append(json.loads(line[len(marker):]))
    except Exception as exc:result['error_type']=type(exc).__name__
    finally:
        try:
            if srv is not None:srv.stop()
        finally:
            signal.alarm(0);result['seconds']=time.monotonic()-started
            with (root/('step-'+str(slot)+'.json')).open('x') as f:json.dump(result,f,indent=2)
            print(json.dumps(result),flush=True)
    return 0 if result.get('kernel_ok') is True else 1


def allocation(root):
    job=os.environ['SLURM_JOB_ID'];pids=[];streams=[];started=time.monotonic()
    try:
        for slot in range(2):
            out=(root/('step-'+str(slot)+'.out')).open('x')
            err=(root/('step-'+str(slot)+'.err')).open('x');streams.extend((out,err))
            cmd=['srun','--jobid='+job,'--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=6',
                 '--gres=gpu:1','--time=00:04:00','--job-name=forets-native-jupyter-'+str(slot),
                 sys.executable,str(Path(__file__).resolve()),'--root',str(root),'--mode=step','--slot',str(slot)]
            pids.append(subprocess.Popen(cmd,stdout=out,stderr=err))
        for p in pids:p.wait(timeout=max(1,260-(time.monotonic()-started)))
        print(json.dumps({'job':job,'returncodes':[p.returncode for p in pids]}),flush=True)
        return 0 if all(p.returncode==0 for p in pids) else 1
    finally:
        for p in pids:
            if p.poll() is None:p.terminate()
        for stream in streams:stream.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--mode',choices=('step','allocation'),required=True)
    p.add_argument('--slot',type=int,choices=(0,1));a=p.parse_args();root=a.root.resolve(strict=True)
    if root.parent!=SOURCE.parent.parent or not root.name.startswith('forets-native-gpu-adapter-20260911-'):
        raise ValueError('fresh integration root required')
    raise SystemExit(step(root,a.slot) if a.mode=='step' else allocation(root))
