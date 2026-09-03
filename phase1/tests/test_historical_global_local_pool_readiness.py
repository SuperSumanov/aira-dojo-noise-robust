import json
import pytest
from phase1.historical_global_local_pool_readiness import project_pairs,summarize


def test_projection_is_outcome_and_orientation_independent():
    a={'better':'a','worse':'b','intask_split':'train','gap_raw':1}
    b=dict(a,better='b',worse='a',gap_raw=-100)
    assert project_pairs(json.dumps(a))==project_pairs(json.dumps(b))
    with pytest.raises(ValueError): project_pairs(json.dumps(dict(a,intask_split='test')))


def test_exhaustive_partition_and_shared_endpoints():
    runs=dict(a='r1',b='r1',c='r1',d='r2',e='r1')
    tasks=dict(a='t',b='t',c='t',d='t',e='other')
    g=[('a','b'),('a','c'),('a','c'),('a','missing'),('a','d'),('a','e')]
    r=summarize(g,[('a','b')],runs,tasks)
    assert r['exclusive_partition_counts']=={'same_unordered_pair_as_local':1,
        'within_boundary_nonlocal_pair':2,'missing_card_identity':1,'outside_local_train_run_boundary':1,
        'cross_task_pair':1}
    assert r['partition_covers_all_rows']
    assert r['proposed_unique_global_pairs']==1 and r['proposed_repeated_unordered_rows']==1
    assert r['shared_endpoint_ids_with_local']==1 and r['proposed_additional_endpoint_ids']==1
    assert r==summarize(g[::-1],[('a','b')],runs,tasks)


def test_missing_local_endpoint_rejected():
    with pytest.raises(ValueError): summarize([('a','b')],[('a','missing')],{'a':'r'},{'a':'t'})
