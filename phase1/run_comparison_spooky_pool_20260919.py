"""Bounded complete initial pools from NEW shared Qwen development runs only."""
import argparse,datetime as dt,hashlib,json,logging,os,re,shutil,socket,subprocess,sys,tarfile,tempfile,time
from dataclasses import asdict
from pathlib import Path,PurePosixPath

BASE=Path('/research/d7/spc/yzyang4')
INPUT=BASE/'comparison-quarantine-20260919-_tda9fh6'
SOURCE_ROOT=BASE/'forets-wallclock-20260912-km65uuej'
SOURCE=SOURCE_ROOT/'source'
DONOR=BASE/'forets-fresh-integration-20260914-ih6u0mpw'
TREE='61b48862532d048f5f04a517e3f89b211c59bd3d'
STRUCTURE='2d87541d73a597b0d487285949b1c8f306e756ae97dc9fde7c175f83783d7d94'
NODES='370976e31c8a9f501bc75fb7826f529f85b0e34059146291f2e7bb3cab4062c9'
SCRIPT='run_comparison_spooky_pool_20260919.py'
HELPERS=('forets_closed_pool_native_20260911.py','forets_current_pool_native_20260912.py',
 'forets_gpu_binding_20260911.py','forets_native_cuda_identity_20260911.py','forets_native_gpu_binding_20260911.py',
 'forets_opencl_allowlist_20260911.py','forets_opencl_readonly_ab.py','forets_closed_pool_20260911.py','bin/singularity')
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')

def sha(raw):return hashlib.sha256(raw).hexdigest()
def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def read(path,expected=None):
    raw=path.read_bytes()
    if path.is_symlink() or (expected and sha(raw)!=expected) or SECRET.search(raw):raise ValueError('input identity/security')
    return json.loads(raw)
def write(path,obj):
    raw=(json.dumps(obj,sort_keys=True,allow_nan=False)+'\n').encode()
    if SECRET.search(raw):raise ValueError('unsafe receipt')
    with path.open('xb') as h:h.write(raw);h.flush();os.fsync(h.fileno())
    return sha(raw)
def source_check():
    a=read(SOURCE_ROOT/'artifact.json')
    if a['source_tree']!=TREE:raise ValueError('source identity')
    for n,h in a['source_files'].items():
        if sha((SOURCE/n).read_bytes())!=h:raise ValueError('source drift')
def root_check(root):
    root=root.resolve(strict=True)
    if root.parent!=BASE or not re.fullmatch(r'comparison-spooky-pool-20260919-[a-z0-9_]+',root.name):raise ValueError('root scope')
    return root
def setup(root,commit):
    for name in list(os.environ):
        if re.search(r'(?i)(api.?key|primary_key|token|password|secret)',name) or name in ('FORETS_NATIVE_RELEASE','FORETS_CLOSED_POOL_ROOT','FORETS_NATIVE_INTEGRATION_ROOT'):
            os.environ.pop(name,None)
    os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',LOGGING_DIR=str(root),
        MLE_BENCH_DATA_DIR=str(BASE/'mle-bench-data'),SUPERIMAGE_DIR=str(BASE/'aira-dojo/build/superimage'),
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu',
        FORETS_CURRENT_POOL_ROOT=str(root),FORETS_SOURCE_COMMIT=commit,PATH=str(root/'bin')+':'+os.environ['PATH'])
    sys.path[:0]=[str(root),str(SOURCE/'src')];logging.disable(logging.CRITICAL)
def prepared(root):
    root_check(root);p=read(root/'prepared.json')
    if len(p['rows'])!=18 or p['execution_seconds']!=7200:raise ValueError('protocol')
    if (p['allocation_seconds'],p.get('only_seed')) != (9000,None):raise ValueError('schedule protocol')
    if any(r['task']!='spooky-author-identification' for r in p['rows']):raise ValueError('task protocol')
    for n,h in p['files'].items():
        if sha((root/n).read_bytes())!=h:raise ValueError('prepared drift')
    return p
def binding_context(env):
    root=root_check(Path(env['FORETS_CURRENT_POOL_ROOT']));identity=Path(env['DOJO_WORKER_IDENTITY_PATH'])
    if identity.parent!=root or not re.fullmatch(r'identity-(?:[0-9]|1[0-7])\.json',identity.name):raise ValueError('identity scope')
    if read(root/'execution-claim.json')['job']!=env['SLURM_JOB_ID']:raise ValueError('allocation')
    return identity.with_suffix('.native-binding.json')

