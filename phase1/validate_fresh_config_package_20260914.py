"""Isolated CPU source overlay; no active checkout, model request, or GPU launch."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

BASE=Path('/research/d7/spc/yzyang4')
SOURCE=BASE/'forets-wallclock-20260912-88v5m9dr/source'
FILES={
    'src/dojo/core/interpreters/fresh_container.py',
    'src/dojo/config_dataclasses/interpreter/fresh_container.py',
    'src/dojo/config_dataclasses/interpreter/__init__.py',
    'src/dojo/configs/interpreter/fresh_container.yaml',
    'phase1/test_fresh_config_integration_20260914.py',
    'phase1/forets_process_interpreter_20260914.py',
}
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def main(overlay):
    os.umask(0o077)
    before={str(p.relative_to(SOURCE)):sha(p.read_bytes()) for p in (SOURCE/'src').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    root=Path(tempfile.mkdtemp(prefix='forets-fresh-config-20260914-',dir=BASE))
    shutil.copytree(SOURCE/'src',root/'src',ignore=shutil.ignore_patterns('__pycache__'))
    with tarfile.open(overlay) as archive:
        members=archive.getmembers()
        if len(members)!=len(FILES) or {m.name for m in members}!=FILES or any(not m.isfile() for m in members):raise ValueError('exact source overlay required')
        for member in members:
            raw=archive.extractfile(member).read()
            if SECRET.search(raw):raise ValueError('credential shape in code')
            target=root/member.name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    env=dict(os.environ,PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',FORETS_CONFIG_TEST_SOURCE=str(root),
        LOGGING_DIR=str(root),MLE_BENCH_DATA_DIR=str(BASE/'mle-bench-data'),SUPERIMAGE_DIR=str(BASE/'aira-dojo/build/superimage'),
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu')
    for name in ('OPENROUTER_API_KEY','PRIMARY_KEY'):env.pop(name,None)
    run=subprocess.run([sys.executable,'-B',str(root/'phase1/test_fresh_config_integration_20260914.py')],
        cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
    after={str(p.relative_to(SOURCE)):sha(p.read_bytes()) for p in (SOURCE/'src').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    if after!=before:raise ValueError('active source changed')
    if SECRET.search(run.stdout):raise ValueError('credential shape in diagnostic output')
    (root/'tests.txt').write_bytes(run.stdout)
    result=dict(status='PASS_CONFIG_INTEGRATION' if run.returncode==0 else 'CONFIG_TEST_FAILED',root=str(root),
        overlay_sha256=sha(overlay.read_bytes()),code={n:sha((root/n).read_bytes()) for n in sorted(FILES)},
        test_output_sha256=sha(run.stdout),active_source_unchanged=True,api_calls=0,gpu_jobs=0)
    (root/'result.json').write_text(json.dumps(result,sort_keys=True)+'\n')
    print(json.dumps(result));print(run.stdout.decode())
    return run.returncode
if __name__=='__main__':sys.exit(main(Path(sys.argv[1]).resolve(strict=True)))
