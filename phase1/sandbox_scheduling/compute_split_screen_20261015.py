"""Closed-only structural screen for generation/execution GPU repartitioning.

No program, prediction, label, outcome or model response is read. Structural
replay fixes observed arrivals/durations: it is NOT a new closed-loop rollout,
GPU kernel profiler, throughput forecast, or evidence of quality improvement.
"""
import argparse
from collections import Counter
import hashlib
import heapq
import json
import math
from pathlib import Path
import re
import statistics

from effort_pressure_diagnostic_20261012 import structural_events, state_changes, integrate

PINNED = {
    'scheduling-metric-deployment-20261015-v2': ('e3baf5d2fa704cdd0c3fc458549aa21449fdbf3209bac87337b370e2a416e154', 48, 6),
    'scheduling-weight-confirmation-20261014-v1': ('316381bce41c9ceb9c34fb165e94996eeeb8c9968eff3cb4e63642fbfa549626', 32, 4),
}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def telemetry(samples, start, end):
    """Left-held GPU samples, without extrapolating beyond final observation."""
    if len(samples) < 2:
        raise ValueError('insufficient GPU telemetry')
    span = area = nonzero = 0.0
    gaps = []
    for a, b in zip(samples, samples[1:]):
        if b['time'] <= a['time']:
            raise ValueError('nonmonotonic telemetry')
        if not (0 <= a['utilization'] <= 100):
            raise ValueError('invalid utilization')
        dt = max(0.0, min(end, b['time']) - max(start, a['time']))
        span += dt
        area += dt*a['utilization']
        nonzero += dt*(a['utilization'] > 0)
        if dt:
            gaps.append(b['time']-a['time'])
    return dict(covered_seconds=span, window_coverage=span/(end-start),
                utilization_time_weighted_pct=area/span if span else None,
                nonzero_sample_time_fraction=nonzero/span if span else None,
                longest_sample_gap=max(gaps) if gaps else None,
                samples=len(samples), peak_memory_mib=max(x['memory_mib'] for x in samples))

def jobs(events):
    arrivals, starts, out = {}, {}, []
    for e in events:
        t, k, kind = e['time'], e['key'], e['kind']
        if kind == 'queued':
            arrivals[k] = t
        elif kind == 'admitted':
            starts[k] = t
        elif kind == 'released':
            out.append(dict(arrival=arrivals.pop(k), original_start=starts[k],
                            duration=t-starts.pop(k)))
        elif kind == 'cancelled':
            arrivals.pop(k)
    if arrivals or starts:
        raise ValueError('unclosed execution queue')
    return out

def replay_fixed_arrivals(work, capacity, end):
    if capacity < 1:
        raise ValueError('capacity')
    free = [-math.inf]*capacity
    waits, finishes = [], []
    for j in sorted(work, key=lambda x: (x['arrival'], x['original_start'])):
        if j['duration'] < 0:
            raise ValueError('negative duration')
        start = max(j['arrival'], heapq.heappop(free))
        finish = start+j['duration']
        heapq.heappush(free, finish)
        waits.append(start-j['arrival']); finishes.append(finish)
    return dict(jobs=len(work), capacity=capacity, total_wait_seconds=sum(waits),
                wait_median=statistics.median(waits) if waits else None,
                finishes_by_pool_end=sum(t <= end for t in finishes),
                last_finish_past_end=max(0, max(finishes, default=end)-end))

def simultaneous(streams, start, end):
    points = [(t, i, q, a) for i, stream in enumerate(streams) for t,q,a in stream]
    points.sort(key=lambda p: (p[0], p[1]))
    states = [(0,0)]*len(streams); prev=start; area=Counter()
    def add(dt):
        gq, ga = states[0]; eq=sum(x[0] for x in states[1:]); ea=sum(x[1] for x in states[1:])
        area['gen_wait_with_at_most_two_exec_seconds'] += dt*(gq > 0 and ea <= 2)
        area['gen_wait_with_zero_exec_seconds'] += dt*(gq > 0 and ea == 0)
        area['exec_more_than_two_seconds'] += dt*(ea > 2)
        area['gen_wait_seconds'] += dt*(gq > 0)
        area['exec_wait_seconds'] += dt*(eq > 0)
    for t,i,q,a in points:
        if t < start-0.01 or t > end+0.01:
            raise ValueError('event outside pool')
        t=max(start,min(end,t)); add(t-prev); states[i]=(q,a); prev=t
    add(end-prev)
    return dict(area)

