"""Read-only v2 progress and intervention replay; no interim score output."""
import datetime
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(sys.argv[1]) if len(sys.argv) == 2 else Path('/research/d7/spc/yzyang4/scheduling-generation-quota-20261017-v3')
assert len(sys.argv) <= 2 and str(ROOT) in (
    '/research/d7/spc/yzyang4/scheduling-generation-quota-20261017-v2',
    '/research/d7/spc/yzyang4/scheduling-generation-quota-20261017-v3')
ORDER = ('partitioned', 'pooled', 'pooled', 'partitioned')


def load(path):
    return json.loads(path.read_text())


def replay(path, mode):
    # Read one finite snapshot. A partial last append is not a completed event.
    raw = path.read_text()
    complete = raw.splitlines()
    if raw and not raw.endswith('\n'):
        complete = complete[:-1]
    waiting, active, seen = {}, {}, set()
    admissions = borrowed = peak = 0
    for line in complete:
        event = json.loads(line)
        kind, key = event['event'], event.get('key')
        if kind == 'queued':
            request = {k: event['request'][k] for k in ('key', 'task', 'role', 'requested', 'run')}
            key = request['key']
            assert key not in seen
            seen.add(key)
            waiting[key] = request
        elif kind == 'admitted':
            assert len(active) < 4
            eligible = [r for r in waiting.values() if mode == 'pooled' or
                        sum(x['task'] == r['task'] for x in active.values()) < 2]
            assert eligible
            chosen = min(eligible, key=lambda r: (r['role'] != 'analyze', r['requested'], r['run']))
            assert key == chosen['key'], 'live generation arbiter differs from frozen contract'
            borrowed += sum(x['task'] == chosen['task'] for x in active.values()) >= 2
            admissions += 1
            active[key] = waiting.pop(key)
            peak = max(peak, len(active))
        elif kind == 'released':
            assert key in active
            active.pop(key)
        elif kind == 'cancelled':
            assert key in waiting
            waiting.pop(key)
        elif kind not in ('parent_used', 'round_complete', 'abandoned', 'warm_start'):
            raise ValueError('unknown generation event')
    return dict(mode=mode, metadata_order_passed=True, admissions=admissions,
                borrowed_admissions=borrowed, peak_active=peak,
                active=len(active), waiting=len(waiting), complete_event_lines=len(complete))


def main():
    out = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), root=str(ROOT))
    for name in ('plan', 'preflight', 'submit-intent', 'launch', 'service-ready', 'closed'):
        out[name] = (ROOT / f'{name}.json').exists()
    out['cpu_inputs'] = sum((ROOT / f'input-matrix/{i}.safe.json').exists() for i in range(32))
    if out['plan']:
        raw = (ROOT / 'plan.json').read_bytes()
        out['plan_sha256'] = hashlib.sha256(raw).hexdigest()
        out['source_commit'] = json.loads(raw)['source_commit']
    if out['launch']:
        out['job'] = load(ROOT / 'launch.json')['job']
    out['started'] = sum((ROOT / f'episode-{i}/deadline.json').exists() for i in range(32))
    out['finished_receipts'] = sum((ROOT / f'episode-{i}/finished.json').exists() for i in range(32))
    out['pool_slots_finished'] = sum((ROOT / f'block-{i}/budget-slot.json').exists() for i in range(4))
    out['quota_pools'] = [dict(block=b, **replay(ROOT / f'generation-{b}/events.jsonl', mode))
                         for b, mode in enumerate(ORDER) if (ROOT / f'generation-{b}/events.jsonl').exists()]
    if out['closed']:
        c = load(ROOT / 'closed.json')
        out.update(complete=c['complete'], attempted_blocks=c['attempted_blocks'], error=c['error'])
    print(json.dumps(out, sort_keys=True))


if __name__ == '__main__':
    main()
