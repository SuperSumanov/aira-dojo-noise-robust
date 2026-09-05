import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile

ARCHIVE = Path('/tmp/development_pipeline_0d0bcb7.tar')
CODE = Path('/tmp/development-pipeline-code-0d0bcb7')
OUTPUT = Path('/tmp/development-final-pipeline-0d0bcb7')
os.umask(0o077)
assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() == '3e23a38382057b60d8e167d746d6b67da7039e3a63f3c566d3fc682a9815cac0'
assert not CODE.exists(); CODE.mkdir(mode=0o700)
with tarfile.open(ARCHIVE) as tar:
    for m in tar:
        assert m.isdir() or m.isfile()
        assert not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
        assert m.name.startswith('phase1/') or m.name == 'source_manifest.json' or (m.isdir() and m.name == 'phase1')
    tar.extractall(CODE, filter='data')
manifest = json.loads((CODE/'source_manifest.json').read_bytes())
assert manifest['code_commit'] == '0d0bcb70a6ae688f263b0224f945cd4d543f4f8e'
for relative, desc in manifest['files'].items():
    p = CODE/relative
    assert p.is_file() and not p.is_symlink() and desc == {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
verification = Path('/tmp/critic-entry-cpu-95e72f3-a/independent_verification.json')
verified = json.loads(verification.read_bytes())
assert verified['classification'] == 'INDEPENDENT_PINNED_TRAIN_CPU_LIFECYCLE_NOT_EFFECT'
assert verified['trajectories'] == 16 and verified['actual_state_comparisons'] == 8 and verified['AB_engineering_state_bytes_equal']
verification_sha = hashlib.sha256(verification.read_bytes()).hexdigest()
print(json.dumps({'verification_sha256': verification_sha, 'verified_cpu_trajectories': verified['trajectories']}), flush=True)
env = dict(os.environ, CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
    HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false', PYTHONHASHSEED='0',
    PYTHONPATH=str(CODE), DEVELOPMENT_PIPELINE_COMMIT=manifest['code_commit'])
for stage, runtime, cap in (('tfidf', 'exp', 120), ('neural', 'critic-blackwell-g0-20260905-r5', 300)):
    argv = ['timeout', '--signal=TERM', '--kill-after=10s', str(cap)+'s', 'strace', '-f', '-qq', '-e', 'trace=%file,%process',
        '-o', str(CODE/f'pipeline-{stage}.trace.private'), f'/research/d7/spc/yzyang4/venvs/{runtime}/bin/python',
        '-m', 'phase1.scripts.validate_development_final_pipeline_cpu_20260906', '--stage', stage,
        '--output', str(OUTPUT), '--verification-sha', verification_sha,
        '--source-root', '/research/d7/spc/yzyang4/worktrees/critic-g0-final-only-20260903-b']
    subprocess.run(argv, cwd=CODE, env=env, check=True, timeout=cap+20)
print(json.dumps({'pipeline_summary_sha256': hashlib.sha256((OUTPUT/'summary.json').read_bytes()).hexdigest()}), flush=True)
