"""Execute every runnable fresh debug draw once, at original full task limit."""
import argparse,hashlib,json,os,re,shutil,socket,subprocess,tempfile,time
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace as NS
from run_comparison_spooky_pool_20260919 import BASE,DONOR,HELPERS,TREE,setup,source_check,one,read,write,sha,now,SECRET

GEN=BASE/'comparison-live-debug-20260919-kksebq_4'
GEN_PREPARED='329beee61b95b79430ba95eba45d4da95f170e93a0f0b159848a18aef73b5283'
SCRIPT=Path(__file__).name


def check(root):
    root=root.resolve(strict=True)
    if root.parent!=BASE or not re.fullmatch('comparison-fresh-debug-exec-20260919-[a-z0-9_]+',root.name):raise ValueError('scope')
    p=read(root/'prepared.json')
    if [r['seed'] for r in p['rows']]!=[1,2] or p['program_seconds']!=7200:raise ValueError('matrix')
    for name,digest in p['files'].items():
        if sha((root/name).read_bytes())!=digest:raise ValueError('file drift')
    return p


def binding_context(env):
    root=Path(env['FORETS_CURRENT_POOL_ROOT']);check(root)
    identity=Path(env['DOJO_WORKER_IDENTITY_PATH'])
    if identity.parent!=root or identity.name not in ('identity-0.json','identity-1.json'):raise ValueError('identity path')
    if read(root/'execution-claim.json')['job']!=env['SLURM_JOB_ID']:raise ValueError('allocation')
    return identity.with_suffix('.native-binding.json')


