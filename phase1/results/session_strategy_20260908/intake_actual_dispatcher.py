"""Deploy once or execute one bounded, in-session intake + original delta audit."""
import datetime,fcntl,hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
BASE=Path('/research/d7/spc/yzyang4');REPO=BASE/'aira-dojo'
COMMIT='28a139f481764951485ad6d278920a2fa3efe62c'
DEPLOY=BASE/'session-0906-source-28a139f-r2';SOURCE=DEPLOY/'source'
OUT=BASE/'session-0906-intake-20260908';PY=BASE/'venvs/exp/bin/python'
CHAIN=BASE/'worktrees/snapshot_delta_chain_monitor_2e59423'
CHAIN_COMMIT='2e59423736747f7d806d50a69fd1f312d4927c48'
CHAIN_REL='phase1/scripts/monitor_prospective_snapshot_delta_chain_20260831.sh'
CHAIN_SHA='d74a5050804cf37dd5a4905453453be315752b2c6e7e25bf3f5ea4d854ebe856'
PATHS=['phase1/scripts/session_0906_intake_once_20260908.py','phase1/scripts/foreground_intake_session_20260905.py',
       'phase1/scripts/run_prospective_continuous_intake_monitor_20260821.sh','phase1/tests/test_session_0906_intake_once.py']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def blob(n):return subprocess.check_output(['git','-C',str(REPO),'show',COMMIT+':'+n],timeout=30)
def save(p,v):
    with p.open('x') as f:json.dump(v,f,sort_keys=True,indent=2);f.flush();os.fsync(f.fileno())
os.umask(0o077)
env=dict(os.environ,PYTHONPATH=str(SOURCE),PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',
    OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
    SNAPSHOT_DELTA_CHAIN_MAX_POLLS='1',SNAPSHOT_DELTA_CHAIN_POLL_SECONDS='300')

def deployment():
    assert not DEPLOY.exists();DEPLOY.mkdir();SOURCE.mkdir()
    hashes={}
    for n in PATHS:
        raw=blob(n);p=SOURCE/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);hashes[n]=sha(p)
    sys.path.insert(0,str(SOURCE))
    from phase1.scripts import foreground_intake_session_20260905 as base
    original=subprocess.check_output(['git','-C',str(REPO),'show',base.COMMIT+':'+base.REL],timeout=30)
    base.validate_derivation(original,(SOURCE/base.REL).read_bytes())
    p=subprocess.run([str(PY),'-B','-m','pytest','-q','-p','no:cacheprovider',PATHS[-1]],cwd=SOURCE,env=env,capture_output=True,timeout=90)
    (DEPLOY/'cpu-tests.log').write_bytes(p.stdout+p.stderr)
    assert p.returncode==0 and b'8 passed' in p.stdout
    save(DEPLOY/'DEPLOYED.json',{'commit':COMMIT,'hashes':hashes,'cpu_tests_passed':8,
        'cpu_log_sha256':sha(DEPLOY/'cpu-tests.log'),'scientific_body_derivation_verified':True,'dispatcher_sha256':sha(Path(__file__))})
    print(json.dumps({'status':'DEPLOYED_NOT_CALLED','commit':COMMIT,'files':len(hashes),'cpu_tests_passed':8}))

def stop_session(pid,sig):
    # Only descendants in the fresh session this dispatcher created, same UID.
    affected=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal():continue
        n=int(p.name)
        try:
            if p.stat().st_uid==os.getuid() and os.getsid(n)==pid:
                os.kill(n,sig);affected.append(n)
        except (ProcessLookupError,FileNotFoundError,PermissionError):pass
    return affected

