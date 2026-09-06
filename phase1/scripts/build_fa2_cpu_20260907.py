"""One offline CPU source build into an isolated overlay, no existing env edits."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

BASE = Path('/research/d7/spc/yzyang4')
ROOT = BASE / 'flash-attn-build-20260907-r2'
RUNTIME = BASE / 'venvs/critic-blackwell-g0-20260905-r5'
HOST_CXX = '/usr/bin/g++'
HOST_SHA = '1353e9bdd29a7295c7226bf6c63abccce056d8cac31f112e5cdbecc3f28c2769'
SDIST_SHA = '1e71dd64a9e0280e0447b8a0c2541bad4bf6ac65bdeaa2f90e51a9e57de0370d'
WHEEL_SHA = '708e7481cc80179af0e556bbf0cc00b8444c7321e2700b8d8580231d13017248'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()


def record(name, data):
    with (ROOT / name).open('x') as f:
        json.dump(data, f, sort_keys=True, indent=2)


def invoke(name, args, env, seconds, cwd=ROOT):
    start = time.monotonic()
    with (ROOT / (name + '.log')).open('xb') as log:
        p = subprocess.Popen(list(map(str, args)), env=env, cwd=cwd,
                             stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            rc = p.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGTERM)
            try:
                rc = p.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                rc = p.wait(timeout=20)
            record(name + '-timeout.json', {'timeout_seconds': seconds, 'returncode': rc})
            raise RuntimeError('bounded_stage_timeout')
    record(name + '-status.json', {'returncode': rc, 'elapsed_seconds': time.monotonic()-start,
                                  'log_sha256': sha(ROOT / (name + '.log'))})
    if rc != 0:
        raise RuntimeError(name + '_failed')


def compiler_check(tag):
    """Compile only; explicitly select the previously verified C++ driver."""
    assert re.fullmatch(r'(?:cpu|job-[0-9]+)', tag)
    assert sha(HOST_CXX) == HOST_SHA, 'host_compiler_changed'
    root = ROOT / ('compiler-' + tag)
    root.mkdir()
    src = root / 'sanity.cu'
    src.write_text('#include <cuda_runtime.h>\n#include <cuda_bf16.h>\n#include <string>\n'
                   '__global__ void add(float* x) { x[threadIdx.x] += 1.f; }\n'
                   'std::string host_string() { return "compile-only"; }\n')
    cuda = BASE/'private-cuda128-toolchain-20260906/prefix'
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='', PATH='/usr/bin:/bin',
               CC=HOST_CXX, CXX=HOST_CXX, NVCC_CCBIN=HOST_CXX)
    command = [str(cuda/'bin/nvcc'), '-ccbin', HOST_CXX, '-arch=sm_120',
               '-std=c++17', '-c', str(src), '-o', str(root/'sanity.o')]
    invoke('compiler-'+tag, command, env, 45, root)
    record('compiler-'+tag+'-verified.json', {'command':command,
           'host_compiler_sha256':sha(HOST_CXX), 'source_sha256':sha(src),
           'object_sha256':sha(root/'sanity.o'), 'gpu_context_created':False})


def main():
    os.umask(0o077)
    assert ROOT.resolve() == ROOT and not ROOT.is_symlink()
    assert os.environ.get('SLURM_JOB_ID', '').isdigit()
    assert len(os.environ.get('SLURM_JOB_GPUS', '').split(',')) == 1 and os.environ.get('SLURM_JOB_GPUS')
    assert not os.environ.get('CUDA_VISIBLE_DEVICES')
    assert os.environ.get('SLURM_CPUS_PER_TASK') == '4'
    assert sys.executable == str(RUNTIME/'bin/python')
    compiler_check('job-'+os.environ['SLURM_JOB_ID'])
    assert sha(ROOT/'flash_attn-2.8.3.tar.gz') == SDIST_SHA
    assert sha(ROOT/'wheel-0.45.1-py3-none-any.whl') == WHEEL_SHA
    source = ROOT/'source/flash_attn-2.8.3'
    assert sha(source/'setup.py') == 'd089d876c34366979708a87abe051bf3e30f81ee4ee685e4bb446c11f0940a73'
    import torch
    assert torch.__version__ == '2.11.0+cu128' and torch.version.cuda == '12.8'
    assert torch._C._GLIBCXX_USE_CXX11_ABI and not torch.cuda.is_initialized()
    original = {str(p): sha(p) for p in [RUNTIME/'pyvenv.cfg', Path(torch.__file__)]}
    record('BUILD_INTENT.json', {'job_id': os.environ['SLURM_JOB_ID'], 'hostname': os.uname().nodename,
           'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'source_script_sha256': sha(__file__),
           'torch': torch.__version__, 'cuda': torch.version.cuda, 'arch': '120', 'reserved_gpu_count': 1,
           'cuda_context_created': False, 'gpu_reservation_upper_bound_seconds': 2760,
           'original_fingerprints': original, 'source_commit': os.environ['FA2_BUILD_CODE_COMMIT'],
           'sdist_sha256': SDIST_SHA, 'automatic_retries': 0})
    for name in ('build_deps', 'wheels', 'overlay', 'temp'):
        (ROOT/name).mkdir()
    cuda = BASE/'private-cuda128-toolchain-20260906/prefix'
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='', CUDA_HOME=str(cuda),
               PATH=str(RUNTIME/'bin')+':'+str(cuda/'bin')+':/usr/bin:/bin',
               PYTHONPATH=str(ROOT/'build_deps'), PYTHONDONTWRITEBYTECODE='1',
               MAX_JOBS='2', NVCC_THREADS='2', FLASH_ATTENTION_FORCE_BUILD='TRUE',
               CC=HOST_CXX, CXX=HOST_CXX, NVCC_CCBIN=HOST_CXX,
               FLASH_ATTN_CUDA_ARCHS='120', TMPDIR=str(ROOT/'temp'),
               PIP_NO_INDEX='1', PIP_DISABLE_PIP_VERSION_CHECK='1',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    pip = [sys.executable, '-m', 'pip']
    invoke('build-dependency', pip+['install','--no-deps','--no-index','--no-compile','--target',ROOT/'build_deps',ROOT/'wheel-0.45.1-py3-none-any.whl'],env,60)
    invoke('compile', pip+['wheel','--no-deps','--no-index','--no-build-isolation','--no-cache-dir','--wheel-dir',ROOT/'wheels',source],env,2100,source)
    wheels = list((ROOT/'wheels').glob('*.whl'))
    assert len(wheels) == 1 and re.fullmatch(r'flash_attn-2\.8\.3[^/]*cp311[^/]*linux_x86_64\.whl', wheels[0].name)
    invoke('overlay-install', pip+['install','--no-deps','--no-index','--no-compile','--target',ROOT/'overlay',wheels[0]],env,90)
    env['PYTHONPATH'] = str(ROOT/'overlay')
    check = "import json,torch,flash_attn,flash_attn_2_cuda; from transformers.utils import is_flash_attn_2_available; assert not torch.cuda.is_initialized(); print(json.dumps({'torch':torch.__version__,'flash_attn':flash_attn.__version__,'extension':flash_attn_2_cuda.__file__,'cuda_initialized':False,'availability_without_gpu':is_flash_attn_2_available()}))"
    invoke('import', [sys.executable,'-B','-c',check],env,60)
    assert {p:sha(p) for p in original} == original
    files = {p.relative_to(ROOT/'overlay').as_posix():sha(p) for p in sorted((ROOT/'overlay').rglob('*')) if p.is_file()}
    record('BUILT.json', {'classification':'ISOLATED_FA2_CPU_BUILD_NOT_GPU_ACCEPTANCE',
           'job_id':os.environ['SLURM_JOB_ID'],'wheel':wheels[0].name,'wheel_sha256':sha(wheels[0]),
           'overlay_files':files,'original_fingerprints_unchanged':True,'gpu_used':False})
    print('FA2_CPU_BUILD_COMPLETE_NOT_GPU_ACCEPTED',flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['--compiler-check-cpu']:
        compiler_check('cpu')
    else:
        assert len(sys.argv) == 1, 'unexpected_arguments'
        main()
