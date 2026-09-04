import pytest
from phase1.historical_label_reuse_cost_source import costs, length_map, annotate


def test_cached_cost_pair_sum_equals_exposure_sum():
    c=costs([('a','b'),('b','c')],[('a','c')],dict(a=3,b=5,c=7))
    assert c['local_once_valid_tokens']==20
    assert c['reuse_global_once_valid_tokens']==10
    assert c['hypothetical_reuse_then_local_tokens']==30
    assert c['unique_endpoints']==3 and c['new_endpoints_over_local']==0
    assert not c['new_budget_adopted'] and not c['equal_gpu_time_or_equal_effect_claimed']


def test_cached_length_indices_and_limit():
    rows=[dict(ordinal=str(i),raw_tokens=str(n),valid_tokens=str(min(n,16384)),encoding_sha256='a'*64)
          for i,n in enumerate([17000,200])]
    assert length_map([('a','b')],rows)==dict(a=16384,b=200)
    with pytest.raises(ValueError): length_map([('a','b')],list(reversed(rows)))
    rows[0]['valid_tokens']='17000'
    with pytest.raises(ValueError): length_map([('a','b')],rows)


def test_all_source_config_cells_remain_visible():
    cards={'a':('r1','t1','c1',(True,)*4),'b':('r2','t1','c1',(True,)*4),
           'c':('r3','t1','c2',(True,)*4),'d':('r4','t1','c1',(True,)*4),
           'e':('r5','t1','c2',(True,)*4)}
    batches={r:('t1','unique' if r in ('r1','r2','r3') else 'ambiguous','sha') for r in ('r1','r2','r3','r4','r5')}
    result=annotate([('a','b'),('a','c'),('a','d'),('a','e')],cards,batches)
    assert len(result)==4 and all(v['pairs']==1 for v in result.values())
    assert all(v['tasks']==1 for v in result.values())
