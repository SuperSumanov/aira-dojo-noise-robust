"""Independent audit of the closed, fixed R14 neural scheduling experiment.

Reads approved public-derived outputs remotely; exports differences, never values.
Does not rerun candidates, score quality, or amend the frozen primary readout.
"""
from collections import Counter
import itertools
import json
from pathlib import Path
import statistics

from lifecycle_pilot import read, sha, write
from verify_pool_outputs import strict

ROOT = Path('/research/d7/spc/yzyang4/scheduling-neural-20261008-v1')
PLAN_SHA = '8da0e849c3203efc2c47c13f134fe9d841ede0f9c3d667789e41ab2aefb95edc'


def intervals_summary(intervals, start, end):
    if end < start or any(not start <= a <= z <= end for a, z in intervals):
        raise ValueError('interval outside block')
    points = sorted({start, end, *(t for span in intervals for t in span)})
    union = shared = 0.0
    for a, z in zip(points, points[1:]):
        active = sum(left < z and right > a for left, right in intervals)
        union += (z - a) if active else 0
        shared += (z - a) if active > 1 else 0
    return dict(union=union, overlap=shared, outside=end-start-union)


def compare(a, b):
    if a[0] != b[0] or a[1].keys() != b[1].keys():
        raise ValueError('output schema/identity mismatch')
    largest = 0.0
    count = nonzero = 0
    for key, values in a[1].items():
        other = b[1][key]
        if len(values) != len(other):
            raise ValueError('numeric width')
        for x, y in zip(values, other):
            delta = abs(x-y)
            largest = max(largest, delta)
            count += 1
            nonzero += delta != 0
    return dict(max_abs=largest, values=count, different_values=nonzero)


def main():
    if sha(ROOT/'plan.json') != PLAN_SHA:
        raise ValueError('exact plan drift')
    plan = read(ROOT/'plan.json')
    for name, expected in plan['files'].items():
        if sha(ROOT/name) != expected:
            raise ValueError('frozen file drift')
    report = read(ROOT/'readout-v1/summary.json')
    closed = read(ROOT/'closed.json')
    runs = read(ROOT/'runs.json')
    if report['runs'] != runs or report['plan_sha256'] != PLAN_SHA:
        raise ValueError('primary provenance')
    if [r['index'] for r in runs] != list(range(12)):
        raise ValueError('slot denominator')
    if Counter((r['program'], r['arm']) for r in runs) != Counter({(p,a):3 for p in (0,1) for a in ('serial','share2')}):
        raise ValueError('matrix denominator')
    if closed['completed'] != sum(r['status']=='complete' for r in runs):
        raise ValueError('completion denominator')
    outputs = {}
    receipts = []
    for row in runs:
        if row['status'] != 'complete':
            continue
        ep = ROOT/f'episode-{row["index"]}'
        done = read(ep/'completed.json')
        supervisor = read(ep/'closed.json')
        if not done['complete'] or supervisor['returncode'] != 0:
            raise ValueError('completion inconsistency')
        output = ep/'work/submission.csv'
        if sha(output) != row['output_sha256'] or sha(output) != done['output']['sha256']:
            raise ValueError('output drift')
        outputs[row['index']] = strict(output)
        training = read(ep/'work/gpu_training.json')
        if training != done['gpu_training']:
            raise ValueError('training receipt drift')
        steps = training['host_step_intervals']
        start = read(ep/'candidate_started.json')['time']
        end = read(ep/'candidate_ended.json')['time']
        if not steps or training['steps'] != len(steps) or row['gpu_steps'] != len(steps):
            raise ValueError('step count')
        if any(s['devices'] != ['cuda:0'] or s['gradient_parameters'] <= 0 or not start <= s['start'] <= s['end'] <= end for s in steps):
            raise ValueError('device/step interval')
        if any(left['end'] > right['start'] for left, right in zip(steps, steps[1:])):
            raise ValueError('host step ordering')
        receipts.append(dict(index=row['index'], program=row['program'], arm=row['arm'],
                             steps=len(steps), step_span_seconds=steps[-1]['end']-steps[0]['start'],
                             candidate_seconds=end-start, host_calls_not_kernel_time=True))
    numerical = []
    for p in (0,1):
        own = [r for r in runs if r['program']==p and r['index'] in outputs]
        pairs = [dict(indices=[a['index'],b['index']], arms=[a['arm'],b['arm']],
                      **compare(outputs[a['index']], outputs[b['index']]))
                 for a,b in itertools.combinations(own,2)]
        original = report['output_equivalence'][p]
        if pairs != original['pairs']:
            raise ValueError('independent numeric disagreement')
        numerical.append(dict(program=p, outputs=len(own), comparisons=len(pairs),
                              max_difference=max((r['max_abs'] for r in pairs),default=None),
                              primary_numerical_gate=original['numerical_gate'],
                              comparisons_not_independent_observations=True))
    blocks = []
    for b in range(6):
        path = ROOT/f'block-{b}.json'
        if not path.exists():
            continue
        block = read(path)
        own = runs[2*b:2*b+2]
        spans = []
        for r in own:
            ep = ROOT/f'episode-{r["index"]}'
            if (ep/'candidate_started.json').exists() and (ep/'candidate_ended.json').exists():
                spans.append((read(ep/'candidate_started.json')['time'],read(ep/'candidate_ended.json')['time']))
        blocks.append(dict(block=b,arm=block['arm'],repeat=block['repeat'],
                           complete=all(r['status']=='complete' for r in own),
                           seconds=block['end']-block['start'], interval_count=len(spans),
                           **intervals_summary(spans,block['start'],block['end'])))
    ratios = []
    for repeat in range(3):
        own = {b['arm']:b for b in blocks if b['repeat']==repeat}
        if set(own)=={'serial','share2'} and all(b['complete'] for b in own.values()):
            ratios.append(dict(repeat=repeat,ratio=own['serial']['seconds']/own['share2']['seconds']))
    if ratios != report['paired_ratios']:
        raise ValueError('independent makespan disagreement')
    result = dict(job=report['job'],plan_sha256=PLAN_SHA,primary_sha256=sha(ROOT/'readout-v1/summary.json'),
                  full_denominator=12,completed=closed['completed'],frozen_files_match=True,
                  numeric_comparisons=numerical,training_receipts=receipts,blocks=blocks,ratios=ratios,
                  paired_median=statistics.median(r['ratio'] for r in ratios) if ratios else None,
                  no_quality_labels_read=True,no_prediction_values_exported=True,
                  boundary='Independent audit, not additional trials; interval decomposition is not causal attribution.')
    dest = ROOT/'audit-v1'
    dest.mkdir(mode=0o700,exist_ok=False)
    write(dest/'summary.json',result)
    print(json.dumps(dict(job=result['job'],completed=result['completed'],audit_sha256=sha(dest/'summary.json'),
                          paired_median=result['paired_median'],numerical=numerical),sort_keys=True))


if __name__=='__main__':
    main()
