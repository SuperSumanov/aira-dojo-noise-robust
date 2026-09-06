"""Independent CPU receipt/layout checks for the fixed synthetic pivot run.

No loader, model, CUDA, training-data reader or scheduler. An orchestrator must
authenticate job/source/files and check actual checkpoint payloads separately.
Expected receipts below are comparisons, never substituted for observations.
"""
from functools import lru_cache
import hashlib
import json
import math
import re

ROLES={'model_shards','master_shards','adamw','scaler','python_rng','numpy_rng','torch_rng'}
PARAMETERS=1720577025
REPORT_ARM='ENGINEERING_SYNTHETIC_G_TO_L_NOT_DEVELOPMENT'

def require(ok,reason):
    if not ok:raise ValueError(reason)

def finite(x):return type(x) in (int,float) and math.isfinite(x) and x>=0

@lru_cache(maxsize=1)
def expected_plan():
    from phase1.pivot_zero3_shape_fixture import fixture,summary
    plan,*_=fixture();description=summary()
    require(plan.sha256=='d1fcdddc6ecb6e58d025f97ae9633b2bd5cb0390b20a05cb9cbd597e0a6e5ec6',
            'frozen_pivot_plan_changed')
    require(description['valid_tokens']==8388608 and description['steps']==2,'frozen_pivot_totals')
    return plan,description

