"""Read-only, credential-first model-server telemetry at closed pool boundaries.

Client permits are not server occupancy. Discrete log samples can show observed
idle gaps, not prove that every request was cancelled or exclude cache effects.
"""
import argparse, hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path

BASE = Path('/research/d7/spc/yzyang4')
CASES = (
    ('18807', 'scheduling-colocation-20261016-v1', '36ce5852b26de2299755c19a8b9711a1f4161d68abd25a3de6cc7687cdde8560'),
    ('18997', 'scheduling-selective-20261017-v1', '1783555a7c680021b2a1bae874798f1042c0bfe79d0b11af70fa7f2a75d26e32'),
    ('19004', 'scheduling-generation-quota-20261017-v1', 'f08b3052fcecf467f500b5b9aa6638087c602321ca3a81bf22ef8b65a55b41f9'),
)
SECRET = re.compile(r'(?i)\b(?:sk-[A-Za-z0-9._-]{12,}|bearer\s+[A-Za-z0-9._-]{12,}|(?:api[_-]?key|token|secret|password)\s*[=:]\s*[\"\']?[A-Za-z0-9._-]{12,})')
STAMP = re.compile(r'\b(\d{2})[-/](\d{2})\s+(\d{2}:\d{2}:\d{2})(?:\.\d+)?')
METRICS = re.compile(r'Running:\s*(\d+)\s+reqs.*?Waiting:\s*(\d+)\s+reqs')

def sha(raw): return hashlib.sha256(raw).hexdigest()

def inspect(job, name, pin):
    root = BASE / name
    assert sha((root / 'plan.json').read_bytes()) == pin
    slots, events, hashes = [], [], {}
    for b in range(4):
        sp, ep = root / f'block-{b}/budget-slot.json', root / f'generation-{b}/events.jsonl'
        sr, er = sp.read_bytes(), ep.read_bytes()
        hashes[str(sp.relative_to(root))] = sha(sr)
        hashes[str(ep.relative_to(root))] = sha(er)
        slots.append(json.loads(sr))
        # Only event type/time cross the redaction boundary; no candidate payload.
        events.append([(e['event'], float(e['time'])) for e in map(json.loads, er.splitlines())])
    lp = root / 'block-0/service.private.log'
    raw = lp.read_bytes()
    assert len(raw) < 32 * 1024**2
    text, hits = SECRET.subn('[REDACTED]', raw.decode(errors='replace'))
    rows, unmatched = [], 0
    for line in text.splitlines():
        if 'Avg generation throughput:' not in line: continue
        stamp, metric = STAMP.search(line), METRICS.search(line)
        if not stamp or not metric:
            unmatched += 1
            continue
        m, d, clock = stamp.groups()
        dt = datetime.fromisoformat(f'2026-{m}-{d}T{clock}').replace(tzinfo=timezone.utc)
        rows.append((dt.timestamp(), int(metric[1]), int(metric[2])))
    assert rows and unmatched == 0, ('unparsed numeric telemetry', len(rows), unmatched)
    lo, hi = slots[0]['start'] - 900, slots[-1]['start'] + slots[-1]['actual_seconds'] + 300
    # Timestamp format omits timezone. Accept only a unique UTC/HK alignment
    # against sealed controller times; never silently assume the login timezone.
    offsets = [o for o in (0, 8*3600) if all(lo <= t-o <= hi for t, _, _ in rows)]
    assert len(offsets) == 1, ('ambiguous timestamp timezone', offsets)
    offset = offsets[0]
    rows = [(t-offset, r, w) for t, r, w in rows]
    assert all(rows[i][0] <= rows[i+1][0] for i in range(len(rows)-1))
    gaps = []
    for b in range(4):
        end = slots[b]['start'] + slots[b]['actual_seconds']
        last = max(t for event, t in events[b] if event in ('released', 'cancelled'))
        stop = min(t for event, t in events[b+1] if event == 'queued') if b < 3 else end
        assert last <= end <= stop if b < 3 else last <= end
        samples = [dict(seconds_after_last_release=t-last, running=r, waiting=w) for t,r,w in rows if last < t < stop]
        gaps.append(dict(block=b, last_client_release=last, slot_end=end, next_first_queue=stop if b<3 else None,
            interval_end=stop, samples=samples, observed_zero_samples=sum(s['running']==s['waiting']==0 for s in samples),
            observed_busy_samples=sum(s['running']>0 or s['waiting']>0 for s in samples)))
    return dict(job=job, plan_sha256=pin, log_sha256=sha(raw), source_hashes=hashes,
        credentials_redacted=hits, telemetry_samples=len(rows), unparsed_metric_lines=unmatched,
        inferred_log_utc_offset_seconds=offset, gaps=gaps)

def main():
    p=argparse.ArgumentParser(); p.add_argument('output'); a=p.parse_args()
    result=dict(reader_sha256=sha(Path(__file__).read_bytes()), pools=[inspect(*c) for c in CASES],
        limits=['Discrete service samples only; not continuous request-ID tracing or cancellation proof.',
                'No GPU/model/scorer calls, no outcomes, candidate text or raw logs exported.',
                'No primary readout/gate changes; does not rehabilitate invalid19004 or prove causal scheduling effects.',
                'Idle occupancy does not exclude prefix-cache/order/warmup effects.'])
    with Path(a.output).open('x') as f: json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(dict(reader_sha256=result['reader_sha256'], pools=[dict(job=x['job'],samples=x['telemetry_samples'],
        gaps=[{k:v for k,v in g.items() if k!='samples'} for g in x['gaps']]) for x in result['pools']]),allow_nan=False))

if __name__ == '__main__': main()
