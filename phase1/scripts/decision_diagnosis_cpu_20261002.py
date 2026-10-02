"""Exercise actual two-generation loop and encoded SDK without network/GPU."""
import asyncio, copy, importlib.util, json, os, socket, sys, tempfile, types
from pathlib import Path
from unittest.mock import patch
ROOT=Path('/research/d7/spc/yzyang4/decision-diagnosis-20261002-v1')
sys.path.insert(0,str(ROOT))
import task_feedback_real_20261001 as d
m=d.m; m.check(); m.setup()
from dojo.config_dataclasses.run import RunConfig
from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
from dojo.tasks.mlebench.task import MLEBenchTask
from dojo.core.tasks.constants import EXECUTION_OUTPUT,VALID_SOLUTION,VALIDATION_FITNESS
from dojo.utils.experiment_deadline import ExperimentDeadline
from omegaconf import OmegaConf
import httpx

def response(mode='SOLUTION',code='print(1)'):
    return mode+'\nA rationale\n```python\n'+code+'\n```'
assert d.decode(response('CHECK'),'B',1)[0]=='CHECK'
bad=[('', 'A',1),(response('SOLUTION'),'B',1),(response('CHECK'),'A',2),
     ('SOLUTION\n```json\n{}\n```','A',2),(response()+response(),'A',2),
     (response(code='x=('),'A',2)]
for raw,arm,step in bad:
    try: d.decode(raw,arm,step)
    except (ValueError,SyntaxError): pass
    else: raise AssertionError('bad action accepted')

configs=[]
for s in d.schedule():
    c=RunConfig.load_from_json(ROOT/'configs'/f'{s["index"]}.json'); c.validate()
    t=MLEBenchTask(c.task)
    assert t._search_only_score and not t.private_dir.exists()
    assert c.solver.step_limit==3 and c.solver.time_limit_secs==900
    configs.append(c)
for seed in {s['seed'] for s in d.schedule()}:
    pair=[s for s in d.schedule() if s['seed']==seed]
    a,b=[json.loads((ROOT/'configs'/f'{s["index"]}.json').read_bytes()) for s in pair]
    for cfg in (a,b):
        cfg.pop('id'); cfg['logger'].pop('output_dir'); cfg['solver'].pop('checkpoint_path'); cfg['interpreter'].pop('working_dir')
    assert a==b

os.environ['PRIMARY_KEY_QWEN3_8_27B']='synthetic-test-only'
requests=[]
async def send(self,request,**kw):
    body=json.loads(request.content); requests.append(body)
    assert request.url.host=='127.0.0.1' and request.url.port==19445
    assert body['max_tokens']==4096 and not any(k.startswith('bounded_') for k in body)
    assert body['chat_template_kwargs']=={'enable_thinking':False}
    return httpx.Response(200,request=request,json={'id':'mock','object':'chat.completion','created':0,
        'model':'local27b','choices':[{'index':0,'message':{'role':'assistant','content':response()},'finish_reason':'stop'}],
        'usage':{'prompt_tokens':2,'completion_tokens':3,'total_tokens':5}})
async def sdk():
    for c in configs:
        llm=GenericLLM(OmegaConf.structured(c.solver.operators['improve']))
        raw,info=await llm(messages=[{'role':'user','content':'synthetic'}])
        assert info['usage']['adapter_attempts']==1 and str(raw)==response()
with patch.object(httpx.AsyncClient,'send',send),patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')):
    asyncio.run(sdk())
m.write(ROOT/'transport-cpu.json',dict(status='PASS',encoded_requests=len(requests),network_calls=0,plan_sha256=m.sha(ROOT/'plan.json')))

