import copy
import pytest
from phase1.forets_seed_pair_report_20260912 import aggregate,BINDINGS,TASKS


def fixtures():
    blocks=[]
    for seed,(job,tree) in BINDINGS.items():
        rows=[]
        for task in TASKS:
            for arm in ('uniform_random','critic_topk_random'):
                rows.append(dict(seed=seed,task=task,arm=arm,comparable_final=True,
                    external_final_score=.4 if arm=='uniform_random' else .5))
        blocks.append(dict(job=job,source_tree=tree,verification='selected-node/external-grade consistency passed',rows=rows))
    return blocks


def test_opposite_metric_directions_and_variance():
    result=aggregate(fixtures())
    assert result['tasks'][0]['conditional_median_improvement']=='-0.1'
    assert result['tasks'][1]['conditional_median_improvement']=='0.1'
    assert result['tasks'][0]['conditional_sample_variance']=='0'


def test_missing_is_visible_and_not_a_zero_or_tie():
    blocks=fixtures()
    for row in blocks[0]['rows'][:2]:row.update(comparable_final=False,external_final_score=None)
    result=aggregate(blocks)
    assert result['pairs'][0]['status']=='neither_valid'
    assert result['pairs'][0]['signed_critic_improvement'] is None
    assert result['tasks'][0]['comparable_seed_pairs']==1
    assert result['tasks'][0]['conditional_sample_variance'] is None


@pytest.mark.parametrize('change',['incomplete','duplicate','missing_zero','unverified','bad_tree','mixed_seeds'])
def test_invalid_receipts_rejected(change):
    blocks=fixtures()
    if change=='incomplete':blocks.pop()
    if change=='duplicate':blocks[1]=copy.deepcopy(blocks[0])
    if change=='missing_zero':blocks[0]['rows'][0].update(comparable_final=False,external_final_score=0)
    if change=='unverified':blocks[0]['verification']='pending'
    if change=='bad_tree':blocks[0]['source_tree']='a'*40
    if change=='mixed_seeds':blocks[0]['rows'][0]['seed']=12
    with pytest.raises(ValueError):aggregate(blocks)
