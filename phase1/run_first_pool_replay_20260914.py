"""Both programs from every closed run's first pool; zero API, no debug."""
import argparse,datetime as dt,hashlib,json,logging,os,re,shutil,socket,sqlite3,subprocess,sys,tempfile,time
from contextlib import closing
from pathlib import Path
BASE=Path('/research/d7/spc/yzyang4')
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
HELPERS=('forets_closed_pool_native_20260911.py','forets_current_pool_native_20260912.py','forets_gpu_binding_20260911.py',
    'forets_native_cuda_identity_20260911.py','forets_native_gpu_binding_20260911.py','forets_opencl_allowlist_20260911.py',
    'forets_opencl_readonly_ab.py','forets_closed_pool_20260911.py','bin/singularity')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def checked(path,expected=None,secret=True):
    if path.is_symlink():raise ValueError('symlink input')
    raw=path.read_bytes()
    if (expected is not None and sha(raw)!=expected) or (secret and SECRET.search(raw)):raise ValueError('hash/security')
    return raw
def read(path,expected=None):return json.loads(checked(path,expected))
SOURCE_ROOT=BASE/'forets-wallclock-20260912-km65uuej'
SOURCE=SOURCE_ROOT/'source'
TREE='61b48862532d048f5f04a517e3f89b211c59bd3d'
SUMMARY='a2024478c6aa23feb7457d8d45738b51c622725b71eeba928af5e4d0a9dcac82'
DONOR=BASE/'forets-fresh-integration-20260914-ih6u0mpw'
PLAN='CHEAP_FIRST_POOL_REPLAY_PLAN_20260914.md'
DEPENDENCY='13311'

def write(p,v):
    raw=(json.dumps(v,sort_keys=True,allow_nan=False)+'\n').encode()
    with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return sha(raw)
def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def root_check(root):
    root=root.resolve(strict=True)
    if root.parent!=BASE or not re.fullmatch(r'forets-first-pool-replay-20260914-[a-z0-9_]+',root.name):raise ValueError('root scope')
    return root
def source_check():
    a=read(SOURCE_ROOT/'artifact.json')
    if a['source_tree']!=TREE:raise ValueError('source tree')
    for n,h in a['source_files'].items():checked(SOURCE/n,h,False)
def inputs():
    s=read(SOURCE_ROOT/'cheap-selector-summary.json',SUMMARY)
    f=read(SOURCE_ROOT/'readout-finished.json')
    if f['status']!='verified' or f['summary_sha256']!=SUMMARY or len(s['rows'])!=12:raise ValueError('all closed source')
    source_check();sys.path.insert(0,str(SOURCE/'src'))
    from dojo.core.solvers.utils.response import extract_code
    rows=[];codes={};configs={}
    for i,r in enumerate(s['rows']):
        cfg=read(SOURCE_ROOT/'configs'/(r['run_id']+'.json'));cp=Path(cfg['solver']['checkpoint_path']);candidates=[]
        for proof in s['selection_replays']:
            if proof['run_id']!=r['run_id']:continue
            p=cp/'forets-candidates-private'/proof['pool']
            if sha(p.read_bytes())!=proof['sha256']:raise ValueError('pool hash')
            with closing(sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)) as db:raw,h=db.execute('select payload,sha256 from snapshot').fetchone()
            if sha(raw.encode())!=h or SECRET.search(raw.encode()):raise ValueError('pool hash/security')
            v=json.loads(raw)
            if not v['binding'].get('common_start') and len(v['candidates'])==2:candidates.append((v['binding']['step'],proof,v))
        if not candidates:raise ValueError('one source has no initial pool')
        step,proof,v=min(candidates,key=lambda x:x[0])
        if sum(x[0]==step for x in candidates)!=1:raise ValueError('duplicate step')
        for slot in ((0,1) if i%2==0 else (1,0)):
            raw=v['candidates'][slot]['node']['code'];delivered=extract_code(raw);index=len(rows)
            rows.append(dict(index=index,block=1+i//6,source_run_id=r['run_id'],source_seed=r['seed'],task=r['task'],source_arm=r['arm'],
                pool=proof['pool'],pool_sha256=proof['sha256'],step=step,slot=slot,original_selected=slot in v['selected'],raw_code_sha256=sha(raw.encode()),code_sha256=sha(delivered.encode())))
            codes[index]=(raw,delivered);configs[index]=cfg['interpreter']
    if len(rows)!=24:raise ValueError('all24')
    return rows,codes,configs
