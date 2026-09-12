"""Export only immutable seed13 code/config; exclude all run data and credentials."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

ROOT=Path('/research/d7/spc/yzyang4/forets-context-e2e-20260912-5xz0w6iy')
TREE='5950c7d3acf1e03173ba2ea7081d8ba6593279d9'
LAUNCHER='launchers/forets_context_20260912.sbatch'
CAPSULE_NAME='release-code-capsule-v3'
LICENSES=Path(__file__).with_name('context-capsule-licenses.tar')
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9a-z_-]{30,}|Bearer\s+[a-z0-9_.-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def main():
    prepared=json.loads((ROOT/'prepared.json').read_bytes());source=json.loads((ROOT/'source-files.json').read_bytes())
    code=json.loads((ROOT/'code/code-manifest.json').read_bytes());files={}
    if prepared['source_tree']!=TREE or len(source)!=237:raise ValueError('different source')
    for prefix,mapping in [('source/',source),('code/',code['files'])]:
        for name,digest in mapping.items():
            path=ROOT/(prefix+name)
            if path.is_symlink() or not path.resolve().is_relative_to(ROOT):raise ValueError('unsafe path')
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('source changed')
            files[prefix+name]=raw
    for name in ('prepared.json','source-files.json','manifest.json','build.json','plan.md',
        'allocation-budget-correction.json','PACKAGE_STATE.json','code/code-manifest.json',
        'forets_environment_session_20260912.py','forets_paid_measurements_20260912.py',
        'forets_paid_failure_verify_20260912.py',LAUNCHER,'launchers/block-1.json'):
        files[name]=(ROOT/name).read_bytes()
    for row in prepared['run_configs']:
        name='configs/'+row['run_id']+'.json';raw=(ROOT/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=row['config_sha256']:raise ValueError('config changed')
        files[name]=raw
    # Caller uses git -c core.autocrlf=false archive and verifies blob equality.
    with tarfile.open(LICENSES) as licenses:
        names={m.name for m in licenses.getmembers() if m.isfile()}
        if names!={'LICENSE','THIRD_PARTY_LICENSES.md'}:raise ValueError('license inventory')
        for name in names:files[name]=licenses.extractfile(name).read()
    for raw in files.values():
        if SECRET.search(raw):raise ValueError('credential-shaped bytes; export blocked')
    output=ROOT/(CAPSULE_NAME+'.tar.gz')
    with output.open('xb') as stream:
        with gzip.GzipFile(filename='',fileobj=stream,mode='wb',mtime=0) as compressed:
            with tarfile.open(fileobj=compressed,mode='w') as archive:
                for name,raw in sorted(files.items()):
                    info=tarfile.TarInfo(name);info.size=len(raw);info.mode=0o700 if name.endswith('.sbatch') or name=='code/bin/singularity' else 0o600
                    archive.addfile(info,io.BytesIO(raw))
    manifest=dict(source_tree=TREE,controller_commit=code['commit'],files=len(files),source_files=len(source),
        controller_files=len(code['files']),archive_bytes=output.stat().st_size,archive_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        credential_shape_hits=0,contains_model_or_task_data=False,contains_results=False)
    with (ROOT/(CAPSULE_NAME+'.json')).open('x') as stream:json.dump(manifest,stream,indent=2)
    print(json.dumps(manifest))


if __name__=='__main__':main()
