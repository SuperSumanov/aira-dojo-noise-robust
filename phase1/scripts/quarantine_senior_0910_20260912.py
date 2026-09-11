"""Bounded quarantine of six discovered 0910 archives. No decompression/intake."""
from datetime import datetime,timezone
import hashlib
import importlib
import json
import os
from pathlib import Path,PurePosixPath
import re
import signal
import tempfile
import time
from urllib.parse import urlparse

BASE=Path('/research/d7/spc/yzyang4')
INVENTORY=BASE/'senior-root-metadata-20260912-nr5ioaoh/inventory.private.json'
INVENTORY_SHA='379259f9dadecb27adb49e744bd83e6d4f21c389698208a3ef00cb2e05a98254'
DOWNLOAD_SHA='25a72cbed857190c010762291c7484f1e9fb7d9df17d7bf74bb26a14cd48ed56'
FOLDER_SHA='ad0042b99e7adbaff1c4adf542ba60838887b9d66ff7a96555c736168132d143'
OUT=BASE/'senior-quarantine-0910-20260912'
FILE_CAP=128*1024**2
TOTAL_CAP=6*FILE_CAP
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):digest.update(block)
    return digest.hexdigest()


def expired(*_):raise TimeoutError('bounded quarantine deadline')


def main():
    import gdown,requests
    os.umask(0o077);signal.signal(signal.SIGALRM,expired);signal.alarm(900)
    raw=INVENTORY.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=INVENTORY_SHA or SECRET.search(raw):raise ValueError('inventory drift')
    groups=[x for x in json.loads(raw)['folders'] if x['relative']=='0910']
    if len(groups)!=1:raise ValueError('folder binding')
    group=groups[0];rows=group['entries']
    if len(rows)!=6 or len({x[0] for x in rows})!=6 or len({x[1] for x in rows})!=6:raise ValueError('scope count')
    for fid,name,kind in rows:
        if (not re.fullmatch('[A-Za-z0-9_-]{10,80}',fid) or PurePosixPath(name).name!=name or '\\' in name
            or not name.endswith('.tar.gz') or any(ord(c)<32 for c in name) or kind!='application/x-gzip'):
            raise ValueError('unsafe archive identity')
    folder_module=importlib.import_module('gdown.download_folder')
    download_module=importlib.import_module('gdown.download')
    if sha(Path(folder_module.__file__))!=FOLDER_SHA or sha(Path(download_module.__file__))!=DOWNLOAD_SHA:
        raise ValueError('downloader drift')
    if OUT.exists() or OUT.resolve().parent!=BASE.resolve():raise ValueError('quarantine already exists')
    OUT.mkdir(mode=0o700)
    reserve=OUT/'own-space-reservation'
    with reserve.open('xb') as stream:
        os.posix_fallocate(stream.fileno(),0,TOTAL_CAP);os.fsync(stream.fileno());st=os.fstat(stream.fileno())
    if reserve.resolve()!=reserve or reserve.stat().st_ino!=st.st_ino or st.st_blocks*512<TOTAL_CAP:raise ValueError('quota reserve failed')
    reserve.unlink()  # Only this just-created, inode-checked file.
    requests_count=0;send=requests.Session.send
    def bounded_send(session,request,**kwargs):
        nonlocal requests_count
        p=urlparse(request.url);host=p.hostname or ''
        if (request.method!='GET' or p.scheme!='https' or p.username or p.password or
            not(host.endswith('.google.com') or host.endswith('.googleusercontent.com')) or
            requests_count>=40 or kwargs.get('verify',True) is not True or 'Authorization' in request.headers):
            raise ValueError('unexpected network request')
        requests_count+=1;kwargs['timeout']=(10,30)
        return send(session,request,**kwargs)
    requests.Session.send=bounded_send
    budget={'bytes':0}
    class Writer:
        def __init__(self,stream):self.stream=stream;self.n=0;self.hash=hashlib.sha256()
        def write(self,chunk):
            if self.n+len(chunk)>FILE_CAP or budget['bytes']+len(chunk)>TOTAL_CAP:raise ValueError('download byte cap')
            n=self.stream.write(chunk)
            if n!=len(chunk):raise ValueError('short write')
            self.n+=n;budget['bytes']+=n;self.hash.update(chunk);return n
    def relist():
        session=requests.Session();session.trust_env=False
        session.proxies={'http':'http://137.189.90.241:8000/','https':'http://137.189.90.241:8000/'}
        url='https://drive.google.com/drive/folders/'+group['folder_id']
        response=session.get(url,params={'hl':'en'},allow_redirects=False,timeout=(10,30))
        if response.status_code!=200 or len(response.content)>4*1024**2:raise ValueError('folder unavailable')
        _,now=folder_module._parse_google_drive_file(url,response.text)
        if sorted(now)!=sorted(tuple(r) for r in rows):raise ValueError('folder changed')
    relist();started=time.monotonic();records=[]
    folder=OUT/'archives/0910';folder.mkdir(parents=True,mode=0o700)
    for fid,name,_ in rows:
        target=folder/name
        with target.open('xb') as stream:
            writer=Writer(stream)
            value=gdown.download(id=fid,output=writer,quiet=True,use_cookies=False,verify=True,resume=False,proxy='http://137.189.90.241:8000/')
            if value is not writer:raise ValueError('download result')
            stream.flush();os.fsync(stream.fileno())
        if sha(target)!=writer.hash.hexdigest() or target.stat().st_size!=writer.n:raise ValueError('download hash')
        with target.open('rb') as stream:
            if stream.read(3)!=b'\x1f\x8b\x08':raise ValueError('not gzip')
        target.chmod(0o400)
        records.append(dict(relative='0910/'+name,drive_id=fid,bytes=writer.n,sha256=writer.hash.hexdigest(),mtime_ns=target.stat().st_mtime_ns))
        print(json.dumps(dict(event='ARCHIVE_QUARANTINED',ordinal=len(records),bytes=writer.n,contents_opened=False)),flush=True)
    relist()
    if len({x['sha256'] for x in records})!=6:raise ValueError('duplicate archive payload')
    with (OUT/'private_manifest.json').open('x') as stream:json.dump(dict(records=records,inventory_sha256=INVENTORY_SHA),stream,sort_keys=True,indent=2)
    summary=dict(status='QUARANTINED_NOT_INTAKE_OR_TRAINING',utc=datetime.now(timezone.utc).isoformat(),
        group='0910',archives=6,bytes=budget['bytes'],requests=requests_count,elapsed_seconds=time.monotonic()-started,
        manifest_sha256=sha(OUT/'private_manifest.json'),script_sha256=sha(Path(__file__)),
        archive_contents_opened=False,production_source_changed=False,protected_values_read=False,
        gpu_jobs=0,model_calls=0,root_listing_may_be_paginated=True)
    with (OUT/'summary.json').open('x') as stream:json.dump(summary,stream,sort_keys=True,indent=2)
    print(json.dumps(summary),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps(dict(status='QUARANTINE_FAILED_CLOSED',error_type=type(exc).__name__)),flush=True)
        raise SystemExit(2)
