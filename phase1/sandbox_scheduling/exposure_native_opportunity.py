"""Post-outcome diagnostic, not a replacement of the frozen qualification.

Match native extract_code output exactly in sequence, including empty code.
Distinguish external scorable artifacts from native accepted nodes. Never change
the solver, replay programs, impute missing results, or export candidate content.
"""
from collections import Counter
import csv
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
from exposure_opportunity_readout import ROOT, PLAN, ORIENTATION
from lifecycle_pilot import read, sha, write
from live_readout import ground_scores, lines


def diagnose(nodes, candidates, sign, extract):
    nodes=[n for n in nodes if n.get('operators_used')]
    if len(nodes)!=len(candidates):raise ValueError('exact full sequence required')
    steps=[n['step'] for n in nodes]
    if steps!=sorted(steps) or len(steps)!=len(set(steps)):raise ValueError('step order')
    counts=Counter();parents={};best=None;external_best=None;improvements=[]
    for n,c in zip(nodes,candidates):
        code=extract(n['code'])
        if hashlib.sha256(code.encode()).hexdigest()!=c['code_sha256']:
            raise ValueError('native extraction sequence mismatch')
        role=n['operators_used'][0]
        if role not in ('draft','debug','improve'):raise ValueError('role')
        counts['matched']+=1;counts['empty_executed_code']+=not code.strip()
        counts['external_valid']+=c['valid'] is True
        accepted=n.get('is_buggy') is False and n.get('metric') is not None
        if accepted and (c['valid'] is not True or n['metric']!=c['score']
                         or n.get('metric_maximize')!=(sign==1)):
            raise ValueError('accepted node lacks exact external grounding')
        counts['native_accepted']+=accepted
        if c['valid'] and not accepted:
            counts['external_valid_native_rejected']+=1
            counts['external_valid_rejected_exit_zero']+=n.get('exit_code')==0
        score=sign*Decimal(str(c['score'])) if accepted else None
        external_score=sign*Decimal(str(c['score'])) if c['valid'] else None
        if role=='improve':
            counts['improve_attempts']+=1
            counts['external_valid_improves']+=c['valid'] is True
            counts['native_accepted_improves']+=accepted
            ps=n.get('parents',[]);parent=parents.get(ps[0]) if len(ps)==1 else None
            delta=None if score is None or parent is None else score-parent
            record=None if score is None or best is None else score-best
            external_record=None if score is None or external_best is None else score-external_best
            improvements.append(dict(accepted=accepted,parent_grounded=parent is not None,
                parent_oriented_delta=None if delta is None else str(delta),
                incumbent_oriented_delta=None if record is None else str(record),
                all_external_history_oriented_delta=None if external_record is None else str(external_record),
                returned_seconds=c['elapsed_seconds']))
        parents[n['step']]=score
        if score is not None:best=score if best is None else max(best,score)
        if external_score is not None:external_best=external_score if external_best is None else max(external_best,external_score)
    counts['strict_native_incumbent_improvements']=sum(r['incumbent_oriented_delta'] is not None
        and Decimal(r['incumbent_oriented_delta'])>0 for r in improvements)
    counts['accepted_improves_beating_all_external_history']=sum(r['all_external_history_oriented_delta'] is not None
        and Decimal(r['all_external_history_oriented_delta'])>0 for r in improvements)
    counts['better_than_parent']=sum(r['parent_oriented_delta'] is not None
        and Decimal(r['parent_oriented_delta'])>0 for r in improvements)
    return dict(counts=dict(counts),improves=improvements)


def main():
    if sha(ROOT/'plan.json')!=PLAN or not (ROOT/'closed.json').exists():raise ValueError('exact closed batch')
    plan=read(ROOT/'plan.json')
    for name,pin in plan['files'].items():
        if sha(ROOT/name)!=pin:raise ValueError('source drift')
    source=ROOT/'source/src/dojo/core/solvers/utils/response.py'
    spec=importlib.util.spec_from_file_location('frozen_response',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    primary=read(ROOT/'exposure-readout-v1.json');rows=[]
    for s in plan['schedule']:
        ep=ROOT/f'episode-{s["index"]}'
        cs=sorted([read(p) for p in ep.glob('candidate-*.json') if '.private.' not in p.name],key=lambda c:c['elapsed_seconds'])
        if any(c['elapsed_seconds']>3000 for c in cs):raise ValueError('late candidate')
        if not ground_scores(read(ep/'finished.json'),cs,[read(p)['receipt'] for p in ep.glob('scored-*.json')]):
            raise ValueError('external receipt grounding')
        p=next(r for r in primary['rows'] if r['index']==s['index'])
        rows.append(dict(**s,complete=p['complete'],**diagnose(lines(ep/'checkpoint/journal.jsonl'),cs,ORIENTATION[s['task']],module.extract_code)))
    result=dict(plan_sha256=PLAN,primary_sha256=sha(ROOT/'exposure-readout-v1.json'),
        analysis_sha256=sha(__file__),native_extractor_sha256=sha(source),rows=rows,
        source_commit=plan['source_commit'],allocation_gpu_seconds=primary['allocation_gpu_seconds'],
        boundary='Post-outcome diagnosis after frozen secondary refused native/external mismatch. '
        'Frozen primary and failed cross-task/all4 qualification unchanged. '
        'Native accepted nodes only for parent/incumbent gains, all4 retained. '
        'Single-arm dependent development gains: not scheduling effects, generalization, repeatability or confirmation.')
    dest=ROOT/'native-opportunity-diagnosis-v1.json';write(dest,result)
    flat=[]
    for r in rows:
        flat.append(dict(**{k:r[k] for k in ('index','task','seed','arm','complete')},
            source_commit=plan['source_commit'],plan_sha256=PLAN,run_budget_seconds=3000,
            shared_allocation_gpu_seconds=primary['allocation_gpu_seconds'],
            cost_scope='shared pool total repeated; do not sum',**r['counts']))
    fields=list(dict.fromkeys(k for r in flat for k in r))
    with (ROOT/'native-opportunity-safe-runs-v1.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(flat)
    print(json.dumps(dict(sha256=sha(dest),csv_sha256=sha(ROOT/'native-opportunity-safe-runs-v1.csv'),**result)))


if __name__=='__main__':main()
