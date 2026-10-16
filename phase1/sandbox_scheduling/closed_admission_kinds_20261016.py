"""Explain missing terminal traces at sealed18807 admissions, no outcomes."""
import hashlib
import json
from pathlib import Path
from collections import Counter
from closed_online_observability_20261016 import ROOT, PIN, intervals, read, sha


def main():
    assert sha(ROOT/'plan.json') == PIN and (ROOT/'closed.json').exists()
    obs = ROOT/'online-observability-20261016.safe.json'
    assert sha(obs) == '1c1e49c4622b8a6883d5ae9b1716b06a9a6c90703b595c1cf17f9d78e4f7a1ce'
    prior = {(r['block'],r['admission_ordinal']): r for r in read(obs)['admissions']}
    rows=[]
    for block in (1,2):
        source=ROOT/f'pool-{block}/events.jsonl'
        leases, admissions=intervals([json.loads(l) for l in source.read_text().splitlines()])
        for ordinal, event in enumerate(admissions):
            row=dict(block=block, admission_ordinal=ordinal)
            for side in ('incumbent','newcomer'):
                key=event[side]; index, op=map(int,key.split(':')); lease=leases[key]
                log=ROOT/f'episode-{index}/events.jsonl'
                events=[json.loads(l) for l in log.read_text().splitlines()]
                kind=[e['kind'] for e in events if e['event']=='operation_ready' and e['operation']==op]
                assert len(kind)==1 and kind[0] in ('preview','candidate')
                scoped=[e for e in events if lease['start']<=e['time']<=lease['end']]
                ready=[e['success'] for e in scoped if e['event']=='kernel_ready']
                cells=[dict(exit_code=e['exit_code'],timed_out=e['timed_out']) for e in scoped if e['event']=='cell_return']
                row[side]=dict(kind=kind[0], ready_observations=ready, cell_returns=cells,
                    terminal_cuda_trace_available=prior[(block,ordinal)][side+'_cuda_trace_available'],
                    event_sha256=sha(log))
            rows.append(row)
    counts=Counter(r['incumbent']['kind']+'+'+r['newcomer']['kind'] for r in rows)
    missing=Counter()
    for r in rows:
        for side in ('incumbent','newcomer'):
            s=r[side]
            if s['terminal_cuda_trace_available']:continue
            if s['kind']=='preview':kind='preview'
            elif False in s['ready_observations']:kind='candidate_readiness_failure'
            elif any(c['timed_out'] for c in s['cell_returns']):kind='candidate_timeout_return'
            elif any(c['exit_code']!=0 for c in s['cell_returns']):kind='candidate_error_return'
            else:kind='candidate_unresolved_from_event_receipts'
            missing[kind]+=1
    result=dict(posthoc=True,analysis_sha256=sha(Path(__file__)),plan_sha256=PIN,
        parent_analysis_sha256=sha(obs),admissions=rows,admission_kind_counts=dict(counts),
        missing_side_occurrence_counts=dict(missing),
        boundary='A lease may occur in more than one admission: side occurrences are not distinct jobs. Terminal traces exist only for scored returns with recorded CUDA optimizer calls. Preview/timeout/error event categories do not prove absence of GPU work. No candidate source, output, score or prediction read; not online baseline effectiveness or causality.')
    with (ROOT/'admission-kinds-20261016.safe.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(result))


if __name__=='__main__':main()
