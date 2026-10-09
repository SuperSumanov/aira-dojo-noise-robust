"""Mechanical all-run CSV export after the immutable primary/secondary readouts.

No candidate-level text or scores. allocation_total_gpu_seconds is shared pool
cost, repeated for identification only: NEVER sum that column across rows.
"""
import argparse
import csv
import json
from pathlib import Path

from lifecycle_pilot import read, sha
from exposure_opportunity_readout import PLAN, ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root
    if root != ROOT or sha(root/'plan.json') != PLAN:
        raise ValueError('exact exposure batch required')
    plan = read(root/'plan.json')
    primary = read(root/'exposure-readout-v1.json')
    secondary = read(root/'opportunity-readout-v1.json')
    if secondary['primary_sha256'] != sha(root/'exposure-readout-v1.json'):
        raise ValueError('primary linkage')
    if sorted(r['index'] for r in primary['rows']) != list(range(4)) or sorted(r['index'] for r in secondary['rows']) != list(range(4)):
        raise ValueError('all four assigned rows required')
    rows = []
    for assignment in plan['schedule']:
        p = next(r for r in primary['rows'] if r['index'] == assignment['index'])
        q = next(r for r in secondary['rows'] if r['index'] == assignment['index'])
        if any(p[k] != assignment[k] or q[k] != assignment[k] for k in ('task', 'seed', 'arm')):
            raise ValueError('assignment drift')
        rows.append(dict(**assignment, source_commit=plan['source_commit'], plan_sha256=PLAN,
                         primary_sha256=sha(root/'exposure-readout-v1.json'),
                         secondary_sha256=sha(root/'opportunity-readout-v1.json'),
                         model=plan['used_model'], task_image_sha256=plan['task_image_sha256'],
                         service_image_sha256=plan['service_image_sha256'], run_budget_seconds=3000,
                         allocation_total_gpu_seconds=primary['allocation_gpu_seconds'],
                         cost_scope='shared allocation total; do not sum over runs',
                         complete=p['complete'], candidate_returns=p['candidate_returns'],
                         valid_returns=p['valid_returns'], generation_calls=p['generation_calls'],
                         completed_valid_improves=p['completed_valid_improves'],
                         unmatched_recorded_nodes=p['unmatched_recorded_nodes'],
                         readiness_failures=p['readiness_failures'],
                         paired_valid_parent_edges=q['paired_valid_parent_edges'],
                         better_than_parent=q['better_than_parent'], tied_with_parent=q['tied_with_parent'],
                         worse_than_parent=q['worse_than_parent'],
                         strict_incumbent_improvements=q['strict_incumbent_improvements']))
    destination = root/'exposure-safe-runs-v1.csv'
    with destination.open('x', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(dict(assigned=4, csv_sha256=sha(destination), exporter_sha256=sha(Path(__file__)))))


if __name__ == '__main__':
    main()
