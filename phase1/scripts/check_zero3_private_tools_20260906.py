"""Allocated gpu28 check of the exact independently verified private toolkit."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from phase1.scripts.verify_private_cuda128_20260906 import ROOT,check,digest_file,verify_prefix

RECOVERY='8701d0fc275c5c0f7a124d05e622bbe0a1e7f5313b7260911000326808b5730a'
INDEPENDENT='6732f4045503fb658cce9a0fbf7c449985ecee41f01886d3e4f2a704463dd2fe'
MANIFEST='ce7f9f18218799db0776d08a2c3e2342e51273bcaccae61c1ebab8e340e959f1'


def environment_gate(env,host):
    check(host.split('.')[0]=='gpu28','wrong_host')
    check(re.fullmatch('[0-9]+',env.get('SLURM_JOB_ID','')),'allocation_required')
    check(env.get('CUDA_HOME')==str(ROOT/'prefix'),'cuda_home_not_pinned')
    check(env.get('CXX')==env.get('NVCC_CCBIN')=='/usr/bin/g++','host_compiler_not_explicit')
    check(env.get('G0_BUDGET_REVISION')=='20260905-r5','runtime_revision')


def main():
    environment_gate(os.environ,os.uname().nodename)
    check(digest_file(ROOT/'RECOVERY_COMPLETE.json')==RECOVERY,'recovery_receipt_drift')
    check(digest_file(ROOT/'INDEPENDENT_VERIFIED.json')==INDEPENDENT,'independent_receipt_drift')
    check(digest_file(ROOT/'installed_manifest.json')==MANIFEST,'manifest_drift')
    observed=verify_prefix(ROOT/'prefix',json.loads((ROOT/'installed_manifest.json').read_bytes()))
    runtime=Path('/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5')
    ninja=runtime/'bin/ninja'
    check(shutil.which('ninja')==str(ninja) and digest_file(ninja)=='696f9628a79d9ce50314cf9556d7cd1a1d1ec52b8fd52828f6f9db1719565b67','ninja_binding')
    def output(argv):return subprocess.check_output(argv,stderr=subprocess.STDOUT,timeout=15).decode().strip()
    compiler=Path('/usr/bin/g++')
    frontend=Path(output([str(compiler),'-print-prog-name=cc1plus']))
    check(frontend.is_absolute() and frontend.is_file(),'allocated_host_frontend_missing')
    version=output([str(ROOT/'prefix/bin/nvcc'),'--version'])
    check('release 12.8,' in version and 'V12.8.61' in version,'nvcc_version')
    result={'status':'ALLOCATED_PRIVATE_CUDA128_BUILD_TOOLS_PASS','job_id':os.environ['SLURM_JOB_ID'],
        'hostname':os.uname().nodename,'cuda_home':str(ROOT/'prefix'),'nvcc_version':version,
        'nvcc_sha256':digest_file(ROOT/'prefix/bin/nvcc'),'toolkit_manifest_sha256':MANIFEST,
        'toolkit_recovery_sha256':RECOVERY,'toolkit_independent_sha256':INDEPENDENT,
        'host_compiler_path':str(compiler.resolve()),'host_compiler_sha256':digest_file(compiler),
        'host_compiler_version':output([str(compiler),'--version']).splitlines()[0],
        'host_frontend_sha256':digest_file(frontend),'ninja_sha256':digest_file(ninja),
        'nccl_ib_disable':os.environ.get('NCCL_IB_DISABLE'),'nccl_net':os.environ.get('NCCL_NET'),
        'nccl_debug':os.environ.get('NCCL_DEBUG'),'python_faulthandler':os.environ.get('PYTHONFAULTHANDLER'),
        'verified_files_and_links':len(observed),'model_load':False,'gpu_context_created':False}
    with (Path(os.environ['G0_RUN_ROOT'])/'build_tools.json').open('x') as out:json.dump(result,out,sort_keys=True,indent=2)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