def expected_update(rank,step):
    """Reconstruct the exact digest of observed tensor-boundary metadata."""
    require(type(rank) is int and rank in (0,1) and type(step) is int and step in (1,2),'pivot_update_address')
    plan,_=expected_plan();batches=[b for b in plan.batches if b.rank==rank and b.optimizer_step==step-1]
    require(len(batches)==8 and all(len(b.rows)==8 for b in batches),'pivot_microbatch_layout')
    consumption=[{'plan_sha256':plan.sha256,'optimizer_step':b.optimizer_step,'micro_step':b.micro_step,
        'rank':rank,'pair_keys':[r.key for r in b.rows],
        'encoded_digests':[[r.a.encoded_sha256,r.b.encoded_sha256] for r in b.rows],
        'valid_tokens':b.valid_tokens,'padded_slots':b.padded_slots} for b in batches]
    event={'plan_sha256':plan.sha256,'rank':rank,'completed_steps':step,'source':'G' if step==1 else 'L',
        'cycle':0,'local_pair_visits':64,'local_valid_tokens':2097152,'global_update_pairs':128,
        'cumulative_global_valid_tokens':step*4194304,'learning_rate':0.00001,
        'step_owner':'deepspeed_boundary_backward','consumption':consumption}
    digest=hashlib.sha256(json.dumps(event,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    result={k:v for k,v in event.items() if k not in ('plan_sha256','completed_steps','consumption')}
    result.update(step=step,consumption_receipt_sha256=digest,first_update_of_process=True)
    return result

def verify_binding(binding,*,approval_sha,source_sha,runtime):
    from phase1.global_local_execution_plan import digest_records
    plan,_=expected_plan()
    require(set(binding)=={'protocol','world','total_steps','seed','arm','training_contract_sha256',
        'plan_sha256','input_sha256','runtime_sha256','ds_config_sha256','model_schema_sha256',
        'initial_optimizer_groups_sha256','source_sha256'},'pivot_session_fields')
    expected={'protocol':'critic-zero3-session-v1','world':2,'total_steps':2,'seed':6,'arm':'G_to_L',
        'training_contract_sha256':approval_sha,'plan_sha256':plan.sha256,'input_sha256':plan.input_sha256,
        'runtime_sha256':digest_records([runtime]),'source_sha256':source_sha}
    require(all(binding.get(k)==v for k,v in expected.items()),'pivot_session_binding')
    require(all(type(binding[k]) is str and re.fullmatch('[0-9a-f]{64}',binding[k])
        for k in binding if k.endswith('sha256')),'pivot_session_digest')

def verify_counters(value,step):
    require(value=={'global_steps':step,'global_samples':128*step,'skipped_steps':0,
        'micro_steps':step,'micro_step_id':0,'step_applied':True},'pivot_engine_counters')
    require(all(type(value[k]) is int for k in value if k!='step_applied'),'pivot_counter_types')

def verify_segment(case,receipt,contexts,updates,engineering,observed,*,binding,manifest_sha,
                   prefix_manifest_sha,native_helper_sha,runtime):
    require(case in ('prefix1','resume2'),'pivot_case')
    step=1 if case=='prefix1' else 2;start=step-1;plan,_=expected_plan()
    wanted={'status':'CHECKPOINTED_NOT_COMPLETED' if step==1 else 'COMPLETED','sequence':2,
        'arm':REPORT_ARM,'seed':6,'plan_sha256':plan.sha256,'start_step':start,'stop_step':step,
        'source_qualification_attested_by_runner':False,'model_effect_evaluated':False,
        'contains_preprocessing_or_queue_time':False}
    require(set(receipt)==set(wanted)|{'ranks'} and all(receipt[k]==v for k,v in wanted.items()),'pivot_run_receipt')
    require(len(receipt['ranks'])==2 and [r['rank'] for r in receipt['ranks']]==[0,1],'pivot_rank_coverage')
    require(all(set(v)=={0,1} for v in (contexts,updates,engineering,observed)),'pivot_rank_artifacts')
    binaries=[]
    for rank in (0,1):
        ctx=contexts[rank]
        fixed={'protocol':'critic-training-run-v1','sequence':2,'arm':REPORT_ARM,'consumer_arm':'G_to_L',
            'seed':6,'rank':rank,'world_size':2,'plan_sha256':plan.sha256,'session_binding':binding,
            'start_step':start,'stop_step':step,'full_plan_steps':2,'checkpoint_steps':[step],
            'resume_manifest_sha256':prefix_manifest_sha if start else None,'dev_or_test_reader_present':False}
        require(set(ctx)==set(fixed)|{'started_at_utc','restore_receipt'}
            and all(ctx.get(k)==v for k,v in fixed.items()),'pivot_context_binding')
        from datetime import datetime,timedelta
        stamp=datetime.fromisoformat(ctx['started_at_utc'])
        require(stamp.tzinfo is not None and stamp.utcoffset()==timedelta(0),'pivot_timestamp')
        restore=ctx['restore_receipt']
        if start==0:require(restore is None,'unexpected_pivot_restore')
        else:
            require(set(restore)=={'completed_steps','cumulative_valid_tokens','all_state_components_restored',
                'manifest_sha256','native_cpu_adam_cache'} and restore['completed_steps']==1
                and restore['cumulative_valid_tokens']==4194304 and restore['all_state_components_restored'] is True
                and restore['manifest_sha256']==prefix_manifest_sha,'pivot_restore_identity')
            cache=restore['native_cpu_adam_cache']
            require(cache['policy']=='replay_native_bias_powers_on_empty_tensors_v1'
                and cache['completed_steps']==cache['empty_native_calls']==1
                and cache['parameter_elements_passed']==cache['python_optimizer_step_calls']==0
                and cache['policy_sha256']==native_helper_sha,'pivot_native_cache')
            require(re.fullmatch('[0-9a-f]{64}',cache['native_extension_sha256']) is not None,'pivot_native_binary')
            binaries.append(cache['native_extension_sha256'])
        require(len(updates[rank])==1,'pivot_update_count')
        u=updates[rank][0];expected=expected_update(rank,step)
        require(set(u)==set(expected)|{'update_seconds'} and all(u[k]==v for k,v in expected.items()),'pivot_consumption')
        require(finite(u['update_seconds']) and u['update_seconds']>0,'pivot_update_timing')
        obs=observed[rank];eng=engineering[rank]
        require(set(obs)=={'rank','binding','completed_steps','cumulative_valid_tokens','state','counters'}
            and obs['rank']==rank and obs['binding']==binding and obs['completed_steps']==step
            and obs['cumulative_valid_tokens']==step*4194304,'pivot_saved_observation')
        require(set(obs['state'])==ROLES and all(type(v) is str and re.fullmatch('[0-9a-f]{64}',v)
            for v in obs['state'].values()),'pivot_state_fields')
        verify_counters(obs['counters'],step)
        require(eng['classification']=='PIVOT_SIZE_SYNTHETIC_ENGINEERING_ONLY' and eng['rank']==rank
            and eng['parameters']==PARAMETERS and eng['state']==obs['state'] and eng['counters']==obs['counters']
            and eng['runtime']==runtime and 'PRO 6000' in eng['gpu'].upper()
            and eng['actual_attention_backend']=='flash_attention_2' and eng['actual_parameter_dtypes']==['torch.bfloat16']
            and type(eng['deterministic_algorithms_enabled']) is bool
            and eng['matmul_tf32'] is False and eng['cudnn_tf32'] is False
            and eng['source_admission'] is False and eng['no_uninterrupted_pivot_comparison'] is True,'pivot_engineering_scope')
        r=receipt['ranks'][rank]
        fixed_rank={'rank':rank,'completed_steps':step,'cumulative_global_valid_tokens':step*4194304,
            'new_updates':1,'first_update_seconds':[u['update_seconds']],'later_update_seconds':[]}
        require(set(r)==set(fixed_rank)|{'saved','segment_elapsed_seconds','peak_allocated_bytes','peak_reserved_bytes'}
            and all(r[k]==v for k,v in fixed_rank.items()),'pivot_rank_receipt')
        require(len(r['saved'])==1 and r['saved'][0]['step']==step
            and r['saved'][0]['manifest_sha256']==manifest_sha and finite(r['saved'][0]['save_seconds'])
            and finite(r['segment_elapsed_seconds'])
            and r['segment_elapsed_seconds']>=u['update_seconds']+r['saved'][0]['save_seconds'],'pivot_save_timing')
        require(type(r['peak_allocated_bytes']) is int and type(r['peak_reserved_bytes']) is int
            and 0<r['peak_allocated_bytes']<=r['peak_reserved_bytes'],'pivot_memory')
    require(not binaries or len(set(binaries))==1,'pivot_native_rank_drift')
    return {'case':case,'ranks':2,'step':step,'new_pair_visits':128,'new_valid_tokens':4194304,
        'state_roles_observed_each':7,'checkpoint_sha256':manifest_sha,
        'warmup_updates':2,'steady_state_updates':0,'full_size_final_parity_measured':False}
