"""Check repeated candidate outcomes and exact known framework timing suffix."""
import argparse,hashlib,json,re
from pathlib import Path


def verify(prior,current,history):
    fresh={r['node']:r for r in current['rows'] if r['seed']==1 and r['role']=='cache'}
    previous={r['node']:r for r in prior['rows'] if r['seed']==1 and not r['original_selected']}
    if set(fresh)!=set(previous) or len(fresh)!=4:raise ValueError('same complete four cache nodes')
    repeats=[]
    for node,row in fresh.items():
        old=previous[node]
        if row['raw_code_sha256']!=old['raw_code_sha256'] or row['code_sha256']!=old['code_sha256']:raise ValueError('code drift')
        repeats.append(dict(node=node,validity_agrees=row['valid']==old['valid'],
                            previous_valid=old['valid'],current_valid=row['valid'],
                            score_agrees_at_reported_precision=row['score']==old['score']))
    record,=history['records'];old=record['historical_terminal_error'];new=record['fresh_terminal_error']
    timing_only=bool(old and new and old.startswith(new) and
        re.fullmatch(r'Execution time: [0-9]+ seconds \(time limit is 2 hours\)\.',old[len(new):]))
    return dict(role='source_failure_and_cache_repeatability_check_not_new_independent_runs',cache_repeats=repeats,
                debug_historical_exit_code=record['historical_exit_code'],debug_fresh_exit_code=record['fresh_exit_code'],
                historical_debug_was_buggy=record['historical_is_buggy'],
                debug_error_literal_equal=old==new,known_framework_timing_suffix_only=timing_only,
                same_debug_error_core=(old==new or timing_only),
                caveat='A matching terminal error rules out this failure arising only in the fresh execution, not all possible workspace/environment differences.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('prior',type=Path);p.add_argument('current',type=Path);p.add_argument('history',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    raws=[path.read_bytes() for path in (a.prior,a.current,a.history)]
    expected=['721f995ca597568303f65c32e9d04667bcdd173c174b2e6af99bb78e765c0eb1',
              'f3ea334c94257bbbbc06229a8a3aeea609e2516879bdf9a32822e176897ee9ce']
    if [hashlib.sha256(v).hexdigest() for v in raws[:2]]!=expected:raise ValueError('closed summary identity')
    result=verify(*(json.loads(v) for v in raws));result['source_sha256']=[hashlib.sha256(v).hexdigest() for v in raws]
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result,indent=2))
