"""Independent raw prediction/truth recomputation and flat aggregate export."""
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

B = Path('/research/d7/spc/yzyang4')
R = B / 'task-feedback-public-rule-20261002-v1'
P = B / 'tweet-search-only-20260927-a4d1/public'
O = B / 'task-feedback-real-20261001-v6'


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score(x, y):
    x, y = dict.fromkeys(x.lower().split()), dict.fromkeys(y.lower().split())
    total = len(dict.fromkeys(list(x) + list(y)))
    return sum(t in y for t in x) / total if total else 0.0


def main():
    expected = read(R / 'harm-review.json')
    plan = read(R / 'harm-plan.json')
    assert sha(R / 'harm-plan.json') == expected['plan_sha256']
    assert sha(R / 'summary.json') == plan['summary_sha256']
    assert sha(R / 'rule.json') == plan['rule_sha256']
    assert sha(Path(__file__).with_name('task_feedback_rule_harm_20261002.py')) == plan['script_sha256']
    original = read(R / 'summary.json')
    rule = read(R / 'rule.json')['chosen']
    inputs = {v['textID']: v for v in rows(P / 'test.csv')}
    sys.path.insert(0, str(O))
    import task_feedback_real_20261001 as engine
    engine.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    task = MLEBenchTask(RunConfig.load_from_json(O / 'configs/11.json').task)
    spec = task._search_only_module.SPEC['tweet-sentiment-extraction']
    truth = {v['textID']: v['selected_text'] for v in rows(B / spec.get('source', spec.get('view')) / 'private/dsearch.csv')}
    assert inputs.keys() == truth.keys()
    n = len(truth)
    exported, unique = [], {}
    for i, (source, report) in enumerate(zip(original['rows'], expected['rows'])):
        assert i == report['endpoint_number']
        flat = {k: v for k, v in report.items() if k != 'decomposition'}
        if source['source'] is None:
            assert report['status'] == 'MISSING' and report['decomposition'] is None
            exported.append(flat)
            continue
        predfile = Path(source['source'])
        assert sha(predfile) == source['source_sha256']
        before = {v['textID']: v['selected_text'] for v in rows(predfile)}
        after = {v['textID']: v['selected_text'] for v in rows(R / f'prediction-{i}.private.csv')}
        assert before.keys() == after.keys() == truth.keys()
        pos, neg, delta, floor, target_a, target_b = [], [], [], [], [], []
        changed = 0
        for key, y in truth.items():
            take = inputs[key][rule['column']] == rule['value']
            wanted = inputs[key]['text'] if take else before[key]
            assert after[key] == wanted
            a, b = score(before[key], y), score(after[key], y)
            diff = b - a
            pos.append(max(diff, 0)); neg.append(min(diff, 0)); delta.append(diff)
            changed += before[key] != after[key]
            if take:
                target_a.append(a); target_b.append(b); floor.append(b - 1)
            else:
                assert before[key] == after[key]
        actual = dict(rows=n, covered_rows=len(target_a), changed_text_rows=changed,
                      improved_rows=sum(d > 1e-12 for d in delta), harmed_rows=sum(d < -1e-12 for d in delta),
                      metric_ties=sum(abs(d) <= 1e-12 for d in delta), positive_contribution=sum(pos)/n,
                      negative_contribution=sum(neg)/n, net_change=sum(delta)/n,
                      covered_rule_mean=sum(target_b)/len(target_b), covered_baseline_mean=sum(target_a)/len(target_a),
                      finite_set_worst_incumbent_difference=sum(floor)/n, non_target_predictions_unchanged=True)
        for key, value in actual.items():
            assert math.isclose(value, report['decomposition'][key], rel_tol=0, abs_tol=1e-12), (i, key)
        flat.update(report['decomposition'])
        exported.append(flat)
        unique[source['source_sha256']] = actual
    assert len(exported) == 9 and len(unique) == 6
    assert expected['distinct_with_harmed_rows'] == sum(v['harmed_rows'] > 0 for v in unique.values())
    assert expected['distinct_with_positive_net'] == sum(v['net_change'] > 0 for v in unique.values())
    fields = sorted(set().union(*(r.keys() for r in exported)))
    with (R / 'harm-rows.csv').open('x', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(exported)
    result = dict(status='PASS', review_sha256=sha(R / 'harm-review.json'), plan_sha256=sha(R / 'harm-plan.json'),
                  export_sha256=sha(R / 'harm-rows.csv'), verified_endpoints=7, missing=2, distinct_predictions=len(unique),
                  source_script_sha256=plan['script_sha256'], verifier_script_sha256=sha(Path(__file__)),
                  scope='Independent arithmetic verification, not independent data or prospective replication.')
    with (R / 'harm-verification.json').open('x') as f:
        json.dump(result, f, sort_keys=True, indent=2); f.write('\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
