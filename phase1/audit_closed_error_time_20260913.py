"""Time-weighted description of the same frozen old development error corpus."""
from collections import defaultdict
import json
import math
from pathlib import Path
from forets_environment_build_20260912 import read, write, encode, sha
from audit_closed_error_families_20260913 import BASE, SECRET, classify
from inspect_closed_error_recurrence_20260913 import SUMMARY, SUMMARY_SHA


def accumulate(nodes):
    groups = defaultdict(lambda: dict(nodes=0, interpreter_seconds=0.0))
    for node in nodes:
        if node['step'] == 0 or node.get('exec_time') is None:
            continue
        seconds = node['exec_time']
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
            raise ValueError('invalid reported execution duration')
        failed = node.get('exit_code') not in (None, 0)
        tags = ['all_saved_executed', 'nonzero_exit' if failed else 'zero_or_unreported_exit']
        if failed:
            families = classify(node.get('term_out') or '')[1]
            tags += ['family:' + f for f in families] if families else ['unclassified_failure']
        if 'debug' in node.get('operators_used', []):
            tags += ['debug', 'debug_nonzero_exit' if failed else 'debug_zero_or_unreported_exit']
        for tag in tags:
            groups[tag]['nodes'] += 1
            groups[tag]['interpreter_seconds'] += seconds
    return dict(groups)


def main():
    source = read(SUMMARY, SUMMARY_SHA); rows = []
    for proof in source['proof']:
        path = BASE / proof['root'] / 'runs' / proof['run_id'] / 'checkpoint/journal.jsonl'
        raw = path.read_bytes()
        if sha(raw) != proof['journal_sha256']: raise ValueError('old journal drift')
        safe = SECRET.sub('[REDACTED]', raw.decode())
        nodes = [json.loads(line) for line in safe.splitlines()]
        counts = accumulate(nodes)
        if sha(path.read_bytes()) != proof['journal_sha256']: raise ValueError('reading changed journal')
        rows.append(dict(root=proof['root'], run_id=proof['run_id'], journal_sha256=proof['journal_sha256'], groups=counts))
    totals = defaultdict(lambda: dict(nodes=0, interpreter_seconds=0.0))
    for row in rows:
        for key, count in row['groups'].items():
            for field in ('nodes', 'interpreter_seconds'): totals[key][field] += count[field]
    if totals['all_saved_executed']['nodes'] != 157 or totals['nonzero_exit']['nodes'] != 105:
        raise ValueError('must match exactly the original observed taxonomy')
    result = dict(role='same_closed_development_count_vs_execution_time_not_savings',
        source_summary_sha256=SUMMARY_SHA, totals=dict(totals), rows=rows,
        script_sha256=sha(Path(__file__).read_bytes()),
        limitations=['Only the same saved nodes in 27 journals of 32 planned old searches, heterogeneous protocols.',
            'Reported interpreter execution time is not allocation time, GPU utilization, model latency, or entire failed-attempt cost.',
            'Families overlap; their times cannot be added as exclusive costs. No estimate of counterfactual saved time.',
            'The frozen future memory observations remain unchanged; this is not a new selection rule.'])
    digest = write(SUMMARY.with_name('closed-error-time.json'), encode(result))
    print(json.dumps(dict(sha256=digest, totals=dict(totals))))


if __name__ == '__main__': main()
