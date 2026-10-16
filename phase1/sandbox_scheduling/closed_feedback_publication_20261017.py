"""Closed18807 certificate-to-archive delay, not an early-publication policy.

An observed admission could have selected a better already validated program
only if its original score exceeded the recorded archive at that exact time.
That does NOT identify the quality of the ungenerated alternative child.
"""
import ast,collections,hashlib,json,math,statistics
from datetime import datetime
from pathlib import Path
from closed_quota_borrowing_20261017 import ROOT,PIN,TASKS

SUMMARY='c8c2f71009a39e9932ec59e388f9b052ce190730179119aed5d73e4fa38576a4'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def stats(v):
    return dict(n=len(v),median=statistics.median(v) if v else None,
        sample_sd=statistics.stdev(v) if len(v)>1 else None,min=min(v) if v else None,max=max(v) if v else None)

def main():
    assert sha(ROOT/'plan.json')==PIN and sha(ROOT/'readout-20261016-v1/summary.json')==SUMMARY
    plan=read(ROOT/'plan.json');assert read(ROOT/'closed.json')['complete']==32
    source=ROOT/'source/src/dojo/solvers/mcts/mcts.py'
    assert sha(source)==plan['files']['source/src/dojo/solvers/mcts/mcts.py']
    tree=ast.parse(source.read_text());method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='parse_eval_result')
    analyze=[n.lineno for n in ast.walk(method) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='_analyze']
    assert len(analyze)==1
    parent=ROOT/'feedback_parent_policy_20261012.py';assert sha(parent)==plan['files'][parent.name]
    parent_tree=ast.parse(parent.read_text());parse=next(n for n in ast.walk(parent_tree) if isinstance(n,ast.FunctionDef) and n.name=='parse')
    first=parse.body[0];assert isinstance(first,ast.Expr) and isinstance(first.value,ast.Call) and isinstance(first.value.func,ast.Name) and first.value.func.id=='original_parse'
    hashes={str(source.relative_to(ROOT)):sha(source),parent.name:sha(parent)};pools=[]
    for b in range(4):
        f=ROOT/f'generation-{b}/events.jsonl';hashes[str(f.relative_to(ROOT))]=sha(f)
        events=[json.loads(x) for x in f.read_text().splitlines()]
        published=collections.defaultdict(list);admissions=[];requests={}
        for e in events:
            if e['event']=='queued':requests[e['request']['key']]=e['request']
            elif e['event']=='round_complete':published[(e['run'],e['code_sha256'])].append(e)
            elif e['event']=='admitted' and e['role']=='improve':admissions.append(e)
        candidates=[];unmatched=0
        for row in [r for r in plan['schedule'] if r['block']==b]:
            ep=ROOT/f"episode-{row['index']}";d=read(ep/'deadline.json');start=datetime.fromisoformat(d['started_utc']).timestamp()
            hashes[str((ep/'deadline.json').relative_to(ROOT))]=sha(ep/'deadline.json')
            for file in ep.glob('candidate-*.json'):
                if '.private.' in file.name:continue
                c=read(file);hashes[str(file.relative_to(ROOT))]=sha(file)
                if not(c['elapsed_seconds']<=1020 and c['valid'] is True and c['exit_code']==0 and not c['timed_out']):continue
                assert type(c['score']) in (int,float) and math.isfinite(c['score'])
                matches=published[(row['index'],c['code_sha256'])];assert len(matches)<=1
                finish=matches[0]['time'] if matches else start+1020
                returned=start+c['elapsed_seconds'];assert finish>=returned-.01
                if matches:assert matches[0]['valid']
                else:unmatched+=1
                candidates.append(dict(task=row['task'],returned=returned,published=finish,censored=not matches,score=c['score']))
        refs=[r for r in read(ROOT/'readout-20261016-v1/runs.json') if r['block']==b]
        assert len(candidates)==sum(r['valid_returns'] for r in refs)
        by=[]
        for task in TASKS:
            selected=[c for c in candidates if c['task']==task];sign=1 if task==TASKS[0] else -1
            considered=potential=0;gains=[]
            for a in admissions:
                if requests[a['key']]['task']!=task:continue
                pending=[c for c in selected if c['returned']<=a['time']<c['published']]
                if not pending:continue
                considered+=1
                incumbent=max(sign*v['metric'] for v in a['snapshot']['archive'][task].values())
                gain=max(sign*c['score'] for c in pending)-incumbent
                if gain>1e-12:potential+=1;gains.append(gain)
            delays=[max(0,c['published']-c['returned']) for c in selected if not c['censored']]
            by.append(dict(task=task,valid=len(selected),published=len(delays),not_published_before_run_deadline=sum(c['censored'] for c in selected),
                observed_delay_seconds=stats(delays),admissions_during_unpublished_valid_window=considered,
                admissions_with_a_better_unpublished_valid_parent=potential,potential_parent_score_gain=stats(gains)))
        pools.append(dict(block=b,by_task=by))
    result=dict(plan_sha256=PIN,summary_sha256=SUMMARY,reader_sha256=sha(Path(__file__)),source_hashes=hashes,pools=pools,
        source_order=dict(native_analyze_before_parent_wrapper_archive_update=True,native_parse_analyze_line=analyze[0]),
        boundary='Closed descriptive observations only; exact code-hash join and all valid candidate denominator. Publication delay includes waiting, analysis and overhead, not all LLM compute. Unpublished candidates are censored at run deadline. Potential parent changes are not generated children, saved time or causal final-quality gain. No new policy, model, GPU or scorer call; no primary gate changed.')
    out=ROOT/'feedback-publication-20261017-v1.safe.json'
    with out.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(dict(sha256=sha(out),pools=pools,source_order=result['source_order'])))

if __name__=='__main__':main()
