"""QOS-compliant metadata job: one GPU ALLOCATED/CHARGED, no model or CUDA use."""
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess

ROOT = Path('/research/d7/spc/yzyang4/toolchain-metadata-gpu28-20260906-r2')


def main():
    job = os.environ.get('SLURM_JOB_ID', '')
    commit = os.environ.get('TOOLCHAIN_SOURCE_COMMIT', '')
    assert job.isdigit() and re.fullmatch('[0-9a-f]{40}',commit)
    assert socket.gethostname().split('.')[0] == 'gpu28' and os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    assert ROOT.resolve()==ROOT and ROOT.is_dir() and not (ROOT/'observed.json').exists()
    env = dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    raw = subprocess.check_output(['scontrol','show','job','-o',job],env=env,timeout=10).decode()
    fields = dict(x.split('=',1) for x in raw.split() if '=' in x)
    assert all(fields.get(k)==v for k,v in {'JobId':job,'JobState':'RUNNING','NodeList':'gpu28',
        'ReqNodeList':'gpu28','TresPerNode':'gpu:rtx3090:1','NumCPUs':'6','CPUs/Task':'6',
        'TimeLimit':'00:01:00','Requeue':'0','Restarts':'0'}.items())
    from phase1.scripts import inspect_gpu28_cuda_toolchains_20260906 as inventory
    rows = inventory.discover_toolchains()
    result = {'classification':'INSTALLED_TOOLCHAIN_METADATA_ONE_GPU_ALLOCATION_NO_MODEL_RUN',
        'job_id':job,'host':'gpu28','source_commit':commit,
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'inventory_source_sha256':hashlib.sha256(Path(inventory.__file__).read_bytes()).hexdigest(),
        'toolchains':rows,'allocated_gpus':1,'gpu_context_or_framework_imports':0,
        'model_runs':0,'archive_or_checkpoint_reads':0,'installation_or_environment_changes':False,
        'actual_gpu_seconds':'REQUIRES_TERMINAL_SACCT','wall_cap_seconds':60,
        'scope_limitation':'Three shallow system prefixes, not every possible toolkit location.'}
    encoded = (json.dumps(result,sort_keys=True,indent=2)+'\n').encode()
    with (ROOT/'observed.json').open('xb') as stream: stream.write(encoded)
    print(json.dumps({'status':result['classification'],'job_id':job,'toolchains':rows,
                      'receipt_sha256':hashlib.sha256(encoded).hexdigest()},sort_keys=True))


if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(json.dumps({'status':'TOOLCHAIN_METADATA_R2_FAILED_CLOSED','exception_type':type(exc).__name__}))
        raise SystemExit(1)
