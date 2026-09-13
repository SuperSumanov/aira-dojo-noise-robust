"""In-session read-only watcher; prints only changes and exits at full closure."""
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import time

END=dt.datetime(2026,9,14,3,6,43,tzinfo=dt.timezone.utc)
prior=None
while dt.datetime.now(dt.timezone.utc)<END:
    run=subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('monitor_current_experiments_20260914.py'))],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45)
    if run.returncode:
        print(json.dumps(dict(status='MONITOR_FAILED',exit_code=run.returncode)),flush=True);sys.exit(1)
    state=json.loads(run.stdout)
    # Accounting elapsed time changes continually; compare statuses only.
    signature=json.dumps([state['blocks'],state['closed_termination_reasons'],
        [line.split('|')[:2] for line in state['all_accounting']]],sort_keys=True)
    if signature!=prior:
        print(json.dumps({key:state[key] for key in ('utc','blocks','billing','closed_termination_reasons','all_accounting')}),flush=True)
        prior=signature
    rows=[r for b in state['blocks'] for r in b.get('runs',[])]
    if len(rows)==16 and not state['all_queue'] and all(r['status'] not in ('pending','launching','running') for r in rows):
        print('ALL_SCOPE_RUNS_CLOSED',flush=True);break
    time.sleep(60)
