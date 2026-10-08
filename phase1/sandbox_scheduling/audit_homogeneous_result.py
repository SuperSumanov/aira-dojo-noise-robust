"""Closed-batch independent audit; no quality scoring or raw prediction export.

Secondary response/slowdown analysis is descriptive, not a new selection gate.
Two replicas share one program and seed; neither is an independent task.
"""
from collections import Counter
import itertools
import json
from pathlib import Path
import statistics

from lifecycle_pilot import read, write, sha
from verify_pool_outputs import strict
from audit_neural_result import compare, intervals_summary

R = Path('/research/d7/spc/yzyang4/scheduling-homogeneous-20261008-v1')
PIN = '1015a7039bdb3436f9d0c0fb2711c045b9c4b48513224bff4c70aa66b381388a'


def validate_matrix(rows):
    if [r['index'] for r in rows] != list(range(24)):
        raise ValueError('full slot denominator')
    expected = Counter((p, a, k, replica) for p in (0, 1)
                       for a in ('serial', 'share2') for k in range(3)
                       for replica in (0, 1))
    if Counter((r['program'], r['arm'], r['repeat'], r['replica'])
               for r in rows) != expected:
        raise ValueError('fixed matrix')
    if any(r['source_seed'] != 42 or r['harness_seed'] != 130701 for r in rows):
        raise ValueError('seed contract')


def descriptive(values):
    return dict(n=len(values), median=statistics.median(values) if values else None,
                sample_std=statistics.stdev(values) if len(values) > 1 else None,
                minimum=min(values) if values else None,
                maximum=max(values) if values else None)


def paired_latencies(serial, shared):
    """One paired block, matching replica positions; not independent samples."""
    if set(serial) != {0, 1} or set(shared) != {0, 1}:
        raise ValueError('two replicas per block')
    answer = []
    for replica in (0, 1):
        a, b = serial[replica], shared[replica]
        if min(a['candidate_seconds'], b['candidate_seconds'],
               a['response_seconds'], b['response_seconds']) <= 0:
            raise ValueError('nonpositive duration')
        answer.append(dict(replica=replica,
                           candidate_slowdown=b['candidate_seconds']/a['candidate_seconds'],
                           response_ratio=b['response_seconds']/a['response_seconds']))
    return answer


