"""Fresh input-state reproduction on fixed new task seeds; no policy selection."""
import argparse,json,os,re,shutil,socket,subprocess,tarfile,tempfile
from dataclasses import asdict
from pathlib import Path,PurePosixPath
import run_comparison_spooky_pool_20260919 as old
BASE=old.BASE;SCRIPT=Path(__file__).name
RUNS={1:'5c3f818a9595bd79',2:'1eee3186d26dcbcd'}
TASK='random-acts-of-pizza'
ROOT_PREFIX='comparison-pizza-prefix-20260919-'
SELECT_SECOND=False
PLAN=None
ALLOWED_JOBS={'12535','14146'}

def select_fixed_node(nodes,run):
    candidates=sorted([r for r in nodes if r['run']==run and r['group']=='executed' and r['parents']==[0] and 'draft' in r['operators_used']],key=lambda n:n['step'])
    if len(candidates)!=2 or candidates[0]['step']!=1:raise ValueError('original selected pair')
    return candidates[1 if SELECT_SECOND else 0]

def scope(root):
    root=root.resolve(strict=True)
    if root.parent!=BASE or not re.fullmatch(re.escape(ROOT_PREFIX)+'[a-z0-9_]+',root.name):raise ValueError('scope')
    return root

def prepared(root):
    scope(root);p=old.read(root/'prepared.json')
    if len(p['rows'])!=2 or {r['seed'] for r in p['rows']}!={1,2}:raise ValueError('two fixed prefixes')
    for name,digest in p['files'].items():
        if old.sha((root/name).read_bytes())!=digest:raise ValueError('prepared drift')
    return p

def binding_context(env):
    root=scope(Path(env['FORETS_CURRENT_POOL_ROOT']));identity=Path(env['DOJO_WORKER_IDENTITY_PATH'])
    if identity.parent!=root or identity.name not in ('identity-0.json','identity-1.json'):raise ValueError('identity scope')
    if old.read(root/'execution-claim.json')['job']!=env['SLURM_JOB_ID']:raise ValueError('job identity')
    return identity.with_suffix('.native-binding.json')

