"""Same six programs and two repair cycles, only schedule order changes."""
import argparse,ast,asyncio,copy,hashlib,importlib.util,json,math,os,random,subprocess,sys,tarfile,time,types
from pathlib import Path,PurePosixPath
from unittest.mock import patch
import run_comparison_online_continuation_20260919 as driver
import run_comparison_pizza_transfer_20260920 as bank
rt=driver.rt
SCRIPT=Path(__file__).name
SOURCE_SEEDS=(5,6)

def configure():
    driver.SCRIPT=SCRIPT;driver.TASK=bank.TASK;driver.ROOT_PREFIX='comparison-complete-pool-order-20260920-'
    driver.FULL_DEADLINE=True;driver.CONTEXT_MODULE=SCRIPT[:-3];driver.PLAN='comparison_complete_pool_order_plan_20260920.json'
    driver.FILES=(SCRIPT,driver.PLAN,'run_comparison_online_continuation_20260919.py','run_comparison_live_debug_20260919.py',
        'run_comparison_pizza_transfer_20260920.py','run_comparison_spooky_pool_20260919.py','local_generator_runtime_20260914.py',
        'comparison_full_deadline_policy_20260919.py','run_comparison_frozen_reward_20260919.py','forets_e2e_critic_service.py',
        'readout_comparison_complete_pool_order_20260920.py','readout_comparison_online_continuation_20260919.py','comparison_auc_20260920.py')
    driver.inputs=inputs;driver.cpu=cpu

def binding_context(env):configure();return driver.binding_context(env)

def select_pair(programs,scores,seed):
    if len(programs)!=6 or set(scores)!={p['slot'] for p in programs} or sorted(scores)!=list(range(6)):raise ValueError('all six scores')
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in scores.values()):raise ValueError('finite reward')
    order=sorted(scores,key=lambda slot:(-scores[slot],slot))
    chosen=sorted(random.Random(f'complete-pool-order:20260920:{seed}').sample(order[:3],2),key=order.index)
    remaining=[p['slot'] for p in sorted(programs,key=lambda p:p['slot']) if p['slot'] not in chosen]
    return dict(chosen=chosen,remaining=remaining,critic_order=order)

def schedule(selection,ready_first):
    chosen=selection['chosen'];tail=selection['remaining']
    if len(chosen)!=2 or len(tail)!=4 or sorted(chosen+tail)!=list(range(6)):raise ValueError('shared action set')
    if ready_first:return [('execute',slot) for slot in chosen+tail]+[('repair',slot) for slot in chosen]
    return [('execute',chosen[0]),('repair',chosen[0]),('execute',chosen[1]),('repair',chosen[1])]+[('execute',slot) for slot in tail]

