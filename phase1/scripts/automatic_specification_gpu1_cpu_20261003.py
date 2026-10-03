"""Actual-loop synthetic preflight: no network, model, GPU or effect evidence."""
import asyncio, hashlib, json, logging, os, socket, sys, tempfile, types
from pathlib import Path
from unittest.mock import patch

R=Path('/research/d7/spc/yzyang4/automatic-specification-20261003-gpu1-v2')
sys.path.insert(0,str(R))
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
    assert c.interpreter.timeout==300 and c.interpreter.env['PYTHONHASHSEED']=='42'
for seed in {s['seed'] for s in x.schedule() if s['role']=='comparison'}:
    cc=[]
    for s in x.schedule():
        if s['seed']!=seed:continue
        c=json.loads((R/'configs'/f'{s["index"]}.json').read_bytes())
        c.pop('id');c['logger'].pop('output_dir');c['solver'].pop('checkpoint_path');c['interpreter'].pop('working_dir');cc.append(c)
    assert len(cc)==3 and cc[0]==cc[1]==cc[2]
assert len(configs)==14 and len({(s['start'],s['seed']) for s in x.schedule()[2:]})==4

def response(mode='SOLUTION',code='print(1)'):
    return 'Reason\n'+mode+'\n```python\n'+code+'\n```'
PLAN='PLAN\nPreserve the current transform; check the observed public metric before changing one component.'
requests=[]
async def send(self,request,**kw):
    body=json.loads(request.content);requests.append(body)
    assert request.url.host=='127.0.0.1' and request.url.port==19455
    assert body['max_tokens']==4096 and not any(k.startswith('bounded_') for k in body)
    assert body['chat_template_kwargs']['enable_thinking'] is False
    return httpx.Response(200,request=request,json={'id':'mock','object':'chat.completion','created':0,'model':'local27b','choices':[{'index':0,'message':{'role':'assistant','content':response()},'finish_reason':'stop'}],'usage':{'prompt_tokens':2,'completion_tokens':3,'total_tokens':5}})
async def sdk():
    for c in configs:
        raw,info=await GenericLLM(OmegaConf.structured(c.solver.operators['improve']))(messages=[{'role':'user','content':'synthetic'}])
        assert str(raw)==response() and info['usage']['adapter_attempts']==1
with patch.object(httpx.AsyncClient,'send',send),patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')):
    asyncio.run(sdk())

assert x.decode(PLAN,1)[0]=='PLAN'
for raw,step in [(PLAN,4),('PLAN\n```python\npass\n```',1),('PLAN\nCHECK\n'+'x'*40,1)]:
    try:x.decode(raw,step)
    except ValueError:pass
    else:raise AssertionError('invalid PLAN accepted')

