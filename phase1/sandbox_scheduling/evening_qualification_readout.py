"""Closeout-only CSV/JSON for the fixed no-data live qualification."""
import argparse
import csv
import json
import os
from pathlib import Path
import statistics
import subprocess
from lifecycle_pilot import read,write,sha

ROOT = Path('/research/d7/spc/yzyang4/scheduling-readiness-live-20261008-evening-v1')
PIN = '18331b8dcdc5c8df5c6cf8a85b7000218d0bcb23e57834fe49f45bb9c6fba53c'


def main(output):
    if sha(ROOT/'plan.json') != PIN:
        raise ValueError('qualification plan drift')
    plan = read(ROOT/'plan.json')
    closed = read(ROOT/'closed.json')
    if closed != dict(planned=3,attempted=3,complete=True,returncodes=[0,0,0]):
        raise ValueError('not complete')
    rows = []
    for row in plan['schedule']:
        ep = ROOT/f'episode-{row["index"]}'
        done = read(ep/'completed.json'); calls = read(ep/'handshake.json')
        if not done['complete'] or done['error_type'] is not None or read(ep/'closed.json')['returncode'] != 0:
            raise ValueError('failed episode')
        if not calls or not all(c['ready'] for c in calls):
            raise ValueError('failed handshake')
        fixture = ep/'work/fixture.json'
        if sha(fixture) != done['fixture_sha256'] or read(fixture) != dict(elements=16777216,sum=16777216,dtype='torch.float32'):
            raise ValueError('fixture output')
        samples = {v['phase']:v for v in read(ep/'samples.json')}
        rows.append(dict(**row,job='17124',source_commit=plan['source_commit'],plan_sha256=PIN,
            allocation_cap_seconds=600,worker_seconds=done['elapsed_seconds'],
            fixture_exec_seconds=done['exec_seconds'],handshake_calls=len(calls),
            handshake_total_seconds=sum(c['seconds'] for c in calls),
            gpu_uuid=done['gpu_uuid'],fixture_sha256=done['fixture_sha256'],
            close_to_no_client_seconds=done['close_start_to_no_client_seconds'],
            before_mib=samples['before_container']['data']['metrics']['memory_used_mib'],
            after_close_mib=samples['after_close_no_clients']['data']['metrics']['memory_used_mib'],complete=True))
    if len({v['gpu_uuid'] for v in rows}) != 1 or len({v['fixture_sha256'] for v in rows}) != 1:
        raise ValueError('GPU/output identity')
    raw = subprocess.check_output(['sacct','-j','17124','-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],
        text=True,timeout=20,env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'))
    allocations = [s.split('|') for s in raw.splitlines() if s.split('|')[0]=='17124']
    if len(allocations)!=1 or allocations[0][1]!='COMPLETED' or allocations[0][4]!='0:0':
        raise ValueError('allocation not cleanly completed')
    seconds = int(allocations[0][2])
    if not 0 < seconds <= 600 or 'gres/gpu=1' not in allocations[0][3].split(','):
        raise ValueError('GPU budget')
    output.mkdir(mode=0o700,exist_ok=False)
    with (output/'runs.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    result=dict(job='17124',plan_sha256=PIN,planned=3,completed=3,allocation_seconds=seconds,
        whole_pool_gpu_hours=seconds/3600,source_commit=plan['source_commit'],rows=rows,
        worker_seconds_median=statistics.median(v['worker_seconds'] for v in rows),
        worker_seconds_sample_variance=statistics.variance(v['worker_seconds'] for v in rows),
        boundary='Three fresh-kernel qualification fixtures, not speedup comparisons or proof of rare-failure reliability. No dataset/model training/API.')
    write(output/'summary.json',result)
    print(json.dumps({k:result[k] for k in ('job','planned','completed','allocation_seconds','whole_pool_gpu_hours')},sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    main(Path(parser.parse_args().output))
