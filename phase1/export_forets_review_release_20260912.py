"""Export only the exact released code/configs of 13115, never live outcomes.

The generated source tree is not reachable from the published branch. A small
immutable capsule makes its actual executed files accessible without our disk.
No keys, call ledgers, model weights, submissions, task data or run logs.
"""
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

ROOT=Path('/research/d7/spc/yzyang4/forets-review-20260912-csh5q4i8')
PREPARED='e6ec9d4c6664a98a6c069b13cb85624ece78b864adf036591ed34f4c8df18718'
INVENTORY='9fbd2e1a336a96c241a03a837649854b38e1fd0d12991d3bac3f94367df28a6a'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|AKIA[A-Z0-9]{16}|AIza[0-9a-z_-]{30,}|Bearer\s+[a-z0-9_.-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    files={}
    def take(name,expected=None):
        path=ROOT/name
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):raise ValueError('unsafe release path')
        raw=path.read_bytes()
        if expected is not None and sha(raw)!=expected:raise ValueError('released file hash differs')
        if len(raw)>4*1024*1024 or SECRET.search(raw):raise ValueError('oversized or credential-shaped release file')
        if name in files:raise ValueError('duplicate release member')
        files[name]=raw
        return raw
    prepared=json.loads(take('prepared.json',PREPARED))
    inventory=json.loads(take('source-files.json',INVENTORY))
    if prepared['source_tree']!='6ca01fba9892a350cbb24152054b5296dc7095f1':raise ValueError('wrong released source')
    for name,digest in inventory.items():
        if not name.startswith(('src/dojo/','src/aira_core/')):raise ValueError('not released experiment source')
        take('source/'+name,digest)
    code=json.loads(take('code/code-manifest.json'))
    if code['commit']!='a383c2abb5fa9def7e85e7b3313c3894159e7be3':raise ValueError('wrong controller')
    for name,digest in code['files'].items():take('code/'+name,digest)
    for run in prepared['run_configs']:take('configs/'+run['run_id']+'.json',run['config_sha256'])
    for name in ('manifest.json','build.json','paid-authorization.json','plan.md',
                 'launchers/block-1.json','launchers/forets_review_20260912.sbatch',
                 'forets_environment_session_20260912.py'):
        take(name)
    manifest=dict(role='forets_development_release_code_only',source_tree=prepared['source_tree'],
        controller_commit=code['commit'],file_count=len(files),
        files={n:sha(b) for n,b in sorted(files.items())},
        exclusions=['credentials','paid.sqlite','all run outputs and outcomes','model weights','task data'],
        warning='Captured absolute paths are not portable launch authorization. Do not submit the historical job again.')
    output=ROOT/'release-code-capsule.tar.gz'
    with output.open('xb') as raw, gzip.GzipFile(fileobj=raw,mode='wb',mtime=0,filename='') as gz:
        with tarfile.open(fileobj=gz,mode='w|') as archive:
            for name,body in sorted({**files,'CAPSULE_MANIFEST.json':(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode()}.items()):
                info=tarfile.TarInfo(name);info.size=len(body);info.mtime=0
                info.mode=0o700 if name=='code/bin/singularity' else 0o600
                archive.addfile(info,io.BytesIO(body))
    report=dict(source_tree=prepared['source_tree'],controller_commit=code['commit'],
        files=len(files),source_files=len(inventory),controller_files=len(code['files']),
        archive_bytes=output.stat().st_size,archive_sha256=sha(output.read_bytes()),credential_shape_hits=0,
        contains_model_or_task_data=False,contains_results=False)
    with (ROOT/'release-code-capsule.json').open('x') as stream:json.dump(report,stream,indent=2)
    print(json.dumps(report))


if __name__=='__main__':main()
