"""Closed development debug edges; not parallel-node repetition or efficacy."""
from collections import Counter
import json
from pathlib import Path

from forets_environment_build_20260912 import read, write, encode, sha
from audit_closed_error_families_20260913 import BASE, SECRET, classify
from inspect_closed_error_recurrence_20260913 import SUMMARY, SUMMARY_SHA


def edges(nodes):
    bystep = {n['step']: n for n in nodes}
    if len(bystep) != len(nodes):
        raise ValueError('duplicate saved step')
    rows = []
    for child in nodes:
        if 'debug' not in child.get('operators_used', []) or child.get('exec_time') is None:
            continue
        parents = child.get('parents')
        if not isinstance(parents, list) or len(parents) != 1:
            raise ValueError('debug must have exactly one saved parent step')
        step = parents[0]
        if not isinstance(step, int) or step >= child['step']:
            raise ValueError('parent must precede child')
        parent = bystep.get(step)
        if parent is None:
            rows.append(dict(parent_step=step, child_step=child['step'], parent_missing=True))
            continue
        if parent.get('exec_time') is None:
            raise ValueError('debug parent was not executed')
        pf = classify(parent.get('term_out') or '')[1] if parent.get('exit_code') not in (None, 0) else []
        cf = classify(child.get('term_out') or '')[1] if child.get('exit_code') not in (None, 0) else []
        rows.append(dict(parent_step=step, child_step=child['step'], parent_missing=False,
            parent_families=pf, child_families=cf, same_failed_families=sorted(set(pf) & set(cf)),
            code_bytes_changed=sha(parent['code'].encode()) != sha(child['code'].encode()),
            child_exit_nonzero=child.get('exit_code') not in (None, 0),
            child_valid_submission=(child.get('metric_info') or {}).get('valid_submission') == 1))
    return rows


def main():
    source = read(SUMMARY, SUMMARY_SHA)
    rows = []; proofs = []; totals = Counter()
    for proof in source['proof']:
        path = BASE / proof['root'] / 'runs' / proof['run_id'] / 'checkpoint/journal.jsonl'
        raw = path.read_bytes()
        if sha(raw) != proof['journal_sha256']:
            raise ValueError('closed journal drift')
        safe = SECRET.sub('[REDACTED]', raw.decode())
        found = edges([json.loads(line) for line in safe.splitlines()])
        for row in found:
            row.update(root=proof['root'], run_id=proof['run_id'])
            rows.append(row); totals['executed_debug_children'] += 1
            if row['parent_missing']:
                totals['missing_parent'] += 1
                continue
            totals['observed_edges'] += 1
            totals['nonzero_debug_children'] += int(row['child_exit_nonzero'])
            totals['valid_debug_children'] += int(row['child_valid_submission'])
            totals['recurrent_same_family_edges'] += bool(row['same_failed_families'])
            for family in row['parent_families']:
                totals['parent_family:' + family] += 1
            for family in row['same_failed_families']:
                totals['recurrent_family:' + family] += 1
        if sha(path.read_bytes()) != proof['journal_sha256']:
            raise ValueError('journal changed while reading')
        proofs.append({k: proof[k] for k in ('root', 'run_id', 'journal_sha256')})
    result = dict(role='closed_debug_parent_child_error_recurrence_not_memory_efficacy',
        source_summary_sha256=SUMMARY_SHA, totals=dict(totals), rows=rows, proofs=proofs,
        script_sha256=sha(Path(__file__).read_bytes()),
        limitations='Only saved executed debug children with observed parent links; journals missing in five of 32 runs. Correlated edges from heterogeneous protocols. Same error family is not identical root cause. This does not establish the model attended to the error or that memory fixes it.')
    digest = write(SUMMARY.with_name('closed-debug-error-edges.json'), encode(result))
    print(json.dumps(dict(sha256=digest, totals=dict(totals))))


if __name__ == '__main__':
    main()
