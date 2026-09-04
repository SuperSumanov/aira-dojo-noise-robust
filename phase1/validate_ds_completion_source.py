"""Execute hash-bound library control flow against explicit non-numerical stubs.

This is NOT a DeepSpeed engine initialization, distributed numerical run, fit,
or GPU test. No Torch/Accelerate/DeepSpeed package is imported.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace as NS

from phase1.global_local_ds_completion import begin_deepspeed_update
from phase1.global_local_accelerate_update_adapter import finish_non_deepspeed_update, planned_microbatch_context
from phase1.global_local_execution_plan import BatchShape, Endpoint, Pair, PlanError
from phase1.global_local_token_budget_plan import _layout

ROOT=Path(__file__).resolve().parents[1]
ALIASED_SITE=Path('/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260903-selective/lib/python3.11/site-packages')
SITE=Path('/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260903-overlay/lib/python3.11/site-packages')
FILES={
 'accelerator':(SITE/'accelerate/accelerator.py','47088e0ab3bf21eec97e16afa14595e1db511f6ead9ab85c4eaa5f6f66fe5e61'),
 'wrapper':(SITE/'accelerate/utils/deepspeed.py','82dfa3c0ea4eb51b3a378b2886e48ed88df1d6a2e83bab986239cfacaa7a664e'),
 'engine':(SITE/'deepspeed/runtime/engine.py','e5d1e2642302fc092994dd4a4712a0d4c62c3541c632dcd93528281fd40dd1ec'),
 'legacy':(ROOT/'legacy/phase1/global_local_accelerate_update_adapter.py','26ff2a4e4e9c18530ed31c47d87d223bbaa5774a2e88ada6f0aa0ad8229720d2'),
}
PATTERN=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')


def guard():
    opened={}
    allowed={p for p,_ in FILES.values()}
    def hook(event,args):
        if event in ('subprocess.Popen','socket.connect','socket.bind','os.system'):
            raise PermissionError('no_process_or_network')
        if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)):return
        path=Path(os.fsdecode(args[0])).absolute()
        mode,flags=args[1:3]
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_APPEND|os.O_TRUNC)):
            raise PermissionError('no_file_writes')
        if path in allowed:
            if path.resolve()!=path:raise PermissionError('linked_source')
            opened[str(path)]=opened.get(str(path),0)+1
        elif path.suffix not in ('.py','.pyc'):
            raise PermissionError('unlisted_read')
    sys.addaudithook(hook)
    return opened


def extract(source, cls, name, namespace):
    tree=ast.parse(source)
    scope=tree.body if cls is None else next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls).body
    matches=[n for n in scope if isinstance(n,ast.FunctionDef) and n.name==name]
    if len(matches)!=1:raise ValueError('method_binding_failed')
    node=matches[0]
    body=ast.get_source_segment(source,node)
    # Property wrapping is applied explicitly to the extracted getter below.
    node.decorator_list=[]
    env=dict(namespace)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'<bound-library-method>','exec'),env)
    return env[name],hashlib.sha256(body.encode()).hexdigest()


def stub_engine(methods, skipped):
    raw=NS(overflow=False,step_calls=0,applied_calls=0,zero_calls=0)
    def raw_step():
        raw.step_calls+=1;raw.overflow=skipped;raw.applied_calls+=int(not skipped)
    def raw_zero():raw.zero_calls+=1
    raw.step=raw_step;raw.zero_grad=raw_zero
    noop=lambda *args,**kwargs:None
    false=lambda:False
    e=NS(optimizer=raw,global_steps=0,skipped_steps=0,micro_steps=0,global_samples=0,
        _step_applied=False,lr_scheduler=None,gradient_clipping=lambda:1.0,
        torch_autocast_z0_gradscaler=None,fp16_enabled=false,bfloat16_enabled=false,amp_enabled=false,
        zero_optimization=lambda:True,quantizer=None,compression_scheduler=NS(step=noop),
        steps_per_print=lambda:None,train_batch_size=lambda:128,inside_no_sync_ctxt=False,
        memory_breakdown=false,flops_profiler_enabled=false,global_rank=0,
        _start_timers=noop,_stop_timers=noop,engine_timers=NS(step_timers=[]),zenflow=False,
        gas_boundary_ctr=0,checkpoint_engine=NS(is_decoupled=false),eigenvalue_enabled=false,
        progressive_layer_drop=False,tput_timer=NS(stop=noop),monitor=NS(enabled=False),
        autotuning_enabled=false,wall_clock_breakdown=false,boundary=False,backward_calls=[])
    e.is_gradient_accumulation_boundary=lambda:e.boundary
    e.set_gradient_accumulation_boundary=lambda is_boundary:setattr(e,'boundary',is_boundary)
    e.backward=lambda loss,**kwargs:e.backward_calls.append(dict(loss=loss,**kwargs))
    e._take_model_step=methods['take'].__get__(e)
    e.step=methods['step'].__get__(e)
    o=type('BoundOptimizerGetter',(),{'step_was_skipped':property(methods['optimizer_skip'])})()
    o.optimizer=raw;o.__has_overflow__=True
    a=type('BoundAcceleratorGetter',(),{'optimizer_step_was_skipped':property(methods['accelerator_skip'])})()
    wrapper=NS(engine=e)
    wrapper.backward=methods['wrapper'].__get__(wrapper)
    a.distributed_type='DEEPSPEED';a.deepspeed_engine_wrapped=wrapper;a._optimizers=[o];a.sync_gradients=False
    a.gradient_state=NS(_set_sync_gradients=lambda sync:setattr(a,'sync_gradients',sync))
    return a,e,o,wrapper


def main():
    opened=guard()
    texts={}
    for name,(path,expected) in FILES.items():
        if name!='legacy' and (ALIASED_SITE/path.relative_to(SITE)).resolve()!=path:
            raise ValueError('runtime_alias_target_drift')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected or PATTERN.search(raw):raise ValueError('source_integrity_or_security')
        texts[name]=raw.decode()
    namespace={'see_memory_usage':lambda *a,**k:None,'DummyOptim':type('DummyOptim',(),{})}
    specs=[('accelerator_skip','accelerator','Accelerator','optimizer_step_was_skipped'),
        ('optimizer_skip','wrapper','DeepSpeedOptimizerWrapper','step_was_skipped'),
        ('wrapper','wrapper','DeepSpeedEngineWrapper','backward'),
        ('take','engine','DeepSpeedEngine','_take_model_step'),('step','engine','DeepSpeedEngine','step'),
        ('legacy','legacy',None,'finish_non_deepspeed_update')]
    methods,method_hashes={},{}
    for key,file,cls,name in specs:
        methods[key],method_hashes[key]=extract(texts[file],cls,name,{**namespace,'_is_deepspeed':lambda a:True})
    rows=[]
    negative_control_hits=0
    for world in (2,4):
        shape=BatchShape(world,8,8 if world==2 else 4)
        for count in (128,48,114,81):
            pairs=tuple(Pair.canonical('G',Endpoint('synthetic:'+str(i)+':a',3,'a'*64),
                        Endpoint('synthetic:'+str(i)+':b',5,'b'*64),'c'*64) for i in range(count))
            _,batches=_layout([('G',0,pairs)],shape,1)
            for rank in range(world):
                local=[b for b in batches if b.rank==rank]
                for skipped in (False,True):
                    a,e,o,wrapper=stub_engine(methods,skipped)
                    before=begin_deepspeed_update(a,e,o,max_grad_norm=1.0)
                    for i,batch in enumerate(local):
                        sync=i==len(local)-1
                        with planned_microbatch_context(a,e,synchronize=sync):
                            wrapper.backward(1.0,sync_gradients=a.sync_gradients,scale_wrt_gas=False)
                        if e.global_steps!=int(sync):raise ValueError('source_boundary_mismatch')
                    old=methods['legacy'](a,e,o,max_grad_norm=1.0)
                    new=finish_non_deepspeed_update(a,e,o,max_grad_norm=1.0,deepspeed_before=before)
                    if old['optimizer_step_skipped'] is not False or new['optimizer_step_skipped'] is not skipped:
                        raise ValueError('skip_regression')
                    if e.optimizer.step_calls!=1 or e.optimizer.applied_calls!=int(not skipped):
                        raise ValueError('stub_step_accounting')
                    if any(call['scale_wrt_gas'] is not False for call in e.backward_calls):raise ValueError('kwargs_lost')
                    negative_control_hits+=int(skipped and not old['optimizer_step_skipped'])
                    rows.append(dict(world=world,rank=rank,seed=6,planned_update_pairs=count,
                        local_pair_counts=[len(b.rows) for b in local],simulated_overflow=skipped,
                        attempted_updates=e.global_steps,stub_applied_updates=e.optimizer.applied_calls,
                        engine_reported_samples=e.global_samples,legacy_reported_skip=old['optimizer_step_skipped'],**new))
    fault_checks=[]
    for fault in ('missing_step','double_step','skipped_counter_drift'):
        a,e,o,wrapper=stub_engine(methods,False)
        before=begin_deepspeed_update(a,e,o,max_grad_norm=1.0)
        step=e.step
        if fault=='missing_step':e.step=lambda:None
        if fault=='double_step':e.step=lambda:(step(),step())
        with planned_microbatch_context(a,e,synchronize=True):wrapper.backward(1.0,sync_gradients=True)
        if fault=='skipped_counter_drift':e.skipped_steps+=1
        try:finish_non_deepspeed_update(a,e,o,max_grad_norm=1.0,deepspeed_before=before)
        except PlanError:fault_checks.append(fault)
        else:raise ValueError('fault_not_detected')
    for name,(path,expected) in FILES.items():
        if name!='legacy' and (ALIASED_SITE/path.relative_to(SITE)).resolve()!=path:
            raise ValueError('runtime_alias_target_drift')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('source_drift')
    return dict(status='SOURCE_CONTROL_FLOW_VERIFIED_NOT_NUMERICAL_DEEPSPEED',
        runtime_file_sha256={k:s for k,(_,s) in FILES.items()},method_sha256=method_hashes,
        cases=rows,case_count=len(rows),legacy_false_success_detected_cases=negative_control_hits,
        injected_faults_detected=fault_checks,data_open_counts=opened,
        selective_runtime_alias_and_exact_overlay_target_bound=True,
        imported_gpu_training_libraries=False,real_backend_executed=False,
        runtime_sources_are_executed_with_explicit_stubs=True,real_data_opened=False,
        model_fits=0,new_gpu_jobs=0,api_calls=0,protected_cohort_opened=False)


if __name__=='__main__':
    try:print(json.dumps(main(),sort_keys=True,allow_nan=False))
    except Exception as exc:
        reason=str(exc)
        print(json.dumps(dict(status='FAILED_CLOSED',exception_type=type(exc).__name__,
            safe_reason=reason if re.fullmatch('[a-z_]+',reason) else 'details_withheld')))
        raise SystemExit(1)
