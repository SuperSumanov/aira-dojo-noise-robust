"""Fixed third-task full-pool transfer: frozen predictions before fresh execution."""
import argparse,ast,copy,ctypes,hashlib,importlib.util,json,os,re,shutil,socket,subprocess,sys,tarfile,tempfile,time,types,uuid
from dataclasses import asdict
from pathlib import Path,PurePosixPath
import run_comparison_spooky_pool_20260919 as base
import local_generator_runtime_20260914 as rt

SCRIPT=Path(__file__).name;PLAN='comparison_pizza_transfer_plan_20260920.json'
PREFIX='comparison-pizza-transfer-20260920-';TASK='random-acts-of-pizza';SEEDS=(3,4)
GPU_PYTHON=base.BASE/'venvs/exp/bin/python'

def prepared(root):
    if root.resolve(strict=True)!=root or root.parent!=base.BASE or not re.fullmatch(re.escape(PREFIX)+r'[a-z0-9_]+',root.name):raise ValueError('scope')
    p=base.read(root/'prepared.json')
    if len(p['rows'])!=12 or {r['seed'] for r in p['rows']}!=set(SEEDS):raise ValueError('fixed population')
    for name,digest in p['files'].items():
        if base.sha((root/name).read_bytes())!=digest:raise ValueError('prepared drift')
    return p

def binding_context(env):
    root=Path(env['FORETS_CURRENT_POOL_ROOT']);prepared(root);identity=Path(env['DOJO_WORKER_IDENTITY_PATH'])
    if identity.parent!=root or not re.fullmatch(r'identity-(?:[0-9]|1[01])\.json',identity.name):raise ValueError('worker scope')
    if base.read(root/'execution-claim.json')['job']!=env['SLURM_JOB_ID']:raise ValueError('allocation')
    return identity.with_suffix('.native-binding.json')

def population(structure,nodes):
    record,=[a for a in structure['archives'] if a['archive']==TASK+'.tar.gz']
    configs={str(PurePosixPath(c['path']).parent):c for c in record['configs'] if '/forets-1/' in c['path']
        and c['fields'].get('metadata.seed') in SEEDS and c['fields'].get('solver.operators.draft.llm.client.model_id')=='qwen3.8-27b'
        and c['fields'].get('metadata.launch_time','')[:10]>='2026-09-12'}
    if sorted(c['fields']['metadata.seed'] for c in configs.values())!=list(SEEDS):raise ValueError('exact seeds present once')
    for c in configs.values():
        if c['fields'].get('solver.num_children')!=6 or c['fields'].get('solver.critic_top_k')!=3 or c['fields'].get('solver.execution_timeout')!=7200:raise ValueError('source protocol')
    runseed={base.sha(path.encode())[:16]:c['fields']['metadata.seed'] for path,c in configs.items()}
    chosen=[r for r in nodes if r['run'] in runseed and r['parents']==[0] and 'draft' in r['operators_used']]
    if len(chosen)!=12 or len({r['id'] for r in chosen})!=12:raise ValueError('all twelve')
    return configs,runseed,chosen

