"""Describe missing search measurements in exactly the frozen old journals.

This does not inspect new memory outcomes, rescore, or recover any node.
"""
from collections import Counter
import json
import math
from pathlib import Path
from forets_environment_build_20260912 import read, write, encode, sha
from audit_closed_error_families_20260913 import BASE, SECRET
from inspect_closed_error_recurrence_20260913 import SUMMARY, SUMMARY_SHA


def submission_validity(node):
    values = []
    info = node.get('metric_info')
    if isinstance(info, dict) and 'valid_submission' in info:
        values.append(info['valid_submission'])
    if 'metric_info/valid_submission' in node:
        values.append(node['metric_info/valid_submission'])
    if any(v not in (None, 0, 1) for v in values):
        raise ValueError('unexpected submission validity')
    if values and any(v != values[0] for v in values):
        raise ValueError('inconsistent nested/flat validity')
    return values[0] if values else None


def classify_node(node):
    if node['step'] == 0 or node.get('exec_time') is None:
        return None
    code = node.get('exit_code')
    metric = node.get('metric')
    if metric is not None and (type(metric) not in (int, float) or not math.isfinite(metric)):
        raise ValueError('unexpected saved search metric')
    buggy = node.get('is_buggy')
    if buggy is not None and type(buggy) is not bool:
        raise ValueError('unexpected saved buggy flag')
    return dict(exit_status='unknown' if code is None else 'zero' if code == 0 else 'nonzero',
        valid_submission=submission_validity(node), search_metric_present=metric is not None,
        is_buggy=buggy)


def accumulate(nodes):
    counts = Counter(); gaps = []
    for node in nodes:
        state = classify_node(node)
        if state is None:
            continue
        counts['saved_executed_nodes'] += 1
        counts['exit_' + state['exit_status']] += 1
        counts['validity_' + str(state['valid_submission'])] += 1
        if state['exit_status'] != 'zero':
            continue
        counts['zero_exit_metric_present' if state['search_metric_present'] else 'zero_exit_metric_missing'] += 1
        if state['valid_submission'] == 1:
            counts['zero_exit_valid_submission'] += 1
            counts['zero_valid_buggy_' + str(state['is_buggy'])] += 1
            counts['zero_valid_metric_present' if state['search_metric_present'] else 'zero_valid_metric_missing'] += 1
            if state['is_buggy'] is True or not state['search_metric_present']:
                gaps.append(dict(step=node['step'], **state))
    return dict(counts), gaps


def main():
    source = read(SUMMARY, SUMMARY_SHA); rows = []; totals = Counter()
    for proof in source['proof']:
        path = BASE / proof['root'] / 'runs' / proof['run_id'] / 'checkpoint/journal.jsonl'
        raw = path.read_bytes()
        if sha(raw) != proof['journal_sha256']:
            raise ValueError('old journal drift')
        safe = SECRET.sub('[REDACTED]', raw.decode())
        counts, gaps = accumulate([json.loads(line) for line in safe.splitlines()])
        totals.update(counts)
        rows.append(dict(root=proof['root'], run_id=proof['run_id'], counts=counts, gaps=gaps,
            journal_sha256=proof['journal_sha256']))
        if sha(path.read_bytes()) != proof['journal_sha256']:
            raise ValueError('journal changed while reading')
    if totals['saved_executed_nodes'] != 157 or totals['exit_nonzero'] != 105:
        raise ValueError('must match the fixed old corpus')
    result = dict(role='closed_development_measurement_missingness_not_repair_gain',
        source_summary_sha256=SUMMARY_SHA, totals=dict(totals), rows=rows,
        script_sha256=sha(Path(__file__).read_bytes()),
        limitations=['Only 27 saved journals of 32 old runs; heterogeneous protocols, incomplete persistence.',
            'Valid submission is only file/schema validity, not model quality or absence of data leakage.',
            'Missing metric and buggy flag co-occurrence does not establish causal direction or that bug flag is wrong.',
            'No new outcome, metric value, private label, repair, selection, or API/GPU execution.'])
    digest = write(SUMMARY.with_name('closed-measurement-gaps.json'), encode(result))
    print(json.dumps(dict(sha256=digest, totals=dict(totals))))


if __name__ == '__main__': main()
