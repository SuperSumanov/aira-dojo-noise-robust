"""Alternate metadata-only reader for the unresolved shared comparison folder."""
import contextlib,datetime,hashlib,io,json,os,signal,tempfile
from pathlib import Path

BASE=Path('/research/d7/spc/yzyang4')
INVENTORY=BASE/'comparison-discovery-20260919-pv25nsna/inventory.private.json'
EXPECTED='130937f91475e66a065a92c428888578150e0ecc0cbc854ab03b0b177552c9dd'


def main():
    import gdown
    import requests
    os.umask(0o077)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('deadline')))
    signal.alarm(180)
    raw=INVENTORY.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=EXPECTED:raise ValueError('inventory drift')
    folders=[f for f in json.loads(raw)['folders'] if f['relative']=='comparison/0918']
    if len(folders)!=1:raise ValueError('folder identity')
    root=Path(tempfile.mkdtemp(prefix='comparison-0918-metadata-20260919-',dir=BASE))
    original=requests.sessions.Session.request
    calls=0
    def bounded(self,method,url,**kwargs):
        nonlocal calls
        calls+=1
        if calls>16 or method.upper()!='GET':raise ValueError('metadata request cap')
        kwargs['timeout']=(10,25)
        response=original(self,method,url,**kwargs)
        if len(response.content)>8*1024**2:raise ValueError('metadata response cap')
        return response
    requests.sessions.Session.request=bounded
    snapshots=[]
    for _ in range(2):
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            entries=gdown.download_folder(id=folders[0]['id'],output=str(root/'not-downloaded'),quiet=True,
                proxy='http://137.189.90.241:8000/',use_cookies=False,remaining_ok=False,skip_download=True)
        if entries is None:raise ValueError('unresolved listing')
        snapshots.append(sorted((e.id,str(e.path)) for e in entries))
    if snapshots[0]!=snapshots[1]:raise ValueError('unstable metadata')
    private=dict(folder_id=folders[0]['id'],entries=snapshots[0])
    (root/'listing.private.json').write_text(json.dumps(private))
    receipt=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),root=str(root),
        status='STABLE_ALTERNATE_METADATA_LISTING',visible_files=len(snapshots[0]),requests=calls,
        downloads=0,listing_sha256=hashlib.sha256((root/'listing.private.json').read_bytes()).hexdigest(),
        caveat='An empty public listing does not rule out files not shared with this viewer.')
    (root/'receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps(dict(status='LISTING_UNRESOLVED',error_type=type(exc).__name__,downloads=0)),flush=True)
        raise SystemExit(2)
