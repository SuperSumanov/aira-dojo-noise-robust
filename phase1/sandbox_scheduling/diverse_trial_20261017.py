"""Conditional48-run task-diverse pairing vs BOTH sharedFIFO and ordinary cap2.

Reuses the actually executed18807 path. No task/code/effort/CPU budget changes
within a pair; only pool mode differs. Known-dev baseline qualification, not
novelty or independent task generalization. One shared service, ABC/CBA pools.
"""
import argparse
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime,timezone
import colocation_trial_20261016 as original
import diverse_pool_20261017 as diverse
from pool_stop_contract_20261017 import require_completed_workers

R=Path('/research/d7/spc/yzyang4/scheduling-diverse-20261017-v3')
NODE='gpu3'
NAME=Path(__file__).name
ORDER=('shared','colocated','diverse','diverse','colocated','shared')
CAP=8400
WINDOW_END=int(datetime(2026,10,17,0,49,tzinfo=timezone.utc).timestamp())
PARENT=R.parent/'clock-pairing-20261017-v2'
PARENT_PIN='a2f2ea693c0d2a194ac194a3023e81645eeb55b94263733dd12e943515d6ed22'
ORIGINALS=getattr(original,'_diverse_originals',
    {n:getattr(original,n) for n in ('prepare','controller','task_runtime','executor')})
original._diverse_originals=ORIGINALS
read,write,sha=original.read,original.write,original.sha


