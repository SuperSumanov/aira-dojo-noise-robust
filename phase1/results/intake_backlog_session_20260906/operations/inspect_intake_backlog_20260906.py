"""Read archive-observer/transaction METADATA only; emit date-bucket counts."""
from collections import Counter
import datetime as dt
import fcntl
import hashlib
import json
from pathlib import Path
import re
import time

base = Path('/research/d7/spc/yzyang4/prospective_decision_v1')
first = '76a2d7d426b1da88f30d28449506fea78208f9ca5cd012ba6316efe346462285'
expected = 'db4ba10d1441d4305666cbb67fd2f2dd31a9c79aab2c7720055e985a9b1bcfd9'
secret = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
reads = {}
def raw(path):
    assert path.resolve(strict=True) == path and path.is_file() and path.stat().st_size < 10_000_000
    x = path.read_bytes(); assert not secret.search(x)
    reads[path] = hashlib.sha256(x).hexdigest()
    return x
def day(relative):
    p = Path(relative)
    assert not p.is_absolute() and '..' not in p.parts and len(p.parts) == 2
    assert re.fullmatch(r'\d{4}', p.parts[0])
    return p.parts[0]
with (base/'runner.lock').open('rb') as lock:
    fcntl.flock(lock, fcntl.LOCK_SH|fcntl.LOCK_NB)
    latest = raw(base/'LATEST').decode().strip(); assert latest == expected
    old_raw = raw(base/'snapshots'/first/'transactions.jsonl')
    now_raw = raw(base/'snapshots'/latest/'transactions.jsonl')
    assert now_raw.startswith(old_raw)
    old = [json.loads(x) for x in old_raw.splitlines()]
    current = [json.loads(x) for x in now_raw.splitlines()]
    for key in ('archive_relative_path', 'archive_sha256', 'drop_id'):
        assert len({r[key] for r in current}) == len(current)
    observed = json.loads(raw(base/'observations.json'))
    assert observed['protocol'] == 'prospective_archive_observer_v1'
    appended_days = Counter(day(r['archive_relative_path']) for r in current[len(old):])
    counts = Counter(); remaining = Counter(); ready = Counter()
    now = time.time()
    for relative, row in observed['entries'].items():
        if not row['present']: counts['not_present'] += 1; continue
        counts['present'] += 1
        flags = (row['baseline'], row['committed_archive_sha256'] is not None, row['rejected_archive_sha256'] is not None)
        assert sum(flags) <= 1
        if flags[0]: counts['baseline'] += 1
        elif flags[1]: counts['committed'] += 1
        elif flags[2]: counts['rejected'] += 1
        else:
            counts['pending'] += 1; remaining[day(relative)] += 1
            if (now-row['mtime_ns']/1e9 >= 21600 and row['stable_observations'] >= 3
                    and row['last_observed_at_epoch']-row['first_stable_at_epoch'] >= 600):
                ready[day(relative)] += 1
    assert counts['committed'] == len(current)
    assert counts['present'] == sum(counts[k] for k in ('baseline', 'committed', 'rejected', 'pending'))
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p,h in reads.items())
result = {'classification': 'ARCHIVE_BACKLOG_METADATA_ONLY', 'current_time_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
    'initial_snapshot': first, 'latest': latest, 'counts': dict(counts),
    'session_appended_transactions': len(current)-len(old), 'session_appended_archive_dates': dict(appended_days),
    'pending_archive_dates': dict(remaining), 'ready_archive_dates': dict(ready),
    'observations_sha256': reads[base/'observations.json'],
    'transactions_sha256': reads[base/'snapshots'/latest/'transactions.jsonl'],
    'duplicate_transaction_paths_hashes_drop_ids': 0, 'source_files_mutated': False,
    'archive_payload_labels_predictions_or_candidate_identities_read': False,
    'individual_archive_paths_or_ids_emitted': False}
serialized = (json.dumps(result, sort_keys=True)+'\n').encode()
with Path('/tmp/intake-backlog-20260906-metadata.json').open('xb') as f: f.write(serialized)
print(serialized.decode().strip())
print(json.dumps({'metadata_receipt_sha256': hashlib.sha256(serialized).hexdigest()}))
