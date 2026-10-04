"""Closed-trial returned-failure taxonomy without raw stdout or score values."""
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


def main():
    assert hashlib.sha256((R/'plan.json').read_bytes()).hexdigest() == PLAN
    assert (R/'all-closed.json').exists() and read(R/'closed.json')['service_closed']
    rows = []
    for s in read(R/'plan.json')['schedule']:
        for step in range(5):
            root = R/f'episode-{s["index"]}'/f'action-{step}'
            if not (root/'result.json').exists():
                continue
            result = read(root/'result.json')
            if result['execution_success']:
                continue
            node = read(root/'node.private.json')
            errors = re.findall(r'(?m)^((?:[A-Za-z]+Error|[A-Za-z]+Exception):[^\n]*)', node['terminal'])
            row = dict(index=s['index'], task=s['task'], arm=s['arm'], step=step,
                timed_out=result['timed_out'], exit_code=result['exit_code'],
                execution_seconds=result['execution_wall_seconds'], elapsed_seconds=result['elapsed_seconds'],
                code_sha256=result['code_sha256'], error_lines=errors,
                result_sha256=hashlib.sha256((root/'result.json').read_bytes()).hexdigest())
            assert not SECRET.search(json.dumps(row).encode())
            rows.append(row)
    value = dict(plan_sha256=PLAN, returned_failures=rows,
        boundary='Only returned execution failures. Does not include format rejections, unstarted actions or reconstruction failures. Error text is evidence of this run, not proof of the agent rationale.')
    with (R/'readout-v1/returned-errors.json').open('x') as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)
    print(json.dumps(value))


if __name__ == '__main__':
    main()
