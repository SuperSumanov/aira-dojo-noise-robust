"""One read-only snapshot of the active development pair; never launch or score."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess

ROOT = Path('/research/d7/spc/yzyang4/forets-resilience-20260910-4LGN21/package')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    env = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    account = subprocess.run(['sacct', '-j', '13004', '-P', '-n',
        '--format=JobID,State,ElapsedRaw,AllocTRES,ExitCode,Start,End'],
        env=env, capture_output=True, text=True, timeout=20, check=True)
    manifest = ROOT / 'runs/srun_pool/b3e0510df6c4/manifest.json'
    raw = manifest.read_bytes()
    pool = json.loads(raw)
    report = dict(observed_utc=datetime.now(timezone.utc).isoformat(), job_id=13004,
        role='development_live_structure_only', manifest_sha256=hashlib.sha256(raw).hexdigest(),
        sacct=account.stdout.splitlines(), runs=[],
        campaign_finished_exists=(ROOT / 'campaign.finished.json').is_file())
    for run_id, task in pool['tasks'].items():
        # IDs come only from this explicit campaign, not any corpus or frozen cohort.
        if '/' in run_id or '..' in run_id:
            raise ValueError('unexpected run identity')
        row = dict(run_id=run_id, status=task.get('status'))
        if task.get('attempts'):
            identity = Path(task['attempts'][-1]['identity_path'])
            log = identity.with_suffix('.bounded') / 'execution/stderr.private.log'
            if not log.resolve().is_relative_to(ROOT.resolve()):
                raise ValueError('log escapes explicit development package')
            events = {}
            if log.is_file():
                text = log.read_text(errors='replace')
                malformed = 0
                for line in text.splitlines():
                    if 'bounded_transport {' not in line:
                        continue
                    try:
                        event = json.loads(line.split('bounded_transport ', 1)[1])
                        events[event['attempt_id']] = event
                    except (ValueError, KeyError):
                        malformed += 1
                row['malformed_transport_lines'] = malformed
                row['transport_counts'] = dict(Counter(
                    'success' if e.get('success') is True else e.get('error_type', e.get('state', 'unknown'))
                    for e in events.values()))
                row['http_status_counts'] = dict(Counter(str(e['http_status']) for e in events.values()
                    if type(e.get('http_status')) is int))
                row['opencl_error_seen'] = 'No OpenCL device' in text
            row['batches'] = []
            for step in range(4):
                ledger = ROOT / 'runs' / run_id / 'checkpoint/forets-candidates-private' / f'batch-{step}.sqlite'
                if not ledger.is_file():
                    continue
                with sqlite3.connect(ledger.as_uri() + '?mode=ro', uri=True) as db:
                    payload, digest = db.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchone()
                encoded = payload.encode() if isinstance(payload, str) else payload
                if hashlib.sha256(encoded).hexdigest() != digest:
                    raise ValueError('candidate ledger hash mismatch')
                data = json.loads(payload)
                calls = data.get('task_calls', [])
                if isinstance(calls, dict):
                    calls = calls.values()
                row['batches'].append(dict(step=step, phase=data.get('phase'),
                    candidate_count=len(data.get('candidates', [])),
                    task_call_states=dict(Counter(c.get('state', 'unknown') for c in calls))))
        report['runs'].append(row)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        with args.output.open('x', encoding='utf-8') as output:
            output.write(rendered + '\n')
    print(rendered)


if __name__ == '__main__':
    main()
