"""Metadata-only positive control: same viewer/parser on known and new folders."""
import contextlib,datetime,hashlib,io,json,os,signal,tempfile
from pathlib import Path
BASE=Path('/research/d7/spc/yzyang4')
INVENTORY=BASE/'comparison-discovery-20260919-pv25nsna/inventory.private.json'
EXPECTED='130937f91475e66a065a92c428888578150e0ecc0cbc854ab03b0b177552c9dd'

def main():
    import gdown,requests
    os.umask(0o077);signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('deadline')));signal.alarm(180)
    raw=INVENTORY.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=EXPECTED:raise ValueError('inventory drift')
    inventory=json.loads(raw);root=Path(tempfile.mkdtemp(prefix='comparison-listing-control-20260919-',dir=BASE))
    original=requests.sessions.Session.request;calls=0
    def bounded(self,method,url,**kwargs):
        nonlocal calls
        calls+=1
        if calls>16 or method.upper()!='GET':raise ValueError('scope')
        kwargs['timeout']=(10,25);response=original(self,method,url,**kwargs)
        if len(response.content)>8*1024**2:raise ValueError('response cap')
        return response
    requests.sessions.Session.request=bounded;rows=[]
    for name in ('comparison/0912','comparison/0918'):
        folder,=[f for f in inventory['folders'] if f['relative']==name]
        snapshots=[]
        for _ in range(2):
            with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                entries=gdown.download_folder(id=folder['id'],output=str(root/'not-downloaded'),quiet=True,proxy='http://137.189.90.241:8000/',use_cookies=False,remaining_ok=False,skip_download=True)
            if entries is None:raise ValueError('unresolved listing')
            snapshots.append(sorted((e.id,str(e.path)) for e in entries))
        if snapshots[0]!=snapshots[1]:raise ValueError('unstable metadata')
        private=root/(name.split('/')[-1]+'.private.json');private.write_text(json.dumps(dict(folder_id=folder['id'],entries=snapshots[0])))
        rows.append(dict(relative=name,visible_files=len(snapshots[0]),listing_sha256=hashlib.sha256(private.read_bytes()).hexdigest()))
    if rows[0]['visible_files']!=5:raise ValueError('known folder positive control changed')
    result=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),root=str(root),status='PASS_KNOWN_FOLDER_POSITIVE_CONTROL',rows=rows,requests=calls,downloads=0,caveat='No visibility claim about unshared files.')
    (root/'receipt.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps(dict(status='LISTING_CONTROL_UNRESOLVED',error_type=type(exc).__name__,downloads=0)));raise SystemExit(2)
