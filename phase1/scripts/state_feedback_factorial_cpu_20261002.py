"""Actual factorial loop and SDK transport tests; no data execution or sockets."""
import asyncio, copy, json, logging, os, socket, sys, tempfile, types
from pathlib import Path
from unittest.mock import patch
R=Path(os.environ.get('STATE_FACTORIAL_TEST_ROOT','/research/d7/spc/yzyang4/state-feedback-factorial-20261002-v1'))
sys.path.insert(0,str(R));import task_feedback_real_20261001 as d
m=d.m;m.check();m.setup()
from dojo.config_dataclasses.run import RunConfig
from dojo.tasks.mlebench.task import MLEBenchTask
from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
from dojo.utils.experiment_deadline import ExperimentDeadline
from omegaconf import OmegaConf
import httpx
logging.disable(logging.CRITICAL)

def response(mode='SOLUTION',code='print(1)'):
    return mode+'\nSynthetic rationale\n```python\n'+code+'\n```'
for step in range(1,5): assert d.decode(response(),step)[0]=='SOLUTION'
for raw,step in [(response('CHECK'),4),('',1),(response(code='x=('),1),
                 ('SOLUTION\n```json\n{}\n```',1),(response()+response(),2)]:
    try:d.decode(raw,step)
    except (ValueError,SyntaxError):pass
    else:raise AssertionError('invalid accepted')

configs=[]
for s in d.schedule():
    c=RunConfig.load_from_json(R/'configs'/f'{s["index"]}.json');c.validate()
    task=MLEBenchTask(c.task)
    assert task._search_only_score and not task.private_dir.exists()
    assert c.solver.time_limit_secs==720 and c.solver.step_limit==5
    configs.append(c)
for seed in {s['seed'] for s in d.schedule()}:
    copies=[]
    for s in d.schedule():
        if s['seed']!=seed:continue
        c=json.loads((R/'configs'/f'{s["index"]}.json').read_bytes())
        c.pop('id');c['logger'].pop('output_dir');c['solver'].pop('checkpoint_path');c['interpreter'].pop('working_dir')
        copies.append(c)
    assert len(copies)==4 and all(c==copies[0] for c in copies)

os.environ['PRIMARY_KEY_QWEN3_8_27B']='synthetic-test-only'
requests=[]
async def send(self,request,**kw):
    body=json.loads(request.content);requests.append(body)
    assert request.url.host=='127.0.0.1' and request.url.port==m.PORT
    assert body['max_tokens']==4096 and not any(k.startswith('bounded_') for k in body)
    assert body['chat_template_kwargs']=={'enable_thinking':False}
    return httpx.Response(200,request=request,json={'id':'mock','object':'chat.completion','created':0,'model':'local27b',
        'choices':[{'index':0,'message':{'role':'assistant','content':response()},'finish_reason':'stop'}],
        'usage':{'prompt_tokens':2,'completion_tokens':3,'total_tokens':5}})
async def sdk():
    for c in configs:
        raw,info=await GenericLLM(OmegaConf.structured(c.solver.operators['improve']))(messages=[{'role':'user','content':'synthetic'}])
        assert str(raw)==response() and info['usage']['adapter_attempts']==1
with patch.object(httpx.AsyncClient,'send',send),patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')):
    asyncio.run(sdk())

real_config=RunConfig.load_from_json;real_init=MLEBenchTask.__init__;loops=[]
for arm in 'ABCD':
    for broken in (False,True):
        s=next(s for s in d.schedule() if s['arm']==arm and s['start']==0)
        ep=Path(tempfile.mkdtemp(prefix='state-loop-cpu-',dir=R));prompts=[];instances=[];calls=[]
        def cfg(path):
            c=real_config(path);c.logger.output_dir=str(ep/'native-log');return c
        def task_init(self,*a,**kw):
            real_init(self,*a,**kw)
            self._search_only_score=lambda *_:{'auc':.6 if len(prompts)>1 else .5}
        class I:
            def __init__(self,c):self.cfg=c;self.working_dir=c.working_dir;self._instance=None;self.id=len(instances);instances.append(self)
            def run(self,code,reset_session=True,**kw):
                assert not reset_session;calls.append((self.id,code))
                is_first=(len(calls)==1);fail=broken and "CELL_CHECK" in code and len(prompts)==1
                marker='INITIAL_PUBLIC_MARKER_71' if is_first else 'FUTURE_PUBLIC_MARKER_29'
                return types.SimpleNamespace(term_out=[marker],exit_code=1 if fail else 0,timed_out=False,exec_time=.01)
            def fetch_file(self,p):Path(p).write_text('synthetic\n');return str(p)
            def close(self):pass
        async def llm(self,messages=None,**kw):
            prompts.append(messages[0]['content'])
            return response('CHECK','print("CELL_CHECK")') if len(prompts)==1 else response(),{'usage':{'total_tokens':5}}
        with patch.object(RunConfig,'load_from_json',cfg),patch.object(MLEBenchTask,'__init__',task_init),\
             patch('dojo.utils.config.build',lambda c,*a,**kw:I(c)),patch.object(GenericLLM,'__call__',llm),\
             patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')):
            d.episode(s,ep,ExperimentDeadline(60))
        assert len(prompts)==4 and m.read(ep/'completed.json')['selected_metric']==.6
        assert ('INITIAL_PUBLIC_MARKER_71' in prompts[0])==s['visible']
        assert 'FUTURE_PUBLIC_MARKER_29' in prompts[1] # reacquisition is not masked
        if not broken:assert len(instances)==(1 if s['retained'] else 5)
        else:
            assert len(instances)>=2
            assert 'CELL_CHECK' not in prompts[2].split('SUCCESSFUL CODE LEDGER:',1)[1].split('OBSERVED HISTORY:',1)[0]
        loops.append(dict(arm=arm,broken=broken,instances=len(instances),calls=len(calls)))

# Live timeout updates must reach the actual executor, not just factory cfg.
executor=types.SimpleNamespace(_timeout=999)
inner=types.SimpleNamespace(timeout=999,code_executor=executor)
outer=types.SimpleNamespace(cfg=types.SimpleNamespace(timeout=999),timeout=999,_instance=inner,run=lambda *a,**kw:kw)
assert d.execute(outer,'pass',7)['reset_session'] is False
assert outer.cfg.timeout==outer.timeout==inner.timeout==executor._timeout==7

m.subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
assert 'spawned=began, now=time.monotonic())' in (R/'root_trial_step_supervisor_20260927.py').read_text()
for name,out in [('cpu.json',dict(typed_configs=len(configs),paired_configs_equal=True,loops=loops,live_timeout_test=True)),
                 ('transport-cpu.json',dict(encoded_requests=len(requests),network_calls=0))]:
    m.write(R/name,dict(status='PASS',plan_sha256=m.sha(R/'plan.json'),**out))
print(json.dumps(dict(status='PASS',typed_configs=len(configs),sdk_requests=len(requests),actual_loops=len(loops))))
