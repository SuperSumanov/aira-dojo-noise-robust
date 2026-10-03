"""Socket-blocked SDK and actual episode-loop tests; never experiment results."""
import asyncio,copy,json,logging,os,socket,sys,tempfile,types
from pathlib import Path
from unittest.mock import patch
R=Path('/research/d7/spc/yzyang4/opportunity-information-20261003-v2');sys.path.insert(0,str(R))
import task_feedback_real_20261001 as x
m=x.m;d=x.d;m.check();m.setup();logging.disable(logging.CRITICAL)
from dojo.config_dataclasses.run import RunConfig
from dojo.tasks.mlebench.task import MLEBenchTask
from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
from dojo.utils.experiment_deadline import ExperimentDeadline
from omegaconf import OmegaConf
import httpx
os.environ['PRIMARY_KEY_QWEN3_8_27B']='synthetic-test-only'
configs=[]
for s in x.schedule():
    c=RunConfig.load_from_json(R/'configs'/f'{s["index"]}.json');c.validate();configs.append(c)
    assert not c.solver.root_failure_randomization and not c.solver.acquisition_first_slot and not c.solver.use_test_score
    assert c.solver.time_limit_secs==600 and c.solver.step_limit==5
for seed in {s['seed'] for s in x.schedule()}:
    cc=[]
    for s in x.schedule():
        if s['seed']!=seed:continue
        c=json.loads((R/'configs'/f'{s["index"]}.json').read_bytes());c.pop('id');c['logger'].pop('output_dir');c['solver'].pop('checkpoint_path');c['interpreter'].pop('working_dir');cc.append(c)
    assert len(cc)==3 and cc[0]==cc[1]==cc[2]
def response(mode='SOLUTION',code='print(1)'):return 'Reason\n'+mode+'\n```python\n'+code+'\n```'
requests=[]
async def send(self,request,**kw):
    body=json.loads(request.content);requests.append(body)
    assert request.url.host=='127.0.0.1' and request.url.port==19453
    assert body['max_tokens']==4096 and not any(k.startswith('bounded_') for k in body)
    return httpx.Response(200,request=request,json={'id':'mock','object':'chat.completion','created':0,'model':'local27b','choices':[{'index':0,'message':{'role':'assistant','content':response()},'finish_reason':'stop'}],'usage':{'prompt_tokens':2,'completion_tokens':3,'total_tokens':5}})
async def sdk():
    for c in configs:
        raw,info=await GenericLLM(OmegaConf.structured(c.solver.operators['improve']))(messages=[{'role':'user','content':'synthetic'}]);assert str(raw)==response() and info['usage']['adapter_attempts']==1
with patch.object(httpx.AsyncClient,'send',send),patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')):asyncio.run(sdk())
real_config=RunConfig.load_from_json;real_init=MLEBenchTask.__init__;loops=[]
for task_index in (0,1):
 for arm in 'ABC':
  for broken in (False,True):
    s=next(s for s in x.schedule() if s['start']==task_index and s['arm']==arm);ep=Path(tempfile.mkdtemp(prefix='cpu-loop-',dir=R));prompts=[];instances=[];calls=[]
    def cfg(path):
        c=real_config(path);c.logger.output_dir=str(ep/'native-log');return c
    def init(self,*a,**kw):
        real_init(self,*a,**kw);metric='auc' if task_index==0 else 'log_loss'
        self._search_only_score=lambda *_:{metric:(.6 if task_index==0 else .4) if len(prompts)>1 else .5}
    class I:
        def __init__(self,c):self.cfg=c;self.working_dir=c.working_dir;self._instance=None;self.id=len(instances);instances.append(self)
        def run(self,code,reset_session=True,**kw):
            assert not reset_session;calls.append((self.id,code));fail=broken and 'CHECK_MARKER' in code and len(prompts)==1
            return types.SimpleNamespace(term_out=['INITIAL_MARKER' if len(calls)==1 else 'FUTURE_MARKER'],exit_code=1 if fail else 0,timed_out=False,exec_time=.01)
        def fetch_file(self,p):Path(p).write_text('synthetic\n');return str(p)
        def close(self):pass
    async def llm(self,messages=None,**kw):
        prompts.append(messages[0]['content']);return (response('CHECK','print("CHECK_MARKER")') if len(prompts)==1 else response()),{'usage':{'total_tokens':5}}
    with patch.object(RunConfig,'load_from_json',cfg),patch.object(MLEBenchTask,'__init__',init),patch('dojo.utils.config.build',lambda c,*a,**kw:I(c)),patch.object(GenericLLM,'__call__',llm),patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')):
        d.episode(s,ep,ExperimentDeadline(60))
    assert len(prompts)==4 and m.read(ep/'completed.json')['selected_metric']==(.6 if task_index==0 else .4)
    assert 'INITIAL_MARKER' in prompts[0] and 'FUTURE_MARKER' in prompts[1]
    assert all((x.FACTS[task_index] in p)==(arm=='B') and (x.SPECS[task_index] in p)==(arm=='C') for p in prompts)
    if broken:
        assert len(instances)>=2 and 'CHECK_MARKER' not in prompts[2].split('SUCCESSFUL CODE LEDGER:',1)[1].split('OBSERVED HISTORY:',1)[0]
    else:assert len(instances)==1
    loops.append(dict(task_index=task_index,arm=arm,failed_cell=broken,instances=len(instances),calls=len(calls)))
out=dict(status='PASS',plan_sha256=m.sha(R/'plan.json'),script_sha256=m.sha(Path(__file__)),sdk_requests=len(requests),network_calls=0,typed_configs=len(configs),paired_configs_identical=True,actual_episode_loops=len(loops),loops=loops,scope='Synthetic CPU transport/control tests only, not model or task evidence.')
m.write(R/'transport-loop-cpu.json',out);print(json.dumps({k:v for k,v in out.items() if k!='loops'}))
