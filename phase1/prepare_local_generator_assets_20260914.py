"""Bounded public artifact staging on the research disk, without GPU or inference."""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request

BASE = Path('/research/d7/spc/yzyang4')
MODEL = 'cyankiwi/Qwen3.8-27B-AWQ-BF16-INT4'
REV = 'dc430725f831dd90d9271738b877879a46a82239'
IMAGE_BYTES = 7939788800
IMAGE_URL = 'https://drive.usercontent.google.com/download?id=1hhqjRI1LWgyRrd-EXlm4qdCOv_5joAmE&export=download&confirm=t'

def timestamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')

def digest(path, kind='sha256', git_blob=False):
    result = hashlib.new(kind)
    if git_blob:
        result.update(f'blob {path.stat().st_size}\0'.encode())
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            result.update(block)
    return result.hexdigest()

def plan():
    with urllib.request.urlopen(f'https://huggingface.co/api/models/{MODEL}/tree/{REV}?recursive=false&expand=false', timeout=30) as response:
        raw = response.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError('metadata limit')
    entries = json.loads(raw)
    files = []
    for entry in entries:
        name = entry['path']
        if entry['type'] != 'file' or name in ('.gitattributes', 'README.md'):
            continue
        if Path(name).name != name or not 0 < entry['size'] < 20*1024**3:
            raise ValueError('unexpected artifact path/size')
        lfs = entry.get('lfs')
        files.append(dict(path='model/'+name, size=entry['size'], url=f'https://huggingface.co/{MODEL}/resolve/{REV}/{name}',
                          expected=lfs['oid'] if lfs else entry['oid'], digest_kind='sha256' if lfs else 'git_blob_sha1'))
    if sum(x['path'].endswith('.safetensors') for x in files) != 6:
        raise ValueError('expected six shards')
    files.append(dict(path='vllm.sif', size=IMAGE_BYTES, url=IMAGE_URL, expected=None, digest_kind='sha256'))
    total = sum(x['size'] for x in files)
    if total > 55*1024**3:
        raise ValueError('download exceeds fixed 55GiB staging bound')
    root = Path(tempfile.mkdtemp(prefix='local-qwen27b-20260914-', dir=BASE))
    os.chmod(root, 0o700)
    record = dict(utc=timestamp(), root=str(root), model=MODEL, revision=REV, files=files, total_bytes=total,
                  transient_reservation_bytes=total+2*1024**3, max_download_seconds=7200,
                  gpu_jobs=0, inference_calls=0, user_quota_report_available=False)
    save(root/'plan.json', record)
    print(json.dumps(record), flush=True)

def checked(root):
    root = root.resolve(strict=True)
    if root.parent != BASE or not root.name.startswith('local-qwen27b-20260914-'):
        raise ValueError('staging target outside intended parent')
    value = json.loads((root/'plan.json').read_text())
    if value['root'] != str(root) or value['model'] != MODEL or value['revision'] != REV:
        raise ValueError('plan mismatch')
    return root, value

def capacity_required(root, entries):
    missing = 0
    for entry in entries:
        path = root/entry['path']
        if path.is_symlink():
            raise ValueError('artifact symlink not permitted')
        if path.exists():
            if not path.is_file() or path.stat().st_size != entry['size']:
                raise ValueError('existing artifact size/type differs')
        else:
            # Conservatively reserve the whole object when it is still partial.
            missing += entry['size']
    return missing + 2*1024**3


def transfer_limit(size):
    # curl also applies this ceiling to intermediate redirect responses. Small
    # HF objects can have a larger 307 body than their final payload. Final
    # payload size and publisher hash below remain exact, including on resume.
    return max(size, 1024*1024)


