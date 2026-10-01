"""Post-hoc harm decomposition of a FROZEN rule, not another rule search.

Uses only previously approved and scored D_search artifacts. No new candidate,
model fit, label release, threshold tuning or selection; keeps all nine endpoints.
"""
import csv
import hashlib
import json
import math
import os
import statistics
import sys
from pathlib import Path

BASE = Path('/research/d7/spc/yzyang4')
ROOT = BASE / 'task-feedback-public-rule-20261002-v1'
OLD = BASE / 'task-feedback-real-20261001-v6'
PUBLIC = BASE / 'tweet-search-only-20260927-a4d1/public'
SUMMARY_SHA = '7445f0c59ade28985cc039ba78c6e7663d8abf57464b2772405ee596837e46f7'
RULE_SHA = '2beaad25ab591c957f1183de5b17457ff738b25130d13075df500c36bb4fbfc0'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def csvrows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def similarity(left, right):
    left, right = set(left.lower().split()), set(right.lower().split())
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def decompose(baseline, amended, covered, text_changed):
    assert len(baseline) == len(amended) == len(covered) == len(text_changed) > 0
    assert all(math.isfinite(v) and 0 <= v <= 1 for v in baseline + amended)
    assert all(x == y and not changed for x, y, take, changed in zip(baseline, amended, covered, text_changed) if not take)
    diffs = [b - a for a, b in zip(baseline, amended)]
    n = len(diffs)
    gain = math.fsum(max(d, 0) for d in diffs) / n
    loss = math.fsum(min(d, 0) for d in diffs) / n
    target = [b for b, take in zip(amended, covered) if take]
    # Finite observed-set bound vs a perfect incumbent ON THE COVERED GROUP;
    # not a confidence bound, deployable oracle, or distribution-level guarantee.
    floor = math.fsum(b - 1 for b in target) / n
    assert loss >= floor - 1e-12
    return dict(rows=n, covered_rows=sum(covered), changed_text_rows=sum(text_changed),
                improved_rows=sum(d > 1e-12 for d in diffs), harmed_rows=sum(d < -1e-12 for d in diffs),
                metric_ties=sum(abs(d) <= 1e-12 for d in diffs),
                positive_contribution=gain, negative_contribution=loss, net_change=gain + loss,
                covered_rule_mean=statistics.mean(target) if target else None,
                covered_baseline_mean=statistics.mean(a for a, take in zip(baseline, covered) if take) if target else None,
                finite_set_worst_incumbent_difference=floor,
                non_target_predictions_unchanged=True)


def run():
    os.umask(0o077)
    assert sha(ROOT / 'summary.json') == SUMMARY_SHA
    assert sha(ROOT / 'rule.json') == RULE_SHA
    summary, manifest = load(ROOT / 'summary.json'), load(ROOT / 'evaluation-plan.json')
    assert len(summary['rows']) == len(manifest['sources']) == 9
    assert sha(PUBLIC / 'test.csv') == manifest['public_input_sha256']
    rule = summary['rule']
    assert rule == load(ROOT / 'rule.json')['chosen']
    plan = dict(analysis='POSTHOC_FROZEN_RULE_HARM', summary_sha256=SUMMARY_SHA, rule_sha256=RULE_SHA,
                script_sha256=sha(Path(__file__)), source_count=9,
                metrics=['covered', 'text_changed', 'improved', 'harmed', 'ties', 'positive_contribution', 'negative_contribution', 'finite_set_loss_bound'],
                allowed_labels='previously scored D_search only', new_fit=0, new_gpu=0, llm_calls=0,
                scope='No rule reselection; no independent validation or generalization claim; no confidence interval over dependent predictions.')
    with (ROOT / 'harm-plan.json').open('x') as stream:
        json.dump(plan, stream, sort_keys=True, indent=2)
        stream.write('\n')
    sys.path.insert(0, str(OLD))
    import task_feedback_real_20261001 as engine
    engine.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    task = MLEBenchTask(RunConfig.load_from_json(OLD / 'configs/11.json').task)
    spec = task._search_only_module.SPEC['tweet-sentiment-extraction']
    private = BASE / spec.get('source', spec.get('view')) / 'private/dsearch.csv'
    truth_rows, public_rows = csvrows(private), csvrows(PUBLIC / 'test.csv')
    truth = {r['textID']: r['selected_text'] for r in truth_rows}
    inputs = {r['textID']: r for r in public_rows}
    assert len(truth) == len(truth_rows) == len(inputs) == len(public_rows) and set(inputs) == set(truth)
    result, distinct = [], {}
    for number, row in enumerate(summary['rows']):
        item = {k: row[k] for k in ('batch', 'index', 'arm', 'seed', 'source_sha256')}
        item.update(endpoint_number=number, status='MISSING', decomposition=None)
        if row['source'] is not None:
            source = Path(row['source'])
            assert sha(source) == row['source_sha256']
            original_rows = csvrows(source)
            original = {r['textID']: r['selected_text'] for r in original_rows}
            assert len(original) == len(original_rows) == len(inputs) and set(original) == set(inputs)
            changed = csvrows(ROOT / f'prediction-{number}.private.csv')
            amended = {r['textID']: r['selected_text'] for r in changed}
            assert len(amended) == len(changed) == len(inputs) and set(amended) == set(inputs)
            keys = sorted(inputs)
            take = [inputs[k][rule['column']] == rule['value'] for k in keys]
            expected = {k: inputs[k]['text'] if inputs[k][rule['column']] == rule['value'] else original[k] for k in keys}
            assert amended == expected
            a = [similarity(truth[k], original[k]) for k in keys]
            b = [similarity(truth[k], amended[k]) for k in keys]
            d = decompose(a, b, take, [original[k] != amended[k] for k in keys])
            assert math.isclose(statistics.mean(a), row['baseline'], abs_tol=1e-12)
            assert math.isclose(statistics.mean(b), row['rule_score'], abs_tol=1e-12)
            assert math.isclose(d['net_change'], row['difference'], abs_tol=1e-12)
            item.update(status='SCORED', decomposition=d)
            if row['source_sha256'] in distinct:
                assert distinct[row['source_sha256']] == d
            distinct[row['source_sha256']] = d
        result.append(item)
    assert len(distinct) == 6
    out = dict(plan_sha256=sha(ROOT / 'harm-plan.json'), rows=result, planned_endpoints=9,
               scored_endpoints=7, missing_endpoints=2, distinct_predictions=6,
               distinct_with_harmed_rows=sum(d['harmed_rows'] > 0 for d in distinct.values()),
               distinct_with_positive_net=sum(d['net_change'] > 0 for d in distinct.values()),
               scope=plan['scope'])
    assert sha(ROOT / 'summary.json') == SUMMARY_SHA and sha(ROOT / 'rule.json') == RULE_SHA
    with (ROOT / 'harm-review.json').open('x') as stream:
        json.dump(out, stream, sort_keys=True, indent=2)
        stream.write('\n')
    print(json.dumps(out, sort_keys=True))


if __name__ == '__main__':
    run()
