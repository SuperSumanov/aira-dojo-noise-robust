"""Inside one owned Slurm GPU step: read-only driver diagnosis, no context/fit."""
import ctypes as C
import json
import os
from pathlib import Path
import socket
import subprocess

def main():
    if not os.environ.get('SLURM_JOB_ID','').isdigit() or not os.environ.get('SLURM_STEP_ID','').isdigit():
        raise ValueError('native Slurm step required')
    node=socket.gethostname().split('.')[0]
    if node not in ('gpu24','gpu29'):raise ValueError('bounded diagnostic nodes only')
    d=C.CDLL('libcuda.so.1');rc=d.cuInit(C.c_uint(0))
    name=C.c_char_p();desc=C.c_char_p()
    d.cuGetErrorName(C.c_int(rc),C.byref(name));d.cuGetErrorString(C.c_int(rc),C.byref(desc))
    out=dict(node=node,job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],
             cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES'),slurm_step_gpus=os.environ.get('SLURM_STEP_GPUS'),
             init_return_code=rc,error_name=name.value.decode() if name.value else None,
             error_description=desc.value.decode() if desc.value else None,
             no_cuda_context_or_arithmetic=True)
    if rc==0:
        count=C.c_int();out['count_return_code']=d.cuDeviceGetCount(C.byref(count));out['visible_device_count']=count.value
    out['libcuda_paths']=sorted({line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines() if '/libcuda' in line})
    q=subprocess.run(['nvidia-smi','--query-gpu=name,driver_version','--format=csv,noheader'],capture_output=True,text=True,timeout=10)
    out['nvidia_smi_returncode']=q.returncode
    if q.returncode==0:out['gpu_types_and_driver']=sorted(set(q.stdout.strip().splitlines()))
    else:out['nvml_mismatch']='Driver/library version mismatch' in q.stderr+q.stdout
    print(json.dumps(out,sort_keys=True))

if __name__=='__main__':main()
