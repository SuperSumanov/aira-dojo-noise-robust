"""Download only the hash-bound 0903 missing archives. Never decompress them."""
import datetime as dt
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import time
from urllib.parse import urlparse

BASE = Path('/research/d7/spc/yzyang4')
ROOT = BASE/'external/senior_data/mle'
OUT = BASE/'senior-0903-sync-20260905'
MANIFEST = BASE/'senior-drive-metadata-dates-20260905/private_inventory.json'
MANIFEST_SHA = 'd9e28b413b64c9fff05af15015060e977fbc467365e7f7a10b8ae1e7f7f5ea08'
ROOT_MANIFEST = BASE/'senior-drive-metadata-root-20260905/private_inventory.json'
ROOT_MANIFEST_SHA = 'b6b4d0bcf1530840122dda9343b7ed54adfb30b2ac28d52ebcb3703b236b3099'
DOWNLOAD_SHA = '25a72cbed857190c010762291c7484f1e9fb7d9df17d7bf74bb26a14cd48ed56'
FOLDER_SHA = 'ad0042b99e7adbaff1c4adf542ba60838887b9d66ff7a96555c736168132d143'
FILE_CAP = 128 * 1024**2
TOTAL_CAP = 1024**3
SECONDS_CAP = 1800


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024**2),b''): h.update(block)
    return h.hexdigest()


def document(name,value):
    with (OUT/name).open('x',encoding='utf-8') as f:
        json.dump(value,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())


def bound_manifest():
    require(MANIFEST.resolve()==MANIFEST and sha(MANIFEST)==MANIFEST_SHA,'manifest_drift')
    rows=[x for x in json.loads(MANIFEST.read_bytes()) if x['name']=='0903']
    require(len(rows)==1,'manifest_folder')
    children=rows[0]['children']
    require(len(children)==9 and len(rows[0]['missing_archives'])==9,'archive_count')
    require(len({x[0] for x in children})==len({x[1] for x in children})==9,'duplicate_manifest')
    for fid,name,kind in children:
        require(re.fullmatch('[A-Za-z0-9_-]{10,80}',fid) is not None,'drive_id')
        require(PurePosixPath(name).name==name and '\\' not in name and name.endswith('.tar.gz')
                and '\n' not in name and '\r' not in name,'archive_basename')
        require(kind!='application/vnd.google-apps.folder','unexpected_subdirectory')
    require(ROOT_MANIFEST.resolve()==ROOT_MANIFEST and sha(ROOT_MANIFEST)==ROOT_MANIFEST_SHA,'root_manifest_drift')
    ids=[fid for fid,name,kind in json.loads(ROOT_MANIFEST.read_bytes())['children'] if name=='0903']
    require(len(ids)==1,'root_folder_id')
    return children,ids[0]