real_config=RunConfig.load_from_json;real_init=MLEBenchTask.__init__;loops=[]
def loop(s,case):
    tr=Path(tempfile.mkdtemp(prefix='cpu-auto-',dir=R));ep=tr/'episode';ep.mkdir();(tr/'starts').mkdir()
    prompts=[];instances=[];calls=[];graded=[]
    parent='print("INITIAL_MARKER")'
    m.write(tr/'starts'/f'{s["start"]}.private.json',{'code':parent})
    m.write(tr/'roots-ready.json',{'starts':[{'start':s['start'],'code_sha256':hashlib.sha256(parent.encode()).hexdigest()}]})
    def cfg(path):
        c=real_config(R/'configs'/f'{s["index"]}.json');c.logger.output_dir=str(ep/'native-log');return c
    def init(self,*a,**kw):
        real_init(self,*a,**kw)
        def score(*_):
            graded.append(len(prompts));return {self._search_only_metric_name:(.5 if not prompts else (.6 if s['start']==0 else .4))}
        self._search_only_score=score
    class I:
        def __init__(self,c):
            self.cfg=c;self.working_dir=c.working_dir;self._instance=None;self.id=len(instances);instances.append(self)
        def run(self,code,reset_session=True,**kw):
            assert not reset_session;calls.append((self.id,code))
            fail='FAIL_MARKER' in code
            return types.SimpleNamespace(term_out=['INITIAL_MARKER' if len(calls)==1 else 'FUTURE_MARKER'],exit_code=1 if fail else 0,timed_out=False,exec_time=.01)
        def fetch_file(self,p):Path(p).write_text('synthetic\n');return str(p)
        def close(self):pass
    async def llm(self,messages=None,**kw):
        prompts.append(messages[0]['content']);n=len(prompts)
        if case=='root_first':raw=response()
        elif case=='root_debug':raw=response('CHECK','a=1') if n==1 else response('SOLUTION','print("FAIL_MARKER")' if n==2 else 'print(a)')
        elif case=='root_failed':raw='invalid output'
        elif case=='reject_first' and n==1:raw=response()
        elif case=='last_plan' and n==4:raw=PLAN
        elif n==1:raw=PLAN
        elif n==2:raw=response('CHECK','print("FAIL_MARKER")' if case=='rollback' else 'print("CHECK_MARKER")')
        else:raw=response()
        return raw,{'usage':{'total_tokens':5}}
    with patch.object(d,'ROOT',tr),patch.object(RunConfig,'load_from_json',cfg),patch.object(MLEBenchTask,'__init__',init),patch('dojo.utils.config.build',lambda c,*a,**kw:I(c)),patch.object(GenericLLM,'__call__',llm),patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')):
        d.episode(s,ep,ExperimentDeadline(60))
    done=m.read(ep/'completed.json')
    if s['role']=='comparison':
        assert len(prompts)==done['generations']==4
        assert graded[0]==0 and 1 not in graded
        assert 'INITIAL_MARKER' in prompts[0]
        if case=='reject_first':
            assert m.read(ep/'action-1/format.json')['status']=='REJECT'
            assert not (ep/'action-1/started.json').exists()
        else:
            assert m.read(ep/'action-1/format.json')['mode']=='PLAN'
            assert not (ep/'action-1/started.json').exists()
            assert not (ep/'action-1/result.json').exists()
            assert PLAN in prompts[1] and PLAN not in prompts[0]
            assert PLAN not in prompts[1].split('SUCCESSFUL CODE LEDGER:',1)[1].split('OBSERVED HISTORY:',1)[0]
        if case=='last_plan':assert m.read(ep/'action-4/format.json')['status']=='REJECT'
        assert done['selected_metric']==(.6 if s['start']==0 else .4)
        assert x.RULES in prompts[0]
        if case=='rollback':
            assert len(instances)==2 and m.read(ep/'action-3/replay.json')['success']
            assert 'FAIL_MARKER' not in prompts[2].split('SUCCESSFUL CODE LEDGER:',1)[1].split('OBSERVED HISTORY:',1)[0]
    else:
        assert not (ep/'action-0').exists()
        if case=='root_failed':
            assert len(prompts)==4 and not done['valid'] and not (ep/'first-valid.json').exists()
        else:
            n=1 if case=='root_first' else 3
            assert len(prompts)==n and m.read(ep/'first-valid.json')['step']==n
            code=m.read(ep/'seed-program.private.json')['code']
            assert code.count('_r.seed(42)')==(1 if case=='root_first' else 2)
            assert 'FAIL_MARKER' not in code
            assert hashlib.sha256(code.encode()).hexdigest()==m.read(ep/'first-valid.json')['code_sha256']
    loops.append({'role':s['role'],'arm':s['arm'],'start':s['start'],'case':case,'generations':len(prompts),'executions':len(calls),'graded':len(graded)})

for k in (0,1):
    for arm in 'ABC':
        s=next(s for s in x.schedule() if s['start']==k and s['arm']==arm)
        for case in ('plan','rollback','last_plan'):loop(s,case)
        if arm in 'BC':loop(s,'reject_first')
    for case in ('root_first','root_debug','root_failed'):loop(x.schedule()[k],case)

# Freeze gate accepts a first-valid receipt, not a better later metric.
def fake_roots(valid):
    tr=Path(tempfile.mkdtemp(prefix='cpu-freeze-',dir=R));(tr/'starts').mkdir()
    for k in range(valid):
        code=f'print({k})';ep=tr/f'episode-{k}';ep.mkdir();(ep/'action-4').mkdir()
        m.write(ep/'seed-program.private.json',{'code':code})
        m.write(ep/'first-valid.json',{'step':2,'code_sha256':hashlib.sha256(code.encode()).hexdigest()})
        m.write(ep/'action-4/result.json',{'metric':9999})
    with patch.object(x,'R',tr):got=x.freeze_roots()
    assert got==(valid==2)
    if got:
        assert all(r['first_valid_step']==2 for r in m.read(tr/'roots-ready.json')['starts'])
    else:assert m.read(tr/'roots-unavailable.json')['status']=='STOP_NO_REPLACEMENT' and not (tr/'roots-ready.json').exists()
for valid in (0,1,2):fake_roots(valid)

# Per-cell RNG reset survives source flattening, with no model/task execution.
ledger=['a=_r.random()','b=_r.random()']
frozen='\n\n'.join(x.wrapper(c,42,False) for c in ledger);g={}
exec(frozen,g);assert g['a']==g['b']

out=dict(status='PASS',plan_sha256=m.sha(R/'plan.json'),script_sha256=m.sha(Path(__file__)),typed_configs=len(configs),sdk_requests=len(requests),network_calls=0,paired_configs_identical=True,actual_episode_loops=len(loops),loops=loops,root_freeze_cases=3,scope='Synthetic CPU control/transport tests only; no experiment or model evidence.')
m.write(R/'transport-loop-cpu.json',out)
print(json.dumps({k:v for k,v in out.items() if k!='loops'}))
