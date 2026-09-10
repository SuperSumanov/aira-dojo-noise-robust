"""Bounded integration of the actual task Jupyter server, not a model/effect run."""
import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

SOURCE=Path('/research/d7/spc/yzyang4/forets-next-config-20260911-4h_0y6b4/source')


def module(root):
    os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',
                      LOGGING_DIR=str(root),LITELLM_LOCAL_MODEL_COST_MAP='True',
                      SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
                      MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',
                      DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu')
    sys.path.insert(0,str(SOURCE/'src'))
    sys.path.insert(0,str(root))
    from dojo.core.interpreters.jupyter import singularity_jupyter_server as server
    if Path(server.__file__).resolve()!=SOURCE/'src/dojo/core/interpreters/jupyter/singularity_jupyter_server.py':
        raise RuntimeError('wrong source')
    return server


def cpu_check(root):
    server=module(root)
    from forets_gpu_binding_20260911 import rewrite,split_command,IMAGE
    args=server._build_singularity_command(runtime_executable='/adapter/bin/singularity',
        image_path=IMAGE,working_dir=root/'work',bind_inputs_dir=root/'inputs',
        read_only_overlays=[],read_only_binds={},container_env=server._build_container_environment({},host_env={}),
        token='artificial-test-only',port=8888)[1:]
    original=split_command(args)
    final,gate=rewrite(args,minor=1,uuid='GPU-00000000-0000-0000-0000-000000000001',
                       libraries={'libcuda.so.1':Path('/host/libcuda.so.1')},vendors=root/'opencl-vendors')
    assert '--nv' not in final and '/dev/nvidia1:/dev/nvidia1' in final
    assert not any('/dev/nvidia0:' in s or '/dev/nvidia9:' in s for s in final)
    assert final[-len(original[2]):]==original[2]
    for i in range(0,len(original[0]),2):
        option,value=original[0][i:i+2]
        assert any(final[j:j+2]==[option,value] for j in range(len(final)-1))
    for bad in (args[1:],['--nv']+args,[x if x!=str(IMAGE) else '/other.sif' for x in args]):
        try:split_command(bad)
        except ValueError:pass
        else:raise AssertionError('malformed invocation accepted')
    print(json.dumps({'actual_builder_checked':True,'original_task_payload_preserved':True,
                      'negative_cases':3,'gpu_calls':0,'api_calls':0}))


def step(root,index):
    logging.disable(logging.CRITICAL)
    server_module=module(root)
    from forets_opencl_allowlist_20260911 import GATE,OBSERVABLE_PROBE,CUDA_CHECK,IMAGE
    work=root/f'work-{index}';work.mkdir()
    identity=root/f'identity-{index}.json'
    with identity.open('x') as f:json.dump({},f)
    os.environ.update(FORETS_GPU_BINDING='explicit_step_v1',FORETS_GPU_INTEGRATION_ROOT=str(root),
                      DOJO_WORKER_IDENTITY_PATH=str(identity),PATH=str(root/'bin')+':'+os.environ['PATH'],
                      NO_PROXY='localhost,127.0.0.1,0.0.0.0')
    report=dict(role='actual_jupyter_gpu_adapter_integration_not_effect',index=index,
                allocation=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],
                slurm_step_gpus=os.environ['SLURM_STEP_GPUS'],api_calls=0,task_runs=0,model_calls=0,
                source_tree='3aae90ae26b5ae7b65e6efed14fb49f2907c9c42',
                integration_commit=os.environ['FORETS_SOURCE_COMMIT'])
    srv=None;start=time.monotonic()
    def deadline(*_):raise TimeoutError('integration bound')
    signal.signal(signal.SIGALRM,deadline);signal.alarm(180)
    try:
        srv=server_module.SingularityJupyterServer(working_dir=work,superimage_directory=IMAGE.parent,
            superimage_version='2026-07-macos-v1',startup_timeout=65)
        receipts=list(root.glob(identity.name+'.gpu-binding-*.json'))
        if len(receipts)!=1:raise RuntimeError('binding receipt missing or duplicated')
        binding=json.loads(receipts[0].read_text());report['binding']=binding
        prefix=f"import os\nos.environ['EXPECTED_GPU_MINORS']={str(binding['minor'])!r}\nos.environ['EXPECTED_GPU_MAJOR']='195'\n"
        client=srv.get_client()
        kernel=client.start_kernel('python3')
        with client.get_kernel_client(kernel) as k:
            if not k.wait_for_ready(timeout_seconds=10):raise TimeoutError('kernel ready')
            result=k.execute(prefix+GATE+'\n'+CUDA_CHECK+'\n'+OBSERVABLE_PROBE,timeout_seconds=65)
            report.update(kernel_ok=result.is_ok,kernel_timed_out=result.timed_out,records=[])
            for text in result.output:
                for line in text.splitlines():
                    for marker in ('ALLOWLIST_GATE ','CUDA_ALLOWLIST ','OPENCL_DIAGNOSTIC '):
                        if line.startswith(marker):report['records'].append(json.loads(line[len(marker):]))
    except Exception as exc:
        report['error_type']=type(exc).__name__
        report['adapter_error_tags']=re.findall(r'FORETS_GPU_BINDING_FAILED [A-Za-z]+',str(exc))
    finally:
        signal.alarm(0)
        if srv is not None:
            # Use actual server lifecycle; outer allocation remains a hard bound.
            srv.stop()
        report['seconds']=time.monotonic()-start
        with (root/f'step-{index}.json').open('x') as f:json.dump(report,f,indent=2)
        print(json.dumps({k:v for k,v in report.items() if k!='binding'}),flush=True)


def allocation(root):
    # salloc runs this CPU controller on login; only explicit exclusive steps run GPU checks.
    job=os.environ['SLURM_JOB_ID'];workers=[];streams=[];start=time.monotonic()
    try:
        for index in (0,1):
            out=(root/f'step-{index}.out').open('x');err=(root/f'step-{index}.err').open('x');streams += [out,err]
            command=['srun',f'--jobid={job}','--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=6',
                '--gres=gpu:1','--time=00:04:00',f'--job-name=forets-adapter-{index}',
                '/research/d7/spc/yzyang4/venvs/aira/bin/python',str(Path(__file__).resolve()),
                '--root',str(root),'--mode','step','--index',str(index)]
            workers.append(subprocess.Popen(command,stdout=out,stderr=err))
        for worker in workers:worker.wait(timeout=max(1,260-(time.monotonic()-start)))
        print(json.dumps({'allocation':job,'worker_returncodes':[p.returncode for p in workers]}),flush=True)
    finally:
        for p in workers:
            if p.poll() is None:p.terminate()
        for s in streams:s.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--mode',choices=['cpu','allocation','step'],required=True);p.add_argument('--index',type=int,choices=[0,1])
    a=p.parse_args();root=a.root.resolve(strict=True)
    if root.parent!=SOURCE.parent.parent or not root.name.startswith('forets-gpu-adapter-20260911-'):raise ValueError('isolated root required')
    if a.mode=='cpu':cpu_check(root)
    elif a.mode=='step':step(root,a.index)
    else:allocation(root)