def cpu(root):
    p=prepared(root);base.setup(root,p['commit']);counts=dict(calls=0,cleanups=0)
    with tempfile.TemporaryDirectory(prefix='cpu-check-',dir=root) as tmp:
        target=Path(tmp);(target/'configs').mkdir();(target/'codes').mkdir()
        for row in p['rows']:
            i=row['index'];cfg=base.read(root/'configs'/f'{i}.json');cfg['working_dir']=str(target/f'work-{i}')
            base.write(target/'configs'/f'{i}.json',cfg);shutil.copy2(root/'codes'/f'{i}.private.py',target/'codes'/f'{i}.private.py')
            class Fake:
                def __init__(self,cfg,data_dir):
                    if cfg.timeout!=7200 or data_dir!=base.BASE/'mle-bench-data'/TASK/'prepared/public' or set(cfg.env.values())!={'6'}:raise ValueError('config')
                    self.work=Path(cfg.working_dir)
                def run(self,code,**kwargs):
                    if base.sha(code.encode())!=row['code_sha256']:raise ValueError('code delivery')
                    counts['calls']+=1;base.write(Path(os.environ['DOJO_WORKER_IDENTITY_PATH']).with_suffix('.native-binding.json'),dict(namespace=dict(exact_device_namespace=True)))
                    (self.work/'submission.csv').write_text('id,requester_received_pizza\n1,0\n')
                    return types.SimpleNamespace(term_out=['CPU_ONLY'],exit_code=0,timed_out=False,exec_time=.001)
                def fetch_file(self,path):return str(path)
                def close(self):counts['cleanups']+=1
            out=base.one(target,row,Fake)
            if out['status']!='returned' or not out['submission_sha256']:raise ValueError('actual native delivery failed')
    if counts!={'calls':12,'cleanups':12}:raise ValueError('matrix')
    from run_comparison_frozen_reward_20260919 import SOURCE,infer
    tree=ast.parse((SOURCE/'bradley_terry_server.py').read_bytes())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='RewardScorer')
    if not any(isinstance(n,ast.FunctionDef) and n.name=='score_batch' for n in cls.body):raise ValueError('actual scorer API')
    score_calls=[]
    class MockScorer:
        def score_batch(self,pairs):
            if len(pairs)!=1 or pairs[0][0]!=TASK:raise ValueError('scorer request shape')
            score_calls.append(base.sha(pairs[0][1].encode()));return [.5]
    output=list(infer([r|dict(code_path=str(root/'codes'/f'{r["index"]}.private.py')) for r in p['rows']],lambda task,code:score_one(MockScorer(),task,code)))
    if score_calls!=[r['code_sha256'] for r in p['rows']] or len(output)!=12:raise ValueError('exact scoring delivery')
    subprocess.run(['bash','-n',str(root/'run.sbatch')],check=True,timeout=10)
    base.write(root/'cpu-preflight.json',dict(status='PASS_ALL_TWELVE_ACTUAL_EXECUTION_PATHS',counts=counts,prepared_sha256=rt.sha(root/'prepared.json'),model_calls=0))

def score_one(scorer,task,code):
    return float(scorer.score_batch([(task,code)])[0])