def main():
    import fcntl
    os.umask(0o077)
    require(ROOT.resolve(strict=True)==ROOT and not OUT.exists(),'unsafe_or_existing_output')
    children,folder_id=bound_manifest()
    require(not (ROOT/'0903').exists(),'destination_exists')
    require(sum(1 for _ in ROOT.glob('*/*.tar.gz'))==316,'initial_archive_count_changed')
    source=Path(importlib.util.find_spec('gdown').origin).parent
    require(sha(source/'download.py')==DOWNLOAD_SHA and sha(source/'download_folder.py')==FOLDER_SHA,'gdown_source_drift')
    OUT.mkdir(mode=0o700)
    staging=OUT/'0903';staging.mkdir(mode=0o700)
    require(OUT.stat().st_dev==ROOT.stat().st_dev,'cross_device_promotion')
    with (OUT/'writer.lock').open('xb') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        reservation=OUT/'own_space_reservation'
        with reservation.open('xb') as f:
            os.posix_fallocate(f.fileno(),0,TOTAL_CAP);os.fsync(f.fileno());s=os.fstat(f.fileno())
        require(s.st_size==TOTAL_CAP and s.st_blocks*512>=TOTAL_CAP,'reservation_short')
        require(reservation.resolve()==reservation and reservation.stat().st_ino==s.st_ino
                and reservation.stat().st_dev==s.st_dev and s.st_uid==os.getuid(),'reservation_identity')
        document('space_receipt.json',dict(bytes=s.st_size,allocated_bytes=s.st_blocks*512,inode=s.st_ino,
                                          device=s.st_dev,uid=s.st_uid,not_a_quota_query=True))
        reservation.unlink()  # Only this exact new diagnostic inode; no user files.
        started=time.monotonic();network_count=0;total=0;records=[];http=[]
        import requests,gdown
        send=requests.Session.send
        def guarded_send(session, request, **kwargs):
            nonlocal network_count
            hostname=urlparse(request.url).hostname or ''
            require(request.method=='GET' and (hostname.endswith('.google.com') or hostname.endswith('.googleusercontent.com')),
                    'unexpected_http_destination_or_method')
            require(network_count<100 and time.monotonic()-started<SECONDS_CAP,'network_budget')
            require(kwargs.get('verify',True) is True,'tls_verification_disabled')
            kwargs['timeout']=(10,30);network_count+=1
            response=send(session,request,**kwargs)
            http.append(dict(status=response.status_code,host=hostname,
                             content_length=response.headers.get('Content-Length'),
                             last_modified=response.headers.get('Last-Modified')))
            return response
        requests.Session.send=guarded_send
        class BoundedWriter:
            def __init__(self,f):self.f=f;self.n=0;self.h=hashlib.sha256()
            def write(self,chunk):
                nonlocal total
                require(time.monotonic()-started<SECONDS_CAP and self.n+len(chunk)<=FILE_CAP
                        and total+len(chunk)<=TOTAL_CAP,'download_byte_or_time_limit')
                written=self.f.write(chunk);require(written==len(chunk),'short_write')
                self.n+=written;total+=written;self.h.update(chunk)
                return written
        for index,(fid,name,kind) in enumerate(children):
            target=staging/name;before=time.time()
            with target.open('xb') as f:
                writer=BoundedWriter(f)
                result=gdown.download(id=fid,output=writer,quiet=True,use_cookies=False,verify=True,resume=False,
                                      proxy='http://137.189.90.241:8000/')
                require(result is writer,'download_result')
                f.flush();os.fsync(f.fileno())
            stat=target.stat()
            require(target.resolve()==target and 3<stat.st_size<=FILE_CAP and before<=stat.st_mtime<=time.time(),
                    'download_file_or_fresh_mtime')
            with target.open('rb') as f: require(f.read(3)==b'\x1f\x8b\x08','not_gzip')
            verify_sha=sha(target)
            require(verify_sha==writer.h.hexdigest() and stat.st_size==writer.n,'download_hash_mismatch')
            records.append(dict(name=name,drive_id=fid,sha256=verify_sha,bytes=stat.st_size,mtime_ns=stat.st_mtime_ns))
            target.chmod(0o400)
            print(json.dumps(dict(status='PRIVATE_ARCHIVE_DOWNLOADED',ordinal=index+1,bytes=stat.st_size,
                                  compressed_sha256=verify_sha,archive_contents_parsed=False)),flush=True)
        # Re-list the same folder, without recursively visiting siblings.
        session=requests.Session();session.proxies={'http':'http://137.189.90.241:8000/','https':'http://137.189.90.241:8000/'}
        url='https://drive.google.com/drive/folders/'+folder_id
        response=session.get(url,params={'hl':'en'},timeout=(10,30),allow_redirects=False)
        require(response.status_code==200,'relist_status')
        _,after=importlib.import_module('gdown.download_folder')._parse_google_drive_file(url,response.text)
        require(sorted(after)==sorted(tuple(x) for x in children),'relist_identity_changed')
        require(not (ROOT/'0903').exists(),'destination_appeared')
        require(sum(1 for _ in ROOT.glob('*/*.tar.gz'))==316,'old_source_count_changed')
        for r in records:
            target=staging/r['name']
            require(sha(target)==r['sha256'] and target.stat().st_mtime_ns==r['mtime_ns'],'staged_file_drift')
        document('private_manifest.json',dict(records=records,http_metadata=http,source_manifest_sha256=MANIFEST_SHA,
                                               script_sha256=sha(Path(__file__)),gdown_download_sha256=DOWNLOAD_SHA))
        os.rename(staging,ROOT/'0903')
        require(sum(1 for _ in ROOT.glob('*/*.tar.gz'))==325,'promoted_count')
        earliest=max(r['mtime_ns']/1e9 for r in records)+21600
        receipt=dict(status='NINE_ARCHIVES_DOWNLOADED_AND_PROMOTED_NOT_YET_INTAKE_ELIGIBLE',
                     checked_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),downloaded_archives=len(records),
                     bytes=total,source_archives_before=316,source_archives_after=325,
                     requests=network_count,elapsed_seconds=time.monotonic()-started,
                     all_files_six_hour_age_at_utc=dt.datetime.fromtimestamp(earliest,dt.timezone.utc).isoformat(),
                     private_manifest_sha256=sha(OUT/'private_manifest.json'),archive_contents_parsed=False,
                     mtime_backdated=False,cookie_files_used=False,model_or_competition_files_downloaded=0,
                     old_archives_overwritten=0,gpu_jobs=0,paid_api_calls=0,model_fits=0,
                     own_one_gib_reservation_removed=True,stability_protocol_unchanged=True)
        document('safe_receipt.json',receipt)
        print(json.dumps(receipt,sort_keys=True),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        reason=str(exc) if isinstance(exc,RuntimeError) and re.fullmatch('[a-z_]+',str(exc)) else 'detail_withheld'
        receipt=dict(status='SYNC_FAILED_CLOSED',error=type(exc).__name__,reason=reason,automatic_retry=False)
        if OUT.is_dir() and not (OUT/'FAILED.json').exists():document('FAILED.json',receipt)
        print(json.dumps(receipt),flush=True);sys.exit(1)
