"""Read-only local archive manifest and credential-shape check; never echo hits."""
import hashlib,json,re,tarfile
from pathlib import Path
ROOT=Path(__file__).parent/'releases/forets-cheap-selector-source-20260914-v4'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def main():
    spec=json.loads((ROOT/'artifact.json').read_bytes());tar=ROOT/'source.tar'
    if sha(tar.read_bytes())!=spec['archive_sha256']:raise ValueError('archive')
    seen={};hits=[]
    with tarfile.open(tar) as archive:
        for member in archive.getmembers():
            if member.isdir():continue
            if not member.isfile() or member.name.startswith('/') or '..' in Path(member.name).parts:raise ValueError('archive path/type')
            raw=archive.extractfile(member).read()
            if member.name in seen:raise ValueError('duplicate member')
            seen[member.name]=sha(raw)
            if SECRET.search(raw):hits.append(member.name)
    if seen!=spec['source_files']:raise ValueError('exact member manifest')
    print(json.dumps(dict(archive_sha256=sha(tar.read_bytes()),verified_members=len(seen),credential_shape_hit_files=hits)))
    if hits:raise ValueError('review shape-hit files before publish')
if __name__=='__main__':main()
