"""One explicitly authorized continuation of the time-limited official build.

The failed job/logs are immutable evidence. Only its compiler work directory is
continued; completed objects and the exact ninja command graph must stay equal.
No compiler, architecture, algorithm, model, environment or GPU math fallback.
"""
import hashlib,importlib.util,json,os,re,signal,subprocess,sys,time
from pathlib import Path

BASE=Path('/research/d7/spc/yzyang4')
OLD=BASE/'flash-attn-build-20260907-r3'
ROOT=BASE/'flash-attn-build-20260907-r4'
RUNTIME=BASE/'venvs/critic-blackwell-g0-20260905-r5'
SOURCE=OLD/'source/flash_attn-2.8.3'
BUILD=SOURCE/'build/temp.linux-x86_64-cpython-311'
OLD_SOURCE_SHA='b0e3b1ed8bb7003f41f8d307cda36cca97f08867bd66ca89ffc3d1d5128ee889'
HOST_SHA='52f1ddb33fe78b9441e0f42e9cd22c571f1101938e046c8a26582494e041cc73'
SDIST_SHA='1e71dd64a9e0280e0447b8a0c2541bad4bf6ac65bdeaa2f90e51a9e57de0370d'
COMPILER_SECONDS=4800
GPU_CAP=5760


def require(ok,why):
    if not ok:raise ValueError(why)


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()


def safe(p):
    p=Path(p);require(p.is_absolute() and not any(x.is_symlink() for x in (p,*p.parents)),'unsafe_path')
    require(p.is_file() and p.stat().st_uid==os.getuid() and p.stat().st_nlink==1,'unsafe_file')


def read(p):
    def unique(rows):
        value={}
        for k,v in rows:require(k not in value,'duplicate_receipt_field');value[k]=v
        return value
    safe(p);require(p.stat().st_size<2**20,'receipt_size');return json.loads(p.read_bytes(),object_pairs_hook=unique)


def record(name,value):
    with (ROOT/name).open('x') as f:json.dump(value,f,sort_keys=True,indent=2);f.flush();os.fsync(f.fileno())


def old_source():
    p=OLD/'submission/phase1/scripts/build_fa2_cpu_20260907.py'
    safe(p);require(sha(p)==OLD_SOURCE_SHA,'original_source_drift')
    spec=importlib.util.spec_from_file_location('fixed_prior_fa2_source',p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def completed_objects(log,build):
    """Only completed outputs in the original ninja log are reusable inputs."""
    build=Path(build);seen={}
    require(log.startswith('# ninja log v5\n'),'ninja_log_version')
    for line in log.splitlines()[1:]:
        if not line:continue
        fields=line.split('\t');require(len(fields)==5,'ninja_record_schema')
        start,end,stamp,name,command=fields
        require(all(x.isdecimal() for x in (start,end,stamp)) and int(end)>=int(start)
                and re.fullmatch('[0-9a-f]+',command),'ninja_record_values')
        p=Path(name)
        require(p.is_absolute() and p.suffix=='.o' and '..' not in p.parts,'ninja_object_path')
        try:relative=p.relative_to(build).as_posix()
        except ValueError:raise ValueError('ninja_object_outside_build') from None
        require(relative not in seen,'duplicate_completed_object');safe(p)
        require(p.stat().st_size>4,'empty_completed_object')
        with p.open('rb') as f:require(f.read(4)==b'\x7fELF','object_not_elf')
        seen[relative]={'bytes':p.stat().st_size,'sha256':sha(p),'command_hash':command}
    require(bool(seen),'no_reusable_objects');return seen


def verify_prior(value):
    require(value.get('prior_job')=='12641' and value.get('prior_state')=='FAILED'
            and value.get('prior_elapsed_seconds')==2126 and value.get('prior_gpu_seconds_total')==9423,'prior_identity')
    require(value.get('new_compile_seconds')==COMPILER_SECONDS and value.get('new_gpu_seconds_upper_bound')==GPU_CAP
            and value.get('combined_gpu_seconds_upper_bound')==19023 and 19023<=21600,'approved_resume_budget')
    require(not (OLD/'BUILT.json').exists(),'prior_already_completed')
    require(read(OLD/'compile-timeout.json')['timeout_seconds']==2100,'wrong_prior_failure')
    for relative,h in value['preserved_receipts'].items():safe(OLD/relative);require(sha(OLD/relative)==h,'prior_evidence_drift')
    for relative,h in value['copied_evidence'].items():safe(ROOT/'previous'/relative);require(sha(ROOT/'previous'/relative)==h,'copied_evidence_drift')
    require(completed_objects((ROOT/'previous/ninja.log').read_text(),BUILD)==value['objects'],'original_completion_record_drift')
    require(sha(BUILD/'build.ninja')==value['ninja_graph_sha256'],'ninja_commands_drift')
    for relative,entry in value['objects'].items():
        p=BUILD/relative;safe(p)
        require(entry['bytes']==p.stat().st_size and entry['sha256']==sha(p),'completed_object_drift')
    require(sha(OLD/'flash_attn-2.8.3.tar.gz')==SDIST_SHA,'sdist_drift')
    old_source().verify_source_contents(OLD/'flash_attn-2.8.3.tar.gz',SOURCE,after_build=True)


def invoke(name,args,env,seconds,cwd):
    started=time.monotonic()
    with (ROOT/(name+'.log')).open('xb') as log:
        p=subprocess.Popen(list(map(str,args)),cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:rc=p.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGTERM)
            try:rc=p.wait(timeout=20)
            except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);rc=p.wait(timeout=20)
            record(name+'-timeout.json',{'seconds':seconds,'returncode':rc});raise ValueError('bounded_stage_timeout')
    record(name+'-status.json',{'returncode':rc,'elapsed_seconds':time.monotonic()-started,'log_sha256':sha(ROOT/(name+'.log'))})
    require(rc==0,'stage_failed_'+name)


