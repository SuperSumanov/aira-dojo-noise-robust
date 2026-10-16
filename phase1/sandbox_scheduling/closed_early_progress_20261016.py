"""18819 post-hoc observability, NOT a SchedMate reproduction or online replay.

First32/128 host optimizer-call envelopes are fixed descriptive windows here.
They require a separate solo reference, whose profile cost is not amortized.
No new candidate execution, no rescoring, no admission/policy benefit estimate.
"""
import hashlib
import json
from pathlib import Path

ROOT=Path('/research/d7/spc/yzyang4/clock-rank-20261016-v1')
PIN='4c22748699952da0b79bf862e1db5e785b7d2a9fb951bb26ee9c21be47ca3306'
WINDOWS=(32,128)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rate(steps,n):
    assert n>1 and len(steps)>=n
    a=steps[:n]
    assert all(x['end']>=x['start'] for x in a)
    assert all(y['start']>=x['end'] for x,y in zip(a,a[1:]))
    span=a[-1]['end']-a[0]['start'];assert span>0
    return n/span
def main():
    assert sha(ROOT/'plan.json')==PIN and (ROOT/'closed.json').exists()
    assert read(ROOT/'readout-20261016-v1/summary.json')['complete']==16
    rows=[]
    for s in read(ROOT/'plan.json')['schedule']:
        if s['program'] not in (2,3):continue
        p=ROOT/f"episode-{s['index']}/gpu-training.json";t=read(p)
        assert t['steps']==t['cuda_gradient_steps']
        for n in WINDOWS:
            rows.append(dict(index=s['index'],program=s['program'],mode=s['mode'],block=s['block'],
                window=n,host_calls_per_second=rate(t['host_step_intervals'],n),trace_sha256=sha(p)))
    ranges=[]
    for program in (2,3):
        for n in WINDOWS:
            a=[r['host_calls_per_second'] for r in rows if r['program']==program and r['window']==n and r['mode']=='solo']
            b=[r['host_calls_per_second'] for r in rows if r['program']==program and r['window']==n and r['mode']=='colocated']
            ratios=[co/solo for solo in a for co in b]
            ranges.append(dict(program=program,window=n,solo_rates=a,colocated_rates=b,
                all_cross_restart_co_to_solo_ratio_range=[min(ratios),max(ratios)],
                all_cross_restart_host_rate_drop_exceeds_35_percent=max(ratios)<.65))
    out=dict(posthoc=True,plan_sha256=PIN,analysis_sha256=sha(Path(__file__)),rows=rows,ranges=ranges,
        boundary='First-N host-call envelopes are not CUDA kernel throughput, SchedMate runtime progress extraction, its before/after-packing profile, or eviction replay. Separate solo profiles cost extra. Threshold comparison is descriptive only; no proof of baseline success/failure or E2E benefit.')
    with (ROOT/'early-progress-20261016.safe.json').open('x') as f:json.dump(out,f,indent=2,allow_nan=False)
    print(json.dumps(out))
if __name__=='__main__':main()
