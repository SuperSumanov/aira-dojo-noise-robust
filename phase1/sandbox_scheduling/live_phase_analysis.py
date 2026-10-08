"""Descriptive live-loop phase accounting; never changes eligibility/readout.

Execution lease time includes execution, result retrieval, dev scoring and
cleanup. It is not GPU kernel time. Each run is clipped to its own wall budget;
summing runs gives task-slot seconds, NOT reserved GPU seconds or savings.
"""
import argparse
import json
import math
from pathlib import Path
from lifecycle_pilot import read, write, sha


def interval(a, b, horizon):
    if not all(math.isfinite(v) for v in (a, b, horizon)) or b < a or horizon <= 0:
        raise ValueError('invalid phase interval')
    return max(0., a), min(horizon, b)


def length_union(spans, horizon):
    normalized = sorted(interval(a, b, horizon) for a, b in spans)
    total = 0.; right = 0.
    for a, b in normalized:
        if b <= a:
            continue
        total += max(0., b - max(a, right))
        right = max(right, b)
    return total


def phases(events, horizon=600.):
    spans = {k: [] for k in ('generation', 'kernel_readiness', 'queue', 'lease')}
    calls = {}; leases = {}; unfinished = {}; last = -math.inf
    for e in events:
        t = e['elapsed']
        if not math.isfinite(t) or t < last:
            raise ValueError('run monotonic clock moved backwards')
        last = t
        kind = e['event']
        if kind == 'generation_started':
            key = e['call']
            if key in calls:
                raise ValueError('duplicate generation start')
            calls[key] = t
        elif kind == 'generation_returned':
            key = e['call']
            if key not in calls:
                raise ValueError('generation end without start')
            start = calls.pop(key)
            if abs((t-start)-e['seconds']) > .5:
                raise ValueError('generation duration disagreement')
            spans['generation'].append((start, t))
        elif kind == 'kernel_ready':
            spans['kernel_readiness'].append((t-e['seconds'], t))
        elif kind in ('admitted', 'admission_interrupted'):
            spans['queue'].append((t-e['wait_seconds'], t))
            if kind == 'admitted' or e.get('held'):
                key = e['operation']
                if key in leases:
                    raise ValueError('duplicate live lease')
                leases[key] = t
        elif kind == 'released':
            key = e['operation']
            if key not in leases:
                raise ValueError('lease end without start')
            spans['lease'].append((leases.pop(key), t))
    # A killed process can leave a start with no end. Never pretend its span
    # lasted to the deadline; mark phase accounting incomplete instead.
    for label, remaining in (('generation', calls), ('lease', leases)):
        if remaining:
            unfinished[label] = len(remaining)
    totals = {k: length_union(v, horizon) for k, v in spans.items()}
    covered = length_union([s for v in spans.values() for s in v], horizon)
    overlap = sum(totals.values())-covered
    observed_through = min(horizon, max(0., last)) if events else 0.
    return dict(seconds=totals, observed_phase_union_seconds=covered,
        observed_through_seconds=observed_through,
        unclassified_within_observation_seconds=observed_through-covered,
        budget_after_last_event_seconds=horizon-observed_through,
        cross_phase_overlap_seconds=overlap,
        unfinished=unfinished, complete=not unfinished,
        boundary='Per-run task-slot seconds. The budget after the last event is unobserved, not measured idle time. Lease includes scoring/cleanup; neither GPU kernel time nor measured savings.')


def main(root, output):
    root = Path(root); output = Path(output)
    if not (root/'closed.json').exists():
        raise ValueError('batch must be closed before descriptive analysis')
    plan = read(root/'plan.json')
    rows = []
    for s in plan['schedule']:
        path = root/f'episode-{s["index"]}/events.jsonl'
        if not path.exists():
            rows.append(dict(**s, observed=False, phase_accounting=None))
            continue
        events = [json.loads(v) for v in path.read_text().splitlines()]
        rows.append(dict(**s, observed=True, phase_accounting=phases(events, plan['run_seconds']),
                         events_sha256=sha(path)))
    write(output, dict(plan_sha256=sha(root/'plan.json'), analysis_source_sha256=sha(__file__),
                       assigned=len(plan['schedule']), rows=rows,
                       purpose='Descriptive bottleneck localization only; no replacement of frozen outcome/advance criteria.'))
    print(json.dumps(dict(written=True, observed=sum(r['observed'] for r in rows), assigned=len(rows))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('root'); p.add_argument('output')
    a = p.parse_args(); main(a.root, a.output)