original_config=RunConfig.load_from_json; original_init=MLEBenchTask.__init__; records=[]
for arm in 'AB':
    for broken in (False,True):
        ep=Path(tempfile.mkdtemp(prefix='loop-cpu-',dir=ROOT)); prompts=[]; modes=[]
        s=next(s for s in d.schedule() if s['arm']==arm and s['task']==d.TASKS[0])
        def config(path):
            c=original_config(path); c.logger.output_dir=str(ep/'native-log'); return c
        def taskinit(self,*a,**kw):
            original_init(self,*a,**kw); self._search_only_score=lambda *_: {'split':'D_search_development_only','auc':.5}
        class Interpreter:
            factory=True
            def __init__(self,cfg): self.working_dir=cfg.working_dir
            def close(self): pass
            def cleanup_session(self): pass
            def run(self,code,**kw):
                modes.append('CHECK')
                return types.SimpleNamespace(term_out=['OBSERVED_DISTINGUISHING_VALUE_17'],exit_code=(1 if broken else 0),timed_out=False,exec_time=.1)
        def build(c,*a,**kw): return Interpreter(c)
        def step(self,state,code):
            modes.append('SOLUTION'); path=ep/f'mock-{len(modes)}.csv'; path.write_text('mock\n')
            self._search_only_score(s['task'],path)
            out=types.SimpleNamespace(term_out=['baseline or solution output'],exit_code=0,timed_out=False,exec_time=.1)
            return state,{EXECUTION_OUTPUT:out,VALID_SOLUTION:True,VALIDATION_FITNESS:(.5 if len(modes)==1 else .6)}
        async def llm(self,messages=None,**kw):
            prompts.append(messages[0]['content'])
            return response('CHECK' if len(prompts)==1 and arm=='B' else 'SOLUTION'),{'usage':{'total_tokens':5}}
        with patch.object(RunConfig,'load_from_json',config),patch.object(MLEBenchTask,'__init__',taskinit),\
             patch('dojo.utils.config.build',build),patch.object(MLEBenchTask,'step_task',step),patch.object(GenericLLM,'__call__',llm):
            d.episode(s,ep,ExperimentDeadline(60))
        assert len(prompts)==2 and m.read(ep/'completed.json')['selected_metric']==.6
        assert modes==(['SOLUTION','CHECK','SOLUTION'] if arm=='B' else ['SOLUTION']*3)
        if arm=='B':
            assert 'OBSERVED_DISTINGUISHING_VALUE_17' not in prompts[0] and 'OBSERVED_DISTINGUISHING_VALUE_17' in prompts[1]
            assert f'Exit={1 if broken else 0}' in prompts[1]
            assert m.read(ep/'action-1/result.json')['successful_check']==(not broken)
        records.append(dict(arm=arm,broken_check=broken,modes=modes))

# Explicit regression for the old supervisor timestamp race: receipt published
# after loop timestamp must pass against a fresh post-read timestamp; stale or
# wrong-budget receipts must still fail. No relaxation of bounds.
spec=importlib.util.spec_from_file_location('supervisor',ROOT/'root_trial_step_supervisor_20260927.py')
sup=importlib.util.module_from_spec(spec); spec.loader.exec_module(sup)
r={'clock':'time.monotonic','budget_seconds':900,'started_monotonic':10.01,'deadline_monotonic':910.01}
try: sup.worker_cutoff(r,seconds=900,spawned=9,now=10)
except ValueError: pass
else: raise AssertionError('old race fixture did not fail')
assert sup.worker_cutoff(r,seconds=900,spawned=9,now=10.02)==910.01
for bad_r in (dict(r,budget_seconds=100),dict(r,started_monotonic=8),dict(r,deadline_monotonic=999)):
    try: sup.worker_cutoff(bad_r,seconds=900,spawned=9,now=10.02)
    except ValueError: pass
    else: raise AssertionError('bad clock accepted')
assert 'spawned=began, now=time.monotonic())' in (ROOT/'root_trial_step_supervisor_20260927.py').read_text()
m.subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
m.write(ROOT/'cpu.json',dict(status='PASS',typed_configs=8,paired_configs_equal=True,loops=records,
    clock_race_regression=True,real_calls=0,gpu=0,plan_sha256=m.sha(ROOT/'plan.json')))
print(json.dumps(dict(status='PASS',typed_configs=8,sdk_requests=len(requests),actual_loops=len(records))))
