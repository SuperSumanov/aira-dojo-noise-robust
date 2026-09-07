"""Bounded foreground CPU supervisor; not a scheduler or GPU launcher."""
import datetime, fcntl, hashlib, json, os, re, signal, subprocess, sys, time
from pathlib import Path
B=Path('/research/d7/spc/yzyang4')
C='c7c0aa4a0181be51d7c38dfa1942c6b68ca353e9'
TRAIN='88522f74cafcd45778751c5315fa0a89a1704965'
D=B/'partitioned-postflight-source-c7c0aa4-20260907'; S=D/'source'
O=B/'critic-pivot-ampere-partitioned-postflight-20260907'
PY=B/'venvs/critic-blackwell-g0-20260905-r5/bin/python'
SECRET=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
DENY=(b'/prospective_decision_v1/',b'decision_frozen_v11_',b'/target522-',b'/target300-',b'/label_vault/',
 b'/outcome_vault/',b'/prediction_escrow/',b'/external/senior_data/',b'first-960',b'first960')
ENV={'PATH':str(PY.parent)+':/usr/local/bin:/usr/bin:/bin','HOME':str(O/'home'),
 'PYTHONPATH':str(S),'PYTHONDONTWRITEBYTECODE':'1','PYTHONHASHSEED':'6','CUDA_VISIBLE_DEVICES':'',
 'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1',
 'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','SLURM_CONF':'/opt1/slurm/gpu-slurm.conf'}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    assert p.is_file() and not p.is_symlink() and p.stat().st_size<2**20
    raw=p.read_bytes();assert not SECRET.search(raw);return json.loads(raw)
def save(p,value):
    raw=json.dumps(value,sort_keys=True,indent=2,allow_nan=False).encode();assert not SECRET.search(raw)
    with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    p.chmod(0o400)
def cmd(argv,timeout=90):
    p=subprocess.run(list(map(str,argv)),capture_output=True,timeout=timeout)
    assert not SECRET.search(p.stdout+p.stderr) and p.returncode==0,'command_failed'
    return p.stdout

def prepare():
    bundle=Path('/tmp/partitioned-postflight.bundle')
    assert sha(bundle)=='f6a3e9a5f2d65468cd734bec1da8636760101c75b138e7bc2273aa5af5533b5b'
    cmd(['git','-C',B/'aira-dojo','bundle','verify',bundle])
    cmd(['git','-C',B/'aira-dojo','fetch','--no-tags',bundle,C])
    assert not D.exists() and not O.exists();D.mkdir();S.mkdir();O.mkdir();(O/'home').mkdir()
    start=time.time();save(D/'INTENT.json',{'audit_commit':C,'training_commit':TRAIN,'start_epoch':start,
      'end_epoch':start+4800,'helper_sha256':sha(Path(__file__)),'new_gpu_jobs':0})
    ready=read(B/'critic-pivot-ampere/submission-20260907-r3/READY.json')
    assert ready['commit']==TRAIN
    hashes={}
    for n,h in ready['hashes'].items():
        p=Path(ready['control'])/n;assert p.is_file() and not p.is_symlink() and sha(p)==h
        raw=p.read_bytes();assert not SECRET.search(raw)
        target=S/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw);hashes[n]=h
    for n in ('phase1/__init__.py','phase1/partitioned_payload_audit.py',
      'phase1/scripts/partitioned_pivot_postflight_20260907.py','phase1/tests/test_partitioned_payload_audit.py',
      'phase1/tests/test_critic_zero3_payload_observation.py'):
        raw=cmd(['git','-C',B/'aira-dojo','show',C+':'+n]);assert not SECRET.search(raw)
        target=S/n
        if target.exists():assert target.read_bytes()==raw
        else:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        hashes[n]=hashlib.sha256(raw).hexdigest()
    for n in hashes:(S/n).chmod(0o400)
    p=subprocess.run([str(PY),'-B','-m','pytest','-q','--tb=short','-p','no:cacheprovider',
      'phase1/tests/test_partitioned_payload_audit.py','phase1/tests/test_critic_zero3_payload_observation.py'],
      env=ENV,cwd=S,capture_output=True,timeout=180)
    raw=p.stdout+p.stderr;(D/'tests.log').write_bytes(raw);assert not SECRET.search(raw)
    assert p.returncode==0 and b'43 passed' in raw and b'skipped' not in raw,'actual_linux_tests_failed'
    assert all(sha(S/n)==h for n,h in hashes.items())
    save(D/'SOURCE.json',{'audit_commit':C,'training_commit':TRAIN,'files':hashes,
      'tests_passed':True,'tests_count':43,'tests_sha256':sha(D/'tests.log'),
      'helper_sha256':sha(Path(__file__))})
    print(json.dumps({'status':'DEPLOYED_LINUX_TESTED_NOT_PAYLOAD_ACCEPTED','audit_commit':C,
      'tests':43,'files':len(hashes),'source_receipt_sha256':sha(D/'SOURCE.json')},sort_keys=True),flush=True)

