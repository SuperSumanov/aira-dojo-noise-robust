"""Bounded frozen-critic inference on five complete, already-seen fresh pools."""
import argparse,ctypes,hashlib,importlib.util,json,math,os,re,shutil,socket,subprocess,sys,tempfile,time,types,uuid
from pathlib import Path
import local_generator_runtime_20260914 as rt
from forets_e2e_critic_service import SOURCE,INCOMING

SCRIPT=Path(__file__).name
PLAN='comparison_frozen_reward_plan_20260919.json'
SOURCES=[('comparison-pool-20260919-7ujiaajp','394470c82755bdebf02d34c86f7474ef950a178f5718c4c0ca87ac24882e98a5',(1,2,3)),
         ('comparison-spooky-pool-20260919-04qsl2xc','e3337e7affc534e6e0c3e4e2a75571fc08a9b4a7c271877a71073dda5e8917d6',(1,2))]
LOADER={'bradley_terry_server.py':'ebe289b5d22ac8186c8a13c9462aa62782d12cd32c628283081b488468d35fad',
        'bradley_terry_evaluation.py':'31ecf62ecd92a88ee2a4a7b9a3f723081c8075adb448c592b4c62cd2303bd99d'}

def rows_from_sources():
    rows=[]
    for name,digest,seeds in SOURCES:
        root=rt.BASE/name
        if rt.sha(root/'prepared.json')!=digest:raise ValueError('pool identity')
        for source in rt.read(root/'prepared.json')['rows']:
            if source['seed'] not in seeds:continue
            path=root/'codes'/f"{source['index']}.private.py";raw=path.read_bytes()
            if path.is_symlink() or rt.sha(path)!=source['code_sha256'] or rt.SHAPES.search(raw):raise ValueError('code identity/security')
            row={k:source[k] for k in ('task','seed','run','slot','node','code_sha256')}
            row.update(code_path=str(path),source_prepared_sha256=digest);rows.append(row)
    if len(rows)!=30 or len({r['node'] for r in rows})!=30:raise ValueError('complete population')
    groups={}
    for row in rows:groups.setdefault((row['task'],row['seed']),[]).append(row['slot'])
    if len(groups)!=5 or any(sorted(slots)!=list(range(6)) for slots in groups.values()):raise ValueError('complete pools')
    return rows

def model_files():
    for name,digest in LOADER.items():
        if rt.sha(SOURCE/name)!=digest:raise ValueError('delivered loader changed')
    adapter=INCOMING/'unpacked/Qwen3-8B_reward_seed1/checkpoint-100'
    if not adapter.is_dir() or not (INCOMING/'base-metadata/config.json').is_file():raise ValueError('existing model absent')
    files={}
    for path in sorted(adapter.rglob('*')):
        if path.is_file():
            stat=path.stat();files[str(path.relative_to(adapter))]=dict(size=stat.st_size,mtime_ns=stat.st_mtime_ns)
    return dict(adapter=str(adapter),offline_base=str(INCOMING/'base-metadata'),adapter_file_stat=files,loader_sha256=LOADER)

def infer(rows,score):
    for row in rows:
        path=Path(row['code_path'])
        if rt.sha(path)!=row['code_sha256']:raise ValueError('code drift')
        start=time.monotonic();value=score(row['task'],path.read_text())
        if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('nonfinite reward')
        yield {k:v for k,v in row.items() if k!='code_path'}|dict(reward=float(value),inference_seconds=time.monotonic()-start)

def check(root):
    if root.resolve()!=root or root.parent!=rt.BASE or not root.name.startswith('comparison-frozen-reward-20260919-'):raise ValueError('root scope')
    p=rt.read(root/'prepared.json')
    for name,digest in p['files'].items():
        if rt.sha(root/name)!=digest:raise ValueError('prepared code drift')
    if model_files()!=p['model']:raise ValueError('model/loader changed')
    return p

def prepare(commit):
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('commit')
    rows=rows_from_sources();model=model_files();root=Path(tempfile.mkdtemp(prefix='comparison-frozen-reward-20260919-',dir=rt.BASE))
    for name in (SCRIPT,PLAN,'local_generator_runtime_20260914.py','forets_e2e_critic_service.py'):shutil.copy2(Path(__file__).with_name(name),root/name)
    batch='''#!/bin/bash
#SBATCH -p gpu_24h
#SBATCH -w gpu28
#SBATCH --gres=gpu:1
#SBATCH -c 6
#SBATCH --time=00:30:00
#SBATCH --job-name=frozen-reward-pools
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
exec timeout --signal=TERM --kill-after=10s 1750s /research/d7/spc/yzyang4/venvs/aira/bin/python -u -B ROOT/run_comparison_frozen_reward_20260919.py worker --root ROOT
'''.replace('ROOT',str(root))
    (root/'run.sbatch').write_text(batch)
    p=dict(commit=commit,rows=rows,model=model,files={f.name:rt.sha(f) for f in root.iterdir() if f.is_file()},gpu_hours_cap=.5)
    rt.write(root/'prepared.json',p)
    mocked=list(infer(rows,lambda task,code:float(len(code))))
    if len(mocked)!=30 or any(set(r)&{'valid','score','independent_score'} for r in rows):raise ValueError('dispatch/outcome isolation')
    rt.write(root/'cpu.json',dict(status='PASS_EXACT_THIRTY_CODE_DISPATCH_NO_LABELS',prepared_sha256=rt.sha(root/'prepared.json'),cases=len(mocked),model_calls=0))
    print(json.dumps(dict(status='PREPARED',root=str(root),prepared_sha256=rt.sha(root/'prepared.json'),cases=30,gpu_hours_cap=.5)))

