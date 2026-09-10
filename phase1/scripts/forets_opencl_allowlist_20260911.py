"""One allocated GPU, original SIF, explicit devices/libraries; never --nv.

Not a launcher. Run only in a separate 5-minute, one-GPU gpu28 srun.
The old diagnostic is reused only after an independent namespace allowlist gate.
No task data, model, credentials, packages, fallback, or automatic retry.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import stat
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from forets_opencl_readonly_ab import IMAGE, PROBE

# Save the reached stage before a native-library abort could bypass Python's
# exception handler. The original diagnostic remains unchanged.
OBSERVABLE_PROBE = PROBE.replace(
    "r['chosen_platform_index'] = platform_index",
    "r['chosen_platform_index'] = platform_index\n"
    "                print('OPENCL_STAGE ' + json.dumps(r, sort_keys=True), flush=True)")


def run(command, timeout=15):
    return subprocess.run(command, capture_output=True, text=True,
                          check=True, timeout=timeout)


def driver_binds(cache):
    """Explicit driver + OpenCL-loader subset of the site's legacy --nv list.

    The original SIF has no OpenCL loader (verified without --nv). Bind the
    site's loader read-only, in BOTH conditions; do not install a new version.
    """
    paths = {}
    selected_loader = None
    for line in cache.splitlines():
        fields = line.split()
        if len(fields) < 4 or 'x86-64' not in line or '=>' not in fields:
            continue
        soname, path = fields[0], Path(fields[-1])
        if not (soname.startswith('libnvidia-') or soname.startswith(('libcuda.so','libOpenCL.so'))):
            continue
        if soname.startswith('libOpenCL.so'):
            # Freeze one existing SONAME-1 implementation in ldconfig's reported
            # order. Do not combine aliases belonging to different installations.
            # Same selection in both fresh containers, never outcome-based.
            if soname != 'libOpenCL.so.1' or selected_loader is not None:
                continue
            selected_loader = path
        resolved = path.resolve(strict=True)
        if not resolved.is_file() or any(c in str(resolved) for c in ',:\n'):
            raise ValueError('unsafe library path')
        for name in (soname, resolved.name):
            if name in paths and paths[name] != resolved:
                raise ValueError('ambiguous driver library')
            paths[name] = resolved
    for required in ('libcuda.so.1', 'libnvidia-opencl.so.1', 'libnvidia-ml.so.1','libOpenCL.so.1'):
        if required not in paths:
            raise ValueError('required host driver library absent: ' + required)
    return paths


GATE = r'''
import json,os,pathlib,re,stat
expected=int(os.environ['EXPECTED_GPU_MINORS'])
devices=[p for p in pathlib.Path('/dev').iterdir() if re.fullmatch(r'nvidia[0-9]+',p.name)]
if [p.name for p in devices] != ['nvidia'+str(expected)]:
    raise RuntimeError('unexpected GPU path exposed; NO GPU library calls')
s=devices[0].stat()
if not stat.S_ISCHR(s.st_mode) or os.major(s.st_rdev)!=int(os.environ['EXPECTED_GPU_MAJOR']) or os.minor(s.st_rdev)!=expected:
    raise RuntimeError('GPU device number mismatch')
fd=os.open(devices[0],os.O_RDWR|os.O_CLOEXEC);os.close(fd)
mounts={line.split()[4]:line.split()[5].split(',') for line in open('/proc/self/mountinfo')}
libs=[p for p in pathlib.Path('/run/forets-driverlibs').iterdir()]
if not libs or any('ro' not in mounts.get(str(p),[]) for p in libs):
    raise RuntimeError('driver library bind not read-only')
print('ALLOWLIST_GATE '+json.dumps({'exact_device_namespace':True,'minor':expected,'readonly_driver_libraries':len(libs)}),flush=True)
'''

CUDA_CHECK = r'''
import json,torch
if not torch.cuda.is_available() or torch.cuda.device_count()!=1:
    raise RuntimeError('expected exactly one CUDA GPU; no CPU fallback')
x=torch.tensor([[1.,2.],[3.,4.]],device='cuda')
y=(x@x).cpu().tolist()
if y != [[7.,10.],[15.,22.]]:raise RuntimeError('CUDA arithmetic incorrect')
print('CUDA_ALLOWLIST '+json.dumps({'version':torch.__version__,'device':torch.cuda.get_device_name(0),'devices':1,'arithmetic_correct':True}),flush=True)
'''


def bounded_container(command, env, timeout):
    p = subprocess.Popen(command, env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, err = p.communicate(timeout=timeout)
        return p.returncode, out, err
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate(timeout=10)
        return -9, '', 'bounded_timeout'


def main():
    here = Path(__file__).resolve().parent
    output = here / 'result.json'
    job = os.environ.get('SLURM_JOB_ID', '')
    step = os.environ.get('SLURM_STEP_ID', '')
    assigned = os.environ.get('SLURM_STEP_GPUS', '')
    commit = os.environ.get('FORETS_SOURCE_COMMIT', '')
    if (not job.isdigit() or not step.isdigit() or not re.fullmatch(r'\d+', assigned)
            or not re.fullmatch(r'[0-9a-f]{40}', commit)
            or job in {'12535','13004','13007','13009','13010'}
            or socket.gethostname().split('.')[0] != 'gpu28'):
        raise RuntimeError('requires NEW explicit single-GPU gpu28 step')
    with (here / 'execution.claim').open('x') as f:
        f.write(job + '.' + step + '\n')
    if output.exists():
        raise FileExistsError('preserve prior result')
    started = time.monotonic()
    before = IMAGE.stat()
    report = dict(role='explicit_device_opencl_diagnostic_not_effect', job_id=job,
                  source_commit=commit,
                  step_id=step, observed_utc=datetime.now(timezone.utc).isoformat(),
                  node='gpu28', variants=[], api_calls=0, task_runs=0, critic_calls=0,
                  image=str(IMAGE), image_size=before.st_size,
                  image_mtime_ns=before.st_mtime_ns,
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  shared_probe_sha256=hashlib.sha256((here/'forets_opencl_readonly_ab.py').read_bytes()).hexdigest())
    try:
        mapping = run(['nvidia-smi','--query-gpu=index,uuid','--format=csv,noheader,nounits']).stdout
        xml = ET.fromstring(run(['nvidia-smi','-q','-x']).stdout)
        ids = {int(line.split(',')[0]):line.split(',')[1].strip() for line in mapping.splitlines()}
        uuid = ids[int(assigned)]
        gpu = next(g for g in xml.findall('gpu') if g.findtext('uuid') == uuid)
        minor = int(gpu.findtext('minor_number'))
        device = Path('/dev/nvidia'+str(minor))
        s = device.stat()
        if not stat.S_ISCHR(s.st_mode) or os.minor(s.st_rdev) != minor:
            raise RuntimeError('host device inconsistent')
        cache = run(['/sbin/ldconfig','-p']).stdout
        report['loader_cache_entries']=[x.strip() for x in cache.splitlines() if 'libOpenCL.so' in x]
        libs = driver_binds(cache)
        report.update(slurm_step_gpu=assigned, allocated_uuid=uuid, allocated_minor=minor,
                      driver_version=xml.findtext('driver_version'),
                      driver_libraries={k:str(v) for k,v in libs.items()})
        cmd = ['singularity','exec','--containall','--cleanenv','--no-home',
               '--no-mount','bind-paths,cwd']
        devices = [device,Path('/dev/nvidiactl'),Path('/dev/nvidia-uvm')]
        optional = Path('/dev/nvidia-uvm-tools')
        if optional.exists(): devices.append(optional)
        for p in devices:
            if not stat.S_ISCHR(p.stat().st_mode): raise RuntimeError('not a device')
            cmd += ['--bind',f'{p}:{p}']
        for name,p in sorted(libs.items()):
            cmd += ['--bind',f'{p}:/run/forets-driverlibs/{name}:ro']
        env = {'PATH':'/usr/local/bin:/usr/bin:/bin', 'HOME':os.environ['HOME']}
        inside = [str(IMAGE),'env','LD_LIBRARY_PATH=/run/forets-driverlibs',
                  'HOME=/workspace/.home','PYTHONUSERBASE=/workspace/.local','PYTHONUNBUFFERED=1',
                  'CUDA_VISIBLE_DEVICES='+uuid,'CUDA_DEVICE_ORDER=PCI_BUS_ID',
                  f'EXPECTED_GPU_MINORS={minor}',f'EXPECTED_GPU_MAJOR={os.major(s.st_rdev)}',
                  'OMP_NUM_THREADS=1','python','-c']
        vendors = here / 'opencl-vendors'
        if (vendors/'nvidia.icd').read_text().strip() != 'libnvidia-opencl.so.1':
            raise RuntimeError('unexpected ICD')
        for variant in ('no_icd','readonly_icd'):
            workspace=here/('workspace-'+variant)
            (workspace/'.home/.local/share/jupyter/runtime').mkdir(parents=True)
            (workspace/'.local').mkdir()
            case = cmd + ['--bind',f'{workspace}:/workspace:rw','--pwd','/workspace']
            if variant=='readonly_icd': case+=['--bind',f'{vendors}:/etc/OpenCL/vendors:ro']
            command = case+inside+[GATE+'\n'+OBSERVABLE_PROBE]
            rc,out,err = bounded_container(command,env,min(95, max(1,260-(time.monotonic()-started))))
            # No arbitrary logs/credentials; print only our machine-readable lines.
            gates = [json.loads(x.removeprefix('ALLOWLIST_GATE ')) for x in out.splitlines() if x.startswith('ALLOWLIST_GATE ')]
            probes = [json.loads(x.removeprefix('OPENCL_DIAGNOSTIC ')) for x in out.splitlines() if x.startswith('OPENCL_DIAGNOSTIC ')]
            row = dict(variant=variant,rc=rc,gates=gates,probes=probes,
                       stages=[json.loads(x.removeprefix('OPENCL_STAGE ')) for x in out.splitlines() if x.startswith('OPENCL_STAGE ')],
                       command=command[:-1]+['<fixed source GATE + OBSERVABLE_PROBE>'],
                       timed_out=(err=='bounded_timeout'))
            if rc or len(gates)!=1 or len(probes)!=1:
                row['error_tail'] = (err[-1500:] if not re.search(r'(?i)(?:sk-[a-z0-9_.-]{12,}|Bearer\s+)',err) else 'WITHHELD')
            report['variants'].append(row)
            print(json.dumps(row),flush=True)
            if rc or len(gates)!=1 or len(probes)!=1 or not probes[0].get('gpu_isolation_verified'):
                report['blocked']='namespace_or_diagnostic_failure';break
        if any(v['gates'] for v in report['variants']):
            # Independent control for the changed driver binding, even when an
            # OpenCL native library failed. This new process rechecks isolation.
            workspace=here/'workspace-cuda'
            (workspace/'.home').mkdir(parents=True)
            (workspace/'.local').mkdir()
            cuda_cmd=cmd+['--bind',f'{workspace}:/workspace:rw','--pwd','/workspace']
            rc,out,err=bounded_container(cuda_cmd+inside+[GATE+'\n'+CUDA_CHECK],env,min(30,max(1,280-(time.monotonic()-started))))
            report['cuda_rc']=rc
            report['cuda']=[json.loads(x.removeprefix('CUDA_ALLOWLIST ')) for x in out.splitlines() if x.startswith('CUDA_ALLOWLIST ')]
            if rc: report['cuda_error_type']='bounded_timeout' if err=='bounded_timeout' else 'container_failed'
    except Exception as exc:
        report['blocked']=type(exc).__name__
        report['error']=str(exc)[:500]
    finally:
        after=IMAGE.stat()
        report['image_metadata_unchanged']=(before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
        report['diagnostic_seconds']=time.monotonic()-started
        with output.open('x') as f:json.dump(report,f,indent=2)
        print('FINAL '+json.dumps(report),flush=True)


if __name__=='__main__':main()
