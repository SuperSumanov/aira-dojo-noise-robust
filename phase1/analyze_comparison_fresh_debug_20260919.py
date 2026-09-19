"""Compare every new draw to its fixed cache bank, not best-of-responses."""
import argparse,hashlib,json,math
from pathlib import Path
from readout_comparison_reuse_20260919 import compare
from verify_comparison_reuse_results_20260919 import enumerate_paths,close,verify


def analyze(banks,fresh):
    verify(banks)
    if fresh['role']!='fresh_native_debug_draws_not_live_e2e':raise ValueError('fresh source role')
    if sorted(r['seed'] for r in fresh['rows'])!=[1,2] or sorted(r['request_seed'] for r in fresh['rows'])!=[501,502]:raise ValueError('fixed two draws')
    out=[]
    for seed in (1,2):
        original=[r for r in banks['rows'] if r['seed']==seed]
        new,=[r for r in fresh['rows'] if r['seed']==seed]
        group,=[g for g in banks['groups'] if g['seed']==seed]
        if len({r['run'] for r in original}|{new['run']})!=1:raise ValueError('prefix run identity')
        records=[r if r['role']!='debug' else dict(new,role='debug') for r in original]
        result=compare(records,group['prefix_matches'])
        result.update(seed=seed,request_seed=new['request_seed'],generation_status=new['generation_status'],
                      generation_seconds=new['generation_seconds'],historical_debug_result_retained_separately=True,
                      caveat='One new native debug draw for each of two fixed exploratory prefixes. Neither independent cache alternatives nor a live same-budget E2E comparison.')
        if result['status']=='COMPLETE_EXPLORATORY_CONTINUATION_BANK':
            # Independent enumeration, not another invocation of producer math.
            e=enumerate_paths(records);g=new['generation_seconds']
            if not math.isfinite(g) or g<0:raise ValueError('fresh generation time')
            close(result['cache_valid_probability'],e['pc'])
            if result['one_action_cache_vs_debug']!=dict(e['one'],alternatives=4):raise ValueError('independent contrast mismatch')
            symbolic=result['symbolic_cache_first_then_debug']
            close(symbolic['expected_latency_intercept_seconds'],e['intercept'])
            close(symbolic['expected_latency_generation_coefficient'],e['slope'])
            times=[float(path['intercept'])+path['generation_count']*g for path in e['paths']]
            baseline=float(e['debug_time'])+g
            result['plug_in_latency_not_live_policy']=dict(
                baseline_seconds=baseline,mean_cache_first_seconds=sum(times)/4,
                mean_seconds_difference_baseline_minus_cache_first=baseline-sum(times)/4,
                caveat='Fresh measured generation latency inserted into a fixed-code replay formula. Does not include analysis calls, changed continuation prompts, global budget censoring or service opportunity costs. Not E2E speedup.')
        out.append(result)
    return dict(role='exploratory_fresh_response_sensitivity_not_e2e',groups=out,
                source_banks_jobs=banks['job'],fresh_generation_job=fresh['generation_job'],fresh_execution_job=fresh['job'],
                caveat='Every planned new response retained; no successful-response selection. Two original prefixes, not four independent trials.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('banks',type=Path);parser.add_argument('fresh',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
    b=args.banks.read_bytes();f=args.fresh.read_bytes();result=analyze(json.loads(b),json.loads(f))
    result['source_sha256']=dict(banks=hashlib.sha256(b).hexdigest(),fresh=hashlib.sha256(f).hexdigest())
    with args.output.open('x',encoding='utf-8') as handle:json.dump(result,handle,indent=2);handle.write('\n')
    print(json.dumps(result,indent=2))
