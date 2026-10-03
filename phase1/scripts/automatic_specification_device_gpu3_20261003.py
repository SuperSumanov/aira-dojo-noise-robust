"""One bounded two-GPU metadata probe; no model, tensor or task execution."""
import ctypes as C,json,os,subprocess,sys,uuid
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/automatic-specification-device-probe-gpu3-20261003')
def capture():
    result={k:os.environ.get(k) for k in ('CUDA_VISIBLE_DEVICES','CUDA_DEVICE_ORDER','SLURM_JOB_ID','SLURM_STEP_ID','SLURM_JOB_GPUS','SLURM_STEP_GPUS','GPU_DEVICE_ORDINAL')}
    d=C.CDLL('libcuda.so.1');result['init_rc']=int(d.cuInit(C.c_uint(0)))
    n=C.c_int();result['count_rc']=int(d.cuDeviceGetCount(C.byref(n)));result['cuda_count']=n.value;result['uuids']=[]
    if result['init_rc']==0 and result['count_rc']==0:
        for k in range(min(n.value,12)):
            dev=C.c_int();assert d.cuDeviceGet(C.byref(dev),C.c_int(k))==0
            uid=(C.c_ubyte*16)();assert d.cuDeviceGetUuid(C.byref(uid),dev)==0
            bus=C.create_string_buffer(64);assert d.cuDeviceGetPCIBusId(bus,C.c_int(64),dev)==0
            result['uuids'].append(dict(uuid='GPU-'+str(uuid.UUID(bytes=bytes(uid))),bus=bus.value.decode()))
    result['cgroup']=Path('/proc/self/cgroup').read_text().splitlines()
    print(json.dumps(result))
def step():
    records=[]
    # Preserve Slurm's visibility mask. Only query native vs conventional PCI ordering.
    for order in (None,'PCI_BUS_ID'):
        env=dict(os.environ)
        if order is not None:env['CUDA_DEVICE_ORDER']=order
        p=subprocess.run([sys.executable,'-B',__file__,'capture'],env=env,capture_output=True,text=True,timeout=20)
        assert p.returncode==0
        record=json.loads(p.stdout);record['requested_order']=order;records.append(record)
    with (ROOT/'result.json').open('x') as f:json.dump(dict(role='native metadata only, no model or CUDA arithmetic',records=records),f,sort_keys=True,indent=2)
def main():
    ROOT.mkdir(mode=0o700)
    script=ROOT/'run.sbatch'
    script.write_text('#!/bin/bash\n#SBATCH --job-name=auto-spec-device\n#SBATCH --partition=gpu_24h\n#SBATCH --account=gpu\n#SBATCH --qos=gpu\n#SBATCH --nodelist=gpu3\n#SBATCH --gres=gpu:2\n#SBATCH --cpus-per-task=4\n#SBATCH --time=00:02:00\nset -euo pipefail\nexport SLURM_CONF=/opt1/slurm/gpu-slurm.conf\nsrun --exclusive --ntasks=1 --cpus-per-task=4 --gres=gpu:2 --time=00:01:00 '+sys.executable+' -B '+__file__+' step\n')
    p=subprocess.run(['sbatch','--parsable','--output='+str(ROOT/'allocation-%j.out'),'--error='+str(ROOT/'allocation-%j.err'),str(script)],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,capture_output=True,timeout=25)
    assert p.returncode==0 and p.stdout.strip().isdigit()
    with (ROOT/'launch.json').open('x') as f:json.dump(dict(job=p.stdout.strip(),gpus=2,allocation_seconds=120,max_gpu_hours=2*120/3600),f)
    print(p.stdout.strip())
if __name__=='__main__':
    os.umask(0o077);globals()[sys.argv[1] if len(sys.argv)>1 else 'main']()
