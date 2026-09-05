from copy import deepcopy
import pytest
from phase1.global_local_training_inputs import prepare_training_inputs
from phase1.global_local_execution_plan import BatchShape,EncoderBinding,PlanError
from phase1.global_local_batch_adapter import pack_batch,observe_batch


class Tokenizer:
    def __call__(self,text,*,add_special_tokens):
        assert not add_special_tokens
        return {'input_ids':[1,2,3,4]}


def inputs():
    cards=[{'endpoint_id':f'card{i}','code':f'x={i}','task_name':'A' if i<4 else 'B'} for i in range(8)]
    g=[('card0','card2'),('card1','card3'),('card4','card6'),('card5','card7')]
    l=[('card0','card1'),('card2','card3'),('card4','card5'),('card6','card7')]
    return cards,g,l


def prepare(args):
    return prepare_training_inputs(*args,Tokenizer(),encoder=EncoderBinding('a'*64,'b'*64,8),protocol_sha256='c'*64)


@pytest.mark.parametrize('arm',['L1','Lbudget','Gbudget','G_to_L','Ghash_to_L'])
def test_encoder_plan_batch_consumption(arm):
    prepared=prepare(inputs());plan=prepared.plan(arm,6,BatchShape(2,1,1))
    keys=prepared.required_label_keys(plan)
    labels={r.key:r.a.card_id for pool in prepared.pools for r in pool if r.key in keys}
    truth=prepared.true_sign_provider(labels,plan=plan)
    tokens=0
    for batch in plan.batches:
        packed=pack_batch(plan,batch,prepared.encoding_provider,truth,pad_id=0)
        seen=observe_batch(plan,batch,packed,truth,pad_id=0)
        tokens+=seen.valid_tokens
    assert tokens==plan.planned_valid_tokens


def test_order_and_orientation_do_not_change_inputs_or_plan():
    cards,g,l=inputs();a=prepare((cards,g,l))
    b=prepare((list(reversed(cards)),[tuple(reversed(x)) for x in reversed(g)],list(reversed(l))))
    assert a.projection_sha256==b.projection_sha256
    assert a.plan('G_to_L',6,BatchShape(2,1,1))==b.plan('G_to_L',6,BatchShape(2,1,1))


def test_labels_copied_after_plan_not_used_for_ordering():
    p=prepare(inputs());plan=p.plan('G_to_L',6,BatchShape(2,1,1));before=plan.sha256
    labels={r.key:r.a.card_id for pool in p.pools for r in pool}
    a=p.true_sign_provider(labels,plan=plan)
    for pool in p.pools:
        for r in pool:labels[r.key]=r.b.card_id
    b=p.true_sign_provider(labels,plan=plan)
    assert all(a(k)==1 and b(k)==-1 for k in labels)
    assert before==p.plan('G_to_L',6,BatchShape(2,1,1)).sha256


@pytest.mark.parametrize('failure',['duplicate','extra','cross_task','overlap','missing','raw_card','self_pair'])
def test_no_silent_filtering_or_raw_card_admission(failure):
    cards,g,l=deepcopy(inputs())
    if failure=='duplicate':g.append(g[0])
    elif failure=='extra':cards.append({'endpoint_id':'extra','code':'x','task_name':'A'})
    elif failure=='cross_task':g[0]=('card0','card4')
    elif failure=='overlap':g.append(l[0])
    elif failure=='missing':g[0]=('card0','absent')
    elif failure=='raw_card':cards[0]['grade']=1
    elif failure=='self_pair':g[0]=('card0','card0')
    with pytest.raises(PlanError):prepare((cards,g,l))


def test_unknown_label_or_encoding_cannot_be_looked_up():
    p=prepare(inputs())
    plan=p.plan('G_to_L',6,BatchShape(2,1,1))
    with pytest.raises(PlanError):p.encoding_provider('c'*64,'absent')
    with pytest.raises(PlanError):p.true_sign_provider({},plan=plan)
    labels={r.key:r.a.card_id for pool in p.pools for r in pool}
    lookup=p.true_sign_provider(labels,plan=plan)
    with pytest.raises(PlanError):lookup('absent')
    labels[next(iter(labels))]='absent'
    with pytest.raises(PlanError):p.true_sign_provider(labels,plan=plan)


@pytest.mark.parametrize('arm,sources',[('L1',{'L'}),('Lbudget',{'L'}),('Gbudget',{'G'}),
    ('G_to_L',{'G','L'}),('Ghash_to_L',{'L'})])
def test_only_needed_true_label_sources_are_admitted(arm,sources):
    p=prepare(inputs());plan=p.plan(arm,6,BatchShape(2,1,1))
    rows={r.key:r for pool in p.pools for r in pool}
    keys=p.required_label_keys(plan)
    assert {rows[k].source for k in keys}==sources
    labels={k:rows[k].a.card_id for k in keys}
    truth=p.true_sign_provider(labels,plan=plan)
    for k in set(rows)-set(keys):
        with pytest.raises(PlanError):truth(k)
    extras=set(rows)-set(keys)
    if extras:
        labels[next(iter(extras))]=object()
        with pytest.raises(PlanError,match='training_label_support_mismatch'):
            p.true_sign_provider(labels,plan=plan)


def test_plan_from_another_projection_rejected():
    p=prepare(inputs());cards,g,l=inputs();cards[0]['task_name']=cards[1]['task_name']=cards[2]['task_name']=cards[3]['task_name']='changed'
    other=prepare((cards,g,l));plan=other.plan('G_to_L',6,BatchShape(2,1,1))
    with pytest.raises(PlanError):p.required_label_keys(plan)


def test_bad_card_identity_is_fixed_reason_error():
    cards,g,l=inputs();cards[0]['endpoint_id']=[]
    with pytest.raises(PlanError,match='training_card_identity'):prepare((cards,g,l))
