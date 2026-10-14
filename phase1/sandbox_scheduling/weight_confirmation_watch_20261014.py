"""Bounded read-only watcher for the current chat, not a scheduler/launcher."""
from contextlib import redirect_stdout
from datetime import datetime,timezone
import io
import json
from pathlib import Path
import runpy
import time

previous=None
started=time.monotonic()
while time.monotonic()-started<10800:
    buffer=io.StringIO()
    try:
        with redirect_stdout(buffer):runpy.run_path(str(Path(__file__).with_name('weight_confirmation_status_20261014.py')))
        state=json.loads(buffer.getvalue())
    except Exception as exc:
        print(json.dumps(dict(monitor_failed=True,error_type=type(exc).__name__)),flush=True)
        raise SystemExit(1)
    if state!=previous:
        print(json.dumps(dict(observed_utc=datetime.now(timezone.utc).isoformat(),**state)),flush=True)
        previous=state
    if state['closed']:break
    time.sleep(20)
else:
    print(json.dumps(dict(monitor_window_elapsed=True,experiment_status='not_inferred')),flush=True)
