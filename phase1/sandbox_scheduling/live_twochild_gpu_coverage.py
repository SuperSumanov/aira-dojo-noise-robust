"""Read archived execution-card samples only, never query a live GPU.

Workload coverage diagnosis, not saved-GPU-time or causal bottleneck estimation.
No raw PIDs, code, scores or private content leave the host.
"""
import json
import math
import statistics
from lifecycle_pilot import read, sha, write
from closed_gpu_utilization import weighted
from live_twochild_alignment import ROOT, PLAN, PRIMARY


def summarize(samples, start, end):
    if not samples:raise ValueError('missing telemetry remains unknown')
    for s in samples:
        if not all(type(s[k]) in (int,float) and math.isfinite(s[k]) for k in ('time','utilization','memory_mib')):
            raise ValueError('finite telemetry required')
        if not 0<=s['utilization']<=100 or s['memory_mib']<0 or not isinstance(s['pids'],list):
            raise ValueError('telemetry schema')
    window=[s for s in samples if start<=s['time']<=end]
    if not window:raise ValueError('no samples in execution window')
    return dict(samples=len(window),utilization_median=statistics.median(s['utilization'] for s in window),
        utilization_max=max(s['utilization'] for s in window),nonzero_utilization_samples=sum(s['utilization']>0 for s in window),
        memory_mib_max=max(s['memory_mib'] for s in window),max_resident_clients=max(len(s['pids']) for s in window),
        **weighted(samples,start,end))


def main():
    if sha(ROOT/'plan.json')!=PLAN or sha(ROOT/'readout-v1/summary.json')!=PRIMARY or not (ROOT/'closed.json').exists():
        raise ValueError('exact closed scope')
    plan=read(ROOT/'plan.json');rows=[];pins={}
    for block in range(4):
        directory=ROOT/f'block-{block}'
        execution,service,closed=[read(directory/n) for n in ('execution-native.json','service-native.json','closed.json')]
        if execution['gpu_uuid'] in service['gpu_uuids'] or execution['job']!=service['job'] or str(execution['job'])!='17368':
            raise ValueError('separate assigned execution card required')
        if closed['telemetry_errors'] or closed['gpu_clean'] is not True:
            raise ValueError('incomplete telemetry or cleanup')
        samples=read(directory/'telemetry.json')
        arm=next(r['arm'] for r in plan['schedule'] if r['block']==block)
        rows.append(dict(block=block,arm=arm,start=closed['start'],end=closed['end'],**summarize(samples,closed['start'],closed['end'])))
        for name in ('execution-native.json','service-native.json','closed.json','telemetry.json'):
            pins[str((directory/name).relative_to(ROOT))]=sha(directory/name)
    result=dict(job='17368',plan_sha256=PLAN,primary_sha256=PRIMARY,analysis_sha256=sha(__file__),
        weighted_helper_sha256=sha(__import__('closed_gpu_utilization').__file__),rows=rows,receipt_sha256=pins,
        boundary='Post-hoc sampled whole execution-card coverage, not per-candidate attribution or actual GPU kernel duration. Low samples cannot prove CPU bottleneck or absent brief GPU activity. Execution-block window excludes generator startup/padded pool reservation; do not translate it into saved allocation cost. Original live quality gate is unchanged.')
    dest=ROOT/'execution-gpu-coverage-v1.json';write(dest,result)
    print(json.dumps(dict(written=True,sha256=sha(dest),rows=rows),sort_keys=True))


if __name__=='__main__':main()
