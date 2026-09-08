"""One bounded metadata-only listing; never downloads or opens an archive."""
import datetime,hashlib,importlib,importlib.util,json,os,re,sys,time
from pathlib import Path,PurePosixPath
B=Path('/research/d7/spc/yzyang4');OUT=B/'senior-metadata-session-20260908-0436'
os.umask(0o077);assert not OUT.exists()
src=Path(importlib.util.find_spec('gdown').origin).parent/'download_folder.py'
assert hashlib.sha256(src.read_bytes()).hexdigest()=='ad0042b99e7adbaff1c4adf542ba60838887b9d66ff7a96555c736168132d143'
import requests
parse=importlib.import_module('gdown.download_folder')._parse_google_drive_file
sess=requests.Session();sess.trust_env=False
sess.proxies={'http':'http://137.189.90.241:8000/','https':'http://137.189.90.241:8000/'}
deadline=time.monotonic()+180;requests_count=0
secret=re.compile(rb'(?i)(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
def listing(file_id):
 global requests_count
 assert re.fullmatch('[A-Za-z0-9_-]+',file_id) and requests_count<4 and time.monotonic()<deadline
 url='https://drive.google.com/drive/folders/'+file_id;requests_count+=1
 r=sess.get(url,params={'hl':'en'},timeout=(10,30),allow_redirects=False)
 assert r.status_code==200 and len(r.content)<8*2**20
 _,children=parse(url,r.text)
 assert len({n for _,n,_ in children})==len(children)
 assert not secret.search(json.dumps(children).encode())
 return children
OUT.mkdir()
try:
 children=listing('1yKoLdcEpouFsG8RpsWH0XPFPEVWi9BNz')
 dated=[r for r in children if re.fullmatch('09[0-9]{2}',r[1])]
 selected=[r for r in dated if '0906'<=r[1]<='0908'];assert len(selected)<=3
 private={'root':children,'recent':[]};public=[]
 for file_id,name,kind in sorted(selected,key=lambda r:r[1]):
  assert kind=='application/vnd.google-apps.folder'
  entries=listing(file_id);assert len(entries)<50
  for _,n,_ in entries:assert PurePosixPath(n).name==n and '\\' not in n and n not in ('.','..')
  archives={n for _,n,k in entries if n.endswith('.tar.gz') and k!='application/vnd.google-apps.folder'}
  local={p.name for p in (B/'external/senior_data/mle'/name).glob('*.tar.gz')}
  private['recent'].append({'date':name,'entries':entries,'missing':sorted(archives-local)})
  public.append({'date':name,'entries':len(entries),'remote_archives':len(archives),'local_archives':len(local),
    'missing_archives':len(archives-local),'local_extra_names':len(local-archives),
    'config_v2_sidecars':sum(n.endswith('.config_v2.jsonl') for _,n,_ in entries),
    'other_non_archive_files':sum(not n.endswith('.tar.gz') and k!='application/vnd.google-apps.folder' for _,n,k in entries),
    'subfolders':sum(k=='application/vnd.google-apps.folder' for _,_,k in entries)})
 raw=json.dumps(private,sort_keys=True).encode();assert not secret.search(raw)
 with (OUT/'inventory.private.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 result={'classification':'SAFE_UPLOAD_METADATA_ONLY_NOT_CONTENT_OR_TRAINING_ADMISSION',
   'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'root_entries':len(children),
   'september_date_folders':sorted(r[1] for r in dated),'checked_folders':public,'requests':requests_count,
   'archive_payloads_downloaded':0,'archive_payloads_opened':0,'frozen_intake_inputs_changed':False,
   'private_inventory_sha256':hashlib.sha256(raw).hexdigest(),'name_equality_is_not_content_equality':True,
   'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 blob=json.dumps(result,sort_keys=True,indent=2).encode();assert not secret.search(blob)
 with (OUT/'summary.json').open('xb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
 print(json.dumps(result,sort_keys=True));print('summary_sha256='+hashlib.sha256(blob).hexdigest())
except Exception as e:
 result={'status':'METADATA_FAILED_CLOSED','error_type':type(e).__name__,'requests':requests_count,
   'error_sha256':hashlib.sha256(str(e).encode()).hexdigest()}
 with (OUT/'FAILED.json').open('x') as f:json.dump(result,f,sort_keys=True)
 print(json.dumps(result));sys.exit(1)
