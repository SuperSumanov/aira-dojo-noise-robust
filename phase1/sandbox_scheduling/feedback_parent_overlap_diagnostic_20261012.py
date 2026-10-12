"""Post-readout descriptive check; no new policy, samples, or causal rescue.

Does an improvement admitted while the same parent was already in flight
produce a useful, distinct program? Candidate identities remain remote.
Debug descendants are NOT silently credited to the originating Improve.
"""
import argparse
import json
from pathlib import Path
import hashlib
import math


def summarize(events, candidates, task_by_run, sign):
    requests, pending, calls = {}, {}, {}
    for e in events:
        kind, key = e['event'], e.get('key')
        if kind == 'queued':
            requests[e['request']['key']] = e['request']
        elif kind == 'admitted' and e['role'] == 'improve':
            r = requests[key]; task = r['task']; arc = e['snapshot']['archive'][task]
            same = any(v == (task, e['parent']) for v in pending.values())
            pending[key] = (task, e['parent'])
            calls[key] = dict(run=e['run'], task=task, overlapping_parent=same,
                parent=e['parent'], parent_score=arc[e['parent']]['metric'],
                incumbent=max((v['metric'] for v in arc.values()), key=lambda x:sign[task]*x))
        elif kind == 'parent_used':
            calls[key]['child'] = e['child']
        elif kind in ('round_complete','abandoned'):
            pending.pop(key, None)
    assert not pending
    output = {}
    for task in sorted(set(task_by_run.values())):
        result = {}
        for overlap in (False, True):
            selected=[v for v in calls.values() if v['task']==task and v['overlapping_parent']==overlap]
            scores=[];parent_gains=[];incumbent_gains=[];codes=[];ambiguous=0
            for c in selected:
                if 'child' not in c: continue
                codes.append(c['child'])
                records=candidates.get((c['run'],c['child']),[])
                valid=[r for r in records if r['elapsed_seconds']<=1020 and r.get('valid') is True
                       and r.get('exit_code')==0 and not r.get('timed_out')
                       and type(r.get('score')) in (int,float) and math.isfinite(r['score'])]
                if len(valid)>1:
                    ambiguous+=1
                    continue
                if valid:
                    score=valid[0]['score'];scores.append(score)
                    parent_gains.append(sign[task]*(score-c['parent_score']))
                    incumbent_gains.append(sign[task]*(score-c['incumbent']))
            result['overlapping_same_parent' if overlap else 'no_overlapping_same_parent']=dict(
                admitted=len(selected),generated=len(codes),unique_generated_code=len(set(codes)),
                direct_timely_valid=len(scores),ambiguous_multiple_valid_executions=ambiguous,
                improves_selected_parent=sum(x>1e-12 for x in parent_gains),
                improves_incumbent_at_admission=sum(x>1e-12 for x in incumbent_gains),
                direct_best=max(scores,key=lambda x:sign[task]*x) if scores else None)
        output[task]=result
    return output


def main(root, out):
    root=Path(root);read=lambda p:json.loads(p.read_text())
    summary=read(root/'partial-readout-v1/summary.json');plan=read(root/'plan.json')
    assert summary['predeclared_success_gate_met'] is False
    qualified=[b['block'] for b in summary['blocks'] if b['qualified']]
    assert qualified==[0,1,2,3]
    sign={'aerial-cactus-identification':1,'denoising-dirty-documents':-1}
    result=[]
    for b in qualified:
        schedule=[r for r in plan['schedule'] if r['block']==b]
        candidates={}
        for row in schedule:
            for file in (root/f"episode-{row['index']}").glob('candidate-*.json'):
                if '.private.' in file.name:continue
                r=read(file);candidates.setdefault((row['index'],r['code_sha256']),[]).append(r)
        events=[json.loads(v) for v in (root/f'generation-{b}/events.jsonl').read_text().splitlines()]
        result.append(dict(block=b,arm=schedule[0]['arm'],by_task=summarize(events,candidates,
                            {r['index']:r['task'] for r in schedule},sign)))
    value=dict(posthoc_after_quality_read=True,source_commit=plan['source_commit'],
        plan_sha256=hashlib.sha256((root/'plan.json').read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),pools=result,
        limitation='Descriptive factual outcomes of overlapping admissions; not the counterfactual outcome if withheld. Exact code diversity is not behavioral diversity. Direct Improve only; debug descendants not attributed. No new success gate or expansion.')
    with Path(out).open('x') as f:json.dump(value,f,indent=2,allow_nan=False,sort_keys=True)
    print(json.dumps(value,allow_nan=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('output')
    a=p.parse_args();main(a.root,a.output)
