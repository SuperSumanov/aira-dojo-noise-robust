"""Recheck only the shared producer branch head; no documents/results opened."""
import json
import subprocess
from datetime import datetime, timezone

REPO = '/research/d7/spc/yzyang4/aira-dojo'
PREVIOUS = '54e8a0e3458e12443658104d244e2b6d9e553451'
command = ('source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1; '
           'git -C ' + REPO + ' fetch --quiet --no-tags fork dojo-reproduce')
result = subprocess.run(['bash', '-c', command], capture_output=True, timeout=70)
if result.returncode:
    print(json.dumps(dict(status='FETCH_FAILED',returncode=result.returncode)))
    raise SystemExit(2)
head = subprocess.check_output(['git', '-C', REPO, 'rev-parse', 'refs/remotes/fork/dojo-reproduce'],
                               stderr=subprocess.PIPE, text=True, timeout=20).strip()
print(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(), head=head,
                      previous=PREVIOUS, changed=head != PREVIOUS, documents_opened=0)))
