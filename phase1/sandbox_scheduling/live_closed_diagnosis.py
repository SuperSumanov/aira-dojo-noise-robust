"""Metadata-only diagnosis of the closed v4 pilot; never changes its verdict.

No candidate code, model responses, predictions or labels are exported. The
single allowed root is the fresh, non-protected R14 development experiment.
"""
import json
from pathlib import Path
import statistics
from lifecycle_pilot import read, write, sha

ROOT = Path('/research/d7/spc/yzyang4/scheduling-live-search-20261009-v4')


def diagnose():
    closed = read(ROOT/'closed.json')
    plan = read(ROOT/'plan.json')
    assert closed['attempted_blocks'] == [0]
    execution = read(ROOT/'block-0/execution-native.json')
    service = read(ROOT/'block-0/service-native.json')
    rows = []
    for i in range(4):
        ep = ROOT/f'episode-{i}'
        events = [json.loads(v) for v in (ep/'events.jsonl').read_text().splitlines()]
        candidates = []
        for p in sorted(ep.glob('candidate-*.json')):
            if '.private.' in p.name:
                continue
            v = read(p)
            candidates.append({k:v.get(k) for k in
                ('valid','elapsed_seconds','exit_code','timed_out','exec_seconds')})
        native = read(ep/'native.json')
        safe_events = []
        numeric = ('elapsed','operation','call','seconds','wait_seconds','exec_seconds','queue_seconds','exit_code')
        boolean = ('success','timed_out','held','verified')
        kinds = ('operation_ready','kernel_ready','admitted','admission_interrupted','cell_return',
                 'released','cleanup','generation_started','generation_returned','runtime_hooks_installed')
        for e in events:
            if e['event'] not in kinds:
                raise ValueError('unknown event: inspect schema, not values')
            row = {'event':e['event']}
            for key in numeric + boolean:
                if key in e:
                    if not isinstance(e[key], (int,float,bool)) and e[key] is not None:
                        raise ValueError('non-numeric event metadata')
                    row[key] = e[key]
            if 'kind' in e:
                if e['kind'] not in ('preview','candidate'):
                    raise ValueError('unknown operation type')
                row['kind'] = e['kind']
            safe_events.append(row)
        rows.append(dict(index=i,task=plan['schedule'][i]['task'],candidates=candidates,
            events=safe_events,worker_job_matches=native['job']==execution['job']==service['job'],
            worker_execution_step_matches=native['step']==execution['step'],
            service_execution_steps_differ=service['step']!=execution['step'],
            worker_gpu_matches=native['gpu_uuids']==[execution['gpu_uuid']],
            source_event_sha256=sha(ep/'events.jsonl')))
    telemetry = read(ROOT/'block-0/telemetry.json')
    result = dict(plan_sha256=sha(ROOT/'plan.json'),closed_sha256=sha(ROOT/'closed.json'),
        original_readout_sha256=sha(ROOT/'readout-v1/summary.json'),rows=rows,
        execution_affinity_logical_cpus=execution['affinity'],
        service_execution_gpu_disjoint=execution['gpu_uuid'] not in service['gpu_uuids'],
        service_has_two_distinct_gpus=len(set(service['gpu_uuids']))==2,
        telemetry=dict(samples=len(telemetry),utilization_median=statistics.median(v['utilization'] for v in telemetry),
            utilization_max=max(v['utilization'] for v in telemetry),memory_mib_max=max(v['memory_mib'] for v in telemetry)),
        boundary='Post-closure descriptive diagnosis, no replacement of v4 outcome gate. GPU utilization is device telemetry, not attribution to a particular kernel or workload.')
    write(ROOT/'diagnosis-v1.json',result)
    print(json.dumps(result,sort_keys=True))


if __name__ == '__main__':
    diagnose()
