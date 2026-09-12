import copy
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from summarize_forets_context_repetition_20260912 import combine,SPECS
from verify_forets_context_e2e_20260912 import complete_pair_outcomes


def blocks():
    result=[]
    for seed,job,_,tree in SPECS:
        rows=[];cost=[]
        for task in ('leaf-classification','spaceship-titanic'):
            for arm in ('uniform_random','critic_topk_random'):
                score=.6 if arm=='uniform_random' else .5
                if seed==15 and task=='spaceship-titanic' and arm=='uniform_random':score=None
                rid=f'{seed}-{task}-{arm}'
                rows.append(dict(run_id=rid,seed=seed,task=task,arm=arm,comparable_final=score is not None,official_final_score=score))
                cost.append(dict(run_id=rid,seed=seed,task=task,arm=arm,api_calls=10,settled_api_cost_usd=.01,
                    unresolved_api_calls=0,task_calls=5,execution_timeout_seconds=300,step_limit=6,worker_wall_cap_seconds=3540))
        result.append((dict(seed=seed,job=job,source_tree=tree,verification='passed',rows=rows,
            pairs=complete_pair_outcomes(rows),allocation_gpu_hours=1),dict(runs=cost,
            billing=dict(new_api_calls=42,new_settled_usd='0.0401'))))
    return result


def test_full_matrix_missingness_and_task_specific_scores():
    answer=combine(blocks());leaf,space=answer['task_summaries']
    assert leaf['comparable_seed_pairs']==2 and leaf['median_conditional_benefit']=='0.1'
    assert space['comparable_seed_pairs']==1 and space['median_conditional_benefit']=='-0.1'
    assert space['sample_std_conditional_benefit'] is None
    assert len(answer['rows'])==8 and len(answer['pairs'])==4
    missing=[p for p in answer['pairs'] if p['availability']=='critic_only_valid']
    assert len(missing)==1 and missing[0]['conditional_benefit_delta'] is None


def test_wrong_family_seed_subset_or_imputation_rejected():
    for mutation in ('subset','wrong_seed','wrong_source','imputed','cost_binding'):
        data=copy.deepcopy(blocks())
        if mutation=='subset':data.pop()
        if mutation=='wrong_seed':data[0][0]['seed']=13
        if mutation=='wrong_source':data[0][0]['source_tree']='old-8b'
        if mutation=='imputed':data[1][0]['pairs'][1]['conditional_benefit_delta']='0.5'
        if mutation=='cost_binding':data[0][1]['runs'][0]['seed']=0
        with pytest.raises(ValueError):combine(data)
