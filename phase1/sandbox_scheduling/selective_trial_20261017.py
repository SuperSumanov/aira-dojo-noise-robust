"""Independent32-run selective sharing vs shared FIFO, not pairing rescue.

The16-program partner experiment18987 and its conditional diverse experiment
remain closed. This tests a different admission decision: whether a job may
share at all, using an explicitly task-specific prior. Not a novel scheduler.
"""
import argparse,inspect,json,os,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
import colocation_trial_20261016 as original
import selective_pool_20261017 as selective
from pool_stop_contract_20261017 import require_completed_workers

R=Path('/research/d7/spc/yzyang4/scheduling-selective-20261017-v1')
NODE='gpu3';NAME=Path(__file__).name;CAP=6000
ORDER=('shared','selective','selective','shared')
WINDOW_END=int(datetime(2026,10,17,0,49,tzinfo=timezone.utc).timestamp())
ORIGINALS=getattr(original,'_selective_originals',{n:getattr(original,n) for n in ('prepare','executor')})
original._selective_originals=ORIGINALS
read,write,sha=original.read,original.write,original.sha


def schedule():
    return [dict(index=8*b+2*l+k,block=b,lane=l,slot=2*l+k,repeat=b//2,
        arm='old_fast',pool_mode=mode,task=t,seed=217701+100*(b//2)+2*l+k)
        for b,mode in enumerate(ORDER) for l in range(4) for k,t in enumerate(original.base.c.trial.TASKS)]


def scientific_metadata():
    return dict(
        staging_note='Independent task-specific admission qualification after18987 failed first-group validity. Neither18987 nor its conditional diverse batch is resumed. Different question: selective exclusivity vs same sharedFIFO, not alternative matching of an unchanged cap2 workload.',
        prior_failures=[],new_window_gpu_seconds_cap=36000,combined_gpu_seconds_cap=36000,
        approval='User Oct17HK02:49 authorizes bounded autonomous six-hour experiments.32searches=2knownDEV tasks*4paired seeds*2conditions*2reverse pool comparisons;2service+4execution3090,<=6000s/10GPUh inclusive of startup/failures/cleanup. NoAPI/base training/retries.',
        primary='Task-pool best pristineDEV returned solution within1020s per trajectory including common incumbent. Full32denominator; per-trajectory endpoints, pool median/sampleSD and native-selected score separate.',
        single_change='Admission eligibility: sharedFIFO cap1 vs selectiveFIFO allowing two Aerial leases only. Denoise never shares. Both use FIFO request order, empty-first lowest-occupancy device placement, original generator/start/history/images/seeds/CPU/deadlines. No candidate rewriting, timer changes, migration, preemption or waiting to create partners.',
        advance='All32complete; input/isolation/dispatch/cleanup/full-cost pass; BOTHselective pools actually co-admit and observe protected-head deferral while ordinary cap2 would have space. Selective Denoise task-pool best improves sharedFIFO by>=.001 in BOTH reverse comparisons; Aerial best nondeclines in BOTH. No pooled rescue/substitution/newseed follow-up on failure.',
        limitation='A task-specific simple baseline informed by known-program observations, NOT a semantic classifier/general algorithm. Only two previously studiedDEV tasks; two reverse comparisons share a service, not32independent treatments. No contemporaneous ordinarycap2/SchedMate control, so no claim of beating either. Failed candidates remain within valid completed search trajectories; infrastructure failures halt later pools.',
        rationale='18819 repeated coarse completed-fold loss versus Aerial less-work/better-output;18987program2 entered a whole second fold after153.6s and CV ended287.6s, leaving insufficient time for inference/materialization. This supports testing selective exclusivity, not extending timeout or claiming output-write bottleneck alone. Ordinarycap2 and task-diverse partner plans stay closed.',
        stop='One fixed32batch. Stop remaining pools on abnormal worker/infrastructure/input/isolation/cleanup failure. Ordinary candidate failure stays in denominator and does not abort whole search. No automatic retry or reopening closed batches.',
        common_execution_change='Original18807sixGPU path/images, common arithmetic/isolation/two-container qualification, and fixedCPU. Allarms readiness failure propagates; executor now enforces already-declared worker closure stop before later pools. No change to successful search path.',
        independent_predecessor=dict(job='18987',root='/research/d7/spc/yzyang4/clock-pairing-20261017-v2',sealed=True,budget_reused=False,qualification='false; this is not its conditional diverse follow-up'))


def preflight():
    p=original.base.c.trial.check();assert p['planned']==32 and p['gpu_hours_cap']==10 and p['allocation_seconds']==CAP
    assert p['node']==NODE and 'require_completed_workers' in original.executor.__code__.co_names
    for row in schedule():
        ref=next(r for r in schedule() if r['seed']==row['seed'] and r['pool_mode']=='shared')
        a,b=(read(R/f"configs/{r['index']}.json") for r in (row,ref))
        assert original.base.c.trial.t.scientific(a)==original.base.c.trial.t.scientific(b)
        assert a['solver']['time_limit_secs']==1020 and a['interpreter']['timeout']==300
        for role,op in a['solver']['operators'].items():
            kw=op['llm']['generation_kwargs'];assert op['llm']['client']['model_id']=='qwen3.8-27b'
            assert kw['reasoning_effort']==original.policy.effort('old_fast',role)
            assert kw['max_tokens']==(8192 if role=='analyze' else 32768)
    matrix=read(R/'input-matrix/summary.safe.json');assert matrix['assigned']==matrix['passed']==32 and matrix['exact_input_gate']
    subprocess.run([str(original.base.c.trial.PY),'-B','-m','unittest','test_selective_pool_20261017',
        'test_selective_readout_20261017','test_pool_stop_contract_20261017','test_fixed_public_preview_20261014'],cwd=R,check=True)
    subprocess.run([str(original.base.c.trial.PY),'-B',str(R/'selective_production_gate_20261017.py'),str(R)],cwd=R,check=True)
    write(R/'cpu.json',dict(plan_sha256=sha(R/'plan.json'),configs=32,exact_inputs=True,no_gpu=True))
    write(R/'preflight.json',dict(source_commit=p['source_commit'],plan_sha256=sha(R/'plan.json'),configs=32,
        exact_input_gate=True,gpu_hours_cap=10,no_gpu=True,no_model_calls=True))
    print(json.dumps(read(R/'preflight.json')))


def configure():
    original.R=R;original.NODE=NODE;original.NAME=NAME;original.CAP=CAP;original.ORDER=ORDER
    original.schedule=schedule;original.preflight=preflight;original.scientific_metadata=scientific_metadata
    original.require_completed_workers=require_completed_workers;original.__file__=__file__
    original.NAMES=('colocation_trial_20261016.py','colocation_pool_20261016.py','colocation_readout_20261016.py',
        'colocation_production_gate_20261016.py','colocation_coexistence_20261016.py',NAME,'selective_pool_20261017.py',
        'selective_readout_20261017.py','selective_production_gate_20261017.py','test_selective_pool_20261017.py',
        'test_selective_readout_20261017.py','pool_stop_contract_20261017.py','test_pool_stop_contract_20261017.py',
        'clock_pairing_20261016.py','clock_rank_20261016.py','clock_contention_20261016.py')
    original.pool.State=selective.State
    source=inspect.getsource(ORIGINALS['prepare']);needle="    write(R/'preparation-plan.json'"
    assert source.count(needle)==1;source=source.replace(needle,"    p.update(scientific_metadata())\n"+needle)
    exec(compile(source,'selective-prepare','exec'),original.__dict__)
    source=inspect.getsource(ORIGINALS['executor']);needle="    for row in rows:\n        ep=R/f\"episode-{row['index']}\""
    assert source.count(needle)==1;source=source.replace(needle,'    require_completed_workers(R,rows,results)\n'+needle)
    exec(compile(source,'selective-executor','exec'),original.__dict__)
    original.configure()
    old_install=getattr(original,'_selective_install_original',original.install_hooks);original._selective_install_original=old_install
    def install(row,ep,deadline):
        old_install(row,ep,deadline)
        from dojo.core.interpreters.jupyter.jupyter_client import JupyterKernelClient as Client
        from clock_pairing_20261016 import require_ready
        before=getattr(Client.wait_for_ready,'_selective_original',Client.wait_for_ready)
        def guarded(self,*a,**kw):return require_ready(before,self,*a,**kw)
        guarded._selective_original=before;Client.wait_for_ready=guarded
    original.install_hooks=install;original.base.install_hooks=install


def submit():
    p=original.base.c.trial.check();assert read(R/'cpu.json')['plan_sha256']==sha(R/'plan.json')
    assert WINDOW_END-time.time()>CAP+600
    assert all(sha(R/n)==h for n,h in p['input_files'].items())
    m=host();assert sha(m.TASK_IMAGE)==p['task_image_sha256'] and sha(m.VLLM)==p['service_image_sha256']
    assert all(sha(n)==h for n,h in p['model_files'].items())
    assert WINDOW_END-time.time()>CAP+600,'not enough time after hashing'
    env=m.infra().clean_env();jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True).split()
    assert not set(jobs)-{'12535'},'no overlap with previous active experiment'
    assert not (R/'submit-intent.json').exists();write(R/'submit-intent.json',dict(plan_sha256=sha(R/'plan.json'),wall=time.time(),gpu_hours_cap=10))
    cp=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.private.out'),
        '--error='+str(R/'allocation-%j.private.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=cp.stdout.strip().split(';')[0]
    if cp.returncode or not job.isdigit():raise RuntimeError('ambiguous submit; do not repeat')
    write(R/'launch.json',dict(job=job,plan_sha256=sha(R/'plan.json')))
    print(json.dumps(dict(submitted=True,job=job,plan_sha256=sha(R/'plan.json'),gpu_hours_cap=10)))


def controller():
    if WINDOW_END-time.time()<CAP+600:
        write(R/'window-refusal.json',dict(no_workers_started=True,remaining_seconds=WINDOW_END-time.time()))
        raise RuntimeError('insufficient window after queue wait')
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