def schedule():
    return [dict(index=8*b+2*l+k,block=b,lane=l,slot=2*l+k,repeat=b//3,
        arm='old_fast',pool_mode=mode,task=t,seed=217501+100*(b//3)+2*l+k)
        for b,mode in enumerate(ORDER) for l in range(4) for k,t in enumerate(original.base.c.trial.TASKS)]


def transform(name,replacements):
    source=inspect.getsource(ORIGINALS[name])
    for old,new,count in replacements:
        assert source.count(old)==count,(name,old,source.count(old),count)
        source=source.replace(old,new)
    exec(compile(source,'independent-diverse-'+name,'exec'),original.__dict__)


def qualifying_parent():
    assert sha(PARENT/'plan.json')==PARENT_PIN
    path=PARENT/'readout-20261017-v1/summary.json'
    p=read(path)
    assert p['plan_sha256']==PARENT_PIN
    assert p['planned']==p['complete']==p['valid']==p['recomputed']==16
    assert p['structure'] and p['predeclared_gate_met']
    verifier=read(PARENT/'independent-readout-verification.json')
    assert verifier['passed'] and verifier['summary_sha256']==sha(path) and verifier['plan_sha256']==PARENT_PIN
    return dict(root=str(PARENT),plan_sha256=PARENT_PIN,summary_sha256=sha(path))


def scientific_metadata():
    return dict(planned=48,gpu_hours_cap=14,combined_gpu_seconds_cap=50400,
        new_window_gpu_seconds_cap=50400,run_seconds=1020,slot_seconds=1180,
        qualifying_parent=dict(root=str(PARENT),plan_sha256=PARENT_PIN,
            requirement='Parent full16/quality/structure gate AND independent summary-bound verifier before submit and service start'),prior_failures=[],
        staging_note='Independent Oct17 batch, only after fixed-program pairing gate. v1 CPU preparation failed because fixture patched overwritten method. v2 fixes fixture only; before any GPU submit, review found executor checked cleanup but not abnormal worker closure before next pool. v3 enforces the already-declared infrastructure stop rule for all modes, without changing successful execution, policy/input/quality gates. No predecessor submitted or budget reused.',
        approval='User Oct17HK02:49 approves bounded autonomous six-hour work.48trajectories,2tasks*4paired seeds*3modes*2reverse comparisons;2service+4execution3090;<=8400s/14GPUh including failures/startup/qualification/cleanup. No API, training or automatic retry.',
        primary='Best pristineDEV returned solution per trajectory within1020s including common incumbent; four-run task-pool best primary, trajectory medians/SD and native-selected endpoint reported separately.',
        single_change='Execution device assignment policy: sharedFIFO cap1 / least-occupiedFIFO cap2 / cap2 task-diverse tie-break. All retain FIFO request order, empty-GPU-first admission, fixed per-program CPU partition and deadlines. Diverse chooses opposite-task incumbent only among equally occupied devices, never waits for a partner.',
        advance='All48complete; input/isolation/cleanup/cost pass. Diverse must improve denoising task-pool best>=.001 vs EACH baseline in BOTH reverse comparisons; aerial task-pool best nondecline vs EACH in BOTH. Both diverse pools must actually change>=1device choice relative to ordinary cap2 at that event. No pooled rescue, sample replacement or follow-up seeds.',
        limitation='Task label is a simple known grouping feature, not method novelty. Two reused DEV tasks; ABC/CBA pools share one service and are not48independent treatment replicates. Passing is exploratory E2E qualification only, not SchedMate superiority. Source pairing cohort outcome-known. CPU/memory/I-O coeffects not isolated as pureGPU interference.',
        stop='One fixed48batch. Infrastructure/input/namespace/dispatch/cleanup failure stops remaining pools. No retries/replacements. Candidate failure stays in denominator. No interim quality decisions.',
        common_execution_change='All modes use the18807 actual sixGPU execution path, original images, fixed CPU slots, common CUDA/device/two-container gates. Native readiness false/None now propagates infrastructure failure in all three modes before candidate execution.',
        independent_predecessor=dict(job='18807',root=str(R.parent/'scheduling-colocation-20261016-v1'),sealed=True,budget_reused=False))


def preflight():
    p=original.base.c.trial.check()
    assert 'require_completed_workers' in original.executor.__code__.co_names
    assert p['planned']==48 and p['gpu_hours_cap']==14 and p['allocation_seconds']==CAP
    assert p['node']==NODE and f'#SBATCH --nodelist={NODE}' in (R/'run.sbatch').read_text()
    for row in schedule():
        ref=next(r for r in schedule() if r['seed']==row['seed'] and r['pool_mode']=='shared')
        a,b=(read(R/f"configs/{r['index']}.json") for r in (row,ref))
        assert original.base.c.trial.t.scientific(a)==original.base.c.trial.t.scientific(b)
        assert a['solver']['time_limit_secs']==1020 and a['interpreter']['timeout']==300
        for role,op in a['solver']['operators'].items():
            kw=op['llm']['generation_kwargs']
            assert op['llm']['client']['model_id']=='qwen3.8-27b'
            assert kw['reasoning_effort']==original.policy.effort('old_fast',role)
            assert kw['max_tokens']==(8192 if role=='analyze' else 32768)
    matrix=read(R/'input-matrix/summary.safe.json')
    assert matrix['assigned']==matrix['passed']==48 and matrix['exact_input_gate']
    subprocess.run([str(original.base.c.trial.PY),'-B','-m','unittest',
        'test_diverse_pool_20261017','test_diverse_readout_20261017','test_pool_stop_contract_20261017','test_fixed_public_preview_20261014'],cwd=R,check=True)
    subprocess.run([str(original.base.c.trial.PY),'-B',str(R/'diverse_production_gate_20261017.py'),str(R)],cwd=R,check=True)
    write(R/'cpu.json',dict(plan_sha256=sha(R/'plan.json'),configs=48,exact_inputs=True,no_gpu=True))
    write(R/'preflight.json',dict(source_commit=p['source_commit'],plan_sha256=sha(R/'plan.json'),configs=48,
        exact_input_gate=True,gpu_hours_cap=14,no_gpu=True,no_model_calls=True))
    print(json.dumps(read(R/'preflight.json')))


def configure():
    original.R=R;original.NODE=NODE;original.NAME=NAME;original.ORDER=ORDER;original.CAP=CAP
    original.schedule=schedule;original.preflight=preflight
    original.scientific_metadata=scientific_metadata
    original.require_completed_workers=require_completed_workers
    original.__file__=__file__
    original.NAMES=('colocation_trial_20261016.py','colocation_pool_20261016.py','colocation_production_gate_20261016.py',
        'colocation_readout_20261016.py','colocation_coexistence_20261016.py',
        NAME,'diverse_pool_20261017.py','diverse_readout_20261017.py',
        'diverse_production_gate_20261017.py','test_diverse_pool_20261017.py',
        'test_diverse_readout_20261017.py','clock_pairing_20261016.py',
        'clock_rank_20261016.py','clock_contention_20261016.py',
        'pool_stop_contract_20261017.py','test_pool_stop_contract_20261017.py')
    original.pool.State=diverse.State
    transform('prepare',[
        ('for b in range(4):','for b in range(6):',1),
        ("'#SBATCH --time=01:40:00'","'#SBATCH --time=02:20:00'",1),
        ("'5940s'","'8340s'",1),
        ("    write(R/'preparation-plan.json'","    p.update(scientific_metadata())\n    write(R/'preparation-plan.json'",1),
        ("matrix['assigned']==matrix['passed']==32","matrix['assigned']==matrix['passed']==48",1),
        ('for i in range(32)','for i in range(48)',1)])
    transform('controller',[
        ('--time=01:39:00','--time=02:19:00',1),
        ('for block in range(4):','for block in range(6):',1),
        ('dict(planned=32,','dict(planned=48,',1)])
    transform('task_runtime',[
        ('episode-(?:[0-9]|[12][0-9]|3[01])','episode-(?:[0-9]|[123][0-9]|4[0-7])',1)])
    transform('executor',[
        ("    for row in rows:\n        ep=R/f\"episode-{row['index']}\"",
         "    require_completed_workers(R,rows,results)\n    for row in rows:\n        ep=R/f\"episode-{row['index']}\"",1)])
    original.configure()
    # Propagate infrastructure readiness failure; same behavior in all arms.
    old_install=getattr(original,'_diverse_old_install',original.install_hooks)
    original._diverse_old_install=old_install
    def install(row,ep,deadline):
        old_install(row,ep,deadline)
        from dojo.core.interpreters.jupyter.jupyter_client import JupyterKernelClient as Client
        from clock_pairing_20261016 import require_ready
        before=getattr(Client.wait_for_ready,'_diverse_original',Client.wait_for_ready)
        def guarded(self,*a,**kw):return require_ready(before,self,*a,**kw)
        guarded._diverse_original=before;Client.wait_for_ready=guarded
    original.install_hooks=install;original.base.install_hooks=install


def submit():
    parent_receipt=qualifying_parent();c=original.base.c;p=c.trial.check()
    assert read(R/'cpu.json')['plan_sha256']==sha(R/'plan.json')
    if WINDOW_END-time.time()<CAP+600:raise RuntimeError('not enough time for complete batch/readout')
    assert all(sha(R/n)==h for n,h in p['input_files'].items())
    m=host()
    assert sha(m.TASK_IMAGE)==p['task_image_sha256'] and sha(m.VLLM)==p['service_image_sha256']
    assert all(sha(n)==h for n,h in p['model_files'].items())
    # All expensive checks are complete BEFORE this final clock/queue gate.
    if WINDOW_END-time.time()<CAP+600:raise RuntimeError('insufficient time after image/model hashes')
    env=m.infra().clean_env()
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True).split()
    assert not set(jobs)-{'12535'},'prior job must be fully closed before six-card allocation'
    assert not (R/'submit-intent.json').exists()
    assert qualifying_parent()==parent_receipt
    write(R/'qualification-receipt.json',parent_receipt)
    write(R/'submit-intent.json',dict(plan_sha256=sha(R/'plan.json'),gpu_hours_cap=14,wall=time.time()))
    out=subprocess.run(['sbatch','--parsable','--chdir='+str(R),
        '--output='+str(R/'allocation-%j.private.out'),'--error='+str(R/'allocation-%j.private.err'),str(R/'run.sbatch')],
        env=env,capture_output=True,text=True,timeout=25)
    job=out.stdout.strip().split(';')[0]
    if out.returncode or not job.isdigit():raise RuntimeError('ambiguous submission: do not repeat')
    write(R/'launch.json',dict(job=job,plan_sha256=sha(R/'plan.json')))
    print(json.dumps(dict(submitted=True,job=job,gpu_hours_cap=14,plan_sha256=sha(R/'plan.json'))))


def controller():
    assert read(R/'qualification-receipt.json')==qualifying_parent()
    if WINDOW_END-time.time()<CAP+600:
        write(R/'window-refusal.json',dict(no_workers_started=True,remaining_seconds=WINDOW_END-time.time()))
        raise RuntimeError('not enough time after queue wait')
    return original.controller()


def task_runtime():return original.task_runtime()
def host():return original.host()
def install_hooks(row,ep,deadline):return original.install_hooks(row,ep,deadline)


configure()
if __name__=='__main__':
    os.umask(0o077);os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('prepare','preflight','submit','controller','service','executor','worker'))
    p.add_argument('--commit');p.add_argument('--block',type=int);p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='prepare':original.prepare(a.commit)
    elif a.mode=='preflight':preflight()
    elif a.mode=='submit':submit()
    elif a.mode=='controller':controller()
    elif a.mode=='service':original.base.c.trial.service(0)
    elif a.mode=='executor':original.executor(a.block)
    elif a.mode=='worker':original.worker(a.index)
