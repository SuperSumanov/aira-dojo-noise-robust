"""Post-hoc retained-artifact ceiling only; no new selection or execution."""
from decimal import Decimal
import importlib.util
import json
from exposure_opportunity_readout import ROOT, PLAN, ORIENTATION
from exposure_native_opportunity import diagnose
from lifecycle_pilot import read, write, sha
from live_readout import ground_scores, lines


def main():
    if sha(ROOT/'plan.json')!=PLAN:raise ValueError('exact closed batch')
    prior=read(ROOT/'native-opportunity-diagnosis-v1.json')
    plan=read(ROOT/'plan.json')
    source=ROOT/'source/src/dojo/core/solvers/utils/response.py'
    if sha(source)!=prior['native_extractor_sha256']:raise ValueError('extractor drift')
    spec=importlib.util.spec_from_file_location('frozen_response',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    rows=[]
    for s in plan['schedule']:
        ep=ROOT/f'episode-{s["index"]}';sign=ORIENTATION[s['task']]
        ns=[n for n in lines(ep/'checkpoint/journal.jsonl') if n.get('operators_used')]
        cs=sorted([read(p) for p in ep.glob('candidate-*.json') if '.private.' not in p.name],key=lambda c:c['elapsed_seconds'])
        checked=diagnose(ns,cs,sign,module.extract_code)
        old=next(r for r in prior['rows'] if r['index']==s['index'])
        if checked['counts']!=old['counts']:raise ValueError('prior linkage')
        if not ground_scores(read(ep/'finished.json'),cs,[read(p)['receipt'] for p in ep.glob('scored-*.json')]):raise ValueError('receipt')
        all_scores=[sign*Decimal(str(c['score'])) for c in cs if c['valid']]
        accepted=[sign*Decimal(str(c['score'])) for n,c in zip(ns,cs) if not n['is_buggy'] and n['metric'] is not None]
        gap=None if not all_scores or not accepted else max(all_scores)-max(accepted)
        rejected=[n for n,c in zip(ns,cs) if c['valid'] and n['is_buggy']]
        rows.append(dict(index=s['index'],task=s['task'],seed=s['seed'],complete=old['complete'],
            external_best_minus_native_best=None if gap is None else str(gap),
            external_valid_rejected=len(rejected),
            rejected_with_blank_analysis=sum(not (n.get('analysis') or '').strip() for n in rejected)))
    result=dict(plan_sha256=PLAN,prior_sha256=sha(ROOT/'native-opportunity-diagnosis-v1.json'),
        analysis_sha256=sha(__file__),rows=rows,
        boundary='Post-hoc ceiling using artifacts already produced. Not an intervention, restored score-channel policy, '
        'causal savings, or proof all rejected programs should be accepted. No node identities or raw scores exported.')
    dest=ROOT/'selection-loss-diagnosis-v1.json';write(dest,result)
    print(json.dumps(dict(sha256=sha(dest),**result)))


if __name__=='__main__':main()
