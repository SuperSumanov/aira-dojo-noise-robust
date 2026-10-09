"""Pre-outcome secondary diagnostic: actual dev gains, never scheduling effects.

Closed exposure-v1 only, all4 retained. External scorer receipts ground every
valid return. Parent-child and incumbent comparisons are descriptive, not a
randomized control, independent replication, test gain, or prior-gate override.
No raw code, labels, predictions, generation or node identities exported.
"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from lifecycle_pilot import read, write, sha
from live_readout import finite, ground_scores, lines

PLAN = 'b78c0101dec77c6c919a9f7669a07e4c6a5f377a20437e301c0fb8025ab047aa'
ROOT = Path('/research/d7/spc/yzyang4/scheduling-live-exposure-20261009-v1')
ORIENTATION = {'random-acts-of-pizza': 1, 'spooky-author-identification': -1}


def summarize(nodes, candidates, sign):
    if sign not in (-1, 1):
        raise ValueError('known metric direction required')
    cursor = 0
    mapped = {}
    incumbent = None
    rows = []
    unmatched = 0
    for node in nodes:
        names = node.get('operators_used', [])
        if not names:
            continue
        role = names[0]
        if role not in ('draft', 'debug', 'improve'):
            raise ValueError('unknown operator')
        step = node['step']
        if step in mapped:
            raise ValueError('duplicate journal step')
        code = node.get('code')
        pin = hashlib.sha256(code.encode()).hexdigest() if isinstance(code, str) else None
        found = next((i for i in range(cursor, len(candidates))
                      if candidates[i]['code_sha256'] == pin), None)
        if found is None:
            unmatched += 1
            mapped[step] = None
            continue
        cursor = found + 1
        candidate = candidates[found]
        score = None
        if candidate['valid']:
            if not finite(candidate.get('score')):
                raise ValueError('finite external score required')
            if node.get('metric') != candidate['score'] or node.get('metric_maximize') != (sign == 1):
                raise ValueError('native/external metric or direction mismatch')
            score = sign * Decimal(str(candidate['score']))
        if role == 'improve':
            parents = node.get('parents', [])
            parent = mapped.get(parents[0]) if len(parents) == 1 else None
            parent_delta = score - parent if score is not None and parent is not None else None
            incumbent_delta = score - incumbent if score is not None and incumbent is not None else None
            rows.append(dict(valid=score is not None, parent_grounded=parent is not None,
                             parent_oriented_delta=None if parent_delta is None else str(parent_delta),
                             incumbent_oriented_delta=None if incumbent_delta is None else str(incumbent_delta),
                             returned_seconds=candidate['elapsed_seconds']))
        mapped[step] = score
        if score is not None:
            incumbent = score if incumbent is None else max(incumbent, score)
    deltas = [Decimal(r['parent_oriented_delta']) for r in rows if r['parent_oriented_delta'] is not None]
    return dict(unmatched_recorded_nodes=unmatched, completed_improve_attempts=len(rows),
                valid_improve_returns=sum(r['valid'] for r in rows), paired_valid_parent_edges=len(deltas),
                better_than_parent=sum(d > 0 for d in deltas), tied_with_parent=sum(d == 0 for d in deltas),
                worse_than_parent=sum(d < 0 for d in deltas),
                strict_incumbent_improvements=sum(r['incumbent_oriented_delta'] is not None
                                                and Decimal(r['incumbent_oriented_delta']) > 0 for r in rows),
                improve_rows=rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root
    if root != ROOT or sha(root/'plan.json') != PLAN:
        raise ValueError('exact fresh development batch only')
    primary = read(root/'exposure-readout-v1.json')
    if primary['plan_sha256'] != PLAN:
        raise ValueError('primary readout required first')
    plan = read(root/'plan.json')
    for name, pin in plan['files'].items():
        if sha(root/name) != pin:
            raise ValueError('frozen source drift')
    rows = []
    for row in plan['schedule']:
        ep = root/f'episode-{row["index"]}'
        candidates = sorted([read(f) for f in ep.glob('candidate-*.json') if '.private.' not in f.name],
                            key=lambda c: c['elapsed_seconds'])
        if any(c['elapsed_seconds'] > 3000 for c in candidates):
            raise ValueError('late returns retained in primary; secondary refused')
        end = read(ep/'finished.json') if (ep/'finished.json').exists() else {}
        grounded = ground_scores(end, candidates, [read(f)['receipt'] for f in ep.glob('scored-*.json')])
        if not grounded:
            raise ValueError('external grounding failed')
        own = next(r for r in primary['rows'] if r['index'] == row['index'])
        diagnostic = summarize(lines(ep/'checkpoint/journal.jsonl'), candidates, ORIENTATION[row['task']])
        rows.append(dict(**row, complete=own['complete'], **diagnostic))
    result = dict(plan_sha256=PLAN, primary_sha256=sha(root/'exposure-readout-v1.json'),
                  analysis_sha256=sha(Path(__file__)), assigned=4, rows=rows,
                  boundary='Secondary exploratory opportunity diagnostic, specified before reading this batch outcomes. '
                  'Within-run improvements are dependent and dev-selected; no CI treating edges as independent. '
                  'No same-budget comparator, model/scheduler superiority, generalization or final-test claim. '
                  'Invalid, unmatched and incomplete cases retained; no previous gate changed.')
    destination = root/'opportunity-readout-v1.json'
    write(destination, result)
    print(json.dumps(dict(sha256=sha(destination), rows=rows)))


if __name__ == '__main__':
    main()
