"""Unmodified improve_op AST with synthetic objects; not whole-Dojo integration.

The formatting dependency is a synthetic stub here. Tests make no claim about
real provider routing, prompt-template resource correctness, timeout accounting
or actual MLE execution. They exercise the real operator's query construction.
"""
import ast,hashlib,json,os,random,subprocess
from pathlib import Path
from types import SimpleNamespace as N
from typing import Callable,Optional
from copy import deepcopy
from phase1.frozen_candidate_requests import capture_improve_batch,GenerationOnlyBatch

ROOT=Path(os.environ.get('FROZEN_REQUEST_REFERENCE_REPO', Path(__file__).resolve().parents[2]))
PATH='src/dojo/core/solvers/operators/improve.py'


def real_operator():
    # Pin to the repository blob, independent of Windows checkout newlines.
    raw=subprocess.check_output(['git','show','ef19d100ac6cb1a747c332eb1b8596051f47a695:'+PATH],cwd=ROOT)
    expected='b0b9bc561f26682ce84701287bd3c92a57b58ed37d2664a31eae4b56c5aab5e0'
    assert hashlib.sha256(raw).hexdigest()==expected
    nodes=[n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name=='improve_op']
    assert len(nodes)==1
    ns={'random':random,'Callable':Callable,'Optional':Optional,'GenericLLM':object,'DictConfig':object,
        'Journal':object,'Node':object,'Complexity':object,
        'humanize':N(naturaldelta=lambda n:f'synthetic-duration:{n}'),
        'wrap_code':lambda s,lang='python':f'```{lang}\n{s}\n```'}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),PATH,'exec'),ns)
    return ns['improve_op'],expected


def state():
    return {'cfg':N(available_packages=['numpy','torch','pandas'],execution_timeout=1200,step_limit=20,data_preview=True),
        'memory_op':lambda journal,node:';'.join(journal), 'task_description':'synthetic task',
        'journal':['past result'], 'input_node':N(code='print(1)',term_out='past stdout'),
        'step_count':5,'remaining_time':3600,'complexity':N(value='simple'),'data_preview':'synthetic schema'}


def test_existing_operator_requests_match_frozen_reference_per_slot():
    op,sha=real_operator();s=state();seeds=[6,7,8];reference=[];rng=random.getstate()
    try:
        for seed in seeds:
            random.seed(seed)
            def capture(**kwargs):reference.append(deepcopy(kwargs));return 'captured'
            assert op(improve_llm=capture,**deepcopy(s))=='captured'
    finally:random.setstate(rng)
    batch=capture_improve_batch(operator=op,operator_kwargs=s,render_system=lambda **kw:json.dumps(kw,sort_keys=True),
        generation_kwargs={'temperature':0.7},slot_seeds=seeds,state_sha256='a'*64,operator_sha256=sha,generator_contract_sha256='c'*64)
    for r,want in zip(batch.requests,reference):
        actual=json.loads(json.loads(r.wire_json)['messages'][0]['content'])
        assert actual==want['query_data']
        assert actual['execution_timeout']=='synthetic-duration:1200'
    assert s['cfg'].available_packages==['numpy','torch','pandas']


def test_real_operator_no_cross_slot_feedback_and_all_render_before_query():
    op,sha=real_operator();s=state();order=[]
    def render(**kw):order.append('render');return json.dumps(kw,sort_keys=True)
    batch=capture_improve_batch(operator=op,operator_kwargs=s,render_system=render,generation_kwargs={},
        slot_seeds=[6,7,8],state_sha256='a'*64,operator_sha256=sha,generator_contract_sha256='c'*64)
    def query(messages,**kw):
        order.append('query');s['journal'].append('FORBIDDEN_SAME_BATCH_FEEDBACK')
        assert 'FORBIDDEN' not in messages[0]['content']
        return 'synthetic output',{}
    GenerationOnlyBatch(batch,durable_event=lambda e:None).generate(query=query)
    assert order==['render']*3+['query']*3
