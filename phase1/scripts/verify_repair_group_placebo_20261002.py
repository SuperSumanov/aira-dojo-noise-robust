"""Read-only independent replay of the fixed descriptive random-group check.

Uses sorted negative predictions / binary search instead of producer rank sums.
No new grouping choice, fit, candidate execution, or protected data access.
"""
import csv
import hashlib
import json
import math
import os
import statistics
import sys
from pathlib import Path

B = Path('/research/d7/spc/yzyang4')
SOURCE = B / 'repair-opportunity-20261002-v1'
ROOT = SOURCE / 'group-placebo-v1'
TASK = 'random-acts-of-pizza'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_bytes())
def rows(p):
    with p.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))
def close(a, b):
    assert math.isclose(float(a), float(b), rel_tol=1e-10, abs_tol=1e-11)


def main():
    os.umask(0o077)
    assert sha(ROOT/'plan.json') == '6e9e7a7f4ee3c4dfc809e24e0bbd0e80014790de2e7d6a743ad6a7b69576847f'
    assert sha(ROOT/'replicates.csv') == '303de257e560d0fc70c57827b18922d1c4f675772684429a64557f98fc07c7fb'
    assert sha(SOURCE/'summary.json') == 'c714d7daf46ed431f87a7d0428a60a188613b7452541b932b9e7ad20dfb37139'
    import numpy as np
    old = B/'task-feedback-real-20261001-v6'
    sys.path.insert(0, str(old))
    import task_feedback_real_20261001 as runtime
    runtime.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    index = next(r['index'] for r in read(old/'plan.json')['schedule'] if r['task'] == TASK)
    task = MLEBenchTask(RunConfig.load_from_json(old/'configs'/f'{index}.json').task)
    spec = task._search_only_module.SPEC[TASK]
    truth_path = B/spec.get('source', spec.get('view'))/'private/dsearch.csv'
    bindings = read(SOURCE/'bindings.private.json')
    for p, h in bindings.items(): assert sha(Path(p)) == h
    assert str(truth_path) in bindings
    truth = rows(truth_path)
    ids = [r['request_id'] for r in truth]
    labels = np.asarray([int(r['requester_received_pizza']) for r in truth])
    train = read(task.public_dir/'train.json')
    public = read(task.public_dir/'test.json')
    lengths = sorted(len((r.get('request_text_edit_aware') or '').split()) for r in train)
    boundaries = [lengths[(len(lengths)-1)//3], lengths[2*(len(lengths)-1)//3]]
    by_id = {r['request_id']: sum(len((r.get('request_text_edit_aware') or '').split()) > c for c in boundaries) for r in public}
    groups = np.asarray([by_id[i] for i in ids])
    positives, negatives = labels == 1, labels == 0

    def auc(p):
        n = np.sort(p[negatives])
        lower = np.searchsorted(n, p[positives], side='left')
        upper = np.searchsorted(n, p[positives], side='right')
        return float((lower+upper).sum()/(2*positives.sum()*negatives.sum()))

    # Deterministic tie test using the actual class mask, without scores.
    close(auc(np.ones(len(labels))), .5)
    close(auc(labels.astype(float)), 1.)
    close(auc(-labels.astype(float)), 0.)
    candidates = [r for r in rows(SOURCE/'pairs.csv') if r['task'] == TASK and r['automatic_guidance'] == 'True' and r['child_valid'] == 'True']
    assert len(candidates) == 15
    def predictions(path):
        assert str(path) in bindings and sha(path) == bindings[str(path)]
        rr = rows(path)
        values = {r['request_id']: float(r['requester_received_pizza']) for r in rr}
        assert len(values) == len(rr) == len(ids) and set(values) == set(ids)
        return np.asarray([values[i] for i in ids])
    pairs = []
    for row in candidates:
        ep = B/row['batch']/f'episode-{row["episode"]}'
        p = predictions(ep/f'action-{row["parent_step"]}/submission.private.csv')
        c = predictions(ep/f'action-{row["step"]}/submission.private.csv')
        close(auc(p), row['parent_utility']); close(auc(c), row['child_utility'])
        pairs.append((p, c, auc(p), auc(c)))
    reference = read(SOURCE/'summary.json')['references'][TASK]['utility']
    def stats(g):
        best = [max(auc(np.where(g == k, c, p)) for k in (0, 1, 2)) for p, c, _, _ in pairs]
        return dict(max_margin=max(best)-reference,
                    above_reference=sum(s > reference+1e-12 for s in best),
                    rescue_worse_child=sum(child < parent-1e-12 and s > parent+1e-12 for s, (_, _, parent, child) in zip(best, pairs)))
    observed = stats(groups)
    expected = rows(ROOT/'replicates.csv')
    assert len(expected) == 1000
    rng = np.random.default_rng(102501)
    replay = []
    for i in range(1000):
        new_groups = groups.copy()
        for label in (0, 1):
            mask = np.flatnonzero(labels == label)
            new_groups[mask] = rng.permutation(groups[mask])
            assert np.array_equal(np.bincount(new_groups[mask], minlength=3), np.bincount(groups[mask], minlength=3))
        values = stats(new_groups)
        assert int(expected[i]['repetition']) == i
        for name, value in values.items(): close(value, expected[i][name])
        replay.append(values)
    summary = read(ROOT/'summary.json')
    for name, value in observed.items():
        wanted = summary['results'][name]
        close(value, wanted['observed'])
        vector = [v[name] for v in replay]
        close(statistics.median(vector), wanted['random_median'])
        close(statistics.variance(vector), wanted['random_variance'])
        close(np.quantile(vector, .025), wanted['random_q025'])
        close(np.quantile(vector, .975), wanted['random_q975'])
        assert sum(v >= value-1e-12 for v in vector) == wanted['random_at_least_observed']
    receipt = dict(status='PASS', scope='descriptive check only, not new evidence of method benefit',
                   replayed_replicates=1000, candidates=15, groups=3,
                   source_sha256=sha(Path(__file__)), plan_sha256=sha(ROOT/'plan.json'),
                   summary_sha256=sha(ROOT/'summary.json'), replicates_sha256=sha(ROOT/'replicates.csv'),
                   input_bindings_checked=len(bindings), gpu=0, api_calls=0, fits=0)
    with (ROOT/'verification.json').open('x') as f:
        json.dump(receipt, f, sort_keys=True, indent=2); f.write('\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__': main()
