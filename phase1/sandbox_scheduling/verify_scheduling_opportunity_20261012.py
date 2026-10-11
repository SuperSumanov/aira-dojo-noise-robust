"""Independent closed-receipt checks; no imports from the screen implementation."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

BASE = Path('/research/d7/spc/yzyang4')
ROOTS = {'17592': 'scheduling-image-live-2plus4-20261011-v3',
         '17656': 'scheduling-image-generation-deadline-20261011-v1',
         '17670': 'scheduling-image-deadline-replication-20261012-v1'}


def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def lines(p): return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def verify(result):
    checks = []; choices = []
    assert len(result['batches']) == len(ROOTS)
    for batch in result['batches']:
        root = BASE / ROOTS[batch['job']]
        assert sha(root/'plan.json') == batch['plan_sha256']
        assert sha(root/'readout-v1/summary.json') == batch['original_summary_sha256']
        plan = read(root/'plan.json'); kinds = {}; total = Counter()
        for row in batch['rows']:
            ep = root / f"episode-{row['index']}"
            events = lines(ep/'events.jsonl')
            for e in events:
                if e['event'] == 'operation_ready':
                    kinds[f"{row['index']}:{e['operation']}"] = e['kind']
            nodes = [n for n in lines(ep/'checkpoint/journal.jsonl') if n.get('operators_used')]
            count = Counter(n['operators_used'][0] for n in nodes)
            assert all(count[k] == row['native_exposure'][k] for k in ('draft','debug','improve'))
            total.update(count)
            valid = [c for p in ep.glob('candidate-*.json') if '.private.' not in p.name
                     for c in [read(p)] if c['valid'] and c['elapsed_seconds'] <= plan['run_seconds']]
            assert len(valid) == row['valid_returns']
        for q in batch['queues']:
            directory = root / f"queue-{q['block']}-{q['lane']}"
            path = directory/'events.jsonl'; es = lines(path) if path.exists() else []
            requested = []; admitted = set(); ended = set(); scarce = candidate = n = 0
            for e in es:
                key = e['key']; action = e['event']; width = q['width']
                waiting = [k for k in requested if k not in admitted | ended]
                running = admitted - ended
                if action == 'queued':
                    assert key not in requested
                    requested.append(key)
                elif action == 'admitted':
                    assert waiting[0] == key and len(running) < width
                    free = width - len(running)
                    scarce += len(waiting) > free
                    candidate += sum(kinds[k] == 'candidate' for k in waiting) > free
                    if len(waiting) > free:
                        choices.append(dict(job=batch['job'], block=q['block'], lane=q['lane'],
                            ordered_ready_kinds=[kinds[k] for k in waiting], free_permits=free,
                            actual_kind=kinds[key]))
                    admitted.add(key); n += 1
                elif action in ('released','queue_cancelled'):
                    assert key in (running if action == 'released' else waiting)
                    ended.add(key)
                else: raise ValueError('unknown event')
            state = read(directory/'state.json')
            assert set(requested) == ended == set(state['finished'])
            assert not state['active'] and not state['queue']
            assert (scarce, candidate, n) == (q['scarce_subset_choices'],q['candidate_subset_choices'],q['admissions'])
        checks.append(dict(job=batch['job'], runs=len(batch['rows']), queues=len(batch['queues']),
            journal_role_counts=dict(total), all_checks_pass=True))
    return dict(checks=checks, scarce_choice_contexts=choices,
        boundary='Independent structural/role verification only; no counterfactual utility or new quality endpoint.')


if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('input',type=Path); p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(); result=verify(read(args.input))
    result.update(screen_sha256=sha(args.input),verifier_sha256=sha(Path(__file__)))
    with args.output.open('x') as f: json.dump(result,f,sort_keys=True,indent=2); f.write('\n')
    print(json.dumps(result))
