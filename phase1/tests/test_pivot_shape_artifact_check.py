import copy
import hashlib
import json
import pytest
from phase1.pivot_shape_artifact_check import (REPORT_ARM,PARAMETERS,ROLES,expected_plan,expected_update,
    verify_binding,verify_segment)

A='a'*64;S='b'*64;N='c'*64;M='d'*64;P='e'*64

def fixture(case='prefix1'):
    from phase1.global_local_execution_plan import digest_records
    plan,_=expected_plan();runtime={'synthetic_test':True}
    binding={'protocol':'critic-zero3-session-v1','world':2,'total_steps':2,'seed':6,'arm':'G_to_L',
        'training_contract_sha256':A,'plan_sha256':plan.sha256,'input_sha256':plan.input_sha256,
        'runtime_sha256':digest_records([runtime]),'source_sha256':S,'ds_config_sha256':'f'*64,
        'model_schema_sha256':'1'*64,'initial_optimizer_groups_sha256':'2'*64}
    step=1 if case=='prefix1' else 2;start=step-1
    receipt={'status':'CHECKPOINTED_NOT_COMPLETED' if step==1 else 'COMPLETED','sequence':2,
        'arm':REPORT_ARM,'seed':6,'plan_sha256':plan.sha256,'start_step':start,'stop_step':step,
        'source_qualification_attested_by_runner':False,'model_effect_evaluated':False,
        'contains_preprocessing_or_queue_time':False,'ranks':[]}
    contexts={};updates={};engineering={};observed={}
    for rank in (0,1):
        restore=None if start==0 else {'completed_steps':1,'cumulative_valid_tokens':4194304,
            'all_state_components_restored':True,'manifest_sha256':P,'native_cpu_adam_cache':{
                'policy':'replay_native_bias_powers_on_empty_tensors_v1','completed_steps':1,'empty_native_calls':1,
                'parameter_elements_passed':0,'python_optimizer_step_calls':0,'policy_sha256':N,'native_extension_sha256':'3'*64}}
        contexts[rank]={'protocol':'critic-training-run-v1','sequence':2,'arm':REPORT_ARM,'consumer_arm':'G_to_L',
            'seed':6,'rank':rank,'world_size':2,'plan_sha256':plan.sha256,'session_binding':binding,
            'start_step':start,'stop_step':step,'full_plan_steps':2,'checkpoint_steps':[step],
            'resume_manifest_sha256':P if start else None,'dev_or_test_reader_present':False,
            'started_at_utc':'2026-09-07T00:00:00+00:00','restore_receipt':restore}
        updates[rank]=[{**expected_update(rank,step),'update_seconds':10.0}]
        counters={'global_steps':step,'global_samples':128*step,'skipped_steps':0,
            'micro_steps':step,'micro_step_id':0,'step_applied':True}
        state={k:'4'*64 for k in ROLES}
        observed[rank]={'rank':rank,'binding':binding,'completed_steps':step,'cumulative_valid_tokens':4194304*step,
            'state':state,'counters':counters}
        engineering[rank]={'classification':'PIVOT_SIZE_SYNTHETIC_ENGINEERING_ONLY','rank':rank,
            'parameters':PARAMETERS,'state':copy.deepcopy(state),'counters':copy.deepcopy(counters),
            'runtime':runtime,'gpu':'NVIDIA RTX PRO 6000','actual_attention_backend':'flash_attention_2',
            'actual_parameter_dtypes':['torch.bfloat16'],'deterministic_algorithms_enabled':False,
            'matmul_tf32':False,'cudnn_tf32':False,'source_admission':False,'no_uninterrupted_pivot_comparison':True}
        receipt['ranks'].append({'rank':rank,'completed_steps':step,'cumulative_global_valid_tokens':4194304*step,
            'new_updates':1,'first_update_seconds':[10.0],'later_update_seconds':[],
            'saved':[{'step':step,'manifest_sha256':M,'save_seconds':2.0}],
            'segment_elapsed_seconds':13.0,'peak_allocated_bytes':1024,'peak_reserved_bytes':2048})
    return (case,receipt,contexts,updates,engineering,observed),dict(binding=binding,manifest_sha=M,
        prefix_manifest_sha=P,native_helper_sha=N,runtime=runtime)

@pytest.mark.parametrize('case',['prefix1','resume2'])
def test_complete_segment_not_full_size_parity(case):
    args,kw=fixture(case);r=verify_segment(*args,**kw)
    verify_binding(kw['binding'],approval_sha=A,source_sha=S,runtime=kw['runtime'])
    assert r['full_size_final_parity_measured'] is False and r['steady_state_updates']==0

