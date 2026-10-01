"""Post-hoc exposure audit; descriptive, not causal mediation or a new trial."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path('/research/d7/spc/yzyang4/task-feedback-real-20261001-v6')
PLAN_SHA = '15751d3b52bdc42617df02006ce724635f4bf49df6e477686769fd1979d53403'


def read(path):
    return json.loads(path.read_bytes())


def audit():
    assert hashlib.sha256((ROOT / 'plan.json').read_bytes()).hexdigest() == PLAN_SHA
    assert read(ROOT / 'all-closed.json')['attempts'] == 18
    plan = read(ROOT / 'plan.json')
    rows = []
    for scheduled in plan['schedule']:
        episode = ROOT / f'episode-{scheduled["index"]}'
        assert (episode / 'closed.json').exists()
        counts = Counter()
        for step in range(1, 5):
            action = episode / f'action-{step}'
            path = action / 'feedback.json'
            if not path.exists():
                continue
            receipt = read(path)
            encoded = receipt['facts_json']
            assert hashlib.sha256(encoded.encode()).hexdigest() == receipt['facts_sha256']
            data = json.loads(encoded)
            assert receipt['arm'] == scheduled['arm']
            facts = data.get('aggregate_diagnostics')
            valid = data['trusted_result']['valid']
            if scheduled['arm'] == 'A':
                assert 'aggregate_diagnostics' not in data
            else:
                assert (facts is not None) == valid
                if facts is not None:
                    assert facts['role'] == 'development_descriptive_only'
                    assert len(facts['slices']) == 3
            counts['generation_attempts'] += 1
            counts['valid_parent_attempts'] += int(valid)
            counts['attempts_with_aggregate_facts'] += int(facts is not None)
            counts['generation_returned'] += int((action / 'generation.private.json').exists())
            counts['execution_result_returned'] += int((action / 'result.json').exists())
        rows.append({k: scheduled[k] for k in ('index', 'start', 'task', 'arm')} | dict(counts))
    totals = {}
    for arm in 'ABC':
        totals[arm] = dict(sum((Counter({k: v for k, v in r.items() if k not in ('index', 'start', 'task', 'arm')}) for r in rows if r['arm'] == arm), Counter()))
        # Counter addition drops zero keys; preserve them explicitly.
        for key in ('generation_attempts', 'valid_parent_attempts', 'attempts_with_aggregate_facts', 'generation_returned', 'execution_result_returned'):
            totals[arm].setdefault(key, 0)
    return {'scope': 'Post-hoc descriptive exposure counts. Valid-parent status is treatment-dependent; do not condition on it to claim an effect. No new scoring, generation or execution.', 'plan_sha256': PLAN_SHA, 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'rows': rows, 'totals_by_arm': totals}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    with args.out.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}, sort_keys=True))
