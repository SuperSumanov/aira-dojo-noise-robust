"""Read explicitly listed DEVELOPMENT ForeTS results; never discover run folders.

This is an exploratory result reader, not a launcher, scorer or confirmation gate.
The caller must independently bind the manifest to actual configs/resource records.
Only final EVAL and bounded-process summaries are read. Never use last grading
reports, self-reports, intermediate candidates, or any protected cohort here.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

from forets_pilot_plan import POLICIES, TASKS, SEEDS, run_order


METRICS = {'leaf-classification': ('log_loss', -1),
           'spaceship-titanic': ('accuracy', 1)}
ROLE = 'forets_e2e_development'


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _unique_object(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def _json(text):
    return json.loads(text, object_pairs_hook=_unique_object)


def _inside(root, relative):
    # Explicit relative paths only; resolving first also rejects symlink escapes.
    if not isinstance(relative, str) or not relative or '\\' in relative:
        raise ValueError('explicit POSIX-style relative artifact path required')
    path = Path(relative)
    if path.is_absolute() or ':' in relative or '..' in path.parts:
        raise ValueError('artifact path outside development root')
    result = (root / path).resolve()
    if result == root or not result.is_relative_to(root):
        raise ValueError('artifact path outside development root')
    return result


def _final_event(path, task):
    """Never pick first/last/best among repeated final events."""
    if not path.is_file():
        return None, None, 'missing_final_event'
    try:
        lines = [line for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        if len(lines) != 1:
            return None, None, 'ambiguous_final_event_count'
        event = _json(lines[0])
        data = event.get('data') if isinstance(event, dict) else None
        if not isinstance(data, dict) or 'score' not in data:
            return None, None, 'invalid_final_event'
        score, selected = data['score'], data.get('selected_node_id')
        if not _finite(score) or not isinstance(selected, str) or not selected.strip():
            return None, None, 'invalid_final_event'
        if score < 0 or (task == 'spaceship-titanic' and score > 1):
            return None, None, 'score_outside_metric_domain'
        return score, selected, None
    except (ValueError, OSError, UnicodeError):
        return None, None, 'unreadable_final_event'


def _process(path):
    if not path.is_file():
        return 'missing_process_summary', False, None, None
    try:
        data = _json(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError('object required')
        allowed = {'completed', 'failed', 'timed_out', 'interrupted',
                   'launch_or_supervisor_failed', 'completed_with_leftovers', 'cleanup_unconfirmed'}
        status = data.get('status')
        if status not in allowed:
            raise ValueError('unknown status')
        elapsed = data.get('elapsed_seconds')
        if not _finite(elapsed) or elapsed < 0:
            elapsed = None
        code = data.get('returncode')
        completed = (status == 'completed' and data.get('started') is True
                     and type(code) is int and code == 0)
        if status == 'completed' and not completed:
            status = 'inconsistent_completed_summary'
        return status, completed, elapsed, code if type(code) is int else None
    except (ValueError, OSError, UnicodeError, TypeError):
        return 'invalid_process_summary', False, None, None


def validate_manifest(manifest, root):
    if not isinstance(manifest, dict) or manifest.get('role') != ROLE or manifest.get('schema') != 1:
        raise ValueError('explicit development manifest schema=1 required')
    if not re.fullmatch('[0-9a-f]{40}', str(manifest.get('source_tree', ''))):
        raise ValueError('declared exact experiment source tree required')
    entries = manifest.get('runs')
    if not isinstance(entries, list) or len(entries) != len(tuple(run_order())):
        raise ValueError('all eight planned runs must remain in the manifest')
    matrix, ids, directories = {}, set(), set()
    for entry in entries:
        if not isinstance(entry, dict) or type(entry.get('seed')) is not int:
            raise ValueError('invalid planned run')
        if not re.fullmatch('[0-9a-f]{64}', str(entry.get('config_sha256', ''))):
            raise ValueError('declared actual config SHA256 required')
        key = (entry.get('task'), entry['seed'], entry.get('policy'))
        if key not in tuple(run_order()) or key in matrix:
            raise ValueError('duplicate or out-of-matrix run')
        run_id = entry.get('run_id')
        if not isinstance(run_id, str) or not run_id.strip() or run_id in ids:
            raise ValueError('unique nonempty run_id required')
        run_dir = _inside(root, entry.get('run_dir'))
        if run_dir in directories:
            raise ValueError('multiple planned runs share an artifact directory')
        for old in directories:
            if run_dir.is_relative_to(old) or old.is_relative_to(run_dir):
                raise ValueError('nested run directories are ambiguous')
        # Check both targets BEFORE reading either; links cannot escape even if
        # the containing run directory itself is within the allowed root.
        eval_path = _inside(root, (Path(entry['run_dir']) / 'json/eval.jsonl').as_posix())
        process_path = _inside(root, entry.get('process_summary'))
        matrix[key] = (entry, eval_path, process_path)
        ids.add(run_id)
        directories.add(run_dir)
    if len({value[2] for value in matrix.values()}) != len(matrix):
        raise ValueError('multiple runs share a process summary')
    return matrix


def summarize(manifest, development_root):
    """No new model inference, task evaluation, directory crawl, or writes."""
    root = Path(development_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('development root must be a directory')
    matrix = validate_manifest(manifest, root)
    runs, indexed = [], {}
    for key in run_order():
        task, seed, policy = key
        entry, event_path, process_path = matrix[key]
        score, selected, event_issue = _final_event(event_path, task)
        status, complete, elapsed, code = _process(process_path)
        eligible = complete and event_issue is None
        row = dict(run_id=entry['run_id'], task=task, seed=seed, policy=policy,
                   declared_source_tree=manifest['source_tree'], declared_config_sha256=entry['config_sha256'],
                   metric=METRICS[task][0], process_status=status, process_returncode=code,
                   final_event_issue=event_issue, final_score_observed=score,
                   selected_node_id=selected, comparable_final=eligible,
                   comparable_score=score if eligible else None,
                   process_elapsed_seconds=elapsed)
        runs.append(row)
        indexed[key] = row
    pairs = []
    for task in TASKS:
        for seed in SEEDS:
            random, critic = (indexed[(task, seed, policy)] for policy in POLICIES)
            eligible = random['comparable_final'] and critic['comparable_final']
            delta = METRICS[task][1] * (critic['comparable_score'] - random['comparable_score']) if eligible else None
            pairs.append(dict(task=task, seed=seed, metric=METRICS[task][0], comparable=eligible,
                              random_run_id=random['run_id'], critic_run_id=critic['run_id'],
                              improvement=delta))
    tasks = []
    for task in TASKS:
        deltas = [row['improvement'] for row in pairs if row['task'] == task and row['comparable']]
        by_policy = {}
        for policy in POLICIES:
            subset = [row for row in runs if row['task'] == task and row['policy'] == policy]
            times = [row['process_elapsed_seconds'] for row in subset if row['process_elapsed_seconds'] is not None]
            by_policy[policy] = dict(planned_runs=len(subset),
                observed_final_events=sum(row['final_event_issue'] is None for row in subset),
                comparable_finals=sum(row['comparable_final'] for row in subset),
                known_process_seconds=sum(times), unknown_process_seconds_runs=len(subset)-len(times))
        tasks.append(dict(task=task, metric=METRICS[task][0], planned_pairs=len(SEEDS),
                          comparable_pairs=len(deltas), improvements=deltas,
                          median_improvement=statistics.median(deltas) if deltas else None,
                          sample_stdev_improvement=statistics.stdev(deltas) if len(deltas)>1 else None,
                          by_policy=by_policy))
    return dict(schema=1, role=ROLE, planned_runs=len(runs), planned_pairs=len(pairs),
                reader_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                comparable_pairs=sum(row['comparable'] for row in pairs), runs=runs, pairs=pairs, tasks=tasks,
                limitations=['Exploratory, two tasks; not a confirmation result.',
                             'Manifest identity and fairness need independent config checks.',
                             'Process completion is not Slurm allocation completion.',
                             'No cross-task average; conditional valid pairs are not all-run utility.',
                             'Process seconds exclude some setup/idle allocation time; not GPU hours.',
                             'Allocation GPU hours, initialization cost and API cost are not computed.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--development-root', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    result = summarize(_json(args.manifest.read_text(encoding='utf-8')), args.development_root)
    # Exclusive output: do not overwrite an earlier report or mutate inputs.
    args.output_dir.mkdir(parents=False, exist_ok=False)
    for key in ('runs', 'pairs'):
        rows = result[key]
        with (args.output_dir / (key + '.csv')).open('x', encoding='utf-8', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)  # None remains empty, never numeric zero.
    with (args.output_dir / 'summary.json').open('x', encoding='utf-8') as file:
        json.dump(result, file, ensure_ascii=False, indent=2, allow_nan=False)
        file.write('\n')
    print(json.dumps({key:result[key] for key in ('role','planned_runs','planned_pairs','comparable_pairs')}))


if __name__ == '__main__':
    main()
