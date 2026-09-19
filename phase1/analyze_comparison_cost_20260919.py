"""Historical request latency, NOT additive GPU cost or an intervention result."""
import argparse, hashlib, json, math, statistics, subprocess
from collections import defaultdict
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def distribution(values):
    if not values:
        return dict(n=0, median=None, mean=None, sd=None, minimum=None, maximum=None)
    return dict(n=len(values), median=statistics.median(values), mean=statistics.mean(values),
                sd=statistics.stdev(values) if len(values)>1 else None, minimum=min(values), maximum=max(values))


def analyze(runs, nodes, metadata):
    run_map={r['run']:r for r in runs}
    node_map={(n['run'], n['id']):n for n in nodes}
    met_map={(m['run'], m['node']):m for m in metadata}
    if len(run_map)!=len(runs) or len(node_map)!=len(nodes) or len(met_map)!=len(metadata):
        raise ValueError('duplicate identity')
    if set(node_map)!=set(met_map):
        raise ValueError('metadata/node join is not exact')
    candidates=defaultdict(list); byrun=defaultdict(list)
    for key,n in node_map.items():
        m=met_map[key]
        if m['group']!=n['group'] or m['operators']!=n['operators_used']:
            raise ValueError('operator identity drift')
        ops=m['operators'] or []
        fields=m['numeric_operator_fields']
        if not ops:
            if n['parents'] or n['code_chars'] or fields:
                raise ValueError('unrecognized empty-operator node')
            continue
        if ops[0] not in ('draft','improve','debug'):
            raise ValueError('unrecognized generating operator')
        latency=fields.get('.0.usage.latency')
        if type(latency) not in (int,float) or not math.isfinite(latency) or latency<0:
            raise ValueError('missing or bad request latency')
        for value in fields.values():
            if not math.isfinite(value) or value<0:raise ValueError('bad numeric metadata')
        row=dict(run=n['run'], node=n['id'], group=n['group'], generation_operator=ops[0],
                 request_latency_seconds=latency, logged_cost=fields.get('.0.usage.cost'),
                 total_tokens=fields.get('.0.usage.total_tokens'),
                 execution_seconds=n['exec_time'] if n['group']=='executed' else None)
        byrun[n['run']].append(row)
        if n['parents']==[0] and ops[0]=='draft':candidates[n['run']].append(row)
    output=[]; pools=[]
    for rid,run in run_map.items():
        rows=byrun[rid]
        output.append(dict(run=rid, stratum=run['stratum'], arm=run['arm'], seed=run['seed'],
                           journal_present=run['journal_present'], requests=len(rows),
                           request_latency_seconds=distribution([r['request_latency_seconds'] for r in rows]),
                           executed_request_latency_seconds=distribution([r['request_latency_seconds'] for r in rows if r['group']=='executed']),
                           unselected_request_latency_seconds=distribution([r['request_latency_seconds'] for r in rows if r['group']=='unselected']),
                           zero_logged_costs=sum(r['logged_cost']==0 for r in rows)))
        roots=candidates[rid]
        if run['arm'].startswith('forets') and run['journal_present']:
            chosen=[r for r in roots if r['group']=='executed']
            if len(roots)!=6 or len(chosen)!=2:raise ValueError('expected complete root pool')
            times=[r['request_latency_seconds'] for r in roots]
            execution=[r['execution_seconds'] for r in chosen]
            if any(type(t) not in (int,float) or not math.isfinite(t) or t<0 for t in execution):
                raise ValueError('bad execution duration')
            execute_sum=sum(execution)
            pools.append(dict(run=rid,stratum=run['stratum'],arm=run['arm'],seed=run['seed'],
                              six_request_latencies_seconds=sorted(times),
                              longest_request_seconds=max(times),
                              selected_two_execution_seconds=execution,
                              selected_execution_sum_seconds=execute_sum,
                              longest_generation_over_selected_execution=max(times)/execute_sum if execute_sum>0 else None))
    grouped=[]
    for stratum in sorted({p['stratum'] for p in pools}):
        group=[p for p in pools if p['stratum']==stratum]
        grouped.append(dict(stratum=stratum, pools=len(group),
            longest_generation_seconds=distribution([p['longest_request_seconds'] for p in group]),
            selected_execution_sum_seconds=distribution([p['selected_execution_sum_seconds'] for p in group]),
            per_pool_ratio=distribution([p['longest_generation_over_selected_execution'] for p in group
                                        if p['longest_generation_over_selected_execution'] is not None]),
            longest_generation_exceeds_execution=sum(p['longest_request_seconds']>p['selected_execution_sum_seconds'] for p in group)))
    return dict(role='historical_descriptive_cost_diagnostic',runs=output,root_pools=pools,by_task=grouped,
        limitations=['Client-observed latency includes queuing/retries; not exclusive GPU service time.',
                     'Concurrent request latencies cannot be summed into wall-clock time.',
                     'Longest request is a lower bound on the gather stage; critic/setup overhead not recovered.',
                     'Execution times are original selected programs only; selection/runtime confounding remains.',
                     'Zero logged currency cost is not proof of zero compute cost.',
                     'This is not evidence that shrinking width improves final quality.'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);args=parser.parse_args()
    names=('runs.json','nodes.json','operator-cost-metadata.json')
    payload=analyze(*(json.loads((args.root/n).read_bytes()) for n in names))
    payload['input_sha256']={n:digest(args.root/n) for n in names}
    payload['analysis_commit']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    payload['analysis_file_sha256']=digest(Path(__file__))
    with (args.root/'cost-diagnostic.json').open('x') as out:json.dump(payload,out,indent=2,allow_nan=False)
    print(json.dumps(dict(runs=len(payload['runs']),root_pools=len(payload['root_pools']),by_task=payload['by_task']),indent=2))
