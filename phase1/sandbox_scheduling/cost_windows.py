"""Descriptive secondary analysis of already released CLOSED timing summaries.

Projects timing fields only. No quality outcomes, candidate content or predictions.
Generation time is a task-slot reservation window, NOT measured GPU idle time or
attainable speedup. Unreturned calls and unfinished execution are not imputed.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics


LLM_ARMS = {'continue', 'reimplement', 'new_idea'}
FIELDS = ('index', 'arm', 'task', 'elapsed_seconds', 'returned_generation_seconds', 'recorded_execution_seconds')


def project(row):
    return {key: row[key] for key in FIELDS}


def stats(values):
    return dict(n=len(values), median=statistics.median(values) if values else None,
                sample_variance=statistics.variance(values) if len(values) > 1 else None,
                minimum=min(values) if values else None, maximum=max(values) if values else None)


def analyze(source):
    rows = [project(row) for row in source['rows']]
    for row in rows:
        for field in FIELDS[3:]:
            value = row[field]
            if value is None:
                if field != 'elapsed_seconds':
                    raise ValueError('missing cumulative timing, do not substitute zero')
            elif not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError('invalid timing')
        elapsed = row['elapsed_seconds']
        generation = row['returned_generation_seconds']
        execution = row['recorded_execution_seconds']
        if elapsed is not None and generation + execution > elapsed + 0.01:
            raise ValueError('timing scope/overlap mismatch')
        row['known_elapsed'] = elapsed is not None
        row['returned_generation_fraction'] = generation / elapsed if elapsed and elapsed > 0 else None
    selected = [row for row in rows if row['arm'] in LLM_ARMS]
    if len(rows) != 18 or len(selected) != 12 or len({r['task'] for r in rows}) != 2:
        raise ValueError('unexpected original closed cohort')
    if len({r['index'] for r in rows}) != len(rows):
        raise ValueError('duplicate run index')
    grouped = []
    for key in ('arm', 'task'):
        for name in sorted({r[key] for r in selected}):
            group = [r for r in selected if r[key] == name]
            grouped.append(dict(group_by=key, group=name, runs=len(group),
                unknown_elapsed=sum(not r['known_elapsed'] for r in group),
                returned_generation_seconds_sum=sum(r['returned_generation_seconds'] for r in group),
                generation_seconds=stats([r['returned_generation_seconds'] for r in group]),
                fraction_among_known_elapsed=stats([r['returned_generation_fraction'] for r in group
                                                    if r['returned_generation_fraction'] is not None])))
    total = sum(r['returned_generation_seconds'] for r in selected)
    summary = dict(all_original_rows=len(rows), llm_rows=len(selected), tasks=2,
        unknown_elapsed=sum(not r['known_elapsed'] for r in selected),
        recorded_returned_generation_seconds=total, task_slot_minutes_in_returned_generation=total/60,
        generation_seconds=stats([r['returned_generation_seconds'] for r in selected]),
        fraction_among_known_elapsed=stats([r['returned_generation_fraction'] for r in selected
                                            if r['returned_generation_fraction'] is not None]),
        grouped=grouped, gpu_utilization='not_measured', speedup='not_estimated',
        inference='Existing two-task development cohort; dependent methods share sources/seeds. '
                  'No causal scheduling effect, cross-task generalization or total GPU saving is estimated. '
                  'Each sandbox step reserved one GPU while these calls ran; generator GPUs counted separately. '
                  'Returned-call windows are not automatically reclaimable: backlog, admission, CPU and service limits matter.')
    return rows, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--input-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    config = parser.parse_args()
    raw = config.input.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != config.input_sha256:
        raise ValueError('released timing artifact hash mismatch')
    rows, summary = analyze(json.loads(raw))
    config.output.mkdir(exist_ok=False)
    summary.update(input_sha256=digest, analyzer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   source_commit='e5e83b6e4eed842197f7de924ae4734003e8965a',
                   quality_fields_accessed=False, new_candidate_executions=0, new_gpu_hours=0)
    with (config.output/'timing_rows.csv').open('x', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with (config.output/'summary.json').open('x', encoding='utf-8') as file:
        json.dump(summary, file, sort_keys=True, indent=2, allow_nan=False)
        file.write('\n')
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    main()
