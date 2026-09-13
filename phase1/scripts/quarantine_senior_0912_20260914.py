"""One stable new-child archive only; no production admission or old-index override."""
import inspect
import json
from pathlib import Path
import quarantine_senior_0910_20260912 as old


def main():
    old.INVENTORY=Path('/research/d7/spc/yzyang4/senior-0912-metadata-20260914-s1xb8y5z/inventory.private.json')
    old.INVENTORY_SHA='918ff8f1018309a232e5f937c718ba8fcb9c22c5c0a09027877089a567260239'
    old.OUT=Path('/research/d7/spc/yzyang4/senior-quarantine-0912-20260914')
    old.TOTAL_CAP=old.FILE_CAP
    text=inspect.getsource(old.main)
    replacements=[("x['relative']=='0910'","x['relative']=='0912'"),
        ('len(rows)!=6 or len({x[0] for x in rows})!=6 or len({x[1] for x in rows})!=6',
         'len(rows)!=1 or len({x[0] for x in rows})!=1 or len({x[1] for x in rows})!=1'),
        ("OUT/'archives/0910'","OUT/'archives/0912'"),("relative='0910/'+name","relative='0912/'+name"),
        ("len({x['sha256'] for x in records})!=6","len({x['sha256'] for x in records})!=1"),
        ("group='0910',archives=6","group='0912',archives=1")]
    for a,b in replacements:
        if text.count(a)!=1:raise ValueError('downloader anchor')
        text=text.replace(a,b)
    namespace={**vars(old),'__file__':__file__}
    exec(compile(text,'<bounded-new-child-quarantine>','exec'),namespace);namespace['main']()


if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps(dict(status='QUARANTINE_FAILED_CLOSED',error_type=type(e).__name__)))
        raise SystemExit(2)
