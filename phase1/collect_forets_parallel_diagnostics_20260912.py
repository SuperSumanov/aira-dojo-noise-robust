"""Read only already-closed development logs; export safe counters, never code/text."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import statistics

ROOT = Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-cxb9p0og')
HANDSHAKE = ('received', 'foreign_parent', 'shell_reply', 'idle_status', 'other_type',
             'sent', 'matched_reply', 'matched_idle', 'paired', 'elapsed_seconds', 'success')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def collect(root=ROOT):
    if root.resolve() != ROOT:
        raise ValueError('fixed revealed development allocation only')
    receipt = json.loads((root/'recovery-readout-finished.json').read_bytes())
    raw = (root/'wallclock-summary.json').read_bytes()
    if receipt['status'] != 'verified' or sha(raw) != receipt['summary_sha256']:
        raise ValueError('whole-allocation readout required')
    summary = json.loads(raw)
    start = json.loads((root/'block-1.runtime/started.json').read_bytes())
    pool = json.loads((root/start['pool_manifest']).read_bytes())
    if summary['job'] != '13156' or set(pool['tasks']) != {r['run_id'] for r in summary['rows']}:
        raise ValueError('allocation/run binding')
    rows = []
    with sqlite3.connect((root/'paid.sqlite').as_uri()+'?mode=ro', uri=True) as db:
        for original in summary['rows']:
            rid = original['run_id']
            attempt = pool['tasks'][rid]['attempts']
            if len(attempt) != 1:
                raise ValueError('not single original attempt')
            identity = Path(attempt[0]['identity_path'])
            execution = identity.with_suffix('.bounded')/'execution'
            if not execution.resolve().is_relative_to(root):
                raise ValueError('log outside allocation')
            billed = dict(db.execute('SELECT id,state FROM calls WHERE scope=?', (rid,)))
            handshakes, requests, hashes, seen = [], [], {}, set()
            for name in ('stderr.private.log', 'stdout.private.log'):
                path = execution/name
                if not path.exists():
                    continue
                if path.is_symlink():
                    raise ValueError('symlink log')
                data = path.read_bytes()
                hashes[name] = sha(data)
                for match in re.finditer(r'(kernel_handshake|parallel_transport) (\{[^\n]+\})', data.decode(errors='replace')):
                    kind, payload = match.groups()
                    value = json.loads(payload)
                    if kind == 'kernel_handshake':
                        if set(value) != set(HANDSHAKE):
                            raise ValueError('unexpected handshake fields')
                        handshakes.append({k:value[k] for k in HANDSHAKE})
                    else:
                        ident = value['attempt_id']
                        if ident not in billed or ident in seen or value['concurrency_limit'] != 4:
                            raise ValueError('request identity/cap mismatch')
                        if value['settled'] != (billed[ident] == 'settled'):
                            raise ValueError('request and billing state differ')
                        seen.add(ident)
                        requests.append(value)
            latencies = [v['request_and_settlement_seconds'] for v in requests]
            rows.append(dict(run_id=rid, log_sha256=hashes,
                handshake_events=len(handshakes), handshake_successes=sum(v['success'] for v in handshakes),
                failed_handshakes=[v for v in handshakes if not v['success']],
                request_traces=len(requests), billed_requests=len(billed),
                client_peak_inflight=max((v['active_at_dispatch'] for v in requests), default=0),
                per_request_median_seconds=statistics.median(latencies) if latencies else None))
    return dict(job='13156', summary_sha256=sha(raw), rows=rows, reader_sha256=sha(Path(__file__).read_bytes()),
        role='posthoc_safe_transport_and_handshake_diagnostics',
        limitation='Request durations overlap and include transport/settlement; not provider inference speed or causal speedup. No kernel response does not identify the underlying server/transport cause.')


if __name__ == '__main__':
    result = collect()
    with (ROOT/'parallel-diagnostics.json').open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print(json.dumps(result))
