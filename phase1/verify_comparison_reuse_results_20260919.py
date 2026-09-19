"""Independent path enumeration for the frozen continuation action bank.

No imports from the producer/readout or their comparison routines. This verifies
reported statistics, not the external grading or prefix logs themselves.
"""
import argparse
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path


def close(actual, expected):
    if expected is None:
        assert actual is None
    elif isinstance(expected, bool):
        assert actual is expected
    else:
        assert math.isclose(actual, float(expected), rel_tol=1e-10, abs_tol=1e-8), (actual, float(expected))


def relation(a,b):
    if a['valid'] != b['valid']:
        return 'wins' if a['valid'] else 'losses'
    if not a['valid'] or a['score'] == b['score']:
        return 'ties'
    return 'wins' if a['score'] < b['score'] else 'losses'


def enumerate_paths(rows):
    debug, = [r for r in rows if r['role']=='debug']
    cache = [r for r in rows if r['role']=='cache']
    assert len(cache)==4
    one={k:0 for k in ('wins','ties','losses')}
    terminal={k:0 for k in one}
    paths=[]
    for candidate in cache:
        final=candidate if candidate['valid'] else debug
        one[relation(candidate,debug)]+=1
        terminal[relation(final,debug)]+=1
        paths.append(dict(final_valid=final['valid'],
                          executions=1+int(not candidate['valid']),
                          generation_count=int(not candidate['valid']),
                          intercept=Fraction(str(candidate['wall_seconds']))+
                          (Fraction(str(debug['wall_seconds'])) if not candidate['valid'] else 0)))
    intercept=sum(p['intercept'] for p in paths)/4
    slope=Fraction(sum(p['generation_count'] for p in paths),4)
    debug_time=Fraction(str(debug['wall_seconds']))
    threshold=(intercept-debug_time)/(1-slope) if slope!=1 else None
    return dict(one=one,terminal=terminal,paths=paths,intercept=intercept,slope=slope,
                threshold=threshold,debug_time=debug_time,
                pc=Fraction(sum(c['valid'] for c in cache),4),
                ec=sum(Fraction(str(c['wall_seconds'])) for c in cache)/4)


def verify(summary):
    assert summary['role']=='exploratory_continuation_action_bank_not_live_e2e'
    assert len(summary['rows'])==12 and len({r['index'] for r in summary['rows']})==12
    assert len({r['node'] for r in summary['rows']})==12
    assert summary['api_calls']==0
    close(summary['gpu_hours'],Fraction(summary['allocation_seconds']*summary['allocated_gpus'],3600))
    for field, status in [('valid',True),('no_valid_output',False),('unknown',None)]:
        assert summary[field]==sum(r['valid'] is status for r in summary['rows'])
    assert sorted(g['seed'] for g in summary['groups'])==[1,2]
    verified=[]
    for group in summary['groups']:
        rows=[r for r in summary['rows'] if r['seed']==group['seed']]
        assert sorted(r['role'] for r in rows)==['cache']*4+['debug','prefix']
        if any(r['valid'] is None for r in rows):
            assert group['status']=='UNKNOWN_NO_EFFECT_CLAIM'
            verified.append(dict(seed=group['seed'],status='unknown'));continue
        for row in rows:
            assert type(row['valid']) is bool and math.isfinite(row['wall_seconds']) and row['wall_seconds']>=0
            if row['valid']:
                assert math.isfinite(row['score'])
                close(row['score'],round(row['independent_score'],5))
        prefix,=[r for r in rows if r['role']=='prefix']
        if prefix['valid'] or not group['prefix_matches']:
            assert group['status']=='PREFIX_NOT_REPRODUCED_NO_CONTINUATION_EFFECT'
            verified.append(dict(seed=group['seed'],status='prefix_not_reproduced'));continue
        assert group['status']=='COMPLETE_EXPLORATORY_CONTINUATION_BANK'
        debug,=[r for r in rows if r['role']=='debug']
        e=enumerate_paths(rows)
        close(group['debug_valid'],debug['valid']);close(group['debug_score'],debug['score'])
        close(group['cache_valid_probability'],e['pc'])
        close(group['cache_valid_probability_gain'],e['pc']-int(debug['valid']))
        assert group['one_action_cache_vs_debug']==dict(e['one'],alternatives=4)
        close(group['mean_cache_execution_seconds'],e['ec'])
        close(group['debug_execution_seconds'],e['debug_time'])
        symbolic=group['symbolic_cache_first_then_debug']
        assert symbolic['terminal_quality_vs_debug']==e['terminal']
        close(symbolic['terminal_valid_probability'],Fraction(sum(p['final_valid'] for p in e['paths']),4))
        close(symbolic['expected_latency_intercept_seconds'],e['intercept'])
        close(symbolic['expected_latency_generation_coefficient'],e['slope'])
        close(symbolic['baseline_latency_intercept_seconds'],e['debug_time'])
        close(symbolic['baseline_latency_generation_coefficient'],1)
        close(symbolic['strict_latency_gain_if_generation_seconds_greater_than'],e['threshold'])
        close(symbolic['expected_additional_executions'],e['slope'])
        for generation in (0,1,10,100,1000,10000):
            sampled=sum(p['intercept']+generation*p['generation_count'] for p in e['paths'])/4
            assert sampled==e['intercept']+e['slope']*generation
            advantage=e['debug_time']+generation-sampled
            if e['threshold'] is not None:
                assert (advantage>0)==(generation>e['threshold'])
            else:
                assert advantage<=0
        verified.append(dict(seed=group['seed'],status='verified_by_independent_path_enumeration'))
    return dict(status='PASS',groups=verified,unit='two exploratory physical runs; four cache alternatives are not seeds',
                boundary='Arithmetic verification only; no live E2E or fresh-generation claim')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('summary',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();raw=args.summary.read_bytes();result=verify(json.loads(raw))
    result['summary_sha256']=hashlib.sha256(raw).hexdigest()
    with args.output.open('x',encoding='utf-8') as handle:json.dump(result,handle,indent=2);handle.write('\n')
    print(json.dumps(result,indent=2))
