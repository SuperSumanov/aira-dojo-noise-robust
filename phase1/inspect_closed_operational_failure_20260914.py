"""Only exception class names from closed execution logs; never model content."""
import json
from pathlib import Path
import re
import monitor_edit_scope_20260914 as es

rows=[]
for block in (1,2):
    start=es.ROOT/f'block-{block}.runtime/started.json'
    if not start.exists():continue
    pool=es.read(es.ROOT/es.read(start)['pool_manifest'])
    for rid,t in pool['tasks'].items():
        if t['status'] in ('pending','launching','running') or not t['attempts']:continue
        identity=Path(t['attempts'][0]['identity_path'])
        if not identity.resolve().is_relative_to(es.ROOT/'runs/srun_pool'):raise ValueError('scope')
        work=identity.with_suffix('.bounded')/'execution';p=work/'summary.json'
        if not p.exists():continue
        s=es.read(p)
        if s['status']!='failed':continue
        log=work/'stderr.private.log'
        with log.open('rb') as f:f.seek(max(0,log.stat().st_size-24000));raw=f.read()
        names=re.findall(rb'(?:^|\n)(?:[a-zA-Z_][a-zA-Z0-9_]*\.)*([a-zA-Z_][a-zA-Z0-9_]*(?:Error|Exception|Expired)):',raw)
        rows.append(dict(run_id=rid,status=s['status'],elapsed_seconds=s['elapsed_seconds'],exception_classes=[v.decode() for v in names[-3:]],
            raw_exported=False))
print(json.dumps(rows))
