from phase1.scripts.validate_training_input_session_cpu_20260905 import prepared_fixture,projected_fixture
from phase1.global_local_batch_adapter import pack_batch,observe_batch


def test_projection_fixture_reaches_four_updates_without_model():
    cards,g,l,_=projected_fixture()
    assert len(cards)==48 and len(g)==11 and len(l)==13
    plans=[]
    for arm in ('G_to_L','Ghash_to_L'):
        plan,pools,encoded,truth=prepared_fixture(arm)
        assert plan.steps==4 and plan.planned_valid_tokens==384
        count=0
        for batch in plan.batches:
            value=pack_batch(plan,batch,encoded,truth,pad_id=0)
            count+=observe_batch(plan,batch,value,truth,pad_id=0).valid_tokens
        assert count==384;plans.append(plan)
    assert plans[0].input_sha256==plans[1].input_sha256
