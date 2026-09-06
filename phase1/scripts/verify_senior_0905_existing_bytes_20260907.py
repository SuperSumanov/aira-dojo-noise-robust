"""Compare existing opaque archives with fixed Drive objects; never unpack.

Remote-only streaming hash, no new archive copy, no overwrite/mtime changes.
This proves current byte equality, not original download time or run eligibility.
"""
import datetime as dt
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path,PurePosixPath
import re
import time
from urllib.parse import urlparse

BASE=Path('/research/d7/spc/yzyang4')
ROOT=BASE/'external/senior_data/mle/0905'
OUT=BASE/'senior-0905-byte-compare-20260907'
METADATA=BASE/'senior-metadata-session-20260907-2217/inventory.private.json'
METADATA_SHA='4da094a253a9e635c21d709e88ff7b38310486cae6971360923e1a2e65c4c992'
FILE_CAP=128*1024**2
TOTAL_CAP=1024**3
SECONDS_CAP=900
SECRET=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')


def require(ok,reason):
    if not ok:raise RuntimeError(reason)


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024**2),b''):h.update(b)
    return h.hexdigest()


def fingerprint(path):
    require(path.resolve()==path and path.is_file() and not any(p.is_symlink() for p in (path,*path.parents)),'unsafe_existing_archive')
    s=path.stat()
    require(s.st_uid==os.getuid() and s.st_nlink==1 and 3<s.st_size<=FILE_CAP,'existing_file_identity')
    return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode)


def allowed_request(method,url):
    host=urlparse(url).hostname or ''
    return method=='GET' and urlparse(url).scheme=='https' and (
        host.endswith('.google.com') or host.endswith('.googleusercontent.com'))


class HashOnlyWriter:
    def __init__(self,budget,deadline):
        self.budget=budget;self.deadline=deadline;self.n=0;self.h=hashlib.sha256();self.prefix=b''
    def write(self,chunk):
        require(time.monotonic()<self.deadline and self.n+len(chunk)<=FILE_CAP
                and self.budget[0]+len(chunk)<=TOTAL_CAP,'stream_budget_exceeded')
        self.prefix=(self.prefix+chunk[:3])[:3]
        self.n+=len(chunk);self.budget[0]+=len(chunk);self.h.update(chunk)
        return len(chunk)


def save(name,value):
    raw=(json.dumps(value,sort_keys=True,allow_nan=False,indent=2)+'\n').encode()
    require(not SECRET.search(raw),'receipt_credential_shape')
    with (OUT/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())