def inputs():
    base=bank.base;base.source_check();bank.SEEDS=SOURCE_SEEDS
    structure=base.read(base.INPUT/'structure.redacted.json',base.STRUCTURE);nodes=base.read(base.INPUT/'qwen-readout-v1/nodes.json',base.NODES)
    configs,runseed,pool=bank.population(structure,nodes);wanted={r['id']:r for r in pool};codes={};solvers={}
    with tarfile.open(base.INPUT/'archives'/f'{bank.TASK}.tar.gz','r|gz') as archive:
        for member in archive:
            path=PurePosixPath(member.name)
            if not member.isfile():continue
            if path.name=='dojo_config.json' and str(path.parent) in configs:
                raw=archive.extractfile(member).read();known=configs[str(path.parent)]
                if base.sha(raw)!=known['sha256'] or base.SECRET.search(raw):raise ValueError('source config')
                solvers[base.sha(str(path.parent).encode())[:16]]=json.loads(raw)['solver']
            elif path.name in ('journal.jsonl','journal_for_unselected.jsonl') and str(path.parent.parent) in configs:
                for line in archive.extractfile(member):
                    if base.SECRET.search(line):raise ValueError('credential-first')
                    row=json.loads(line)
                    if row.get('id') not in wanted:continue
                    raw=(row.get('code') or '').encode()
                    if row['id'] in codes or base.sha(raw)!=wanted[row['id']]['code_sha256']:raise ValueError('code identity')
                    if bank.re.search(rb'/prepared/private|/data/private|/research/[^\s\"\x27]+',raw):raise ValueError('unapproved paths')
                    codes[row['id']]=raw
    if len(codes)!=12 or set(solvers)!=set(runseed):raise ValueError('complete new sources')
    sys.path.insert(0,str(rt.ASSETS/'source/src'))
    from dojo.core.solvers.utils.response import extract_code
    from run_comparison_frozen_reward_20260919 import model_files,interpreter_receipt
    model=model_files();interpreter=interpreter_receipt();description=(base.BASE/'mle-bench-data'/bank.TASK/'prepared/public/description.md').read_bytes()
    if rt.SHAPES.search(description):raise ValueError('public description security')
    cases=[]
    for run,seed in sorted(runseed.items(),key=lambda item:item[1]):
        cfg=solvers[run]
        if cfg['use_test_score'] is not False or cfg['max_debug_depth']!=20:raise ValueError('native contract')
        group=sorted((r for r in pool if r['run']==run),key=lambda r:(r['creation_time'],r['id']))
        if len(group)!=6:raise ValueError('six slots')
        programs=[]
        for slot,row in enumerate(group):
            code=extract_code(codes[row['id']].decode());programs.append(dict(slot=slot,node=row['id'],code=code,code_sha256=base.sha(code.encode())))
        cases.append(dict(seed=seed,run=run,programs=programs,model=model,interpreter=interpreter,description=description.decode(),
            operator=copy.deepcopy(cfg['operators']['debug']),analysis_operator=copy.deepcopy(cfg['operators']['analyze']),
            analysis_sampling={k:cfg['operators']['analyze']['llm']['generation_kwargs'].get(k) for k in ('temperature','top_p')},
            solver={k:cfg[k] for k in ('available_packages','execution_timeout','step_limit','data_preview')},debug_memory=cfg['debug_memory']))
    return cases

def score(root):
    p=driver.check(root);cases=rt.read(root/'inputs.private.json')['cases']
    from run_comparison_frozen_reward_20260919 import GPU_PYTHON,SOURCE,model_files
    if sys.executable!=str(GPU_PYTHON) or not os.environ.get('SLURM_STEP_ID','').isdigit():raise ValueError('dedicated critic interpreter/step')
    if rt.read(root/'launch.json')['job']!=os.environ['SLURM_JOB_ID']:raise ValueError('allocation')
    for k in tuple(os.environ):
        if bank.re.search(r'(?i)(api.?key|primary_key|token|password|secret)',k):os.environ.pop(k,None)
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHON_DOTENV_DISABLED='1',OMP_NUM_THREADS='6',TOKENIZERS_PARALLELISM='false')
    if any(c['model']!=model_files() for c in cases):raise ValueError('frozen model drift')
    import torch
    if torch.cuda.device_count()!=1 or '3090' not in torch.cuda.get_device_name(0):raise ValueError('one RTX3090')
    torch.manual_seed(20260920);package=types.ModuleType('order_frozen_reward');package.__path__=[str(SOURCE)];sys.modules[package.__name__]=package
    for name in ('bradley_terry_evaluation','bradley_terry_server'):
        spec=importlib.util.spec_from_file_location(package.__name__+'.'+name,SOURCE/(name+'.py'));module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    start=time.monotonic();service=sys.modules[package.__name__+'.bradley_terry_server'];m=cases[0]['model'];scorer=service.RewardScorer(m['adapter'],offline_base_dir=m['offline_base'])
    if scorer.max_len!=16384 or scorer.head_frac!=.25 or scorer.task_cond is not True or scorer.model.training:raise ValueError('encoder')
    if any(v.device.type!='cuda' or v.dtype!=torch.bfloat16 for v in scorer.model.parameters()):raise ValueError('dtype/offload')
    load=time.monotonic()-start;selections=[]
    with torch.inference_mode():
        for case in cases:
            scores={};started=time.monotonic()
            for program in case['programs']:
                if hashlib.sha256(program['code'].encode()).hexdigest()!=program['code_sha256']:raise ValueError('code drift')
                scores[program['slot']]=bank.score_one(scorer,bank.TASK,program['code'])
            selections.append(dict(seed=case['seed'],scores={str(k):v for k,v in scores.items()},query_seconds=time.monotonic()-started,**select_pair(case['programs'],scores,case['seed'])))
    rt.write(root/'policy-selections.json',dict(load_seconds=load,selections=selections,utc=rt.utc(),job=os.environ['SLURM_JOB_ID']))

