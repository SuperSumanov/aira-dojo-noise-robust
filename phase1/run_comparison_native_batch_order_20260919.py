"""Same original chosen batch, same repair; only change action order."""
import argparse,ast,asyncio,hashlib,json,math,os,subprocess,time,types
from pathlib import Path
from unittest.mock import patch
import run_comparison_pizza_online_20260919 as pizza
driver=pizza.driver;rt=driver.rt

def configure():
    pizza.configure();pizza.CHOOSE_ORIGINAL_SECOND=True
    driver.SCRIPT=Path(__file__).name;driver.ROOT_PREFIX='comparison-native-batch-order-20260919-'
    driver.CONTEXT_MODULE='run_comparison_native_batch_order_20260919'
    driver.PLAN='comparison_native_batch_order_plan_20260919.json'
    driver.FILES=(driver.SCRIPT,driver.PLAN,'run_comparison_online_continuation_20260919.py','run_comparison_pizza_online_20260919.py','local_generator_runtime_20260914.py','run_comparison_live_debug_20260919.py','comparison_full_deadline_policy_20260919.py')

def binding_context(env):configure();return driver.binding_context(env)

def stages(sibling_first):return ('sibling','repair') if sibling_first else ('repair','sibling')

def improves(metric,best):
    if type(metric) not in (int,float) or not math.isfinite(metric):return False
    return best is None or metric>best

def cpu_debug_code(code):
    tree=ast.parse(code)
    return len(tree.body)==1 and isinstance(tree.body[0],ast.Pass)

def keep_incumbent(ep,value,metric,previous):
    if not improves(metric,previous):return previous
    row=dict(value,internal_metric=metric)
    rt.write(ep/f'incumbent-decision-{value["action_index"]}.json',row)
    temp=ep/f'incumbent-current-{value["action_index"]}.json';rt.write(temp,row)
    os.replace(temp,ep/'incumbent.json')
    return metric

def episode(root,index,cpu_only=False):
    ep=root/f'{"batch-cpu-episode" if cpu_only else "episode"}-{index}';start=rt.read(ep/'start.json');lane=start['lane'];driver.lane_setup(root,lane)
    os.environ['FORETS_CURRENT_POOL_ROOT']=str(ep)
    case=rt.read(root/'inputs.private.json')['cases'][start['seed']-1]
    from dojo.core.solvers.utils import data_preview
    from dojo.core.solvers.utils.response import extract_code,extract_text_up_to_code
    from dojo.core.solvers.utils.journal import Node
    from dojo.core.solvers.utils.metric import WorstMetricValue
    preview=data_preview.generate(rt.BASE/'mle-bench-data'/driver.TASK/'prepared/public')
    if rt.SHAPES.search(preview.encode()):raise ValueError('preview security')
    journal,parent,last=driver.new_journal(case);deadline=start['monotonic']+driver.EPISODE
    def remaining():return deadline-time.monotonic()
    async def run():
        nonlocal last
        actions=[];best=None;status='batch_complete';first_valid=None;completed=[];repair_context_exhausted=False
        for stage in stages(start['cache']):
            for depth in ([0] if stage=='sibling' else range(1,21)):
                if remaining()<=1:status='deadline';break
                i=len(actions);accepted=False
                action=dict(depth=depth,kind=stage,started_seconds=time.monotonic()-start['monotonic'])
                try:
                    if stage=='sibling':code=case['cache']['code'];plan=''
                    else:
                        answer,info=await driver.call_native(case,'debug',lane,depth,remaining(),last,journal,preview)
                        rt.write(ep/f'generation-{depth}.private.json',dict(answer=answer,info=info));action['generation_usage']=info.get('usage')
                        if (info.get('usage') or {}).get('finish_reason')=='length':
                            action['status']='truncated';status='generation_incomplete';actions.append(action);rt.write(ep/f'action-{i}.json',action);break
                        code=extract_code(answer);plan=extract_text_up_to_code(answer)
                        if not code.strip():raise ValueError('no complete code')
                    if rt.SHAPES.search(code.encode()):raise ValueError('code security')
                    if remaining()<=1:status='deadline';break
                    (ep/f'code-{i}.private.py').write_text(code)
                    action['code_sha256']=hashlib.sha256(code.encode()).hexdigest()
                    node=Node(code=code,plan=plan,parents=[parent if stage=='sibling' else last],is_buggy=True,metric=WorstMetricValue(),operators_used=['draft' if stage=='sibling' else 'debug'])
                    result,submission,binding=driver.execute(ep,code,i,remaining());node.absorb_exec_result(result)
                    action.update(exit_code=result.exit_code,timed_out=result.timed_out,submission_sha256=submission,binding_sha256=binding)
                    if remaining()<=1:status='deadline';break
                    response,info=await driver.call_native(case,'analyze',lane,depth,remaining(),node,journal,preview)
                    rt.write(ep/f'analysis-{depth}.private.json',dict(response=response,info=info));action['analysis_status']='returned'
                    accepted=driver.apply_native(node,result,response,lower_is_better=False) and bool(submission) and not result.timed_out
                    journal.append(node);elapsed=time.monotonic()-start['monotonic']
                    accepted=accepted and elapsed<=driver.EPISODE and improves(node.metric.value,None)
                    action.update(status='returned',native_accepted=accepted,completed_seconds=elapsed,internal_metric=node.metric.value if accepted else None)
                    # Action must be durable before its incumbent is exposed to the closed reader.
                    actions.append(action);rt.write(ep/f'action-{i}.json',action)
                    if accepted:
                        if first_valid is None:
                            first_valid=elapsed;rt.write(ep/'first-accepted.json',dict(action_index=i,accepted_seconds=elapsed))
                        best=keep_incumbent(ep,dict(action_index=i,submission_sha256=submission,accepted_seconds=elapsed,code_sha256=action['code_sha256']),node.metric.value,best)
                    if stage=='repair':last=node
                except Exception as exc:
                    status='deadline' if remaining()<=1 else 'unknown'
                    action.update(status=status,error_type=type(exc).__name__)
                    if len(actions)==i:actions.append(action);rt.write(ep/f'action-{i}.json',action)
                if status!='batch_complete' or accepted:break
            if status=='generation_incomplete' and stage=='repair':
                # An incomplete repair is not permission to discard the ready
                # second original candidate when its execution time remains.
                repair_context_exhausted=True;status='batch_complete'
            if status!='batch_complete':break
            completed.append(stage)
        return dict(status=status,actions=len(actions),native_accepted=best is not None,first_valid_seconds=first_valid,completed_stages=completed,repair_context_exhausted=repair_context_exhausted,elapsed_seconds=time.monotonic()-start['monotonic'])
    rt.write(ep/'finished.json',asyncio.run(run()))

