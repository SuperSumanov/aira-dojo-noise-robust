import hashlib,json,os,subprocess
from pathlib import Path
base=Path('/research/d7/spc/yzyang4/critic-zero3-engineering/node-metadata')
job=os.environ['SLURM_JOB_ID'];assert job.isdigit();assert os.uname().nodename.split('.')[0]=='gpu28'
os.umask(0o077);out=base/job;out.mkdir(mode=0o700)
cuda=Path('/usr/local/cuda-12.8');runtime=Path('/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5')
paths=['bin/nvcc','include/cuda.h','include/cuda_runtime.h','lib64/libcudart.so','lib64/libcurand.so']
result={'job':job,'host':os.uname().nodename,'cuda_files':{p:(cuda/p).is_file() for p in paths},
    'runtime_python_present':(runtime/'bin/python').is_file(),'gpu_context_created':False,'model_load':False,'requested_gpus':0}
if (cuda/'bin/nvcc').is_file():
    result['nvcc_version']=subprocess.check_output([str(cuda/'bin/nvcc'),'--version'],text=True,timeout=15)
    result['nvcc_sha256']=hashlib.sha256((cuda/'bin/nvcc').read_bytes()).hexdigest()
result['compiler']=subprocess.check_output(['g++','--version'],text=True,timeout=15).splitlines()[0]
(out/'metadata.json').write_text(json.dumps(result,sort_keys=True,indent=2))
print(json.dumps(result,sort_keys=True))