def prepare(commit):
    if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('commit')
    rows,codes,configs=inputs();prior=read(DONOR/'prepared.json')
    root=Path(tempfile.mkdtemp(prefix='forets-first-pool-replay-20260914-',dir=BASE));(root/'codes').mkdir();(root/'configs').mkdir()
    for n in HELPERS:
        checked(DONOR/n,prior['files'][n],False);dst=root/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(DONOR/n,dst)
    for n in (Path(__file__).name,PLAN,'verify_first_pool_replay_20260914.py','readout_first_pool_replay_20260914.py','readout_forets_generation_capacity_20260912.py'):
        shutil.copy2(Path(__file__).with_name(n),root/n)
    (root/'forets_current_pool_20260912.py').write_text('from run_first_pool_replay_20260914 import binding_context\n')
    (root/'opencl-vendors').mkdir();(root/'opencl-vendors/nvidia.icd').write_text('libnvidia-opencl.so.1\n')
    for row in rows:
        i=row['index'];raw,code=codes[i]
        (root/'codes'/f'{i}.raw.private.py').write_text(raw);(root/'codes'/f'{i}.private.py').write_text(code)
        cfg=configs[i];cfg['working_dir']=str(root/f'work-{i}');cfg['timeout']=300
        write(root/'configs'/f'{i}.json',cfg)
    for block in (1,2):
        script='''#!/bin/bash
#SBATCH --job-name=first-pool-replay-BLOCK
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --time=01:30:00
#SBATCH --no-requeue
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1
srun --exclusive --ntasks=1 --cpus-per-task=6 --gres=gpu:1 --time=01:29:00 timeout --signal=TERM --kill-after=10s 5300s /research/d7/spc/yzyang4/venvs/aira/bin/python -B ROOT/run_first_pool_replay_20260914.py execute --root ROOT --block BLOCK
'''.replace('ROOT',str(root)).replace('BLOCK',str(block))
        (root/f'run-{block}.sbatch').write_text(script)
    files={str(p.relative_to(root)):sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
    mechanism=read(SOURCE_ROOT/'cheap-e2e-mechanism.json','6233085f98cbd9cec440245aee25417ae2e6eb35219ee41b69e233042fcc4185')
    policies=[]
    for i in range(0,24,2):
        row=rows[i];m=next(x for x in mechanism['rows'] if (x['run_id'],x['pool'])==(row['source_run_id'],row['pool']))
        if m['pool_sha256']!=row['pool_sha256']:raise ValueError('frozen policy input')
        policies.append(dict(source_run_id=row['source_run_id'],task=row['task'],seed=row['source_seed'],source_arm=row['source_arm'],pool=row['pool'],pool_sha256=row['pool_sha256'],
            choices=m['choices'],original_initial_labels=m['observed_initial_labels']))
    digest=write(root/'prepared.json',dict(commit=commit,source_tree=TREE,source_summary_sha256=SUMMARY,rows=rows,policies=policies,files=files,api_calls=0,gpu_hours_cap=3,execution_seconds=300,dependency=DEPENDENCY,utc=now()))
    print(json.dumps(dict(root=str(root),prepared_sha256=digest,attempts=24,gpu_hours_cap=3,api_calls=0)))
def prepared(root):
    root_check(root);p=read(root/'prepared.json')
    if p['source_tree']!=TREE or len(p['rows'])!=24 or p['dependency']!=DEPENDENCY:raise ValueError('frozen protocol')
    for n,h in p['files'].items():checked(root/n,h,not n.endswith('bin/singularity'))
    return p
def binding_context(env):
    root=root_check(Path(env['FORETS_CURRENT_POOL_ROOT']));identity=Path(env['DOJO_WORKER_IDENTITY_PATH'])
    if identity.parent!=root or not re.fullmatch(r'identity-([0-9]|1[0-9]|2[0-3])\.json',identity.name):raise ValueError('identity path')
    i=int(identity.stem.split('-')[1]);block=1+i//12
    if read(root/f'execution-claim-{block}.json')['job']!=env['SLURM_JOB_ID']:raise ValueError('allocation')
    return identity.with_suffix('.native-binding.json')
def setup(root,p):
    for n in ('OPENROUTER_API_KEY','PRIMARY_KEY','FORETS_NATIVE_RELEASE','FORETS_CLOSED_POOL_ROOT','FORETS_NATIVE_INTEGRATION_ROOT'):os.environ.pop(n,None)
    os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',LOGGING_DIR=str(root),MLE_BENCH_DATA_DIR=str(BASE/'mle-bench-data'),
        SUPERIMAGE_DIR=str(BASE/'aira-dojo/build/superimage'),DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu',
        FORETS_CURRENT_POOL_ROOT=str(root),FORETS_SOURCE_COMMIT=p['commit'],PATH=str(root/'bin')+':'+os.environ['PATH'],NO_PROXY='localhost,127.0.0.1,0.0.0.0')
    sys.path[:0]=[str(root),str(SOURCE/'src')];logging.disable(logging.CRITICAL)