def cpu(root):
    driver.cpu(root)
    import dojo.core.solvers.llm_helpers.backends.lite_llm as backend
    from dojo.core.solvers.utils import data_preview
    outcomes=[]
    for i in range(6):
        lane=i%2;ep=root/f'batch-cpu-episode-{i}';ep.mkdir();sibling_first=lane==i//2
        if i>=4:sibling_first=bool(i%2)
        rt.write(ep/'start.json',dict(seed=i//2+1 if i<4 else 1,lane=lane,cache=sibling_first,monotonic=time.monotonic()))
        seen=[];debugs=0;last_kind=None;last_success=False
        def fake_execute(where,code,index,remaining):
            nonlocal last_kind,last_success,debugs
            last_kind='repair' if cpu_debug_code(code) else 'sibling'
            if last_kind=='repair':debugs+=1
            last_success=last_kind=='sibling' or debugs==2;seen.append(last_kind)
            result=types.SimpleNamespace(term_out=['mock'],exit_code=0 if last_success else 1,timed_out=False,exec_time=.001)
            return result,'f'*64 if last_success else None,'e'*64
        async def complete(**kwargs):
            assert 'max_tokens' not in kwargs
            if 'response_format' in kwargs:
                metric=(.9 if i<2 else .7) if last_kind=='sibling' else .8
                text=json.dumps(dict(is_bug=not last_success,summary='CPU_ONLY',metric=metric if last_success else None))
            else:text='```python\npass #debug\n```'
            finish='length' if i>=4 and 'response_format' not in kwargs else 'stop'
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=text),finish_reason=finish)],to_dict=lambda:{'usage':{'prompt_tokens':1,'completion_tokens':1}})
        with patch.object(backend,'completion_fn',complete),patch.object(driver,'execute',fake_execute),patch.object(data_preview,'generate',lambda _:'CPU_PREVIEW'):
            episode(root,i,cpu_only=True)
        finished=rt.read(ep/'finished.json');incumbent=rt.read(ep/'incumbent.json')
        assert seen==(['sibling'] if i>=4 else (['sibling','repair','repair'] if sibling_first else ['repair','repair','sibling']))
        assert finished['completed_stages']==list(stages(sibling_first)) and finished['status']=='batch_complete'
        assert incumbent['internal_metric']==(.9 if i<2 else (.7 if i>=4 else .8))
        outcomes.append(dict(index=i,order=seen,selected_internal_metric=incumbent['internal_metric']))
    rt.write(root/'batch-cpu.json',dict(status='PASS_ACTUAL_NATIVE_BATCH_ORDER_AND_INTERNAL_SELECTION',cases=outcomes,prepared_sha256=rt.sha(root/'prepared.json'),real_model_calls=0))

if __name__=='__main__':
    os.umask(0o077);configure();parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','submit','controller','server','bounded-worker','episode']);parser.add_argument('--root',type=Path);parser.add_argument('--commit');parser.add_argument('--lane',type=int);parser.add_argument('--index',type=int);a=parser.parse_args()
    if a.mode=='prepare':
        original=driver.cpu;driver.cpu=cpu
        # cpu() calls the original common preflight, not itself.
        common_cpu=original
        def combined(root):
            driver.cpu=common_cpu
            cpu(root)
        driver.cpu=combined;driver.prepare(a.commit)
    elif a.mode=='submit':
        if rt.read(a.root/'batch-cpu.json')['prepared_sha256']!=rt.sha(a.root/'prepared.json'):raise ValueError('batch preflight')
        driver.submit(a.root)
    elif a.mode=='server':driver.check(a.root);rt.ROOT=a.root/f'lane-{a.lane}';rt.server()
    elif a.mode=='bounded-worker':
        start=rt.read(a.root/f'episode-{a.index}/start.json');left=max(1,start['monotonic']+driver.EPISODE-time.monotonic())
        raise SystemExit(subprocess.call(['timeout','--signal=TERM','--kill-after=10s',str(left)+'s',str(rt.PYTHON),'-B',str(a.root/driver.SCRIPT),'episode','--root',str(a.root),'--index',str(a.index)]))
    elif a.mode=='episode':episode(a.root,a.index)
    else:driver.controller(a.root)