def submit(root):
    p=check(root)
    if rt.read(root/'cpu.json')['prepared_sha256']!=rt.sha(root/'prepared.json'):raise ValueError('cpu gate')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    raw=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=25)
    jobs=set(raw.split())
    if not jobs<={'12535','14167'}:raise ValueError('unexpected other job; total GPU gate')
    if shutil.disk_usage(root).free<1024**3:raise ValueError('one GiB output margin')
    rt.write(root/'submit-intent.json',dict(utc=rt.utc(),prepared_sha256=rt.sha(root/'prepared.json'),gpu_hours_cap=.5,concurrent_allowed_job='14167'))
    out=subprocess.run(['sbatch','--parsable','--output='+str(root/'allocation-%j.private.out'),'--error='+str(root/'allocation-%j.private.err'),str(root/'run.sbatch')],env=env,text=True,capture_output=True,timeout=25)
    job=out.stdout.strip().split(';')[0]
    if out.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; no retry')
    rt.write(root/'launch.json',dict(job=job,utc=rt.utc()));print(json.dumps(dict(status='SUBMITTED',job=job,root=str(root),gpu_hours_cap=.5)))

def worker(root):
    p=check(root)
    if socket.gethostname().split('.')[0]!='gpu28' or rt.read(root/'launch.json')['job']!=os.environ['SLURM_JOB_ID']:raise ValueError('allocation')
    for name in tuple(os.environ):
        if name.startswith('PRIMARY_KEY') or name in ('OPENROUTER_API_KEY','OPENAI_API_KEY'):os.environ.pop(name,None)
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1',PYTHON_DOTENV_DISABLED='1',OMP_NUM_THREADS='6',TOKENIZERS_PARALLELISM='false')
    import torch
    if torch.cuda.device_count()!=1 or '3090' not in torch.cuda.get_device_name(0):raise ValueError('single RTX3090 required')
    driver=ctypes.CDLL('libcuda.so.1');device=ctypes.c_int();raw_uuid=(ctypes.c_ubyte*16)()
    if driver.cuInit(0) or driver.cuDeviceGet(ctypes.byref(device),0) or driver.cuDeviceGetUuid(ctypes.byref(raw_uuid),device):raise ValueError('CUDA identity')
    physical='GPU-'+str(uuid.UUID(bytes=bytes(raw_uuid)))
    paired=rt.BASE/'comparison-native-batch-order-20260919-hz3c589n'
    occupied=set(sum(rt.read(paired/'services-ready.json')['uuids'],[]))
    for file in paired.glob('episode-*/identity-*.native-binding.json'):
        occupied.add(rt.read(file)['native_identity']['selected_uuid'])
    if physical in occupied:raise ValueError('critic overlaps paired experiment GPU')
    rt.write(root/'device-identity.json',dict(job=os.environ['SLURM_JOB_ID'],uuid=physical,paired_devices_seen=len(occupied),disjoint=True))
    torch.manual_seed(20260919)
    package=types.ModuleType('frozen_pool_reward');package.__path__=[str(SOURCE)];sys.modules[package.__name__]=package
    start=time.monotonic()
    for name in ('bradley_terry_evaluation','bradley_terry_server'):
        spec=importlib.util.spec_from_file_location(package.__name__+'.'+name,SOURCE/(name+'.py'))
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    service=sys.modules[package.__name__+'.bradley_terry_server'];scorer=service.RewardScorer(p['model']['adapter'],offline_base_dir=p['model']['offline_base'])
    if scorer.max_len!=16384 or scorer.head_frac!=.25 or scorer.task_cond is not True or scorer.model.training:raise ValueError('frozen encoder/eval settings')
    if any(v.device.type!='cuda' or v.dtype!=torch.bfloat16 for v in scorer.model.parameters()):raise ValueError('offload/precision drift')
    rt.write(root/'model-ready.json',dict(job=os.environ['SLURM_JOB_ID'],load_seconds=time.monotonic()-start,context=16384,head_frac=.25,task_cond=True,training=False))
    count=0
    with torch.inference_mode():
        for row in infer(p['rows'],lambda task,code:float(scorer.score_batch([(task,code)])[0])):
            rt.write(root/f'prediction-{count:02d}.json',row);count+=1
    if count!=30:raise ValueError('incomplete predictions')
    rt.write(root/'finished.json',dict(job=os.environ['SLURM_JOB_ID'],utc=rt.utc(),predictions=count,elapsed_seconds=time.monotonic()-start,api_calls=0,training=False))
    print(json.dumps(dict(status='FROZEN_REWARD_COMPLETE',predictions=count)))

if __name__=='__main__':
    os.umask(0o077);parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('prepare','submit','worker'));parser.add_argument('--commit');parser.add_argument('--root',type=Path);a=parser.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='submit':submit(a.root)
    else:worker(a.root)
