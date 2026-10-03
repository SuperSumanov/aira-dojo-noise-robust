"""Closed-only safe aggregate export; no raw code, replies, labels or predictions.

Secondary summaries are descriptive and never change the frozen primary gate.
Sources are retained remotely; destination creation is exclusive.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import re
import statistics
from pathlib import Path

R = Path('/research/d7/spc/yzyang4/executable-evidence-20261004-v1')
PLAN = 'f5aba6d06b20a1c4037abc52c373842bae70f6672d3a2ac7b20c8bb3fc82dd3c'
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{10,}|hf_[a-z0-9]{15,}|gh[pousr]_[a-z0-9]{15,}|Bearer\s+\S{12,}|(?:api[_-]?key|password|secret|token)\s*[=:]\s*[\x22\x27]?[a-z0-9_./+-]{12,})')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    raw = path.read_bytes()
    assert not SECRET.search(raw), 'credential shape; no content emitted'
    return json.loads(raw)


def encode(obj):
    raw = (json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    assert not SECRET.search(raw), 'unsafe aggregate; no content emitted'
    return raw


def descriptions(summary, action_rows, verification):
    score_hash = {(x['index'], x['step']): x['submission_sha256']
                  for x in verification['score_checks']}
    groups = []
    for task in sorted({r['task'] for r in summary['runs']}):
        for arm in 'ABC':
            runs = [r for r in summary['runs'] if r['task'] == task and r['arm'] == arm]
            assert len(runs) == 3
            ids = {r['index'] for r in runs}
            actions = [a for a in action_rows if int(a['index']) in ids]
            gains = [r['gain'] for r in runs if r['gain'] is not None]
            hashes = [score_hash[(r['index'], r['selected_step'])] for r in runs
                      if r['selected_step'] is not None]
            group = dict(task=task, arm=arm, assigned=3, valid_initials=len(gains),
                         gains=gains, median_gain=statistics.median(gains) if gains else None,
                         sample_variance=statistics.variance(gains) if len(gains) > 1 else None,
                         retained_prediction_unique=len(set(hashes)), retained_prediction_total=len(hashes))
            for field in ('calls_attempted', 'calls_completed', 'format_rejects',
                          'unreturned_executions', 'successful_checks', 'valid_candidates'):
                group[field] = sum(r[field] for r in runs)
            for field in ('generation_seconds', 'execution_seconds', 'replay_seconds',
                          'prompt_tokens', 'completion_tokens'):
                values = [float(a[field]) for a in actions if a[field] != '']
                group[field + '_recorded_sum'] = sum(values)
                group[field + '_recorded_count'] = len(values)
            groups.append(group)
    return dict(groups=groups, scope='Descriptive only, not a new gate or post-hoc arm selection. '
                'Time columns are recorded components, not assumed disjoint or complete; allocation '
                'GPU hours remain primary cost. Unique prediction bytes do not imply independent trials. '
                'Generation seeds vary; fixed parent, training RNG and development query set are shared.')


def export():
    assert digest((R/'plan.json').read_bytes()) == PLAN
    assert read(R/'closed.json')['service_closed']
    out = R/'readout-v1'
    summary = read(out/'summary.json')
    verification = read(out/'verification.json')
    assert verification['status'] == 'PASS'
    assert verification['summary_sha256'] == digest((out/'summary.json').read_bytes())
    sensitivity = read(out/'conditional-sensitivity.json')
    assert sensitivity['summary_sha256'] == verification['summary_sha256']
    mechanism = read(R/'mechanism-review.json')
    assert mechanism['plan_sha256'] == PLAN and mechanism['assigned'] == 18
    assert mechanism['reviewed_before_numeric_readout'] is True
    payload = {}
    for name in ('runs.csv', 'actions.csv', 'pairs.csv'):
        raw = (out/name).read_bytes()
        assert digest(raw) == summary['files'][name] and not SECRET.search(raw)
        payload[name] = raw
    action_rows = list(csv.DictReader(io.StringIO(payload['actions.csv'].decode())))
    plan = read(R/'plan.json')
    payload['plan.aggregate.json'] = encode({k:v for k,v in plan.items() if k not in ('files', 'starts')})
    payload['summary.aggregate.json'] = encode({k:v for k,v in summary.items() if k != 'input_hashes'})
    payload['verification.json'] = encode(verification)
    payload['conditional-sensitivity.json'] = encode(sensitivity)
    payload['mechanism-review.json'] = encode(mechanism)
    payload['descriptive-resources.json'] = encode(descriptions(summary, action_rows, verification))
    for name in ('cpu.json', 'transport-loop-cpu.json', 'analysis-freeze.json',
                 'readout-freeze.json', 'mechanism-freeze.json', 'sensitivity-freeze.json', 'launch.json'):
        payload[name] = encode(read(R/name))
    receipt = dict(plan_sha256=PLAN, full_summary_sha256=verification['summary_sha256'],
                   exporter_sha256=digest(Path(__file__).read_bytes()),
                   files={name:digest(raw) for name,raw in payload.items()},
                   excluded=['raw candidate code', 'model replies', 'labels', 'predictions', 'credentials'],
                   scope='Only this closed developer batch; all18 assigned retained. No protected cohorts.')
    payload['export-receipt.json'] = encode(receipt)
    dest = R/'safe-export-v1'
    dest.mkdir(mode=0o700)
    for name, raw in payload.items():
        with (dest/name).open('xb') as f:
            f.write(raw)
    assert all(digest((dest/name).read_bytes()) == digest(raw) for name,raw in payload.items())
    print(json.dumps(dict(status='EXPORTED', directory=str(dest), files=len(payload),
                          receipt_sha256=digest(payload['export-receipt.json']))))


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['export'])
    parser.parse_args()
    export()
