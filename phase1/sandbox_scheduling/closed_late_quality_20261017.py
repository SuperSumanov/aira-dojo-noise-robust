"""Closed18997 late-valid outcomes: fixed-history opportunity, not a policy.

All assigned runs and all public candidate receipts are included. No code,
prediction, raw journal, label, or secret value is exported. Late values never
enter the original endpoint or success gate. This is not a counterfactual run.
"""
import hashlib,json,math,re
from pathlib import Path

ROOT=Path('/research/d7/spc/yzyang4/scheduling-selective-20261017-v1')
PLAN='1783555a7c680021b2a1bae874798f1042c0bfe79d0b11af70fa7f2a75d26e32'
SUMMARY='0bd972126ab1bb9427ea93e446be3d3e245955c8bd5aa7e08778b7afa05c3514'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    raw=p.read_bytes()
    assert not SECRET.search(raw),'credential-shape hit; no output'
    return json.loads(raw)

def main():
    assert sha(ROOT/'plan.json')==PLAN and sha(ROOT/'readout-20261017-v1/summary.json')==SUMMARY
    plan=read(ROOT/'plan.json');closed=read(ROOT/'closed.json')
    summary=read(ROOT/'readout-20261017-v1/summary.json')
    runs=read(ROOT/'readout-20261017-v1/runs.json')
    assert closed['complete']==summary['complete']==len(runs)==32
    hashes={};candidates=[];rows=[]
    for r in runs:
        ep=ROOT/f"episode-{r['index']}"
        for p in sorted(ep.glob('candidate-*.json')):
            if '.private.' in p.name:continue
            c=read(p);hashes[str(p.relative_to(ROOT))]=sha(p)
            elapsed=c['elapsed_seconds'];assert type(elapsed) in (float,int) and math.isfinite(elapsed) and elapsed>=0
            valid=c.get('valid') is True and c.get('exit_code')==0 and not c.get('timed_out')
            if valid:assert type(c.get('score')) in (float,int) and math.isfinite(c['score'])
            candidates.append(dict(index=r['index'],block=r['block'],task=r['task'],valid=valid,
                timely=elapsed<=plan['run_seconds'],elapsed_seconds=elapsed,score=c.get('score') if valid else None))
    for group in summary['by_pool']:
        rr=[r for r in runs if r['block']==group['block'] and r['task']==group['task']]
        cc=[c for c in candidates if c['block']==group['block'] and c['task']==group['task']]
        assert len(rr)==4
        timely=[c for c in cc if c['timely']];late=[c for c in cc if not c['timely']]
        assert len(timely)==sum(r['candidate_returns'] for r in rr)
        assert sum(c['valid'] for c in timely)==sum(r['valid_returns'] for r in rr)
        sign=-1 if group['task']=='denoising-dirty-documents' else 1
        lv=[c for c in late if c['valid']]
        augmented=max([group['best']]+[c['score'] for c in lv],key=lambda v:sign*v)
        native=[r['native_selected_score'] for r in rr if type(r.get('native_selected_score')) in (float,int) and math.isfinite(r['native_selected_score'])]
        rows.append(dict(block=group['block'],task=group['task'],pool_mode=group['pool_mode'],assigned=4,
            all_candidate_receipts=len(cc),timely_returns=len(timely),late_returns=len(late),late_valid=len(lv),
            original_best=group['best'],best_including_observed_late=augmented,
            oriented_observed_late_gain=sign*(augmented-group['best']),
            late_valid_lateness_seconds=[c['elapsed_seconds']-plan['run_seconds'] for c in lv],
            native_selected_recorded=len(native),recorded_native_pool_best=max(native,key=lambda v:sign*v) if native else None))
    out=dict(schema=1,plan_sha256=PLAN,summary_sha256=SUMMARY,reader_sha256=sha(Path(__file__)),
        assigned=32,candidate_receipts=len(candidates),rows=rows,receipt_hashes=hashes,
        boundary='Post-closure descriptive diagnostic. Observed late completions do not predict an alternative scheduler, unchanged proposals, or saved wall time. Native-selected values are the recorded readout fields, not an independent native-selection provenance audit. No altered success gate, no rescoring, no GPU/model call.')
    dest=ROOT/'late-quality-20261017.safe.json'
    with dest.open('x') as f:json.dump(out,f,sort_keys=True,indent=2,allow_nan=False)
    print(json.dumps(dict(sha256=sha(dest),assigned=32,candidate_receipts=len(candidates),rows=rows)))

if __name__=='__main__':main()
