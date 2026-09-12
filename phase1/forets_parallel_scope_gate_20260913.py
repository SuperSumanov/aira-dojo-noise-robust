"""Only owned live requests may temporarily remain unsettled across two workers."""
import json
from pathlib import Path
import sqlite3
import time

def validate(state, calls, planned, active, *, now):
    if state['stopped']: raise RuntimeError('billing stopped')
    historical=[r for r in calls if r[1] not in planned and r[4]=='unresolved']
    if len(historical)!=2: raise RuntimeError('historical unknown count changed')
    for row in calls:
        if row[1] in planned and row[4]=='unresolved':
            if row[1] not in active or not 0 <= now-row[5] < 135:
                raise RuntimeError('unsettled request without a young live owned scope')

def check(root):
    root=Path(root)
    from forets_paid_budget_20260911 import snapshot
    state=snapshot(root/'paid.sqlite')
    prepared=json.loads((root/'prepared.json').read_bytes())
    planned={r['run_id'] for r in prepared['run_configs']}
    active=set()
    for block in (1,2):
        path=root/f'block-{block}.runtime/started.json'
        if not path.exists(): continue
        started=json.loads(path.read_bytes());manifest_path=root/started['pool_manifest']
        if not manifest_path.resolve().is_relative_to(root/'runs/srun_pool'):
            raise RuntimeError('foreign manifest')
        manifest=json.loads(manifest_path.read_bytes())
        if set(manifest['tasks'])!={r['run_id'] for r in prepared['run_configs'] if r['block']==block}:
            raise RuntimeError('wrong block scopes')
        active.update(k for k,v in manifest['tasks'].items() if v['status'] in ('running','launching'))
    with sqlite3.connect((root/'paid.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        calls=db.execute('SELECT * FROM calls').fetchall()
    validate(state,calls,planned,active,now=time.time())
