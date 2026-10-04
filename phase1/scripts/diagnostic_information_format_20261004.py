"""Describe all fixed-trial output-format failures; never reinterpret outcomes.

This is a read-only post-closure audit, not a lenient replacement parser, rescue
execution, or success-conditioned analysis. Token cap is not a finish-reason log.
"""
import ast
import collections
import hashlib
import json
from pathlib import Path
import re

R = Path('/research/d7/spc/yzyang4/diagnostic-information-20261004-v1')
PLAN = '63322ce2f5e38ac22c2a98b2c7bae5fa27334c4d5f3052297938418c26627679'
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')


def read(path):
    raw = path.read_bytes()
    assert not SECRET.search(raw), 'credential shape; no content emitted'
    return json.loads(raw)


def classify(raw, step):
    modes = re.findall(r'(?m)^\s*(CHECK|SOLUTION)\s*$', raw.split('```', 1)[0])
    parts = re.findall(r'```python\s*\n(.*?)```', raw, re.S)
    reasons = []
    if len(modes) != 1:
        reasons.append('standalone_mode_count_not_one')
    if len(parts) != 1:
        reasons.append('complete_python_block_count_not_one')
    if raw.count('```') != 2:
        reasons.append('fence_count_not_two')
    if step == 4 and len(modes) == 1 and modes[0] != 'SOLUTION':
        reasons.append('final_call_not_solution')
    if not reasons:
        try:
            ast.parse(parts[0])
        except SyntaxError:
            reasons.append('python_syntax_error')
    return reasons


def main():
    assert hashlib.sha256((R/'plan.json').read_bytes()).hexdigest() == PLAN
    assert (R/'all-closed.json').exists() and read(R/'closed.json')['service_closed']
    rows = []
    for s in read(R/'plan.json')['schedule']:
        for step in range(1, 5):
            root = R/f'episode-{s["index"]}'/f'action-{step}'
            row = dict(index=s['index'], task=s['task'], arm=s['arm'], seed=s['seed'], step=step,
                requested=(root/'request.private.json').exists(), generated=(root/'generation.private.json').exists())
            if row['generated']:
                generation = read(root/'generation.private.json')
                raw = generation['response']
                reasons = classify(raw, step)
                receipt = read(root/'format.json')
                assert receipt['status'] == ('REJECT' if reasons else 'PASS')
                row.update(format_status=receipt['status'], reasons=reasons,
                    response_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                    prompt_tokens=generation.get('usage', {}).get('prompt_tokens'),
                    completion_tokens=generation.get('usage', {}).get('completion_tokens'),
                    recorded_completion_at_4096=generation.get('usage', {}).get('completion_tokens') == 4096)
            rows.append(row)
    assert len(rows) == 48
    counts = collections.Counter(reason for r in rows for reason in r.get('reasons', []))
    value = dict(plan_sha256=PLAN, script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        assigned=12, possible_calls=48, requested=sum(r['requested'] for r in rows),
        generated=sum(r['generated'] for r in rows), rejected=sum(r.get('format_status') == 'REJECT' for r in rows),
        nonexclusive_reasons=dict(counts), rows=rows,
        boundary='All48 possible call positions retained. No alternative parsing, execution, score changes or exclusion. Reasons can overlap. Completion tokens equal4096 indicate a recorded cap, not proof of truncation; finish_reason was not retained. Format compliance is not ML efficacy.')
    destination = R/'readout-v1/format-audit.json'
    with destination.open('x') as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)
    print(json.dumps({k:v for k,v in value.items() if k != 'rows'}))


if __name__ == '__main__':
    main()
