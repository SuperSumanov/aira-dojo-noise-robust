"""Descriptive WHOLE-CARD sampled utilization on closed public-input trials.

No live GPU calls, per-client attribution, kernel-time inference or quality read.
No interpolation before first/after last sample; missing coverage stays missing.
"""
import json
import math
from pathlib import Path
from lifecycle_pilot import read,sha

R=Path('/research/d7/spc/yzyang4/scheduling-homogeneous-20261008-v1')
PIN='1015a7039bdb3436f9d0c0fb2711c045b9c4b48513224bff4c70aa66b381388a'


def weighted(samples,start,end):
    if not math.isfinite(start+end) or end<=start:raise ValueError('invalid window')
    covered=weighted_total=max_gap=0.
    for a,b in zip(samples,samples[1:]):
        if not all(math.isfinite(float(x)) for x in (a['time'],b['time'],a['utilization'])):
            raise ValueError('nonfinite sample')
        if b['time']<=a['time'] or not 0<=a['utilization']<=100:raise ValueError('sample contract')
        overlap=max(0,min(end,b['time'])-max(start,a['time']))
        if overlap:
            covered+=overlap;weighted_total+=overlap*a['utilization']
            max_gap=max(max_gap,b['time']-a['time'])
    return dict(coverage_fraction=covered/(end-start),covered_seconds=covered,
                sampled_whole_card_utilization_percent=weighted_total/covered if covered else None,
                largest_sample_interval_seconds=max_gap if covered else None,
                left_sample_hold_not_actual_kernel_duration=True)


def main():
    if sha(R/'plan.json')!=PIN or not (R/'closed.json').exists():raise ValueError('pinned closed scope')
    report=read(R/'readout-v1/summary.json');rows=[];pins={}
    for b in report['blocks']:
        path=R/f'telemetry-{b["block"]}.json';samples=read(path);pins[path.name]=sha(path)
        record=read(R/f'block-{b["block"]}.json')
        rows.append(dict(block=b['block'],program=b['program'],arm=b['arm'],repeat=b['repeat'],
                         completed=b['completed'],window='whole_block',
                         **weighted(samples,record['start'],record['end'])))
        if b['arm']=='serial':
            for row in report['training_receipts']:
                if row['index']//2!=b['block']:continue
                ep=R/f'episode-{row["index"]}';steps=read(ep/'work/gpu_training.json')['host_step_intervals']
                rows.append(dict(block=b['block'],index=row['index'],program=b['program'],arm='serial',repeat=b['repeat'],
                                 completed=1,window='single_candidate_optimizer_envelope',
                                 **weighted(samples,steps[0]['start'],steps[-1]['end'])))
    print(json.dumps(dict(job='16999',plan_sha256=PIN,planned=24,completed=report['completed'],
                          telemetry_sha256=pins,rows=rows,
                          boundary='Post-hoc mechanism diagnostic, not predictor validation. NVML averages do not measure useful work, GPU kernel concurrency, CPU stalls, or thermal state.'),sort_keys=True))


if __name__=='__main__':main()
