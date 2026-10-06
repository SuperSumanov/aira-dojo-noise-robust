"""Post-closure descriptive analysis of the six approved lifecycle fixtures.

No throughput, training benefit, production leak or warm-start speedup estimate.
Each window median is one repeated-run observation, not independent samples.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics


PLAN_SHA = 'cbece7bc34c10a99e9d65e39ccbb3623d20d047894b94616fa35052e434cda86'
FIXTURE_SHA = '56a1a11cb40374546f960efe2790a4f8c21c51068c57108a41a2096325b8ce9b'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stats(values):
    return dict(n=len(values), median=statistics.median(values) if values else None,
                sample_variance=statistics.variance(values) if len(values)>1 else None,
                minimum=min(values) if values else None, maximum=max(values) if values else None)


def analyze(bundle):
    if bundle['plan_sha256'] != PLAN_SHA or not bundle['closed']['complete']:
        raise ValueError('unclosed or unfrozen batch')
    if bundle['closed']['planned'] != 6 or bundle['closed']['attempted'] != 6:
        raise ValueError('incomplete denominator')
    if bundle['closed']['returncodes'] != [0]*6 or len(bundle['episodes']) != 6:
        raise ValueError('execution incomplete')
    rows=[]
    gpu=set()
    for planned, ep in zip(bundle['plan']['schedule'], bundle['episodes']):
        result, samples=ep['completed'], ep['samples']
        if not result['complete'] or result['error_type'] is not None:
            raise ValueError('failed trial')
        if any(planned[key] != result[key] for key in ('index','arm','repeat','seed')):
            raise ValueError('trial identity mismatch')
        if result['fixture_sha256'] != FIXTURE_SHA:
            raise ValueError('output not identical')
        gpu.add(result['gpu_uuid'])
        grouped={}
        previous=-1
        for sample in samples:
            if sample['elapsed_seconds'] <= previous:
                raise ValueError('nonmonotonic measurement')
            previous=sample['elapsed_seconds']
            if (sample['status']!='ok' or sample['uuid']!=result['gpu_uuid']
                    or sample['scope']!='whole_device_not_candidate'):
                raise ValueError('measurement scope mismatch')
            value=sample['data']['metrics']['memory_used_mib']
            if value is None or not isinstance(value,(int,float)) or value<0:
                raise ValueError('unknown memory, do not impute')
            grouped.setdefault(sample['phase'],[]).append(value)
        for name in ('before_container','after_fetch_before_close','release_verified','after_close_no_clients'):
            if len(grouped.get(name,[])) != 1:
                raise ValueError('missing boundary')
        if len(grouped.get('window',[]))<3:
            raise ValueError('insufficient window measurements')
        baseline=grouped['before_container'][0]
        rows.append(dict(**planned,source_commit=result['source_commit'],job=bundle['job'],
            plan_sha256=PLAN_SHA,task_image_sha256=bundle['preflight']['task_image_sha256'],
            driver_version=samples[0]['data']['driver_version'],gpu_uuid=result['gpu_uuid'],
            window_samples=len(grouped['window']),before_mib=baseline,
            after_fetch_mib=grouped['after_fetch_before_close'][0],
            window_median_mib=statistics.median(grouped['window']),
            window_median_above_baseline_mib=statistics.median(grouped['window'])-baseline,
            release_verified_mib=grouped['release_verified'][0],
            after_close_mib=grouped['after_close_no_clients'][0],
            close_to_observed_no_client_seconds=result['close_start_to_no_client_seconds'],
            exec_seconds_diagnostic_only=result['exec_seconds'],
            worker_seconds=result['elapsed_seconds'],fixture_sha256=result['fixture_sha256']))
    if len(gpu)!=1:
        raise ValueError('hardware changed')
    groups={}
    for arm in ('keep_10s','close_now'):
        group=[row for row in rows if row['arm']==arm]
        if len(group)!=3:
            raise ValueError('unbalanced conditions')
        groups[arm]={name:stats([row[name] for row in group]) for name in
            ('window_median_above_baseline_mib','close_to_observed_no_client_seconds')}
    paired=[]
    for repeat in range(3):
        pair={row['arm']:row for row in rows if row['repeat']==repeat}
        if set(pair)!={'keep_10s','close_now'}:
            raise ValueError('missing pair')
        paired.append(dict(repeat=repeat,window_delta_mib=
            pair['keep_10s']['window_median_above_baseline_mib']-
            pair['close_now']['window_median_above_baseline_mib']))
    return rows,dict(planned=6,completed=6,groups=groups,paired=paired,
        all_after_close_equal_baseline=all(row['after_close_mib']==row['before_mib'] for row in rows),
        all_outputs_identical=True,
        limit='Controlled 64MiB tensor fixture, one GPU, three repeats, one seed. '
              'First trial cold startup retained; execution durations are NOT a speed comparison. '
              'Close latency is an observed upper bound including teardown/query. '
              'Close-now window starts sampling after close returns, unlike keep window. '
              'Not a production leak, resource demand bound, scheduler throughput or end-to-end quality result.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    bundle=json.loads(args.input.read_text(encoding='utf8'))
    rows,summary=analyze(bundle)
    summary.update(input_sha256=digest(args.input),analyzer_sha256=digest(Path(__file__)),
        plan_sha256=PLAN_SHA,job=bundle['job'],allocation=bundle['allocation'])
    args.output.mkdir(exist_ok=False)
    with (args.output/'runs.csv').open('x',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    with (args.output/'summary.json').open('x',encoding='utf8') as f:
        json.dump(summary,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(summary,sort_keys=True,allow_nan=False))


if __name__=='__main__':main()
