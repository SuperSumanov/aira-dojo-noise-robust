"""Fail before loading data/model if the allocated node lacks the pinned build tools."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


def main(expected_host='projgpu39'):
    assert expected_host in ('projgpu39','gpu28')
    root=Path(os.environ['G0_VENV'])
    assert os.environ['G0_BUDGET_REVISION']=='20260905-r5'
    assert os.environ['SLURM_JOB_ID'].isdigit()
    ninja=root/'bin/ninja'
    assert shutil.which('ninja')==str(ninja)
    digest=hashlib.sha256(ninja.read_bytes()).hexdigest()
    assert digest=='696f9628a79d9ce50314cf9556d7cd1a1d1ec52b8fd52828f6f9db1719565b67'
    cuda=Path(os.environ['CUDA_HOME'])
    assert str(cuda)=='/usr/local/cuda-12.8' and cuda.resolve()==cuda
    for rel in ('bin/nvcc','include/cuda.h','include/cuda_runtime.h','lib64/libcudart.so','lib64/libcurand.so'):
        assert (cuda/rel).is_file(),rel
    def output(argv):
        return subprocess.check_output(argv,text=True,stderr=subprocess.STDOUT,timeout=15).strip()
    version=output([str(cuda/'bin/nvcc'),'--version'])
    assert re.search(r'release 12\.8(?:,|\s)',version)
    result={'status':'ALLOCATED_NODE_BUILD_TOOLS_PASS','job_id':int(os.environ['SLURM_JOB_ID']),
            'hostname':os.uname().nodename,'ninja_sha256':digest,
            'ninja_version':output([str(ninja),'--version']),
            'compiler_version':output(['g++','--version']).splitlines()[0],
            'nvcc_version':version,'nvcc_sha256':hashlib.sha256((cuda/'bin/nvcc').read_bytes()).hexdigest(),
            'cuda_home':str(cuda),'model_load':False,'gpu_context_created':False}
    assert result['hostname'].split('.')[0]==expected_host
    with (Path(os.environ['G0_RUN_ROOT'])/'build_tools.json').open('x') as fh:
        json.dump(result,fh,sort_keys=True,indent=2)
        fh.write('\n')
    print(json.dumps({'status':result['status'],'ninja_sha256':digest,'cuda_home':str(cuda)}))


if __name__=='__main__':
    main()
