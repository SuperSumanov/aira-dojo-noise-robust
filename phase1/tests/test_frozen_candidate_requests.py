from copy import deepcopy
import hashlib,json,random
from types import SimpleNamespace as N
import pytest
from phase1.frozen_candidate_requests import FrozenRequestError,GenerationOnlyBatch,capture_improve_batch,canonical,wire


def operator(*,improve_llm,cfg,journal,input_node,remaining_time):
    random.shuffle(cfg.available_packages)
    return improve_llm(query_data={'memory': '|'.join(journal), 'parent': input_node.code,
        'packages':list(cfg.available_packages),'remaining_time':remaining_time},no_user_message=True)


def fixture(op=operator):
    state={'cfg':N(available_packages=['numpy','torch','pandas']), 'journal':['past feedback only'],
           'input_node':N(code='old parent'), 'remaining_time':3600}
    settings={'temperature':0.7,'max_tokens':4096}
    batch=capture_improve_batch(operator=op,operator_kwargs=state,render_system=lambda **x:canonical(x),
        generation_kwargs=settings,slot_seeds=[6,7,8],state_sha256='a'*64,operator_sha256='b'*64,generator_contract_sha256='c'*64)
    return batch,state,settings


def test_all_requests_frozen_before_client_or_execution_feedback():
    batch,state,settings=fixture();calls=[];events=[]
    state['journal'].append('same batch execution result MUST NOT APPEAR')
    state['input_node'].code='mutated parent';settings['temperature']=99
    def query(messages,**kwargs):
        calls.append(deepcopy((messages,kwargs)))
        state['journal'].append('candidate generation output MUST NOT APPEAR')
        messages[0]['content']='client mutation'
        return 'synthetic response',{'calls':1}
    run=GenerationOnlyBatch(batch,durable_event=events.append);out=run.generate(query=query)
    assert len(out)==3 and run.completed
    assert all('MUST NOT APPEAR' not in m[0]['content'] and 'old parent' in m[0]['content'] for m,k in calls)
    assert all(k['temperature']==0.7 and k['json_schema'] is None for m,k in calls)
    assert events[0]['event']=='BATCH_LOCKED' and events[-1]['event']=='BATCH_GENERATED'
    assert [e['event'] for e in events]==['BATCH_LOCKED']+['GENERATION_INTENT','GENERATION_RETURNED']*3+['BATCH_GENERATED']
    with pytest.raises(FrozenRequestError,match='already_attempted'):run.generate(query=query)


def test_live_config_and_python_rng_unchanged():
    random.seed(291);before=random.getstate()
    batch,state,_=fixture()
    assert state['cfg'].available_packages==['numpy','torch','pandas'] and random.getstate()==before
    assert batch.sha256==fixture()[0].sha256


def test_prepare_failure_restores_rng_and_makes_no_batch():
    before=random.getstate()
    def bad(**kwargs):random.random();raise RuntimeError('render failed')
    with pytest.raises(RuntimeError,match='render failed'):fixture(bad)
    assert random.getstate()==before


def test_network_or_durable_sink_failure_is_not_retried():
    batch,_,_=fixture();calls=[]
    def bad_query(*args,**kwargs):calls.append(1);raise OSError('unknown remote completion')
    r=GenerationOnlyBatch(batch,durable_event=lambda event:None)
    with pytest.raises(OSError):r.generate(query=bad_query)
    with pytest.raises(FrozenRequestError):r.generate(query=bad_query)
    assert calls==[1] and not r.completed
    def bad_sink(event):raise OSError('disk unavailable')
    r=GenerationOnlyBatch(batch,durable_event=bad_sink)
    with pytest.raises(OSError):r.generate(query=bad_query)
    assert calls==[1]


def test_copies_preserve_parent_journal_relationships():
    parent=N(code='parent');state={'journal':[parent],'input_node':parent,'cfg':None,'remaining_time':1}
    def op(**kwargs):
        assert kwargs['journal'][0] is kwargs['input_node']
        kwargs['input_node'].code='slot mutation'
        return kwargs['improve_llm'](query_data={'text':'synthetic'},no_user_message=True)
    capture_improve_batch(operator=op,operator_kwargs=state,render_system=lambda **x:canonical(x),generation_kwargs={},
        slot_seeds=[6,7],state_sha256='a'*64,operator_sha256='b'*64,generator_contract_sha256='c'*64)
    assert parent.code=='parent'


@pytest.mark.parametrize('bad',[{'api_key':'placeholder'},{'messages':[]},{'temperature':float('nan')}])
def test_credentials_routing_and_nan_forbidden(bad):
    with pytest.raises(FrozenRequestError):wire([{'role':'system','content':'synthetic'}],bad)


def test_shareable_receipts_do_not_contain_prompt_or_response():
    batch,_,_=fixture();r=canonical(batch.receipt())
    assert 'past feedback only' not in r and 'old parent' not in r
    assert len(batch.sha256)==64


def test_invalid_later_slot_fails_before_any_client_call():
    from dataclasses import replace
    batch,_,_=fixture();requests=list(batch.requests);requests[1]=replace(requests[1],wire_json='not json')
    events=[]
    with pytest.raises(FrozenRequestError,match='invalid_frozen_wire'):
        GenerationOnlyBatch(replace(batch,requests=tuple(requests)),durable_event=events.append)
    assert events==[]


@pytest.mark.parametrize('kwargs',[{'n':2},{'n':True},{'extra_body':{}},{'max_tokens':0},
    {'max_tokens':16,'max_completion_tokens':16}])
def test_unreviewed_or_multi_generation_options_fail(kwargs):
    with pytest.raises(FrozenRequestError):wire([{'role':'system','content':'synthetic'}],kwargs)


@pytest.mark.parametrize('kwargs',[{'temperature':True},{'temperature':3},{'top_p':0},{'top_p':1.1},
    {'presence_penalty':-3},{'frequency_penalty':'0'},{'seed':True},{'seed':-1},{'stop':[]},
    {'stop':['a',None]},{'stop':['a']*5},{'stop':''}])
def test_decoding_options_have_explicit_types_and_ranges(kwargs):
    with pytest.raises(FrozenRequestError):wire([{'role':'system','content':'synthetic'}],kwargs)


def test_invalid_binding_seed_and_sink_rejected_before_events():
    from dataclasses import replace
    batch,_,_=fixture()
    for invalid in (replace(batch,state_sha256='not a binding'),
                    replace(batch,requests=(batch.requests[0],replace(batch.requests[1],preparation_seed=6))),
                    replace(batch,requests=(batch.requests[0],replace(batch.requests[1],preparation_seed=[])))):
        with pytest.raises(FrozenRequestError):GenerationOnlyBatch(invalid,durable_event=lambda e:None)
    with pytest.raises(FrozenRequestError):GenerationOnlyBatch(batch,durable_event=None)
