"""Fixed-commit Linux fixture validation. No production, protected labels, or models."""
import argparse
import datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import resource
import subprocess
import sys
import time

B = Path('/research/d7/spc/yzyang4')
SECRET = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
NAMES = ('phase1/fresh_grade_capture.py', 'phase1/tests/test_fresh_grade_capture.py',
         'phase1/fresh_grade_boundary.py', 'phase1/scripts/validate_fresh_grader_boundary_fixtures_20260907.py',
         'phase1/scripts/validate_fresh_grade_capture_fixtures_20260908.py',
         'phase1/scripts/run_fresh_grade_capture_validation_20260908.py')


def sha(raw): return hashlib.sha256(raw).hexdigest()


def main(commit):
    assert re.fullmatch('[0-9a-f]{40}', commit)
    start = time.monotonic(); os.umask(0o077)
    out = B/('fresh-grade-capture-'+commit[:12]+'-20260908')
    assert not out.exists()
    def command(argv, limit=60, **kwargs):
        remaining = 600-(time.monotonic()-start)
        assert remaining > 0
        p = subprocess.run(list(map(str, argv)), capture_output=True, timeout=min(limit, remaining), **kwargs)
        assert not SECRET.search(p.stdout+p.stderr), 'credential_shape'
        return p
    def git(name):
        p=command(['git','-C',B/'aira-dojo','show',commit+':'+name])
        assert p.returncode == 0, 'git_source_unavailable'
        return p.stdout
    assert Path(__file__).read_bytes() == git(NAMES[-1]), 'launcher_source_mismatch'
    out.mkdir(); source=out/'source'; source.mkdir(); hashes={}
    def save(name, obj):
        raw=json.dumps(obj,sort_keys=True,indent=2,allow_nan=False).encode()
        assert not SECRET.search(raw)
        with (out/name).open('xb') as f: f.write(raw); f.flush(); os.fsync(f.fileno())
        (out/name).chmod(0o400)
    try:
        for name in NAMES:
            raw=git(name); assert not SECRET.search(raw)
            p=source/name; p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(raw); p.chmod(0o400); hashes[name]=sha(raw)
        inventory=B/'historical-fresh-grader-source-20260907/code_inventory.private.json'
        raw=inventory.read_bytes()
        assert sha(raw)=='a0cb54af0c9c604bde76fd9b3d9a1f838f65462f47e4931b01b0d0c8093c3045'
        inv=json.loads(raw); assert inv['commit']=='507f92e1138bb6e40dac5c6ee7a6758e6424bf97'
        repo=Path(inv['repo']); assert repo.resolve()==repo and len(inv['files'])==187
        for row in inv['files']:
            name=row['relative_code_path']; p=repo/name
            assert name.startswith('mlebench/') and '..' not in name and p.is_file() and not p.is_symlink()
            assert p.stat().st_size<2**20
            raw=p.read_bytes(); assert not SECRET.search(raw)
            assert sha(raw)==row['git_blob_sha256']==row['current_file_sha256']
            dest=source/name; dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(raw); dest.chmod(0o400); hashes[name]=sha(raw)
        (out/'temp').mkdir()
        env={'PATH':'/usr/local/bin:/usr/bin:/bin','CUDA_VISIBLE_DEVICES':'','PYTHONDONTWRITEBYTECODE':'1',
             'PYTHONPATH':str(source),'PYTHONHASHSEED':'6','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1',
             'MKL_NUM_THREADS':'1','TMPDIR':str(out/'temp')}
        save('INTENT.json',dict(source_commit=commit,source_hashes=hashes,grader_commit=inv['commit'],
             cpu_processes=1,seconds_limit=600,fixture_bytes_limit=20*2**20,
             gpu_jobs=0,paid_api_calls=0,model_fits=0,production_deployed=False,
             helper_sha256=sha(Path(__file__).read_bytes()),started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
        # Each child is bounded too; no installation/network/system configuration changes.
        def limits(): resource.setrlimit(resource.RLIMIT_CPU,(120,120))
        def checked(argv, log):
            p=command([sys.executable,'-B',*argv],limit=120,env=env,cwd=source,preexec_fn=limits)
            (out/log).write_bytes(p.stdout+p.stderr)
            assert p.returncode==0, 'fixture_child_failed_'+log
            return p.stdout
        test=checked(['-m','pytest','-q','--tb=short','-p','no:cacheprovider',NAMES[1]],'tests.log')
        assert b'29 passed' in test and b'skipped' not in test
        manifests=[]
        for label in ('A','B'):
            for mode in ('capture','verify'):
                checked(['-m','phase1.scripts.validate_fresh_grade_capture_fixtures_20260908',
                         '--output',str(out/label),'--mode',mode],label+'-'+mode+'.log')
            a=json.loads((out/label/'capture.json').read_bytes())
            b=json.loads((out/label/'verify.json').read_bytes())
            assert a==b and a['cases']==31 and a['tasks']==6
            assert a['network_attempts']==a['real_data_attempts']==0
            manifests.append(a)
        assert [r['fixture'] for r in manifests[0]['rows']]==[r['fixture'] for r in manifests[1]['rows']]
        assert all(sha((source/n).read_bytes())==h for n,h in hashes.items())
        fixture_bytes=sum(p.stat().st_size for letter in ('A','B') for p in (out/letter).rglob('*') if p.is_file())
        assert fixture_bytes <= 20*2**20
        summary=dict(classification='CAPTURE_FIXTURES_NOT_PRODUCTION_OR_MODEL_GAIN',source_commit=commit,
            grader_commit=inv['commit'],source_hashes=hashes,tests_passed=29,tasks=6,cases_per_pass=31,
            passes=2,independent_regrade_passes=2,fixture_bytes=fixture_bytes,seconds=time.monotonic()-start,
            per_pass_summary_sha256={letter:sha((out/letter/'capture.json').read_bytes()) for letter in ('A','B')},
            versions={name:importlib.metadata.version(name) for name in ('numpy','pandas','scipy','scikit-learn','pytest')},
            python=sys.version,network_attempts=0,real_data_attempts=0,model_effect_measured=False,
            source_admission=False,production_deployed=False,helper_sha256=sha(Path(__file__).read_bytes()),
            utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        save('SUMMARY.json',summary)
        print(json.dumps({k:v for k,v in summary.items() if k not in ('source_hashes','python','versions')},sort_keys=True))
    except Exception as e:
        save('FAILED.json',dict(error_type=type(e).__name__,error_text_sha256=sha(str(e).encode()),
             automatic_retry_allowed=False,source_admission=False))
        print('CAPTURE_VALIDATION_FAILED_EVIDENCE_PRESERVED'); sys.exit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--commit',required=True);a=p.parse_args();main(a.commit)
