"""Inspect only the newly observed 0912 child; no old-index reconciliation/intake."""
from datetime import datetime,timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import tempfile
import inspect_senior_complete_root_20260912 as old


def main():
    import requests
    raw=old.PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=old.PARENT_SHA or old.SECRET.search(raw):raise ValueError('old root binding')
    root_id=json.loads(raw)['root_id'];parser=importlib.import_module('gdown.download_folder')
    if hashlib.sha256(Path(parser.__file__).read_bytes()).hexdigest()!=old.LEGACY_PARSER_SHA:raise ValueError('parser drift')
    session=requests.Session();session.trust_env=False
    session.proxies={'http':'http://137.189.90.241:8000/','https':'http://137.189.90.241:8000/'}
    count=0
    def get(url,params):
        nonlocal count
        count+=1
        if count>4:raise ValueError('request cap')
        with session.get(url,params=params,stream=True,allow_redirects=False,timeout=(10,30)) as response:
            if response.status_code!=200:raise ValueError('listing status')
            body=bytearray()
            for piece in response.iter_content(65536):
                body.extend(piece)
                if len(body)>8*1024**2:raise ValueError('byte cap')
        return body.decode()
    a=old.embedded_items(get('https://drive.google.com/embeddedfolderview',{'id':root_id}))
    targets=[x for x in a if x[1]=='0912' and x[2]==old.FOLDER]
    if len(targets)!=1:raise ValueError('unique new date folder')
    fid=targets[0][0];url='https://drive.google.com/drive/folders/'+fid
    _,first=parser._parse_google_drive_file(url,get(url,{'hl':'en'}))
    _,second=parser._parse_google_drive_file(url,get(url,{'hl':'en'}))
    b=old.embedded_items(get('https://drive.google.com/embeddedfolderview',{'id':root_id}))
    if a!=b or sorted(first)!=sorted(second):raise ValueError('unstable metadata')
    if not 1<=len(first)<50 or len({x[0] for x in first})!=len(first) or len({x[1] for x in first})!=len(first):raise ValueError('ambiguous child scope')
    for fid,name,kind in first:
        if not re.fullmatch('[A-Za-z0-9_-]{10,80}',fid) or Path(name).name!=name or '/' in name or '\\' in name:
            raise ValueError('invalid child identity')
    private=dict(utc=datetime.now(timezone.utc).isoformat(),root_id=root_id,root_entries=a,
        folders=[dict(relative='0912',folder_id=targets[0][0],entries=first)])
    raw=(json.dumps(private,sort_keys=True,indent=2)+'\n').encode()
    if old.SECRET.search(raw):raise ValueError('credential-shaped metadata')
    os.umask(0o077);output=Path(tempfile.mkdtemp(prefix='senior-0912-metadata-20260914-',dir=old.BASE))
    with (output/'inventory.private.json').open('xb') as f:f.write(raw)
    public=dict(utc=private['utc'],root=str(output),root_entries=len(a),date='0912',child_entries=len(first),
        archive_entries=sum(kind=='application/x-gzip' and name.endswith('.tar.gz') for _,name,kind in first),
        child_directories=sum(kind==old.FOLDER for _,_,kind in first),stable_repeated_root_and_child=True,
        inventory_sha256=hashlib.sha256(raw).hexdigest(),requests=count,archives_downloaded=0,production_changed=False,
        old_legacy_name_disagreement_resolved=False,admission_allowed=False,
        caveat='An isolated new-child metadata observation, not reconciliation of the legacy root or validated production runs.')
    with (output/'summary.json').open('x') as f:json.dump(public,f,sort_keys=True,indent=2)
    print(json.dumps(public))

if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps(dict(status='METADATA_FAILED_CLOSED',error_type=type(e).__name__)))
        raise SystemExit(2)
