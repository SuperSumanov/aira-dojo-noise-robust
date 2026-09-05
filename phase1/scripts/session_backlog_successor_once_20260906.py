"""Bounded foreground successor for a measured seven-archive backlog.

The preceding seven transactions were ALL 0903, not the six downloaded 0904
archives. Preserve the original lease/history; do not change the scientific
runner, maturity, stable observations or identity/rejection rules.
"""
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import time

from phase1.scripts import foreground_intake_session_20260905 as base

BASE_SHA = 'd0769998335115694302d50b39799e91d39fb2aabb77ddd9d59f7d7f1bf70c43'
DERIVED_SHA = 'f7af6bbbd3d253f3b8608a38293c7e750487f2ae72571db0b2ef07b3d1d3e599'
OLD = Path('/research/d7/spc/yzyang4/session-0904-maturity-intake-20260906')
OUT = Path('/research/d7/spc/yzyang4/session-intake-backlog-successor-20260906')
BASELINE = 'db4ba10d1441d4305666cbb67fd2f2dd31a9c79aab2c7720055e985a9b1bcfd9'
START = dt.datetime.fromisoformat('2026-09-05T20:39:13+00:00').timestamp()
END = dt.datetime.fromisoformat('2026-09-06T02:20:00+00:00').timestamp()
MAX_CALLS = 8
OLD_RECEIPTS = (
    '2835c84c902e5ce0985902feb0c9b82cfb06a39732af0b4a003df69a0a18562e',
    '71ba284554d9e1a1fcaedb3b8397bbfe40ca9d856dbfbac62215ea852576cf2a',
    '02ef04f0597c8a4c3c78d0e04302ba0d45831a07a774814f9adcf0d26571516a',
    '4af4d215816cfb55779b01c8b5f290fec99964913fb79d7afaf1261435737dd6',
    'b123519955aa0caa4a912aab31848a44cad77174aa9454ae31e64c9103d8e6cb',
    '06a36962701fd42e6b9ae167c2d5690bdd2c89af14bf3740a0ad9f004f88e80f',
    'e2235374374ff3b6cb99fa1f7d8b092d0e88a11de9b9b3607cbefd33b296122b',
)
BACKLOG_RECEIPT = Path('/tmp/intake-backlog-20260906-metadata.json')
BACKLOG_SHA = '474d458845b97fda6f527a764bdebd4044dc4350ed7c5a7e2fcf90563d719cf3'


def digest(path): return hashlib.sha256(base.regular(path)).hexdigest()


def check_predecessor():
    base.require(len(list(OLD.glob('poll-*'))) == len(list(OLD.glob('wrapper-*.json'))) == 7,
                 'predecessor_changed')
    for i, expected in enumerate(OLD_RECEIPTS):
        p = OLD/f'poll-{i:03d}'/'receipt.json'
        base.require(digest(p) == expected, 'predecessor_receipt_changed')
        w = json.loads(base.regular(OLD/f'wrapper-{i:03d}.json'))
        base.require(w['foreground_receipt_sha256'] == expected and w['poll'] == i
            and w['wrapper_sha256'] == 'f780e525f0c060ea417f4ab0a1357f52d8a859e43846c2cfdaadf4e1ce2158f6',
            'predecessor_wrapper_changed')
    last = json.loads(base.regular(OLD/'poll-006/receipt.json'))
    base.require(last['returncode'] == 0 and last['after']['latest'] == BASELINE
                 and START >= last['finished_epoch']+300, 'predecessor_boundary')


def main():
    base.require(START <= time.time() < END, 'outside_successor_window')
    check_predecessor()
    base.require(digest(Path(base.__file__)) == BASE_SHA, 'base_driver_drift')
    shell = Path(base.__file__).resolve().with_name(Path(base.REL).name)
    base.require(digest(shell) == DERIVED_SHA, 'derived_shell_drift')
    base.require(digest(BACKLOG_RECEIPT) == BACKLOG_SHA, 'backlog_receipt_drift')
    backlog = json.loads(base.regular(BACKLOG_RECEIPT))
    base.require(backlog['latest'] == BASELINE and backlog['pending_archive_dates'] == {'0903': 1, '0904': 6}
        and backlog['ready_archive_dates'] == backlog['pending_archive_dates']
        and backlog['duplicate_transaction_paths_hashes_drop_ids'] == 0, 'measured_backlog_binding')
    base.require(sum(1 for _ in base.SOURCE.glob('*/*.tar.gz')) == 331, 'new_archive_requires_new_review')
    previous = sorted(OUT.glob('wrapper-*.json')) if OUT.exists() else []
    base.require(len(previous) < MAX_CALLS
        and [p.name for p in previous] == [f'wrapper-{i:03d}.json' for i in range(len(previous))]
        and len(list(OUT.glob('poll-*'))) == len(previous), 'successor_history_or_limit')
    for i, p in enumerate(previous):
        w = json.loads(base.regular(p))
        base.require(w['wrapper_sha256'] == digest(Path(__file__)) and w['poll'] == i
            and w['foreground_receipt_sha256'] == digest(OUT/f'poll-{i:03d}'/'receipt.json'),
            'successor_wrapper_drift')
    base.START, base.END, base.OUT, base.BASELINE = START, END, OUT, BASELINE
    base.main()
    check_predecessor()
    receipt = {'wrapper_sha256': digest(Path(__file__)), 'base_driver_sha256': BASE_SHA,
        'backlog_receipt_sha256': BACKLOG_SHA, 'predecessor_final_receipt_sha256': OLD_RECEIPTS[-1],
        'session_end_utc': dt.datetime.fromtimestamp(END, dt.timezone.utc).isoformat(),
        'poll': len(previous), 'foreground_receipt_sha256': digest(OUT/f'poll-{len(previous):03d}'/'receipt.json'),
        'background_process_started': False, 'scientific_or_stability_rules_changed': False}
    target = OUT/f'wrapper-{len(previous):03d}.json'
    with target.open('x') as f: json.dump(receipt, f, sort_keys=True, indent=2)
    target.chmod(0o400)
    print(json.dumps({'status': 'MEASURED_BACKLOG_SUCCESSOR_CALL_COMPLETE', **receipt}, sort_keys=True))


if __name__ == '__main__':
    try: main()
    except Exception as exc:
        reason = str(exc) if isinstance(exc, RuntimeError) and re.fullmatch('[a-z_]+', str(exc)) else 'detail_withheld'
        print(json.dumps({'status': 'BACKLOG_SUCCESSOR_FAILED_CLOSED', 'reason': reason}))
        raise SystemExit(1)
