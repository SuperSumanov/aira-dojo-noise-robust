"""Supplemental work/error counts after the entire width/memory contrast closes.

No new grading, filtering, outcome selection, model calls, or experiment changes.
"""
from collections import Counter
import json
from pathlib import Path
import re
import sys
from forets_environment_build_20260912 import read, write, encode, sha
from forets_paid_measurements_20260912 import read_batch
from audit_closed_error_families_20260913 import SECRET, classify

FIELDS = ('generated_candidates', 'candidate_task_calls', 'debug_task_calls',
    'total_task_calls', 'returned_task_calls', 'unresolved_task_calls', 'raised_task_calls',
    'invalid_return_task_calls', 'metadata_missing_calls', 'interpreter_exit_zero_calls',
    'interpreter_timeout_calls', 'measured_task_calls', 'task_wall_seconds_observed',
    'interpreter_seconds_observed')


def journal_counts(nodes):
    counts = Counter()
    for node in nodes:
        if node['step'] == 0 or node.get('exec_time') is None:
            continue
        counts['saved_executed_nodes'] += 1
        if node.get('exit_code') not in (None, 0):
            counts['nonzero_nodes'] += 1
            families = classify(node.get('term_out') or '')[1]
            counts['unclassified_nonzero_nodes'] += not bool(families)
            for family in families:
                counts['error_family:' + family] += 1
        counts['valid_submission_nodes'] += (node.get('metric_info') or {}).get('valid_submission') == 1
    return dict(counts)


def run(root):
    root = root.resolve(strict=True)
    if root.parent != Path('/research/d7/spc/yzyang4'):
        raise ValueError('explicit experiment root scope')
    finish = read(root / 'readout-finished.json')
    if finish['status'] != 'verified':
        raise ValueError('complete official readout first')
    for name, digest in finish['files'].items():
        if sha((root / name).read_bytes()) != digest:
            raise ValueError('closed export drift')
    kind = 'memory' if 'memory-summary.json' in finish['files'] else 'width'
    value = read(root / (kind + '-summary.json'))
    seeds, arms = ((40, 41), ('no_memory', 'execution_memory')) if kind == 'memory' else ((38, 39), ('batch_four', 'direct_two'))
    expected = {(t, s, a) for t in ('leaf-classification', 'spaceship-titanic') for s in seeds for a in arms}
    if len(value['rows']) != 8 or {(r['task'], r['seed'], r['arm']) for r in value['rows']} != expected:
        raise ValueError('exact frozen complete matrix')
    build = read(root / 'build.json'); prepared = read(root / 'prepared.json', build['prepared_sha256'])
    rows = []
    for runrow in value['rows']:
        rid = runrow['run_id']
        planned = next(p for p in prepared['run_configs'] if p['run_id'] == rid)
        cfg = read(root / 'configs' / (rid + '.json'), planned['config_sha256'])
        cp = Path(cfg['solver']['checkpoint_path'])
        if cp.resolve() != (root / 'runs' / rid / 'checkpoint').resolve():
            raise ValueError('exact development checkpoint only')
        batches = []
        for path in sorted((cp / 'forets-candidates-private').glob('batch-*.sqlite')):
            match = re.fullmatch(r'batch-(\d+)\.sqlite', path.name)
            if not match: raise ValueError('batch step')
            batches.append(read_batch(path, task=runrow['task'], arm='uniform_random', step=int(match[1])))
        row = {k: runrow[k] for k in ('run_id', 'task', 'seed', 'arm', 'technical_eligible')}
        row.update({k: sum(b[k] for b in batches) for k in FIELDS})
        for actual, frozen in (('generated_candidates', 'returned_candidate_records_including_start'),
            ('candidate_task_calls', 'candidate_execution_attempts_including_start'), ('debug_task_calls', 'debug_execution_attempts')):
            if row[actual] != runrow[frozen]: raise ValueError('independent work count mismatch')
        elapsed = runrow['worker_elapsed_seconds']
        row['worker_elapsed_seconds'] = elapsed
        row['observed_task_wall_fraction'] = row['task_wall_seconds_observed'] / elapsed if elapsed else None
        journal = cp / 'journal.jsonl'
        row['journal_present'] = journal.exists()
        if journal.exists():
            raw = journal.read_bytes(); safe = SECRET.sub('[REDACTED]', raw.decode())
            row['journal_counts'] = journal_counts([json.loads(line) for line in safe.splitlines()])
            row['journal_sha256'] = sha(raw)
            if sha(journal.read_bytes()) != row['journal_sha256']: raise ValueError('journal drift')
        else:
            row.update(journal_counts=None, journal_sha256=None)
        row['batch_proofs'] = [{'step': b['step'], 'sha256': b['ledger_sha256']} for b in batches]
        rows.append(row)
    result = dict(role='closed_uniform_work_error_supplement_not_primary_endpoint', kind=kind, rows=rows,
        source_finish_sha256=sha((root / 'readout-finished.json').read_bytes()), script_sha256=sha(Path(__file__).read_bytes()),
        limitations=['Generated/execution counts include the common fixed RF start, not only LLM outputs.',
            'Observed completed task-call wall time includes task/grade work. Missing/in-flight intervals are not zero work.',
            'Remaining worker time is not all model or critic latency; setup, analysis, logging, waiting also contribute.',
            'Exit zero is not a valid or high-quality final submission. Saved journal coverage can be incomplete.',
            'Error families use the unchanged historical parser, may overlap, and are auxiliary; no exclusions or new success endpoint.'])
    digest = write(root / 'closed-uniform-work.json', encode(result))
    print(json.dumps(dict(sha256=digest, kind=kind, rows=rows)))


if __name__ == '__main__': run(Path(sys.argv[1]))
