"""Read-only phase evidence for exactly closed 17366; not kernel profiling.

No program, prediction, label, model or private-log content is exported.
All twelve originally assigned executions must be present and verified.
"""
import json
import math
from pathlib import Path

from lifecycle_pilot import read, sha

ROOT = Path('/research/d7/spc/yzyang4/scheduling-neural-extension-20261010-v1')
PLAN = 'bf0e2b24c267880ade8da3457ca5674b1a545c234485b3479ac0df41be2caa85'
PRIMARY = 'cfa91a7a48774fc10315423ab5547c6b3d65e60644fb4940647f387103094907'


def interval(start, end):
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in (start, end)) or end < start:
        raise ValueError('finite ordered interval required')
    return (start, end)


def overlap(left, right):
    a, b = interval(*left), interval(*right)
    return max(0., min(a[1], b[1])-max(a[0], b[0]))


def phase_row(row, start, end, training):
    interval(start, end)
    first, last = interval(training['first_step_start'], training['last_step_end'])
    if not start <= first <= last <= end:
        raise ValueError('host optimizer envelope outside candidate')
    calls = training['host_step_intervals']
    if (training['device'] != 'cuda:0' or training['steps'] != len(calls)
            or len(calls) != (150 if row['program'] == 0 else 588)):
        raise ValueError('fixed training receipt')
    if calls[0]['start'] != first or calls[-1]['end'] != last:
        raise ValueError('envelope versus detailed receipt')
    previous = start
    for call in calls:
        a, b = interval(call['start'], call['end'])
        if a < previous or b > end or call['devices'] != ['cuda:0'] or call['gradient_parameters'] <= 0:
            raise ValueError('ordered CUDA optimizer calls')
        previous = b
    return dict(index=row['index'], program=row['program'], repeat=row['repeat'], arm=row['arm'],
                candidate_start=start, candidate_end=end, first_optimizer_start=first,
                last_optimizer_end=last, before_first_optimizer_seconds=first-start,
                optimizer_envelope_seconds=last-first, after_last_optimizer_seconds=end-last,
                steps=len(calls), timing_is_host_not_kernel=True)


def main():
    if sha(ROOT/'plan.json') != PLAN or sha(ROOT/'readout-v1/summary.json') != PRIMARY:
        raise ValueError('closed exact scope')
    primary = read(ROOT/'readout-v1/summary.json')
    if (str(primary['job']) != '17366' or primary['completed'] != 12
            or read(ROOT/'closed.json')['completed'] != 12):
        raise ValueError('complete original denominator')
    runs = primary['runs']
    if sorted(r['index'] for r in runs) != list(range(12)):
        raise ValueError('unique full twelve')
    rows, pins = [], {}
    for row in runs:
        if row['status'] != 'complete': raise ValueError('original incomplete row')
        ep = ROOT/f'episode-{row["index"]}'
        done, closed = read(ep/'completed.json'), read(ep/'closed.json')
        training = read(ep/'work/gpu_training.json')
        if done['gpu_training'] != training or not done['complete'] or closed['returncode'] != 0:
            raise ValueError('training/completion receipt drift')
        rows.append(phase_row(row, read(ep/'candidate_started.json')['time'],
                              read(ep/'candidate_ended.json')['time'], training))
        for name in ('completed.json', 'closed.json', 'candidate_started.json',
                     'candidate_ended.json', 'work/gpu_training.json'):
            pins[f'episode-{row["index"]}/{name}'] = sha(ep/name)
    blocks = []
    for rep in range(3):
        for arm in ('pipeline', 'share2'):
            own = sorted((r for r in rows if r['repeat'] == rep and r['arm'] == arm),key=lambda r:r['program'])
            if len(own) != 2 or [r['program'] for r in own] != [0, 1]: raise ValueError('fixed program pair')
            cnn, unet = own
            blocks.append(dict(repeat=rep, arm=arm,
                candidate_overlap_seconds=overlap(*[(r['candidate_start'],r['candidate_end']) for r in own]),
                host_optimizer_envelope_overlap_seconds=overlap(*[(r['first_optimizer_start'],r['last_optimizer_end']) for r in own]),
                unet_end_to_cnn_first_optimizer_seconds=cnn['first_optimizer_start']-unet['candidate_end']))
    result = dict(job='17366',plan_sha256=PLAN,primary_sha256=PRIMARY,analysis_sha256=sha(__file__),
        planned=12,completed=12,rows=rows,blocks=blocks,receipt_sha256=pins,
        boundary='Post-hoc host-clock evidence, not GPU kernel timing. First optimizer follows forward/backward and may follow earlier CUDA work; no-envelope-overlap does not prove no GPU overlap. Existing NVML samples are sparse. Neither gaps nor candidate overlap are causally saved GPU seconds; chronological drift and incomplete reverse replication remain unresolved.')
    print(json.dumps(result,sort_keys=True))


if __name__ == '__main__':main()