def main():
    os.umask(0o077);require(ROOT.resolve()==ROOT and sys.executable==str(RUNTIME/'bin/python'),'runtime_path')
    jid=os.environ.get('SLURM_JOB_ID','');commit=os.environ.get('FA2_BUILD_CODE_COMMIT','')
    require(jid.isdecimal() and re.fullmatch('[0-9a-f]{40}',commit),'job_identity')
    require(os.environ.get('SLURM_CPUS_PER_TASK')=='4' and os.environ.get('CUDA_VISIBLE_DEVICES')==''
            and len(os.environ.get('SLURM_JOB_GPUS','').split(','))==1 and os.environ.get('SLURM_JOB_GPUS'),'cpu_build_allocation')
    require(sha('/usr/bin/g++')==HOST_SHA,'node_compiler_drift')
    prior=read(ROOT/'PRIOR_VERIFIED.json');verify_prior(prior)
    import torch
    require(torch.__version__=='2.11.0+cu128' and torch.version.cuda=='12.8'
            and torch._C._GLIBCXX_USE_CXX11_ABI and not torch.cuda.is_initialized(),'torch_binding')
    original=read(OLD/'BUILD_INTENT.json')['original_fingerprints']
    require(all(sha(p)==h for p,h in original.items()),'original_runtime_drift')
    record('BUILD_INTENT.json',{'job_id':jid,'source_commit':commit,'source_script_sha256':sha(Path(__file__)),
        'prior_receipt_sha256':sha(ROOT/'PRIOR_VERIFIED.json'),'original_fingerprints':original,
        'torch':torch.__version__,'cuda':'12.8','arch':'120','cuda_context_created':False,
        'explicit_prior_job':'12641','new_compile_seconds':COMPILER_SECONDS,'automatic_retries':0,
        'gpu_reservation_upper_bound_seconds':GPU_CAP})
    for name in ('wheels','overlay'): (ROOT/name).mkdir()
    cuda=BASE/'private-cuda128-toolchain-20260906/prefix'
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',CUDA_HOME=str(cuda),
        PATH=str(RUNTIME/'bin')+':'+str(cuda/'bin')+':/usr/bin:/bin',PYTHONPATH=str(OLD/'build_deps'),
        PYTHONDONTWRITEBYTECODE='1',MAX_JOBS='2',NVCC_THREADS='2',FLASH_ATTENTION_FORCE_BUILD='TRUE',
        CC='/usr/bin/g++',CXX='/usr/bin/g++',NVCC_CCBIN='/usr/bin/g++',FLASH_ATTN_CUDA_ARCHS='120',
        TMPDIR=str(OLD/'temp'),PIP_NO_INDEX='1',PIP_DISABLE_PIP_VERSION_CHECK='1',HF_HUB_OFFLINE='1',
        TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    pip=[sys.executable,'-m','pip']
    invoke('compile',pip+['wheel','--no-deps','--no-index','--no-build-isolation','--no-cache-dir',
        '--wheel-dir',ROOT/'wheels',SOURCE],env,COMPILER_SECONDS,SOURCE)
    verify_prior(prior)  # All pre-existing successful objects/flags must survive exactly.
    record('SOURCE_POST_VERIFIED.json',old_source().verify_source_contents(OLD/'flash_attn-2.8.3.tar.gz',SOURCE,after_build=True))
    require(sha('/usr/bin/g++')==HOST_SHA,'compiler_changed_during_build')
    wheels=list((ROOT/'wheels').glob('*.whl'))
    require(len(wheels)==1 and re.fullmatch(r'flash_attn-2\.8\.3[^/]*cp311[^/]*linux_x86_64\.whl',wheels[0].name),'wheel_inventory')
    invoke('overlay-install',pip+['install','--no-deps','--no-index','--no-compile','--target',ROOT/'overlay',wheels[0]],env,90,ROOT)
    env['PYTHONPATH']=str(ROOT/'overlay')
    check="import json,torch,flash_attn,flash_attn_2_cuda;assert not torch.cuda.is_initialized();print(json.dumps({'torch':torch.__version__,'flash_attn':flash_attn.__version__,'extension':flash_attn_2_cuda.__file__,'cuda_initialized':False}))"
    invoke('import',[sys.executable,'-B','-c',check],env,60,ROOT)
    require(all(sha(p)==h for p,h in original.items()),'original_runtime_changed')
    files={p.relative_to(ROOT/'overlay').as_posix():sha(p) for p in sorted((ROOT/'overlay').rglob('*')) if p.is_file()}
    record('BUILT.json',{'classification':'ISOLATED_FA2_RESUMED_BUILD_NOT_GPU_ACCEPTANCE',
        'job_id':jid,'source_commit':commit,'wheel':wheels[0].name,'wheel_sha256':sha(wheels[0]),
        'overlay_files':files,'reused_objects':len(prior['objects']),'prior_receipt_sha256':sha(ROOT/'PRIOR_VERIFIED.json'),
        'original_fingerprints_unchanged':True,'gpu_used':False,'prior_completed_objects_unchanged':True})
    print('FA2_RESUMED_BUILD_COMPLETE_NOT_GPU_ACCEPTED',flush=True)


if __name__=='__main__':main()
