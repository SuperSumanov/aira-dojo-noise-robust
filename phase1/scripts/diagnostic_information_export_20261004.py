"""Export the closed developer trial's bounded aggregate evidence only.

No new score calculation or arm selection. Raw code, messages, labels and
prediction files remain remote. Reuses the earlier reviewed export contract.
"""
import hashlib
import json
import os
import re
from pathlib import Path

R = Path('/research/d7/spc/yzyang4/diagnostic-information-20261004-v1')
PLAN = '63322ce2f5e38ac22c2a98b2c7bae5fa27334c4d5f3052297938418c26627679'
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{10,}|hf_[a-z0-9]{15,}|gh[pousr]_[a-z0-9]{15,}|Bearer\s+\S{12,}|(?:api[_-]?key|password|secret|token)\s*[=:]\s*[\x22\x27]?[a-z0-9_./+-]{12,})')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    raw = path.read_bytes()
    assert not SECRET.search(raw), 'credential shape; no content emitted'
    return json.loads(raw)


def encode(value):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
    assert not SECRET.search(raw), 'unsafe aggregate; no content emitted'
    return raw


def main():
    assert sha((R/'plan.json').read_bytes()) == PLAN
    assert read(R/'closed.json')['service_closed'] and (R/'all-closed.json').exists()
    out = R/'readout-v1'
    summary = read(out/'summary.json')
    verification = read(out/'verification.json')
    sensitivity = read(out/'conditional-sensitivity.json')
    assert verification['status'] == 'PASS'
    assert verification['summary_sha256'] == sha((out/'summary.json').read_bytes())
    assert sensitivity['summary_sha256'] == verification['summary_sha256']
    assert len(summary['runs']) == 12 and all(r['closed'] for r in summary['runs'])
    review = read(R/'mechanism-review.json')
    assert review['plan_sha256'] == PLAN and review['assigned'] == 12
    assert review['summary_sha256'] == verification['summary_sha256']
    payload = {}
    for name in ('runs.csv', 'actions.csv', 'pairs.csv'):
        raw = (out/name).read_bytes()
        assert sha(raw) == summary['files'][name] and not SECRET.search(raw)
        payload[name] = raw
    plan = read(R/'plan.json')
    payload['plan.aggregate.json'] = encode({k:v for k,v in plan.items() if k not in ('files', 'starts')})
    payload['summary.aggregate.json'] = encode({k:v for k,v in summary.items() if k != 'input_hashes'})
    payload['verification.json'] = encode(verification)
    payload['conditional-sensitivity.json'] = encode(sensitivity)
    payload['mechanism-review.json'] = encode(review)
    for name in ('format-audit.json', 'returned-errors.json', 'posthoc-available-pairs.json'):
        value = read(out/name)
        assert value['plan_sha256'] == PLAN
        payload[name] = encode(value)
    for name in ('cpu.json', 'transport-loop-cpu.json', 'context-preflight.json',
                 'analysis-freeze.json', 'readout-freeze.json', 'inspection-freeze.json',
                 'sensitivity-freeze.json', 'launch.json', 'service-ready.json'):
        payload[name] = encode(read(R/name))
    receipt = dict(plan_sha256=PLAN, full_summary_sha256=verification['summary_sha256'],
        exporter_sha256=sha(Path(__file__).read_bytes()), files={n:sha(raw) for n,raw in payload.items()},
        excluded=['raw candidate code', 'model replies', 'labels', 'predictions', 'credentials'],
        scope='All12 assigned retained; only this closed authorized developer batch. Protected cohorts remain sealed.')
    payload['export-receipt.json'] = encode(receipt)
    dest = R/'safe-export-v1'
    dest.mkdir(mode=0o700)
    for name, raw in payload.items():
        with (dest/name).open('xb') as f:
            f.write(raw)
    assert all(sha((dest/n).read_bytes()) == sha(raw) for n,raw in payload.items())
    print(json.dumps(dict(status='EXPORTED', directory=str(dest), files=len(payload),
                         receipt_sha256=sha(payload['export-receipt.json']))))


if __name__ == '__main__':
    os.umask(0o077)
    main()