def one(root,row,factory=None):
    from dojo.config_dataclasses.interpreter.fresh_container import FreshContainerInterpreterConfig
    if factory is None:
        from dojo.core.interpreters.fresh_container import FreshContainerInterpreter
        factory=FreshContainerInterpreter
    i=row['index'];cfg=FreshContainerInterpreterConfig.from_dict(read(root/'configs'/f'{i}.json'));cfg.validate()
    work=Path(cfg.working_dir);work.mkdir(exist_ok=False);identity=root/f'identity-{i}.json';write(identity,{})
    os.environ['DOJO_WORKER_IDENTITY_PATH']=str(identity);start=time.monotonic();worker=None
    out=dict(row,status='infrastructure_unknown',submission_sha256=None,utc=now(),code_timeout_seconds=300)
    try:
        code=checked(root/'codes'/f'{i}.private.py',row['code_sha256']).decode()
        worker=factory(cfg,data_dir=BASE/'mle-bench-data'/row['task']/'prepared/public')
        ans=worker.run(code,file_name='solution.py',include_exec_time=False)
        raw=''.join(ans.term_out).encode()
        if SECRET.search(raw):raise ValueError('credential shape in program output')
        with (root/f'output-{i}.private.log').open('xb') as f:f.write(raw)
        binding=identity.with_suffix('.native-binding.json');checked(binding)
        out.update(status='returned',exit_code=ans.exit_code,timed_out=ans.timed_out,execution_seconds=ans.exec_time,native_binding_sha256=sha(binding.read_bytes()))
        if ans.exit_code==0 and not ans.timed_out:
            path=worker.fetch_file(work/'submission.csv')
            if path is not None:
                if Path(path).is_symlink() or Path(path).resolve()!=work/'submission.csv':raise ValueError('submission scope')
                out['submission_sha256']=sha(Path(path).read_bytes())
    except Exception as e:out.update(status='infrastructure_unknown',error_type=type(e).__name__)
    finally:
        if worker is not None:
            try:worker.close()
            except Exception as e:out.update(status='cleanup_unknown',error_type=type(e).__name__)
        out['wall_seconds']=time.monotonic()-start;write(root/f'result-{i}.json',out)
    return out
def execute(root,block):
    p=prepared(root);source_check();setup(root,p)
    if socket.gethostname().split('.')[0]!='gpu28' or not os.environ.get('SLURM_STEP_ID','').isdigit():raise ValueError('allocated gpu28 required')
    launch=read(root/f'launch-{block}.json')
    if launch['job']!=os.environ['SLURM_JOB_ID']:raise ValueError('job identity')
    write(root/f'execution-claim-{block}.json',dict(job=launch['job'],utc=now()))
    rows=[r for r in p['rows'] if r['block']==block];done=[]
    for row in rows:done.append(one(root,row))
    write(root/f'finished-{block}.json',dict(job=launch['job'],indices=[r['index'] for r in done],completed=len(done),api_calls=0,utc=now()))
    print(json.dumps(dict(block=block,attempted=len(done),api_calls=0)))
def submit(root):
    p=prepared(root);source_check();cpu=read(root/'cpu-preflight.json')
    if cpu['status']!='PASSED_CPU_DRIVER_NOT_GPU_ACCEPTANCE' or cpu['prepared_sha256']!=sha((root/'prepared.json').read_bytes()) or cpu['actual_cases']!=24:raise ValueError('CPU preflight')
    image=BASE/'aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif';st=image.stat()
    if (st.st_size,st.st_mtime_ns)!=(19717783552,1784638286000000000):raise ValueError('original image')
    if shutil.disk_usage(root).free<1024**3:raise ValueError('at least 1GiB filesystem headroom required')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    queue=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=25)
    if len(queue.strip().splitlines())>2:raise ValueError('two job slots unavailable')
    for block in (1,2):
        write(root/f'submit-intent-{block}.json',dict(block=block,dependency=DEPENDENCY,prepared_sha256=sha((root/'prepared.json').read_bytes()),utc=now(),api_calls=0))
        r=subprocess.run(['sbatch','--parsable','--dependency=afterany:'+DEPENDENCY,'--output='+str(root/f'block-{block}-%j.out'),'--error='+str(root/f'block-{block}-%j.err'),str(root/f'run-{block}.sbatch')],env=env,capture_output=True,text=True,timeout=25)
        job=r.stdout.strip().split(';')[0]
        if r.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; do not retry')
        record=dict(block=block,job=job,dependency=DEPENDENCY,utc=now(),prepared_sha256=sha((root/'prepared.json').read_bytes()))
        write(root/f'launch-{block}.json',record);print(json.dumps(record),flush=True)
if __name__=='__main__':
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('mode',choices=('prepare','submit','execute'));p.add_argument('--root',type=Path);p.add_argument('--commit');p.add_argument('--block',type=int,choices=(1,2));a=p.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='execute':execute(a.root,a.block)
    else:submit(a.root)
