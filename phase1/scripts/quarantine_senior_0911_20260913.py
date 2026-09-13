"""One newly listed archive; bounded remote quarantine, no experiment admission."""
from pathlib import Path
import inspect
import json
import quarantine_senior_0910_20260912 as prior

def once(text,old,new):
    if text.count(old)!=1:raise ValueError('exact existing downloader anchor')
    return text.replace(old,new)

def run():
    prior.INVENTORY=Path('/research/d7/spc/yzyang4/senior-root-metadata-20260912-kjo90375/inventory.private.json')
    prior.INVENTORY_SHA='e765eddcd0af8554359e6f41abd1ca7be584f1089e05aad05702582d3813947a'
    prior.OUT=Path('/research/d7/spc/yzyang4/senior-quarantine-0911-20260913')
    prior.TOTAL_CAP=prior.FILE_CAP
    text=inspect.getsource(prior.main)
    for old,new in [
        ("x['relative']=='0910'","x['relative']=='0911'"),
        ('len(rows)!=6 or len({x[0] for x in rows})!=6 or len({x[1] for x in rows})!=6',
         'len(rows)!=1 or len({x[0] for x in rows})!=1 or len({x[1] for x in rows})!=1'),
        ("OUT/'archives/0910'","OUT/'archives/0911'"),
        ("relative='0910/'+name","relative='0911/'+name"),
        ("len({x['sha256'] for x in records})!=6","len({x['sha256'] for x in records})!=1"),
        ("group='0910',archives=6","group='0911',archives=1"),
    ]:text=once(text,old,new)
    namespace={**vars(prior),'__file__':__file__}
    exec(compile(text,'<one-archive-quarantine>','exec'),namespace);namespace['main']()

if __name__=='__main__':
    try:run()
    except Exception as exc:
        print(json.dumps(dict(status='QUARANTINE_FAILED_CLOSED',error_type=type(exc).__name__)),flush=True)
        raise SystemExit(2)