def download(root, image_only=False):
    root, value = checked(root)
    entries = [entry for entry in value['files'] if not image_only or entry['path']=='vllm.sif']
    if image_only and (len(entries)!=1 or entries[0]['size']!=IMAGE_BYTES):
        raise ValueError('exact image-only selection')
    receipt = root/('image-complete.json' if image_only else 'complete.json')
    capacity = root/('image-capacity.json' if image_only else 'capacity.json')
    with (root/'download.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        requested = capacity_required(root, entries)
        if (root/'complete.json').exists() or receipt.exists():
            raise ValueError('already complete, no duplicate download')
        if not capacity.exists():
            reserve = root/'capacity-reservation.tmp'
            # This is a new exclusively-created file under the checked staging root.
            fd = os.open(reserve, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
            try:
                os.posix_fallocate(fd, 0, requested)
                os.fsync(fd)
                actual = os.fstat(fd).st_blocks*512
                if actual < requested:
                    raise ValueError('reservation was sparse')
                save(capacity, dict(utc=timestamp(), allocated_bytes=actual,
                     requested_bytes=requested, image_only=image_only, only_transient_capacity=True))
            finally:
                own = os.fstat(fd)
                now = reserve.lstat()
                if (own.st_dev, own.st_ino) != (now.st_dev, now.st_ino):
                    raise ValueError('reservation identity changed; leave untouched')
                os.close(fd)
                reserve.unlink()
        records = []
        clean_env = dict(os.environ)
        # Public files need no account keys; curl does not read .env or netrc here.
        for entry in entries:
            path = root/entry['path']
            path.parent.mkdir(exist_ok=True)
            part = path.with_name(path.name+'.partial')
            expected = entry['expected']
            if entry['path']=='vllm.sif' and (root/'image-complete.json').exists():
                previous = json.loads((root/'image-complete.json').read_text())
                if len(previous['files'])!=1 or previous['files'][0]['bytes']!=entry['size'] or previous['files'][0]['path']!='vllm.sif':
                    raise ValueError('prior image receipt differs')
                expected = previous['files'][0]['digest']
            if not path.exists():
                if part.exists() and part.stat().st_size > entry['size']:
                    raise ValueError('oversized partial; do not overwrite')
                print(json.dumps(dict(utc=timestamp(), event='download_start', file=entry['path'], bytes=entry['size'])), flush=True)
                if not part.exists() or part.stat().st_size < entry['size']:
                    result = subprocess.run(['curl', '--fail', '--location', '--silent', '--show-error', '--proto', '=https',
                        '--connect-timeout', '20', '--max-time', '3600', '--retry', '3', '--retry-delay', '5', '--retry-max-time', '120',
                        '--continue-at', '-', '--max-filesize', str(transfer_limit(entry['size'])), '--output', str(part), entry['url']],
                        env=clean_env, capture_output=True)
                    if result.returncode:
                        print(json.dumps(dict(event='download_failed', file=entry['path'], curl_rc=result.returncode)), flush=True)
                        raise SystemExit(1)
                if part.stat().st_size != entry['size']:
                    raise ValueError('download size mismatch')
                actual = digest(part, 'sha1', True) if entry['digest_kind']=='git_blob_sha1' else digest(part)
                if expected and actual != expected:
                    raise ValueError('public object hash mismatch')
                if path.exists():
                    raise ValueError('unexpected destination exists')
                part.rename(path)
            actual = digest(path, 'sha1', True) if entry['digest_kind']=='git_blob_sha1' else digest(path)
            if path.stat().st_size != entry['size'] or (expected and actual != expected):
                raise ValueError('completed artifact drift')
            records.append(dict(path=entry['path'], bytes=entry['size'], digest=actual, digest_kind=entry['digest_kind'],
                                publisher_digest_available=entry['expected'] is not None))
            print(json.dumps(dict(utc=timestamp(), event='verified', **records[-1])), flush=True)
        save(receipt, dict(utc=timestamp(), model=MODEL, revision=REV, files=records,
             total_bytes=sum(x['bytes'] for x in records), plan_sha256=digest(root/'plan.json'),
             no_gpu_or_inference=True, image_only=image_only, model_ready=not image_only, image_publisher_hash_unavailable=True))
        print(json.dumps(dict(event='IMAGE_COMPLETE' if image_only else 'COMPLETE', root=str(root), files=len(records))), flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('plan', 'download', 'image'))
    parser.add_argument('root', type=Path, nargs='?')
    args = parser.parse_args()
    os.umask(0o077)
    if args.mode == 'plan':
        plan()
    else:
        if args.root is None:
            parser.error('download requires staging root')
        download(args.root, image_only=args.mode=='image')