def episode(root,index,cpu_only=False):
    ep=root/f'{"cpu-pool-episode" if cpu_only else "episode"}-{index}';start=rt.read(ep/'start.json');lane=start['lane'];driver.lane_setup(root,lane)
    os.environ['FORETS_CURRENT_POOL_ROOT']=str(ep);case=rt.read(root/'inputs.private.json')['cases'][start['seed']-1]
    if cpu_only:selection=select_pair(case['programs'],{p['slot']:float(6-p['slot']) for p in case['programs']},case['seed'])
    else:selection=next(r for r in rt.read(root/'policy-selections.json')['selections'] if r['seed']==case['seed'])
    from dojo.core.solvers.utils import data_preview
    from dojo.core.solvers.utils.response import extract_code,extract_text_up_to_code
    from dojo.core.solvers.utils.journal import Journal,Node
    from dojo.core.solvers.utils.metric import WorstMetricValue
    preview=data_preview.generate(rt.BASE/'mle-bench-data'/bank.TASK/'prepared/public')
    if rt.SHAPES.search(preview.encode()):raise ValueError('preview')
    journal=Journal();parent=Node(code='',plan='',parents=[],is_buggy=True,metric=WorstMetricValue());journal.append(parent)
    deadline=start['monotonic']+driver.EPISODE;states={};actions=[];best=None;first_valid=None;status='schedule_complete'
    def remaining():return deadline-time.monotonic()
    async def run():
        nonlocal best,first_valid,status
        completed=[]
        for kind,slot in schedule(selection,start['cache']):
            if kind=='repair' and not states[slot].is_buggy:completed.append([kind,slot]);continue
            last=states.get(slot,parent)
            for depth in ([0] if kind=='execute' else range(1,21)):
                if remaining()<=1:status='deadline';break
                i=len(actions);action=dict(kind=kind,slot=slot,depth=depth,started_seconds=time.monotonic()-start['monotonic']);accepted=False
                try:
                    if kind=='execute':program=next(p for p in case['programs'] if p['slot']==slot);code=program['code'];plan=''
                    else:
                        answer,info=await driver.call_native(case,'debug',lane,slot*100+depth,remaining(),last,journal,preview)
                        rt.write(ep/f'generation-{i}.private.json',dict(answer=answer,info=info));action['generation_usage']=info.get('usage')
                        if (info.get('usage') or {}).get('finish_reason')=='length':
                            action['status']='truncated';actions.append(action);rt.write(ep/f'action-{i}.json',action);break
                        code=extract_code(answer);plan=extract_text_up_to_code(answer)
                        if not code.strip():raise ValueError('no complete generated code')
                    if rt.SHAPES.search(code.encode()):raise ValueError('code security')
                    if remaining()<=1:status='deadline';break
                    (ep/f'code-{i}.private.py').write_text(code);action['code_sha256']=hashlib.sha256(code.encode()).hexdigest()
                    node=Node(code=code,plan=plan,parents=[parent if kind=='execute' else last],is_buggy=True,metric=WorstMetricValue(),operators_used=['draft' if kind=='execute' else 'debug'])
                    result,submission,binding=driver.execute(ep,code,i,remaining());node.absorb_exec_result(result)
                    action.update(exit_code=result.exit_code,timed_out=result.timed_out,submission_sha256=submission,binding_sha256=binding)
                    if remaining()<=1:status='deadline';break
                    try:
                        response,info=await driver.call_native(case,'analyze',lane,slot*100+depth,remaining(),node,journal,preview)
                        rt.write(ep/f'analysis-{i}.private.json',dict(response=response,info=info));action['analysis_status']='returned'
                    except Exception as exc:
                        # Exactly MCTS.parse_eval_result's _analyze exception rule.
                        response={};action.update(analysis_status='failed_native_empty_response',analysis_error_type=type(exc).__name__)
                    accepted=driver.apply_native(node,result,response,lower_is_better=False) and bool(submission) and not result.timed_out
                    journal.append(node);last=node;states[slot]=node;elapsed=time.monotonic()-start['monotonic']
                    accepted=accepted and elapsed<=driver.EPISODE and type(node.metric.value) in (int,float) and math.isfinite(node.metric.value)
                    action.update(status='returned',native_accepted=accepted,internal_metric=node.metric.value if accepted else None,completed_seconds=elapsed)
                    actions.append(action);rt.write(ep/f'action-{i}.json',action)
                    if accepted:
                        if first_valid is None:first_valid=elapsed;rt.write(ep/'first-accepted.json',dict(action_index=i,accepted_seconds=elapsed))
                        if best is None or node.metric.value>best:
                            best=node.metric.value;incumbent=dict(action_index=i,internal_metric=best,accepted_seconds=elapsed,code_sha256=action['code_sha256'],submission_sha256=submission)
                            rt.write(ep/f'incumbent-decision-{i}.json',incumbent);tmp=ep/f'incumbent-current-{i}.json';rt.write(tmp,incumbent);os.replace(tmp,ep/'incumbent.json')
                except Exception as exc:
                    status='deadline' if remaining()<=1 else 'unknown';action.update(status=status,error_type=type(exc).__name__)
                    if len(actions)==i:actions.append(action);rt.write(ep/f'action-{i}.json',action)
                if status!='schedule_complete' or accepted:break
            if status!='schedule_complete':break
            completed.append([kind,slot])
        return dict(status=status,source_seed=case['seed'],actions=len(actions),completed_stages=completed,first_valid_seconds=first_valid,
            native_accepted=best is not None,elapsed_seconds=time.monotonic()-start['monotonic'])
    rt.write(ep/'finished.json',asyncio.run(run()))

