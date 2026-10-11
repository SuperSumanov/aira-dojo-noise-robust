"""R14 real image-development quality, 2 service + 4 execution GPUs.

ABBA pools, 8 independent trajectories/pool, 32 assigned runs. Each of four
fixed GPU lanes has one trajectory per task. FIFO1 vs FIFO2 is the sole arm
difference; this is not global migration, semantic scheduling or SchedMate.
"""
import argparse, concurrent.futures, copy, csv, hashlib, importlib.util, inspect, json
import os, secrets, shutil, signal, socket, subprocess, sys, threading, time, traceback
from pathlib import Path
import live_search_trial_20261009 as t
from lifecycle_pilot import read,write,sha
from image_dev_data_20261011 import TASKS

B=t.B;R=B/'scheduling-image-live-2plus4-20261011-v1';PY=t.PY;NAME=Path(__file__).name
D=B/'scheduling-live-twochild-20261010-v1'
DONOR_PIN='082645089d69e711f55057312d49e13d0fa99bf53942e91851791c12eb1525a6'
PATCH_DONOR=B/'resource-factory-integration-20261011-v2'
MODEL_DONOR=B/'resource-joint-four-capacity-20261011-v1'
RUN_SECONDS=1500;SLOT_SECONDS=2400;CAP=10200

