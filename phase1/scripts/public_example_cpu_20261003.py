"""Exercise actual episode, equal configs, public selectors and SDK without GPU/API."""
import asyncio,hashlib,json,logging,os,socket,sys,tempfile,types
from pathlib import Path
from unittest.mock import patch
R=Path('/research/d7/spc/yzyang4/public-example-feedback-20261003-v1')
sys.path.insert(0,str(R));import task_feedback_real_20261001 as d
import public_error_examples_20261003 as e
import numpy as np
m=d.m;m.check();m.setup();logging.disable(logging.CRITICAL)
from dojo.config_dataclasses.run import RunConfig
from dojo.tasks.mlebench.task import MLEBenchTask
from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
from dojo.utils.experiment_deadline import ExperimentDeadline
from omegaconf import OmegaConf
import httpx

def response(mode='SOLUTION',code='print(1)'):
    return 'Brief reasoning\n'+mode+'\n```python\n'+code+'\n```'
for step in range(1,7):assert d.decode(response(),step)[0]=='SOLUTION'
for raw,step in [(response('CHECK'),6),('',1),(response(code='x=('),1),('SOLUTION\n'+response(),1),(response()+response(),1),('```python\nprint("SOLUTION")\n```',1)]:
    try:d.decode(raw,step)
    except (ValueError,SyntaxError):pass
    else:raise AssertionError('bad format accepted')

