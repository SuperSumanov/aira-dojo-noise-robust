"""Bounded foreground successor: unchanged scientific intake, new source binding."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import time
from phase1.scripts import foreground_intake_session_20260905 as base

BASE_SHA = 'd0769998335115694302d50b39799e91d39fb2aabb77ddd9d59f7d7f1bf70c43'
SHELL_SHA = 'f7af6bbbd3d253f3b8608a38293c7e750487f2ae72571db0b2ef07b3d1d3e599'
START = dt.datetime.fromisoformat('2026-09-08T03:40:46+00:00').timestamp()
END = dt.datetime.fromisoformat('2026-09-08T05:40:46+00:00').timestamp()
CALL_CAP = 2700
MAX_CALLS = 8
OUT = Path('/research/d7/spc/yzyang4/session-0906-intake-20260908')
BASELINE = '6db37288ac0fe2ca1b833ff63c3b10318cd13610c023a9d2412c194a67dfd116'
SOURCE = Path('/research/d7/spc/yzyang4/external/senior_data/mle/0906')
PROOF = Path('/research/d7/spc/yzyang4/senior-0906-sync-20260908/private_manifest.json')
PROOF_SHA = 'c960d1e4c59cffcb5c571f08a7d87792e89c178758bff6982bad719e9088a48b'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024**2), b''):
            h.update(b)
    return h.hexdigest()


def source_binding():
    raw = base.regular(PROOF)
    base.require(hashlib.sha256(raw).hexdigest() == PROOF_SHA and not base.SECRET.search(raw), 'source_proof_drift')
    rows = json.loads(raw)['records']
    base.require(len(rows) == 11 and len({r['name'] for r in rows}) == 11, 'source_count')
    base.require(SOURCE.resolve() == SOURCE and not SOURCE.is_symlink(), 'unsafe_source_root')
    base.require({p.name for p in SOURCE.iterdir()} == {r['name'] for r in rows}, 'source_inventory_drift')
    base.require(sum(1 for _ in SOURCE.parent.glob('*/*.tar.gz')) == 354, 'unknown_source_accrual')
    fingerprints = []
    for r in rows:
        p = SOURCE / r['name']
        base.require(p.parent == SOURCE and p.resolve() == p and p.is_file() and not p.is_symlink(), 'unsafe_source_file')
        s = p.stat()
        before = (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode, s.st_uid, s.st_nlink)
        base.require(s.st_size == r['bytes'] and s.st_mtime_ns == r['mtime_ns']
                     and s.st_mode & 0o777 == 0o400 and s.st_uid == os.getuid() and s.st_nlink == 1,
                     'source_metadata_drift')
        base.require(time.time() - s.st_mtime >= 21600, 'source_age_gate')
        base.require(sha(p) == r['sha256'], 'source_bytes_drift')
        z = p.stat()
        after = (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns, z.st_mode, z.st_uid, z.st_nlink)
        base.require(before == after, 'source_changed_during_hash')
        fingerprints.append((r['name'], before))
    return hashlib.sha256(json.dumps(sorted(fingerprints), separators=(',', ':')).encode()).hexdigest()


def main():
    now = time.time()
    base.require(START <= now and now + CALL_CAP <= END, 'outside_bounded_session_window')
    prior = sorted(OUT.glob('wrapper-*.json')) if OUT.exists() else []
    base.require(len(prior) < MAX_CALLS, 'session_call_limit')
    base.require([p.name for p in prior] == [f'wrapper-{i:03d}.json' for i in range(len(prior))], 'wrapper_history_gap')
    base.require(len(list(OUT.glob('poll-*'))) == len(prior), 'unfinished_prior_intake')
    base.require(sha(Path(base.__file__)) == BASE_SHA, 'base_driver_drift')
    shell = Path(base.__file__).resolve().with_name(Path(base.REL).name)
    base.require(sha(shell) == SHELL_SHA, 'derived_shell_drift')
    binding = source_binding()
    for i, p in enumerate(prior):
        old = json.loads(base.regular(p))
        base.require(old['wrapper_sha256'] == sha(Path(__file__)) and old['poll'] == i
                     and old['source_fingerprint_sha256'] == binding
                     and old['foreground_receipt_sha256'] == sha(OUT / f'poll-{i:03d}/receipt.json'),
                     'prior_wrapper_or_source_drift')
    previous = (base.START, base.END, base.OUT, base.BASELINE)
    try:
        base.START, base.END, base.OUT, base.BASELINE = START, END, OUT, BASELINE
        base.main()
    finally:
        base.START, base.END, base.OUT, base.BASELINE = previous
    base.require(source_binding() == binding, 'source_changed_during_intake')
    receipt = dict(wrapper_sha256=sha(Path(__file__)), base_driver_sha256=BASE_SHA,
                   readonly_source_manifest_sha256=PROOF_SHA, source_fingerprint_sha256=binding,
                   poll=len(prior), foreground_receipt_sha256=sha(OUT / f'poll-{len(prior):03d}/receipt.json'),
                   session_end_utc=dt.datetime.fromtimestamp(END, dt.timezone.utc).isoformat(),
                   background_process_started=False, scientific_or_stability_rules_changed=False,
                   archive_bytes_or_mtime_modified=False, training_source_qualified=False)
    target = OUT / f'wrapper-{len(prior):03d}.json'
    with target.open('x') as f:
        json.dump(receipt, f, sort_keys=True, indent=2)
        f.flush()
        os.fsync(f.fileno())
    target.chmod(0o400)
    print(json.dumps(dict(status='0906_FOREGROUND_CALL_COMPLETE', **receipt), sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        reason = str(exc) if isinstance(exc, RuntimeError) and re.fullmatch('[a-z_]+', str(exc)) else 'detail_withheld'
        print(json.dumps(dict(status='0906_INTAKE_FAILED_CLOSED', reason=reason)))
        raise SystemExit(1)