def cpu(root):
    driver.check(root);cases=rt.read(root/'inputs.private.json')['cases'];outcomes=[]
    bridge_spec=importlib.util.spec_from_file_location('cpu_pool_bridge',root/'forets_current_pool_20260912.py')
    bridge=importlib.util.module_from_spec(bridge_spec);bridge_spec.loader.exec_module(bridge)
    original_read=rt.read
    with patch.object(rt,'read',lambda path:{'job':'cpu-only'} if path==root/'execution-claim.json' else original_read(path)):
        bound=bridge.binding_context(dict(FORETS_CURRENT_POOL_ROOT=str(root/'episode-0'),DOJO_WORKER_IDENTITY_PATH=str(root/'episode-0/identity-0.json'),SLURM_JOB_ID='cpu-only'))
    assert bound==root/'episode-0/identity-0.native-binding.json'
    from run_comparison_frozen_reward_20260919 import SOURCE
    tree=ast.parse((SOURCE/'bradley_terry_server.py').read_bytes())
    scorer_cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='RewardScorer')
    assert any(isinstance(n,ast.FunctionDef) and n.name=='score_batch' for n in scorer_cls.body)
    delivered=[]
    class MockScorer:
        def score_batch(self,pairs):
            assert len(pairs)==1 and pairs[0][0]==bank.TASK
            delivered.append(hashlib.sha256(pairs[0][1].encode()).hexdigest());return [.5]
    for case in cases:
        for program in case['programs']:bank.score_one(MockScorer(),bank.TASK,program['code'])
    assert delivered==[p['code_sha256'] for c in cases for p in c['programs']]
    for index in range(4):
        pair=index//2;lane=index%2;case=cases[pair];ready_first=lane==pair;driver.lane_setup(root,lane)
        import dojo.core.solvers.llm_helpers.backends.lite_llm as backend
        from dojo.core.solvers.utils import data_preview
        selection=select_pair(case['programs'],{p['slot']:float(6-p['slot']) for p in case['programs']},case['seed'])
        ep=root/f'cpu-pool-episode-{index}';ep.mkdir();rt.write(ep/'start.json',dict(seed=pair+1,lane=lane,cache=ready_first,monotonic=time.monotonic()))
        seen=[];last_slot=None;last_success=False;requests=[]
        def execute(where,code,i,left):
            nonlocal last_slot,last_success
            candidates=[p['slot'] for p in case['programs'] if p['code']==code]
            last_slot=candidates[0] if candidates else None;seen.append(['execute',last_slot] if candidates else ['repair',None])
            last_success=last_slot not in selection['chosen']
            return types.SimpleNamespace(term_out=['CPU'],exit_code=0 if last_success else 1,timed_out=False,exec_time=.01),'f'*64 if last_success else None,'e'*64
        async def completion(**kwargs):
            assert kwargs['base_url']==f'http://127.0.0.1:{8000+lane}/v1' and 'max_tokens' not in kwargs
            assert kwargs['max_retries']==kwargs['num_retries']==0
            requests.append('analyze' if 'response_format' in kwargs else 'debug')
            if 'response_format' in kwargs:text=json.dumps(dict(is_bug=not last_success,metric=.7 if last_success else None,summary='CPU_ONLY'))
            else:text='```python\npass #CPU_DEBUG\n```'
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=text),finish_reason='stop')],to_dict=lambda:{'usage':{'prompt_tokens':1,'completion_tokens':1}})
        with patch.object(backend,'completion_fn',completion),patch.object(driver,'execute',execute),patch.object(data_preview,'generate',lambda _:'CPU_PREVIEW'):
            episode(root,index,True)
        closed=rt.read(ep/'finished.json');inc=rt.read(ep/'incumbent.json')
        expected=[['execute',slot] if kind=='execute' else ['repair',None] for kind,slot in schedule(selection,ready_first)]
        assert seen==expected and closed['status']=='schedule_complete' and closed['completed_stages']==[list(x) for x in schedule(selection,ready_first)]
        assert inc['internal_metric']==.7 and len(requests)==10
        outcomes.append(dict(index=index,source_seed=case['seed'],ready_first=ready_first,actions=len(seen),same_full_action_set=True))
    subprocess.run(['bash','-n',str(root/'run.sbatch')],check=True,timeout=10)
    rt.write(root/'cpu.json',dict(status='PASS_FOUR_NATIVE_FULL_SCHEDULES',cases=outcomes,actual_binding_bridge_checked=True,actual_scorer_interface_checked=True,prepared_sha256=rt.sha(root/'prepared.json'),real_calls=0))

