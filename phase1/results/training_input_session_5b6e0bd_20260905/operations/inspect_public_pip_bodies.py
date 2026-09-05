import json,os,re,stat,zipfile
from pathlib import Path
root=Path('/research/d7/spc/yzyang4/cache/pip/http-v2')
assert root.resolve(strict=True)==root and not root.is_symlink()
rows=[]
for p in sorted(root.rglob('*.body')):
    s=p.lstat()
    if s.st_size<100*1024**2:continue
    assert p.resolve(strict=True)==p and stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid==os.getuid()
    with zipfile.ZipFile(p) as z:
        names=[n for n in z.namelist() if n.endswith('.dist-info/METADATA')]
        assert len(names)==1
        raw=z.read(names[0]);name=re.search(rb'^Name: ([A-Za-z0-9_.-]+)$',raw,re.M).group(1).decode()
        version=re.search(rb'^Version: ([A-Za-z0-9_.+-]+)$',raw,re.M).group(1).decode()
    if not (name in {'torch','triton','xgboost','tensorflow'} or name.startswith('nvidia-')):
        continue  # Only explicitly reviewed, replaceable upstream packages.
    rows.append({'path':str(p),'bytes':s.st_size,'allocated_bytes':s.st_blocks*512,'inode':s.st_ino,'device':s.st_dev,'mtime_ns':s.st_mtime_ns,'name':name,'version':version})
out=Path('/tmp/public-pip-body-inventory-20260905.json')
with out.open('x') as f:json.dump(rows,f,sort_keys=True,indent=2)
print(json.dumps({'files':len(rows),'bytes':sum(r['bytes'] for r in rows),'allocated_bytes':sum(r['allocated_bytes'] for r in rows),'inventory':str(out),'packages':[{'name':r['name'],'version':r['version']} for r in rows]},sort_keys=True))
