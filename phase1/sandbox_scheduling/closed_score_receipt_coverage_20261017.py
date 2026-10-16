"""Reconcile all35 external scores with all76 returned candidate receipts.

Follow-up to zero observed late returns. A scorer artifact is not necessarily
a valid, timely program return; do not label an unmatched artifact a late win.
"""
import json,math
from pathlib import Path
from closed_late_quality_20261017 import ROOT,PLAN,SUMMARY,sha,read

def main():
    assert sha(ROOT/'plan.json')==PLAN and sha(ROOT/'readout-20261017-v1/summary.json')==SUMMARY
    summary=read(ROOT/'readout-20261017-v1/summary.json');runs=read(ROOT/'readout-20261017-v1/runs.json')
    spec=read(ROOT/'dev-views/spec.json');assert summary['complete']==len(runs)==32
    rows=[];hashes={}
    for r in runs:
        ep=ROOT/f"episode-{r['index']}"
        candidates=[read(p) for p in ep.glob('candidate-*.json') if '.private.' not in p.name]
        for p in sorted(ep.glob('scored-*.json')):
            obj=read(p);rec=obj['receipt'];hashes[str(p.relative_to(ROOT))]=sha(p)
            metric=spec[r['task']]['metric_name'];score=rec[metric]
            assert type(score) in (float,int) and math.isfinite(score)
            matches=[c for c in candidates if (c.get('aux') or {}).get('submission_sha256')==rec['submission_sha256']]
            eligible=[c for c in matches if c.get('valid') is True and c.get('exit_code')==0 and not c.get('timed_out') and c['elapsed_seconds']<=1020]
            best=next(x['best'] for x in summary['by_pool'] if x['block']==r['block'] and x['task']==r['task'])
            sign=-1 if r['task']=='denoising-dirty-documents' else 1
            rows.append(dict(index=r['index'],block=r['block'],task=r['task'],score=score,
                matched_candidate_receipts=len(matches),eligible_matches=len(eligible),
                matched_states=[{k:c.get(k) for k in ('valid','exit_code','timed_out','elapsed_seconds')} for c in matches],
                original_pool_best=best,oriented_artifact_minus_pool_best=sign*(score-best)))
    assert len(rows)==summary['scores_recomputed']
    result=dict(schema=1,plan_sha256=PLAN,summary_sha256=SUMMARY,reader_sha256=sha(Path(__file__)),
        assigned=len(runs),scorer_artifacts=len(rows),eligible_candidate_matched_artifacts=sum(bool(x['eligible_matches']) for x in rows),
        rows=rows,source_hashes=hashes,
        boundary='All external scoring artifacts were recomputed by the original frozen readout. Artifact values without eligible candidate receipts are NOT eligible scores, observed late returns, or scheduler counterfactuals. Matching uses exact submission hash; repeated identical submissions can match more than one receipt. No success gate or original artifact changed.')
    dest=ROOT/'score-receipt-coverage-20261017.safe.json'
    with dest.open('x') as f:json.dump(result,f,sort_keys=True,indent=2,allow_nan=False)
    print(json.dumps(dict(sha256=sha(dest),assigned=len(runs),scorer_artifacts=len(rows),eligible_candidate_matched_artifacts=result['eligible_candidate_matched_artifacts'],
        ineligible_or_unmatched=[x for x in rows if not x['eligible_matches']])))

if __name__=='__main__':main()