def schedule():
    return [dict(index=8*b+2*lane+k,block=b,lane=lane,slot=2*lane+k,repeat=b//2,
                 arm=('fifo1','share2','share2','fifo1')[b],task=task,seed=211001+100*(b//2)+2*lane+k)
            for b in range(4) for lane in range(4) for k,task in enumerate(TASKS)]

def change(source,a,b,n=1):
    if source.count(a)!=n:raise ValueError('exact interface drift '+a[:80])
    return source.replace(a,b)

def check():
    p=read(R/'plan.json')
    assert p['schedule']==schedule() and p['gpus']==6 and p['allocation_seconds']==CAP
    for n,h in p['files'].items():
        if sha(R/n)!=h:raise ValueError('frozen file drift '+n)
    return p

def install_hooks(row,ep,deadline):
    import live_runtime_hooks as hooks
    # The old common adapter is reused, with per-lane independent FIFO queues.
    local=dict(row,block=f"{row['block']}-{row['lane']}")
    hooks.install(local,ep,deadline)

def host():
    path=R/'runtime.py';assert sha(path)==t.DONOR_RUNTIME
    spec=importlib.util.spec_from_file_location('image_native_host',path)
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
    m.R=R;m.SECONDS=RUN_SECONDS;m.CAP=CAP;m.schedule=schedule;m.check=check;m.install_hooks=install_hooks
    source=inspect.getsource(m.worker)
    source=change(source,"read(R/'service-native.json')","read(R/f'block-{s[\"block\"]}/service-native.json')")
    source=change(source,'PRIMARY_KEY=key,PRIMARY_KEY_QWEN3_5_9B=key','PRIMARY_KEY=key,PRIMARY_KEY_QWEN3_8_27B=key,PRIMARY_KEY_QWEN3_5_9B=key')
    source=change(source,"deadline=ExperimentDeadline(SECONDS);write(ep/'deadline.json',deadline.receipt())",
                  "deadline=ExperimentDeadline(SECONDS);write(ep/'deadline.json',deadline.receipt())\n    install_hooks(s,ep,deadline)")
    source=change(source,"HARDWARE='one NVIDIA RTX3090, six CPU cores',TIME_LIMIT='10 minutes',TIME_LIMIT_SECS='600'",
                  "HARDWARE='one shared NVIDIA RTX3090, two dedicated CPU cores',TIME_LIMIT='25 minutes',TIME_LIMIT_SECS='1500'")
    source=change(source,"cfg=RunConfig.load_from_json(R/'configs'/f'{index}.json');cfg.validate();config_logger(cfg)",
                  "cfg=RunConfig.load_from_json(R/'configs'/f'{index}.json');cfg.interpreter.env['CUDA_VISIBLE_DEVICES']=own[0];cfg.validate();config_logger(cfg)")
    source=change(source,"                receipt=original_score(name,submission)","""                receipt=original_score(name,submission)
                try:
                    if interp.fetch_file(Path(interp.working_dir)/'gpu_training.json'):
                        training=read(Path(interp.working_dir)/'gpu_training.json')
                        write(ep/f'gpu-training-{len(scored)}.json',training)
                except Exception as exc:
                    write(ep/f'gpu-training-missing-{len(scored)}.json',dict(error_type=type(exc).__name__))""")
    source=change(source,"                out,result=step_task(state,executable)","""                from image_gpu_observation_20261011 import INSTRUMENT,RECEIPT
                executable='import sys;sys.argv=[\"candidate.py\"]\\nimport torch\\ntorch.manual_seed('+str(s['seed'])+')\\n'+INSTRUMENT+'\\n'+executable+'\\n'+RECEIPT
                out,result=step_task(state,executable)""")
    exec(compile(source,'image-live-native-worker','exec'),m.__dict__)
    source=change(inspect.getsource(m.task_runtime),'episode-[0-7]','episode-(?:[0-9]|[12][0-9]|3[01])')
    exec(compile(source,'image-live-native-runtime','exec'),m.__dict__)
    return m

def prepare(commit):
    assert sha(D/'plan.json')==DONOR_PIN
    p=read(D/'plan.json');assert read(D/'closed.json')['complete']==15
    assert len(commit)==40 and read(MODEL_DONOR/'audit-v1.json')['full_capacity_gate']
    patched=read(PATCH_DONOR/'plan.json')
    assert read(PATCH_DONOR/'audit-v1.json')['accepted']==6
    for n,h in p['files'].items():assert sha(D/n)==h
    for n,h in patched['files'].items():assert sha(PATCH_DONOR/n)==h
    R.mkdir(mode=0o700)
    for n,h in p['files'].items():
        if n.startswith(('episode-','block-','configs/','bin/')) or n in ('run.sbatch',):continue
        dst=R/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(D/n,dst)
    for n in ('jupyter_client.py','jupyter_code_executor.py','jupyter_interpreter.py','singularity_jupyter_server.py'):
        rel='source/src/dojo/core/interpreters/jupyter/'+n
        shutil.copyfile(PATCH_DONOR/rel,R/rel)
    shutil.copytree(PATCH_DONOR/'gateway',R/'gateway')
    # Extend the established external-only scorer's whitelist by one genuine metric.
    taskfile=R/'source/src/dojo/tasks/mlebench/task.py'
    taskfile.write_text(change(taskfile.read_text(),'"log_loss", "auc", "mean_columnwise_spearman", "mean_word_jaccard"',
        '"log_loss", "auc", "mean_columnwise_spearman", "mean_word_jaccard", "rmse"'))
    for n in (NAME,'image_dev_data_20261011.py','test_image_live_20261011.py','image_gpu_observation_20261011.py','resource_gpu_identity.py','live_identity.py'):
        shutil.copyfile(Path(__file__).with_name(n),R/n)
    from image_dev_data_20261011 import prepare as make_views
    specs=make_views(B/'mle-bench-data',R/'dev-views')
    scorer=R/'image_scorer.py'
    scorer.write_text("from pathlib import Path\nimport json\nfrom image_dev_data_20261011 import InvalidSubmissionError,score_at\nBASE=Path("+repr(str(R))+ ")\nSPEC=json.loads((BASE/'dev-views/spec.json').read_text())\ndef score(task,submission):return score_at(BASE,SPEC,task,submission)\n")
    helper=R/'forets_native_cuda_identity_20260911.py'
    helper.write_text(change(helper.read_text(),"split('.')[0]!='gpu27'","split('.')[0]!='gpu3'"))
    hook=R/'live_runtime_hooks.py';text=hook.read_text()
    text=change(text,"'a6c6abdca37745ce8d5137f48595a3c0e6332c113e8133b0782425b7bbb291bf'",repr(sha(R/'source/src/dojo/core/interpreters/jupyter/jupyter_client.py')))
    text=change(text,'0 <= index <= 16','0 <= index <= 31');hook.write_text(text)
    for n in ('configs','bin'):(R/n).mkdir(exist_ok=True)
    (R/'bin/singularity').write_text(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(NAME).stem} import host\nhost().task_runtime()\n')
    os.chmod(R/'bin/singularity',0o700)
    with (R/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    os.chmod(R/'.service.env',0o600)
    # Model entry is the validated unchanged 27B; only its local port is the live port.
    for b in range(4):(R/f'block-{b}/service-cache/tmp').mkdir(parents=True)
    configs=[]
    for row in schedule():
        ep=R/f"episode-{row['index']}";(ep/'work/input_cache').mkdir(parents=True)
        cfg=read(D/f"configs/{row['slot']%2}.json")
        cfg['id']='image-live-'+str(row['index']);cfg['metadata'].update(seed=row['seed'],script_id='image-live-2plus4-20261011',base_path=str(R/'source'))
        cfg['logger'].update(output_dir=str(ep/'native-log'),write_env_vars=False,use_console=False,print_config=False,use_wandb=False)
        cfg['solver'].update(checkpoint_path=str(ep/'checkpoint'),time_limit_secs=RUN_SECONDS,num_children=2,execution_timeout=300)
        view=Path(specs[row['task']]['view'])
        cfg['task'].update(name=row['task'],public_dir=str(view/'public'),data_dir=str(view/'public'),
            private_dir=str(view/'private-unavailable'),cache_dir=str(R/'no-official-data'),results_output_dir=str(ep/'native-task-results'),
            search_only_dev_scorer_path=str(scorer),search_only_dev_scorer_sha256=sha(scorer))
        cfg['interpreter'].update(working_dir=str(ep/'work'),timeout=300,
            read_only_binds={str(R/'gateway'):'/r14gateway'},
            env=dict(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONHASHSEED=str(row['seed']),
                     OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2',PYTHONPATH='/r14gateway'))
        for op in cfg['solver']['operators'].values():
            op['llm']['client']['model_id']='qwen3.8-27b'
            kw=op['llm']['generation_kwargs'];kw.update(seed=row['seed'],max_tokens=8192,reasoning_effort='medium',bounded_request_timeout_seconds=240)
            kw['extra_body']={'chat_template_kwargs':{'enable_thinking':True}}
        write(R/f"configs/{row['index']}.json",cfg);configs.append(cfg)
    for a,b in [(i,i+8) for i in range(8)]+[(i,i+8) for i in range(16,24)]:
        assert t.scientific(configs[a])==t.scientific(configs[b])
    batch=f'''#!/bin/bash
#SBATCH --job-name=r14-image-quality
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu3
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:6
#SBATCH --cpus-per-task=24
#SBATCH --hint=nomultithread
#SBATCH --time=02:50:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=30s 10110s {PY} -B {R/NAME} controller
'''
    (R/'run.sbatch').write_text(batch);subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    write(R/'plan.json',dict(source_commit=commit,dojo_commit=p['source_dojo_commit'],schedule=schedule(),planned=32,
        gpus=6,service_gpus=2,execution_gpus=4,physical_cpu=24,service_cpu=8,lane_cpu=4,worker_cpu=2,
        allocation_seconds=CAP,gpu_hours_cap=17,run_seconds=RUN_SECONDS,slot_seconds=SLOT_SECONDS,candidate_seconds=300,
        source_donor_plan_sha256=DONOR_PIN,patch_donor_plan_sha256=sha(PATCH_DONOR/'plan.json'),
        model_files=p['model_files'],task_image_sha256=p['task_image_sha256'],service_image_sha256=p['service_image_sha256'],
        primary='Native-selected externally scored development endpoint at1500s; all32 assigned, failures/missing retained; per-task paired deltas and validity-ranked wins, no zero imputation.',
        secondary='Best valid endpoint/task/pool; useful candidate returns, CUDA optimizer steps and sampledGPUtime. Pool-level scheduling replication count=2 paired AB/BA blocks, not32.',
        advance='All32 endpoints grounded, both paired pools more timely CUDA-valid feedback, per-task paired score median nonnegative and at least one task strictly positive, no greater invalid-endpoint count, complete equal-budget/isolation/cleanup receipts. Otherwise no automatic expansion.',
        single_change='Per-GPU lane FIFO candidate permits1 versus2. Both4 execution GPUs active; same8run arrivals, fixed2runs/lane, native run order, model medium and8192tokens, seed, CPU2/run, data and all-pool budgets.',
        limitation='Not global migration/phase-aware strong baseline or SchedMate reproduction. New reused-public-training dev views, not hidden confirmatory quality; no claims from more returns alone.',
        no_paid_api=True,no_base_update=True,no_official_test=True,reserved_fraction_untouched=True,
        stop='Stop remaining pools on isolation/cleanup/service infrastructure failure; retain all32; candidate failures retained without replacement or retries.',
        input_files={str(f.relative_to(R)):sha(f) for f in (R/'dev-views').rglob('*') if f.is_file()},
        files={str(f.relative_to(R)):sha(f) for f in R.rglob('*') if f.is_file() and f.name!='.service.env' and '__pycache__' not in f.parts and 'dev-views' not in f.relative_to(R).parts}))
    cpu()
    print(json.dumps(dict(prepared=True,planned=32,plan_sha256=sha(R/'plan.json'),gpu_hours_cap=17)))

def cpu():
    check();m=host();m.setup();os.environ.update(PRIMARY_KEY='offline-fixture',PRIMARY_KEY_QWEN3_8_27B='offline-fixture')
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    from dojo.solvers.mcts.mcts import MCTS
    from dojo.core.tasks.constants import TASK_DESCRIPTION
    from dojo.utils.logger import config_logger
    from omegaconf import OmegaConf
    for row in schedule():
        cfg=RunConfig.load_from_json(R/f"configs/{row['index']}.json");cfg.validate();config_logger(cfg)
        task=MLEBenchTask(cfg.task);interp=build(cfg.interpreter,INTERPRETER_MAP,data_dir=cfg.task.data_dir)
        assert interp.factory and task._search_only_score and not task.private_dir.exists() and not cfg.solver.use_test_score
        solver=MCTS(OmegaConf.structured(cfg.solver),{TASK_DESCRIPTION:task.task_description,'lower_is_better':task._search_only_lower_is_better})
        assert len(solver.journal.nodes)==0 and cfg.interpreter.timeout==300 and cfg.solver.num_children==2
    write(R/'cpu.json',dict(configs=32,paired_equal=16,no_kernel=True,no_model=True,plan_sha256=sha(R/'plan.json')))

def service(block):
    check();m=host();x=m.infra();from resource_gpu_identity import gpu_uuids
    from live_identity import cpu_topology,cores
    top=cpu_topology();assert len(cores(top))==8 and socket.gethostname().split('.')[0]=='gpu3'
    devices=gpu_uuids(2)
    write(R/f'block-{block}/service-native.json',dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],gpu_uuids=devices,cpu_topology=top))
    model=B/'local-qwen27b-20260914-zcx1k1dy/model';cache=R/f'block-{block}/service-cache'
    cmd=['/usr/bin/singularity','exec','--containall','--cleanenv','--no-home','--nv','--no-mount','bind-paths,cwd',
         '--bind',str(model)+':/model:ro','--bind',str(cache)+':/cache:rw','--bind',str(cache/'tmp')+':/tmp:rw',
         '--bind',str(R/'service_entry.py')+':/run/service_entry.py:ro','--pwd','/cache',str(m.VLLM),'/usr/bin/python3','/run/service_entry.py']
    values=dict(CUDA_VISIBLE_DEVICES=','.join(devices),EXPECTED_GPU_UUIDS=','.join(devices),VLLM_API_KEY=x.local_key(),VLLM_WORKER_MULTIPROC_METHOD='spawn',
        VLLM_CACHE_ROOT='/cache/vllm',TRITON_HOME='/cache/triton',TORCH_HOME='/cache/torch',HF_HOME='/cache/hf',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
        FLASHINFER_WORKSPACE_BASE='/cache/flashinfer',XDG_CACHE_HOME='/cache/xdg',TMPDIR='/tmp',MAX_JOBS='2',VLLM_NO_USAGE_STATS='1',VLLM_CONFIG_ROOT='/cache/vllm-config')
    env={k:os.environ[k] for k in ('PATH','HOME','USER','LOGNAME') if k in os.environ};env.update({'SINGULARITYENV_'+k:v for k,v in values.items()})
    os.execve(cmd[0],cmd,env)

def activate_helpers():
    t.R=R;t.NAME=NAME;t.PY=PY
    t.host=host
    src=change(inspect.getsource(t.run_one),'timeout=690','timeout=1590')
    exec(compile(src,'image-live-supervisor','exec'),t.__dict__)

def worker(index):
    from resource_gpu_identity import gpu_uuids
    gpu=gpu_uuids(1)[0];os.environ['CUDA_VISIBLE_DEVICES']=gpu
    allowed=sorted(os.sched_getaffinity(0));assert len(allowed)==4
    # Same CPU entitlement even while the competing run waits or generates.
    slot=schedule()[index]['slot']%2;os.sched_setaffinity(0,allowed[slot*2:slot*2+2])
    return host().worker(index)

def lane(block,lane_id):
    check();activate_helpers();m=host();m.setup()
    from resource_gpu_identity import gpu_uuids
    from live_identity import cpu_topology,cores
    from live_admission import initialize,audit_events
    gpu=gpu_uuids(1)[0];top=cpu_topology();assert len(cores(top))==4
    service_id=read(R/f'block-{block}/service-native.json');assert gpu not in service_id['gpu_uuids']
    assert not cores(top)&cores(service_id['cpu_topology']) and not t.gpu_sample(gpu)['pids']
    rows=[r for r in schedule() if r['block']==block and r['lane']==lane_id]
    limit=1 if rows[0]['arm']=='fifo1' else 2;q=R/f'queue-{block}-{lane_id}';initialize(q,limit)
    write(R/f'block-{block}/lane-{lane_id}-native.json',dict(gpu_uuid=gpu,cpu_topology=top,job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID']))
    stop=threading.Event();samples=[];errors=[]
    def observe():
        while not stop.is_set():
            try:samples.append(t.gpu_sample(gpu))
            except Exception as e:errors.append(type(e).__name__);break
            stop.wait(2)
    th=threading.Thread(target=observe,daemon=True);th.start()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(t.run_one,rows))
    finally:stop.set();th.join(22)
    events=[json.loads(s) for s in (q/'events.jsonl').read_text().splitlines()] if (q/'events.jsonl').exists() else []
    audit=audit_events(events,limit);clean=not t.gpu_sample(gpu)['pids']
    write(R/f'block-{block}/lane-{lane_id}-telemetry.json',samples)
    write(R/f'block-{block}/lane-{lane_id}-closed.json',dict(results=results,queue_audit=audit,gpu_clean=clean,telemetry_errors=errors))
    assert clean and not errors and not th.is_alive() and audit['all_released'] and all(r['cleanup_verified'] for r in results)

def controller():
    check();activate_helpers();m=host();m.setup();job=os.environ['SLURM_JOB_ID'];start=time.monotonic()
    assert socket.gethostname().split('.')[0]=='gpu3'
    for _ in range(40):
        if (R/'launch.json').exists():break
        time.sleep(.25)
    assert read(R/'launch.json')['job']==job
    env=m.infra().clean_env();base=['srun','--exclusive','--nodes=1','--ntasks=1','--hint=nomultithread']
    attempted=[];error=None
    try:
        for block in range(4):
            if CAP-(time.monotonic()-start)<SLOT_SECONDS:raise TimeoutError('no full pool slot')
            bd=R/f'block-{block}';begin=time.monotonic();wall=time.time();workers=[];logs=[]
            with (bd/'service.private.log').open('xb') as slog:
                server=subprocess.Popen(base+['--cpus-per-task=8','--gres=gpu:2','--time=00:40:00',str(PY),'-B',str(R/NAME),'service','--block',str(block)],env=env,stdout=slog,stderr=slog,start_new_session=True)
                try:
                    while time.monotonic()-begin<660:
                        if server.poll() is not None:raise RuntimeError('service failed')
                        try:
                            if {r['id'] for r in m.api('/v1/models')['data']}=={'qwen3.8-27b'}:break
                        except Exception:pass
                        time.sleep(2)
                    else:raise TimeoutError('service startup')
                    write(bd/'service-ready.json',dict(startup_seconds=time.monotonic()-begin))
                    attempted.append(block)
                    for lane_id in range(4):
                        log=(bd/f'lane-{lane_id}.private.log').open('xb');logs.append(log)
                        workers.append(subprocess.Popen(base+['--cpus-per-task=4','--gres=gpu:1','--time=00:29:00',str(PY),'-B',str(R/NAME),'lane','--block',str(block),'--lane',str(lane_id)],env=env,stdout=log,stderr=log,start_new_session=True))
                    while any(w.poll() is None for w in workers):
                        if server.poll() is not None:raise RuntimeError('model died')
                        if time.monotonic()-begin>SLOT_SECONDS-90:raise TimeoutError('pool slot')
                        time.sleep(2)
                    codes=[w.returncode for w in workers];write(bd/'steps.json',dict(returncodes=codes))
                    assert codes==[0]*4,'lane infrastructure failure'
                    from live_identity import cores
                    ids=[read(bd/f'lane-{i}-native.json') for i in range(4)]
                    assert len({i['gpu_uuid'] for i in ids})==4
                    sets=[cores(i['cpu_topology']) for i in ids]+[cores(read(bd/'service-native.json')['cpu_topology'])]
                    assert all(not sets[i]&sets[j] for i in range(5) for j in range(i))
                finally:
                    for w in workers:
                        if w.poll() is None:
                            w.send_signal(signal.SIGTERM)
                            try:w.wait(timeout=15)
                            except subprocess.TimeoutExpired:os.killpg(w.pid,signal.SIGKILL);w.wait(timeout=10)
                    for log in logs:log.close()
                    t.stop_service(server,block,job)
            active=time.monotonic()-begin
            if active>SLOT_SECONDS:raise TimeoutError('slot exceeded')
            while time.monotonic()-begin<SLOT_SECONDS:time.sleep(min(1,SLOT_SECONDS-(time.monotonic()-begin)))
            write(bd/'budget-slot.json',dict(reserved_seconds=SLOT_SECONDS,actual_seconds=time.monotonic()-begin,active_seconds=active,start=wall,gpus=6))
    except Exception as exc:
        error=dict(type=type(exc).__name__,frames=[dict(file=Path(f.filename).name,line=f.lineno,function=f.name) for f in traceback.extract_tb(exc.__traceback__)])
        raise
    finally:
        rows=[]
        for row in schedule():
            out=dict(row,status='not_started',source_commit=read(R/'plan.json')['source_commit']);ep=R/f"episode-{row['index']}"
            if (ep/'closed.json').exists():out.update(read(ep/'closed.json'));out['status']='incomplete'
            if (ep/'finished.json').exists():
                final=read(ep/'finished.json');out.update(final)
                out['status']='complete' if out.get('returncode')==0 and out.get('cleanup_verified') and final['status'] in ('completed','budget_exhausted') else 'incomplete'
            rows.append(out)
        write(R/'runs.json',rows)
        with (R/'runs.csv').open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=sorted({k for r in rows for k in r}));w.writeheader();w.writerows(rows)
        write(R/'closed.json',dict(planned=32,attempted_blocks=attempted,complete=sum(r['status']=='complete' for r in rows),error=error,elapsed_seconds=time.monotonic()-start))

def submit():
    p=check();assert read(R/'cpu.json')['plan_sha256']==sha(R/'plan.json')
    assert all(sha(R/n)==h for n,h in p['input_files'].items())
    m=host();assert sha(m.TASK_IMAGE)==p['task_image_sha256'] and sha(m.VLLM)==p['service_image_sha256']
    assert all(sha(n)==h for n,h in p['model_files'].items())
    env=m.infra().clean_env();jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True).split()
    assert not set(jobs)-{'12535'}
    write(R/'submit-intent.json',dict(plan_sha256=sha(R/'plan.json'),gpu_hours_cap=17))
    out=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),'--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=out.stdout.strip().split(';')[0]
    if out.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; no retry')
    write(R/'launch.json',dict(job=job,plan_sha256=sha(R/'plan.json')))
    print(json.dumps(dict(submitted=True,job=job,gpu_hours_cap=17)))

if __name__=='__main__':
    os.umask(0o077);os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','cpu','submit','controller','service','lane','worker']);p.add_argument('--commit');p.add_argument('--block',type=int);p.add_argument('--lane',type=int);p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='worker':worker(a.index)
    elif a.mode=='service':service(a.block)
    elif a.mode=='lane':lane(a.block,a.lane)
    else:globals()[a.mode]()
