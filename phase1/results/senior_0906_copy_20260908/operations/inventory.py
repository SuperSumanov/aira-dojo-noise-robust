"""Two folder GETs; private names stay remote, no archive or sidecar reads."""
import datetime as dt
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import requests
import signal
signal.alarm(90)

os.umask(0o077)
source=Path(importlib.util.find_spec('gdown').origin).parent/'download_folder.py'
assert hashlib.sha256(source.read_bytes()).hexdigest()=='ad0042b99e7adbaff1c4adf542ba60838887b9d66ff7a96555c736168132d143'
parse=importlib.import_module('gdown.download_folder')._parse_google_drive_file
out=Path('/research/d7/spc/yzyang4/senior-0906-metadata-20260908')
out.mkdir(mode=0o700)
session=requests.Session();session.proxies={'http':'http://137.189.90.241:8000/','https':'http://137.189.90.241:8000/'}
def listing(fid):
    url='https://drive.google.com/drive/folders/'+fid
    r=session.get(url,params={'hl':'en'},timeout=(10,30),allow_redirects=False,verify=True)
    assert r.status_code==200
    _,children=parse(url,r.text)
    assert len(children)<50 and len({x[0] for x in children})==len(children)
    return children
root=listing('1yKoLdcEpouFsG8RpsWH0XPFPEVWi9BNz')
target=[x for x in root if x[1]=='0906' and x[2]=='application/vnd.google-apps.folder']
assert len(target)==1
items=listing(target[0][0])
assert len({x[1] for x in items})==len(items)
for fid,name,kind in items:
    assert re.fullmatch('[A-Za-z0-9_-]{10,80}',fid)
    assert PurePosixPath(name).name==name and '\\' not in name and '\n' not in name and '\r' not in name
archives=[x for x in items if x[1].endswith('.tar.gz') and x[2]!='application/vnd.google-apps.folder']
local=Path('/research/d7/spc/yzyang4/external/senior_data/mle/0906')
assert not local.exists()
private={'folder':'0906','folder_id':target[0][0],'items':items,'archives':archives}
raw=(json.dumps(private,sort_keys=True)+'\n').encode()
assert not re.search(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \\t]+[A-Za-z0-9._-]{20,})',raw)
(out/'private_inventory.json').write_bytes(raw)
safe={'status':'NEW_0906_FOLDER_METADATA_FIXED_NOT_DOWNLOADED','checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
      'root_entries':len(root),'entries':len(items),'archives':len(archives),
      'subfolders':sum(x[2]=='application/vnd.google-apps.folder' for x in items),
      'nonarchive_files':len(items)-len(archives)-sum(x[2]=='application/vnd.google-apps.folder' for x in items),
      'private_inventory_sha256':hashlib.sha256(raw).hexdigest(),'payload_reads':0,'payload_downloads':0,
      'source_qualification':False}
(out/'safe_summary.json').write_text(json.dumps(safe,sort_keys=True,indent=2)+'\n')
print(json.dumps(safe,sort_keys=True))
