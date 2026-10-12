"""Outcome-blindly specified secondary checks; frozen main gate is unchanged.

No raw code, score, prediction, or candidate identity is exported. Exact code
duplicates do not establish equal prompts, equal predictions, or a seed cause.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from feedback_parent_mechanism_20261012 import analyze_events


def duplicates(events):
    used = [e for e in events if e['event'] == 'parent_used']
    outputs = Counter(e['child'] for e in used)
    same_context = Counter((e['run'], e['parent'], e['child']) for e in used)
    return dict(completed_generations=len(used), unique_generated_code=len(outputs),
                repeated_code_calls=sum(n-1 for n in outputs.values()),
                same_run_parent_child_repeat_calls=sum(n-1 for n in same_context.values()))


def main(root, output):
    root, output = Path(root), Path(output)
    read = lambda p: json.loads(p.read_text())
    assert read(root/'closed.json')['complete'] == 48
    plan = read(root/'plan.json')
    pools = []
    for b in range(6):
        rows = [r for r in plan['schedule'] if r['block'] == b]
        events = [json.loads(s) for s in (root/f'generation-{b}/events.jsonl').read_text().splitlines()]
        by_task = {}
        for task in sorted({r['task'] for r in rows}):
            subset = [r for r in rows if r['task'] == task]
            runs = {r['index'] for r in subset}
            es = [e for e in events if e['run'] in runs]
            by_task[task] = dict(**analyze_events(es, subset, rows[0]['arm']), **duplicates(es))
        pools.append(dict(block=b, arm=rows[0]['arm'], by_task=by_task))
    value = dict(plan_sha256=hashlib.sha256((root/'plan.json').read_bytes()).hexdigest(),
                 analyzer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 helper_sha256=hashlib.sha256(Path(__file__).with_name('feedback_parent_mechanism_20261012.py').read_bytes()).hexdigest(),
                 secondary_only=True, quality_gate_unchanged=True, pools=pools,
                 limitation='Exact-code repetition is descriptive, not proof of identical requests or fixed-seed degeneration; task-wise mechanism counts do not identify causal mediation.')
    with output.open('x') as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)
    print(json.dumps(value, allow_nan=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('root'); p.add_argument('output')
    a = p.parse_args(); main(a.root, a.output)
