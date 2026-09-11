"""Bounded public Drive folder metadata refresh; no archive bytes or admission."""
from datetime import datetime,timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import tempfile

BASE=Path('/research/d7/spc/yzyang4')
PARENT=BASE/'senior-drive-metadata-root-20260905/private_inventory.json'
PARENT_SHA='b6b4d0bcf1530840122dda9343b7ed54adfb30b2ac28d52ebcb3703b236b3099'
FOLDER_SHA='ad0042b99e7adbaff1c4adf542ba60838887b9d66ff7a96555c736168132d143'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')


def main():
    import requests
    raw=PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA or SECRET.search(raw):raise ValueError('parent metadata unsafe')
    previous=json.loads(raw);module=importlib.import_module('gdown.download_folder')
    if hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()!=FOLDER_SHA:raise ValueError('parser changed')
    session=requests.Session();session.trust_env=False
    session.proxies={'http':'http://137.189.90.241:8000/','https':'http://137.189.90.241:8000/'}
    requests_made=0
    def listing(folder_id):
        nonlocal requests_made
        if not re.fullmatch('[A-Za-z0-9_-]{10,80}',folder_id) or requests_made>=5:raise ValueError('folder/request scope')
        url='https://drive.google.com/drive/folders/'+folder_id;requests_made+=1
        with session.get(url,params={'hl':'en'},stream=True,allow_redirects=False,timeout=(10,30)) as response:
            if response.status_code!=200:raise ValueError('metadata response unavailable')
            data=bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data)>4*1024**2:raise ValueError('metadata byte cap')
        _,items=module._parse_google_drive_file(url,data.decode('utf-8'))
        if SECRET.search(json.dumps(items).encode()):raise ValueError('credential-shaped metadata')
        if len({x[0] for x in items})!=len(items):raise ValueError('duplicate listing identity')
        return items
    items=listing(previous['root_id'])
    dates=[x for x in items if x[2]=='application/vnd.google-apps.folder' and re.fullmatch('09[0-3][0-9]',x[1])]
    recent=sorted((x for x in dates if x[1]>='0910'),key=lambda x:x[1])
    nested=[]
    for fid,name,_ in recent[:4]:nested.append(dict(relative=name,folder_id=fid,entries=listing(fid)))
    output=Path(tempfile.mkdtemp(prefix='senior-root-metadata-20260912-',dir=BASE));os.chmod(output,0o700)
    private=dict(utc=datetime.now(timezone.utc).isoformat(),root_id=previous['root_id'],children=items,folders=nested)
    encoded=(json.dumps(private,sort_keys=True,indent=2)+'\n').encode()
    with (output/'inventory.private.json').open('xb') as stream:stream.write(encoded)
    os.chmod(output/'inventory.private.json',0o600)
    summary=dict(utc=private['utc'],output=str(output),root_entries=len(items),
        september_directories=sorted(x[1] for x in dates),newer_than_known_0909=[x[1] for x in recent],
        inspected_recent=[dict(relative=x['relative'],entries=len(x['entries']),
            child_folders=sum(i[2]=='application/vnd.google-apps.folder' for i in x['entries'])) for x in nested],
        requests=requests_made,inventory_sha256=hashlib.sha256(encoded).hexdigest(),
        archives_downloaded=0,archive_contents_opened=False,production_or_latest_changed=False,
        caveat='Folder names are not verified production dates; no corpus or run admission.')
    with (output/'summary.json').open('x') as stream:json.dump(summary,stream,indent=2)
    print(json.dumps(summary))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps(dict(status='METADATA_CHECK_FAILED_CLOSED',error_type=type(exc).__name__)))
        raise SystemExit(2)
