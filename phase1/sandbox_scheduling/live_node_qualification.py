"""Original task-image arithmetic on a new same-architecture node, not G0."""
import json
import os
from pathlib import Path
import time
from lifecycle_pilot import read,write
from live_runtime_hooks import gateway_port
from bounded_readiness import wait_for_ready


def qualify(trial):
    trial.check();m=trial.host();m.setup();ep=trial.R/'episode-qualification'
    gpu=m.infra().native_uuids(1)[0]
    if trial.gpu_sample(gpu)['pids']:raise ValueError('nonempty qualification GPU')
    os.environ.update(DOJO_GPU_UUIDS=gpu,POLICY9B_EPISODE=str(ep),
        DOJO_WORKER_IDENTITY_PATH=str(ep/'identity.json'),
        DOJO_EXECUTION_ID=f'{os.environ["SLURM_JOB_ID"]}.{os.environ["SLURM_STEP_ID"]}:qualification',
        PATH=str(trial.R/'bin')+':'+os.environ['PATH'])
    from dojo.main_local_worker import _process_start_ticks,_host_boot_id
    from dojo.config_dataclasses.interpreter.jupyter import JupyterInterpreterConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    from dojo.utils.experiment_deadline import ExperimentDeadline
    import dojo.core.interpreters.jupyter.jupyter_interpreter as ji
    from dojo.core.interpreters.jupyter.jupyter_client import JupyterKernelClient
    if not hasattr(ji,'_gateway_port'):raise ValueError('native gateway interface changed')
    ji._gateway_port=lambda:gateway_port(os.environ['SLURM_JOB_ID'],16)
    JupyterKernelClient.wait_for_ready=lambda self,timeout_seconds=None:wait_for_ready(self,120 if timeout_seconds is None else timeout_seconds)
    write(ep/'native.json',dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],gpu_uuids=[gpu]))
    write(ep/'identity.json',dict(pid=os.getpid(),pgid=os.getpgid(0),
        process_start_ticks=_process_start_ticks(os.getpid()),host_boot_id=_host_boot_id(),
        gpu_uuids=[gpu],container_pid=None,container_process_start_ticks=None))
    cfg=JupyterInterpreterConfig(working_dir=str(ep/'work'),timeout=45,container_runtime='singularity',
        superimage_directory=str(m.TASK_IMAGE.parent),superimage_version='2026-07-macos-v1',
        env={'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'})
    interp=None;receipt=None;error=None;start=time.time()
    try:
        with ExperimentDeadline(150).activate():
            interp=build(cfg,INTERPRETER_MAP,data_dir=trial.R/'qualification-empty-data')
            code='''import json,torch
from pathlib import Path
assert torch.cuda.is_available() and torch.cuda.device_count()==1
assert "3090" in torch.cuda.get_device_name(0)
x=torch.ones((64,64),device="cuda")
y=x@x
torch.cuda.synchronize()
assert torch.isfinite(y).all().item() and y[0,0].item()==64
Path("gpu_qualification.json").write_text(json.dumps(dict(torch=torch.__version__,cuda=torch.version.cuda,device=torch.cuda.get_device_name(0),device_count=1,arithmetic_passed=True)))
'''
            result=interp.run(code)
            if result.exit_code or result.timed_out or not interp.fetch_file(ep/'work/gpu_qualification.json'):
                raise ValueError('original image GPU arithmetic did not complete')
            receipt=read(ep/'work/gpu_qualification.json')
    except Exception as e:
        error=type(e).__name__
    finally:
        if interp is not None:
            try:interp.close()
            except Exception as e:error=error or type(e).__name__
        clean=not trial.gpu_sample(gpu)['pids']
        write(trial.R/'node-qualification.json',dict(complete=error is None and clean and bool(receipt),
            error_type=error,gpu_clean=clean,start=start,end=time.time(),receipt=receipt,
            node=trial.NODE,no_candidate_or_data_execution=True,task_image_sha256=trial.read(trial.R/'plan.json')['task_image_sha256']))
    return 0 if error is None and clean and receipt else 1