def prepare(commit):
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('commit')
    old.source_check();nodes=old.read(old.INPUT/'qwen-readout-v1/nodes.json',old.NODES);selected={}
    for seed,run in RUNS.items():
        n=select_fixed_node(nodes,run)
        if n['parents']!=[0] or 'draft' not in n['operators_used']:raise ValueError('prefix structure')
        selected[n['id']]=(seed,n)
    raw_cases={}
    with tarfile.open(old.INPUT/f'archives/{TASK}.tar.gz','r|gz') as archive:
        for member in archive:
            path=PurePosixPath(member.name)
            if not member.isfile() or path.name!='journal.jsonl' or old.sha(str(path.parent.parent).encode())[:16] not in RUNS.values():continue
            for line in archive.extractfile(member):
                if old.SECRET.search(line):raise ValueError('credential-first journal')
                n=json.loads(line)
                if n.get('id') not in selected:continue
                seed,known=selected[n['id']];code=(n.get('code') or '').encode()
                if old.sha(code)!=known['code_sha256'] or (not SELECT_SECOND and n.get('exit_code')!=1):raise ValueError('original node identity')
                if re.search(rb'/prepared/private|/data/private|/research/[^\s\"\x27]+',code):raise ValueError('unapproved path')
                term=n.get('_term_out') or n.get('term_out') or '';term=''.join(term) if isinstance(term,list) else term
                error=None
                if not SELECT_SECOND:
                    from audit_comparison_third_prefix_20260919 import core
                    error=core(term)
                    if not error.startswith('NameError:'):raise ValueError('preobserved fixed failure class')
                raw_cases[seed]=(n,code,error)
    if set(raw_cases)!={1,2}:raise ValueError('complete extraction')
    root=Path(tempfile.mkdtemp(prefix=ROOT_PREFIX,dir=BASE));old.setup(root,commit)
    from dojo.core.solvers.utils.response import extract_code
    from dojo.config_dataclasses.interpreter.fresh_container import FreshContainerInterpreterConfig
    for name in ('codes','configs','opencl-vendors'):(root/name).mkdir()
    prior=old.read(old.DONOR/'prepared.json')
    for name in old.HELPERS:
        if old.sha((old.DONOR/name).read_bytes())!=prior['files'][name]:raise ValueError('GPU helper drift')
        dst=root/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(old.DONOR/name,dst)
    for name in dict.fromkeys((SCRIPT,'run_comparison_pizza_prefix_20260919.py','run_comparison_spooky_pool_20260919.py','run_comparison_reuse_20260919.py','verify_comparison_reuse_driver_20260919.py','audit_comparison_third_prefix_20260919.py')+((PLAN,) if PLAN else ())):
        shutil.copy2(Path(__file__).with_name(name),root/name)
    (root/'forets_current_pool_20260912.py').write_text('from '+SCRIPT[:-3]+' import binding_context\n')
    (root/'opencl-vendors/nvidia.icd').write_text('libnvidia-opencl.so.1\n')
    rows=[]
    for seed in (1,2):
        i=seed-1;n,raw,error=raw_cases[seed];code=extract_code(raw.decode())
        (root/'codes'/f'{i}.raw.private.py').write_bytes(raw);(root/'codes'/f'{i}.private.py').write_bytes(code.encode())
        cfg=FreshContainerInterpreterConfig(working_dir=str(root/f'work-{i}'),timeout=7200,container_runtime='singularity',
            superimage_directory=str(BASE/'aira-dojo/build/superimage'),superimage_version='2026-07-macos-v1',env={k:'6' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')})
        cfg.validate();old.write(root/'configs'/f'{i}.json',asdict(cfg))
        rows.append(dict(index=i,seed=seed,run=RUNS[seed],task=TASK,node=n['id'],raw_code_sha256=old.sha(raw),code_sha256=old.sha(code.encode()),historical_error=error))
    batch=f'''#!/bin/bash
#SBATCH --job-name=comparison-pizza-prefix
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=12
#SBATCH --time=02:10:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 7740s {BASE}/venvs/aira/bin/python -B {root}/{SCRIPT} coordinate --root {root}
'''
    (root/'run.sbatch').write_text(batch)
    old.write(root/'prepared.json',dict(commit=commit,utc=old.now(),rows=rows,files={str(p.relative_to(root)):old.sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()},
        execution_seconds=7200,allocation_seconds=7800,gpu_hours_cap=7800*2/3600,no_api_or_training=True))
    import verify_comparison_reuse_driver_20260919 as checker
    checker.prepared=prepared;checker.main(root)
    print(json.dumps(dict(status='PREPARED_NOT_SUBMITTED',root=str(root),prepared_sha256=old.sha((root/'prepared.json').read_bytes()))))

def submit(root):
    p=prepared(root);old.source_check()
    if old.read(root/'cpu-preflight.json')['prepared_sha256']!=old.sha((root/'prepared.json').read_bytes()):raise ValueError('preflight')
    image=BASE/'aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif';st=image.stat()
    if (st.st_size,st.st_mtime_ns)!=(19717783552,1784638286000000000):raise ValueError('image')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    ids=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=20).split()
    if set(ids)-ALLOWED_JOBS:raise ValueError('concurrency/QOS')
    old.write(root/'submit-intent.json',dict(utc=old.now(),gpu_hours_cap=p['gpu_hours_cap']))
    result=subprocess.run(['sbatch','--parsable','--chdir='+str(root),'--output='+str(root/'allocation-%j.out'),'--error='+str(root/'allocation-%j.err'),str(root/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=result.stdout.strip().split(';')[0]
    if result.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; no retry')
    old.write(root/'launch.json',dict(job=job,utc=old.now()));print(json.dumps(dict(job=job,root=str(root),gpu_hours_cap=p['gpu_hours_cap'])))

def coordinate(root):
    p=prepared(root);job=os.environ['SLURM_JOB_ID']
    if socket.gethostname().split('.')[0]!='gpu28' or old.read(root/'launch.json')['job']!=job:raise ValueError('allocation')
    old.write(root/'execution-claim.json',dict(job=job,utc=old.now()));children=[]
    for i in (0,1):
        with (root/f'worker-{i}.private.log').open('xb') as out:
            children.append(subprocess.Popen(['srun','--exclusive','--ntasks=1','--cpus-per-task=6','--gres=gpu:1','--time=02:04:00',str(BASE/'venvs/aira/bin/python'),'-B',str(root/SCRIPT),'execute','--root',str(root),'--index',str(i)],stdout=out,stderr=out))
    codes=[child.wait() for child in children];old.write(root/'finished.json',dict(job=job,worker_returncodes=codes,utc=old.now()))

def execute(root,index):
    p=prepared(root);old.setup(root,p['commit']);old.one(root,p['rows'][index])

if __name__=='__main__':
    os.umask(0o077);parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','submit','coordinate','execute']);parser.add_argument('--root',type=Path);parser.add_argument('--commit');parser.add_argument('--index',type=int);a=parser.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='execute':execute(a.root,a.index)
    else:globals()[a.mode](a.root)
