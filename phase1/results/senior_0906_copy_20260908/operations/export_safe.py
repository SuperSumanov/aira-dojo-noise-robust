"""Export exact allowlisted receipts, never archive data or private manifests."""
import hashlib,json,re
from pathlib import Path
B=Path('/research/d7/spc/yzyang4')
items={
    'metadata.json':B/'senior-0906-metadata-20260908/safe_summary.json',
    'source_ready.json':B/'senior-0906-source-20260908/READY.json',
    'space.json':B/'senior-0906-sync-20260908/space_receipt.json',
    'copy.json':B/'senior-0906-sync-20260908/safe_receipt.json',
    'copy_exit.json':B/'senior-0906-source-20260908/COPY_EXIT.json',
    'independent_copy.json':B/'senior-0906-source-20260908/INDEPENDENT_COPY.json',
}
rx=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
out=[]
for name,p in items.items():
    assert p.is_file() and not p.is_symlink() and p.resolve()==p and p.stat().st_size<20000
    raw=p.read_bytes();assert not rx.search(raw) and b'\0' not in raw
    v=json.loads(raw)
    assert not any(k in v for k in ['records','items','archives_manifest','prediction','accuracy','utility'])
    out.append(dict(name=name,text=raw.decode('utf-8'),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
print(json.dumps(dict(status='ALLOWLISTED_SAFE_EXPORT',files=out),sort_keys=True))
