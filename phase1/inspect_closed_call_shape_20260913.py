import json
from pathlib import Path
import sqlite3
root=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-y_p2tlmi')
for p in sorted((root/'runs').glob('*critic_topk_random/checkpoint/forets-candidates-private/batch-2.sqlite')):
    with sqlite3.connect(p.as_uri()+'?mode=ro',uri=True) as db:d=json.loads(db.execute('SELECT payload FROM snapshot WHERE id=1').fetchone()[0])
    print(json.dumps(dict(run=p.parts[-4],keys=list(d),calls=[dict(keys=list(c),role=c['intent']['role'],state=c['state'],
        metadata_keys=list(c.get('execution_metadata') or {})) for c in d['task_calls']])))
