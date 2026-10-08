"""Read-only, allowlisted monitoring of this live batch, never raw log export."""
import datetime
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path('/research/d7/spc/yzyang4/scheduling-live-search-20261009-v2')


def read(name):
    p = ROOT / name
    return json.loads(p.read_bytes()) if p.exists() else {}


def log_shape(path):
    if not path.exists():
        return None
    # No log line, prompt, response, arbitrary exception value, or environment
    # value leaves the host. These are diagnosis hints, not failure verdicts.
    with path.open('rb') as f:
        f.seek(max(0, path.stat().st_size - 65536))
        tail = f.read().decode('utf-8', errors='replace')
    kinds = re.findall(r'^([A-Za-z][A-Za-z0-9_.]*(?:Error|Exception|Expired))(?::|$)', tail, re.M)
    markers = {k: bool(re.search(p, tail)) for k, p in {
        'ready': r'Application startup complete|Uvicorn running on',
        'oom': r'CUDA out of memory|OutOfMemoryError',
        'step_wait': r'step creation temporarily disabled',
        'traceback': r'Traceback \(most recent call last\)',
    }.items()}
    return dict(bytes=path.stat().st_size, exception_types=kinds[-5:], **markers)


def main():
    p = read('plan.json')
    launch = read('launch.json')
    result = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  root_exists=ROOT.exists(), plan_exists=bool(p),
                  preflight=read('preflight.json'), cpu=read('cpu.json'),
                  launch=launch, controller_closed=read('closed.json'),
                  generator_qualification=read('generator-qualification.json'))
    result['blocks'] = []
    for b in range(4):
        closed = read(f'block-{b}/closed.json')
        result['blocks'].append(dict(block=b, service_ready=read(f'block-{b}/service-ready.json'),
            cycle_closed=bool(read(f'block-{b}/cycle-closed.json')),
            step_return=read(f'block-{b}/step-return.json'),
            supervisor_closed=sum((ROOT/f'episode-{i}/closed.json').exists() for i in range(4*b,4*b+4)),
            worker_finished=sum((ROOT/f'episode-{i}/finished.json').exists() for i in range(4*b,4*b+4)),
            worker_started=sum((ROOT/f'episode-{i}/native.json').exists() for i in range(4*b,4*b+4)),
            gpu_clean=closed.get('gpu_clean'), service_cleanup=read(f'block-{b}/service-cleanup.json'),
            service_log=log_shape(ROOT/f'block-{b}/service.private.log'),
            block_log=log_shape(ROOT/f'block-{b}/block.private.log')))
    job = launch.get('job')
    if job is not None:
        if not re.fullmatch(r'\d+', str(job)):
            raise ValueError('unexpected job identity')
        env = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
        for key, args in (
            ('queue', ['squeue', '-h', '-j', str(job), '-o', '%i,%T,%M,%R']),
            ('accounting', ['sacct', '-X', '-n', '-P', '-j', str(job),
                            '--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode,Start,End']),
        ):
            r = subprocess.run(args, env=env, capture_output=True, text=True, timeout=20)
            result[key] = dict(returncode=r.returncode, rows=r.stdout.strip().splitlines())
        result['allocation_log'] = log_shape(ROOT/f'allocation-{job}.err')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
