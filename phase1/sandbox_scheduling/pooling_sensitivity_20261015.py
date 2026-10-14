"""Future-blind FIFO placement in fixed-arrival traces; NOT a closed-loop trial.

All 24 task-balanced session pairings are the static sensitivity control.
The best static permutation is a retrospective oracle, not a deployable baseline.
Extra dispatch cost 0/5/15/30s is sensitivity, not a measured migration cost.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import statistics

OVERHEADS=(0,5,15,30)


def replay(jobs, pairing=None, overhead=0):
    assert overhead>=0
    free=[float('-inf')]*4
    output=[]
    # No duration/score/finish is used for request order or lane choice.
    ordered=sorted(enumerate(jobs),key=lambda pair:(pair[1]['arrival'],pair[1]['session'],pair[0]))
    for idx,j in ordered:
        eligible=range(4) if pairing is None else [pairing[j['session']]]
        lane=min(eligible,key=lambda k:(free[k],k))
        begin=max(j['arrival'],free[lane]);end=begin+j['duration']+overhead
        free[lane]=end
        output.append(dict(index=idx,begin=begin,end=end,wait=begin-j['arrival'],
            flow=end-j['arrival'],by_deadline=end<=j['deadline']))
    return output


def summarize(rows):
    vals=[r['flow'] for r in rows]
    return dict(requests=len(rows),total_wait_seconds=sum(r['wait'] for r in rows),
        total_flow_seconds=sum(vals),median_flow_seconds=statistics.median(vals) if vals else None,
        sample_sd_flow_seconds=statistics.stdev(vals) if len(vals)>1 else None,
        released_by_search_deadline=sum(r['by_deadline'] for r in rows))


def balanced_pairs(jobs):
    bytask={k:sorted({j['session'] for j in jobs if j['task']==k}) for k in (0,1)}
    # All eight sessions may have zero completed execution jobs. Task/slot map is
    # frozen by original schedule, independently of which jobs completed.
    expected={0:[0,2,4,6],1:[1,3,5,7]}
    # Alphabetical task ordering must agree with structural slots or reject.
    assert all(set(bytask[k])<=set(expected[k]) for k in (0,1))
    for perm in itertools.permutations(expected[1]):
        yield {s:lane for lane,pair in enumerate(zip(expected[0],perm)) for s in pair}


def main(files,out):
    data=[]
    for file in files:
        raw=Path(file).read_bytes();d=json.loads(raw)
        assert not d['quality_claim'] and d['new_gpu_jobs']==0
        pools=[]
        for p in d['pools']:
            jobs=p['jobs'];pairs=list(balanced_pairs(jobs));assert len(pairs)==24
            static=[summarize(replay(jobs,m)) for m in pairs]
            observed=summarize([dict(flow=j['original_start']+j['duration']-j['arrival'],
                wait=j['original_start']-j['arrival'],by_deadline=j['original_start']+j['duration']<=j['deadline']) for j in jobs])
            assert observed['released_by_search_deadline']==p['original_completed_by_search_deadline']
            original_mapping={j['session']:j['lane'] for j in jobs}
            original_ideal=summarize(replay(jobs,original_mapping))
            alternatives=[]
            for extra in OVERHEADS:
                q=summarize(replay(jobs,overhead=extra))
                q.update(extra_dispatch_seconds=extra,
                    static_pairings_strictly_dominated=sum(q['total_flow_seconds']<s['total_flow_seconds']-1e-6 and q['released_by_search_deadline']>=s['released_by_search_deadline'] for s in static),
                    flow_reduction_vs_observed=1-q['total_flow_seconds']/observed['total_flow_seconds'],
                    flow_reduction_vs_best_static=1-q['total_flow_seconds']/min(s['total_flow_seconds'] for s in static))
                alternatives.append(q)
            pools.append(dict(block=p['block'],arm=p['arm'],known_requests=len(jobs),
                cancelled_unknown_duration=len(p['cancelled']),observed=observed,original_mapping_ideal=original_ideal,
                static_pairings=24,static_flow_min=min(s['total_flow_seconds'] for s in static),
                static_flow_median=statistics.median(s['total_flow_seconds'] for s in static),
                static_flow_max=max(s['total_flow_seconds'] for s in static),
                static_best_ontime=max(s['released_by_search_deadline'] for s in static),
                global_fifo=alternatives,static_details=static))
        data.append(dict(source=Path(file).name,source_sha256=hashlib.sha256(raw).hexdigest(),
                         assigned=d['assigned'],pools=pools))
    result=dict(kind='fixed_arrival_pooling_sensitivity',script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        cases=data,dispatch_cost_seconds=OVERHEADS,quality_claim=False,hardware_speedup_claim=False,new_gpu_jobs=0,
        limits=['All known completed requests retained; cancelled requests remain unknown, not zero cost or claimed completions.',
            'Arrival times and durations are held fixed. Faster feedback can change future prompts, code and arrivals in reality.',
            'Release includes cleanup; this is not valid-feedback arrival or model quality.',
            'Best static pairing is hindsight oracle. Fixed-arrival common CPU/IO/VRAM conditions and unmeasured dispatch overhead limit feasibility claims.',
            'Pools share models/tasks and histories; 24 permutations are sensitivity cases, not independent replications.',
            'Rebinding GPUs across isolated execution steps is not implemented by this simulation.'])
    with Path(out).open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps([dict(source=c['source'],rows=[{k:v for k,v in p.items() if k!='static_details'} for p in c['pools']]) for c in data],allow_nan=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('files',nargs=2);ap.add_argument('out');a=ap.parse_args();main(a.files,a.out)
