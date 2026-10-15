"""Independent Python union-of-intervals verification of the JS sensitivity."""
import hashlib
import json
from pathlib import Path
import sys

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def waiting(intervals,at):
    # Integrate Boolean occupancy across distinct breakpoints, not JS's sum.
    bounds=sorted({0.,at}|{max(0.,min(at,v)) for pair in intervals for v in pair})
    return sum(b-a for a,b in zip(bounds,bounds[1:]) if any(x<=(a+b)/2<y for x,y in intervals))

def main(gain_file,result_file,out):
    g,r=read(gain_file),read(result_file);assert sha(gain_file)==r['gain_source_sha256']
    assert r['tested_threshold_seconds']==1020 and not r['quality_claim']
    count=0
    for s in g['sources']:
        timing_path=Path(__file__).parent/'compute_split_20261015_cpu'/f"{s['name']}-pooling-input.json"
        timing=read(timing_path)
        ref=next(v for v in r['sources'] if v['name']==s['name'])
        assert sha(timing_path)==ref['timing_sha256'] and s['plan_sha256']==timing['plan_sha256']
        for p in s['pools']:
            old=[p['initial']];new=[p['initial']];events=[];known=0
            pool=next(x for x in timing['pools'] if x['block']==p['block'])
            for row in s['rows']:
                if (row['block'],row['task'])!=(p['block'],p['task']):continue
                sid=row['index']%8
                intervals=[(j['arrival'],j['original_start']) for j in pool['jobs'] if j['session']==sid]
                intervals.extend((j['arrival'],j['cancelled_at']) for j in pool['cancelled'] if j['session']==sid)
                for e in row['valid_events']:
                    saved=waiting(intervals,e['elapsed']+row['offset']);t=e['elapsed']-saved
                    events.append((row['index'],e['score'],e['elapsed'],t,saved))
                    if e['elapsed']<=1020:old.append(e['score'])
                    if t<=1020:new.append(e['score'])
                    known+=e['elapsed']>1020 and t<=1020
            rr=next(x for x in r['rows'] if (x['source'],x['block'],x['task'])==(s['name'],p['block'],p['task']))
            key=lambda x:p['sign']*x
            assert abs(max(old,key=key)-rr['observed_at_1020'])<1e-12
            assert abs(max(new,key=key)-rr['fixed_history_without_exec_wait_at_1020'])<1e-12
            assert known==rr['newly_on_time_known_valid']
            assert len(events)==len(rr['shifted_known_events'])
            for a,b in zip(events,rr['shifted_known_events']):
                assert a[0]==b['index'] and a[1]==b['score'] and a[2]==b['observed']
                assert abs(a[3]-b['no_exec_wait'])<1e-7 and abs(a[4]-b['removed_wait'])<1e-7
            count+=1
    assert count==20
    result=dict(passed=True,task_pool_cells=count,input_sha256=sha(result_file),new_gpu_jobs=0,
        independent_algorithm='Boolean interval occupancy integration; reproduce every shifted known event and endpoint',
        boundary='Conditional historical sensitivity only; no assertion about unobserved future quality or actual FIFO gains.')
    with Path(out).open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))

if __name__=='__main__':main(*sys.argv[1:])
