"""Independent projgpu36 metadata-only follow-up; no task, model, or allocation retry."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

assert socket.gethostname().split('.')[0] == 'projgpu36'
root = Path(sys.argv[1]).resolve()
assert root == Path('/research/d7/spc/yzyang4/node-runtime-20261016-JnNPsD')
result = dict(job=os.environ['SLURM_JOB_ID'], node='projgpu36', model_calls=0,
              task_executions=0, code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
result['allocation'] = {k:os.environ.get(k) for k in ('SLURM_JOB_GPUS','SLURM_STEP_GPUS','CUDA_VISIBLE_DEVICES')}
lib = ctypes.CDLL('libcuda.so.1')
code = lib.cuInit(0)
result['cuInit_returncode'] = code
for func, name in (('cuGetErrorName','cuda_error_name'),('cuGetErrorString','cuda_error_text')):
    p = ctypes.c_char_p()
    if getattr(lib,func)(code,ctypes.byref(p)) == 0:
        result[name] = p.value.decode()
version = ctypes.c_int()
result['cuDriverGetVersion_rc'] = lib.cuDriverGetVersion(ctypes.byref(version))
result['cuda_driver_api_version'] = version.value
result['loaded_libcuda_paths'] = sorted(set(line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines() if '/libcuda.so' in line))
version_file = Path('/proc/driver/nvidia/version')
result['kernel_driver_version'] = version_file.read_text() if version_file.exists() else None
for label, args in (
    ('nvidia_smi', ['/usr/bin/nvidia-smi','--query-gpu=name,driver_version','--format=csv,noheader']),
    ('container_exec_help', ['/usr/bin/singularity','exec','--help']),
):
    try:
        r = subprocess.run(args,capture_output=True,text=True,timeout=15)
        result[label+'_rc'] = r.returncode
        if label == 'container_exec_help':
            result['container_help_has_no_mount'] = '--no-mount' in r.stdout
            result['container_help_has_containall'] = '--containall' in r.stdout
        else:
            result[label+'_stdout'] = r.stdout[-1800:]
        result[label+'_stderr'] = r.stderr[-1000:]
    except subprocess.TimeoutExpired:
        result[label+'_timeout'] = True
with (root/('driver-'+result['job']+'.json')).open('x') as f:
    json.dump(result,f,indent=2)
print(json.dumps(result),flush=True)