def prepare(commit,remainder_of=None):
    if remainder_of is not None:raise ValueError('no automatic continuation authorized in this matrix')
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('commit')
    source_check()
    root=Path(tempfile.mkdtemp(prefix='comparison-spooky-pool-20260919-',dir=BASE))
    setup(root,commit)
    from dojo.core.solvers.utils.response import extract_code
    from dojo.config_dataclasses.interpreter.fresh_container import FreshContainerInterpreterConfig
    structure=read(INPUT/'structure.redacted.json',STRUCTURE)
    exported=read(INPUT/'qwen-readout-v1/nodes.json',NODES)
    archive=next(a for a in structure['archives'] if a['archive']=='spooky-author-identification.tar.gz')
    configs={str(PurePosixPath(c['path']).parent):c for c in archive['configs']
             if '/forets-1/' in c['path'] and c['fields'].get('metadata.seed') in (1,2,3)
             and c['fields'].get('solver.operators.draft.llm.client.model_id')=='qwen3.8-27b'
             and c['fields'].get('metadata.launch_time','')[:10]>='2026-09-12'}
    if any(c['fields'].get('solver.num_children')!=6 or c['fields'].get('solver.critic_top_k')!=3
           or c['fields'].get('solver.execution_timeout')!=7200 for c in configs.values()):raise ValueError('historical scope')
    if sorted(c['fields']['metadata.seed'] for c in configs.values())!=[1,2,3]:raise ValueError('all three initial pools')
    wanted={n['id']:n for n in exported if n['run'] in {sha(k.encode())[:16] for k in configs}
            and n['parents']==[0] and 'draft' in n['operators_used']}
    if len(wanted)!=18:raise ValueError('candidate identity')
    codes={}
    with tarfile.open(INPUT/'archives'/archive['archive'],'r|gz') as tf:
        for member in tf:
            p=PurePosixPath(member.name)
            if not member.isfile() or p.name not in ('journal.jsonl','journal_for_unselected.jsonl') or str(p.parent.parent) not in configs:continue
            for line in tf.extractfile(member):
                n=json.loads(line)
                if n.get('id') not in wanted:continue
                code=(n.get('code') or '').encode();known=wanted[n['id']]
                if sha(code)!=known['code_sha256'] or SECRET.search(code) or n['id'] in codes:raise ValueError('candidate drift/security')
                if re.search(rb'/prepared/private|/data/private|/research/[^\s\"\x27]+',code):raise ValueError('unapproved filesystem reference')
                codes[n['id']]=code.decode()
    if set(codes)!=set(wanted):raise ValueError('incomplete extraction')
    for name in ('codes','configs','opencl-vendors'):(root/name).mkdir()
    prior=read(DONOR/'prepared.json')
    for name in HELPERS:
        src=DONOR/name
        if sha(src.read_bytes())!=prior['files'][name]:raise ValueError('adapter changed')
        dst=root/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    for name in (SCRIPT,'COMPARISON_SPOOKY_EXECUTION_20260919.md','readout_comparison_spooky_pool_20260919.py'):
        shutil.copy2(Path(__file__).with_name(name),root/name)
    (root/'forets_current_pool_20260912.py').write_text('from run_comparison_spooky_pool_20260919 import binding_context\n')
    (root/'opencl-vendors/nvidia.icd').write_text('libnvidia-opencl.so.1\n')
    rows=[]
    for k,c in sorted(configs.items(),key=lambda kv:kv[1]['fields']['metadata.seed']):
        run=sha(k.encode())[:16];seed=c['fields']['metadata.seed']
        pool=sorted((n for n in wanted.values() if n['run']==run),key=lambda n:(n['creation_time'],n['id']))
        if len(pool)!=6 or sum(n['group']=='executed' for n in pool)!=2:raise ValueError('six with two selected')
        for slot,n in enumerate(pool):
            i=len(rows);raw=codes[n['id']];code=extract_code(raw)
            (root/'codes'/f'{i}.raw.private.py').write_bytes(raw.encode())
            (root/'codes'/f'{i}.private.py').write_bytes(code.encode())
            cfg=FreshContainerInterpreterConfig(working_dir=str(root/f'work-{i}'),timeout=7200,
                container_runtime='singularity',superimage_directory=str(BASE/'aira-dojo/build/superimage'),
                superimage_version='2026-07-macos-v1',env={n:'6' for n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')})
            cfg.validate();write(root/'configs'/f'{i}.json',asdict(cfg))
            rows.append(dict(index=i,seed=seed,task='spooky-author-identification',run=run,slot=slot,node=n['id'],
                original_selected=n['group']=='executed',raw_code_sha256=sha(raw.encode()),code_sha256=sha(code.encode())))
    batch='''#!/bin/bash
#SBATCH --job-name=comparison-pool-qwen
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:6
#SBATCH --cpus-per-task=36
#SBATCH --time=02:30:00
#SBATCH --no-requeue
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
timeout --signal=TERM --kill-after=10s 8950s /research/d7/spc/yzyang4/venvs/aira/bin/python -B ROOT/run_comparison_spooky_pool_20260919.py coordinate --root ROOT
'''.replace('ROOT',str(root))
    (root/'run.sbatch').write_text(batch)
    files={str(p.relative_to(root)):sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
    p=dict(commit=commit,source_tree=TREE,utc=now(),rows=rows,files=files,execution_seconds=7200,allocation_seconds=9000,gpu_hours_cap=15,api_calls=0)
    h=write(root/'prepared.json',p)
    print(json.dumps(dict(status='PREPARED_NOT_SUBMITTED',root=str(root),prepared_sha256=h,candidates=18,gpu_hours_cap=p['gpu_hours_cap'])),flush=True)

def one(root,row,factory=None):
    from dojo.config_dataclasses.interpreter.fresh_container import FreshContainerInterpreterConfig
    from dojo.config_dataclasses.utils import dataclass_from_dict
    if factory is None:
        from dojo.core.interpreters.fresh_container import FreshContainerInterpreter
        factory=FreshContainerInterpreter
    i=row['index'];cfg=dataclass_from_dict(FreshContainerInterpreterConfig,read(root/'configs'/f'{i}.json'));cfg.validate()
    work=Path(cfg.working_dir);work.mkdir(exist_ok=False);identity=root/f'identity-{i}.json';write(identity,{})
    os.environ['DOJO_WORKER_IDENTITY_PATH']=str(identity);start=time.monotonic();worker=None
    out=dict(row,status='infrastructure_unknown',submission_sha256=None,utc=now(),code_timeout_seconds=7200)
    try:
        code=(root/'codes'/f'{i}.private.py').read_bytes()
        if sha(code)!=row['code_sha256']:raise ValueError('delivered code changed')
        worker=factory(cfg,data_dir=BASE/'mle-bench-data'/row['task']/'prepared/public')
        ans=worker.run(code.decode(),file_name='solution.py',include_exec_time=False)
        raw=''.join(ans.term_out).encode()
        if SECRET.search(raw):raise ValueError('credential shape in program output')
        (root/f'output-{i}.private.log').write_bytes(raw)
        binding=identity.with_suffix('.native-binding.json');b=read(binding)
        if b.get('namespace',{}).get('exact_device_namespace') is not True:raise ValueError('native binding')
        out.update(status='returned',exit_code=ans.exit_code,timed_out=ans.timed_out,execution_seconds=ans.exec_time,native_binding_sha256=sha(binding.read_bytes()))
        if ans.exit_code==0 and not ans.timed_out:
            path=worker.fetch_file(work/'submission.csv')
            if path is not None:
                path=Path(path)
                if path.is_symlink() or path.resolve()!=work/'submission.csv':raise ValueError('submission scope')
                out['submission_sha256']=sha(path.read_bytes())
    except Exception as exc:out.update(status='infrastructure_unknown',error_type=type(exc).__name__)
    finally:
        if worker is not None:
            try:worker.close()
            except Exception as exc:out.update(status='cleanup_unknown',error_type=type(exc).__name__)
        out['wall_seconds']=time.monotonic()-start;write(root/f'result-{i}.json',out)
    return out

def coordinate(root):
    p=prepared(root);source_check();job=os.environ['SLURM_JOB_ID']
    if socket.gethostname().split('.')[0]!='gpu28' or read(root/'launch.json')['job']!=job:raise ValueError('allocation')
    write(root/'execution-claim.json',dict(job=job,utc=now()))
    started=time.monotonic();completed=[];deferred=[]
    schedule=(1,2,3)
    for seed in schedule:
        if p['allocation_seconds']-100-(time.monotonic()-started)<7500:deferred.append(seed);continue
        rows=[r for r in p['rows'] if r['seed']==seed];processes=[]
        write(root/f'pool-start-{seed}.json',dict(seed=seed,job=job,utc=now(),indices=[r['index'] for r in rows]))
        print(json.dumps(dict(event='POOL_START',seed=seed,programs=len(rows))),flush=True)
        for r in rows:
            command=['srun','--exclusive','--ntasks=1','--cpus-per-task=6','--gres=gpu:1','--time=02:04:00',
                str(BASE/'venvs/aira/bin/python'),'-B',str(root/SCRIPT),'execute','--root',str(root),'--index',str(r['index'])]
            with (root/f'worker-{r["index"]}.private.log').open('xb') as out:
                processes.append(subprocess.Popen(command,stdout=out,stderr=out))
        codes=[proc.wait() for proc in processes]
        write(root/f'pool-finished-{seed}.json',dict(seed=seed,worker_returncodes=codes,utc=now()))
        completed.append(seed)
        print(json.dumps(dict(event='POOL_CLOSED',seed=seed,worker_returncodes=codes)),flush=True)
        if any(codes):
            deferred.extend(s for s in schedule if s>seed);break
    write(root/'finished.json',dict(job=job,utc=now(),attempted_seeds=completed,unstarted_seeds=deferred,api_calls=0))

def execute(root,index):
    p=prepared(root);setup(root,p['commit'])
    if not os.environ.get('SLURM_STEP_ID','').isdigit():raise ValueError('srun step required')
    if read(root/'execution-claim.json')['job']!=os.environ['SLURM_JOB_ID']:raise ValueError('allocation')
    one(root,p['rows'][index])

def submit(root):
    p=prepared(root);source_check();cpu=read(root/'cpu-preflight.json')
    if cpu['status']!='PASS' or cpu['prepared_sha256']!=sha((root/'prepared.json').read_bytes()) or cpu['cases']!=18:raise ValueError('CPU preflight')
    image=BASE/'aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif';st=image.stat()
    if (st.st_size,st.st_mtime_ns)!=(19717783552,1784638286000000000):raise ValueError('original image')
    if not (BASE/'mle-bench-data/spooky-author-identification/prepared/public/train.csv').is_file():raise ValueError('public data')
    reserve=root/'own-capacity-check'
    with reserve.open('xb') as h:os.posix_fallocate(h.fileno(),0,256*1024**2)
    reserve.unlink()
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    queue=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=25)
    if len(queue.strip().splitlines())>=4:raise ValueError('job slot cap')
    write(root/'submit-intent.json',dict(utc=now(),prepared_sha256=sha((root/'prepared.json').read_bytes()),gpu_hours_cap=p['gpu_hours_cap']))
    result=subprocess.run(['sbatch','--parsable','--output='+str(root/'allocation-%j.out'),'--error='+str(root/'allocation-%j.err'),str(root/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=result.stdout.strip().split(';')[0]
    if result.returncode or not job.isdigit():raise RuntimeError('ambiguous submit; do not retry')
    write(root/'launch.json',dict(job=job,utc=now(),prepared_sha256=sha((root/'prepared.json').read_bytes())))
    print(json.dumps(dict(job=job,root=str(root),gpu_hours_cap=p['gpu_hours_cap'])),flush=True)

if __name__=='__main__':
    os.umask(0o077);a=argparse.ArgumentParser();a.add_argument('mode',choices=('prepare','submit','coordinate','execute'))
    a.add_argument('--root',type=Path);a.add_argument('--commit');a.add_argument('--index',type=int);a.add_argument('--remainder-of',type=Path);args=a.parse_args()
    try:
        if args.mode=='prepare':prepare(args.commit,args.remainder_of)
        elif args.mode=='submit':submit(args.root)
        elif args.mode=='coordinate':coordinate(args.root)
        else:execute(args.root,args.index)
    except Exception as exc:
        print(json.dumps(dict(status='FAILED',error_type=type(exc).__name__,reason=str(exc) if isinstance(exc,ValueError) else 'details withheld')),flush=True)
        raise SystemExit(2)
