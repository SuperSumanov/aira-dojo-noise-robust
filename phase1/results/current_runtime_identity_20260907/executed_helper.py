"""One fixed existing image; no actual candidate, historical data or scores."""
import datetime,hashlib,json,os,re,signal,subprocess,sys,time
from pathlib import Path
B=Path('/research/d7/spc/yzyang4');C='d045abbddfd64ebabedf3cd919343bc68810db29';O=B/'fresh-runtime-fingerprint-d045abb-20260907'
SIF=B/'aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif';os.umask(0o077)
SECRET=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
E=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(a,timeout=90,env=E,cwd=None):
    p=subprocess.run(list(map(str,a)),capture_output=True,timeout=timeout,env=env,cwd=cwd)
    assert p.returncode==0 and not SECRET.search(p.stdout+p.stderr)
    return p.stdout
def save(n,v):
    raw=json.dumps(v,sort_keys=True,indent=2).encode();assert not SECRET.search(raw)
    with (O/n).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
bundle=Path('/tmp/fresh-runtime-d045abb-complete.bundle')
assert sha(bundle)=='0052a8a014286f60bbc108cb0929326a906e33dda9d7b9780b54b480e9090ccb'
run(['git','-C',B/'aira-dojo','bundle','verify',bundle]);run(['git','-C',B/'aira-dojo','fetch','--no-tags',bundle,C])
assert not O.exists();O.mkdir(mode=0o700);S=O/'source';S.mkdir();hashes={}
for n in ['phase1/fresh_runtime_fingerprint.py','phase1/tests/test_fresh_runtime_fingerprint.py']:
    raw=run(['git','-C',B/'aira-dojo','show',C+':'+n]);p=S/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);hashes[n]=sha(p)
sys.path.insert(0,str(S));from phase1.fresh_runtime_fingerprint import identity,digest,accept
begin=time.monotonic();deadline=begin+1300
save('INTENT.json',{'source_commit':C,'helper_sha256':sha(Path(__file__)),'source_hashes':hashes,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'maximum_seconds':1300,'two_full_image_reads':True,'actual_candidate_programs':0,'real_dataset_reads':0,'gpu_requested':False})
try:
    raw=run([sys.executable,'-B','-m','pytest','-q','--tb=short','-p','no:cacheprovider','phase1/tests/test_fresh_runtime_fingerprint.py'],env=dict(E,PYTHONPATH=str(S)),cwd=S)
    (O/'tests.log').write_bytes(raw);assert b'16 passed' in raw and b' skipped' not in raw
    first=digest(SIF);save('PYTHON_IMAGE_HASH.json',first)
    print('PYTHON_IMAGE_CONTENT_HASH_COMPLETE',flush=True)
    raw=run(['sha256sum','--',SIF],timeout=min(600,max(1,deadline-time.monotonic())))
    (O/'gnu-sha256sum.private').write_bytes(raw)
    second=raw.decode().split()[0];assert re.fullmatch('[0-9a-f]{64}',second)
    value=accept(first,second,identity(SIF));save('IMAGE_VERIFIED.json',value)
    print('INDEPENDENT_IMAGE_CONTENT_HASH_PASS',flush=True)
    for n in ('home','tmp','input','output'):(O/n).mkdir(mode=0o700)
    (O/'input/canary').write_text('fresh-runtime-positive-control\n');(O/'input/canary').chmod(0o400)
    hostnet=os.readlink('/proc/self/ns/net')
    denied=[str(B/'prospective_decision_v1'),str(B/'mle-bench-data'),str(B/'aira-dojo/.env'),'/uac/y24/yzyang4/.ssh',str(O/'INTENT.json')]
    code='''import errno,importlib.metadata as m,json,os,platform,socket
from pathlib import Path
assert Path('/audit-in/canary').read_text()=='fresh-runtime-positive-control\\n'
err=None
try:Path('/audit-in/unexpected').write_text('unexpected')
except OSError as e:err=e.errno
assert err in (errno.EROFS,errno.EACCES)
assert all(not os.path.lexists(x) for x in DENIED)
assert os.readlink('/proc/self/ns/net')!=HOSTNET and all(x[1]=='lo' for x in socket.if_nameindex())
assert not any(k in os.environ for k in ('OPENAI_API_KEY','OPENROUTER_API_KEY','DEEPSEEK_API_KEY','QWEN_API_KEY','DASHSCOPE_API_KEY','HF_TOKEN'))
versions={}
for name in ('numpy','pandas','scipy','scikit-learn','torch','transformers','xgboost','lightgbm','catboost','mlebench'):
    try:versions[name]=m.version(name)
    except m.PackageNotFoundError:versions[name]=None
print(json.dumps({'versions':versions,'python':platform.python_version(),'read_only_bind_enforced':True,
 'negative_paths_hidden':len(DENIED),'isolated_loopback_only_network':True,'known_api_variables_absent':True,
 'package_version_metadata_only':True,'candidate_programs_executed':0,'dataset_payloads_read':0},sort_keys=True))
'''.replace('DENIED',repr(denied)).replace('HOSTNET',repr(hostnet))
    env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':str(O/'home'),'TMPDIR':str(O/'tmp'),
      'SINGULARITY_CACHEDIR':str(O/'cache'),'SINGULARITY_TMPDIR':str(O/'tmp'),'CUDA_VISIBLE_DEVICES':''}
    argv=['singularity','exec','--containall','--cleanenv','--net','--network','none','--no-mount','hostfs,bind-paths,cwd',
      '--bind',str(O/'input')+':/audit-in:ro','--bind',str(O/'output')+':/audit-work:rw','--pwd','/audit-work',str(SIF),'python3','-c',code]
    save('CONTAINER_COMMAND.json',argv)
    raw=run(argv,timeout=min(90,max(1,deadline-time.monotonic())),env=env,cwd=O)
    v=json.loads(raw);assert v['negative_paths_hidden']==5 and v['dataset_payloads_read']==0 and not (O/'input/unexpected').exists()
    assert list(identity(SIF))==first['identity'] and time.monotonic()<deadline
    save('CONTAINER_VERSIONS.json',v)
    final={'classification':'CURRENT_CONTENT_ADDRESSED_RUNTIME_PREPARATION_NOT_HISTORICAL_PROOF_OR_EXECUTION_GAIN',
      'code_commit':C,'image':value,'container':v,'tests_passed':16,'source_admission':False,
      'candidate_programs_executed':0,'real_dataset_reads':0,'gpu_count':0,'api_calls':0,
      'helper_sha256':sha(Path(__file__)),'source_hashes':hashes,'seconds':time.monotonic()-begin,
      'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    save('SUMMARY.json',final);print(json.dumps(final,sort_keys=True),flush=True)
except Exception as e:
    save('FAILED.json',{'class':type(e).__name__,'elapsed_seconds':time.monotonic()-begin,'state':'FAIL_CLOSED_NO_RETRY'})
    print(json.dumps({'status':'FAILED_CLOSED','error_class':type(e).__name__}),flush=True);raise
