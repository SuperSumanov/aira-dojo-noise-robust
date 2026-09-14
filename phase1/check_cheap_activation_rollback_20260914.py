from contextlib import closing
import json,sqlite3
from pathlib import Path
BASE=Path('/research/d7/spc/yzyang4')
out=[]
for name in ('forets-wallclock-20260912-q_imzdb_','forets-wallclock-20260912-tpjljg17'):
    with closing(sqlite3.connect((BASE/name/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        tables=[r[0] for r in db.execute('select name from sqlite_master where type="table"')]
        item=dict(root=name,tables=tables)
        if 'auth' in tables:item['auth']=db.execute('select digest,stopped from auth').fetchall();item['calls']=db.execute('select count(*) from calls').fetchone()[0]
        out.append(item)
if out[0]['auth']!=[['c102fefa484c9902367aa4dca4ea1a451c241f482e4b30eb3953fe2c6fdad3e8',0]] and out[0]['auth']!=[('c102fefa484c9902367aa4dca4ea1a451c241f482e4b30eb3953fe2c6fdad3e8',0)]:raise ValueError('predecessor no longer active')
if out[0]['calls']!=2623 or out[1]['tables']:raise ValueError('rollback unconfirmed')
print(json.dumps(dict(status='ROLLBACK_CONFIRMED_NO_NEW_CHARGES',items=out)))
