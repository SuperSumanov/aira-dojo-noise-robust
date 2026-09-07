"""One bounded public folder listing plus structural snapshot read, no payload."""
import datetime,hashlib,importlib,importlib.util,json,os,re,time
from pathlib import Path,PurePosixPath
base=Path('/research/d7/spc/yzyang4');out=base/'senior-metadata-resume-20260907-1001'
os.umask(0o077);out.mkdir()
src=Path(importlib.util.find_spec('gdown').origin).parent/'download_folder.py'
assert hashlib.sha256(src.read_bytes()).hexdigest()=='ad0042b99e7adbaff1c4adf542ba60838887b9d66ff7a96555c736168132d143'
import requests
parse=importlib.import_module('gdown.download_folder')._parse_google_drive_file
session=requests.Session();session.proxies={'http':'http://137.189.90.241:8000/','https':'http://137.189.90.241:8000/'}
deadline=time.monotonic()+180;requests_count=0
secret=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
def listing(file_id):
    global requests_count
    assert re.fullmatch('[A-Za-z0-9_-]+',file_id) and requests_count<6 and time.monotonic()<deadline
    url='https://drive.google.com/drive/folders/'+file_id;requests_count+=1
    r=session.get(url,params={'hl':'en'},timeout=(10,30),allow_redirects=False)
    assert r.status_code==200
    _,children=parse(url,r.text)
    assert len({name for _,name,_ in children})==len(children)
    return children
children=listing('1yKoLdcEpouFsG8RpsWH0XPFPEVWi9BNz')
dated=[row for row in children if re.fullmatch('09[0-9]{2}',row[1])]
selected=[row for row in dated if '0904'<=row[1]<='0907'];assert len(selected)<=4
private={'root':children,'recent':[]};public=[]
local=base/'external/senior_data/mle'
for file_id,name,kind in sorted(selected,key=lambda r:r[1]):
    assert kind=='application/vnd.google-apps.folder'
    entries=listing(file_id);assert len(entries)<50
    for _,n,_ in entries:assert PurePosixPath(n).name==n and '\\' not in n and n not in ('.','..')
    archives={n for _,n,k in entries if n.endswith('.tar.gz') and k!='application/vnd.google-apps.folder'}
    localnames={p.name for p in (local/name).glob('*.tar.gz')}
    private['recent'].append({'date':name,'entries':entries,'missing':sorted(archives-localnames)})
    public.append({'date':name,'entries':len(entries),'remote_archives':len(archives),'local_archives':len(localnames),
                   'missing_archives':len(archives-localnames),'local_extra_names':len(localnames-archives),
                   'sidecar_files':sum(n.endswith('.config_v2.jsonl') for _,n,_ in entries),
                   'subfolders':sum(k=='application/vnd.google-apps.folder' for _,_,k in entries)})
state=base/'prospective_decision_v1';latest=(state/'LATEST').read_text().strip();assert re.fullmatch('[0-9a-f]{64}',latest)
raw=(state/'snapshots'/latest/'accumulator/summary.json').read_bytes();assert not secret.search(raw)
v=json.loads(raw);inventory={k:v['inventory'][k] for k in ('all_physical_runs','eligible_runs','eligible_structural_pairs','eligible_tasks')}
assert all(type(n) is int and n>=0 for n in inventory.values())
assert type(v['closure']['provided']) is bool
private_raw=json.dumps(private,sort_keys=True).encode();assert not secret.search(private_raw)
(out/'inventory.private.json').write_bytes(private_raw)
result={'classification':'CURRENT_SAFE_METADATA_NOT_NEW_RUN_OR_EFFECT_EVIDENCE','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'root_entries':len(children),'september_date_folders':sorted(r[1] for r in dated),'checked_folders':public,
        'requests':requests_count,'archive_payload_downloaded':False,'archive_payload_opened':False,
        'latest':latest,'snapshot_inventory':inventory,'closure_provided':v['closure']['provided'],
        'snapshot_summary_sha256':hashlib.sha256(raw).hexdigest(),'private_inventory_sha256':hashlib.sha256(private_raw).hexdigest(),
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'name_equality_is_not_content_equality':True}
with (out/'summary.json').open('x') as f:json.dump(result,f,sort_keys=True,indent=2)
print(json.dumps(result,sort_keys=True))
