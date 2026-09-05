"""One foreground call per invocation after exact age, within this sleep lease.

Uses the unchanged credential-first/outcome-blind accumulator. No scheduler,
background monitor, new cohort or outcome reader. At most nine spaced calls:
three stable observations plus six archive transactions; never a sleep loop.
"""
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import time

from phase1.scripts import foreground_intake_session_20260905 as base

BASE_SHA256 = 'd0769998335115694302d50b39799e91d39fb2aabb77ddd9d59f7d7f1bf70c43'
DERIVED_SHA256 = 'f7af6bbbd3d253f3b8608a38293c7e750487f2ae72571db0b2ef07b3d1d3e599'
SYNC_RECEIPT = Path('/research/d7/spc/yzyang4/senior-0904-sync-20260905/safe_receipt.json')
SYNC_SHA256 = '282ae8972a9153e15cdffe1c3f0a8e3deb05b6d84769af4243548fd71d89a4c1'
MATURITY = dt.datetime.fromisoformat('2026-09-05T19:44:48.903091+00:00').timestamp()
START = dt.datetime.fromisoformat('2026-09-05T19:45:00+00:00').timestamp()
END = dt.datetime.fromisoformat('2026-09-06T02:20:00+00:00').timestamp()
MAX_CALLS = 9
OUT = Path('/research/d7/spc/yzyang4/session-0904-maturity-intake-20260906')
BASELINE = '76a2d7d426b1da88f30d28449506fea78208f9ca5cd012ba6316efe346462285'


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    base.require(START > MATURITY and START <= time.time() < END, 'outside_mature_session_window')
    previous = sorted(OUT.glob('wrapper-*.json')) if OUT.exists() else []
    base.require(len(previous) < MAX_CALLS, 'session_call_limit')
    base.require([p.name for p in previous] == [f'wrapper-{i:03d}.json' for i in range(len(previous))], 'wrapper_history_gap')
    # A failed/incomplete base invocation cannot be retried under a new index.
    base.require(len(list(OUT.glob('poll-*'))) == len(previous), 'unfinished_prior_intake')
    base.require(digest(Path(base.__file__)) == BASE_SHA256, 'base_driver_drift')
    shell = Path(base.__file__).resolve().with_name(Path(base.REL).name)
    base.require(digest(shell) == DERIVED_SHA256, 'derived_shell_drift')
    raw = base.regular(SYNC_RECEIPT)
    base.require(hashlib.sha256(raw).hexdigest() == SYNC_SHA256 and not base.SECRET.search(raw), 'sync_receipt_drift')
    sync = json.loads(raw)
    base.require(dt.datetime.fromisoformat(sync['all_files_six_hour_age_at_utc']).timestamp() == MATURITY
        and sync['downloaded_archives'] == 6 and sync['bytes'] == 179805006, 'maturity_source_binding')
    base.START, base.END, base.OUT, base.BASELINE = START, END, OUT, BASELINE
    base.main()
    receipt = {'wrapper_sha256': digest(Path(__file__)), 'base_driver_sha256': BASE_SHA256,
        'sync_receipt_sha256': SYNC_SHA256, 'maturity_utc': sync['all_files_six_hour_age_at_utc'],
        'session_end_utc': dt.datetime.fromtimestamp(END, dt.timezone.utc).isoformat(),
        'poll': len(previous),
        'foreground_receipt_sha256': digest(OUT/f'poll-{len(previous):03d}'/'receipt.json'),
        'background_process_started': False}
    target = OUT/f'wrapper-{len(previous):03d}.json'
    with target.open('x') as f: json.dump(receipt, f, sort_keys=True, indent=2)
    target.chmod(0o400)
    print(json.dumps({'status': '0904_MATURE_FOREGROUND_CALL_COMPLETE', **receipt}, sort_keys=True))


if __name__ == '__main__':
    try: main()
    except Exception as exc:
        reason = str(exc) if isinstance(exc, RuntimeError) and re.fullmatch('[a-z_]+', str(exc)) else 'detail_withheld'
        print(json.dumps({'status': '0904_INTAKE_FAILED_CLOSED', 'reason': reason}))
        raise SystemExit(1)
