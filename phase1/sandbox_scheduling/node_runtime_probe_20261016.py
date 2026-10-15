"""Bounded node qualification, not a search/model benchmark. No task data mounted."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import uuid

B = Path('/research/d7/spc/yzyang4')
IMAGES = {
    'task': (B/'aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif', 'python'),
    'service': (B/'local-qwen27b-20260914-zcx1k1dy/vllm.sif', '/usr/bin/python3'),
}

def visible_uuids():
    lib = ctypes.CDLL('libcuda.so.1')
    if lib.cuInit(0) != 0:
        raise RuntimeError('host_cuda_init_failed')
    count = ctypes.c_int()
    if lib.cuDeviceGetCount(ctypes.byref(count)) != 0 or count.value != 1:
        raise RuntimeError('host_single_device_isolation_failed')
    device = ctypes.c_int()
    raw = (ctypes.c_ubyte * 16)()
    if lib.cuDeviceGet(ctypes.byref(device), 0) != 0 or lib.cuDeviceGetUuid(ctypes.byref(raw), device) != 0:
        raise RuntimeError('host_uuid_query_failed')
    return ['GPU-' + str(uuid.UUID(bytes=bytes(raw)))]

def main():
    root = Path(sys.argv[1]).resolve()
    source_commit = sys.argv[2]
    assert len(source_commit) == 40 and all(c in '0123456789abcdef' for c in source_commit)
    assert root.parent == B and root.name.startswith('node-runtime-20261016-')
    node = socket.gethostname().split('.')[0]
    assert node in ('projgpu36', 'gpu1') and os.environ.get('SLURM_JOB_ID')
    job = os.environ['SLURM_JOB_ID']
    out = root / ('job-' + job)
    out.mkdir(mode=0o700)
    scratch = out/'scratch'
    scratch.mkdir(mode=0o700)
    receipt = dict(node=node, job=job, started_unix=time.time(), scientific_runs=0,
                   model_loads=0, task_data_reads=0, system_installs=0,
                   source_commit=source_commit, allocation_gpu_cap=1, allocation_seconds_cap=180,
                   code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   cuda_script_sha256=hashlib.sha256((root/'node_runtime_cuda_20261016.py').read_bytes()).hexdigest(), images={})
    env = {'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
           'HOME': str(scratch), 'USER': os.environ.get('USER', 'yzyang4'), 'LANG':'C'}
    try:
        candidates = [shutil.which(n) for n in ('singularity', 'apptainer')]
        candidates += ['/usr/bin/singularity', '/usr/local/bin/singularity',
                       '/usr/bin/apptainer', '/usr/local/bin/apptainer',
                       '/opt/singularity/bin/singularity', '/opt/apptainer/bin/apptainer']
        found = list(dict.fromkeys(str(Path(p).resolve()) for p in candidates if p and os.access(p, os.X_OK)))
        receipt['launcher_candidates'] = found
        if not found:
            modules = []
            for init in ('/etc/profile.d/modules.sh', '/etc/profile.d/lmod.sh', '/usr/share/modules/init/bash'):
                if Path(init).is_file():
                    r = subprocess.run(['/bin/bash', '--noprofile', '--norc', '-c',
                                        '. "$1"; module -t avail 2>&1', 'probe', init],
                                       env=env, capture_output=True, text=True, timeout=12)
                    modules += [line[:250] for line in r.stdout.splitlines()
                                if any(x in line.lower() for x in ('singularity', 'apptainer'))]
            receipt['matching_module_metadata'] = modules
            receipt['status'] = 'no_launcher_in_checked_locations'
            return 2
        launcher = found[0]
        r = subprocess.run([launcher, '--version'], env=env, capture_output=True, text=True, timeout=10)
        receipt['launcher_version'] = r.stdout.strip()[:200]
        receipt['launcher_version_rc'] = r.returncode
        if r.returncode:
            raise RuntimeError('launcher_version_failed')
        devices = visible_uuids()
        receipt['host_gpu_uuids'] = devices
        for label, (image, python) in IMAGES.items():
            before = image.stat()
            child_env = dict(env)
            for prefix in ('SINGULARITYENV_', 'APPTAINERENV_'):
                child_env[prefix+'CUDA_VISIBLE_DEVICES'] = devices[0]
                child_env[prefix+'EXPECTED_GPU_UUID'] = devices[0]
                child_env[prefix+'PYTHONDONTWRITEBYTECODE'] = '1'
                child_env[prefix+'OMP_NUM_THREADS'] = '1'
            cmd = [launcher, 'exec', '--containall', '--cleanenv', '--no-home', '--nv',
                   '--no-mount', 'bind-paths,cwd', '--bind', str(scratch)+':/probe-work:rw',
                   '--bind', str(root/'node_runtime_cuda_20261016.py')+':/probe-cuda.py:ro',
                   '--pwd', '/probe-work', str(image), python, '-B', '/probe-cuda.py']
            tick = time.monotonic()
            r = subprocess.run(cmd, env=child_env, capture_output=True, text=True, timeout=50)
            after = image.stat()
            item = dict(returncode=r.returncode, elapsed_seconds=time.monotonic()-tick,
                        image_path=str(image), image_size=before.st_size,
                        image_stat_unchanged=(before.st_size, before.st_mtime_ns)==(after.st_size, after.st_mtime_ns))
            payloads = [x[len('PROBE_JSON='):] for x in r.stdout.splitlines() if x.startswith('PROBE_JSON=')]
            if payloads:
                item['cuda'] = json.loads(payloads[-1])
            # Only controlled, credential-free process receives this environment.
            item['stderr_tail'] = r.stderr[-2200:]
            receipt['images'][label] = item
            if r.returncode or not item['image_stat_unchanged'] or not item.get('cuda',{}).get('passed'):
                receipt['status'] = label+'_image_failed'
                return 3
        receipt['status'] = 'both_original_images_cuda_passed'
        return 0
    except Exception as exc:
        receipt['status'] = 'failed_closed'
        receipt['error_type'] = type(exc).__name__
        receipt['error'] = str(exc)[:300]
        return 4
    finally:
        receipt['ended_unix'] = time.time()
        with (out/'receipt.json').open('x') as f:
            json.dump(receipt, f, indent=2)
        print(json.dumps(receipt), flush=True)

if __name__ == '__main__':
    sys.exit(main())