@pytest.mark.parametrize('mutation',['missing_rank','bad_stage','repeated_update','wrong_order','wrong_digest',
    'wrong_count','nan_timing','negative_timing','wrong_checkpoint','fake_restore','wrong_native',
    'changed_saved_state','incomplete_roles','counter','dtype','backend','tf32','zero_memory','claim_effect'])
def test_segment_integrity_failures(mutation):
    args,kw=fixture('resume2');case,r,c,u,e,o=args
    if mutation=='missing_rank':r['ranks'].pop()
    elif mutation=='bad_stage':r['start_step']=0
    elif mutation=='repeated_update':u[0].append(copy.deepcopy(u[0][0]))
    elif mutation=='wrong_order':u[0][0]['source']='G'
    elif mutation=='wrong_digest':u[0][0]['consumption_receipt_sha256']='5'*64
    elif mutation=='wrong_count':u[0][0]['local_pair_visits']=63
    elif mutation=='nan_timing':u[0][0]['update_seconds']=float('nan')
    elif mutation=='negative_timing':u[0][0]['update_seconds']=-1
    elif mutation=='wrong_checkpoint':c[0]['restore_receipt']['manifest_sha256']='6'*64
    elif mutation=='fake_restore':c[0]['restore_receipt']['all_state_components_restored']=False
    elif mutation=='wrong_native':c[0]['restore_receipt']['native_cpu_adam_cache']['parameter_elements_passed']=1
    elif mutation=='changed_saved_state':e[0]['state']['master_shards']='6'*64
    elif mutation=='incomplete_roles':del o[0]['state']['numpy_rng']
    elif mutation=='counter':o[0]['counters']['micro_steps']=1
    elif mutation=='dtype':e[0]['actual_parameter_dtypes']=['torch.float32']
    elif mutation=='backend':e[0]['actual_attention_backend']='sdpa'
    elif mutation=='tf32':e[0]['matmul_tf32']=True
    elif mutation=='zero_memory':r['ranks'][0]['peak_allocated_bytes']=0
    else:r['model_effect_evaluated']=True
    with pytest.raises(ValueError):verify_segment(*args,**kw)

def test_binding_wrong_source_rejected():
    _,kw=fixture()
    with pytest.raises(ValueError):verify_binding(kw['binding'],approval_sha=A,source_sha='6'*64,runtime=kw['runtime'])

def test_postflight_does_not_import_backend_before_identity_and_artifacts():
    import ast
    import subprocess
    import sys
    from pathlib import Path
    p=subprocess.run([sys.executable,'-B','-c',
        "import sys;import phase1.scripts.verify_pivot_shape_artifacts_20260907;assert 'torch' not in sys.modules"],capture_output=True)
    assert p.returncode==0
    code=(Path(__file__).parents[1]/'scripts/verify_pivot_shape_artifacts_20260907.py').read_text()
    tree=ast.parse(code)
    main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    top_imports=[n for n in main.body if isinstance(n,ast.Import) and any(x.name=='torch' for x in n.names)]
    assert len(top_imports)==1
    assert code.index("'AUTHENTICATED.json'")<code.index('    import torch\n')<code.index('torch.load(')
    assert "mmap=(x.suffix=='.pt')" in code

@pytest.mark.parametrize('rank,step',[(0,1),(1,2)])
def test_expected_digest_matches_real_cpu_tensor_boundary(rank,step):
    torch=pytest.importorskip('torch')
    from dataclasses import asdict
    from phase1.global_local_critic_consumer import UpdateReceipt
    from phase1.global_local_batch_adapter import PackedBatch,pack_batch,observe_batch
    from phase1.pivot_zero3_shape_fixture import fixture as workload
    plan,_,encode,truth=workload();rows=[]
    for b in plan.batches:
        if b.rank!=rank or b.optimizer_step!=step-1:continue
        packed=pack_batch(plan,b,encode,truth.__getitem__,pad_id=0)
        actual=PackedBatch(tuple(map(tuple,torch.tensor(packed.input_ids).tolist())),
            tuple(map(tuple,torch.tensor(packed.attention_mask).tolist())),tuple(torch.tensor(packed.signs).tolist()))
        rows.append(observe_batch(plan,b,actual,truth.__getitem__,pad_id=0))
    event=UpdateReceipt(plan.sha256,rank,step,'G' if step==1 else 'L',0,64,2097152,128,4194304*step,
        0.00001,'deepspeed_boundary_backward',tuple(rows))
    h=hashlib.sha256(json.dumps(asdict(event),sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert h==expected_update(rank,step)['consumption_receipt_sha256']
    assert not torch.cuda.is_initialized()
