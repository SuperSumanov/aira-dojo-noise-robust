"""Join only old seeds 1/2 with the originally unstarted seed 3.

Never choose between repeated scored versions; none may exist.
"""
import argparse,csv,hashlib,json
from pathlib import Path
from readout_comparison_pool_20260919 import pairs_summary


def merge(first,second):
    a={r['index']:r for r in first['rows']};b={r['index']:r for r in second['rows']}
    if len(a)!=18 or len(b)!=18 or set(a)!=set(range(18)) or set(b)!=set(range(18)):
        raise ValueError('complete planned slots required')
    if first['job']==second['job']:raise ValueError('distinct allocations')
    rows=[]
    identity=('index','seed','task','run','slot','node','original_selected','raw_code_sha256','code_sha256')
    for i in range(18):
        if any(a[i][k]!=b[i][k] for k in identity):raise ValueError('candidate identity mismatch')
        chosen,ignored=(a[i],b[i]) if a[i]['seed'] in (1,2) else (b[i],a[i])
        if ignored['status']!='not_started' or ignored['valid'] is not None:raise ValueError('attempted duplicate cannot be ignored')
        row=dict(chosen,replay_job=first['job'] if a[i]['seed'] in (1,2) else second['job'])
        rows.append(row)
    return dict(role='complete_initial_pool_exploration_not_e2e',
        jobs=[dict(job=x['job'],allocation_state=x['allocation_state'],allocation_seconds=x['allocation_seconds'],
                   allocated_gpus=x['allocated_gpus'],gpu_hours=x['gpu_hours'],prepared_sha256=x['prepared_sha256']) for x in (first,second)],
        gpu_hours=first['gpu_hours']+second['gpu_hours'],api_calls=first['api_calls']+second['api_calls'],
        rows=rows,pools=[dict(seed=s,**pairs_summary([r for r in rows if r['seed']==s])) for s in (1,2,3)],
        valid=sum(r['valid'] is True for r in rows),program_failure=sum(r['valid'] is False for r in rows),
        unknown=sum(r['valid'] is None for r in rows))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('first',type=Path);p.add_argument('second',type=Path);args=p.parse_args()
    aa=args.first.read_bytes();bb=args.second.read_bytes();result=merge(json.loads(aa),json.loads(bb))
    result['input_summary_sha256']=[hashlib.sha256(x).hexdigest() for x in (aa,bb)]
    output=args.first.parent/'combined';output.mkdir(exist_ok=False)
    with (output/'summary.json').open('x') as handle:json.dump(result,handle,indent=2,allow_nan=False)
    with (output/'runs.csv').open('x',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=sorted({k for r in result['rows'] for k in r}));writer.writeheader();writer.writerows(result['rows'])
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
