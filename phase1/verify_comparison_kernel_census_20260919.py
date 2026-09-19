"""Verify safe census counts against independently exported run/node identities."""
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path


def main():
    root = Path(__file__).parent/'results/comparison_qwen_20260919'
    def load(name, expected):
        raw = (root/name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f'identity changed: {name}')
        return json.loads(raw)
    census = load('kernel-readiness-census.json', 'c10fe98afa81ee13effbbd05d072de802794598e8a740b3554be892858215fb5')
    runs = load('runs.json', '040c4463a967a34667dd1943735e923d0193a4f50c4c5eae24e9ada3a2da68c8')
    nodes = load('nodes.json', '370976e31c8a9f501bc75fb7826f529f85b0e34059146291f2e7bb3cab4062c9')
    run_index = {r['run']: r for r in runs if r['journal_present']}
    node_index = {(r['run'], r['id']): r for r in nodes if r['group'] == 'executed'}
    nonroot = Counter(r['run'] for r in node_index.values() if r['operators_used'])
    if len(census['rows']) != len(run_index) or {r['run'] for r in census['rows']} != set(run_index):
        raise ValueError('run coverage')
    seen = set(); counts = Counter(); affected = Counter(); denominators = Counter(); times = []
    for row in census['rows']:
        run = run_index[row['run']]
        if row['nodes'] != nonroot[row['run']] or row['commit'] != run['commit']:
            raise ValueError('node denominator/commit')
        arm = run['arm']
        denominators[arm] += row['nodes']
        affected[arm] += bool(row['readiness_failures'])
        for marker in row['readiness_failures']:
            key = (row['run'], marker['node'])
            if key in seen or key not in node_index:
                raise ValueError('duplicate or foreign node')
            seen.add(key)
            if not marker['generic_program_timeout_message'] or marker['exit_code'] != 1:
                raise ValueError('failure shape not expected')
            counts[arm] += 1
            times.append(marker['exec_time'])
    if len(seen) != census['marker_nodes'] or sum(nonroot.values()) != census['nonroot_executed_nodes']:
        raise ValueError('aggregate mismatch')
    result = dict(independent_identity_and_count_checks=True, raw_log_marker_reparse=False,
                  marker_nodes=len(seen), denominator=sum(nonroot.values()),
                  node_fraction=len(seen)/sum(nonroot.values()), affected_runs=sum(affected.values()),
                  by_arm={a:dict(markers=counts[a],nonroot_nodes=denominators[a],affected_runs=affected[a]) for a in sorted(denominators)},
                  exec_seconds_min=min(times), exec_seconds_median=statistics.median(times),exec_seconds_max=max(times),
                  limitation='Not an independent reparse of logs; no recovery rate or causal arm comparison implied.')
    with (root/'kernel-readiness-independent.json').open('x') as handle:
        json.dump(result,handle,indent=2,allow_nan=False)
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