sampling=[]
for k in (2,3):
    y=np.tile(np.arange(k),80);z=np.linspace(.01,.99,len(y))
    p=np.full((len(y),k),0.)
    for i,c in enumerate(y):p[i]=[(z[i] if j==c else (1-z[i])/(k-1)) for j in range(k)]
    texts=['public training '+str(i) for i in range(len(y))]
    for policy in ('uniform','contrast'):
        a,b=e.packet(texts,y,p,[str(i) for i in range(k)],103501,policy)
        assert (a,b)==e.packet(texts,y,p,[str(i) for i in range(k)],103501,policy)
        assert len(a['examples'])==12 and len(set(b['selected_indices']))==12
        assert all(sum(r['true_class']==str(c) for r in a['examples'])==12//k for c in range(k))
        if policy=='contrast':
            losses=-np.log(p[np.arange(len(y)),y])
            for c in range(k):
                ids=np.flatnonzero(y==c);order=ids[np.argsort(losses[ids],kind='stable')];q=len(ids)//4
                selected=set(b['selected_indices'])&set(ids)
                assert len(selected&set(order[:q]))==6//k and len(selected&set(order[-q:]))==6//k
        sampling.append(dict(classes=k,policy=policy,rows=len(a['examples'])))

configs=[]
for s in d.schedule():
    c=RunConfig.load_from_json(R/'configs'/f'{s["index"]}.json');c.validate();configs.append(c)
    task=MLEBenchTask(c.task);assert task._search_only_score and not task.private_dir.exists()
    assert c.solver.time_limit_secs==900 and c.solver.step_limit==7
for seed in {s['seed'] for s in d.schedule()}:
    copies=[]
    for s in d.schedule():
        if s['seed']!=seed:continue
        c=json.loads((R/'configs'/f'{s["index"]}.json').read_bytes())
        c.pop('id');c['logger'].pop('output_dir');c['solver'].pop('checkpoint_path');c['interpreter'].pop('working_dir');copies.append(c)
    assert len(copies)==2 and copies[0]==copies[1]
    ss=[s for s in d.schedule() if s['seed']==seed]
    assert d.prompt('same task',ss[0],1,['pass'],'SAME HISTORY',500)==d.prompt('same task',ss[1],1,['pass'],'SAME HISTORY',500)

os.environ['PRIMARY_KEY_QWEN3_8_27B']='synthetic-test-only';requests=[]
async def send(self,request,**kw):
    body=json.loads(request.content);requests.append(body)
    assert request.url.host=='127.0.0.1' and request.url.port==19449
    assert body['max_tokens']==4096 and not any(k.startswith('bounded_') for k in body)
    assert body['chat_template_kwargs']=={'enable_thinking':False}
    return httpx.Response(200,request=request,json={'id':'mock','object':'chat.completion','created':0,'model':'local27b','choices':[{'index':0,'message':{'role':'assistant','content':response()},'finish_reason':'stop'}],'usage':{'prompt_tokens':2,'completion_tokens':3,'total_tokens':5}})
async def sdk():
    for c in configs:
        raw,info=await GenericLLM(OmegaConf.structured(c.solver.operators['improve']))(messages=[{'role':'user','content':'synthetic'}])
        assert str(raw)==response() and info['usage']['adapter_attempts']==1
with patch.object(httpx.AsyncClient,'send',send),patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')):asyncio.run(sdk())

real_config=RunConfig.load_from_json;real_init=MLEBenchTask.__init__;loops=[]
for arm in ('uniform','contrast'):
    for broken in (False,True):
        s=next(s for s in d.schedule() if s['arm']==arm and s['start']==0)
        ep=Path(tempfile.mkdtemp(prefix='examples-cpu-',dir=R));prompts=[];instances=[];calls=[]
        def cfg(path):
            c=real_config(path);c.logger.output_dir=str(ep/'native-log');return c
        def task_init(self,*a,**kw):
            real_init(self,*a,**kw);self._search_only_score=lambda *_:{'auc':.6 if len(prompts)>1 else .5}
        shown,meta=e.packet(texts,y,p,[str(i) for i in range(k)],s['seed'],arm)
        fixture='PUBLIC_EXAMPLE_PACKET '+json.dumps(dict(shown=shown,metadata=meta),sort_keys=True)
        class I:
            def __init__(self,c):self.cfg=c;self.working_dir=c.working_dir;self._instance=None;self.id=len(instances);instances.append(self)
            def run(self,code,reset_session=True,**kw):
                assert not reset_session;calls.append((self.id,code))
                first=len(calls)==1;fail=broken and 'CELL_CHECK' in code and len(prompts)==1
                terminal='INITIAL_PUBLIC_MARKER\n'+fixture if first else 'FUTURE_PUBLIC_MARKER'
                return types.SimpleNamespace(term_out=[terminal],exit_code=1 if fail else 0,timed_out=False,exec_time=.01)
            def fetch_file(self,p):Path(p).write_text('synthetic\n');return str(p)
            def close(self):pass
        async def llm(self,messages=None,**kw):
            prompts.append(messages[0]['content'])
            return response('CHECK','print("CELL_CHECK")') if len(prompts)==1 else response(),{'usage':{'total_tokens':5}}
        with patch.object(RunConfig,'load_from_json',cfg),patch.object(MLEBenchTask,'__init__',task_init),patch('dojo.utils.config.build',lambda c,*a,**kw:I(c)),patch.object(GenericLLM,'__call__',llm),patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')):
            d.episode(s,ep,ExperimentDeadline(60))
        assert len(prompts)==6 and m.read(ep/'completed.json')['selected_metric']==.6
        assert 'INITIAL_PUBLIC_MARKER' in prompts[0] and 'PUBLIC TRAINING EXAMPLES' in prompts[0]
        assert 'mean_selected_loss' not in prompts[0] and 'FUTURE_PUBLIC_MARKER' in prompts[1]
        assert 'from_namespace' in calls[0][1] and 'from_namespace' not in prompts[0].split('OBSERVED HISTORY:')[0]
        assert len(instances)==(2 if broken else 1)
        assert m.read(ep/'action-0/public-packet.private.json')['metadata']['policy']==arm
        if broken:assert 'CELL_CHECK' not in prompts[2].split('SUCCESSFUL CODE LEDGER:')[1].split('OBSERVED HISTORY:')[0]
        loops.append(dict(arm=arm,broken=broken,instances=len(instances),calls=len(calls)))

executor=types.SimpleNamespace(_timeout=999);inner=types.SimpleNamespace(timeout=999,code_executor=executor)
outer=types.SimpleNamespace(cfg=types.SimpleNamespace(timeout=999),timeout=999,_instance=inner,run=lambda *a,**kw:kw)
assert d.execute(outer,'pass',7)['reset_session'] is False and executor._timeout==7
m.subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
batch=(R/'run.sbatch').read_text();assert '--gres=gpu:4' in batch and '--time=01:40:00' in batch and '5940s' in batch
for name,out in [('cpu.json',dict(typed_configs=len(configs),paired_configs_equal=True,identical_prompt_given_identical_history=True,selector_cases=sampling,loops=loops,live_timeout_test=True)),('transport-cpu.json',dict(encoded_requests=len(requests),network_calls=0))]:m.write(R/name,dict(status='PASS',plan_sha256=m.sha(R/'plan.json'),test_script_sha256=m.sha(Path(__file__)),**out))
print(json.dumps(dict(status='PASS',typed_configs=len(configs),sdk_requests=len(requests),actual_loops=len(loops),selector_cases=len(sampling))))