def invoke(argv,log,deadline):
    remain=deadline-time.monotonic();assert remain>0
    with log.open('xb') as f:
        p=subprocess.Popen(list(map(str,argv)),env=env,cwd=SOURCE,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        try:rc=p.wait(timeout=remain)
        except subprocess.TimeoutExpired:
            term=stop_session(p.pid,signal.SIGTERM)
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:pass
            killed=stop_session(p.pid,signal.SIGKILL);p.wait(timeout=10)
            save(log.with_suffix('.timeout.json'),{'session_leader':p.pid,'terminated_own_session_pids':term,'killed_own_session_pids':killed})
            raise RuntimeError('session_call_timeout')
    assert rc==0,'stage_failed'

def once():
    record=json.loads((DEPLOY/'DEPLOYED.json').read_bytes())
    assert record['commit']==COMMIT and record['dispatcher_sha256']==sha(Path(__file__))
    assert all(sha(SOURCE/n)==h==hashlib.sha256(blob(n)).hexdigest() for n,h in record['hashes'].items())
    sys.path.insert(0,str(SOURCE))
    from phase1.scripts import session_0906_intake_once_20260908 as m
    assert time.time()+2700+30<=m.END
    OUT.mkdir(mode=0o700,exist_ok=True)
    with (OUT/'dispatch.lock').open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        prior=sorted(OUT.glob('wrapper-*.json'));posts=sorted(OUT.glob('post-audit-*.json'))
        assert len(prior)==len(posts),'previous_postaudit_incomplete'
        i=len(prior);assert i<m.MAX_CALLS
        current=(m.base.STATE/'LATEST').read_text().strip()
        expected=m.BASELINE if i==0 else json.loads((OUT/f'poll-{i-1:03d}/receipt.json').read_bytes())['after']['latest']
        assert current==expected
        state=BASE/'prospective-snapshot-delta-chain/monitor_v1/state.tsv'
        assert state.read_text().split('\t')[0]==current,'audit_state_not_current'
        assert subprocess.check_output(['git','-C',str(CHAIN),'rev-parse','HEAD']).decode().strip()==CHAIN_COMMIT
        assert not subprocess.check_output(['git','-C',str(CHAIN),'status','--porcelain','--untracked-files=all']).strip()
        assert sha(CHAIN/CHAIN_REL)==CHAIN_SHA
        log=OUT/f'dispatch-{i:03d}.log';deadline=time.monotonic()+2700
        invoke([PY,'-B','-m','phase1.scripts.session_0906_intake_once_20260908'],log,deadline)
        raw=log.read_bytes();assert not m.base.SECRET.search(raw)
        r=json.loads((OUT/f'poll-{i:03d}/receipt.json').read_bytes())
        after=r['after']['latest']
        if after!=current:invoke(['bash',CHAIN/CHAIN_REL,'--run',CHAIN,CHAIN_COMMIT],OUT/f'delta-{i:03d}.log',deadline)
        assert (m.base.STATE/'LATEST').read_text().strip()==after
        snapshot,artifact,digest=state.read_text().strip().split('\t')
        assert snapshot==after;artifact=Path(artifact)
        assert artifact.is_relative_to(BASE/'prospective-snapshot-delta-chain/artifacts_v1') and sha(artifact/'SHA256SUMS')==digest
        assert (artifact/'COMPLETE').is_file() and not (artifact/'FAILED').exists()
        for line in (artifact/'SHA256SUMS').read_text().splitlines():
            h,n=line.split('  ',1);p=Path(n)
            assert p.is_relative_to(artifact) and not p.is_symlink() and p.is_file() and not p.stat().st_mode&0o222 and sha(p)==h
        assert (artifact/'receipt_a.json').read_bytes()==(artifact/'receipt_b.json').read_bytes()
        assert (artifact/'grounded_a.json').read_bytes()==(artifact/'grounded_b.json').read_bytes()
        a=json.loads((artifact/'receipt_a.json').read_bytes());b=json.loads((artifact/'grounded_a.json').read_bytes())
        assert a['security']==b['security'] and a['transactions']==b['transactions'] and a['inventory']['delta']==b['inventory_delta']
        assert a['security']['outcomes_predictions_accuracy_utility_read'] is False
        assert a['security']['archive_drop_run_endpoint_pair_candidate_identities_emitted'] is False
        assert (artifact/'security.txt').read_text()=='network_hits=0\nforbidden_path_hits=0\ncredential_hits=0\n'
        proof={'poll':i,'source_commit':COMMIT,'snapshot':after,'audit_artifact':str(artifact),'audit_manifest_sha256':digest,
            'foreground_receipt_sha256':sha(OUT/f'poll-{i:03d}/receipt.json'),'wrapper_sha256':sha(OUT/f'wrapper-{i:03d}.json'),
            'outcome_values_read':False,'audit_readonly_verified':True,'next_call_not_before_epoch':r['finished_epoch']+300}
        save(OUT/f'post-audit-{i:03d}.json',proof)
        print(json.dumps({'status':'FOREGROUND_INTAKE_AND_POSTAUDIT_COMPLETE','poll':i,'after':r['after'],
            'next_call_not_before_utc':datetime.datetime.fromtimestamp(r['finished_epoch']+300,datetime.timezone.utc).isoformat(),
            'snapshot_changed':after!=current},sort_keys=True))

if __name__=='__main__':
    assert sys.argv[1:] in (['deploy'],['once'])
    deployment() if sys.argv[1]=='deploy' else once()
