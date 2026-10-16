"""Independent fixed-budget32-run quota-pooling baseline qualification.

Not a retry/continuation of selective sharing. Every execution GPU remains
exclusive in BOTH conditions; the sole intervention is generation eligibility.
"""
import argparse,json,os,subprocess
from pathlib import Path
import selective_trial_20261017 as common
import generation_quota_policy_20261017 as quota

R=Path('/research/d7/spc/yzyang4/scheduling-generation-quota-20261017-v1')
ORDER=('partitioned','pooled','pooled','partitioned')
NAME=Path(__file__).name
read,write,sha=common.read,common.write,common.sha

def schedule():
    return [dict(index=8*b+2*l+k,block=b,lane=l,slot=2*l+k,repeat=b//2,arm='old_fast',
        pool_mode='shared',quota_mode=mode,task=t,seed=217901+100*(b//2)+2*l+k)
        for b,mode in enumerate(ORDER) for l in range(4) for k,t in enumerate(common.original.base.c.trial.TASKS)]

def scientific_metadata():
    return dict(prior_failures=[],new_window_gpu_seconds_cap=36000,combined_gpu_seconds_cap=36000,
        accounting_scope='The legacy new_window/combined cap fields bound this independent allocation only, NOT the entire six-hour user session. Session accounting separately sums closed18987, actual18997 and this batch including failures. No third GPU batch is planned in this window.',
        staging_note='Independent quota baseline, frozen before observing selective32quality. Both arms keep execution sharedFIFO cap1. Not reopening any closed experiment or recovering selective/pairing failures.',
        approval='User2026-10-17HK02:49 approves bounded autonomous six-hour experiments.32=2knownDEV tasks*4pairedseeds*2conditions*2reversepoolcomparisons;2service+4execution3090,<=6000s/10GPUh inclusive of preparation on allocation, service, failures, idle and cleanup. NoAPI/base training/retries; submit only after prior allocation closes and window permits.',
        primary='Task-pool best pristineDEV timely returned solution within1020s per trajectory including common incumbent; all32denominator, task/pool medians/sampleSD, native-selected separately. Not32independent treatment replicates.',
        single_change='Generation eligibility: partitioned two permits per task versus pooled four permits total. SAME global completion-first/FIFO arbitration among eligible requests in BOTH arms. Maximum4 concurrent model requests, same2service+4execution cards, model/effort/token caps/start/history/CPU/images/time remain fixed. Both execution pools are cap1 sharedFIFO; no selective/dualGPUsharing.',
        common_execution_change='Same original-image CUDA/device qualification, fixedCPU, fatal-readiness propagation and worker closure stop as selective32. New common global request arbiter removes cross-task process-race tie-breaking in BOTH arms, so neither condition is an exact replay of older independently arbitrated per-task quotas.',
        advance='All32complete and exactinput/isolation/queue/cleanup/wholecost pass; pooled actual borrows in BOTH pools, no model concurrency above4. Pooled Denoise task-pool best improves partitioned by>=.001 in BOTH reverse comparisons; Aerial best nondeclines BOTH. No pooled rescue, replacement or newseed follow-up if false.',
        stop='Fixed32 only. Ordinary candidate failure remains within completed searches. Infrastructure/worker/input/namespace/cleanup failure stops later pools. No retry/oldroot reopening or old budget reuse.',
        rationale='Closed18807 independent observed-state integration found123.56-287.05seconds per1180s pool with queued requests blocked by per-task2while totalactive<4.408vLLM telemetry samples had maxRunning4,Waiting0,KVcache<=13.3percent. Observational eligibility opportunity, not proof of spare compute, saved time or quality. New comparison keeps total4, so no proposed8request-capacity extrapolation.',
        limitation='Work-conserving quota pooling is an established baseline, NOT algorithm novelty or MARS/SchedMate reproduction. Two reusedDEVtasks, two reverse comparisons share one service. Task service allocation can shift; report both task results and preserve per-run wall budget. Warm construction is sunk/common, not from-scratch savings. Do not combine effects with selective-sharing batch.',
        independent_predecessor=dict(root='/research/d7/spc/yzyang4/scheduling-colocation-20261016-v1',job='18807',sealed=True,budget_reused=False,
            quota_evidence_sha256='77952b1eb54995f4aa19e8e81ef0278e6b60a760f60bb167b8a1506145bee096'))

def preflight():
    p=common.original.base.c.trial.check()
    assert p['planned']==32 and p['allocation_seconds']==6000 and p['node']=='gpu3'
    assert 'require_completed_workers' in common.original.executor.__code__.co_names
    for row in schedule():
        ref=next(r for r in schedule() if r['seed']==row['seed'] and r['quota_mode']=='partitioned')
        a,b=(read(R/f"configs/{r['index']}.json") for r in (row,ref))
        assert common.original.base.c.trial.t.scientific(a)==common.original.base.c.trial.t.scientific(b)
        assert row['pool_mode']=='shared' and a['solver']['time_limit_secs']==1020 and a['interpreter']['timeout']==300
        for role,op in a['solver']['operators'].items():
            kw=op['llm']['generation_kwargs'];assert op['llm']['client']['model_id']=='qwen3.8-27b'
            assert kw['reasoning_effort']==common.original.policy.effort('old_fast',role)
            assert kw['max_tokens']==(8192 if role=='analyze' else 32768)
    matrix=read(R/'input-matrix/summary.safe.json')
    assert matrix['passed']==matrix['assigned']==32 and matrix['exact_input_gate']
    py=str(common.original.base.c.trial.PY)
    subprocess.run([py,'-B','-m','unittest','test_generation_quota_policy_20261017','test_pool_stop_contract_20261017','test_fixed_public_preview_20261014'],cwd=R,check=True)
    subprocess.run([py,'-B',str(R/'generation_quota_production_gate_20261017.py'),str(R)],cwd=R,check=True)
    write(R/'cpu.json',dict(plan_sha256=sha(R/'plan.json'),configs=32,exact_inputs=True,no_gpu=True))
    write(R/'preflight.json',dict(source_commit=p['source_commit'],plan_sha256=sha(R/'plan.json'),configs=32,exact_input_gate=True,gpu_hours_cap=10,no_gpu=True,no_model_calls=True))
    print(json.dumps(read(R/'preflight.json')))

def configure():
    common.R=R;common.NAME=NAME;common.__file__=__file__;common.ORDER=('shared',)*4
    common.schedule=schedule;common.scientific_metadata=scientific_metadata;common.preflight=preflight
    common.configure()
    common.original.NAMES+=('selective_trial_20261017.py','generation_quota_policy_20261017.py',
        'generation_quota_readout_20261017.py','generation_quota_production_gate_20261017.py','test_generation_quota_policy_20261017.py')
    ready_install=common.original.install_hooks
    def hooks(row,ep,deadline):
        ready_install(row,ep,deadline)
        quota.install(row['quota_mode'])
    common.original.install_hooks=hooks;common.original.base.install_hooks=hooks

configure()
task_runtime=common.task_runtime;host=common.host
def install_hooks(row,ep,deadline):return common.original.install_hooks(row,ep,deadline)
if __name__=='__main__':
    os.umask(0o077);os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('prepare','preflight','submit','controller','service','executor','worker'))
    p.add_argument('--commit');p.add_argument('--block',type=int);p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='prepare':common.original.prepare(a.commit)
    elif a.mode=='preflight':preflight()
    elif a.mode=='submit':common.submit()
    elif a.mode=='controller':common.controller()
    elif a.mode=='service':common.original.base.c.trial.service(0)
    elif a.mode=='executor':common.original.executor(a.block)
    elif a.mode=='worker':common.original.worker(a.index)
