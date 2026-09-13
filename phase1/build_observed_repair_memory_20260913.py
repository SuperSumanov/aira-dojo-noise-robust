"""Outcome-independent *old development* repair inventory, not a new method.

Retain every observed failed-parent/successful-debug transition. Store full
code only in a new remote private directory; public export has hashes/counts.
No new memory trial is an input and no final numerical score selects examples.
"""
import ast
from collections import Counter
import difflib
import json
import math
import os
from pathlib import Path
import tempfile
from forets_environment_build_20260912 import read, write, encode, sha
from audit_closed_error_families_20260913 import BASE, SECRET, classify
from inspect_closed_error_recurrence_20260913 import SUMMARY, SUMMARY_SHA
from audit_debug_error_edges_20260913 import edges
from audit_closed_measurement_gaps_20260913 import submission_validity


def eligible_transitions(nodes):
    bystep = {node['step']: node for node in nodes}
    selected = []; exclusions = Counter()
    for edge in edges(nodes):
        if edge['parent_missing']:
            exclusions['missing_parent'] += 1; continue
        parent, child = bystep[edge['parent_step']], bystep[edge['child_step']]
        if parent.get('exit_code') in (None, 0):
            exclusions['parent_not_observed_nonzero'] += 1; continue
        if child.get('exit_code') != 0 or submission_validity(child) != 1:
            exclusions['child_not_zero_and_valid'] += 1; continue
        if child.get('is_buggy') is not False:
            exclusions['child_buggy_or_unclassified'] += 1; continue
        value = child.get('metric')
        if type(value) not in (int, float) or not math.isfinite(value):
            exclusions['child_search_measurement_absent'] += 1; continue
        if not edge['code_bytes_changed']:
            exclusions['unchanged_code'] += 1; continue
        if any(SECRET.search(node['code']) for node in (parent, child)):
            raise ValueError('credential-shaped code must not enter memory')
        for node in (parent, child): ast.parse(node['code'])
        diff = ''.join(difflib.unified_diff(parent['code'].splitlines(keepends=True),
            child['code'].splitlines(keepends=True), fromfile='observed_parent.py', tofile='observed_debug_child.py'))
        added = sum(line.startswith('+') and not line.startswith('+++') for line in diff.splitlines())
        removed = sum(line.startswith('-') and not line.startswith('---') for line in diff.splitlines())
        selected.append(dict(parent_step=parent['step'], child_step=child['step'],
            parent_code_sha256=sha(parent['code'].encode()), child_code_sha256=sha(child['code'].encode()),
            diff_sha256=sha(diff.encode()), added_lines=added, removed_lines=removed,
            parent_families=classify(parent.get('term_out') or '')[1],
            parent_code=parent['code'], observed_successful_child_code=child['code'], observed_diff=diff))
    return selected, dict(exclusions)


def main():
    os.umask(0o077)
    source = read(SUMMARY, SUMMARY_SHA)
    task_by_run = {(row['root'], row['run_id']): row['task'] for row in source['rows']}
    private = []; proof_rows = []; exclusions = Counter()
    for proof in source['proof']:
        root = BASE / proof['root']; path = root/'runs'/proof['run_id']/'checkpoint/journal.jsonl'
        raw = path.read_bytes()
        if sha(raw) != proof['journal_sha256']: raise ValueError('old source drift')
        # Never materialize credential-redacted code as if it were executable.
        # This bounded inventory fails closed on a hit, before parsing/writing.
        if SECRET.search(raw.decode()): raise ValueError('credential-shaped old journal requires separate review')
        selected, rejected = eligible_transitions([json.loads(line) for line in raw.splitlines()])
        exclusions.update(rejected)
        artifact = read(root/'artifact.json')
        for item in selected:
            item.update(root=proof['root'], run_id=proof['run_id'], task=task_by_run[(proof['root'], proof['run_id'])],
                source_tree=artifact['source_tree'], journal_sha256=proof['journal_sha256'])
            private.append(item)
        if sha(path.read_bytes()) != proof['journal_sha256']: raise ValueError('old source changed while reading')
        proof_rows.append(dict(**proof, transitions=len(selected), exclusions=rejected))
    public = [{k:v for k,v in row.items() if k not in ('parent_code','observed_successful_child_code','observed_diff')} for row in private]
    hashes = {(r['parent_code_sha256'],r['child_code_sha256']) for r in public}
    total = dict(transitions=len(public), distinct_exact_code_pairs=len(hashes),
        distinct_runs=len({(r['root'],r['run_id']) for r in public}),
        tasks=dict(Counter(r['task'] for r in public)),
        parent_error_families=dict(Counter(f for r in public for f in r['parent_families'])), exclusions=dict(exclusions))
    dest = Path(tempfile.mkdtemp(prefix='forets-repair-memory-inventory-20260913-', dir=BASE))
    private_sha = write(dest/'observed-repair-code.private.json', encode(dict(rows=private)))
    result = dict(role='observed_successful_debug_inventory_not_general_verified_repairs', root=str(dest), totals=total,
        source_summary_sha256=SUMMARY_SHA, private_inventory_sha256=private_sha, rows=public, source_proofs=proof_rows,
        script_sha256=sha(Path(__file__).read_bytes()), api_calls=0, gpu_jobs=0,
        selection_uses_final_score_values=False, input_new_memory_trial=False,
        limitations=['Observed success means zero exit, valid-format submission, nonbuggy and a finite search measurement; not clean learning or high quality.',
            'No independent rerun, transplant validation, or causal isolation of a changed line; diffs can contain algorithm rewrites.',
            'All observed eligible old transitions retained; no tuning to seeds34-41, final grades, or a future cohort.',
            'Hash-unique pairs are not statistically independent repairs. Full code remains remote and is not deployed.'])
    digest = write(dest/'inventory-public.json', encode(result))
    print(json.dumps(dict(root=str(dest), public_sha256=digest, private_sha256=private_sha, totals=total)))


if __name__ == '__main__': main()
