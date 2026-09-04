import pytest
from phase1.global_local_execution_plan import BatchShape, EncoderBinding, Endpoint, Pair, digest_records
from phase1.historical_reuse_execution_readiness import cached_endpoints, project_reuse, plan_matrix


def test_cache_order_lengths_and_encoding_digests():
    rows=[dict(ordinal=str(i), raw_tokens=str(n), valid_tokens=str(min(n,16384)), encoding_sha256='a'*64)
          for i,n in enumerate((4,17000))]
    assert cached_endpoints([('a','b')],rows)['b'].valid_tokens == 16384
    with pytest.raises(ValueError): cached_endpoints([('a','b')],rows[::-1])
    rows[0]['encoding_sha256']='not_a_digest'
    with pytest.raises(ValueError): cached_endpoints([('a','b')],rows)


def test_reuse_definition_preserves_duplicates_as_failure_and_all_tasks():
    l=[('a','b'),('b','c'),('d','e')]
    g=[('a','c'),('a','x'),('a','d'),('a','b')]
    tasks=dict(a='t',b='t',c='t',d='u',e='u',x='t')
    assert project_reuse(l,g,tasks)==(('a','c'),)
    assert project_reuse(l[::-1],g[::-1],tasks)==(('a','c'),)
    with pytest.raises(ValueError): project_reuse(l,g+g,tasks)


def test_full_matrix_retains_L1_and_only_accounts_hypothetical_savings():
    endpoints=[Endpoint(str(i).zfill(3),4,'a'*64) for i in range(32)]
    l=tuple(Pair.canonical('L', endpoints[i], endpoints[i+1], 'c'*64) for i in range(0,32,2))
    g=tuple(Pair.canonical('G', endpoints[i], endpoints[(i+2)%32], 'c'*64) for i in range(0,32,2))
    result=plan_matrix(g,l,EncoderBinding('a'*64,'b'*64,16384),'d'*64,
                       [BatchShape(2,8,8),BatchShape(4,8,4)],[6,7,8])
    assert len(result['plans'])==len(result['independent_replays'])==30
    assert len(result['cross_arm_relations'])==len(result['hypothetical_prefix_savings'])==6
    for row in result['plans']:
        assert row['status']=='HYPOTHETICAL_REUSE_PLAN_NOT_ADOPTED'
        assert not row['training_authorized']
    for row in result['hypothetical_prefix_savings']:
        assert row['evaluation_cells_kept']==5
        assert row['hypothetical_shared_streams']==4
        assert row['five_separate_streams_valid_tokens']-row['four_prefix_shared_streams_valid_tokens']==128
        assert not row['actual_model_state_equivalence_verified']
        assert row['actual_saved_GPU_hours'] is None
