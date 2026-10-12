"""Secondary structural mediator analysis, specified before outcome readout.

No policy import, no changes to the frozen quality gate, no counterfactual
quality estimates. Permission-idle seconds are NOT physical GPU-idle seconds.
"""
import argparse
import hashlib
import json
from pathlib import Path


def analyze_events(events, schedule, arm):
    tasks = {r['index']: r['task'] for r in schedule}
    warm = {}
    for e in events:
        if e['event'] == 'warm_start':
            task = tasks[e['run']]
            if task in warm:
                assert warm[task] == e['code_sha256']
            warm[task] = e['code_sha256']
    assert set(warm) == set(tasks.values())
    archive = {t: {h} for t, h in warm.items()}
    pending, waiting, active = {}, {}, {}
    nonwarm, completed = set(), set()
    overlap, changed = 0, 0
    seconds = {t: 0.0 for t in warm}
    permits = {t: 0.0 for t in warm}
    last = None
    # All hosts in a pool are the same physical node. Event timestamps are
    # taken before append; order by timestamp, retaining ties' original order.
    for e in sorted(events, key=lambda x: x['time']):
        now = e['time']
        if last is not None and arm == 'feedback_gate':
            for task in warm:
                requests = [r for r in waiting.values() if r['task'] == task]
                free = 2 - sum(r['task'] == task for r in active.values())
                busy = {p for t, p in pending.values() if t == task}
                # If completion/debug can be served, this is not a mandatory
                # idle interval imposed by the parent rule.
                forced = requests and all(r['role'] == 'improve' for r in requests)
                forced = forced and free > 0 and not archive[task] - busy
                if forced:
                    seconds[task] += now - last
                    permits[task] += (now - last) * min(free, len(requests))
        last = now
        kind, key = e['event'], e.get('key')
        if kind == 'queued':
            r = e['request']; assert r['key'] not in waiting
            waiting[r['key']] = r
        elif kind == 'admitted':
            r = waiting.pop(key); active[key] = r
            if r['role'] == 'improve':
                task, parent = r['task'], e['parent']
                assert parent in archive[task]
                same = (task, parent) in pending.values()
                if arm == 'feedback_gate':
                    assert not same
                overlap += int(same)
                changed += int(e['alternatives']['pending_ucb'] != parent)
                pending[key] = (task, parent)
                if parent != warm[task]:
                    nonwarm.add(key)
        elif kind == 'released':
            active.pop(key)
        elif kind == 'cancelled':
            waiting.pop(key)
        elif kind == 'round_complete':
            if key is not None:
                pending.pop(key); completed.add(key)
            if e['valid']:
                archive[tasks[e['run']]].add(e['code_sha256'])
        elif kind == 'abandoned':
            pending.pop(key, None)
        elif kind not in ('warm_start', 'parent_used', 'feedback_wait'):
            raise ValueError('unknown structural event')
    assert not pending and not active and not waiting
    return dict(same_parent_pending_admissions=overlap,
                chosen_parent_differs_from_pending_ucb=changed,
                completed_nonwarm_parent=len(nonwarm & completed),
                mandatory_wait_task_seconds=seconds,
                withheld_generation_permit_seconds=permits,
                limitation='Descriptive state intervals, not physical GPU idle, feedback causal mediation, or counterfactual scores.')


def main(root, output):
    root, output = Path(root), Path(output)
    read = lambda p: json.loads(p.read_text())
    assert read(root/'closed.json')['complete'] == 48
    plan = read(root/'plan.json')
    result = []
    for b in range(6):
        rows = [r for r in plan['schedule'] if r['block'] == b]
        events = [json.loads(s) for s in (root/f'generation-{b}/events.jsonl').read_text().splitlines()]
        result.append(dict(block=b, arm=rows[0]['arm'], **analyze_events(events, rows, rows[0]['arm'])))
    payload = dict(source_commit=plan['source_commit'],
                   plan_sha256=hashlib.sha256((root/'plan.json').read_bytes()).hexdigest(),
                   analyzer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   secondary_only=True, quality_gate_unchanged=True, pools=result)
    with output.open('x') as f:
        json.dump(payload, f, indent=2, sort_keys=True, allow_nan=False)
    print(json.dumps(payload, allow_nan=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('root'); p.add_argument('output')
    a = p.parse_args(); main(a.root, a.output)
