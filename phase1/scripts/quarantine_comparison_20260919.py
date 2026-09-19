"""Download the five explicitly shared comparison archives; never extract."""
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import signal
import tempfile
from urllib.parse import urlparse

BASE=Path('/research/d7/spc/yzyang4')
INVENTORY=BASE/'comparison-discovery-20260919-pv25nsna/inventory.private.json'
INVENTORY_SHA='130937f91475e66a065a92c428888578150e0ecc0cbc854ab03b0b177552c9dd'
DOWNLOAD_SHA='25a72cbed857190c010762291c7484f1e9fb7d9df17d7bf74bb26a14cd48ed56'
FILE_CAP=512*1024**2
TOTAL_CAP=1024**3

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024**2),b''):h.update(chunk)
    return h.hexdigest()

def main():
    import gdown, requests
    os.umask(0o077)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError()))
    signal.alarm(1200)
    if sha(INVENTORY)!=INVENTORY_SHA:raise ValueError('inventory drift')
    group=[x for x in json.loads(INVENTORY.read_bytes())['folders'] if x['relative']=='comparison/0912']
    if len(group)!=1 or group[0].get('listing_unresolved'):raise ValueError('scope')
    rows=group[0]['entries']
    if len(rows)!=5 or len({x[0] for x in rows})!=5 or len({x[1] for x in rows})!=5:raise ValueError('five unique files required')
    module=importlib.import_module('gdown.download')
    if sha(Path(module.__file__))!=DOWNLOAD_SHA:raise ValueError('downloader changed')
    out=Path(tempfile.mkdtemp(prefix='comparison-quarantine-20260919-',dir=BASE))
    (out/'archives').mkdir()
    print(json.dumps({'output':str(out),'archives':5,'byte_cap':TOTAL_CAP}),flush=True)
    reserve=out/'own-reservation'
    with reserve.open('xb') as f:
        os.posix_fallocate(f.fileno(),0,TOTAL_CAP);st=os.fstat(f.fileno())
    if reserve.resolve()!=reserve or reserve.stat().st_ino!=st.st_ino:raise ValueError('reservation identity')
    reserve.unlink()  # Only the just-created reservation, never existing data.
    count=0;total=0;records=[];original=requests.Session.send
    def send(session,request,**kwargs):
        nonlocal count
        p=urlparse(request.url);host=p.hostname or ''
        if request.method!='GET' or p.scheme!='https' or p.username or p.password or not (
            host.endswith('.google.com') or host.endswith('.googleusercontent.com')):
            raise ValueError('network destination')
        count+=1
        if count>50 or kwargs.get('verify',True) is not True or 'Authorization' in request.headers:raise ValueError('network gate')
        kwargs['timeout']=(10,30)
        return original(session,request,**kwargs)
    requests.Session.send=send
    class Writer:
        def __init__(self,f):self.f=f;self.n=0;self.h=hashlib.sha256()
        def write(self,data):
            nonlocal total
            if self.n+len(data)>FILE_CAP or total+len(data)>TOTAL_CAP:raise ValueError('byte cap')
            n=self.f.write(data)
            if n!=len(data):raise ValueError('short write')
            self.n+=n;total+=n;self.h.update(data);return n
    for fid,name,kind in rows:
        if PurePosixPath(name).name!=name or '\\' in name or not name.endswith('.tar.gz') or kind!='file':raise ValueError('archive name')
        p=out/'archives'/name
        with p.open('xb') as f:
            writer=Writer(f)
            result=gdown.download(id=fid,output=writer,quiet=True,use_cookies=False,verify=True,resume=False,proxy='http://137.189.90.241:8000/')
            if result is not writer:raise ValueError('download result')
            f.flush();os.fsync(f.fileno())
        with p.open('rb') as f:
            if f.read(3)!=b'\x1f\x8b\x08':raise ValueError('not gzip')
        if sha(p)!=writer.h.hexdigest():raise ValueError('download hash')
        p.chmod(0o400)
        record={'name':name,'drive_id':fid,'sha256':writer.h.hexdigest(),'bytes':writer.n}
        records.append(record)
        # Incremental receipt survives interrupted transfers, without claiming completion.
        with (out/(name+'.receipt.json')).open('x') as f:json.dump(record,f,sort_keys=True)
        print(json.dumps({'event':'QUARANTINED','task_archive':name,'bytes':writer.n}),flush=True)
    if len({r['sha256'] for r in records})!=5:raise ValueError('duplicate archives')
    manifest={'utc':datetime.now(timezone.utc).isoformat(),'inventory_sha256':INVENTORY_SHA,'records':records}
    with (out/'manifest.private.json').open('x') as f:json.dump(manifest,f,sort_keys=True,indent=2)
    public={'status':'QUARANTINED_NOT_ADMITTED','utc':manifest['utc'],'root':str(out),'archives':5,
        'bytes':total,'requests':count,'manifest_sha256':sha(out/'manifest.private.json'),
        'archive_contents_opened':False,'gpu_jobs':0,'api_calls':0,'production_changed':False}
    with (out/'summary.json').open('x') as f:json.dump(public,f,indent=2)
    print(json.dumps(public),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'status':'QUARANTINE_FAILED','error_type':type(exc).__name__}),flush=True)
        raise SystemExit(2)
