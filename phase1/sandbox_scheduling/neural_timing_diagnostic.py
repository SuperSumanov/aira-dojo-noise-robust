"""Read-only descriptive host timing, not GPU profiling or causal attribution.

Only the already closed homogeneous public-input trial is permitted. No raw
prediction/quality values, model weights, candidate text or private logs exported.
"""
import ast
import json
from pathlib import Path
import statistics

from lifecycle_pilot import read, sha

R = Path('/research/d7/spc/yzyang4/scheduling-homogeneous-20261008-v1')
PIN = '1015a7039bdb3436f9d0c0fb2711c045b9c4b48513224bff4c70aa66b381388a'


def describe(values):
    return dict(n=len(values), total=sum(values), median=statistics.median(values)
                if values else None, maximum=max(values) if values else None)


def host_gaps(steps):
    if not steps or any(x['end'] < x['start'] for x in steps):
        raise ValueError('invalid host calls')
    gaps = [b['start']-a['end'] for a, b in zip(steps, steps[1:])]
    if any(x < 0 for x in gaps):
        raise ValueError('host call order')
    calls = [x['end']-x['start'] for x in steps]
    span = steps[-1]['end']-steps[0]['start']
    if abs(sum(calls)+sum(gaps)-span) > 1e-5:
        raise ValueError('interval decomposition')
    return dict(host_calls=describe(calls), between_host_calls=describe(gaps),
                optimizer_envelope_seconds=span,
                gaps_over_one_second=sum(g > 1 for g in gaps),
                not_GPU_kernel_or_CPU_stall_measurement=True)


def source_hints(text):
    """Only resource knob expressions, not code content or runtime assertions."""
    import census
    tree = ast.parse(text)
    hints = list(census.resource_settings(tree))
    allowed = {'torch.set_num_threads', 'torch.set_num_interop_threads',
               'torch.manual_seed', 'torch.cuda.manual_seed_all'}
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and census.dotted(node.func) in allowed:
            calls.append(dict(name=census.dotted(node.func),
                              args=[census.literal(a) for a in node.args]))
    return dict(literal_resource_hints=hints, calls=calls,
                static_hints_not_executed_configuration=True)


def main():
    if sha(R/'plan.json') != PIN or not (R/'closed.json').exists():
        raise ValueError('closed pinned scope')
    plan = read(R/'plan.json')
    rows = read(R/'readout-v1/summary.json')['runs']
    evidence, hints = [], []
    for p in (0, 1):
        source = R/f'programs/{p}.py'
        if sha(source) != plan['programs'][p]['source_sha256']:
            raise ValueError('source drift')
        hints.append(dict(program=p, **source_hints(source.read_text())))
    for row in rows:
        if row['status'] != 'complete':
            continue
        record = read(R/f'episode-{row["index"]}/work/gpu_training.json')
        if record != read(R/f'episode-{row["index"]}/completed.json')['gpu_training']:
            raise ValueError('receipt drift')
        evidence.append(dict(index=row['index'], program=row['program'],
                             arm=row['arm'], repeat=row['repeat'], replica=row['replica'],
                             **host_gaps(record['host_step_intervals'])))
    print(json.dumps(dict(job='16999', plan_sha256=PIN, planned=24,
                          completed=len(evidence), rows=evidence, source_hints=hints,
                          boundary='Post-hoc descriptive decomposition only. CUDA is asynchronous; gaps include data loading, forward/backward, validation and synchronization. Cannot attribute variation to cache, CPU contention or GPU kernels.'), sort_keys=True))


if __name__ == '__main__':
    main()
