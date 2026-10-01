"""Actual native prompts -> bounded adapter -> SDK JSON -> mock HTTP; no network."""
import asyncio,json,os,sys,socket,logging
from pathlib import Path
from unittest.mock import patch
R=Path('/research/d7/spc/yzyang4/task-feedback-real-20261001-v6')
sys.path.insert(0,str(R));import task_feedback_real_20261001 as m
m.setup()
from dojo.config_dataclasses.run import RunConfig
from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
from dojo.core.solvers.operators.improve import improve_op
from dojo.core.solvers.operators.debug import debug_op
from dojo.core.solvers.utils.journal import Journal,Node
from task_feedback_facts_20261001 import feedback
from omegaconf import OmegaConf
import httpx
for name in ('openai','httpx','httpcore','LiteLLM','Backend'):logging.getLogger(name).setLevel(logging.CRITICAL)
os.environ['PRIMARY_KEY_QWEN3_8_27B']='synthetic-test-only'
cfg=RunConfig.load_from_json(R/'configs/0.json')
assert cfg.solver.step_limit==5
old=OmegaConf.structured(cfg.solver.operators['improve']).llm.generation_kwargs
try:json.dumps(dict(old));raise AssertionError('negative control should fail')
except TypeError:pass
requests=[]
async def send(self,request,**kwargs):
    body=json.loads(request.content)
    assert request.url.host=='127.0.0.1' and request.url.path.endswith('/chat/completions')
    assert body['chat_template_kwargs']=={'enable_thinking':False}
    assert body['max_tokens']==8192 and not any(k.startswith('bounded_') for k in body)
    text='\n'.join(x['content'] for x in body['messages'])
    assert 'trusted_result' in text
    requests.append({'evidence_rule':'Evidence-use rule:' in text,'diagnostics':'aggregate_diagnostics' in text})
    return httpx.Response(200,request=request,json={'id':'synthetic','object':'chat.completion','created':0,'model':'Qwen3.8-27B','choices':[{'index':0,'message':{'role':'assistant','content':'MOCK\n```python\npass\n```'},'finish_reason':'stop'}],'usage':{'prompt_tokens':2,'completion_tokens':3,'total_tokens':5}})
async def run():
    for arm in 'ABC':
        for name,operator in [('debug',debug_op),('improve',improve_op)]:
            native=GenericLLM(OmegaConf.structured(cfg.solver.operators[name]));j=Journal();n=Node(code='pass',plan='fixed synthetic goal',_term_out=['mock log']);j.append(n)
            msg,_=feedback(arm,{'valid':False},None,n.plan)
            before=len(requests)
            response,info=await operator(native,OmegaConf.structured(cfg.solver),lambda *_:msg,'synthetic task',j,n,1,100,data_preview='public only')
            assert len(requests)==before+1 and requests[-1]['evidence_rule']==(arm=='C') and requests[-1]['diagnostics']==(arm!='A')
            assert info['usage']['adapter_attempts']==1 and info['usage']['total_tokens']==5
            assert info['usage']['token_usage_source']=='provider'
with patch.object(httpx.AsyncClient,'send',send),patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')):
    asyncio.run(run())
m.write(R/'transport-cpu.json',{'status':'PASS_ACTUAL_SDK_JSON_MOCK_HTTP','calls':len(requests),'old_nested_config_rejected':True,'network_calls':0,'model_generations':0,'plan_sha256':m.sha(R/'plan.json'),'source_step_limit':cfg.solver.step_limit})
print(json.dumps({'status':'PASS','sdk_encoded_requests':len(requests),'network_calls':0,'source_step_limit':cfg.solver.step_limit}))