def prepare(commit):
    if not re.fullmatch('[a-f0-9]{40}',commit) or commit=='0'*40:raise ValueError('real commit')
    base.source_check();structure=base.read(base.INPUT/'structure.redacted.json',base.STRUCTURE);nodes=base.read(base.INPUT/'qwen-readout-v1/nodes.json',base.NODES)
    configs,runseed,pool=population(structure,nodes);wanted={r['id']:r for r in pool};codes={}
    with tarfile.open(base.INPUT/'archives'/f'{TASK}.tar.gz','r|gz') as archive:
        for member in archive:
            path=PurePosixPath(member.name)
            if not member.isfile() or path.name not in ('journal.jsonl','journal_for_unselected.jsonl') or str(path.parent.parent) not in configs:continue
            for line in archive.extractfile(member):
                if base.SECRET.search(line):raise ValueError('credential-first source')
                row=json.loads(line)
                if row.get('id') not in wanted:continue
                code=(row.get('code') or '').encode()
                if row['id'] in codes or base.sha(code)!=wanted[row['id']]['code_sha256']:raise ValueError('code identity')
                if re.search(rb'/prepared/private|/data/private|/research/[^\s\"\x27]+',code):raise ValueError('unapproved path')
                codes[row['id']]=code
    if set(codes)!=set(wanted):raise ValueError('complete codes')
    root=Path(tempfile.mkdtemp(prefix=PREFIX,dir=base.BASE));base.setup(root,commit)
    from dojo.core.solvers.utils.response import extract_code
    from dojo.config_dataclasses.interpreter.fresh_container import FreshContainerInterpreterConfig
    from run_comparison_frozen_reward_20260919 import model_files,interpreter_receipt
    model=model_files();interpreter=interpreter_receipt()
    for name in ('codes','configs','opencl-vendors'):(root/name).mkdir()
    prior=base.read(base.DONOR/'prepared.json')
    for name in base.HELPERS:
        if rt.sha(base.DONOR/name)!=prior['files'][name]:raise ValueError('helper drift')
        dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(base.DONOR/name,dest)
    for name in (SCRIPT,PLAN,'run_comparison_spooky_pool_20260919.py','local_generator_runtime_20260914.py','run_comparison_frozen_reward_20260919.py','forets_e2e_critic_service.py',
                 'readout_comparison_pizza_transfer_20260920.py','comparison_auc_20260920.py'):
        shutil.copy2(Path(__file__).with_name(name),root/name)
    (root/'forets_current_pool_20260912.py').write_text('from '+SCRIPT[:-3]+' import binding_context\n')
    (root/'opencl-vendors/nvidia.icd').write_text('libnvidia-opencl.so.1\n');rows=[]
    for run,seed in sorted(runseed.items(),key=lambda item:item[1]):
        group=sorted((r for r in pool if r['run']==run),key=lambda r:(r['creation_time'],r['id']))
        if len(group)!=6 or sum(r['group']=='executed' for r in group)!=2:raise ValueError('six pool/two original')
        for slot,row in enumerate(group):
            i=len(rows);raw=codes[row['id']];code=extract_code(raw.decode())
            (root/'codes'/f'{i}.private.py').write_bytes(code.encode())
            cfg=FreshContainerInterpreterConfig(working_dir=str(root/f'work-{i}'),timeout=7200,container_runtime='singularity',
                superimage_directory=str(base.BASE/'aira-dojo/build/superimage'),superimage_version='2026-07-macos-v1',env={k:'6' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')})
            cfg.validate();base.write(root/'configs'/f'{i}.json',asdict(cfg))
            rows.append(dict(index=i,task=TASK,seed=seed,run=run,slot=slot,node=row['id'],raw_code_sha256=base.sha(raw),code_sha256=base.sha(code.encode()),original_selected=row['group']=='executed'))
    batch=f'''#!/bin/bash
#SBATCH --job-name=pizza-frozen-transfer
#SBATCH -p gpu_24h
#SBATCH -w gpu28
#SBATCH --gres=gpu:6
#SBATCH -c 36
#SBATCH --time=02:30:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=15s 8940s {base.BASE}/venvs/aira/bin/python -u -B {root}/{SCRIPT} coordinate --root {root}
'''
    (root/'run.sbatch').write_text(batch);files={str(p.relative_to(root)):rt.sha(p) for p in root.rglob('*') if p.is_file()}
    base.write(root/'prepared.json',dict(commit=commit,utc=base.now(),rows=rows,files=files,model=model,interpreter=interpreter,
        execution_seconds=7200,allocation_seconds=9000,gpu_hours_cap=15,api_calls=0,config_sha256={str(seed):configs[path]['sha256'] for path in configs for run,seed in runseed.items() if base.sha(path.encode())[:16]==run}))
    print(json.dumps(dict(status='CPU_START',root=str(root),prepared_sha256=rt.sha(root/'prepared.json'))),flush=True);cpu(root)
    print(json.dumps(dict(status='PREPARED',root=str(root),prepared_sha256=rt.sha(root/'prepared.json'),cases=12,gpu_hours_cap=15)),flush=True)

def score(root):
    p=prepared(root)
    if sys.executable!=str(GPU_PYTHON) or not os.environ.get('SLURM_STEP_ID','').isdigit():raise ValueError('dedicated GPU interpreter/step')
    if base.read(root/'execution-claim.json')['job']!=os.environ['SLURM_JOB_ID']:raise ValueError('allocation')
    for name in tuple(os.environ):
        if re.search(r'(?i)(api.?key|primary_key|token|password|secret)',name):os.environ.pop(name,None)
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHON_DOTENV_DISABLED='1',OMP_NUM_THREADS='6',TOKENIZERS_PARALLELISM='false')
    from run_comparison_frozen_reward_20260919 import model_files,SOURCE,LOADER,infer
    if model_files()!=p['model']:raise ValueError('model drift')
    import torch
    if torch.cuda.device_count()!=1 or '3090' not in torch.cuda.get_device_name(0):raise ValueError('one RTX3090')
    torch.manual_seed(20260920)
    package=types.ModuleType('transfer_reward');package.__path__=[str(SOURCE)];sys.modules[package.__name__]=package
    for name in ('bradley_terry_evaluation','bradley_terry_server'):
        spec=importlib.util.spec_from_file_location(package.__name__+'.'+name,SOURCE/(name+'.py'));module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    start=time.monotonic();service=sys.modules[package.__name__+'.bradley_terry_server'];scorer=service.RewardScorer(p['model']['adapter'],offline_base_dir=p['model']['offline_base'])
    if scorer.max_len!=16384 or scorer.head_frac!=.25 or scorer.task_cond is not True or scorer.model.training:raise ValueError('encoder/eval contract')
    if any(v.device.type!='cuda' or v.dtype!=torch.bfloat16 for v in scorer.model.parameters()):raise ValueError('offload/dtype')
    base.write(root/'model-ready.json',dict(load_seconds=time.monotonic()-start,context=16384,head_frac=.25,task_cond=True,torch_seed=20260920))
    rows=[row|dict(code_path=str(root/'codes'/f'{row["index"]}.private.py')) for row in p['rows']]
    with torch.inference_mode():
        for value in infer(rows,lambda task,code:score_one(scorer,task,code)):base.write(root/f'prediction-{value["index"]}.json',value)
    base.write(root/'prediction-complete.json',dict(cases=12,utc=base.now(),job=os.environ['SLURM_JOB_ID'],prior_program_executions=0))

def coordinate(root):
    p=prepared(root);base.source_check();job=os.environ['SLURM_JOB_ID']
    if socket.gethostname().split('.')[0]!='gpu28' or base.read(root/'launch.json')['job']!=job:raise ValueError('allocation')
    started=time.monotonic();base.write(root/'execution-claim.json',dict(job=job,utc=base.now()))
    env=dict(os.environ)
    for key in ('CUDA_VISIBLE_DEVICES','SLURM_STEP_ID','SLURM_STEP_GPUS','GPU_DEVICE_ORDINAL'):env.pop(key,None)
    with (root/'critic.private.log').open('xb') as log:
        code=subprocess.call(['srun','--exclusive','--ntasks=1','--cpus-per-task=6','--gres=gpu:1','--time=00:15:00',str(GPU_PYTHON),'-B',str(root/SCRIPT),'score','--root',str(root)],env=env,stdout=log,stderr=log)
    if code or not (root/'prediction-complete.json').is_file():raise RuntimeError('fixed critic stage failed; no program execution')
    completed=[];deferred=[]
    for seed in SEEDS:
        if 8900-(time.monotonic()-started)<7500:deferred.append(seed);continue
        rows=[row for row in p['rows'] if row['seed']==seed];processes=[]
        base.write(root/f'pool-start-{seed}.json',dict(seed=seed,utc=base.now(),job=job))
        for row in rows:
            with (root/f'worker-{row["index"]}.private.log').open('xb') as log:
                cmd=['srun','--exclusive','--ntasks=1','--cpus-per-task=6','--gres=gpu:1','--time=02:04:00',str(base.BASE/'venvs/aira/bin/python'),'-B',str(root/SCRIPT),'execute','--root',str(root),'--index',str(row['index'])]
                processes.append(subprocess.Popen(cmd,env=env,stdout=log,stderr=log))
        codes=[proc.wait() for proc in processes];base.write(root/f'pool-finished-{seed}.json',dict(seed=seed,worker_returncodes=codes,utc=base.now()));completed.append(seed)
        if any(codes):deferred.extend(s for s in SEEDS if s>seed);break
    base.write(root/'finished.json',dict(job=job,utc=base.now(),attempted_seeds=completed,unstarted_seeds=deferred))

def submit(root):
    p=prepared(root);base.source_check()
    if base.read(root/'cpu-preflight.json')['prepared_sha256']!=rt.sha(root/'prepared.json'):raise ValueError('cpu gate')
    image=base.BASE/'aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif';st=image.stat()
    if (st.st_size,st.st_mtime_ns)!=(19717783552,1784638286000000000):raise ValueError('original image')
    if not (base.BASE/'mle-bench-data'/TASK/'prepared/public/train.json').is_file():raise ValueError('public task data')
    if shutil.disk_usage(root).free<3*1024**3:raise ValueError('output margin')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    jobs=set(subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=25).split())
    if not jobs<={'12535','14171'}:raise ValueError('eight-GPU cap/owned jobs')
    base.write(root/'submit-intent.json',dict(utc=base.now(),gpu_hours_cap=15,prepared_sha256=rt.sha(root/'prepared.json')))
    result=subprocess.run(['sbatch','--parsable','--output='+str(root/'allocation-%j.private.out'),'--error='+str(root/'allocation-%j.private.err'),str(root/'run.sbatch')],env=env,text=True,capture_output=True,timeout=25)
    job=result.stdout.strip().split(';')[0]
    if result.returncode or not job.isdigit():raise RuntimeError('ambiguous submit; no retry')
    base.write(root/'launch.json',dict(job=job,utc=base.now()));print(json.dumps(dict(status='SUBMITTED',job=job,root=str(root),gpu_hours_cap=15)))

if __name__=='__main__':
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','submit','coordinate','execute','score']);p.add_argument('--root',type=Path);p.add_argument('--commit');p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='execute':
        data=prepared(a.root);base.setup(a.root,data['commit'])
        if not os.environ.get('SLURM_STEP_ID','').isdigit() or base.read(a.root/'execution-claim.json')['job']!=os.environ['SLURM_JOB_ID']:raise ValueError('step identity')
        base.one(a.root,data['rows'][a.index])
    else:globals()[a.mode](a.root)
