"""Fixed two-repair baseline with cumulative observed costs, never E2E claims."""
import argparse, hashlib, json, math
from collections import Counter
from pathlib import Path
from verify_comparison_reuse_results_20260919 import verify, relation

def finite(value):
    if type(value) not in (int,float) or not math.isfinite(value) or value<0:
        raise ValueError('finite nonnegative duration')
    return value

def analyze(banks,first,second):
    verify(banks)
    for data,seeds in ((first,[501,502]),(second,[601,602])):
        if data['role']!='fresh_native_debug_draws_not_live_e2e':raise ValueError('source role')
        if [r['seed'] for r in data['rows']]!=[1,2] or [r['request_seed'] for r in data['rows']]!=seeds:raise ValueError('request matrix')
    output=[]
    for seed in (1,2):
        a,=[r for r in first['rows'] if r['seed']==seed]
        b,=[r for r in second['rows'] if r['seed']==seed]
        cache=[r for r in banks['rows'] if r['seed']==seed and r['role']=='cache']
        group,=[r for r in banks['groups'] if r['seed']==seed]
        if len(cache)!=4 or len({r['run'] for r in cache}|{a['run'],b['run']})!=1:raise ValueError('same fixed prefix')
        if a['valid'] is not False:raise ValueError('second repair requires an observed failed first repair')
        if b['valid'] is None or any(r['valid'] is None for r in cache):
            output.append(dict(seed=seed,status='UNKNOWN_NO_EFFECT_CLAIM'));continue
        if not group['prefix_matches']:
            output.append(dict(seed=seed,status='PREFIX_NOT_REPRODUCED'));continue
        if type(b['valid']) is not bool or (b['valid'] and (type(b['score']) not in (int,float) or not math.isfinite(b['score']))):raise ValueError('second outcome')
        costs=dict(first_generation=finite(a['generation_seconds']),first_execution=finite(a['wall_seconds']),
                   second_analysis_and_generation=finite(b['generation_seconds']),second_execution=finite(b['wall_seconds']))
        baseline=sum(costs.values())
        pc=sum(r['valid'] for r in cache)/4
        terminal=[r if r['valid'] else b for r in cache]
        one=Counter(relation(r,b) for r in cache)
        final=Counter(relation(r,b) for r in terminal)
        path_times=[finite(r['wall_seconds'])+(baseline if not r['valid'] else 0) for r in cache]
        ec=sum(finite(r['wall_seconds']) for r in cache)/4
        output.append(dict(seed=seed,status='COMPLETE_EXPLORATORY_DEPTH2_CONTRAST',
            debug_chain_valid=b['valid'],debug_chain_score=b['score'],cache_single_valid_probability=pc,
            single_cache_vs_depth2={k:one[k] for k in ('wins','ties','losses')},
            cache_then_same_depth2_terminal={k:final[k] for k in ('wins','ties','losses')},
            cumulative_observed_debug_cost_seconds=costs,
            fixed_trace_latency_diagnostic=dict(debug_chain_seconds=baseline,mean_cache_seconds=ec,
                mean_cache_then_same_chain_seconds=sum(path_times)/4,
                baseline_minus_cache_chain_seconds=baseline-sum(path_times)/4,
                max_additional_cache_analysis_seconds_before_replay_gain=pc*baseline-ec,
                limitation='Fixed-code replay algebra only. Cache analysis/acceptance, changed prompts, queue contention, global cutoffs and GPU opportunity costs are not observed. The extra-analysis margin is not a measured speedup.'),
            terminal_valid_probability=sum(r['valid'] for r in terminal)/4,
            originals_are_independent_prefixes=1))
    return dict(role='cumulative_two_repair_sensitivity_not_e2e',groups=output,
        jobs=dict(banks=banks['job'],first_generation=first['generation_job'],first_execution=first['job'],
                  second_generation=second['generation_job'],second_execution=second['job']),
        generation_and_execution_gpu_hours=finite(first['total_gpu_hours'])+finite(second['total_gpu_hours']),
        caveat='Two existing development prefixes. Second repairs were commissioned after first repairs failed; no independent confirmation or deployment acceptance claim. All failed work retained in cumulative cost.')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('banks',type=Path);parser.add_argument('first',type=Path);parser.add_argument('second',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
    raw={name:getattr(args,name).read_bytes() for name in ('banks','first','second')}
    result=analyze(*(json.loads(raw[name]) for name in ('banks','first','second')))
    result['source_sha256']={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
    with args.output.open('x',encoding='utf-8') as handle:json.dump(result,handle,indent=2);handle.write('\n')
    print(json.dumps(result,indent=2))
