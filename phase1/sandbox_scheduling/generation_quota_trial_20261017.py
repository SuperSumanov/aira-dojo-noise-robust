"""Independent fixed-budget32-run quota-pooling baseline qualification.

Not a retry/continuation of selective sharing. Every execution GPU remains
exclusive in BOTH conditions; the sole intervention is generation eligibility.
"""
import argparse,json,os,subprocess
from pathlib import Path
import selective_trial_20261017 as common
import generation_quota_policy_20261017 as quota

R=Path('/research/d7/spc/yzyang4/scheduling-generation-quota-20261017-v3')
ORDER=('partitioned','pooled','pooled','partitioned')
NAME=Path(__file__).name
read,write,sha=common.read,common.write,common.sha

def schedule():
    return [dict(index=8*b+2*l+k,block=b,lane=l,slot=2*l+k,repeat=b//2,arm='old_fast',
        pool_mode='shared',quota_mode=mode,task=t,seed=217901+100*(b//2)+2*l+k)
        for b,mode in enumerate(ORDER) for l in range(4) for k,t in enumerate(common.original.base.c.trial.TASKS)]

def scientific_metadata():
    return dict(prior_failures=[],new_window_gpu_seconds_cap=36000,combined_gpu_seconds_cap=36000,
        accounting_scope='One actual independent allocation capped at36000GPUseconds. The closed previous window61849GPUseconds is NOT reused. Pending administrative predecessor19118 was cancelled with0elapsed/0allocatedTRES/no node/no steps/no workers. Report due2026-10-17UTC13:28:03; queue validity separately ends20:28:03. No second actual GPU allocation or automatic retry.',
        staging_note='Pre-start administrative supersession of never-executed19118: only root/source and queue expiry/report-time separation changed. Same original32matrix,seeds,node,hardware,budgets,arbitration and final-quality gate. One repaired quota qualification after sealed19004; no changes based on19004scores or any successor outcome.',
        approval='User2026-10-17HK18:28 explicitly requests completing the repaired quota contrast under unchanged budget/final-quality gate and stopping the recipe if no benefit; earlier user says obtain six known-compatible GPUs and finish.32=2knownDEV tasks*4pairedseeds*2conditions*2reversepoolcomparisons;2service+4execution3090,<=6000s/10GPUh inclusive of startup, failures, idle and cleanup. NoAPI/base training/retries. Three-hour reporting is NOT an allocation/queue deadline. Refuse start without CAP+600seconds before the separate20:28:03UTC queue-validity end; still report actual progress at13:28:03UTC.',
        queue_only_predecessor=dict(job='19118',root='/research/d7/spc/yzyang4/scheduling-generation-quota-20261017-v2',state='CANCELLED',gpu_seconds=0,workers_started=0,outcomes_read=False,
            receipt_sha256='77fbe0d905fb46ab4d6e9fa3f9050a761af639ac74ca5e95a44a9e076c343dba',original_plan_sha256='8d4d402365257376ba3634d21929624031f349f971c314e2aa26786c42ea147b'),
        primary='Task-pool best pristineDEV timely returned solution within1020s per trajectory including common incumbent; all32denominator, task/pool medians/sampleSD, native-selected separately. Not32independent treatment replicates.',
        single_change='Generation eligibility: partitioned two permits per task versus pooled four permits total. SAME global completion-first/FIFO arbitration among eligible requests in BOTH arms. Maximum4 concurrent model requests, same2service+4execution cards, model/effort/token caps/start/history/CPU/images/time remain fixed. Both execution pools are cap1 sharedFIFO; no selective/dualGPUsharing.',
        common_execution_change='Same original-image CUDA/device qualification, fixedCPU, fatal-readiness propagation and worker closure stop as selective32. New common global request arbiter removes cross-task process-race tie-breaking in BOTH arms, so neither condition is an exact replay of older independently arbitrated per-task quotas.',
        advance='All32complete and exactinput/isolation/queue/cleanup/wholecost pass; pooled actual borrows in BOTH pools, no model concurrency above4. Pooled Denoise task-pool best improves partitioned by>=.001 in BOTH reverse comparisons; Aerial best nondeclines BOTH. No pooled rescue, replacement or newseed follow-up if false.',
        stop='Fixed32 only. Ordinary candidate failure remains within completed searches. Infrastructure/worker/input/namespace/cleanup failure stops later pools. No retry/oldroot reopening or old budget reuse.',
        rationale='18807 observed quota-blocked intervals support testing eligibility, not spare compute or quality. Subsequent publication-chain audit found only two new-best Analyze requests with borrowable waits, both below1second; expected utility is weak. This final bounded strong-baseline qualification tests the censored counterfactual without changing thresholds or selecting new seeds.',
        limitation='Work-conserving quota pooling is an established baseline, NOT algorithm novelty or MARS/SchedMate reproduction. Two reusedDEVtasks, two reverse comparisons share one service. Task service allocation can shift; report both task results and preserve per-run wall budget. Warm construction is sunk/common, not from-scratch savings. Do not combine effects with selective-sharing batch.',
        independent_predecessor=dict(root='/research/d7/spc/yzyang4/scheduling-generation-quota-20261017-v1',job='19004',sealed=True,budget_reused=False,
            qualification='Invalid intervention; all four pools retained old per-task2selector. No quality rescue or old readout overwrite.',
            closure_sha256='ce69cc04504d7160c2d85024ad34b519047e09aeb5934f779c14b2432dbcd43b'))

def preflight():
    p=common.original.base.c.trial.check()
    runtime_hook_guard()
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
    common.WINDOW_END=int(common.datetime(2026,10,17,20,28,3,tzinfo=common.timezone.utc).timestamp())
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
    # Real workers resolve this deeper image-trial binding. Sealed19004 only
    # changed the facades, so its direct-install CPU tests missed the bypass.
    common.original.base.c.trial.install_hooks=hooks

configure()
task_runtime=common.task_runtime;host=common.host
def install_hooks(row,ep,deadline):return common.original.install_hooks(row,ep,deadline)

def runtime_hook_guard():
    entry=host();expected=common.original.install_hooks
    assert entry.install_hooks is expected,'native host bypasses quota hook'
    assert entry.worker.__globals__['install_hooks'] is expected,'worker resolves another hook'
    return entry

def worker(index):
    runtime_hook_guard()
    return common.original.worker(index)
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
    elif a.mode=='worker':worker(a.index)