def service_counts(path):
    # Read raw service log on the remote host ONLY, never export raw text.
    # Numeric allowlist; even a credential-shaped line never leaves the process.
    pattern = re.compile(r'Avg generation throughput: ([0-9.]+) tokens/s.*?Running: (\d+) reqs.*?Waiting: (\d+) reqs')
    rows=[]
    with path.open(errors='replace') as handle:
        for line in handle:
            match=pattern.search(line)
            if match:
                rows.append(tuple(float(x) for x in match.groups()))
    return dict(parsed_samples=len(rows),
                throughput_nonzero_median=statistics.median([r[0] for r in rows if r[0]>0]) if any(r[0]>0 for r in rows) else None,
                max_running=max((r[1] for r in rows),default=None),
                max_waiting=max((r[2] for r in rows),default=None),
                caveat='Whole allocation log, not a per-arm estimate or a hardware-utilization measurement.')

def main(root, out):
    root=Path(root); pin,n,blocks=PINNED[root.name]
    assert sha(root/'plan.json') == pin
    p,c=read(root/'plan.json'),read(root/'closed.json')
    assert p['planned']==n and c['complete']==n and c['error'] is None
    results=[]; sources={}; safe_streams=[]
    for b in range(blocks):
        bd=root/f'block-{b}'; budget=bd/'budget-slot.json'; w=read(budget)
        start,end=w['start'],w['start']+w['actual_seconds']
        streams=[]; audits=[]; work=[]; samples=[]
        for i,(file,generation,cap) in enumerate([(root/f'generation-{b}/events.jsonl',True,4)]+[(root/f'queue-{b}-{k}/events.jsonl',False,1) for k in range(4)]):
            sources[str(file.relative_to(root))]=sha(file)
            events=structural_events(file,generation)
            changes,audit=state_changes(events,cap)
            streams.append(changes);audits.append(audit)
            if not generation:
                work.extend(jobs(events))
        areas=integrate(streams,start,end)
        for prefix,selection in [('generation',audits[:1]),('execution',audits[1:])]:
            for name,target in [('waiting','queued'),('holding','held')]:
                assert abs(sum(a[name+'_seconds'] for a in selection)-areas[prefix+'_'+target+'_seconds']) < 1e-4
        for lane in range(4):
            file=bd/f'lane-{lane}-telemetry.json'; sources[str(file.relative_to(root))]=sha(file)
            assert read(bd/f'lane-{lane}-closed.json')['telemetry_errors']==[]
            raw=read(file)
            samples.append(telemetry(raw,start,end))
        safe_streams.append(dict(block=b,start=start,end=end,streams=streams,
                                 execution_jobs=work))
        results.append(dict(block=b,arm=next(r['arm'] for r in p['schedule'] if r['block']==b),
            duration_seconds=end-start,host_areas=areas,simultaneous=simultaneous(streams,start,end),
            exec_held_fraction=areas['execution_held_seconds']/(4*(end-start)),
            generation_full_fraction=areas['generation_full_seconds']/(end-start),
            lane_telemetry=samples,
            pooled_gpu_sample_utilization_pct=sum(s['utilization_time_weighted_pct']*s['covered_seconds'] for s in samples)/sum(s['covered_seconds'] for s in samples),
            fixed_arrival_replay=[replay_fixed_arrivals(work,k,end) for k in (2,4)]))
    result=dict(kind='posthoc_structural_compute_split_screen',plan_sha256=pin,assigned=n,
        script_sha256=sha(__file__),source_commit=p['source_commit'],pools=results,
        service_numeric_log=service_counts(root/'block-0/service.private.log'),source_hashes=sources,
        safe_structural_streams=safe_streams,quality_claim=False,new_gpu_jobs=0,paid_api_calls=0,
        limitations=['Generation permits are not hardware saturation; Analyze can bypass the code permit.',
                     'GPU utilization is sampled, not kernel tracing; gaps/coverage reported, no zero fill.',
                     'Fixed observed arrivals and durations omit changed service/CPU contention and feedback dependencies. Replay is feasibility screening, NOT a new search trajectory or predicted speedup.',
                     'All assigned closed pools included; post-hoc repeated development data, not confirmation.',
                     'No method novelty follows from imbalance alone; compare Scepsy/MARS and best static allocation.'])
    with Path(out).open('x') as handle:
        json.dump(result,handle,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in result.items() if k not in ('source_hashes','safe_structural_streams')},allow_nan=False))

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('root'); ap.add_argument('out'); a=ap.parse_args()
    main(a.root,a.out)
