import hashlib,json,os,re,subprocess
from pathlib import Path
B=Path('/research/d7/spc/yzyang4');C='c7c0aa4a0181be51d7c38dfa1942c6b68ca353e9';T='88522f74cafcd45778751c5315fa0a89a1704965'
D=B/'partitioned-postflight-source-c7c0aa4-r2-20260907';O=B/'critic-pivot-ampere-partitioned-postflight-20260907'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
r=read(D/'SOURCE.json');assert sha(D/'SOURCE.json')=='9328c4fefebb2f92302a06c166ce318a39759ec128f77ece595ec89caa5bdbbf'
old=read(B/'critic-pivot-ampere/submission-20260907-r3/READY.json')
assert r['audit_commit']==C and r['training_commit']==T and r['tests_count']==43 and r['tests_passed'] is True
assert sha(D/'tests.log')==r['tests_sha256'] and b'43 passed' in (D/'tests.log').read_bytes()
for name,h in r['files'].items():
    p=D/'source'/name;assert p.is_file() and not p.is_symlink() and not p.stat().st_mode&0o222 and p.stat().st_nlink==1
    ref=T if name in old['hashes'] else C
    raw=subprocess.check_output(['git','-C',str(B/'aira-dojo'),'show',ref+':'+name],timeout=30)
    assert hashlib.sha256(raw).hexdigest()==h==sha(p)
assert sha(D/'PREVIOUS_PREPARE.json')==r['previous_prepare_sha256']
prior=read(D/'PREVIOUS_PREPARE.json');assert all(sha(Path(prior['path'])/n)==h for n,h in prior['files_sha256'].items())
assert sha(D/'TEST_TOOLCHAIN.json')==r['test_toolchain_sha256']
test=read(D/'TEST_TOOLCHAIN.json')
assert test['versions']=={'pytest':'7.4.3','pluggy':'1.5.0','iniconfig':'2.1.0'}
assert all(sha(D/'pytest-overlay'/n)==h for n,h in test['files_sha256'].items())
assert test['runtime']['torch']=='2.11.0+cu128' and test['runtime']['deepspeed']=='0.19.3'
assert not test['runtime']['cuda_initialized']
assert sha(B/'critic-pivot-ampere-postflight-12664-20260907/AUTHENTICATED.json')=='522cf8f5e8d3a4ca4f033494e11dc8c7526c2035eb623469b58d30661729e7ce'
assert {p.name for p in O.iterdir()}=={'home'}
proof={'classification':'INDEPENDENT_SOURCE_AND_TEST_OVERLAY_REVIEW_NOT_PAYLOAD_ACCEPTANCE','audit_commit':C,
 'source_receipt_sha256':sha(D/'SOURCE.json'),'source_files':len(r['files']),'linux_tests':43,
 'test_overlay_files':len(test['files_sha256']),'test_runtime_sha256':sha(D/'TEST_TOOLCHAIN.json'),
 'previous_failed_prepare_preserved':True,'gpu_jobs_submitted':0,'helper_sha256':sha(Path(__file__))}
os.umask(0o077)
with (O/'PRE_RELEASE_REVIEW.json').open('x') as f:json.dump(proof,f,sort_keys=True,indent=2);f.flush();os.fsync(f.fileno())
(O/'PRE_RELEASE_REVIEW.json').chmod(0o400)
print(json.dumps(proof,sort_keys=True))