def main():
    if sha(R/'plan.json') != PIN:
        raise ValueError('exact plan')
    plan, report, closed = (read(R/name) for name in
                            ('plan.json', 'readout-v1/summary.json', 'closed.json'))
    for name, pin in plan['files'].items():
        if sha(R/name) != pin:
            raise ValueError('frozen file drift')
    for path, pin in plan['input_files'].items():
        if sha(path) != pin:
            raise ValueError('input drift')
    rows = report['runs']
    validate_matrix(rows)
    if report['plan_sha256'] != PIN or report['source_commit'] != plan['source_commit']:
        raise ValueError('readout provenance')
    for actual, scheduled in zip(rows, plan['schedule']):
        if any(actual[k] != v for k, v in scheduled.items()):
            raise ValueError('schedule mismatch')
    if report['completed'] != sum(r['status'] == 'complete' for r in rows):
        raise ValueError('readout denominator')
    if closed['completed'] != report['completed']:
        raise ValueError('controller denominator')
    outputs, times, training, devices, affinities = {}, {}, {}, set(), set()
    for r in rows:
        ep = R/f'episode-{r["index"]}'
        if (ep/'started.json').exists():
            affinities.add(tuple(read(ep/'started.json')['affinity']))
        if (ep/'native.json').exists():
            devices.add(tuple(read(ep/'native.json')['gpu_uuids']))
        if r['status'] != 'complete':
            continue
        done, supervisor = read(ep/'completed.json'), read(ep/'closed.json')
        if not done['complete'] or supervisor['returncode'] != 0:
            raise ValueError('completion mismatch')
        output = ep/'work/submission.csv'
        if sha(output) != done['output']['sha256'] or sha(output) != r['output_sha256']:
            raise ValueError('output drift')
        outputs[r['index']] = strict(output)
        record = read(ep/'work/gpu_training.json')
        steps = record['host_step_intervals']
        a, z = read(ep/'candidate_started.json')['time'], read(ep/'candidate_ended.json')['time']
        if record != done['gpu_training'] or len(steps) != record['steps'] or len(steps) != r['gpu_steps'] or not steps:
            raise ValueError('step receipt')
        if any(s['devices'] != ['cuda:0'] or s['gradient_parameters'] <= 0
               or not a <= s['start'] <= s['end'] <= z for s in steps):
            raise ValueError('GPU step contract')
        if any(left['end'] > right['start'] for left, right in zip(steps, steps[1:])):
            raise ValueError('step ordering')
        if not done['start'] <= a <= z <= done['end'] <= supervisor['end']:
            raise ValueError('execution interval')
        times[r['index']] = dict(candidate_seconds=z-a, candidate_start=a,
                                candidate_end=z, close=supervisor['end'])
        training[r['index']] = len(steps)
    allocation = read(R/'allocation.json')
    if affinities != {tuple(allocation['affinity'])} or devices != {(allocation['gpu_uuid'],)}:
        raise ValueError('CPU/GPU identity')
    blocks, durations, latency = [], {}, {}
    for b in range(12):
        path = R/f'block-{b}.json'
        if not path.exists():
            continue
        block = read(path)
        own = rows[2*b:2*b+2]
        if any((r['program'], r['arm'], r['repeat']) !=
               (block['program'], block['arm'], block['repeat']) for r in own):
            raise ValueError('block membership')
        spans = [(times[r['index']]['candidate_start'], times[r['index']]['candidate_end'])
                 for r in own if r['index'] in times]
        interval = intervals_summary(spans, block['start'], block['end'])
        if block['arm'] == 'serial' and interval['overlap'] != 0:
            raise ValueError('serial overlap')
        complete = all(r['index'] in times for r in own)
        key = block['program'], block['repeat'], block['arm']
        if complete:
            durations[key] = block['end']-block['start']
            latency[key] = {r['replica']:dict(times[r['index']],
                               response_seconds=times[r['index']]['close']-block['start']) for r in own}
        blocks.append(dict(block=b, program=block['program'], repeat=block['repeat'],
                           arm=block['arm'], complete=complete, seconds=block['end']-block['start'], **interval))
    per_task = []
    for p in (0, 1):
        own = [r for r in rows if r['program'] == p and r['index'] in outputs]
        pairs = [dict(indices=[a['index'], b['index']], arms=[a['arm'], b['arm']],
                      **compare(outputs[a['index']], outputs[b['index']]))
                 for a, b in itertools.combinations(own, 2)]
        primary = next(t for t in report['per_task'] if t['program'] == p)
        for independently, recorded in zip(pairs, primary['pairs']):
            if any(independently[k] != recorded[k] for k in ('indices', 'arms', 'max_abs')):
                raise ValueError('numeric disagreement')
        if len(pairs) != len(primary['pairs']):
            raise ValueError('numeric pair denominator')
        ratios, secondary = [], []
        for repeat in range(3):
            a, b = (p, repeat, 'serial'), (p, repeat, 'share2')
            if a in durations and b in durations:
                ratios.append(dict(repeat=repeat, ratio=durations[a]/durations[b]))
                secondary.append(dict(repeat=repeat,
                                      replicas=paired_latencies(latency[a], latency[b])))
        if ratios != primary['paired_ratios']:
            raise ValueError('makespan disagreement')
        per_task.append(dict(program=p, task=primary['task'], completed=len(own),
                             numeric_comparisons=len(pairs), max_abs_difference=max((x['max_abs'] for x in pairs), default=None),
                             step_counts=sorted({training[r['index']] for r in own}),
                             ratios=ratios, speedup=descriptive([x['ratio'] for x in ratios]),
                             secondary_latency=secondary, primary_gate=primary['exploratory_gate']))
    result = dict(job=report['job'], plan_sha256=PIN, source_commit=plan['source_commit'],
                  primary_sha256=sha(R/'readout-v1/summary.json'), denominator=24,
                  attempted=report['attempted'], completed=report['completed'],
                  allocation_seconds=report['allocation_seconds'],
                  same_CPU_affinity_and_GPU=True, frozen_source_and_input_hashes_match=True,
                  per_task=per_task, blocks=blocks, no_quality_labels_read=True,
                  no_raw_prediction_export=True,
                  boundary='Independent audit, not additional experiments. Per-task paired blocks; secondary latency is descriptive. Replicas/restarts are not independent tasks/seeds. No pooled effect or kernel-time interpretation.')
    dest = R/'audit-v1'
    dest.mkdir(mode=0o700, exist_ok=False)
    write(dest/'summary.json', result)
    print(json.dumps(dict(job=result['job'], completed=result['completed'],
                          audit_sha256=sha(dest/'summary.json'), per_task=per_task), sort_keys=True))


if __name__ == '__main__':
    main()
