"""Fatal worker failure closes the pool; ordinary candidate failure does not.

Called after all current-pool workers have been cleaned up, before the next
pool can start. Does not inspect scores, valid flags, predictions or content.
"""
import json
from pathlib import Path


def require_completed_workers(root, rows, results):
    expected={r['index'] for r in rows}
    if len(results)!=len(rows) or {r.get('index') for r in results}!=expected:
        raise RuntimeError('incomplete worker closure; stop remaining pools')
    for r in results:
        if r.get('returncode')!=0 or r.get('cleanup_verified') is not True or r.get('finished') is not True:
            raise RuntimeError('worker infrastructure failure; stop remaining pools')
        f=json.loads((Path(root)/f"episode-{r['index']}"/'finished.json').read_text())
        if f.get('status') not in ('completed','budget_exhausted'):
            raise RuntimeError('abnormal worker status; stop remaining pools')
    return True
