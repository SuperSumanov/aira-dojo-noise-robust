"""Join disjoint originally planned banks; preserve separate allocation costs."""
import argparse,csv,hashlib,json,math
from pathlib import Path
from verify_comparison_reuse_results_20260919 import verify

FIRST_SHA='f3ea334c94257bbbbc06229a8a3aeea609e2516879bdf9a32822e176897ee9ce'
REMAINDER_PREPARED='40b291747042f3a1e04781870e3d67e33342a29ac1aea896c1a1a93d2a65c399'


def combine(first,second):
    verify(first);verify(second)
    if first['job']!='14115' or second['job']!='14128' or any(s['allocated_gpus']!=6 for s in (first,second)):
        raise ValueError('two distinct fixed allocations required')
    if any(r['valid'] is not None or r['status']!='not_started' for r in first['rows'] if r['seed']==2):raise ValueError('seed2 previously attempted')
    if any(r['valid'] is not None or r['status']!='not_started' for r in second['rows'] if r['seed']==1):raise ValueError('seed1 repeated')
    def identity(row):return tuple(row[k] for k in ('index','seed','run','node','role','slot','raw_code_sha256','code_sha256'))
    if {identity(r) for r in first['rows']}!={identity(r) for r in second['rows']}:raise ValueError('candidate matrix differs')
    rows=[dict(r,execution_job=s['job']) for seed,s in [(1,first),(2,second)] for r in s['rows'] if r['seed']==seed]
    groups=[g for seed,s in [(1,first),(2,second)] for g in s['groups'] if g['seed']==seed]
    seconds=first['allocation_seconds']+second['allocation_seconds']
    result=dict(role='exploratory_continuation_action_bank_not_live_e2e',job='14115+14128',rows=rows,groups=groups,
        allocation_seconds=seconds,allocated_gpus=6,gpu_hours=sum(s['gpu_hours'] for s in (first,second)),api_calls=0,
        valid=sum(r['valid'] is True for r in rows),no_valid_output=sum(r['valid'] is False for r in rows),unknown=sum(r['valid'] is None for r in rows),
        allocations=[{k:s[k] for k in ('job','allocation_state','allocation_seconds','allocated_gpus','gpu_hours','prepared_sha256')} for s in (first,second)],
        time_accounting='Sum of separate allocation seconds, not elapsed wall time; later completion decided after seeing seed1.',
        conclusion_boundary='Two exploratory fixed physical runs, not randomized E2E; all candidate alternatives within a run remain dependent.')
    verify(result);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('first',type=Path);parser.add_argument('remainder',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
    first_raw=args.first.read_bytes();second_raw=args.remainder.read_bytes()
    if hashlib.sha256(first_raw).hexdigest()!=FIRST_SHA:raise ValueError('first immutable result identity')
    first=json.loads(first_raw);second=json.loads(second_raw)
    if second['prepared_sha256']!=REMAINDER_PREPARED:raise ValueError('remainder identity')
    result=combine(first,second);result['source_summary_sha256']=[FIRST_SHA,hashlib.sha256(second_raw).hexdigest()]
    args.output.mkdir(exist_ok=False)
    with (args.output/'summary.json').open('x',encoding='utf-8') as handle:json.dump(result,handle,indent=2);handle.write('\n')
    with (args.output/'runs.csv').open('x',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=sorted({k for r in result['rows'] for k in r}));writer.writeheader();writer.writerows(result['rows'])
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
