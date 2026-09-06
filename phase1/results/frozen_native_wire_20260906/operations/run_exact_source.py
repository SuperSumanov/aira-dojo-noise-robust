import datetime, hashlib, json, os, re, subprocess, sys, tarfile, time
from pathlib import Path

COMMIT='f5b3f6f4e262e19f0045d15957f93d8223d03af2'
ARCHIVE_SHA='84504067830fa7413fb9165632f908f2bf4cdb75e2b8842b0fe619c503fbf2ba'
ROOT=Path('/tmp/frozen-request-complete-'+COMMIT[:12])
ARCHIVE=ROOT.with_suffix('.tar')
TESTS=['phase1/tests/test_frozen_candidate_requests.py','phase1/tests/test_frozen_improve_operator_bridge.py',
       'phase1/tests/test_frozen_native_template_bridge.py']
SHAPE=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')

if len(sys.argv)>1 and sys.argv[1]=='child':
    os.chdir(ROOT/'source')
    sys.path[:0]=[str(ROOT/'source'),str(ROOT/'source/src')]
    attempts=[]; protected=[]
    def audit(event,args):
        if event in ('socket.connect','socket.connect_ex','socket.getaddrinfo','socket.bind'):
            attempts.append(event)
            raise RuntimeError('network_forbidden_in_native_wire_test')
        if event=='open' and args and isinstance(args[0],(str,bytes)):
            value=os.fsdecode(args[0])
            if 'prospective_decision_v1' in value or re.search(r'(?i)(first[-_]?960|target[-_]?(300|522))',value):
                protected.append(hashlib.sha256(value.encode()).hexdigest())
                raise RuntimeError('protected_path_forbidden')
    sys.addaudithook(audit)
    import importlib.metadata
    import pytest
    versions={name:importlib.metadata.version(name) for name in ('pytest','Jinja2','humanize','hydra-core','omegaconf','PyYAML')}
    rc=pytest.main(['-q','-p','no:cacheprovider','--junitxml='+str(ROOT/'junit.xml'),*TESTS])
    with (ROOT/'child_receipt.json').open('x') as stream:
        json.dump({'python':sys.version,'versions':versions,'pytest_rc':int(rc),'network_attempts':attempts,
            'protected_path_attempt_hashes':protected,'real_api_calls':0,'real_mle_executions':0,
            'source_or_effect_qualification':False},stream,sort_keys=True,indent=2)
    raise SystemExit(rc if rc else bool(attempts or protected))

assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()==ARCHIVE_SHA
assert not ROOT.exists()
ROOT.mkdir(mode=0o700);source=ROOT/'source';source.mkdir()
manifest={}
with tarfile.open(ARCHIVE) as tar:
    for member in tar:
        name=Path(member.name)
        assert not name.is_absolute() and '..' not in name.parts
        assert member.isdir() or member.isfile()
        if member.isdir():continue
        assert member.name not in manifest
        raw=tar.extractfile(member).read();assert not SHAPE.search(raw)
        manifest[member.name]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open('xb') as stream:stream.write(raw)
        dest.chmod(0o444)
assert len(manifest)==210
(ROOT/'home').mkdir(mode=0o700)
env={'PATH':'/usr/bin:/bin','HOME':str(ROOT/'home'),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8',
     'PYTHONPATH':str(source)+':'+str(source/'src'),'PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1',
     'CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1',
     'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','LITELLM_LOCAL_MODEL_COST_MAP':'True',
     'FROZEN_REQUEST_REFERENCE_REPO':'/research/d7/spc/yzyang4/aira-dojo'}
start=time.monotonic()
proc=subprocess.run([sys.executable,'-B',__file__,'child'],env=env,capture_output=True,timeout=240)
assert not SHAPE.search(proc.stdout+proc.stderr),'credential_shape_output_withheld'
for name,raw in [('stdout.log',proc.stdout),('stderr.log',proc.stderr)]:
    with (ROOT/name).open('xb') as stream:stream.write(raw)
for name,row in manifest.items():
    raw=(source/name).read_bytes()
    assert row=={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
summary={'commit':COMMIT,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'archive_sha256':ARCHIVE_SHA,'source_files':len(manifest),'source_unchanged':True,
         'returncode':proc.returncode,'elapsed_seconds':time.monotonic()-start,
         'stdout_sha256':hashlib.sha256(proc.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(proc.stderr).hexdigest()}
with (ROOT/'SUMMARY.json').open('x') as stream:json.dump(summary,stream,sort_keys=True,indent=2)
with (ROOT/'SOURCE_MANIFEST.json').open('x') as stream:json.dump(manifest,stream,sort_keys=True,indent=2)
print(json.dumps(summary))
print(proc.stdout.decode(errors='replace')[-6000:])
print(proc.stderr.decode(errors='replace')[-2000:])
raise SystemExit(proc.returncode)
