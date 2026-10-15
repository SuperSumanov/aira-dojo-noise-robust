"""Descriptive marginal-quality timing on ONLY two closed development batches.

No new trajectories, scores, programs, labels, or predictions. Original primary
readouts remain immutable. Prefixes of 30-minute runs are not 17-minute-policy
counterfactuals, and shared pools are the unit of analysis, not independent runs.
"""
import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics

BASE=Path('/research/d7/spc/yzyang4')
SOURCES=(
    ('scheduling-weight-confirmation-20261014-v1','316381bce41c9ceb9c34fb165e94996eeeb8c9968eff3cb4e63642fbfa549626','readout-20261014-v1','d45a9678d64482d036e2f4bb3fcd4f6e0090907ca3de4d7e649e193831d4640b','score'),
    ('scheduling-metric-deployment-20261015-v2','e3baf5d2fa704cdd0c3fc458549aa21449fdbf3209bac87337b370e2a416e154','readout-20261015-v1','c68e4c4caafb3b63ad22443c5e7e2f330a0f22a3ddd47887dc06b10820e366e9','metric'),
)
CUTS=(600,1020,1500,1800)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def finite(x):return type(x) in (int,float) and math.isfinite(x)

def curve(events,initial,sign):
    assert sign in (-1,1) and finite(initial)
    assert all(finite(e['elapsed']) and e['elapsed']>=0 and finite(e['score']) for e in events)
    return [dict(seconds=t,score=max([initial]+[e['score'] for e in events if e['elapsed']<=t],key=lambda x:sign*x)) for t in CUTS]

def pool_stats(rows):
    assert len(rows)==4 and len({r['index'] for r in rows})==4
    assert len({(r['task'],r['arm'],r['block'],r['initial']) for r in rows})==1
    first=rows[0];sign=first['sign'];initial=first['initial']
    # Pool records use actual offset from pool start, not interleaved run clocks.
    events=sorted((dict(e,at=e['elapsed']+r['offset'],index=r['index']) for r in rows for e in r['valid_events']),key=lambda e:(e['at'],e['index']))
    best=initial;records=[]
    for e in events:
        if sign*(e['score']-best)>1e-12:
            records.append(dict(at=e['at'],gain=sign*(e['score']-best),score=e['score']))
            best=e['score']
    by_time=[]
    for k,t in enumerate(CUTS):
        values=[r['curve'][k]['score'] for r in rows]
        by_time.append(dict(seconds=t,best=max(values,key=lambda x:sign*x),median=statistics.median(values),sample_sd=statistics.stdev(values)))
    assert abs(by_time[-1]['best']-best)<1e-12
    return dict(block=first['block'],arm=first['arm'],task=first['task'],n=4,
        initial=initial,sign=sign,valid_returns=len(events),pool_records=len(records),records=records,
        above_initial=sum(sign*(e['score']-initial)>1e-12 for e in events),
        last_record_at=records[-1]['at'] if records else None,
        first_material_gain_at=next((e['at'] for e in records if sign*(e['score']-initial)>=.001),None),
        prefix_curves=by_time,post_1020_gain=sign*(by_time[-1]['best']-by_time[1]['best']))

def main(out):
    result=dict(kind='closed_observed_gain_timing',cuts=list(CUTS),new_gpu_jobs=0,new_model_calls=0,
        source_sha256=sha(Path(__file__)),sources=[],quality_or_speedup_claim=False,
        limitations=[
            'Post-hoc summaries of reused development data, not a new intervention or confirmation.',
            'Prefixes retain a30-minute prompt and historical shared-archive context; not predictions for a17-minute policy.',
            'No shorter allocation cost inferred. Startup, reserved slots, failures and service costs stay in primary readouts.',
            'Pool-record order is descriptive; this does not identify whether a candidate saw the previous record at generation.',
            'Different training lineages/data and shared-service pools cannot be merged into a causal weight or overall win rate.',
            'A new record is not necessarily practically important; raw gains and the pre-existing.001 denoising reference are shown.',
            'No additional requests or unknown cancelled outcomes invented. Existing frozen protocol and quality gate are unchanged.'])
    for name,pin,readout,summary_pin,label in SOURCES:
        root=BASE/name;assert sha(root/'plan.json')==pin
        assert sha(root/readout/'summary.json')==summary_pin
        plan=read(root/'plan.json');closed=read(root/'closed.json')
        assert closed['error'] is None and closed['complete']==plan['planned'] and plan['run_seconds']==1800
        endpoint={r['index']:r for r in read(root/readout/'runs.json')}
        warm=read(root/'warm-receipt.json');rows=[];hashes={}
        def tracked(p):
            before=sha(p);v=read(p);assert sha(p)==before
            hashes[str(p.relative_to(root))]=before;return v
        for s in plan['schedule']:
            ep=root/f"episode-{s['index']}";initial=warm[s['task']]['score']
            sign=1 if s['task']=='aerial-cactus-identification' else -1
            deadline=tracked(ep/'deadline.json')
            slot=tracked(root/f"block-{s['block']}/budget-slot.json")
            assert deadline['budget_seconds']==1800 and deadline['cleanup_is_score_time'] is False
            offset=datetime.fromisoformat(deadline['started_utc']).timestamp()-slot['start']
            assert 0<=offset<60
            receipts=[tracked(p)['receipt'] for p in sorted(ep.glob('scored-*.json'))]
            events=[];returned=late=0
            for p in sorted(ep.glob('candidate-*.json')):
                if '.private.' in p.name:continue
                c=tracked(p);assert finite(c['elapsed_seconds']) and c['elapsed_seconds']>=0
                if c['elapsed_seconds']>1800:late+=1;continue
                returned+=1
                valid=c['valid'] is True and c['exit_code']==0 and not c['timed_out'] and finite(c.get('score'))
                if not valid:continue
                aux=c['aux'];metric=aux['metric_name']
                assert any(r.get('submission_sha256')==aux['submission_sha256'] and r.get(metric)==c['score'] for r in receipts)
                events.append(dict(elapsed=c['elapsed_seconds'],score=c['score']))
            path=curve(events,initial,sign);ref=endpoint[s['index']]
            assert ref['complete'] and abs(path[-1]['score']-ref['score'])<1e-12
            assert returned==ref['candidate_returns'] and len(events)==ref['valid_returns']
            rows.append(dict(index=s['index'],block=s['block'],arm=s['arm'],task=s['task'],sign=sign,initial=initial,
                offset=offset,returned=returned,late=late,valid_events=events,curve=path))
        pools=[pool_stats([r for r in rows if (r['block'],r['task'])==(b,t)]) for b in sorted({r['block'] for r in rows}) for t in sorted(warm)]
        result['sources'].append(dict(name=label,root_name=name,plan_sha256=pin,summary_sha256=summary_pin,
            assigned=len(rows),all_primary_endpoints_reproduced=True,rows=rows,pools=pools,source_hashes=hashes))
    with Path(out).open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(dict(output=str(out),sources=[dict(name=s['name'],assigned=s['assigned'],pools=s['pools']) for s in result['sources']])))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('out');main(p.parse_args().out)
