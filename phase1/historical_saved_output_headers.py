"""Header-only readiness for independent regrading of fixed historical runs.

Never opens a tar member, journal, submission, score, or environment payload.
Counts are availability hints, not run qualification or recovered score evidence.
"""
import argparse,collections,hashlib,json,time,tarfile
from pathlib import Path,PurePosixPath

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024**2),b''):h.update(block)
    return h.hexdigest()

def category(name):
    p=PurePosixPath(name);n=p.name.lower()
    if n.endswith(('.csv','.csv.gz','.parquet','.npy','.npz')):
        return 'submission_named_table' if 'submission' in n else 'other_table'
    if n in ('requirements.txt','uv.lock','poetry.lock','pip-freeze.txt','conda-lock.yml'):
        return 'dependency_manifest'
    if n.endswith('.json') and any(x in n for x in ('grade','grading','evaluation','evaluator')):
        return 'possible_grading_record'
    return None

def scan(path,expected_sha,run_roots,seconds=300):
    path=Path(path);deadline=time.monotonic()+seconds
    assert path.is_file() and not path.is_symlink() and path.resolve()==path
    assert sha(path)==expected_sha,'archive_pre_hash'
    before=path.stat();roots={PurePosixPath(root).parts:rid for rid,root in run_roots.items()}
    assert len(roots)==len(run_roots) and roots
    for parts in roots:assert parts and '..' not in parts and not PurePosixPath(*parts).is_absolute()
    assert not any(a!=b and a[:len(b)]==b for a in roots for b in roots),'nested_run_roots'
    counts={r:collections.Counter() for r in run_roots};seen=set();configs=set();headers=0
    with tarfile.open(path,'r|*') as tar:
        for member in tar:
            assert time.monotonic()<deadline,'header_deadline'
            p=PurePosixPath(member.name)
            assert not p.is_absolute() and '..' not in p.parts and member.name not in seen and (member.isdir() or member.isfile()),'unsafe_header'
            seen.add(member.name);headers+=1
            assert headers<=1_000_000,'header_count_cap'
            if not member.isfile():continue
            matched=[rid for parts,rid in roots.items() if p.parts[:len(parts)]==parts]
            assert len(matched)<=1
            if not matched:continue
            rid=matched[0]
            if p==PurePosixPath(run_roots[rid])/'dojo_config.json':configs.add(rid)
            kind=category(member.name)
            if kind:counts[rid][kind]+=1
    after=path.stat()
    assert configs==set(run_roots),'missing_config_headers'
    assert (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)
    assert sha(path)==expected_sha,'archive_post_hash'
    return {'archive_sha256':expected_sha,'archive_headers':headers,'runs':{r:dict(c) for r,c in counts.items()},'member_payloads_opened':0}


if __name__=='__main__':
    raise SystemExit('Use hash-bound fixed-scope orchestrator; no arbitrary corpus CLI.')
