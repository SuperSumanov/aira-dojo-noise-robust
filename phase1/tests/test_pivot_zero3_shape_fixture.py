import pytest
from phase1.pivot_zero3_shape_fixture import fixture,summary,encoded,CONTEXT
from phase1.global_local_execution_plan import PlanError


def test_exact_full_length_shape_and_same_endpoints():
    p,pools,encode,truth=fixture()
    assert p.steps==2 and p.planned_valid_tokens==8388608
    assert sum(b.padded_slots for b in p.batches)==8388608
    assert [(s.source,s.pair_visits) for s in p.segments]==[('G',128),('L',128)]
    support=lambda rows:{e.card_id for r in rows for e in (r.a,r.b)}
    assert support(pools[0])==support(pools[1]) and len(support(pools[0]))==256
    assert {r.key for r in pools[0]}.isdisjoint({r.key for r in pools[1]})
    assert all(e.valid_tokens==16384 for rows in pools for r in rows for e in (r.a,r.b))
    assert all(len(b.rows)==8 and b.update_real_pairs==128 for b in p.batches)
    assert set(truth)=={r.key for rows in pools for r in rows}
    assert summary()['fit_or_source_admission'] is False


def test_plan_is_repeatable_and_not_real_tokenizer_binding():
    a=summary();b=summary()
    assert a==b and a['classification']=='SYNTHETIC_MAX_LENGTH_SHAPE_PLAN_NOT_REAL_TOKENIZATION'


@pytest.mark.parametrize('context,identity',[('bad','synthetic:pivot:000'),(CONTEXT,'real-card'),
    (CONTEXT,'synthetic:pivot:256'),(CONTEXT,'synthetic:pivot:0'),(CONTEXT,'synthetic:pivot:abc')])
def test_does_not_accept_real_or_unknown_inputs(context,identity):
    with pytest.raises(PlanError):encoded(context,identity)
