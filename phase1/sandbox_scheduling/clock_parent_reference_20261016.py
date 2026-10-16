"""Closed18770 original parent receipts, no new replay outcomes or code export.

Secondary decision-relevance diagnostic. Parent scores are original development
receipts, NOT parent re-executions under each load. No new success gate.
"""
import hashlib
import json
from pathlib import Path
import re

D = Path('/research/d7/spc/yzyang4/scheduling-pooling-20261016-v3')
P = D.parent / 'clock-rank-20261016-v1/plan.json'
PIN = '4c22748699952da0b79bf862e1db5e785b7d2a9fb951bb26ee9c21be47ca3306'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def reference(events, program):
    used = [e for e in events if e['event'] == 'parent_used'
            and e['run'] == program['source_episode'] and e['child'] == program['code_sha256']]
    if len(used) != 1:
        return dict(identified=False, reason='parent_link_not_unique', matches=len(used))
    u = used[0]
    admits = [e for e in events if e['event'] == 'admitted' and e['key'] == u['key']]
    assert len(admits) == 1
    a = admits[0]
    assert a['role'] == 'improve' and a['parent'] == u['parent']
    assert a['run'] == u['run'] and a['time'] <= u['time']
    task = program['task']
    record = a['snapshot']['archive'][task][u['parent']]
    assert a['snapshot']['sign'][task] in (-1, 1)
    return dict(identified=True, parent_code_sha256=u['parent'], parent_score=record['metric'],
                parent_order=record['order'], sign=a['snapshot']['sign'][task],
                parent_receipt_event_sha256=digest(json.dumps(a, sort_keys=True).encode()))


def main():
    raw = P.read_bytes()
    assert digest(raw) == PIN
    plan = json.loads(raw)
    assert len(plan['programs']) == 4
    rows = []
    for k, p in enumerate(plan['programs']):
        path = D / f"generation-{p['source_episode']//8}/events.jsonl"
        raw = path.read_bytes()
        assert not re.search(rb'(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})', raw), 'credential shape, no export'
        events = [json.loads(line) for line in raw.splitlines() if line]
        rows.append(dict(program=k, task=p['task'], source_episode=p['source_episode'],
                         source_candidate=p['source_candidate'], code_sha256=p['code_sha256'],
                         source_events_sha256=digest(raw), **reference(events, p)))
    print(json.dumps(dict(rank_plan_sha256=PIN, rows=rows,
        boundary='Original known-DEV parent receipt only; no parent rerun, no new outcome or code read, secondary analysis not a success gate.'), sort_keys=True))


if __name__ == '__main__':
    main()
