"""Prove the missing-import failure preceded network/model dispatch."""
import sqlite3
from pathlib import Path
root=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-7wzrny21')
assert not any((root/n).exists() for n in ('block-1.plus-catalog.json','block-1.route.json','block-2.route.json','route-1.private.log','route-2.private.log'))
with sqlite3.connect((root/'paid.sqlite').as_uri()+'?mode=ro',uri=True) as db:
    assert db.execute('SELECT COUNT(*) FROM calls').fetchone()==(1310,)
print('Missing helper import preceded any request: zero new calls and no route receipts.')
