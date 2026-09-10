"""Target the observed LightGBM/OpenCL error, outside the active paired run.

Two fresh containers: original --nv vs the same image plus one read-only ICD
directory. No task data, generator, critic, Torch change, or CPU fallback.
Reject access to any GPU outside the assigned one before OpenCL discovery.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import socket
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

IMAGE = Path('/research/d7/spc/yzyang4/aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif')

PROBE = r'''
import ctypes as C, ctypes.util, json, os, pathlib, re
r = dict(role='synthetic_opencl_library_diagnostic_not_task_result', task_runs=0, critic_calls=0)
expected = {int(x) for x in os.environ['EXPECTED_GPU_MINORS'].split(',')}
expected_major = int(os.environ['EXPECTED_GPU_MAJOR'])
accessible = []
masked = []
for p in pathlib.Path('/dev').glob('nvidia[0-9]*'):
    if not re.fullmatch(r'nvidia[0-9]+', p.name): continue
    if os.major(p.stat().st_rdev) != expected_major:
        masked.append(str(p))
        continue
    try:
        fd = os.open(p, os.O_RDONLY | os.O_CLOEXEC)
    except OSError:
        continue
    else:
        os.close(fd)
        accessible.append(os.minor(p.stat().st_rdev))
r['accessible_gpu_minors'] = sorted(accessible)
r['allocated_gpu_minors'] = sorted(expected)
r['non_gpu_device_placeholders'] = sorted(masked)
r['gpu_isolation_verified'] = set(accessible) == expected and len(expected) == 1
r['vendor_directory_exists'] = pathlib.Path('/etc/OpenCL/vendors').is_dir()
r['icd_files'] = sorted(p.name for p in pathlib.Path('/etc/OpenCL/vendors').glob('*.icd'))
if r['gpu_isolation_verified']:
    try:
        cl = C.CDLL('libOpenCL.so.1')
        r['loader_loaded'] = True
        cl.clGetPlatformIDs.argtypes = [C.c_uint, C.POINTER(C.c_void_p), C.POINTER(C.c_uint)]
        cl.clGetPlatformIDs.restype = C.c_int
        n = C.c_uint()
        rc = cl.clGetPlatformIDs(0, None, C.byref(n))
        r.update(platform_rc=rc, platform_count=n.value)
        if rc == 0 and 0 < n.value <= 16:
            platforms = (C.c_void_p * n.value)()
            if cl.clGetPlatformIDs(n, platforms, None) != 0: raise RuntimeError('platform lookup')
            cl.clGetDeviceIDs.argtypes = [C.c_void_p, C.c_ulong, C.c_uint, C.POINTER(C.c_void_p), C.POINTER(C.c_uint)]
            cl.clGetDeviceIDs.restype = C.c_int
            counts = []
            for platform in platforms:
                devices = C.c_uint()
                device_rc = cl.clGetDeviceIDs(platform, 4, 0, None, C.byref(devices))
                counts.append(dict(rc=device_rc, gpu_devices=devices.value))
            r['platform_devices'] = counts
            if sum(v['gpu_devices'] for v in counts) == 1:
                # An explicit GPU-only library fit, not a critic or agent update.
                # No package installation; no retry with device_type=cpu.
                import numpy as np, lightgbm as lgb
                rng = np.random.default_rng(0)
                x = rng.normal(size=(64, 4)); y = (x[:, 0] > 0).astype(int)
                r.update(lightgbm_version=lgb.__version__, synthetic_fit_started=True)
                platform_index = next(i for i, v in enumerate(counts) if v['gpu_devices'] == 1)
                r['chosen_platform_index'] = platform_index
                lgb.train(dict(objective='binary', device_type='gpu', gpu_platform_id=platform_index,
                    gpu_device_id=0, max_bin=15, min_data_in_bin=1, min_data_in_leaf=1,
                    num_leaves=3, num_threads=1, verbosity=-1, seed=0),
                    lgb.Dataset(x, label=y), num_boost_round=2)
                r['synthetic_gpu_fit_completed'] = True
    except Exception as exc:
        r['error_type'] = type(exc).__name__
        r['no_opencl_device_error'] = 'No OpenCL device' in str(exc)
else:
    r['blocked'] = 'assigned_gpu_isolation_not_verified_no_opencl_calls'
print('OPENCL_DIAGNOSTIC ' + json.dumps(r, sort_keys=True))
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--launch', action='store_true', help='One bounded srun, only after the paired job is terminal')
    p.add_argument('--mask-unallocated', action='store_true', help='Read-only /dev/null masks, identically in both variants')
    args = p.parse_args()
    here = Path(__file__).resolve().parent
    if args.output.resolve().parent != here:
        raise ValueError('diagnostic output must be next to this isolated deployment')
    if args.launch:
        env = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
        previous = subprocess.run(['sacct', '-j', '13004', '-P', '-n', '--format=JobID,State'],
            env=env, capture_output=True, text=True, check=True, timeout=20)
        states = [line.split('|')[:2] for line in previous.stdout.splitlines() if line.strip()]
        terminal = {'COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT', 'PREEMPTED', 'NODE_FAIL', 'OUT_OF_MEMORY'}
        if (not any(j == '13004' for j, _ in states)
                or any(s.split()[0].rstrip('+') not in terminal for _, s in states)):
            raise RuntimeError('paired allocation or a step is not terminal; no new job')
        queue = subprocess.run(['squeue', '--user=yzyang4', '-h', '--format=%A'], env=env,
            capture_output=True, text=True, check=True, timeout=20)
        if '13004' in queue.stdout.split():
            raise RuntimeError('paired allocation remains in queue; wait for cleanup')
        command = ['srun', '--immediate=30', '--partition=gpu_24h', '--account=gpu', '--qos=gpu',
            '--nodelist=gpu28', '--nodes=1', '--ntasks=1', '--cpus-per-task=2', '--gres=gpu:1',
            '--time=00:05:00', '--job-name=forets-opencl-ab', '--kill-on-bad-exit=1',
            '--output='+str(here/'opencl-%j.out'), '--error='+str(here/'opencl-%j.err'),
            sys.executable, str(Path(__file__).resolve()), '--output', str(args.output.resolve())]
        if args.mask_unallocated:
            command.append('--mask-unallocated')
        with (here/'launch.claim.json').open('x') as f:
            json.dump(dict(command=command, observed_utc=datetime.now(timezone.utc).isoformat(),
                previous_job_states=states, automatic_retry=False), f, indent=2)
        os.execvpe('srun', command, env)
    job, step = os.environ.get('SLURM_JOB_ID', ''), os.environ.get('SLURM_STEP_ID', '')
    assigned = os.environ.get('SLURM_STEP_GPUS', '')
    if (not job.isdigit() or job == '13004' or not step.isdigit()
            or socket.gethostname().split('.')[0] != 'gpu28' or not re.fullmatch(r'\d+', assigned)):
        raise RuntimeError('requires a separate, explicit one-GPU step on gpu28')
    if args.output.exists():
        raise FileExistsError('preserve prior diagnostic output')
    print(json.dumps(dict(status='OPENCL_DIAGNOSTIC_STARTED', job_id=job, step_id=step, node='gpu28')), flush=True)
    mapping = subprocess.run(['nvidia-smi', '--query-gpu=index,uuid', '--format=csv,noheader,nounits'],
        capture_output=True, text=True, check=True, timeout=15)
    xml = subprocess.run(['nvidia-smi', '-q', '-x'], capture_output=True, text=True, check=True, timeout=15)
    by_uuid = {g.findtext('uuid'):int(g.findtext('minor_number')) for g in ET.fromstring(xml.stdout).findall('gpu')}
    minors = {int(line.split(',')[0]):by_uuid[line.split(',')[1].strip()] for line in mapping.stdout.splitlines()}
    minor = minors[int(assigned)]
    gpu_major = os.major(Path(f'/dev/nvidia{minor}').stat().st_rdev)
    masked_devices = []
    if args.mask_unallocated:
        for device in sorted(Path('/dev').glob('nvidia[0-9]*')):
            if (re.fullmatch(r'nvidia[0-9]+', device.name)
                    and os.major(device.stat().st_rdev) == gpu_major
                    and os.minor(device.stat().st_rdev) != minor):
                masked_devices.append(str(device))
    vendors = Path(__file__).with_name('opencl-vendors')
    icd = vendors / 'nvidia.icd'
    if icd.read_text().strip() != 'libnvidia-opencl.so.1':
        raise ValueError('unexpected ICD contents')
    before = IMAGE.stat()
    report = dict(job_id=job, step_id=step, node='gpu28', observed_utc=datetime.now(timezone.utc).isoformat(),
        image=str(IMAGE), image_bytes=before.st_size, image_mtime_ns=before.st_mtime_ns,
        icd_sha256=hashlib.sha256(icd.read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), variants=[])
    report['common_readonly_device_masks'] = masked_devices
    report['baseline_is_original_image_with_common_device_masks'] = bool(masked_devices)
    env = {k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ('KEY','TOKEN','SECRET','PASSWORD'))}
    for variant in ('original', 'readonly_icd'):
        command = [shutil.which('singularity') or 'singularity', 'exec', '--containall', '--cleanenv', '--no-home', '--nv']
        for device in masked_devices:
            command += ['--bind', f'/dev/null:{device}:ro']
        if variant == 'readonly_icd':
            command += ['--bind', f'{vendors}:/etc/OpenCL/vendors:ro']
        command += [str(IMAGE), 'env', f'EXPECTED_GPU_MINORS={minor}', f'EXPECTED_GPU_MAJOR={gpu_major}',
            'CUDA_VISIBLE_DEVICES='+os.environ.get('CUDA_VISIBLE_DEVICES', assigned),
            'OMP_NUM_THREADS=1', 'python', '-c', PROBE]
        start = time.monotonic()
        process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True)
        try:
            stdout, _ = process.communicate(timeout=100)
            lines = [s for s in stdout.splitlines() if s.startswith('OPENCL_DIAGNOSTIC ')]
            row = json.loads(lines[0].split(' ', 1)[1]) if len(lines) == 1 else dict(error='missing_diagnostic_record')
            row['returncode'] = process.returncode
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate(timeout=10)
            row = dict(error='bounded_diagnostic_timeout')
        row.update(variant=variant, wall_seconds=time.monotonic()-start)
        report['variants'].append(row)
        if row.get('gpu_isolation_verified') is not True:
            report['blocked'] = 'isolation_or_diagnostic_failure_no_further_variant'
            break
    after = IMAGE.stat()
    report['image_metadata_unchanged'] = (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    report['limitation'] = 'Synthetic library result only; no real-task improvement or full environment validity claim.'
    with args.output.open('x', encoding='utf-8') as f:
        json.dump(report, f, indent=2); f.write('\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