def prepare(commit):
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('commit')
    source_check();g=read(GEN/'prepared.json',GEN_PREPARED)
    for name,digest in g['files'].items():
        if sha((GEN/name).read_bytes())!=digest:raise ValueError('generation preparation changed')
    if read(GEN/'closed.json')['status']!='two_draws_closed':raise ValueError('generation not normally closed')
    rows=read(GEN/'generation-summary.json')['rows']
    if [r['seed'] for r in rows]!=[1,2] or [r['request_seed'] for r in rows]!=[501,502]:raise ValueError('generation matrix')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf');job=read(GEN/'launch.json')['job']
    acc=subprocess.check_output(['sacct','-X','-j',job,'-nP','-o','JobIDRaw,State%24,ElapsedRaw,AllocTRES%120'],env=env,text=True,timeout=25)
    allocation,=[line.split('|') for line in acc.splitlines() if line.split('|')[0]==job]
    if allocation[1]!='COMPLETED':raise ValueError('generation allocation not COMPLETED')
    root=Path(tempfile.mkdtemp(prefix='comparison-fresh-debug-exec-20260919-',dir=BASE));setup(root,commit)
    from dojo.config_dataclasses.interpreter.fresh_container import FreshContainerInterpreterConfig
    for name in ('codes','configs','opencl-vendors'):(root/name).mkdir()
    prior=read(DONOR/'prepared.json')
    for name in HELPERS:
        if sha((DONOR/name).read_bytes())!=prior['files'][name]:raise ValueError('adapter drift')
        dst=root/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(DONOR/name,dst)
    for name in (SCRIPT,'readout_comparison_live_debug_20260919.py'):
        shutil.copy2(Path(__file__).with_name(name),root/name)
    (root/'forets_current_pool_20260912.py').write_text('from run_comparison_live_debug_execute_20260919 import binding_context\n')
    (root/'opencl-vendors/nvidia.icd').write_text('libnvidia-opencl.so.1\n')
    exported=[]
    for index,row in enumerate(rows):
        ready=row['status']=='code_ready'
        result=dict(index=index,seed=row['seed'],request_seed=row['request_seed'],run=row['source_run'],
                    task='spooky-author-identification',node=f'fresh-debug-{row["request_seed"]}',role='fresh_debug',
                    generation_status=row['status'],generation_seconds=row['generation_seconds'],runnable=ready)
        if ready:
            code=(GEN/f'code-{row["seed"]}.private.py').read_bytes()
            if sha(code)!=row['code_sha256'] or SECRET.search(code) or re.search(rb'/prepared/private|/data/private|/research/',code):raise ValueError('generated code identity/security')
            (root/'codes'/f'{index}.private.py').write_bytes(code);result['code_sha256']=sha(code)
            config=FreshContainerInterpreterConfig(working_dir=str(root/f'work-{index}'),timeout=7200,
                container_runtime='singularity',superimage_directory=str(BASE/'aira-dojo/build/superimage'),
                superimage_version='2026-07-macos-v1',env={k:'6' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')})
            config.validate();write(root/'configs'/f'{index}.json',asdict(config))
        exported.append(result)
    n=sum(r['runnable'] for r in exported)
    batch=f'''#!/bin/bash
#SBATCH --job-name=comparison-fresh-debug-exec
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:{n}
#SBATCH --cpus-per-task={6*n}
#SBATCH --time=02:10:00
#SBATCH --no-requeue
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=10s 7750s {BASE}/venvs/aira/bin/python -B {root}/{SCRIPT} coordinate --root {root}
'''
    (root/'run.sbatch').write_text(batch)
    files={str(p.relative_to(root)):sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
    write(root/'prepared.json',dict(commit=commit,source_tree=TREE,utc=now(),files=files,rows=exported,program_seconds=7200,
         allocation_seconds=7800,gpus=n,gpu_hours_cap=n*7800/3600,generation_job=job,generation_allocation_seconds=int(allocation[2]),
         generation_prepared_sha256=GEN_PREPARED,generation_summary_sha256=sha((GEN/'generation-summary.json').read_bytes())))
    cpu(root)
    print(json.dumps(dict(root=str(root),status='PREPARED_NOT_SUBMITTED',runnable=n,prepared_sha256=sha((root/'prepared.json').read_bytes()))),flush=True)


def cpu(root):
    p=check(root);setup(root,p['commit']);calls=0
    with tempfile.TemporaryDirectory(prefix='cpu-check-',dir=root) as temporary:
        target=Path(temporary);(target/'codes').mkdir();(target/'configs').mkdir()
        for row in p['rows']:
            if not row['runnable']:continue
            i=row['index'];cfg=read(root/'configs'/f'{i}.json');cfg['working_dir']=str(target/f'work-{i}')
            write(target/'configs'/f'{i}.json',cfg);shutil.copy2(root/'codes'/f'{i}.private.py',target/'codes'/f'{i}.private.py')
            class Mock:
                def __init__(self,cfg,data_dir):
                    assert cfg.timeout==7200 and set(cfg.env.values())=={'6'} and data_dir.name=='public';self.work=Path(cfg.working_dir)
                def run(self,code,**kw):
                    nonlocal calls
                    assert sha(code.encode())==row['code_sha256'];calls+=1
                    write(Path(os.environ['DOJO_WORKER_IDENTITY_PATH']).with_suffix('.native-binding.json'),dict(namespace=dict(exact_device_namespace=True)))
                    (self.work/'submission.csv').write_text('id,EAP,HPL,MWS\n1,1,0,0\n')
                    return NS(term_out=['mock'],exit_code=0,timed_out=False,exec_time=.001)
                def fetch_file(self,path):return str(path)
                def close(self):pass
            result=one(target,row,Mock)
            if result['status']!='returned' or not result['submission_sha256']:raise ValueError('mock delivery')
    if calls!=p['gpus']:raise ValueError('runnable matrix delivery')
    subprocess.run(['bash','-n',str(root/'run.sbatch')],check=True,timeout=10)
    write(root/'cpu.json',dict(status='PASS',actual_delivery_cases=calls,prepared_sha256=sha((root/'prepared.json').read_bytes())))


def submit(root):
    p=check(root);source_check();cpu=read(root/'cpu.json')
    if cpu['status']!='PASS' or cpu['prepared_sha256']!=sha((root/'prepared.json').read_bytes()):raise ValueError('preflight')
    if not p['gpus']:raise ValueError('no runnable code; no GPU job warranted')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    queue=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=20).splitlines()
    if len(queue)>=4:raise ValueError('job cap')
    image=BASE/'aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif'
    if (image.stat().st_size,image.stat().st_mtime_ns)!=(19717783552,1784638286000000000):raise ValueError('image identity')
    with (root/'capacity.tmp').open('xb') as handle:os.posix_fallocate(handle.fileno(),0,256*1024**2)
    (root/'capacity.tmp').unlink()
    write(root/'submit-intent.json',dict(utc=now(),gpu_hours_cap=p['gpu_hours_cap']))
    result=subprocess.run(['sbatch','--parsable','--chdir='+str(root),'--output='+str(root/'allocation-%j.out'),
         '--error='+str(root/'allocation-%j.err'),str(root/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=result.stdout.strip().split(';')[0]
    if result.returncode or not job.isdigit():raise RuntimeError('ambiguous submit; inspect before retry')
    write(root/'launch.json',dict(job=job,utc=now()));print(json.dumps(dict(status='SUBMITTED',job=job,root=str(root),gpu_hours_cap=p['gpu_hours_cap'])),flush=True)


def coordinate(root):
    p=check(root);source_check();job=os.environ['SLURM_JOB_ID']
    if socket.gethostname().split('.')[0]!='gpu28' or read(root/'launch.json')['job']!=job:raise ValueError('allocation')
    write(root/'execution-claim.json',dict(job=job,utc=now()));processes=[]
    for row in p['rows']:
        if not row['runnable']:continue
        cmd=['srun','--exclusive','--ntasks=1','--cpus-per-task=6','--gres=gpu:1','--time=02:04:00',
              str(BASE/'venvs/aira/bin/python'),'-B',str(root/SCRIPT),'execute','--root',str(root),'--index',str(row['index'])]
        with (root/f'worker-{row["index"]}.private.log').open('xb') as log:processes.append(subprocess.Popen(cmd,stdout=log,stderr=log))
    codes=[child.wait() for child in processes]
    write(root/'finished.json',dict(job=job,utc=now(),worker_returncodes=codes))


def execute(root,index):
    p=check(root);setup(root,p['commit']);row=p['rows'][index]
    if not row['runnable'] or not os.environ.get('SLURM_STEP_ID','').isdigit():raise ValueError('native scheduled step')
    if read(root/'execution-claim.json')['job']!=os.environ['SLURM_JOB_ID']:raise ValueError('job')
    one(root,row)


if __name__=='__main__':
    os.umask(0o077);parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','submit','coordinate','execute']);parser.add_argument('--root',type=Path);parser.add_argument('--commit');parser.add_argument('--index',type=int);args=parser.parse_args()
    if args.mode=='prepare':prepare(args.commit)
    elif args.mode=='execute':execute(args.root,args.index)
    else:globals()[args.mode](args.root)
