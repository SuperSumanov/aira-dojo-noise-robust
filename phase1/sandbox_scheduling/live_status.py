"""Read-only, allowlisted monitoring of this live batch, never raw log export."""
import datetime
import argparse
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
    frames=[dict(file=Path(f).name,line=int(n),function=fn) for f,n,fn in
            re.findall(r'File "([^"\r\n]+)", line (\d+), in ([A-Za-z0-9_]+)',tail)]
    known_messages=[v for v in ('cuInit failed','cuDeviceGetCount failed','cuDeviceGet failed',
        'cuDeviceGetUuid failed','CUDA device count mismatch','wrong node',
        'original image GPU arithmetic did not complete','new node/original image qualification failed') if v in tail]
    markers = {k: bool(re.search(p, tail)) for k, p in {
        'ready': r'Application startup complete|Uvicorn running on',
        'oom': r'CUDA out of memory|OutOfMemoryError',
        'step_wait': r'step creation temporarily disabled',
        'traceback': r'Traceback \(most recent call last\)',
        'weights_loading': r'Loading safetensors checkpoint shards|Starting to load model',
        'weights_loaded': r'Loading model weights took|Model loading took',
        'compiling': r'torch\.compile|Compiling a graph|compile range',
        'graph_capture': r'Capturing CUDA graphs|Graph capturing finished',
        'kv_initialized': r'GPU KV cache size|Maximum concurrency for',
    }.items()}
    return dict(bytes=path.stat().st_size, exception_types=kinds[-5:],trace_frames=frames[-8:],
                known_messages=known_messages, **markers)


def main():
    global ROOT
    parser=argparse.ArgumentParser();parser.add_argument('--version',choices=('v2','v3','v4','v5'),default='v2')
    args=parser.parse_args()
    ROOT=ROOT.with_name('scheduling-live-search-20261009-'+args.version)
    p = read('plan.json')
    launch = read('launch.json')
    result = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  root_exists=ROOT.exists(), plan_exists=bool(p),
                  preflight=read('preflight.json'), cpu=read('cpu.json'),
                  launch=launch, controller_closed=read('closed.json'),
                  node_qualification=read('node-qualification.json'),
                  generator_qualification=read('generator-qualification.json'))
    result['blocks'] = []
    for b in range(4):
        closed = read(f'block-{b}/closed.json')
        result['blocks'].append(dict(block=b, service_ready=read(f'block-{b}/service-ready.json'),
            budget_slot=read(f'block-{b}/budget-slot.json'),
            cycle_closed=bool(read(f'block-{b}/cycle-closed.json')),
            step_return=read(f'block-{b}/step-return.json'),
            supervisor_closed=sum((ROOT/f'episode-{i}/closed.json').exists() for i in range(4*b,4*b+4)),
            worker_finished=sum((ROOT/f'episode-{i}/finished.json').exists() for i in range(4*b,4*b+4)),
            worker_started=sum((ROOT/f'episode-{i}/native.json').exists() for i in range(4*b,4*b+4)),
            candidate_receipts=sum(sum('.private.' not in p.name for p in (ROOT/f'episode-{i}').glob('candidate-*.json')) for i in range(4*b,4*b+4)),
            scoring_receipts=sum(sum(1 for _ in (ROOT/f'episode-{i}').glob('scored-*.json')) for i in range(4*b,4*b+4)),
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
        result['node_qualification_log'] = log_shape(ROOT/'node-qualification.private.log')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
