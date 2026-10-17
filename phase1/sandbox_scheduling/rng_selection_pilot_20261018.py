"""New bounded fixed-candidate selection assay, NOT another scheduler batch.

24 selection executions:2tasks*2chronological programs*2seeds*3RNG policies.
8 common deployment executions:2tasks*2programs*2fresh seeds, original RNG.
The policy choices are sealed using selection seeds before audit scores are read.
This tests seed-transfer of fixed-library decisions, not end-to-end LLM search.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
import clock_contention_20261016 as base

BASE=Path('/research/d7/spc/yzyang4')
D=BASE/'scheduling-selective-20261017-v1'
R=BASE/'rng-selection-20261018-v2'
PY=BASE/'venvs/aira/bin/python'
NAME=Path(__file__).name
CAP=3600
TASKS=('aerial-cactus-identification','denoising-dirty-documents')
MODES=('global','sampler','addressed')
BLOCKS=(('selection','global',4101),('selection','sampler',4101),('selection','addressed',4101),
        ('selection','addressed',4102),('selection','sampler',4102),('selection','global',4102),
        ('deployment','global',4103),('deployment','global',4104))
LATEST_START=datetime(2026,10,17,18,10,tzinfo=timezone.utc).timestamp()
read,write,sha=base.read,base.write,base.sha

def setup():
    # Reuse the already-working AIRA runtime, image and exact one-GPU namespace.
    m=base.setup();os.environ['LOGGING_DIR']=str(R)
    return m

def schedule():
    return [dict(index=4*b+k,block=b,program=k,task=TASKS[k//2],slot=k,
                 phase=phase,mode=mode,seed=seed)
            for b,(phase,mode,seed) in enumerate(BLOCKS) for k in range(4)]

def selected():
    from closed_rng_structure_20261018 import SECRET
    plan=read(D/'plan.json');out=[]
    assert (D/'closed.json').exists()
    for task in TASKS:
        chosen=[];seen=set()
        for row in sorted(plan['schedule'],key=lambda r:r['index']):
            if row['task']!=task:continue
            ep=D/f"episode-{row['index']}"
            for p in sorted(ep.glob('candidate-*.json'),key=lambda p:int(p.name.split('-')[1].split('.')[0])):
                if '.private.' in p.name:continue
                c=read(p)
                if not(c['elapsed_seconds']<=1020 and c.get('valid') is True and c.get('exit_code')==0 and not c.get('timed_out')):continue
                if c['code_sha256'] in seen:continue
                code=read(p.with_name(p.stem+'.private.json'))['code']
                assert hashlib.sha256(code.encode()).hexdigest()==c['code_sha256']
                assert not SECRET.search(code),'credential shape; no source exported'
                tree=ast.parse(code)
                # Bounded compatibility of the experimental identity adapter.
                datasets=[n for n in ast.walk(tree) if isinstance(n,ast.ClassDef) and
                          any(isinstance(f,ast.FunctionDef) and f.name=='__getitem__' for f in n.body)]
                assert len(datasets)==1
                item=next(f for f in datasets[0].body if isinstance(f,ast.FunctionDef) and f.name=='__getitem__')
                itemtext=ast.unparse(item)
                assert 'np.random' not in itemtext and 'random.' not in itemtext and '.cuda(' not in itemtext
                assert ('self.images' in itemtext if task==TASKS[0] else 'self.noisy_list' in itemtext)
                observations=[]
                for q in ep.glob('scored-*.json'):
                    if read(q)['receipt']['submission_sha256']==c['aux']['submission_sha256']:
                        tr=ep/('gpu-training-'+q.stem.split('-')[1]+'.json')
                        if tr.exists():observations.append(tr)
                assert len(observations)==1 and read(observations[0])['cuda_gradient_steps']>0
                chosen.append(dict(task=task,source_episode=row['index'],source_candidate=int(p.stem.split('-')[1]),
                    code_sha256=c['code_sha256'],receipt_sha256=sha(p),private_source_sha256=sha(p.with_name(p.stem+'.private.json')),
                    config_sha256=sha(D/f"configs/{row['index']}.json"),gpu_observation_sha256=sha(observations[0]),code=code))
                seen.add(c['code_sha256'])
                if len(chosen)==2:break
            if len(chosen)==2:break
        assert len(chosen)==2
        out.extend(chosen)
    return out

def qualify():
    runtime=setup();chosen=selected()
    assert len(schedule())==32
    assert all({r['slot'] for r in schedule() if r['program']==k}=={k} for k in range(4))
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    from dojo.utils.code_parsing import extract_code
    from unittest.mock import patch
    import dojo.core.interpreters.jupyter.jupyter_interpreter as native
    hook=Path(__file__).with_name('data_rng_coupling_20261018.py').read_text().split('\nif __name__')[0]
    sources=[]
    for k,p in enumerate(chosen):
        seeds=[]
        for n in ast.walk(ast.parse(p['code'])):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('seed','manual_seed','manual_seed_all'):
                seeds.append(ast.unparse(n))
        sources.append(dict(program=k,code_sha256=p['code_sha256'],seed_calls=seeds))
    for row in schedule():
        c=RunConfig.load_from_json(D/f"configs/{chosen[row['program']]['source_episode']}.json");c.validate()
        assert not Path(c.task.private_dir).exists() and not c.logger.use_wandb and not c.logger.write_env_vars
        port=51400+row['slot'];native._gateway_port=lambda:port
        factory=build(c.interpreter,INTERPRETER_MAP,data_dir=c.task.data_dir)
        with patch('dojo.core.interpreters.jupyter.jupyter_interpreter.SingularityJupyterServer') as server:
            assert factory.instance.port==port and factory.instance.timeout==300
            assert server.call_args.kwargs['port']==port
            factory.close()
        ast.parse(extract_code(executable(chosen[row['program']]['code'],row,hook)))
    spec=read(D/'dev-views/spec.json')
    for task in TASKS:
        d=Path(spec[task]['view']);assert sha(d/'manifest.json')==spec[task]['view_sha']
        m=read(d/'manifest.json')
        assert m['not_official_test'] and m['reserved_content_not_copied']
        for n,h in m['public_files'].items():assert sha(d/'public'/n)==h
    print(json.dumps(dict(cpu_qualification=True,actual_factory_configs=32,programs=sources,
        private_dir_absent=True,dev_public_hashes=True,task_image=str(runtime.TASK_IMAGE),
        note='Only external server launcher mocked; no candidate execution, no new quality scores.')))

def executable(code,row,hook):
    from image_gpu_observation_20261011 import INSTRUMENT,RECEIPT
    seed=row['seed']
    prefix=(f'import sys;sys.argv=["candidate.py"]\nimport torch,random,numpy as np\n'
            f'torch.manual_seed({seed});random.seed({seed});np.random.seed({seed})\n'
            +INSTRUMENT+'\n_rng_namespace={"__name__":"rng_hook"}\n'
            +'exec('+repr(hook)+',_rng_namespace)\n'
            +f'_rng_log=_rng_namespace["install"]({row["mode"]!r},{seed})\n')
    suffix='''
import json as _rng_json
from pathlib import Path as _rng_Path
_rng_p=_rng_Path('gpu_training.json')
_rng_v=_rng_json.loads(_rng_p.read_text());_rng_v['data_rng']=_rng_log
_rng_p.write_text(_rng_json.dumps(_rng_v,sort_keys=True))
'''
    return prefix+code+'\n'+RECEIPT+suffix

def prepare(commit,node):
    assert re.fullmatch('[a-f0-9]{40}',commit) and node in ('gpu1','gpu3','gpu27','gpu28','gpu29')
    runtime=setup();old=read(D/'plan.json');chosen=selected()
    assert not R.exists()
    R.mkdir(mode=0o700)
    for n in ('configs','programs','bin'):(R/n).mkdir()
    names=(NAME,'data_rng_coupling_20261018.py','closed_rng_structure_20261018.py',
           'clock_contention_20261016.py','rng_selection_readout_20261018.py')
    for n in names:shutil.copyfile(Path(__file__).with_name(n),R/n)
    hook=(R/'data_rng_coupling_20261018.py').read_text().split("\nif __name__")[0]
    from dojo.config_dataclasses.run import RunConfig
    from dojo.utils.code_parsing import extract_code
    programs=[]
    for k,p in enumerate(chosen):
        (R/f'programs/source-{k}.private.py').write_text(p['code'])
        programs.append({a:v for a,v in p.items() if a!='code'})
    for row in schedule():
        i=row['index'];p=chosen[row['program']];ep=R/f'episode-{i}'
        (ep/'work/input_cache').mkdir(parents=True)
        cfg=read(D/f"configs/{p['source_episode']}.json")
        cfg=json.loads(json.dumps(cfg).replace(str(D/f"episode-{p['source_episode']}"),str(ep)))
        cfg['id']=f"rng-selection-{i}";cfg['logger']['output_dir']=str(ep/'native-log')
        cfg['interpreter']['env']['PYTHONHASHSEED']=str(row['seed'])
        assert cfg['interpreter']['timeout']==300
        write(R/f'configs/{i}.json',cfg)
        c=RunConfig.load_from_json(R/f'configs/{i}.json');c.validate()
        assert not Path(c.task.private_dir).exists() and not c.logger.write_env_vars and not c.logger.use_wandb
        action=executable(p['code'],row,hook)
        (R/f'programs/action-{i}.private.py').write_text(action)
        row['executed_sha256']=hashlib.sha256(extract_code(action).encode()).hexdigest()
    matrix=[]
    for row in schedule():
        row['executed_sha256']=hashlib.sha256(extract_code((R/f"programs/action-{row['index']}.private.py").read_text()).encode()).hexdigest()
        matrix.append(row)
    (R/'bin/singularity').write_text(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(NAME).stem} import task_runtime\ntask_runtime()\n')
    os.chmod(R/'bin/singularity',0o700)
    (R/'run.sbatch').write_text(f'''#!/bin/bash
#SBATCH --job-name=rng-selection
#SBATCH --partition=gpu_24h
#SBATCH --nodelist={node}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:4
#SBATCH --hint=nomultithread
#SBATCH --time=01:00:00
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
exec srun --exclusive --ntasks=1 --cpus-per-task=8 --gres=gpu:4 {PY} -B {R/NAME} run
''')
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and not p.relative_to(R).parts[0].startswith('episode-')}
    write(R/'plan.json',dict(source_commit=commit,schedule=matrix,programs=programs,files=files,
        donor_plan_sha256=sha(D/'plan.json'),donor_root=str(D),runtime_root=str(base.D),
        runtime_plan_sha256=sha(base.D/'plan.json'),runtime_files=read(base.D/'plan.json')['files'],
        task_image=str(runtime.TASK_IMAGE),task_image_sha256=old['task_image_sha256'],
        gpus=4,node=node,allocation_seconds=CAP,worker_seconds=350,execution_seconds=300,
        latest_start_utc=LATEST_START,block_reserved_seconds=390,
        question='Does input-addressed data randomness improve fixed-candidate choice at equal selection execution count versus both same global seed and the explicit DataLoader-generator baseline?',
        selection='First2 distinct-source timely-valid programs/task from closed18997 by episode then candidate. Known DEV, no score sorting. No source replacement.',
        policy='For each task and mode, select program by mean oriented DEV score across4101/4102; tie lowest program index. Any missing selection score makes that task comparison unqualified; no imputation. Seal selections before reading4103/4104.',
        primary='After complete32 and all integrity gates, compare each chosen program on COMMON original-global deployment seeds4103/4104. Addressed must beat BOTH global and sampler by >=.001 RMSE on Denoise in BOTH deployment seeds, with no Aerial AUC decline in either. Otherwise do not expand this recipe.',
        cost='24 actual selection executions plus8 common deployment audit executions, all allocation startup/failures/idle/cleanup <=3600s*4=4GPUh. Each policy has same4 selection evaluations/task. Common full-library audit is measurement overhead, not free online compute or independent E2E search.',
        previous_batch='19245/v1 canceled in first global block before any treatment or score inspection, due to program-by-arm GPU assignment confounding. Its full cost is separate; this window incl v1 <=5GPUh. No reuse of its scores, no further repair batch.',
        hardware_assignment='Each of the four programs uses its own fixed GPU UUID and two physical CPUs across all arms, selection seeds and deployment. Same allocated node/image. Not hardware-generalization evidence.',
        novelty='CRN and synchronized streams are classical. No claim of inventing them; potential contribution would require automatic free-form edit alignment AND quality beyond generator-only baseline. This pilot cannot establish broad novelty.',
        limits=['Fixed2-program libraries,2knownDEV tasks,2selection+2deployment seeds; not generated adaptive search.',
                'DEV images are already used; independent RNG seeds are not new held-out tasks or data.',
                'Shared identity-hash instrumentation cost is included in all arms; no throughput benefit claim.',
                'Only CPU torch dataset randomness is addressed. Model/dropout/CUDA randomness and wall-clock work remain uncontrolled between different programs.',
                'Removing augmentation consumption from the global stream can shift later model initialization; not a pure variance-only causal decomposition.',
                'Two seeds estimate neither reliable covariance nor significance; no claim of variance reduction unless supported separately.'],
        stop='Any infrastructure/isolation/cleanup error stops the batch; candidate timeouts retained. No automatic retries or replacements, no reopening prior batches.'))
    print(json.dumps(dict(status='PREPARED',root=str(R),plan_sha256=sha(R/'plan.json'),executions=32,gpu_hours_cap=4)))

def check():
    p=read(R/'plan.json')
    for n,h in p['files'].items():assert sha(R/n)==h
    assert sha(D/'plan.json')==p['donor_plan_sha256']
    assert sha(base.D/'plan.json')==p['runtime_plan_sha256']
    return p

def task_runtime():
    setup()
    from forets_gpu_binding_20260911 import REAL_SINGULARITY
    from pooling_trial_20261015 import namespace_command
    from resource_gpu_identity import gpu_uuids
    args=sys.argv[1:]
    if args==['--version']:os.execv(REAL_SINGULARITY,[REAL_SINGULARITY,'--version'])
    ep=Path(os.environ['POLICY9B_EPISODE']);assert ep.parent==R and re.fullmatch(r'episode-(?:[0-9]|[12][0-9]|3[01])',ep.name)
    row=read(R/'plan.json')['schedule'][int(ep.name.split('-')[1])];native=read(R/'native.json')
    uid=native['gpu_uuids'][row['slot']]
    assert native['job']==os.environ['SLURM_JOB_ID'] and native['step']==os.environ['SLURM_STEP_ID']
    assert gpu_uuids(1)==[uid]
    cmd,env,receipt=namespace_command(args,uid)
    write(ep/f'binding-{os.getpid()}.json',receipt)
    os.execve(REAL_SINGULARITY,cmd,env)

def worker(index):
    p=check();setup();row=p['schedule'][index];n=read(R/'native.json');ep=R/f'episode-{index}'
    os.sched_setaffinity(0,n['cpu_slots'][row['slot']]);uid=n['gpu_uuids'][row['slot']]
    os.environ.update(CUDA_VISIBLE_DEVICES=uid,DOJO_GPU_UUIDS=uid,POLICY9B_EPISODE=str(ep),
        DOJO_WORKER_IDENTITY_PATH=str(ep/'identity.json'),DOJO_EXECUTION_ID=f"{n['job']}.{n['step']}:{index}",
        PATH=str(R/'bin')+':'+os.environ['PATH'])
    from dojo.main_local_worker import _process_start_ticks,_host_boot_id
    from dojo.utils.experiment_deadline import ExperimentDeadline
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    from dojo.utils.logger import config_logger
    from dojo.core.tasks.constants import EXECUTION_OUTPUT,VALID_SOLUTION,AUX_EVAL_INFO
    from dojo.core.interpreters.jupyter.jupyter_client import JupyterKernelClient
    before=JupyterKernelClient.wait_for_ready
    def ready(self,*a,**kw):
        result=before(self,*a,**kw)
        if result is not True:raise RuntimeError('kernel not ready before candidate execution')
        return result
    JupyterKernelClient.wait_for_ready=ready
    import dojo.core.interpreters.jupyter.jupyter_interpreter as native
    native._gateway_port=lambda:51000+(int(n['job'])%1000)*4+row['slot']
    write(ep/'identity.json',dict(pid=os.getpid(),pgid=os.getpgid(0),process_start_ticks=_process_start_ticks(os.getpid()),
        host_boot_id=_host_boot_id(),gpu_uuids=[uid],container_pid=None,container_process_start_ticks=None))
    deadline=ExperimentDeadline(350);interp=None;error=None;result={}
    try:
        with deadline.activate():
            cfg=RunConfig.load_from_json(R/f'configs/{index}.json');cfg.interpreter.env['CUDA_VISIBLE_DEVICES']=uid
            cfg.validate();config_logger(cfg)
            task=MLEBenchTask(cfg.task);interp=build(cfg.interpreter,INTERPRETER_MAP,data_dir=cfg.task.data_dir)
            state,_=task.prepare(solver_interpreter=interp,eval_interpreter=None)
            oldscore=task._search_only_score
            def capture(name,submission):
                rec=oldscore(name,submission)
                shutil.copyfile(submission,ep/'prediction.private.csv');write(ep/'score.private.json',rec)
                tr=Path(interp.working_dir)/'gpu_training.json'
                if not interp.fetch_file(tr):raise RuntimeError('missing training/RNG receipt')
                write(ep/'training.safe.json',read(tr));return rec
            task._search_only_score=capture
            write(ep/'started.json',dict(wall=time.time(),cpu_affinity=sorted(os.sched_getaffinity(0))))
            state,answer=task.step_task(state,(R/f'programs/action-{index}.private.py').read_text())
            out=answer[EXECUTION_OUTPUT]
            result=dict(valid=bool(answer.get(VALID_SOLUTION)),exit_code=out.exit_code,timed_out=out.timed_out,
                exec_seconds=out.exec_time,executed_sha256=answer.get(AUX_EVAL_INFO,{}).get('executed_code_sha256'))
            assert result['executed_sha256']==row['executed_sha256']
    except BaseException as exc:
        error=dict(type=type(exc).__name__,frames=[dict(file=Path(f.filename).name,line=f.lineno,function=f.name) for f in traceback.extract_tb(exc.__traceback__)])
    finally:
        if interp is not None:
            try:interp.close()
            except BaseException as exc:error=error or dict(type=type(exc).__name__,phase='close')
        write(ep/'finished.json',dict(row,**result,error=error,elapsed_seconds=deadline.elapsed(),wall=time.time()))
    return int(error is not None)

def run():
    p=check();setup();start=time.monotonic();records=[];error=None
    if time.time()>p['latest_start_utc']:
        write(R/'window-refusal.json',dict(no_workers_started=True,wall=time.time()));return 2
    from resource_gpu_identity import gpu_uuids
    from live_identity import cpu_topology
    from live_search_trial_20261009 import owned_cleanup,gpu_sample,process_gone
    assert socket.gethostname().split('.')[0]==p['node']
    cores={}
    for t in cpu_topology():cores.setdefault((t['socket'],t['core']),[]).append(t['logical_cpu'])
    cpus=sorted(min(v) for v in cores.values());assert len(cpus)==8
    own=gpu_uuids(4);assert all(not gpu_sample(u)['pids'] for u in own)
    write(R/'native.json',dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],
        gpu_uuids=own,cpu_slots=[cpus[2*k:2*k+2] for k in range(4)],wall=time.time()))
    try:
        for block in range(8):
            begin=time.monotonic();ps=[];logs=[]
            try:
                for row in p['schedule'][4*block:4*block+4]:
                    i=row['index'];f=(R/f'episode-{i}/worker.private.log').open('xb');logs.append(f)
                    proc=subprocess.Popen([str(PY),'-B',str(R/NAME),'worker','--index',str(i)],stdout=f,stderr=f,start_new_session=True)
                    ps.append((i,proc))
                while any(q.poll() is None for _,q in ps):
                    if time.monotonic()-begin>380 or time.monotonic()-start>CAP-90:raise TimeoutError('batch cap')
                    time.sleep(.5)
            finally:
                for i,q in ps:
                    ep=R/f'episode-{i}';owned_cleanup(q,ep)
                    identity=read(ep/'identity.json') if (ep/'identity.json').exists() else {}
                    clean=bool(identity) and all(process_gone(identity.get(a),identity.get(b)) for a,b in
                        (('pid','process_start_ticks'),('container_pid','container_process_start_ticks')))
                    records.append(dict(index=i,returncode=q.poll(),cleanup=clean))
                for f in logs:f.close()
            assert all(x['returncode']==0 and x['cleanup'] for x in records),'infrastructure/cleanup failure'
            assert all(not gpu_sample(u)['pids'] for u in own)
            while time.monotonic()-begin<390:time.sleep(.5)
    except BaseException as exc:
        error=dict(type=type(exc).__name__,frames=[dict(file=Path(f.filename).name,line=f.lineno,function=f.name) for f in traceback.extract_tb(exc.__traceback__)])
    finally:
        write(R/'closed.json',dict(planned=32,records=records,error=error,elapsed_seconds=time.monotonic()-start,
            cleanup_verified=all(not gpu_sample(u)['pids'] for u in own)))
    return int(error is not None)

def submit():
    p=check();assert time.time()<LATEST_START-60
    assert sha(Path(p['task_image']))==p['task_image_sha256']
    for name,h in p['runtime_files'].items():assert sha(base.D/name)==h
    write(R/'submit-intent.json',dict(plan_sha256=sha(R/'plan.json'),wall=time.time()))
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    v=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.private.out'),
                      '--error='+str(R/'allocation-%j.private.err'),str(R/'run.sbatch')],env=env,text=True,capture_output=True,timeout=25)
    job=v.stdout.strip().split(';')[0]
    if v.returncode or not job.isdigit():raise RuntimeError('ambiguous submission, inspect before any retry')
    write(R/'launch.json',dict(job=job,plan_sha256=sha(R/'plan.json')))
    print(json.dumps(dict(status='SUBMITTED',job=job,root=str(R))))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('action',choices=('qualify','prepare','submit','run','worker'));a.add_argument('--commit');a.add_argument('--node',default='gpu3');a.add_argument('--index',type=int)
    v=a.parse_args()
    if v.action=='qualify':qualify()
    elif v.action=='prepare':prepare(v.commit,v.node)
    elif v.action=='submit':submit()
    elif v.action=='worker':sys.exit(worker(v.index))
    else:sys.exit(run())