def controller(root):
    driver.check(root);start=time.monotonic();env=dict(os.environ)
    for key in ('CUDA_VISIBLE_DEVICES','SLURM_STEP_ID','SLURM_STEP_GPUS','GPU_DEVICE_ORDINAL'):env.pop(key,None)
    with (root/'critic.private.log').open('xb') as log:
        code=subprocess.call(['srun','--exclusive','--ntasks=1','--cpus-per-task=6','--gres=gpu:1','--time=00:15:00',str(bank.GPU_PYTHON),'-B',str(root/SCRIPT),'score','--root',str(root)],env=env,stdout=log,stderr=log)
    elapsed=time.monotonic()-start;rt.write(root/'critic-stage.json',dict(returncode=code,elapsed_seconds=elapsed,utc=rt.utc()))
    if code or not (root/'policy-selections.json').exists():raise RuntimeError('critic stage failed; no episodes')
    driver.CAP=6000-math.ceil(elapsed);driver.controller(root)

if __name__=='__main__':
    os.umask(0o077);configure();p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','submit','controller','score','server','bounded-worker','episode']);p.add_argument('--root',type=Path);p.add_argument('--commit');p.add_argument('--lane',type=int);p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='prepare':driver.prepare(a.commit)
    elif a.mode=='submit':driver.submit(a.root)
    elif a.mode=='server':driver.check(a.root);rt.ROOT=a.root/f'lane-{a.lane}';rt.server()
    elif a.mode=='bounded-worker':
        start=rt.read(a.root/f'episode-{a.index}/start.json');left=max(1,start['monotonic']+driver.EPISODE-time.monotonic())
        raise SystemExit(subprocess.call(['timeout','--signal=TERM','--kill-after=10s',str(left)+'s',str(rt.PYTHON),'-B',str(a.root/SCRIPT),'episode','--root',str(a.root),'--index',str(a.index)]))
    elif a.mode=='episode':episode(a.root,a.index)
    else:globals()[a.mode](a.root)
