"""Parser adversaries, real SDK mocked-HTTP encoding and actual two-step loop."""
import asyncio,copy,json,logging,os,socket,sys,tempfile,types
from pathlib import Path
from unittest.mock import patch
R=Path('/research/d7/spc/yzyang4/task-feedback-local-edit-20261002-v1')
sys.path.insert(0,str(R));from task_feedback_real_20261001 import m,COMMON,FORMATS
m.check();m.setup()
from local_edit_format_20261002 import apply_response
from dojo.config_dataclasses.run import RunConfig
from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
from dojo.core.solvers.operators.improve import improve_op
from dojo.core.solvers.utils.journal import Journal,Node
from dojo.tasks.mlebench.task import MLEBenchTask
from dojo.core.tasks.constants import EXECUTION_OUTPUT,VALID_SOLUTION,VALIDATION_FITNESS,AUX_EVAL_INFO
from dojo.utils.experiment_deadline import ExperimentDeadline
from dojo.utils.code_parsing import extract_code
from task_feedback_facts_20261001 import feedback,packet
from omegaconf import OmegaConf
import httpx
def fenced(value):return '```json\n'+json.dumps(value)+'\n```'
code='x = 1\nprint(x)\n'
new,details=apply_response(fenced([{'search':'x = 1','replace':'x = 2'}]),code,'P',extract_code)
assert new=='x = 2\nprint(x)\n' and details['changed_lines']==1
assert apply_response(fenced([]),code,'P',extract_code)[0]==code
assert apply_response('```python\n'+new+'```',code,'F',extract_code)[0].strip()==new.strip()
bad=[fenced([{'search':'missing','replace':'x'}]),fenced([{'search':'','replace':'x'}]),fenced([{'search':'x','replace':'y'}]),fenced([{'search':'x = 1','replace':'x = ('}]),fenced({'search':'x'}),fenced([{'search':'x = 1','replace':'x = 2','extra':1}]),'```json\n[\n```',fenced([])+'\n'+fenced([])]
for raw in bad:
    try:apply_response(raw,code,'P',extract_code)
    except (ValueError,SyntaxError,TypeError):pass
    else:raise AssertionError('bad edit accepted')
for n in ('openai','httpx','httpcore','LiteLLM','Backend'):logging.getLogger(n).setLevel(logging.CRITICAL)
os.environ['PRIMARY_KEY_QWEN3_8_27B']='synthetic-test-only';requests=[]
async def send(self,request,**kwargs):
    body=json.loads(request.content);assert request.url.host=='127.0.0.1' and request.url.port==19443
    assert body['max_tokens']==8192 and body['chat_template_kwargs']=={'enable_thinking':False}
    assert not any(k.startswith('bounded_') for k in body)
    text='\n'.join(x['content'] for x in body['messages'])
    assert 'Human-curated candidate repair' in text and 'verified_initial_evidence' in text
    arm='P' if 'at most eight objects' in text else 'F'
    assert ('complete runnable program' in text)==(arm=='F')
    requests.append(arm)
    raw=fenced([{'search':'x = 1','replace':'x = 2'}]) if arm=='P' else '```python\nx = 2\nprint(x)\n```'
    return httpx.Response(200,request=request,json={'id':'mock','object':'chat.completion','created':0,'model':'qwen3.8-27b','choices':[{'index':0,'message':{'role':'assistant','content':raw},'finish_reason':'stop'}],'usage':{'prompt_tokens':2,'completion_tokens':3,'total_tokens':5}})
async def sdk():
    for s in m.schedule():
        cfg=RunConfig.load_from_json(R/'configs'/f'{s["index"]}.json');cfg.validate();task=MLEBenchTask(cfg.task)
        assert task._search_only_score and not task.private_dir.exists()
        assert cfg.solver.time_limit_secs==900 and cfg.solver.step_limit==2
        native=GenericLLM(OmegaConf.structured(cfg.solver.operators['improve']))
        j=Journal();n=Node(code=code,plan='mock',_term_out=['mock']);j.append(n)
        msg,_=feedback('C',{'valid':True},packet(s['task']),'mock')
        raw,info=await improve_op(native,OmegaConf.structured(cfg.solver),lambda *_:msg,'mock task',j,n,1,100,data_preview='public')
        assert info['usage']['adapter_attempts']==1 and info['usage']['total_tokens']==5
        assert apply_response(str(raw),code,s['arm'],extract_code)[0].strip()==new.strip()
with patch.object(httpx.AsyncClient,'send',send),patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')):asyncio.run(sdk())
m.write(R/'transport-cpu.json',dict(status='PASS',encoded_requests=len(requests),network_calls=0,plan_sha256=m.sha(R/'plan.json')))
original_config=RunConfig.load_from_json;original_init=MLEBenchTask.__init__;rows=[]
for arm in 'FP':
    ep=Path(tempfile.mkdtemp(prefix='edit-cpu-',dir=R));seen=[];prompts=[]
    s=next(x for x in m.schedule() if x['arm']==arm);initial=m.read(R/'starts'/f'{s["start"]}.private.json')['code']
    def config(path):
        c=original_config(path);c.logger.output_dir=str(ep/'native-log');return c
    def taskinit(self,*args,**kw):
        original_init(self,*args,**kw);self._search_only_score=lambda *_:{'split':'D_search_development_only','auc':.5}
    class Interpreter:
        factory=True
        def __init__(self,cfg):self.working_dir=cfg.working_dir
        def close(self):pass
    def build(c,*a,**kw):return Interpreter(c)
    def step(self,state,code):
        seen.append(code);p=ep/f'mock-{len(seen)}.csv';p.write_text('mock\n');self._search_only_score(s['task'],p)
        out=types.SimpleNamespace(term_out=['mock'],exit_code=0,exec_time=.01,timed_out=False)
        return state,{EXECUTION_OUTPUT:out,VALID_SOLUTION:True,VALIDATION_FITNESS:.5+.1*(len(seen)==2),AUX_EVAL_INFO:{'execution_started':True}}
    async def llm(self,query_data=None,**kw):
        prompts.append(self.system_message_prompt_template.format(**query_data))
        raw=fenced([]) if arm=='P' else '```python\n'+initial+'\n```'
        return raw,{'usage':{'prompt_tokens':1,'completion_tokens':1}}
    with patch.object(RunConfig,'load_from_json',config),patch.object(MLEBenchTask,'__init__',taskinit),patch('dojo.utils.config.build',build),patch.object(MLEBenchTask,'step_task',step),patch.object(GenericLLM,'__call__',llm):m.episode(s,ep,ExperimentDeadline(60))
    assert m.read(ep/'completed.json')['selected_metric']==.6
    assert len(seen)==2 and len(prompts)==1
    assert m.read(ep/'action-1/format.json')['status']=='accepted'
    rows.append(dict(arm=arm,actions=2,generations=1))
m.subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
m.write(R/'cpu.json',dict(status='PASS',typed_configs=12,parser_invalid_cases=len(bad),engine=rows,plan_sha256=m.sha(R/'plan.json'),gpu=0,api=0))
print(json.dumps({'status':'PASS','sdk_requests':len(requests),'engine':rows,'invalid_parser_cases':len(bad)}))
