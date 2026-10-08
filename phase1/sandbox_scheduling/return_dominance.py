"""Post-hoc timing dominance for the CLOSED 17128 batch; no new trials.

Count dominance is evaluated for every deadline, not a chosen favorable one.
Program-specific delay is retained even when total returns dominate. This is
not search quality, a live-loop replay, or proof of interference causation.
"""
import json
import math
from pathlib import Path
import statistics
from lifecycle_pilot import read, sha, write

ROOT=Path('/research/d7/spc/yzyang4/scheduling-neural-qualified-overlap-20261008-evening-v1')
PLAN='c73cb9ce97ae092ee3bb4ea761201da22dc08d35dfa3f5ecf3aa34bdd8415abc'
PRIMARY='c763de7c8ee00db5d4ba4219d49c4d864e573061368be9566f7d48d4cc0bc258'

def compare(reference, shared):
    if set(reference)!=set(shared) or not reference:
        raise ValueError('same complete program set required')
    if not all(math.isfinite(v) and v>=0 for v in list(reference.values())+list(shared.values())):
        raise ValueError('invalid elapsed times')
    a,b=sorted(reference.values()),sorted(shared.values())
    # For CDFs with equal total mass, all order statistics no later is necessary
    # and sufficient for cumulative-return dominance at every wall deadline.
    delta={str(k):shared[k]-reference[k] for k in sorted(reference)}
    return dict(count_dominates_all_deadlines=all(y<=x for x,y in zip(a,b)),
                every_program_no_later=all(v<=0 for v in delta.values()),
                program_delay_seconds=delta,
                ordered_return_times=dict(reference=a,shared=b))

def analyze():
    if sha(ROOT/'plan.json')!=PLAN or sha(ROOT/'readout-v1/summary.json')!=PRIMARY:
        raise ValueError('closed evidence changed')
    summary=read(ROOT/'readout-v1/summary.json')
    if summary['job']!='17128' or summary['planned']!=12 or summary['completed']!=12:
        raise ValueError('unexpected batch or missing assignments')
    if summary['reference_arm']!='pipeline':raise ValueError('not strong baseline')
    hashes={};rows=[]
    for b in summary['blocks']:
        bp=ROOT/f'block-{b["block"]}.json';block=read(bp);hashes[str(bp.relative_to(ROOT))]=sha(bp)
        if abs(block['end']-block['start']-b['makespan'])>1e-6:raise ValueError('block clock mismatch')
        selected=[r for r in summary['runs'] if r['repeat']==b['repeat'] and r['arm']==b['arm']]
        if len(selected)!=2:raise ValueError('matrix mismatch')
        for r in selected:
            cp=ROOT/f'episode-{r["index"]}/closed.json';closed=read(cp);hashes[str(cp.relative_to(ROOT))]=sha(cp)
            if r['status']!='complete' or closed['returncode']!=0:raise ValueError('incomplete run')
            if not block['start']<=r['end']<=closed['end']<=block['end']:raise ValueError('closure clock mismatch')
            rows.append(dict(index=r['index'],arm=r['arm'],repeat=r['repeat'],program=r['program'],
                             return_seconds=closed['end']-block['start']))
    pairs=[]
    for repeat in range(3):
        by_arm={a:{r['program']:r['return_seconds'] for r in rows if r['repeat']==repeat and r['arm']==a}
                for a in ('pipeline','share2')}
        pairs.append(dict(repeat=repeat,**compare(by_arm['pipeline'],by_arm['share2'])))
    delays=[v for p in pairs for v in p['program_delay_seconds'].values()]
    return dict(job='17128',planned=12,completed=12,plan_sha256=PLAN,primary_sha256=PRIMARY,
                analysis_source_sha256=sha(__file__),input_receipt_hashes=hashes,rows=rows,pairs=pairs,
                positive_delays=sum(v>0 for v in delays),program_pairs=len(delays),
                max_program_delay_seconds=max(delays),delay_median=statistics.median(delays),
                boundary='Post-hoc timing only, 3 restarts of the same 2 programs/source seed; no new trials, label access, population inference or live search quality. Identity-level and count-level dominance are different; no chosen deadline and no outcome-based rerun.')

if __name__=='__main__':
    result=analyze()
    # Exclusive new derived receipt; original closed records are never edited.
    write(ROOT/'return-dominance-v1.json',result)
    print(json.dumps({k:result[k] for k in ('job','planned','completed','pairs','positive_delays','program_pairs','max_program_delay_seconds','delay_median','boundary')},sort_keys=True,allow_nan=False))