def main():
    os.umask(0o077);require(not OUT.exists(),'existing_output')
    raw=METADATA.read_bytes();require(hashlib.sha256(raw).hexdigest()==METADATA_SHA and not SECRET.search(raw),'metadata_drift')
    inv=json.loads(raw);folders=[r for r in inv['recent'] if r['date']=='0905']
    require(len(folders)==1 and not folders[0]['missing'],'existing_scope')
    children=folders[0]['entries'];require(len(children)==12,'scope_count')
    require(len({r[0] for r in children})==len({r[1] for r in children})==12,'duplicate_scope')
    for fid,name,kind in children:
        require(re.fullmatch('[A-Za-z0-9_-]{10,80}',fid) is not None and kind!='application/vnd.google-apps.folder','drive_identity')
        require(PurePosixPath(name).name==name and '\\' not in name and '\n' not in name and '\r' not in name and name.endswith('.tar.gz'),'unsafe_archive_name')
    require({p.name for p in ROOT.iterdir()}=={r[1] for r in children},'local_inventory_changed')
    before={name:fingerprint(ROOT/name) for _,name,_ in children}
    local={name:sha(ROOT/name) for _,name,_ in children}
    require(len(set(local.values()))==12,'duplicate_archive_content')
    source=Path(importlib.util.find_spec('gdown').origin).parent
    require(sha(source/'download.py')=='25a72cbed857190c010762291c7484f1e9fb7d9df17d7bf74bb26a14cd48ed56'
        and sha(source/'download_folder.py')=='ad0042b99e7adbaff1c4adf542ba60838887b9d66ff7a96555c736168132d143','gdown_source_drift')
    OUT.mkdir(mode=0o700);started=time.monotonic();deadline=started+SECONDS_CAP;budget=[0];count=0;records=[]
    save('INTENT.json',{'metadata_sha256':METADATA_SHA,'script_sha256':sha(Path(__file__)),'archives':12,
        'byte_cap':TOTAL_CAP,'seconds_cap':SECONDS_CAP,'output_archive_copies':0,'automatic_retry':False})
    import requests,gdown
    original=requests.Session.send
    def send(session,request,**kwargs):
        nonlocal count
        require(allowed_request(request.method,request.url) and count<100 and time.monotonic()<deadline,'network_scope')
        require(kwargs.get('verify',True) is True,'tls_required');kwargs['timeout']=(10,30);count+=1
        return original(session,request,**kwargs)
    requests.Session.send=send
    try:
        for index,(fid,name,_) in enumerate(children):
            writer=HashOnlyWriter(budget,deadline)
            result=gdown.download(id=fid,output=writer,quiet=True,use_cookies=False,verify=True,resume=False,
                proxy='http://137.189.90.241:8000/')
            require(result is writer and writer.prefix==b'\x1f\x8b\x08','opaque_stream_not_gzip')
            require(writer.n==before[name][2] and writer.h.hexdigest()==local[name],'drive_local_bytes_differ')
            require(fingerprint(ROOT/name)==before[name] and sha(ROOT/name)==local[name],'local_file_changed')
            records.append({'name':name,'drive_id':fid,'sha256':local[name],'bytes':writer.n,'fingerprint':before[name]})
            print(json.dumps({'status':'OPAQUE_BYTES_MATCH','ordinal':index+1,'bytes':writer.n}),flush=True)
        folderids=[r[0] for r in inv['root'] if r[1]=='0905'];require(len(folderids)==1,'folder_identity')
        session=requests.Session();session.proxies={'http':'http://137.189.90.241:8000/','https':'http://137.189.90.241:8000/'}
        url='https://drive.google.com/drive/folders/'+folderids[0]
        response=session.get(url,params={'hl':'en'},timeout=(10,30),allow_redirects=False)
        require(response.status_code==200,'relist_status')
        _,after=importlib.import_module('gdown.download_folder')._parse_google_drive_file(url,response.text)
        require(sorted(after)==sorted(tuple(r) for r in children),'remote_inventory_drift')
    finally:requests.Session.send=original
    require({p.name for p in ROOT.iterdir()}==set(local) and all(fingerprint(ROOT/n)==before[n] and sha(ROOT/n)==h for n,h in local.items()),'end_local_drift')
    save('private_manifest.json',{'records':records,'metadata_sha256':METADATA_SHA})
    now=time.time();maturity=max(row[3]/1e9 for row in before.values())+21600
    save('safe_receipt.json',{'classification':'CURRENT_DRIVE_LOCAL_OPAQUE_BYTES_EQUAL_NOT_INTAKE_OR_TRAINING_ADMISSION',
        'utc':dt.datetime.now(dt.timezone.utc).isoformat(),'archives':len(records),'bytes':budget[0],'http_requests':count,
        'elapsed_seconds':time.monotonic()-started,'private_manifest_sha256':sha(OUT/'private_manifest.json'),
        'metadata_sha256':METADATA_SHA,'existing_readonly_files':sum(not r[5]&0o222 for r in before.values()),
        'existing_six_hour_age_at_utc':dt.datetime.fromtimestamp(maturity,dt.timezone.utc).isoformat(),
        'existing_mtime_age_satisfied':now>=maturity,'original_download_time_attested':False,
        'source_files_modified':False,'tar_members_opened':0,'new_archive_copies':0,'training_admitted':False})
    print((OUT/'safe_receipt.json').read_text(),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        result={'status':'FAILED_CLOSED','reason':str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__,'automatic_retry':False}
        if OUT.is_dir() and not (OUT/'FAILED.json').exists():save('FAILED.json',result)
        print(json.dumps(result),flush=True);raise SystemExit(1)
