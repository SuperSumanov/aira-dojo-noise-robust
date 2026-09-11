"""Independent post-closeout check of this failed development matrix.

Does not import the primary score reader, choose partial submissions or replay
programs. Only structured failure classes, counts and charges leave this script.
"""
from collections import Counter
from contextlib import closing
import datetime as dt
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess

ROOT = Path('/research/d7/spc/yzyang4/forets-paid-20260911-oh3np7b8')
SECRET = re.compile(r'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def classify(text):
    if 'TimeoutError: Execution exceeded' in text:
        return 'execution_timeout'
    if re.search(r'(TypeError: (?:train\(\)|LGBMClassifier\.fit\(\)) got an unexpected keyword argument|LightGBMError: Parameter verbose should)', text):
        return 'lightgbm_removed_or_invalid_keyword'
    if 'Cannot setitem on a Categorical with a new category' in text:
        return 'pandas_categorical_assignment'
    if 'Encoders require their input argument' in text:
        return 'mixed_type_encoding'
    if 'IterativeImputer is experimental' in text:
        return 'experimental_import'
    if 'Column not found: Transported' in text:
        return 'missing_target_column'
    return 'other_code_error'


def main():
    p = ROOT
    manifest = json.loads((p/'runtime-manifest-20260912.json').read_text())
    primary = json.loads((p/'final-readout-20260912/summary.json').read_text())
    work = json.loads((p/'cost-work-20260912/measurements.json').read_text())
    assert len(manifest['runs']) == len(primary['runs']) == len(work['runs']) == 8
    assert [r['run_id'] for r in manifest['runs']] == [r['run_id'] for r in primary['runs']]
    env = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    result = subprocess.run(['sacct','-n','-X','-P','-j','13088,13112',
        '-o','JobIDRaw,State%32,NodeList,ElapsedRaw,AllocTRES%256,User,ExitCode'],
        capture_output=True, text=True, timeout=15, env=env, check=True)
    allocation_rows = [r.split('|') for r in result.stdout.splitlines() if r.strip()]
    assert len(allocation_rows) == 2
    elapsed = {}
    for job, state, node, seconds, resources, user, code in allocation_rows:
        tres = dict(x.split('=',1) for x in resources.split(',') if '=' in x)
        assert state == 'COMPLETED' and node == 'gpu28' and user == 'yzyang4' and code == '0:0'
        assert tres['gres/gpu'] == '2' and job in ('13088','13112')
        elapsed[job] = int(seconds)
    assert len(elapsed) == 2
    totals = Counter()
    evidence = {}
    rows = []
    for run, original in zip(manifest['runs'], primary['runs']):
        process = json.loads((p/run['process_summary']).read_text())
        assert process['status'] == 'completed' and process['started'] is True and process['returncode'] == 0
        assert original['final_event_issue'] == 'missing_final_event' and not original['comparable_final']
        final = p/run['run_dir']/'json/eval.jsonl'
        assert not final.exists()
        journal = p/run['run_dir']/'checkpoint/journal.jsonl'
        raw = journal.read_bytes()
        before = hashlib.sha256(raw).hexdigest()
        # Credential-first processing stays remote; the public report has no raw lines.
        safe = SECRET.sub('[REDACTED]', raw.decode('utf-8'))
        nodes = [json.loads(line) for line in safe.splitlines() if line.strip()][1:]
        kinds = Counter()
        for node in nodes:
            assert type(node['exit_code']) is int and node['exit_code'] == 1 and node['is_buggy'] is True
            text = '\n'.join(node['_term_out'])
            kinds[classify(text)] += 1
        receipts = []
        for batch in work['batches']:
            if batch['run_id'] != run['run_id']:
                continue
            ledger = p/batch['ledger']
            assert hashlib.sha256(ledger.read_bytes()).hexdigest() == batch['ledger_sha256']
            with closing(sqlite3.connect(ledger.as_uri()+'?mode=ro', uri=True)) as db:
                payload, digest = db.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchone()
            assert hashlib.sha256(payload.encode()).hexdigest() == digest
            data = json.loads(payload)
            receipts.extend(data['task_calls'])
        assert len(nodes) == len(receipts) == 5
        assert all(c['state'] == 'returned' and c['execution_metadata']['exit_code_reported'] == 1 for c in receipts)
        assert sum(c['execution_metadata']['timed_out_reported'] for c in receipts) == kinds['execution_timeout']
        assert hashlib.sha256(journal.read_bytes()).hexdigest() == before
        evidence[str(journal.relative_to(p))] = before
        totals.update(kinds)
        rows.append(dict(run_id=run['run_id'], task=run['task'], seed=run['seed'], arm=run['arm'],
            process_completed=True, final_event_present=False, task_calls=len(receipts),
            exit_zero_task_calls=0, failure_categories=dict(kinds)))
    with closing(sqlite3.connect((p/'paid.sqlite').as_uri()+'?mode=ro', uri=True)) as db:
        calls = db.execute('SELECT scope,held,cost,state FROM calls').fetchall()
    assert all(held == cost and state == 'settled' for _,held,cost,state in calls)
    cost_nano = sum(c[2] for c in calls)
    assert cost_nano == round(work['api_budget']['settled_usd'] * 10**9)
    result = dict(role='independent_failed_matrix_closeout', utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        jobs=elapsed, processes_completed=len(rows), comparable_pairs=0, task_calls=sum(totals.values()),
        exit_zero_task_calls=0, final_events=0, failure_categories=dict(totals),
        api_calls=len(calls), route_calls=sum(c[0]=='route' for c in calls),
        api_cost_usd=str(Decimal(cost_nano)/10**9), unresolved_api_calls=0,
        allocation_gpu_hours=sum(elapsed.values())*2/3600,
        rows=rows, evidence_sha256=evidence,
        verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        limitations=['No final score can be assigned; missing is not zero.',
            'Failure classes are diagnostic and not a proof that fixing one API makes a whole program succeed.',
            'No partial submission selected, task replay, GPU or API generation was performed.'])
    with (p/'post-closeout-20260912/independent-failure-verification.json').open('x') as f:
        json.dump(result,f,indent=2); f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','evidence_sha256')}))


if __name__ == '__main__':
    main()
