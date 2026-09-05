"""Installed compiler metadata inside a zero-GPU CPU allocation. No installs."""
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess

OUT = Path('/research/d7/spc/yzyang4/toolchain-metadata-gpu28-20260906')
ROOTS = (Path('/usr/local'), Path('/opt'), Path('/opt1'))


def main():
    assert os.environ.get('SLURM_JOB_ID', '').isdigit()
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == '' and socket.gethostname().split('.')[0] == 'gpu28'
    commit = os.environ.get('TOOLCHAIN_SOURCE_COMMIT', '')
    assert re.fullmatch('[0-9a-f]{40}', commit)
    assert OUT.is_dir() and OUT.resolve() == OUT and not (OUT/'observed.json').exists()
    candidates = set()
    # Fixed shallow CUDA-prefix inventory. Never recurse home/project/data trees.
    for parent in ROOTS:
        if parent.is_dir():
            for p in parent.iterdir():
                if re.fullmatch(r'cuda(?:[-_][0-9.]+)?', p.name) and p.is_dir():
                    candidates.add(p)
    assert len(candidates) <= 20
    rows = []
    for p in sorted(candidates):
        nvcc = p/'bin/nvcc'
        files = {name: (p/name).is_file() for name in
                 ('bin/nvcc', 'include/cuda.h', 'include/cuda_runtime.h', 'lib64/libcudart.so', 'lib64/libcurand.so')}
        release, rc, digest = None, None, None
        if nvcc.is_file():
            command = subprocess.run([str(nvcc), '--version'], capture_output=True, timeout=10)
            rc = command.returncode
            # No arbitrary compiler stdout/stderr is emitted.
            matches = re.findall(rb'\brelease ([0-9]+\.[0-9]+)[,\s]', command.stdout)
            assert len(matches) <= 1
            release = matches[0].decode() if matches else None
            digest = hashlib.sha256(nvcc.read_bytes()).hexdigest()
        rows.append({'prefix': str(p), 'resolved_prefix': str(p.resolve()), 'files_present': files,
                     'nvcc_release': release, 'nvcc_returncode': rc, 'nvcc_sha256': digest})
    result = {'classification': 'CPU_ONLY_INSTALLED_CUDA_METADATA_NOT_GPU_QUALIFICATION',
        'job_id': os.environ['SLURM_JOB_ID'], 'host': 'gpu28', 'source_commit': commit,
        'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'python_version': list(__import__('sys').version_info[:3]), 'toolchains': rows,
        'requested_gpus': 0, 'model_imports': 0, 'archive_or_checkpoint_reads': 0,
        'installation_or_environment_changes': False,
        'scope_limitation': 'Three shallow system prefixes only; missing here does not prove no toolkit elsewhere.'}
    raw = (json.dumps(result, sort_keys=True, indent=2)+'\n').encode()
    with (OUT/'observed.json').open('xb') as stream:
        stream.write(raw)
    print(json.dumps({'status': result['classification'], 'job_id': result['job_id'],
                      'toolchains': rows, 'receipt_sha256': hashlib.sha256(raw).hexdigest()}, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'status': 'TOOLCHAIN_METADATA_FAILED_CLOSED', 'exception_type': type(exc).__name__}))
        raise SystemExit(1)