def run():
    source=read(D/'SOURCE.json');intent=read(D/'INTENT.json')
    assert source['audit_commit']==C and source['helper_sha256']==sha(Path(__file__))
    assert all(sha(S/n)==h for n,h in source['files'].items())
    with (O/'dispatch.lock').open('a+b') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        for case,rank in [('prefix1',0),('prefix1',1),('resume2',0),('resume2',1),(None,None)]:
            name=f'{case}-rank{rank}' if case else 'final'
            done=O/(name+'-EXIT.json')
            if done.exists():
                prior=read(done);assert prior['returncode']==0 and prior['trace_security_passed'] is True
                print(json.dumps({'status':'ALREADY_COMPLETED_STAGE','stage':name}),flush=True);continue
            assert not (O/(name+'-START.json')).exists(),'unclosed_previous_stage_requires_review'
            assert time.time()+920<=intent['end_epoch'],'whole_cpu_budget_insufficient'
            trace=O/(name+'-filetrace.log');log=O/(name+'-stdout.log')
            args=[str(PY),'-B','-m','phase1.scripts.partitioned_pivot_postflight_20260907']
            args+=['--case',case,'--rank',str(rank)] if case else ['--finalize']
            argv=['strace','-f','-qq','-e','trace=%file','-o',str(trace),*args]
            with log.open('xb') as f:
                p=subprocess.Popen(argv,stdout=f,stderr=subprocess.STDOUT,env=ENV,cwd=S,start_new_session=True)
                start=time.monotonic();save(O/(name+'-START.json'),{'stage':name,'pid':p.pid,'argv':argv,
                  'audit_commit':C,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'limit_seconds':900})
                print(json.dumps({'status':'CPU_STAGE_RUNNING','stage':name,'pid':p.pid}),flush=True)
                timed=False
                try: rc=p.wait(timeout=900)
                except subprocess.TimeoutExpired:
                    timed=True;os.killpg(p.pid,signal.SIGTERM)
                    try:rc=p.wait(timeout=10)
                    except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);rc=p.wait(timeout=10)
            # Inspect only this own synthetic audit's logs; no unrestricted tails.
            raw=log.read_bytes();security=not bool(SECRET.search(raw));h=hashlib.sha256();lines=0
            with trace.open('rb') as f:
                for line in f:
                    security=security and not SECRET.search(line) and not any(x in line for x in DENY)
                    h.update(line);lines+=1
            security=bool(security and lines>0)
            save(done,{'stage':name,'returncode':rc,'timed_out':timed,'elapsed_seconds':time.monotonic()-start,
              'trace_security_passed':security,'trace_sha256':h.hexdigest(),'trace_lines':lines,'stdout_sha256':sha(log)})
            print(json.dumps({'status':'CPU_STAGE_FINISHED','stage':name,'returncode':rc,'timed_out':timed,
              'trace_security_passed':security,'receipt_sha256':sha(done)},sort_keys=True),flush=True)
            assert rc==0 and not timed and security,'stage_failed_closed'
        final=read(O/'FINAL.json')
        assert final['binding']['audit_commit']==C and final['model_effect_measured'] is False
        print(json.dumps({'status':'ALL_PARTS_AND_FINAL_PASS','final_sha256':sha(O/'FINAL.json'),
          'allocated_gpu_seconds':final['allocated_gpu_seconds'],'actual_payload_checks':len(final['actual_payload_checks'])},sort_keys=True),flush=True)

def status():
    rows=[]
    for case,rank in [('prefix1',0),('prefix1',1),('resume2',0),('resume2',1)]:
        name=f'{case}-rank{rank}';p=O/name/'progress.jsonl';last=None
        if p.exists():
            raw=p.read_bytes();assert not SECRET.search(raw)
            values=[json.loads(line) for line in raw.splitlines()]
            last=values[-1] if values else None
        rows.append({'part':name,'progress':last,'complete':(O/name/'COMPLETE.json').exists(),
          'failed':(O/name/'FAILED.json').exists()})
    print(json.dumps({'parts':rows,'final_exists':(O/'FINAL.json').exists()},sort_keys=True))

os.umask(0o077)
assert sys.argv[1:] in (['prepare'],['run'],['status'])
{'prepare':prepare,'run':run,'status':status}[sys.argv[1]]()
