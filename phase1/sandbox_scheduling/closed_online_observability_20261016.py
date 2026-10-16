"""Closed18807: availability of before/after host progress at real admissions.

Descriptive, post-hoc and outcome-free. Not a SchedMate reproduction, eviction
replay or estimate of alternative-policy quality. Traces were saved only at
successful program return: missing trace != absent GPU work. No raw content,
metrics, model input or predictions are read/exported by this analysis.
"""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path('/research/d7/spc/yzyang4/scheduling-colocation-20261016-v1')
PIN = '36ce5852b26de2299755c19a8b9711a1f4161d68abd25a3de6cc7687cdde8560'
WINDOWS = (32, 128)
NEWCOMER_WARMUP = 32


def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def intervals(events):
    active, leases, admissions = {}, {}, []
    last = float('-inf')
    for e in events:
        k, t = e['key'], e['time']
        assert t >= last
        last = t
        if e['event'] == 'admitted':
            assert k not in leases
            peers = [a for a in active if leases[a]['device'] == e['device']]
            assert len(peers) <= 1
            if peers:
                a = peers[0]
                admissions.append(dict(newcomer=k, incumbent=a, admitted_at=t,
                                       preceding_solo_start=active[a]))
                active[a] = None
            leases[k] = dict(start=t, device=e['device'])
            active[k] = None if peers else t
        elif e['event'] == 'released':
            assert k in active
            del active[k]
            leases[k]['end'] = t
            peers = [a for a in active if leases[a]['device'] == e['device']]
            for a in peers: active[a] = t
    assert not active and all('end' in v for v in leases.values())
    return leases, admissions


def observation(a, b, admission, until, n):
    solo = admission['preceding_solo_start']
    assert solo is not None
    pre = [s for s in a if s['start'] >= solo and s['end'] <= admission['admitted_at']]
    warmup_at = b[NEWCOMER_WARMUP-1]['end'] if len(b) >= NEWCOMER_WARMUP else None
    post = [] if warmup_at is None else [s for s in a if s['start'] >= warmup_at and s['end'] <= until]
    result = dict(window=n, incumbent_pre_steps_available=len(pre),
                  incumbent_post_steps_available=len(post), newcomer_warmup_steps=NEWCOMER_WARMUP,
                  sufficient=len(pre) >= n and len(post) >= n)
    if result['sufficient']:
        pre, post = pre[-n:], post[:n]
        spans = [x[-1]['end']-x[0]['start'] for x in (pre, post)]
        assert min(spans) > 0
        ratio = spans[0]/spans[1]
        result.update(host_call_rate_ratio=ratio, host_rate_drop_over_35_percent=ratio < .65,
                      first_available_seconds_after_admission=post[-1]['end']-admission['admitted_at'])
    return result


def main():
    assert sha(ROOT/'plan.json') == PIN and (ROOT/'closed.json').exists()
    plan = read(ROOT/'plan.json')
    output, trace_counts = [], []
    for block in (1, 2):
        event_file = ROOT/f'pool-{block}/events.jsonl'
        leases, admissions = intervals([json.loads(l) for l in event_file.read_text().splitlines()])
        trace_by_lease, trace_files, zero = {}, 0, 0
        for s in plan['schedule']:
            if s['block'] != block: continue
            ep = ROOT/f"episode-{s['index']}"
            for p in ep.glob('gpu-training-*.json'):
                if not re.fullmatch(r'gpu-training-\d+\.json', p.name): continue
                trace_files += 1
                raw = read(p)
                steps = [v for v in raw['host_step_intervals']
                         if any(d.startswith('cuda:') for d in v['devices']) and v['gradient_parameters'] > 0]
                assert len(steps) == raw['cuda_gradient_steps']
                if not steps:
                    zero += 1
                    continue
                assert all(a['end'] <= b['start'] for a, b in zip(steps, steps[1:]))
                possible = [k for k, v in leases.items() if int(k.split(':')[0]) == s['index']
                            and v['start'] <= steps[0]['start'] and steps[-1]['end'] <= v['end']]
                assert len(possible) == 1, 'trace/lease match is ambiguous'
                k = possible[0]
                assert k not in trace_by_lease, 'duplicate trace for one lease'
                trace_by_lease[k] = (steps, sha(p))
        trace_counts.append(dict(block=block, leases=len(leases), colocation_admissions=len(admissions),
                                 saved_trace_files=trace_files, saved_traces_with_zero_cuda_steps=zero,
                                 nonempty_cuda_traces=len(trace_by_lease), event_sha256=sha(event_file)))
        for order, e in enumerate(admissions):
            a, b = trace_by_lease.get(e['incumbent']), trace_by_lease.get(e['newcomer'])
            row = dict(block=block, admission_ordinal=order,
                       incumbent_cuda_trace_available=a is not None,
                       newcomer_cuda_trace_available=b is not None, windows=[])
            if a and b:
                until = min(leases[e[k]]['end'] for k in ('incumbent', 'newcomer'))
                row.update(incumbent_trace_sha256=a[1], newcomer_trace_sha256=b[1])
                row['windows'] = [observation(a[0], b[0], e, until, n) for n in WINDOWS]
            output.append(row)
    result = dict(posthoc=True, analysis_sha256=sha(Path(__file__)), plan_sha256=PIN,
                  counts=trace_counts, admissions=output,
                  scope='All20actual co-admissions in the two closed treatment pools, never selected by scores.',
                  boundary='Completed-return traces are survivor-conditioned, not an online exported API. Before/after host optimizer-call envelopes may span changing program phases; they are not kernel throughput. Fixed32newcomer warmup and32/128incumbent windows are descriptive, not an exact SchedMate implementation. No eviction occurs; detecting a signal does not establish decision correctness, final quality or equal-cost benefit. Missing traces do not prove no GPU computation.')
    assert len(output) == 20
    dest = ROOT/'online-observability-20261016.safe.json'
    with dest.open('x') as f: json.dump(result, f, indent=2, allow_nan=False)
    print(json.dumps(result))


if __name__ == '__main__': main()
