"""Post-hoc finite-pool feasibility ceiling and transparent cost sensitivity.

Uses ONLY the already published 24-program development ZIP. Does not implement
an oracle selector or inspect/change the new wallclock experiment. The cost
formula is a conditional model, not a measured e2e reward or latency estimate.
"""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import zipfile

ZIP_SHA='dc99104b0faf0d175b9dac7be5fd54aaf02037f2b7268e974571a15afc8322b4'


def pool_bounds(programs, selected, lower_is_better):
    if len(programs)!=4 or len(selected)!=2 or len(set(selected))!=2 or not set(selected)<=set(range(4)):
        raise ValueError('fixed four-candidate/top2 contract')
    for r in programs:
        if type(r['valid']) is not bool or not math.isfinite(r['seconds']) or r['seconds']<0:
            raise ValueError('validity/time schema')
        if r['valid']:
            if type(r['score']) not in (int,float) or not math.isfinite(r['score']):raise ValueError('valid score')
        elif r['score'] is not None:raise ValueError('no missing imputation')
    valid=sum(r['valid'] for r in programs);selected_valid=sum(programs[i]['valid'] for i in selected)
    subsets=list(itertools.combinations(range(4),2))
    max_valid=max(sum(programs[i]['valid'] for i in sub) for sub in subsets)
    if max_valid!=min(2,valid):raise AssertionError('analytic/exhaustive bound mismatch')
    admissible=[sub for sub in subsets if sum(programs[i]['valid'] for i in sub)==max_valid]
    means=[sum(programs[i]['score'] for i in sub if programs[i]['valid'])/max_valid for sub in admissible] if max_valid else []
    optimal=(min(means) if lower_is_better else max(means)) if means else None
    chosen_mean=sum(programs[i]['score'] for i in selected if programs[i]['valid'])/selected_valid if selected_valid else None
    pu=valid/4;pc=selected_valid/2
    tu=sum(r['seconds'] for r in programs)/4;tc=sum(programs[i]['seconds'] for i in selected)/2
    # Under explicitly hypothetical stationary independent repetitions:
    # (G+R+tc)/pc <= (G+tu)/pu iff R <= (pc/pu-1)*G + (pc/pu)*tu-tc.
    # G and R are UNMEASURED generation/ranking seconds, not file timestamps.
    ratio=pc/pu if pu and pc else None
    return dict(pool_valid=valid,selected_valid=selected_valid,max_top2_valid=max_valid,
        attained_feasibility_ceiling=selected_valid==max_valid,
        homogeneous_pool=valid in (0,4),uniform_valid_probability=pu,selected_valid_probability=pc,
        selected_conditional_score=chosen_mean,conditional_score_bound_at_max_validity=optimal,
        quality_regret_to_bound=(chosen_mean-optimal if lower_is_better else optimal-chosen_mean)
            if selected_valid==max_valid and chosen_mean is not None else None,
        mean_uniform_program_seconds=tu,mean_selected_program_seconds=tc,
        break_even_rank_seconds_G_coefficient=ratio-1 if ratio is not None else None,
        break_even_rank_seconds_intercept=ratio*tu-tc if ratio is not None else None)


def analyze(path):
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=ZIP_SHA:raise ValueError('published development ZIP changed')
    with zipfile.ZipFile(path) as archive:
        programs=json.loads(archive.read('programs.json'));pools=json.loads(archive.read('blind-pools.json'))
    if len(programs)!=24 or len(pools)!=4:raise ValueError('whole published evidence required')
    results=[]
    for pool in pools:
        candidates=sorted((r for r in programs if (r['batch'],r['task'])==(pool['batch'],pool['task'])),key=lambda r:r['index'])
        normalized=[]
        for r in candidates:
            if r['valid'] not in ('True','False'):raise ValueError('original CSV bool')
            normalized.append(dict(valid=r['valid']=='True',score=float(r['score']) if r['valid']=='True' else None,
                seconds=float(r['execution_seconds'])))
        bound=pool_bounds(normalized,pool['blind_borda_top2']['slots'],pool['task']=='leaf-classification')
        if bound['pool_valid']!=pool['uniform4']['valid'] or bound['selected_valid']!=pool['blind_borda_top2']['valid']:
            raise ValueError('published pool and per-program evidence differ')
        results.append(dict(batch=pool['batch'],task=pool['task'],**bound))
    return dict(role='posthoc_development_diagnostic_not_new_experiment',source_zip_sha256=ZIP_SHA,rows=results,
        observed_selected_valid=sum(r['selected_valid'] for r in results),
        maximum_selected_valid=sum(r['max_top2_valid'] for r in results),
        discriminating_pools=sum(not r['homogeneous_pool'] for r in results),
        unmeasured_variables=['common candidate generation latency G','two-order rank latency R'],
        limitation='Label-aware bounds describe only these four revealed pools. Conditional stationary-repeat cost model is unverified. No e2e, causal method or generalization claim.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('zip',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    result=analyze(a.zip)
    with a.output.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False)
    print(json.dumps(result))
