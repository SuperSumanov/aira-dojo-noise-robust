"""Inspect exact source capsule bytes and credential shapes before publication."""
import hashlib
import json
from pathlib import Path,PurePosixPath
import re
import tarfile

root=Path(__file__).parent/'releases/forets-edit-scope-source-20260914'
manifest=json.loads((root/'artifact.json').read_bytes());archive=root/'source.tar'
sha=lambda raw:hashlib.sha256(raw).hexdigest()
if sha(archive.read_bytes())!=manifest['archive_sha256']:raise ValueError('archive hash')
pattern=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
hits=0;files={}
with tarfile.open(archive,'r:') as tar:
    for member in tar:
        path=PurePosixPath(member.name)
        if path.is_absolute() or '..' in path.parts or member.issym() or member.islnk():raise ValueError('unsafe source member')
        if not member.isfile():continue
        raw=tar.extractfile(member).read()
        if member.name in files:raise ValueError('duplicate source member')
        files[member.name]=sha(raw);hits+=len(pattern.findall(raw))
expected=manifest['source_files']
if files!=expected:raise ValueError('source inventory mismatch')
hits+=len(pattern.findall((root/'artifact.json').read_bytes()))
print(json.dumps(dict(files=len(files),credential_shape_hits=hits,archive_sha256=manifest['archive_sha256'],source_tree=manifest['source_tree'])))
if hits:raise SystemExit(2)
